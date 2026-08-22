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
Comprehensive tests for the UmerOS lost+found module.

These tests exercise the full /lost+found semantics:
  * mklost+found preallocation
  * fsck Phase 1-5 pipeline
  * orphaned inode detection and recovery
  * corrupted inode handling
  * link-count mismatch correction
  * per-partition isolation
  * lost+found recreation without preallocated blocks
  * claiming and purging recovered files
  * naming collisions (the #<ino>a / #<ino>b convention)
  * auto_repair=False (report-only) mode
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.lostfound import (
    FilesystemChecker,
    FilesystemPartition,
    FsckReport,
    Inode,
    InodeType,
    LostFoundManager,
    OrphanedInode,
    SuperBlock,
)
from lib.lostfound.fsck import FsState  # internal, for assertions


# --------------------------------------------------------------------------- #
# Inode unit tests
# --------------------------------------------------------------------------- #

class TestInode(unittest.TestCase):
    def test_regular_inode_defaults(self):
        i = Inode(ino=5, data=b"hello")
        self.assertEqual(i.type, InodeType.REGULAR)
        self.assertEqual(i.size, 5)
        self.assertEqual(i.nlinks, 1)
        self.assertTrue(i.allocated)
        self.assertFalse(i.corrupted)
        self.assertEqual(i.permission_string()[0], "-")

    def test_directory_inode_has_two_links(self):
        d = Inode(ino=2, type=InodeType.DIRECTORY)
        self.assertEqual(d.nlinks, 2)
        self.assertEqual(d.permission_string()[0], "d")

    def test_symlink_size_is_target_length(self):
        s = Inode(ino=3, type=InodeType.SYMLINK, target="/etc/passwd")
        self.assertEqual(s.size, len("/etc/passwd"))
        self.assertEqual(s.permission_string()[0], "l")

    def test_string_data_computes_size(self):
        i = Inode(ino=4, data="hello world")
        self.assertEqual(i.size, 11)

    def test_is_orphan(self):
        i = Inode(ino=5, data=b"data")
        self.assertFalse(i.is_orphan())
        i.nlinks = 0
        self.assertTrue(i.is_orphan())
        i.corrupted = True
        self.assertFalse(i.is_orphan())

    def test_dirent_add_remove(self):
        d = Inode(ino=2, type=InodeType.DIRECTORY)
        d.add_dirent("child", 10)
        self.assertEqual(d.find_dirent("child"), 10)
        with self.assertRaises(FileExistsError):
            d.add_dirent("child", 11)
        removed = d.remove_dirent("child")
        self.assertEqual(removed, 10)
        self.assertIsNone(d.find_dirent("child"))

    def test_add_dirent_rejects_non_directory(self):
        f = Inode(ino=5, type=InodeType.REGULAR)
        with self.assertRaises(ValueError):
            f.add_dirent("x", 1)

    def test_mode_property_round_trip(self):
        i = Inode(ino=6, type=InodeType.REGULAR, mode_perm=0o755)
        self.assertEqual(i.mode, 0o100755)
        i.mode = 0o040755  # directory 755
        self.assertEqual(i.type, InodeType.DIRECTORY)
        self.assertEqual(i.mode_perm, 0o755)

    def test_touch_updates_timestamps(self):
        i = Inode(ino=7)
        old = i.mtime
        i.touch()
        self.assertGreaterEqual(i.mtime, old)

    def test_to_dict(self):
        i = Inode(ino=8, data=b"abc")
        d = i.to_dict()
        self.assertEqual(d["ino"], 8)
        self.assertEqual(d["size"], 3)
        self.assertEqual(d["type"], "-")


# --------------------------------------------------------------------------- #
# SuperBlock tests
# --------------------------------------------------------------------------- #

class TestSuperBlock(unittest.TestCase):
    def test_defaults(self):
        sb = SuperBlock(total_inodes=100, total_blocks=200)
        self.assertEqual(sb.free_inodes, 99)  # ino 0 reserved
        self.assertEqual(sb.free_blocks, 200)
        self.assertEqual(sb.state, FsState.CLEAN)

    def test_on_mount_marks_dirty(self):
        sb = SuperBlock()
        info = sb.on_mount()
        self.assertEqual(sb.state, FsState.DIRTY)
        self.assertEqual(info["mount_count"], 1)

    def test_needs_check_after_max_mounts(self):
        sb = SuperBlock(max_mount_count=2)
        self.assertFalse(sb.needs_check())
        sb.on_mount()
        sb.on_unmount()
        self.assertFalse(sb.needs_check())
        sb.on_mount()
        sb.on_unmount()
        self.assertTrue(sb.needs_check())  # mount_count >= max

    def test_force_overrides_clean(self):
        sb = SuperBlock()
        sb.mark_clean()
        self.assertFalse(sb.needs_check())
        self.assertTrue(sb.needs_check(force=True))

    def test_mark_errors(self):
        sb = SuperBlock()
        sb.mark_errors("boom")
        self.assertEqual(sb.state, FsState.ERRORS)
        self.assertEqual(sb.error_count, 1)
        self.assertTrue(sb.needs_check())

    def test_allocate_and_free_inodes(self):
        sb = SuperBlock(total_inodes=10)
        self.assertTrue(sb.allocate_inode())
        self.assertEqual(sb.free_inodes, 8)  # started at 9, -1
        sb.free_one_inode()
        self.assertEqual(sb.free_inodes, 9)


# --------------------------------------------------------------------------- #
# LostFoundManager tests
# --------------------------------------------------------------------------- #

class TestLostFoundManager(unittest.TestCase):
    def setUp(self):
        self.lf = LostFoundManager(path="/lost+found", preallocate_entries=8)

    def test_mklost_found_creates_and_preallocates(self):
        result = self.lf.mklost_found()
        self.assertTrue(result["created"])
        self.assertTrue(result["preallocated"])
        self.assertEqual(result["slots_reserved"], 8)
        self.assertTrue(self.lf.exists)
        self.assertTrue(self.lf.has_preallocated_blocks)

    def test_mklost_found_idempotent(self):
        self.lf.mklost_found()
        result = self.lf.mklost_found()
        self.assertTrue(result["already_existed"])
        self.assertFalse(result["created"])

    def test_mklost_found_force_recreates(self):
        self.lf.mklost_found()
        result = self.lf.mklost_found(force=True)
        self.assertTrue(result["preallocated"])

    def test_recreate_without_prealloc(self):
        self.lf.mklost_found()
        self.lf.recreate_without_prealloc()
        self.assertTrue(self.lf.exists)
        self.assertFalse(self.lf.has_preallocated_blocks)
        self.assertEqual(self.lf.reserved_slots_remaining, 0)

    def test_ensure_exists_creates_if_missing(self):
        self.assertFalse(self.lf.exists)
        self.assertTrue(self.lf.ensure_exists())
        self.assertTrue(self.lf.exists)

    def test_recover_assigns_inode_number_name(self):
        self.lf.mklost_found()
        inode = Inode(ino=42, data=b"recovered data")
        inode.nlinks = 0  # orphans have no links
        orphan = OrphanedInode(inode, OrphanedInode.REASON_NLINKS_ZERO)
        name = self.lf.recover(orphan)
        self.assertEqual(name, "#42")
        self.assertEqual(orphan.recovered_name, "#42")
        self.assertTrue(orphan.recovered)
        self.assertEqual(inode.nlinks, 1)  # recovery adds one hard link
        self.assertEqual(len(self.lf), 1)

    def test_recover_skips_corrupted(self):
        self.lf.mklost_found()
        inode = Inode(ino=42)
        inode.corrupted = True
        orphan = OrphanedInode(inode, OrphanedInode.REASON_CORRUPTED)
        name = self.lf.recover(orphan)
        self.assertIsNone(name)
        self.assertEqual(len(self.lf), 0)

    def test_recover_consumes_preallocated_slot(self):
        self.lf.mklost_found()
        self.assertEqual(self.lf.reserved_slots_remaining, 8)
        for i in range(5):
            inode = Inode(ino=100 + i, data=b"x")
            self.lf.recover(OrphanedInode(inode))
        self.assertEqual(self.lf.reserved_slots_remaining, 3)

    def test_name_collision_gets_suffix(self):
        self.lf.mklost_found()
        # Two orphans with the same inode number (e.g. two separate runs
        # recovering the same inode).  Second one should be #42a.
        self.lf.recover(OrphanedInode(Inode(ino=42)))
        name2 = self.lf.recover(OrphanedInode(Inode(ino=42)))
        self.assertEqual(name2, "#42a")
        name3 = self.lf.recover(OrphanedInode(Inode(ino=42)))
        self.assertEqual(name3, "#42b")

    def test_list_returns_oldest_first(self):
        self.lf.mklost_found()
        self.lf.recover(OrphanedInode(Inode(ino=10)))
        self.lf.recover(OrphanedInode(Inode(ino=20)))
        entries = self.lf.list()
        self.assertEqual([e.name for e in entries], ["#10", "#20"])

    def test_claim_and_purge(self):
        self.lf.mklost_found()
        self.lf.recover(OrphanedInode(Inode(ino=42)))
        self.assertTrue(self.lf.claim("#42", "/etc/fstab"))
        self.assertTrue(self.lf.get("#42").claimed)
        n = self.lf.purge_claimed()
        self.assertEqual(n, 1)
        self.assertEqual(len(self.lf), 0)

    def test_claim_nonexistent_returns_false(self):
        self.lf.mklost_found()
        self.assertFalse(self.lf.claim("#999", "/nowhere"))

    def test_find_by_ino(self):
        self.lf.mklost_found()
        self.lf.recover(OrphanedInode(Inode(ino=42)))
        entry = self.lf.find_by_ino(42)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.name, "#42")

    def test_insert_manual(self):
        self.lf.mklost_found()
        inode = Inode(ino=99, data=b"manual")
        name = self.lf.insert(inode)
        self.assertEqual(name, "#99")
        self.assertEqual(self.lf.get(name).source, "manual")

    def test_stats(self):
        self.lf.mklost_found()
        self.lf.recover(OrphanedInode(Inode(ino=1, type=InodeType.REGULAR)))
        self.lf.recover(OrphanedInode(Inode(ino=2, type=InodeType.DIRECTORY)))
        stats = self.lf.stats()
        self.assertEqual(stats["entries"], 2)
        self.assertEqual(stats["total_recovered"], 2)
        self.assertIn("-", stats["by_type"])
        self.assertIn("d", stats["by_type"])


