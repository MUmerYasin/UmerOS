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
Tests for the /mnt subsystem (mnt/).

Covers:
  * AuditLog queries and the new convenience loggers (log_remount,
    log_mount_create, log_mount_remove, recent(0)).
  * Fstab.list_under segment-aware prefix matching (no /mntfoo match).
  * MountPointManager.stale tolerance of non-directory paths,
    cleanup audit logging, and get_summary().
  * MountManager audit wiring (mount/umount/remount/noauto-skip/
    permission-deny) and umount_all().
  * UserMountManager: mtab ownership round-trip, the fstab
    user/users permission check, the noauto user-mount fix, and
    audit wiring.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from mnt.audit import AuditLog                            # noqa: E402
from mnt.fstab import Fstab                               # noqa: E402
from mnt.mount_ops import MountError, MountManager        # noqa: E402
from mnt.mount_point import MountPointManager             # noqa: E402
from mnt.user_mount import UserMountManager               # noqa: E402
from core.capability_gate import gate                     # noqa: E402


def _wired_fstab(tmp):
    """Write a user-mountable fstab inside *tmp*.

    Returns (fstab_path, mnt_root, usb_mount_point, floppy_mount_point).
    """
    fstab_path = os.path.join(tmp, "fstab")
    mnt = os.path.join(tmp, "mnt")
    usb = os.path.join(mnt, "usb")
    floppy = os.path.join(mnt, "floppy")
    os.makedirs(usb, exist_ok=True)
    os.makedirs(floppy, exist_ok=True)
    with open(fstab_path, "w", encoding="utf-8") as fh:
        fh.write(
            f"/dev/sdb1 {usb} vfat user,noauto,uid=1000,gid=100 0 0\n"
            f"/dev/fd0 {floppy} msdos user,noauto 0 0\n"
            "/dev/sda1 / ext4 defaults 0 1\n"
        )
    return fstab_path, mnt, usb, floppy


class TestAuditLog(unittest.TestCase):
    """AuditLog queries and the new convenience loggers."""

    def _audit(self, tmp):
        return AuditLog(os.path.join(tmp, "audit.jsonl"))

    def test_recent_zero_and_negative_return_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = self._audit(tmp)
            audit.log_mount("/dev/sdb1", "/mnt/usb", "vfat")
            self.assertEqual(audit.recent(0), [])
            self.assertEqual(audit.recent(-1), [])

    def test_recent_limits_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = self._audit(tmp)
            for i in range(5):
                audit.log_mount(f"/dev/sdb{i}", f"/mnt/usb{i}", "vfat")
            self.assertEqual(len(audit.recent(3)), 3)
            self.assertEqual(len(audit.recent(10)), 5)

    def test_log_remount(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = self._audit(tmp)
            audit.log_remount("/mnt/usb", "ro", device="/dev/sdb1")
            events = audit.for_mount_point("/mnt/usb")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].event, "remount")
            self.assertEqual(events[0].options, "ro")
            self.assertEqual(events[0].device, "/dev/sdb1")

    def test_log_mount_create_and_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = self._audit(tmp)
            audit.log_mount_create(
                "/mnt/usb", device="/dev/sdb1", fstype="vfat")
            audit.log_mount_remove("/mnt/usb")
            events = audit.for_mount_point("/mnt/usb")
            self.assertEqual(
                [e.event for e in events],
                ["mount_point_create", "mount_point_remove"],
            )


class TestFstabListUnder(unittest.TestCase):
    """list_under must be segment-aware (/mnt must not match /mntfoo)."""

    SAMPLE = (
        "/dev/sda1 / ext4 defaults 0 1\n"
        "/dev/sdb1 /mnt/usb vfat user,noauto 0 0\n"
        "/dev/sdc1 /mntfoo ext4 defaults 0 0\n"
        "/dev/sdd1 /mnt/floppy msdos user,noauto 0 0\n"
    )

    def test_mnt_prefix_excludes_siblings(self):
        fstab = Fstab.from_string(self.SAMPLE)
        entries = fstab.list_under("/mnt")
        self.assertEqual(len(entries), 2)
        self.assertNotIn("/mntfoo", [e.mount_point for e in entries])

    def test_trailing_slash_is_equivalent(self):
        fstab = Fstab.from_string(self.SAMPLE)
        self.assertEqual(len(fstab.list_under("/mnt/")), 2)


