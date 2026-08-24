# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Tests for the UmerOS /lib hierarchy implementation.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib import LibHierarchyManager
from lib.kernel_modules import DEFAULT_KERNEL_VERSION, KernelModuleManager
from lib.library_manager import LibraryManager


class TestLibHierarchyManager(unittest.TestCase):
    def test_audit_reports_missing_essential_libraries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lib").mkdir()
            manager = LibHierarchyManager(root=str(root), alternate_qualifiers=())

            report = manager.audit()

            self.assertFalse(report.ok)
            messages = "\n".join(issue.message for issue in report.errors)
            self.assertIn("libc.so.*", messages)
            self.assertIn("ld*", messages)

    def test_bootstrap_materialises_tldp_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = LibHierarchyManager(root=str(root), alternate_qualifiers=("32", "64"))

            stats = manager.bootstrap(prefer_symlink=False)
            report = manager.audit()

            self.assertTrue(report.ok, [issue.to_dict() for issue in report.errors])
            self.assertGreater(stats["essential_libraries"], 0)
            self.assertGreaterEqual(stats["module_maps"], 4)
            self.assertTrue((root / "lib" / "libc.so.6").exists())
            self.assertTrue((root / "lib" / "ld-2.31.so").exists())
            self.assertTrue((root / "lib" / "cpp").exists())
            self.assertTrue((root / "lib" / "modules" / DEFAULT_KERNEL_VERSION / "modules.dep").exists())
            self.assertTrue((root / "lib" / "modules" / DEFAULT_KERNEL_VERSION / "pcimap").exists())
            self.assertTrue((root / "lib" / "modules" / DEFAULT_KERNEL_VERSION / "usbmap").exists())
            self.assertTrue((root / "lib" / "modules" / DEFAULT_KERNEL_VERSION / "isapnpmap.dep").exists())
            self.assertTrue((root / "lib" / "iptables").is_dir())
            self.assertTrue((root / "lib" / "kbd").is_dir())
            self.assertTrue((root / "lib" / "security").is_dir())
            self.assertTrue((root / "lib" / "oss").is_dir())
            self.assertTrue((root / "lib" / manager.native_arch_triplet()).is_dir())
            self.assertTrue((root / "lib32" / "libc.so.6").exists())
            self.assertTrue((root / "lib64" / "ld-2.31.so").exists())
            self.assertFalse((root / "lib64" / "cpp").exists())

    def test_cpp_reference_can_use_portable_file_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = LibHierarchyManager(
                root=str(root),
                installed_subsystems=(),
                alternate_qualifiers=(),
            )

            cpp = manager.ensure_cpp_reference(prefer_symlink=False)

            self.assertTrue(cpp.is_file())
            self.assertIn("/usr/bin/cpp", cpp.read_text(encoding="utf-8"))
            self.assertTrue(manager.is_cpp_reference())


class TestLibraryManagerPattern(unittest.TestCase):
    def test_find_library_by_pattern_uses_fnmatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_dir = Path(tmp) / "lib"
            lib_dir.mkdir()
            (lib_dir / "libc.so.6").write_text("stub", encoding="utf-8")
            (lib_dir / "libm.so.6").write_text("stub", encoding="utf-8")
            (lib_dir / "libcrypto.so.3").write_text("stub", encoding="utf-8")

            manager = LibraryManager(lib_path=str(lib_dir))
            matches = {lib.name for lib in manager.find_library_by_pattern("lib?.so.*")}

            self.assertEqual(matches, {"libc.so.6", "libm.so.6"})


class TestKernelModuleCompressedFiles(unittest.TestCase):
    def test_compressed_kernel_modules_are_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module_path = (
                root
                / "lib"
                / "modules"
                / DEFAULT_KERNEL_VERSION
                / "kernel"
                / "drivers"
                / "net"
                / "e1000e.ko.xz"
            )
            module_path.parent.mkdir(parents=True)
            module_path.write_bytes(b"\xfd7zXZ\x00UmerOS compressed module stub")

            manager = KernelModuleManager(
                lib_path=str(root / "lib"),
                kernel_version=DEFAULT_KERNEL_VERSION,
            )
            modules = manager.get_modules_for_version()
            found = [module for module in modules if module.path == str(module_path)]

            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].name, "e1000e")
            self.assertEqual(found[0].version, DEFAULT_KERNEL_VERSION)


if __name__ == "__main__":
    unittest.main()