# --------------------------------------------------------------------------- #
# FilesystemPartition tests
# --------------------------------------------------------------------------- #

class TestFilesystemPartition(unittest.TestCase):
    def setUp(self):
        self.p = FilesystemPartition(name="sda1", mount_point="/")
        self.p.mkfs()

    def test_root_inode_is_1(self):
        self.assertEqual(self.p.root_ino, 1)
        root = self.p.get_inode(1)
        self.assertEqual(root.type, InodeType.DIRECTORY)

    def test_mkfs_creates_lost_found(self):
        root = self.p.get_inode(1)
        self.assertIsNotNone(root.find_dirent("lost+found"))
        self.assertTrue(self.p.lost_found.exists)
        self.assertTrue(self.p.lost_found.has_preallocated_blocks)

    def test_create_file_and_read(self):
        f = self.p.create_file("/hello.txt", data=b"hi there")
        self.assertEqual(f.size, 8)
        self.assertEqual(self.p.read_file("/hello.txt"), b"hi there")

    def test_create_directory(self):
        self.p.create_directory("/etc")
        etc = self.p._resolve("/etc")
        self.assertEqual(etc.type, InodeType.DIRECTORY)

    def test_create_nested_requires_parent(self):
        with self.assertRaises(FileNotFoundError):
            self.p.create_file("/no/such/dir/file")

    def test_unlink_makes_orphan(self):
        self.p.create_directory("/etc")
        f = self.p.create_file("/etc/fstab", data=b"UUID=...")
        self.assertEqual(f.nlinks, 1)
        self.assertTrue(self.p.unlink("/etc/fstab"))
        self.assertEqual(f.nlinks, 0)
        self.assertTrue(f.allocated)   # still allocated -> orphan
        self.assertTrue(f.deleted)

    def test_orphan_inode_helper(self):
        self.p.create_directory("/etc")
        f = self.p.create_file("/etc/passwd", data=b"root:x:0:0")
        self.assertTrue(self.p.orphan_inode(f.ino))
        self.assertEqual(f.nlinks, 0)
        # /etc should no longer reference passwd
        etc = self.p._resolve("/etc")
        self.assertIsNone(etc.find_dirent("passwd"))

    def test_corrupt_inode_helper(self):
        f = self.p.create_file("/x", data=b"abc")
        self.assertTrue(self.p.corrupt_inode(f.ino))
        self.assertTrue(f.corrupted)

    def test_break_link_count(self):
        f = self.p.create_file("/x", data=b"abc")
        self.p.break_link_count(f.ino, 99)
        self.assertEqual(f.nlinks, 99)

    def test_per_partition_isolation(self):
        p2 = FilesystemPartition(name="sda2", mount_point="/home")
        p2.mkfs()
        # Different partitions, different lost+found paths and instances
        self.assertEqual(self.p.lost_found.path, "/lost+found")
        self.assertEqual(p2.lost_found.path, "/home/lost+found")
        self.assertIsNot(self.p.lost_found, p2.lost_found)
        # Orphan on p2 doesn't affect p1
        f = p2.allocate_inode(InodeType.REGULAR, data=b"x")
        p2.orphan_inode(f.ino)
        self.assertEqual(len(self.p.lost_found), 0)


