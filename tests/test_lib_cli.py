"""
Tests for the new UmerOS /lib pieces:

* :mod:`lib.libinfo`   - one-shot /lib summary
* :mod:`lib.__main__`  - ``python -m lib`` CLI
* the new ``_selftest()`` functions added to the existing modules

Run with::

    python tests/run_lib_tests.py
    python -m unittest tests.test_lib_cli -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import lib
from lib.libinfo import LibSummary, lib_summary


class TestLibSummary(unittest.TestCase):
    def _make_tree(self, root: Path) -> None:
        """Build a minimal FHS-compliant /lib tree at ``root``."""
        (root / "libc.so.6").write_bytes(b"stub libc")
        (root / "ld-x86-64.so.2").write_bytes(b"stub ld")
        (root / "libm.so.6").write_bytes(b"stub libm")
        (root / "cpp").write_text("/usr/bin/cpp\n")
        # A kernel-version subdir with the FHS-mandated helper files.
        kv = root / "modules" / "6.6.0-umeros"
        kv.mkdir(parents=True)
        (kv / "modules.dep").write_text("# stub\n")
        (kv / "pcimap").write_text("# stub\n")
        (kv / "usbmap").write_text("# stub\n")
        (kv / "isapnpmap.dep").write_text("# stub\n")
        # The build symlink.
        src = root.parent / "usr" / "src" / "6.6.0-umeros"
        src.mkdir(parents=True, exist_ok=True)
        (kv / "build").symlink_to(src, target_is_directory=True)
        # Subsystem dirs.
        for d in ("iptables", "kbd", "oss", "security", "firmware"):
            (root / d).mkdir()
        # ld.so.conf + ld.so.cache.
        etc = root.parent / "etc"
        etc.mkdir(exist_ok=True)
        (etc / "ld.so.conf").write_text(f"{root.as_posix()}\n")
        (etc / "ld.so.cache").write_bytes(b"glibc-ld.so.cache1\x00\x00")

    def test_lib_summary_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lib"
            root.mkdir()
            self._make_tree(root)
            etc = root.parent / "etc"
            info = lib_summary(
                lib_path=str(root),
                ld_so_conf=str(etc / "ld.so.conf"),
                ld_so_cache=str(etc / "ld.so.cache"),
            )
            self.assertTrue(info.exists)
            self.assertGreaterEqual(info.essential_libraries, 1)
            self.assertIn("6.6.0-umeros", info.kernel_versions)
            self.assertTrue(info.cpp_reference_ok)
            self.assertEqual(info.cpp_target, "/usr/bin/cpp")
            self.assertTrue(info.ld_so_conf_exists)
            self.assertTrue(info.ld_so_cache_exists)
            self.assertTrue(info.kernel_build_link_ok)
            for sub in ("iptables", "kbd", "oss", "security", "firmware"):
                self.assertTrue(getattr(info, f"{sub}_dir"),
                                f"{sub} directory should be detected")
            self.assertTrue(info.pcimap_present)
            self.assertTrue(info.usbmap_present)
            self.assertTrue(info.isapnpmap_present)

    def test_lib_summary_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            info = lib_summary(lib_path=str(Path(tmp) / "does-not-exist"))
            self.assertFalse(info.exists)
            self.assertTrue(info.issues)

    def test_render_table_contains_key_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lib"
            root.mkdir()
            self._make_tree(root)
            text = lib_summary(lib_path=str(root)).render_table()
            self.assertIn("Umer OS /lib summary", text)
            self.assertIn("essential libs", text)
            self.assertIn("kernel modules", text)
            self.assertIn("/lib/cpp", text)
            self.assertIn("ld.so.cache", text)

    def test_as_dict_is_jsonable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lib"
            root.mkdir()
            self._make_tree(root)
            info = lib_summary(lib_path=str(root))
            blob = json.dumps(info.as_dict())
            self.assertIsInstance(blob, str)
            roundtrip = json.loads(blob)
            self.assertEqual(roundtrip["lib_path"], str(root))

    def test_alternate_qualifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lib"
            root.mkdir()
            (root / "libc.so.6").write_bytes(b"x")
            (Path(tmp) / "lib32").mkdir()
            (Path(tmp) / "lib64").mkdir()
            info = lib_summary(lib_path=str(root))
            self.assertIn("32", info.alternate_qualifiers)
            self.assertIn("64", info.alternate_qualifiers)

    def test_no_cpp_creates_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lib"
            root.mkdir()
            (root / "libc.so.6").write_bytes(b"x")
            info = lib_summary(lib_path=str(root))
            self.assertFalse(info.cpp_reference_ok)
            self.assertTrue(any("cpp" in i.lower() for i in info.issues))

    def test_libinfo_re_exported_from_package(self):
        self.assertIs(lib.lib_summary, lib_summary)
        self.assertIs(lib.LibSummary, LibSummary)


class TestLibMain(unittest.TestCase):
    def test_help_prints_usage(self):
        from lib.__main__ import main
        rc = main(["help"])
        self.assertEqual(rc, 0)

    def test_unknown_command_is_error(self):
        from lib.__main__ import main
        rc = main(["definitely-not-a-real-command"])
        self.assertEqual(rc, 2)

    def test_list_command_runs(self):
        from lib.__main__ import main
        rc = main(["list"])
        self.assertEqual(rc, 0)

    def test_info_command_runs(self):
        from lib.__main__ import main
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lib"
            root.mkdir()
            rc = main(["info", str(root)])
            # Missing /lib will report issues but the command should
            # still return a non-zero exit; we just want it to not
            # crash.
            self.assertIn(rc, (0, 1))

    def test_selftest_command(self):
        from lib.__main__ import main
        rc = main(["selftest"])
        self.assertEqual(rc, 0)


class TestNewSelftests(unittest.TestCase):
    """The new ``_selftest()`` functions added to existing modules."""

    def test_elf_parser_selftest(self):
        from lib.elf_parser import _selftest
        self.assertTrue(_selftest())

    def test_library_manager_selftest(self):
        from lib.library_manager import _selftest
        self.assertTrue(_selftest())

    def test_essential_libs_selftest(self):
        from lib.essential_libs import _selftest
        self.assertTrue(_selftest())

    def test_ldd_selftest(self):
        from lib.ldd import _selftest
        self.assertTrue(_selftest())

    def test_dynamic_linker_selftest(self):
        from lib.dynamic_linker import _selftest
        self.assertTrue(_selftest())

    def test_libinfo_selftest(self):
        from lib.libinfo import _selftest
        self.assertTrue(_selftest())


class TestCLIInvocation(unittest.TestCase):
    """End-to-end CLI through ``python -m lib``."""

    def test_selftest_via_subprocess(self):
        proc = subprocess.run(
            [sys.executable, "-m", "lib", "selftest"],
            cwd=str(_ROOT),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0,
                         f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}")
        self.assertIn("modules passed", proc.stdout)

    def test_info_via_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lib"
            root.mkdir()
            (root / "libc.so.6").write_bytes(b"x")
            proc = subprocess.run(
                [sys.executable, "-m", "lib", "info", str(root)],
                cwd=str(_ROOT),
                capture_output=True, text=True, timeout=60,
            )
            self.assertIn("Umer OS /lib summary", proc.stdout)

    def test_help_via_subprocess(self):
        proc = subprocess.run(
            [sys.executable, "-m", "lib", "help"],
            cwd=str(_ROOT),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Umer OS /lib", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
