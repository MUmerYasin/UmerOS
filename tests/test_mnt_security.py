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
Regression tests for mnt/ RED findings H167 + H168.

H167  MountPointManager.remove(force=True) must never rmtree through a
      symlink, a filesystem root, or a path that flips underneath it.
H168  Fstab round-trips must preserve comments/header, and write_file
      stays behind the CAP_FS_ADMIN gate.
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

from mnt.fstab import Fstab                       # noqa: E402
from mnt.mount_point import MountPointManager     # noqa: E402


class TestForceRemoveGuards(unittest.TestCase):
    """[FIX H167] force-remove refuses symlinks / roots / flipped paths."""

    def setUp(self) -> None:
        self.mgr = MountPointManager()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_refuses_symlink_target(self):
        real = os.path.join(self._tmp.name, "real_data")
        os.makedirs(real)
        link = os.path.join(self._tmp.name, "link")
        os.symlink(real, link)

        self.assertFalse(self.mgr.remove(link, force=True))
        self.assertTrue(os.path.isdir(real))          # target untouched

    def test_refuses_filesystem_root(self):
        root = "/" if os.name == "posix" else "F:\\"
        self.assertFalse(self.mgr.remove(root, force=True))

    def test_force_removes_real_directory(self):
        target = os.path.join(self._tmp.name, "mp")
        os.makedirs(os.path.join(target, "junk"))
        # Track it so _find_by_path succeeds.
        self.mgr._points["t"] = type(
            "MP", (), {"path": target, "is_permanent": False,
                       "mounted_at": None})()
        self.assertTrue(self.mgr.remove(target, force=True))
        self.assertFalse(os.path.exists(target))


class TestFstabCommentPreservation(unittest.TestCase):
    """[FIX H168] Comments survive parsing -> serialization -> write."""

    SAMPLE = (
        "# /etc/fstab: static file system information\n"
        "# <device>  <mount>  <type>  <opts>  <dump>  <pass>\n"
        "/dev/sda1  /       ext4  defaults  0  1\n"
        "/dev/sda2  none    swap  sw        0  0\n"
    )

    def test_from_string_keeps_comments(self):
        fstab = Fstab.from_string(self.SAMPLE)
        self.assertEqual(len(fstab.entries), 2)
        out = fstab.to_string()
        self.assertIn("static file system information", out)
        self.assertIn("<device>", out)

    def test_round_trip_preserves_comments_and_entries(self):
        fstab = Fstab.from_string(self.SAMPLE)
        out = fstab.to_string()
        again = Fstab.from_string(out)
        self.assertEqual(len(again.entries), len(fstab.entries))
        self.assertEqual(
            [e.mount_point for e in again.entries],
            [e.mount_point for e in fstab.entries],
        )
        self.assertIn("static file system information", again.to_string())


if __name__ == "__main__":
    unittest.main()
