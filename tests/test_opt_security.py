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
Regression tests for opt/ RED findings H184 + H187.

H187  Generated launcher/wrapper scripts must quote every dynamic token
      (no command injection via command/args/env values) and must reject
      traversal script names and control characters.
H184  Privileged /opt lifecycle ops sit behind core.capability_gate
      (fail-closed when wired / strict).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import core.capability_gate as cg                     # noqa: E402
from opt.package import OptPackage                    # noqa: E402


class TestLauncherScriptInjection(unittest.TestCase):
    """[FIX H187] No shell metacharacter escape from generated scripts."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pkg = OptPackage("victim", "", opt_root=self._tmp.name)

    @staticmethod
    def _read(path):
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    def test_arg_injection_is_quoted(self):
        import shlex
        evil = "; rm -rf / #"
        path = self.pkg.create_launcher_script(
            "app", "/opt/victim/bin/run", [evil])
        exec_line = [ln for ln in self._read(path).splitlines()
                     if ln.startswith("exec ")][0]
        tokens = shlex.split(exec_line)
        # The evil string must survive as ONE argument — the shell never
        # sees a bare ";" separator or extra "rm" command token.
        self.assertIn(evil, tokens)
        self.assertNotIn(";", tokens)
        self.assertNotIn("rm", tokens)
        self.assertEqual(tokens[-1], "$@")

    def test_command_control_chars_rejected(self):
        with self.assertRaises(ValueError):
            self.pkg.create_launcher_script("app", "echo hi\nrm -rf /")

    def test_env_value_cannot_execute(self):
        path = self.pkg.create_wrapper_script(
            "wrap", "/opt/victim/bin/tool",
            environment={"LD_PRELOAD": "$(evil)"},
            pre_args=["--flag;id"],
        )
        text = self._read(path)
        self.assertNotIn('export LD_PRELOAD="$(evil)"', text)
        self.assertNotIn("--flag;id ", text.splitlines()[-1])

    def test_env_key_must_be_identifier(self):
        with self.assertRaises(ValueError):
            self.pkg.create_wrapper_script(
                "wrap", "tool", environment={"BAD-KEY": "1"})

    def test_script_name_traversal_rejected(self):
        for bad in ("../escape.sh", "sub/dir.sh", "..", ""):
            with self.assertRaises(ValueError):
                self.pkg.create_launcher_script(bad, "true")


class TestOptCapGate(unittest.TestCase):
    """[FIX H184] Privileged /opt ops are gated fail-closed when strict."""

    def setUp(self) -> None:
        self._prev_strict = cg.gate.strict
        self.addCleanup(cg.gate.set_strict, self._prev_strict)

    def test_package_remove_gated_strict_mode(self):
        pkg = OptPackage("p", "", opt_root=tempfile.mkdtemp())
        cg.gate.set_strict(True)
        with self.assertRaises(PermissionError):
            pkg.remove()

    def test_manager_install_gated_strict_mode(self):
        from opt.manager import OptManager
        mgr = OptManager()
        cg.gate.set_strict(True)
        with self.assertRaises(PermissionError):
            mgr.install("somepkg")

    def test_manager_remove_gated_strict_mode(self):
        from opt.manager import OptManager
        mgr = OptManager()
        cg.gate.set_strict(True)
        with self.assertRaises(PermissionError):
            mgr.remove("somepkg")


if __name__ == "__main__":
    unittest.main()