# --------------------------------------------------------------------------- #
# FilesystemChecker (fsck) tests
# --------------------------------------------------------------------------- #

class TestFilesystemChecker(unittest.TestCase):
    def setUp(self):
        self.p = FilesystemPartition(name="sda1", mount_point="/")
        self.p.mkfs()
        self.p.create_directory("/etc")
        self.p.create_directory("/var")

    def test_clean_filesystem_skipped_without_force(self):
        self.p.superblock.mark_clean()
        report = self.p and FilesystemChecker(self.p).check(force=False)
        self.assertTrue(report.filesystem_clean)
        self.assertEqual(report.orphan_count, 0)
        # Should have a warning about being clean
        self.assertTrue(any("clean" in w for w in report.warnings))

    def test_force_runs_on_clean_fs(self):
        self.p.superblock.mark_clean()
        report = FilesystemChecker(self.p).check(force=True)
        self.assertEqual(report.orphan_count, 0)
        self.assertTrue(report.filesystem_clean)

    def test_recovers_single_orphan(self):
        f = self.p.create_file("/etc/fstab", data=b"UUID=abc / ext4 defaults 0 1\n")
        self.p.orphan_inode(f.ino)
        report = FilesystemChecker(self.p).check(force=True)
        self.assertEqual(report.orphan_count, 1)
        self.assertEqual(report.recovered_count, 1)
        self.assertIn("#" + str(f.ino), report.recovered_names)
        self.assertTrue(report.filesystem_clean)
        entry = self.p.lost_found.find_by_ino(f.ino)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.size, len(b"UUID=abc / ext4 defaults 0 1\n"))

    def test_recovers_multiple_orphans(self):
        files = []
        for name in ["a", "b", "c"]:
            f = self.p.create_file(f"/etc/{name}", data=name.encode() * 10)
            files.append(f)
        for f in files:
            self.p.orphan_inode(f.ino)
        report = FilesystemChecker(self.p).check(force=True)
        self.assertEqual(report.orphan_count, 3)
        self.assertEqual(report.recovered_count, 3)
        self.assertEqual(len(self.p.lost_found), 3)

    def test_recovers_directory_orphan(self):
        d = self.p.create_directory("/opt")
        self.p.orphan_inode(d.ino)
        report = FilesystemChecker(self.p).check(force=True)
        self.assertEqual(report.recovered_count, 1)
        entry = self.p.lost_found.find_by_ino(d.ino)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.type, InodeType.DIRECTORY)

    def test_recovers_symlink_orphan(self):
        s = self.p.create_symlink("/etc/link", target="/etc/passwd")
        self.p.orphan_inode(s.ino)
        report = FilesystemChecker(self.p).check(force=True)
        self.assertEqual(report.recovered_count, 1)
        entry = self.p.lost_found.find_by_ino(s.ino)
        self.assertEqual(entry.type, InodeType.SYMLINK)

    def test_corrupted_inode_not_recovered(self):
        f = self.p.create_file("/etc/bad", data=b"corrupt")
        self.p.orphan_inode(f.ino)
        self.p.corrupt_inode(f.ino)
        report = FilesystemChecker(self.p).check(force=True)
        self.assertEqual(report.corrupted_count, 1)
        self.assertEqual(report.recovered_count, 0)
        self.assertFalse(report.filesystem_clean)

    def test_link_count_mismatch_fixed(self):
        f = self.p.create_file("/etc/fstab", data=b"contents")
        self.p.break_link_count(f.ino, 5)  # wrong nlinks
        report = FilesystemChecker(self.p, auto_repair=True).check(force=True)
        self.assertGreater(report.link_count_mismatches, 0)
        # After auto-repair, nlinks should be corrected
        self.assertEqual(f.nlinks, 1)

    def test_auto_repair_false_reports_only(self):
        f = self.p.create_file("/etc/fstab", data=b"x")
        self.p.orphan_inode(f.ino)
        report = FilesystemChecker(self.p, auto_repair=False).check(force=True)
        self.assertEqual(report.orphan_count, 1)
        self.assertEqual(report.recovered_count, 0)  # not recovered
        self.assertEqual(len(self.p.lost_found), 0)
        self.assertFalse(report.filesystem_clean)

    def test_lost_found_recreated_if_missing(self):
        # Simulate lost+found being deleted
        self.p.lost_found._created = False
        self.p.lost_found._preallocated = False
        self.p.lost_found._reserved_slots = 0
        f = self.p.create_file("/etc/orphan", data=b"x")
        self.p.orphan_inode(f.ino)
        report = FilesystemChecker(self.p).check(force=True)
        self.assertTrue(report.lost_found_recreated)
        self.assertFalse(report.lost_found_prealloc)
        self.assertEqual(report.recovered_count, 1)

    def test_superblock_block_count_error_fixed(self):
        self.p.lose_superblock_blocks()
        report = FilesystemChecker(self.p, auto_repair=True).check(force=True)
        self.assertGreater(report.errors_found, 0)
        # After repair, free_blocks should be sane again
        self.assertLessEqual(self.p.superblock.free_blocks,
                             self.p.superblock.total_blocks)

    def test_report_to_dict_and_summary(self):
        report = FilesystemChecker(self.p).check(force=True)
        d = report.to_dict()
        self.assertIn("errors_found", d)
        self.assertIn("orphans", d)
        s = report.summary()
        self.assertIn("fsck:", s)

    def test_full_report_string(self):
        report = FilesystemChecker(self.p).check(force=True)
        text = report.full_report()
        self.assertIn("fsck report", text)
        self.assertIn("status:", text)

    def test_claim_and_purge_after_recovery(self):
        f = self.p.create_file("/etc/important", data=b"save me")
        self.p.orphan_inode(f.ino)
        FilesystemChecker(self.p).check(force=True)
        entry = self.p.lost_found.find_by_ino(f.ino)
        self.assertIsNotNone(entry)
        # Sysadmin reviews, claims it, moves it back
        self.assertTrue(self.p.lost_found.claim(entry.name, "/etc/important"))
        self.assertEqual(self.p.lost_found.purge_claimed(), 1)

    def test_running_twice_second_run_clean(self):
        f = self.p.create_file("/etc/x", data=b"orphan")
        self.p.orphan_inode(f.ino)
        r1 = FilesystemChecker(self.p).check(force=True)
        self.assertEqual(r1.recovered_count, 1)
        r2 = FilesystemChecker(self.p).check(force=True)
        self.assertEqual(r2.orphan_count, 0)
        self.assertEqual(r2.recovered_count, 0)

    def test_mount_count_triggers_check(self):
        sb = self.p.superblock
        sb.max_mount_count = 1
        sb.on_mount()   # mount_count = 1, state = DIRTY
        report = FilesystemChecker(self.p).check(force=False)
        # Should have run because state is DIRTY
        self.assertEqual(report.orphan_count, 0)


