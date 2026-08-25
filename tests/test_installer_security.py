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

"""Security regression tests for the Umer OS installer.

Covers the remediation cluster H98/H99/H100/H101/H102/H103:
  * H98  - ``from installer import UmerInstaller`` returns the real class (dead stub gone).
  * H99  - the liability waiver is fail-closed (no silent auto-accept).
  * H100 - a programmatic EULA bypass (``consent_override``) is a privileged action.
  * H101 - rollback refuses to remove an unsafe install root (data-loss guard).
  * H102 - the privileged install / rollback pipeline requires a capability.
  * H103 - copy destinations cannot escape the install root; dotfiles are skipped.
"""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest

import pytest

try:  # Mirror installer.py's import strategy.
    from core.capability_gate import gate
except Exception:  # pragma: no cover
    from capability_gate import gate

from installer.installer import (
    UmerInstaller,
    _is_safe_install_root,
    _safe_join,
)
import installer  # noqa: E402  (triggers installer/__init__.py re-export)


@pytest.fixture(autouse=True)
def _gate_state():
    """Reset the process-global gate so strict-mode tests don't leak."""
    strict_before = getattr(gate, "strict", False)
    gate.unwire()
    try:
        yield
    finally:
        gate.unwire()
        if strict_before:
            gate.set_strict(True)


class TestH98Reexport(unittest.TestCase):

    def test_package_reexports_real_installer(self):
        from installer.installer import UmerInstaller as Real
        self.assertIs(installer.UmerInstaller, Real)

    def test_stub_module_removed(self):
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("installer.install")


class TestH99WaiverFailClosed(unittest.TestCase):

    def test_show_eula_non_interactive_denies(self):
        inst = UmerInstaller(interactive=False)
        self.assertFalse(inst.show_eula())


class TestH101RollbackSafety(unittest.TestCase):

    def test_unsafe_root_refuses(self):
        inst = UmerInstaller(interactive=False)
        inst._state["files_copied"] = True
        inst._install_root = "/"
        # Rollback must refuse to touch the filesystem root; '/etc' is never touched.
        self.assertFalse(inst.rollback())
        self.assertTrue(os.path.isdir(os.path.abspath("/")))  # drive root intact

    def test_unsafe_etc_refuses(self):
        inst = UmerInstaller(interactive=False)
        inst._state["files_copied"] = True
        inst._install_root = "/etc"
        self.assertFalse(inst.rollback())

    def test_helper_rejects_system_paths(self):
        self.assertFalse(_is_safe_install_root(""))
        self.assertFalse(_is_safe_install_root("/"))
        self.assertFalse(_is_safe_install_root("/opt"))
        self.assertFalse(_is_safe_install_root("/etc"))
        self.assertFalse(_is_safe_install_root("/etc/passwd"))
        self.assertFalse(_is_safe_install_root("/home/user/x"))
        self.assertTrue(_is_safe_install_root("/opt/umer_os"))
        self.assertTrue(_is_safe_install_root("/mnt/sdcard/umer"))
        self.assertTrue(_is_safe_install_root(tempfile.mkdtemp()))


class TestH103SafeJoin(unittest.TestCase):

    def test_escape_rejected(self):
        self.assertIsNone(_safe_join("/opt/umer_os", "../etc/passwd"))
        self.assertIsNone(_safe_join("/opt/umer_os", "/etc/passwd"))
        self.assertIsNone(_safe_join("/opt/umer_os", "../../root"))

    def test_safe_accepted(self):
        expected = os.path.normpath(
            os.path.abspath(os.path.join("/opt/umer_os", "boot/x"))
        )
        self.assertEqual(_safe_join("/opt/umer_os", "boot/x"), expected)

    def test_copy_skips_dotfiles_and_stays_in_root(self):
        src = tempfile.mkdtemp()
        dst = tempfile.mkdtemp()
        try:
            for name in ("a.py", ".secret", os.path.join("sub", "b.py")):
                p = os.path.join(src, name)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w") as fh:
                    fh.write("x")
            inst = UmerInstaller(source_dir=src, install_root=dst, interactive=False)
            n = inst.copy_os_files(source=src, dest=dst)
            self.assertEqual(n, 2)  # .secret skipped
            self.assertTrue(os.path.isfile(os.path.join(dst, "a.py")))
            self.assertTrue(os.path.isfile(os.path.join(dst, "sub", "b.py")))
            self.assertFalse(os.path.isfile(os.path.join(dst, ".secret")))
        finally:
            shutil.rmtree(src, ignore_errors=True)
            shutil.rmtree(dst, ignore_errors=True)


class TestH102CapGate(unittest.TestCase):

    def test_run_requires_capability_strict_denies(self):
        src = tempfile.mkdtemp()
        dst = tempfile.mkdtemp()
        bkp = tempfile.mkdtemp()
        try:
            with open(os.path.join(src, "main.py"), "w") as fh:
                fh.write("x")
            inst = UmerInstaller(
                source_dir=src, install_root=dst, backup_dir=bkp, interactive=False
            )
            gate.set_strict(True)
            with self.assertRaises(PermissionError):
                inst.run(consent_override=True)
        finally:
            gate.set_strict(False)
            shutil.rmtree(src, ignore_errors=True)
            shutil.rmtree(dst, ignore_errors=True)
            shutil.rmtree(bkp, ignore_errors=True)

    def test_rollback_requires_capability_strict_denies(self):
        tmp = tempfile.mkdtemp()
        try:
            inst = UmerInstaller(install_root=tmp, interactive=False)
            inst._state["files_copied"] = True
            gate.set_strict(True)
            with self.assertRaises(PermissionError):
                inst.rollback()
        finally:
            gate.set_strict(False)
            shutil.rmtree(tmp, ignore_errors=True)


class TestH100ConsentOverride(unittest.TestCase):

    def test_consent_override_requires_capability_strict_denies(self):
        src = tempfile.mkdtemp()
        dst = tempfile.mkdtemp()
        bkp = tempfile.mkdtemp()
        try:
            inst = UmerInstaller(
                source_dir=src, install_root=dst, backup_dir=bkp, interactive=False
            )
            gate.set_strict(True)
            with self.assertRaises(PermissionError):
                inst.run(consent_override=True)
        finally:
            gate.set_strict(False)
            shutil.rmtree(src, ignore_errors=True)
            shutil.rmtree(dst, ignore_errors=True)
            shutil.rmtree(bkp, ignore_errors=True)

    def test_no_consent_non_interactive_denies(self):
        inst = UmerInstaller(interactive=False)
        self.assertFalse(inst.run(consent_override=False))


if __name__ == "__main__":
    unittest.main()
