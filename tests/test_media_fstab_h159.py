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

"""H159 tests — ``media/fstab.py`` validates on add, gates save, hardens media.

The standard flagged ``FstabManager.add`` as **detect-but-don't-fail-closed**
(H72/H170 family): it appended any entry without running ``FstabValidator``;
``make_removable_entry`` omitted hardening; and ``save()`` wrote ``/etc/fstab``
with no capability gate.

The fix: (1) ``add()`` runs the validator and raises ``ValueError`` on
*error*-severity issues (fail-closed), returning warnings, with a
``validate=False`` escape hatch; (2) ``save()`` requires ``fs.admin`` via the
zero-trust capability gate; (3) ``make_removable_entry`` adds
``nosuid,nodev,noexec`` by default.

These tests pin the corrected behaviour.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.capability_gate import CAP_FS_ADMIN, gate  # noqa: E402
from kernel.capability_manager import CapabilityManager  # noqa: E402
from media.fstab import (  # noqa: E402
    FstabEntry,
    FstabManager,
    make_removable_entry,
)

FSTAB_PY = ROOT / "media" / "fstab.py"


class TestAddValidates(unittest.TestCase):
    """``add()`` fails closed on invalid entries (H159)."""

    def test_empty_device_raises(self):
        mgr = FstabManager(simulate=True)
        with self.assertRaises(ValueError):
            mgr.add(FstabEntry("", "/media/usb0", "vfat"))
        self.assertEqual(mgr.count, 0)

    def test_empty_mount_point_raises(self):
        mgr = FstabManager(simulate=True)
        with self.assertRaises(ValueError):
            mgr.add(FstabEntry("/dev/sdb1", "", "vfat"))
        self.assertEqual(mgr.count, 0)

    def test_conflicting_options_raise(self):
        mgr = FstabManager(simulate=True)
        with self.assertRaises(ValueError):
            mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "user,nouser"))

    def test_validate_false_is_escape_hatch(self):
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("", "/media/usb0", "vfat"), validate=False)
        self.assertEqual(mgr.count, 1)

    def test_valid_entry_accepted(self):
        mgr = FstabManager(simulate=True)
        issues = mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "user,noauto"))
        self.assertEqual(mgr.count, 1)
        self.assertIsInstance(issues, list)

    def test_duplicate_mount_point_warns_not_raises(self):
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat"))
        # Same mount point, different device -> warning, not error.
        issues = mgr.add(FstabEntry("/dev/sdz", "/media/usb0", "vfat"))
        self.assertTrue(any(not i.is_error for i in issues))
        self.assertEqual(mgr.count, 2)

    def test_comment_entry_skips_validation(self):
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("# a comment", "", comment="# a comment"))
        self.assertEqual(mgr.count, 1)


class TestMakeRemovableHardened(unittest.TestCase):
    """``make_removable_entry`` applies hardening by default (H159)."""

    def test_hardened_by_default(self):
        e = make_removable_entry("/dev/sdb1", "/media/usb0", uid=1000)
        self.assertTrue({"nosuid", "nodev", "noexec"} <= e.option_set)

    def test_harden_false_omits(self):
        e = make_removable_entry("/dev/sdb1", "/media/usb0", harden=False)
        self.assertNotIn("noexec", e.option_set)
        self.assertNotIn("nosuid", e.option_set)

    def test_core_options_preserved(self):
        e = make_removable_entry("/dev/sdb1", "/media/usb0", uid=1000)
        self.assertTrue(e.is_user_mount)
        self.assertTrue(e.is_noauto)
        self.assertEqual(e.get_option("uid"), "1000")

    def test_iso9660_readonly(self):
        e = make_removable_entry("/dev/sr0", "/media/cdrom", fs_type="iso9660")
        self.assertIn("ro", e.option_set)


class TestSaveGated(unittest.TestCase):
    """``save()`` requires ``fs.admin`` once a manager is wired (H159)."""

    def setUp(self):
        self._snapshot = gate.snapshot()

    def tearDown(self):
        gate.restore(self._snapshot)

    def test_permissive_without_manager(self):
        gate.unwire()
        gate.set_strict(False)
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat"))
        self.assertTrue(mgr.save())

    def test_denied_without_capability(self):
        cm = CapabilityManager()
        cm.register(7777)
        gate.wire(cm, principal=7777)  # registered but NOT granted fs.admin
        mgr = FstabManager(simulate=True)
        with self.assertRaises(PermissionError):
            mgr.save()

    def test_allowed_with_capability(self):
        cm = CapabilityManager()
        cm.register(7777)
        cm.grant(7777, CAP_FS_ADMIN)
        gate.wire(cm, principal=7777)
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat"))
        self.assertTrue(mgr.save())


class TestSourceInvariants(unittest.TestCase):
    def test_source_pins(self):
        src = FSTAB_PY.read_text(encoding="utf-8")
        self.assertIn("gate.require(CAP_FS_ADMIN)", src)
        self.assertIn("validate: bool = True", src)
        self.assertIn('opts.extend(["nosuid", "nodev", "noexec"])', src)


class TestSelftest(unittest.TestCase):
    def test_fstab_selftest(self):
        from media import fstab
        self.assertTrue(fstab._selftest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
