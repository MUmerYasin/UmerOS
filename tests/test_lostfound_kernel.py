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
Integration tests: kernel <-> lost+found wiring.

Verifies that:
  * UmerKernel creates a root partition with an isolated lost+found.
  * Boot-time mkfs + fsck run correctly.
  * The VFS exposes /lost+found.
  * fsck recovery is reachable from the kernel.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class TestKernelLostFoundIntegration(unittest.TestCase):
    def setUp(self):
        import kernel.umer_kernel as uk
        self.uk = uk
        self.kernel = uk.UmerKernel()

    def test_kernel_has_root_partition(self):
        self.assertIsNotNone(self.kernel.root_partition)
        self.assertEqual(self.kernel.root_partition.mount_point, "/")
        self.assertEqual(self.kernel.root_partition.name, "qfs_root")

    def test_kernel_has_lost_found_manager(self):
        self.assertIsNotNone(self.kernel.lost_found)
        self.assertEqual(self.kernel.lost_found.path, "/lost+found")
        # The manager is owned by the partition (per-partition isolation)
        self.assertIs(
            self.kernel.lost_found, self.kernel.root_partition.lost_found
        )

    def test_boot_mkfs_creates_lost_found(self):
        info = self.kernel.root_partition.mkfs()
        self.assertTrue(info["lost_found"]["preallocated"])
        self.assertGreater(info["lost_found"]["slots_reserved"], 0)

    def test_boot_fsck_runs_clean(self):
        p = self.kernel.root_partition
        p.mkfs()
        sb = p.superblock
        sb.on_mount()
        self.assertTrue(sb.needs_check())
        checker = self.uk._LostFoundFsck(p, auto_repair=True)
        report = checker.check(force=True)
        self.assertTrue(report.filesystem_clean)
        self.assertEqual(report.orphan_count, 0)

    def test_vfs_exposes_lost_found_dir(self):
        self.kernel.vfs.mkdir("/lost+found")
        self.assertIn("lost+found", self.kernel.vfs.ls("/"))

    def test_orphan_recovery_via_kernel_partition(self):
        p = self.kernel.root_partition
        p.mkfs()
        p.create_directory("/etc")
        f = p.create_file("/etc/fstab", data=b"UUID=x / ext4 defaults 0 1")
        p.orphan_inode(f.ino)
        checker = self.uk._LostFoundFsck(p, auto_repair=True)
        report = checker.check(force=True)
        self.assertEqual(report.recovered_count, 1)
        self.assertIsNotNone(p.lost_found.find_by_ino(f.ino))


if __name__ == "__main__":
    unittest.main(verbosity=2)