class TestMountPointStale(unittest.TestCase):
    """stale must tolerate a tracked path replaced by a non-directory."""

    def test_stale_survives_non_directory_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            mnt = os.path.join(tmp, "mnt")
            os.makedirs(mnt)
            mgr = MountPointManager(mnt)
            mp = mgr.create("usb")
            os.rmdir(mp.path)
            with open(mp.path, "w", encoding="utf-8") as fh:
                fh.write("not a directory anymore")
            mgr._max_age = 0
            stale = mgr.stale  # must not raise NotADirectoryError
            self.assertIn(mp.path, [x.path for x in stale])


class TestMountPointAuditWiring(unittest.TestCase):
    """create/remove/cleanup log to the audit trail."""

    def test_create_remove_log_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            mnt = os.path.join(tmp, "mnt")
            os.makedirs(mnt)
            audit = AuditLog(os.path.join(tmp, "audit.jsonl"))
            mgr = MountPointManager(mnt, audit=audit)
            mp = mgr.create("usb", device="/dev/sdb1", purpose="USB drive")
            mgr.remove(mp.path)
            events = audit.for_mount_point(mp.path)
            self.assertEqual(
                [e.event for e in events],
                ["mount_point_create", "mount_point_remove"],
            )

    def test_cleanup_stale_logs_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            mnt = os.path.join(tmp, "mnt")
            os.makedirs(mnt)
            audit = AuditLog(os.path.join(tmp, "audit.jsonl"))
            mgr = MountPointManager(mnt, audit=audit)
            mgr.create("temp")
            mgr._max_age = 0
            removed = mgr.cleanup_stale()
            self.assertEqual(len(removed), 1)
            cleanups = [r for r in audit.records if r.event == "cleanup"]
            self.assertEqual(len(cleanups), 1)
            self.assertIn(removed[0], cleanups[0].extra["removed_paths"])

    def test_get_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            mnt = os.path.join(tmp, "mnt")
            os.makedirs(mnt)
            mgr = MountPointManager(mnt)
            mp = mgr.create("usb")
            mgr.mark_mounted(mp.path)
            summary = mgr.get_summary()
            self.assertEqual(summary["mnt_root"], mnt)
            self.assertEqual(summary["mounted"], 1)
            self.assertEqual(summary["mounted_points"], [mp.path])


class TestMountOpsAuditWiring(unittest.TestCase):
    """MountManager logs mount/umount/remount and permission denials."""

    def _mgr(self, tmp, **kwargs):
        audit = AuditLog(os.path.join(tmp, "audit.jsonl"))
        kwargs.setdefault("proc_mounts", "/nonexistent")
        kwargs.setdefault("enforce_noauto", False)
        kwargs["audit"] = audit
        return MountManager(**kwargs), audit

    def test_mount_umount_remount_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr, audit = self._mgr(tmp)
            mp = os.path.join(tmp, "usb")
            os.makedirs(mp)
            mgr.mount("/dev/sdb1", mp, "vfat", "rw")
            mgr.remount(mp, "ro")
            mgr.umount(mp)
            events = audit.for_mount_point(mp)
            self.assertEqual(
                [e.event for e in events],
                ["mount", "remount", "unmount"],
            )
            self.assertEqual(audit.stats["mounts"], 1)
            self.assertEqual(audit.stats["unmounts"], 1)
            self.assertEqual(events[1].options, "ro")

    def test_noauto_skip_is_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr, audit = self._mgr(tmp, enforce_noauto=True)
            mp = os.path.join(tmp, "usb")
            os.makedirs(mp)
            mgr.mount("/dev/sdb1", mp, "vfat", "noauto")
            self.assertFalse(mgr.is_mounted(mp))
            events = audit.for_mount_point(mp)
            self.assertEqual(len(events), 1)
            self.assertIn("noauto", events[0].message)

    def test_permission_deny_is_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr, audit = self._mgr(tmp)
            mp = os.path.join(tmp, "usb")
            os.makedirs(mp)
            state = gate.snapshot()
            gate.set_strict(True)
            try:
                with self.assertRaises(PermissionError):
                    mgr.mount("/dev/sdb1", mp, "vfat")
            finally:
                gate.restore(state)
            self.assertEqual(len(audit.failed()), 1)
            self.assertEqual(audit.stats["permission_denials"], 1)

    def test_umount_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr, audit = self._mgr(tmp)
            mp1 = os.path.join(tmp, "one")
            mp2 = os.path.join(tmp, "two")
            os.makedirs(mp1)
            os.makedirs(mp2)
            mgr.mount("/dev/sdb1", mp1, "vfat")
            mgr.mount("/dev/sdb2", mp2, "vfat")
            removed = mgr.umount_all()
            self.assertEqual(len(removed), 2)
            self.assertEqual(mgr.stats["total"], 0)


