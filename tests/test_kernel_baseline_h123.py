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

"""tests — the ``kernel/`` toy/REPL modules are now on the repo baseline.

The standard flagged ten off-baseline modules (`print`/`input()`, no
`from __future__`/logging/tier) that duplicate canonical modules living
elsewhere in the tree.   brought every one of them to the repo baseline
(docstring + tier label, ``from __future__ import annotations``, module
``logging``, no ``print``/``input``) and dropped the dead interactive REPL entry
points, while preserving the public API that live importers rely on
(``kernel.shell_commands`` → ``power_manager`` → ``cpuidle``; the UI's soft
``kernel.qfs`` import).
"""

import importlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FILES = (
    "container_engine",
    "installer",
    "umer_ai",
    "qfs",
    "quantum_sim",
    "cpuidle",
    "power_manager",
    "pqcrypto_",
    "onnxruntime_",
    "setup_umer_os",
)

TIERS = ("[TODAY]", "[EXPERIMENTAL]", "[FUTURE]")


def _src(name: str) -> str:
    return (ROOT / "kernel" / f"{name}.py").read_text(encoding="utf-8")


class TestBaselineCompliance(unittest.TestCase):
    def test_all_have_future_annotations(self):
        for name in FILES:
            with self.subTest(module=name):
                self.assertIn("from __future__ import annotations", _src(name))

    def test_all_have_tier_label(self):
        for name in FILES:
            with self.subTest(module=name):
                self.assertTrue(
                    any(t in _src(name) for t in TIERS),
                    f"{name}.py has no [TODAY]/[EXPERIMENTAL]/[FUTURE] tier label",
                )

    def test_all_have_module_logger(self):
        for name in FILES:
            with self.subTest(module=name):
                self.assertIn("getLogger(", _src(name))

    def test_no_print(self):
        for name in FILES:
            with self.subTest(module=name):
                self.assertEqual(
                    len(re.findall(r"\bprint\(", _src(name))), 0,
                    f"{name}.py still uses print()",
                )

    def test_no_input(self):
        for name in FILES:
            with self.subTest(module=name):
                self.assertEqual(
                    len(re.findall(r"\binput\(", _src(name))), 0,
                    f"{name}.py still uses input()",
                )

    def test_no_stray_shebang(self):
        for name in FILES:
            with self.subTest(module=name):
                self.assertNotIn("#!/usr/bin/env", _src(name))

    def test_gpl_header_first(self):
        for name in FILES:
            with self.subTest(module=name):
                src = _src(name)
                self.assertTrue(src.startswith("# This program is free software"))
                self.assertIn("GNU General Public License", src)


class TestLiveApiPreserved(unittest.TestCase):
    """The modules that real code imports must keep working."""

    def test_power_manager_cpu_idle(self):
        pm = importlib.import_module("kernel.power_manager")
        self.assertTrue(hasattr(pm, "POWER_MANAGER"))
        result = pm.POWER_MANAGER.cpu_idle()
        self.assertIsInstance(result, str)
        self.assertIn("idle", result.lower())

    def test_cpuidle_enter(self):
        ci = importlib.import_module("kernel.cpuidle")
        self.assertIn(ci.cpuidle_enter(), ("C1", "C2", "C3"))

    def test_shell_commands_imports_power_manager(self):
        # This is the live chain that made power_manager/cpuidle non-dead.
        sc = importlib.import_module("kernel.shell_commands")
        self.assertTrue(hasattr(sc, "POWER_MANAGER"))

    def test_qfs_round_trip(self):
        import tempfile

        q = importlib.import_module("kernel.qfs")
        with tempfile.TemporaryDirectory() as d:
            fs = q.QFS(root=d)
            fs.write_file("a.txt", "hello" * 50)
            self.assertEqual(fs.read_file("a.txt"), "hello" * 50)

    def test_all_modules_import_cleanly(self):
        for name in FILES:
            with self.subTest(module=name):
                importlib.import_module(f"kernel.{name}")


class TestNoImportSideEffects(unittest.TestCase):
    """The [FUTURE] reference snippets must not import 3rd-party deps at import."""

    def test_pqcrypto_has_no_import_time_execution(self):
        src = _src("pqcrypto_")
        # The pqcrypto import must be function-local (indented), never top-level,
        # so importing the module neither needs pqcrypto nor generates keys.
        for line in src.splitlines():
            if "import kyber1024" in line:
                self.assertTrue(
                    line.startswith((" ", "\t")),
                    "kyber1024 import must be inside a function, not top-level",
                )
        self.assertIn('if __name__ == "__main__":', src)
        # The __main__ guard runs the demo (and therefore the keygen).
        tail = src.split('if __name__ == "__main__":', 1)[1]
        self.assertIn("demo()", tail)

    def test_onnxruntime_import_is_lazy(self):
        src = _src("onnxruntime_")
        # No top-level `import onnxruntime`.
        for line in src.splitlines():
            self.assertFalse(
                line.startswith("import onnxruntime"),
                "onnxruntime must be imported lazily",
            )


class TestCanonicalCounterpartsDocumented(unittest.TestCase):
    """Each legacy duplicate points at its canonical module."""

    CASES = {
        "container_engine": "compatibility/container_engine.py",
        "installer": "installer/installer.py",
        "umer_ai": "ai/umer_ai.py",
        "qfs": "fs/qfs.py",
        "quantum_sim": "quantum/quantum_sim.py",
    }

    def test_canonical_counterparts_exist(self):
        for legacy, canonical in self.CASES.items():
            with self.subTest(legacy=legacy):
                self.assertTrue(
                    (ROOT / canonical).exists(),
                    f"canonical counterpart missing: {canonical}",
                )
                # The legacy docstring must reference the canonical module.
                stem = Path(canonical).stem
                self.assertIn(stem, _src(legacy))


if __name__ == "__main__":
    unittest.main()