# --------------------------------------------------------------------------- #
# OrphanedInode unit tests
# --------------------------------------------------------------------------- #

class TestOrphanedInode(unittest.TestCase):
    def test_default_reason(self):
        o = OrphanedInode(Inode(ino=1))
        self.assertEqual(o.reason, OrphanedInode.REASON_NO_DIRENT)
        self.assertTrue(o.is_recoverable)

    def test_corrupted_not_recoverable(self):
        i = Inode(ino=2)
        o = OrphanedInode(i, OrphanedInode.REASON_CORRUPTED)
        self.assertFalse(o.is_recoverable)

    def test_corrupted_inode_field_not_recoverable(self):
        i = Inode(ino=3)
        i.corrupted = True
        o = OrphanedInode(i)
        self.assertFalse(o.is_recoverable)

    def test_to_dict(self):
        o = OrphanedInode(Inode(ino=5, data=b"abc"))
        d = o.to_dict()
        self.assertEqual(d["ino"], 5)
        self.assertTrue(d["recoverable"])


# --------------------------------------------------------------------------- #
# Integration: full mkfs -> damage -> fsck -> recover cycle
# --------------------------------------------------------------------------- #

class TestFullRecoveryCycle(unittest.TestCase):
    def test_end_to_end_recovery(self):
        """Simulate a realistic scenario:
        1. mkfs a fresh partition.
        2. Populate it with files.
        3. 'Crash' — orphan several inodes.
        4. Run fsck.
        5. Verify all orphans appear in lost+found with correct names.
        6. Sysadmin claims and purges them.
        """
        p = FilesystemPartition(name="sda1", mount_point="/", total_inodes=256)
        p.mkfs()
        p.create_directory("/etc")
        p.create_directory("/var")
        p.create_directory("/var/log")
        p.create_directory("/home")
        p.create_directory("/home/umer")

        # Populate
        files = {}
        for name, content in [
            ("fstab", b"UUID=abc / ext4 defaults 0 1\n"),
            ("hostname", b"umeros\n"),
            ("passwd", b"root:x:0:0:root:/root:/bin/bash\n"),
            ("crontab", b"0 5 * * 1 tar -cf /backup\n"),
        ]:
            files[name] = p.create_file(f"/etc/{name}", data=content)

        # Simulate a crash: orphan 3 of the 4 files
        for name in ["fstab", "hostname", "crontab"]:
            p.orphan_inode(files[name].ino)

        # Run fsck
        report = FilesystemChecker(p, auto_repair=True).check(force=True)
        self.assertEqual(report.orphan_count, 3)
        self.assertEqual(report.recovered_count, 3)
        self.assertTrue(report.filesystem_clean)

        # All three should be in lost+found
        entries = p.lost_found.list()
        self.assertEqual(len(entries), 3)
        names = {e.name for e in entries}
        expected = {f"#{files[n].ino}" for n in ["fstab", "hostname", "crontab"]}
        self.assertEqual(names, expected)

        # Sizes preserved through recovery
        fstab_entry = p.lost_found.find_by_ino(files["fstab"].ino)
        self.assertEqual(fstab_entry.size, len(b"UUID=abc / ext4 defaults 0 1\n"))
        hostname_entry = p.lost_found.find_by_ino(files["hostname"].ino)
        self.assertEqual(hostname_entry.size, len(b"umeros\n"))

        # Sysadmin claims everything and purges
        for e in entries:
            p.lost_found.claim(e.name, f"/restored{e.name}")
        purged = p.lost_found.purge_claimed()
        self.assertEqual(purged, 3)
        self.assertEqual(len(p.lost_found), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