class TestMtabRoundTrip(unittest.TestCase):
    """mtab ownership (mounted_by/uid) survives a save/load cycle."""

    def test_ownership_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            fstab_path, mnt, usb, floppy = _wired_fstab(tmp)
            mtab_path = os.path.join(tmp, "mtab")
            mgr = UserMountManager(
                fstab_path=fstab_path, mtab_path=mtab_path)
            mgr.user_mount("alice", "/dev/sdb1", usb, "vfat", uid=1000)

            reloaded = UserMountManager(
                fstab_path=fstab_path, mtab_path=mtab_path)
            self.assertTrue(reloaded.can_user_umount("alice", usb))
            self.assertFalse(reloaded.can_user_umount("bob", usb))
            entry = reloaded.find_mounted_by(usb)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.mounted_by, "alice")
            self.assertEqual(entry.uid, 1000)


class TestUserMountPermission(unittest.TestCase):
    """user_mount enforces the fstab user/users permission."""

    def test_mount_umount_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            fstab_path, mnt, usb, floppy = _wired_fstab(tmp)
            mgr = UserMountManager(
                fstab_path=fstab_path,
                mtab_path=os.path.join(tmp, "mtab"),
            )
            mgr.user_mount("alice", "/dev/sdb1", usb, "vfat", uid=1000)
            self.assertTrue(mgr._mount_mgr.is_mounted(usb))
            mgr.user_umount("alice", usb)
            self.assertFalse(mgr._mount_mgr.is_mounted(usb))

    def test_mount_denied_without_user_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            fstab_path, mnt, usb, floppy = _wired_fstab(tmp)
            mgr = UserMountManager(
                fstab_path=fstab_path,
                mtab_path=os.path.join(tmp, "mtab"),
            )
            # "/" has an fstab entry but no user/noauto options.
            with self.assertRaises(MountError):
                mgr.user_mount("alice", "/dev/sda1", "/", "ext4")

    def test_mount_denied_by_uid_constraint(self):
        with tempfile.TemporaryDirectory() as tmp:
            fstab_path, mnt, usb, floppy = _wired_fstab(tmp)
            mgr = UserMountManager(
                fstab_path=fstab_path,
                mtab_path=os.path.join(tmp, "mtab"),
            )
            with self.assertRaises(MountError):
                mgr.user_mount("alice", "/dev/sdb1", usb, "vfat", uid=999)


class TestUserMountAuditWiring(unittest.TestCase):
    """user_mount/user_umount log USER_MOUNT/USER_UNMOUNT events."""

    def _mgr(self, tmp):
        fstab_path, mnt, usb, floppy = _wired_fstab(tmp)
        audit = AuditLog(os.path.join(tmp, "audit.jsonl"))
        mgr = UserMountManager(
            fstab_path=fstab_path,
            mtab_path=os.path.join(tmp, "mtab"),
            audit=audit,
        )
        return mgr, audit, usb

    def test_user_mount_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr, audit, usb = self._mgr(tmp)
            mgr.user_mount("alice", "/dev/sdb1", usb, "vfat", uid=1000)
            events = [r for r in audit.records if r.event == "user_mount"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].user, "alice")
            self.assertEqual(events[0].mount_point, usb)
            self.assertEqual(events[0].uid, 1000)

    def test_denied_user_mount_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr, audit, usb = self._mgr(tmp)
            with self.assertRaises(MountError):
                mgr.user_mount("alice", "/dev/sdb1", usb, "vfat", uid=999)
            self.assertEqual(audit.stats["permission_denials"], 1)


if __name__ == "__main__":
    unittest.main()
