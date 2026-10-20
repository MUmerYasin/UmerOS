"""Regression tests for H171 - ``/etc/mtab`` was clobbered on every write.

Before H171 :meth:`UserMountManager._save_mtab` did::

    with open(self._mtab_path, "w") as fh:
        for entry in self._mtab:
            fh.write(entry.to_mtab_line())

``/etc/mtab`` is shared state -- ``mount(8)``, the udisks2 daemon and any other
``UserMountManager`` write to it too -- but a manager only ever sees the rows
that existed when it was constructed.  So each save truncated the file and
wrote back a **partial** list, deleting every row it had never loaded, and two
concurrent mounters lost each other's writes.

The fix is a locked read-modify-write merge (:func:`merge_mtab_entries`) plus
an atomic ``os.replace()``, with tombstones so ``user_umount`` can delete a row
without it being resurrected from disk.

Note: ``tempfile.TemporaryDirectory`` is used rather than pytest's ``tmp_path``
because the Windows profile directory contains a space and ``mnt/fstab.py``
splits fstab lines on whitespace (see ``tests/test_mnt.py``).
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile

import pytest

from mnt.user_mount import (
    MtabEntry,
    UserMountManager,
    merge_mtab_entries,
)


def _entry(point: str, by: str = "root", device: str = "/dev/sdb1") -> MtabEntry:
    return MtabEntry(
        device=device,
        mount_point=point,
        fstype="vfat",
        options="user,noauto",
        mounted_by=by,
        uid=1000 if by != "root" else 0,
    )


def _read_points(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [ln.split()[1] for ln in fh if ln.strip()]


@pytest.fixture()
def tmp_tree():
    with tempfile.TemporaryDirectory() as tmp:
        mnt = os.path.join(tmp, "mnt")
        usb = os.path.join(mnt, "usb")
        floppy = os.path.join(mnt, "floppy")
        os.makedirs(usb)
        os.makedirs(floppy)
        fstab = os.path.join(tmp, "fstab")
        with open(fstab, "w", encoding="utf-8") as fh:
            fh.write(
                f"/dev/sdb1 {usb} vfat user,noauto,uid=1000,gid=100 0 0\n"
                f"/dev/fd0 {floppy} msdos user,noauto 0 0\n"
            )
        yield {
            "tmp": tmp,
            "fstab": fstab,
            "mtab": os.path.join(tmp, "mtab"),
            "usb": usb,
            "floppy": floppy,
        }


# ---------------------------------------------------------------------------
# merge_mtab_entries - pure merge semantics
# ---------------------------------------------------------------------------

class TestMergeMtabEntries:
    def test_disk_rows_are_preserved(self):
        merged = merge_mtab_entries(
            [_entry("/mnt/usb")],
            [_entry("/mnt/usb"), _entry("/mnt/other")],
        )
        assert [e.mount_point for e in merged] == ["/mnt/usb", "/mnt/other"]

    def test_on_disk_order_is_kept(self):
        merged = merge_mtab_entries(
            [_entry("/mnt/c")],
            [_entry("/mnt/a"), _entry("/mnt/b")],
        )
        assert [e.mount_point for e in merged] == ["/mnt/a", "/mnt/b", "/mnt/c"]

    def test_local_entry_wins_for_same_mount_point(self):
        merged = merge_mtab_entries(
            [_entry("/mnt/usb", by="bob")],
            [_entry("/mnt/usb", by="alice")],
        )
        assert len(merged) == 1
        assert merged[0].mounted_by == "bob"

    def test_tombstone_removes_row(self):
        merged = merge_mtab_entries(
            [],
            [_entry("/mnt/usb"), _entry("/mnt/other")],
            {"/mnt/usb"},
        )
        assert [e.mount_point for e in merged] == ["/mnt/other"]

    def test_tombstone_also_suppresses_a_local_row(self):
        """A row cannot be both unmounted and written back."""
        merged = merge_mtab_entries(
            [_entry("/mnt/usb")],
            [_entry("/mnt/usb")],
            {"/mnt/usb"},
        )
        assert merged == []

    def test_empty_inputs(self):
        assert merge_mtab_entries([], []) == []
        assert [e.mount_point for e in merge_mtab_entries([_entry("/mnt/x")], [])] == ["/mnt/x"]

    def test_duplicate_local_rows_are_collapsed(self):
        merged = merge_mtab_entries(
            [_entry("/mnt/usb", by="alice"), _entry("/mnt/usb", by="bob")],
            [],
        )
        assert len(merged) == 1
        assert merged[0].mounted_by == "alice"

    def test_duplicate_disk_rows_are_collapsed(self):
        merged = merge_mtab_entries(
            [],
            [_entry("/mnt/usb", by="alice"), _entry("/mnt/usb", by="bob")],
        )
        assert len(merged) == 1


# ---------------------------------------------------------------------------
# _save_mtab - the file-level fix
# ---------------------------------------------------------------------------

class TestSaveMtabMerge:
    def test_row_added_after_load_survives_save(self, tmp_tree):
        """The core regression: another process's row must not be deleted."""
        with open(tmp_tree["mtab"], "w", encoding="utf-8") as fh:
            fh.write(_entry("/mnt/usb").to_mtab_line() + "\n")

        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        # "Another process" mounts something after we loaded the file.
        with open(tmp_tree["mtab"], "a", encoding="utf-8") as fh:
            fh.write(_entry("/mnt/other", device="/dev/sdc1").to_mtab_line() + "\n")

        mgr._mtab.append(_entry("/mnt/new", device="/dev/sdd1"))
        mgr._save_mtab()

        assert sorted(_read_points(tmp_tree["mtab"])) == [
            "/mnt/new", "/mnt/other", "/mnt/usb",
        ]

    def test_two_managers_do_not_lose_each_others_rows(self, tmp_tree):
        """The race half: sequential saves must compose, not overwrite."""
        first = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        second = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )

        first._mtab.append(_entry("/mnt/one", device="/dev/sdb1"))
        first._save_mtab()
        second._mtab.append(_entry("/mnt/two", device="/dev/sdc1"))
        second._save_mtab()

        assert sorted(_read_points(tmp_tree["mtab"])) == ["/mnt/one", "/mnt/two"]

    def test_in_memory_view_is_resynced(self, tmp_tree):
        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        with open(tmp_tree["mtab"], "w", encoding="utf-8") as fh:
            fh.write(_entry("/mnt/external").to_mtab_line() + "\n")

        mgr._save_mtab()
        assert "/mnt/external" in [e.mount_point for e in mgr.mtab]

    def test_missing_mtab_is_created(self, tmp_tree):
        assert not os.path.exists(tmp_tree["mtab"])
        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        mgr._mtab.append(_entry("/mnt/usb"))
        mgr._save_mtab()
        assert _read_points(tmp_tree["mtab"]) == ["/mnt/usb"]

    def test_no_temp_file_is_left_behind(self, tmp_tree):
        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        mgr._mtab.append(_entry("/mnt/usb"))
        mgr._save_mtab()
        leftovers = [
            name for name in os.listdir(tmp_tree["tmp"])
            if name.startswith(".mtab-") and name.endswith(".tmp")
        ]
        assert leftovers == []

    def test_lock_sidecar_is_used(self, tmp_tree):
        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        mgr._save_mtab()
        assert os.path.exists(tmp_tree["mtab"] + ".lock")

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
    def test_file_mode_is_preserved(self, tmp_tree):
        with open(tmp_tree["mtab"], "w", encoding="utf-8") as fh:
            fh.write(_entry("/mnt/usb").to_mtab_line() + "\n")
        os.chmod(tmp_tree["mtab"], 0o640)

        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        mgr._save_mtab()
        assert stat.S_IMODE(os.stat(tmp_tree["mtab"]).st_mode) == 0o640

    def test_symlinked_mtab_is_not_replaced(self, tmp_tree):
        """Modern /etc/mtab is a symlink to /proc/self/mounts."""
        real = os.path.join(tmp_tree["tmp"], "real_mtab")
        with open(real, "w", encoding="utf-8") as fh:
            fh.write(_entry("/mnt/usb").to_mtab_line() + "\n")
        link = os.path.join(tmp_tree["tmp"], "mtab_link")
        try:
            os.symlink(real, link)
        except (OSError, NotImplementedError) as exc:  # pragma: no cover
            pytest.skip(f"symlinks unavailable: {exc}")

        before = open(real, "r", encoding="utf-8").read()
        mgr = UserMountManager(fstab_path=tmp_tree["fstab"], mtab_path=link)
        mgr._mtab.append(_entry("/mnt/new", device="/dev/sdd1"))
        mgr._save_mtab()

        assert os.path.islink(link)
        assert open(real, "r", encoding="utf-8").read() == before


# ---------------------------------------------------------------------------
# Tombstones - user_umount must not be undone by the merge
# ---------------------------------------------------------------------------

class TestTombstones:
    def test_umount_removes_row_from_disk(self, tmp_tree):
        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        mgr.user_mount("alice", "/dev/sdb1", tmp_tree["usb"], "vfat", uid=1000)
        assert _read_points(tmp_tree["mtab"]) == [tmp_tree["usb"]]

        mgr.user_umount("alice", tmp_tree["usb"])
        assert _read_points(tmp_tree["mtab"]) == []

    def test_umount_is_not_resurrected_by_a_later_save(self, tmp_tree):
        """A second save must not bring the unmounted row back."""
        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        mgr.user_mount("alice", "/dev/sdb1", tmp_tree["usb"], "vfat", uid=1000)
        mgr.user_umount("alice", tmp_tree["usb"])

        mgr._save_mtab()
        assert _read_points(tmp_tree["mtab"]) == []

    def test_tombstones_are_cleared_after_a_successful_save(self, tmp_tree):
        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        mgr.user_mount("alice", "/dev/sdb1", tmp_tree["usb"], "vfat", uid=1000)
        mgr.user_umount("alice", tmp_tree["usb"])
        assert mgr._removed == set()

    def test_remounting_clears_the_tombstone(self, tmp_tree):
        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        mgr.user_mount("alice", "/dev/sdb1", tmp_tree["usb"], "vfat", uid=1000)
        mgr.user_umount("alice", tmp_tree["usb"])
        mgr._removed.add(tmp_tree["usb"])  # force a pending tombstone
        mgr.user_mount("alice", "/dev/sdb1", tmp_tree["usb"], "vfat", uid=1000)
        assert tmp_tree["usb"] not in mgr._removed
        assert _read_points(tmp_tree["mtab"]) == [tmp_tree["usb"]]

    def test_other_rows_survive_an_umount(self, tmp_tree):
        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"], mtab_path=tmp_tree["mtab"]
        )
        with open(tmp_tree["mtab"], "w", encoding="utf-8") as fh:
            fh.write(_entry("/mnt/external").to_mtab_line() + "\n")

        mgr.user_mount("alice", "/dev/sdb1", tmp_tree["usb"], "vfat", uid=1000)
        mgr.user_umount("alice", tmp_tree["usb"])
        assert _read_points(tmp_tree["mtab"]) == ["/mnt/external"]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class TestParsing:
    def test_ownership_comment_round_trips(self):
        entry = _entry("/mnt/usb", by="alice")
        parsed = UserMountManager._parse_mtab_lines([entry.to_mtab_line()])
        assert parsed[0].mounted_by == "alice"
        assert parsed[0].uid == 1000

    def test_plain_rows_default_to_unknown(self):
        parsed = UserMountManager._parse_mtab_lines(
            ["/dev/sda1 / ext4 rw 0 0\n"]
        )
        assert parsed[0].mounted_by == "unknown"
        assert parsed[0].uid == 0

    @pytest.mark.parametrize("line", ["", "   ", "/dev/sda1 / ext4", "# comment only"])
    def test_malformed_lines_are_skipped(self, line):
        assert UserMountManager._parse_mtab_lines([line]) == []

    def test_unreadable_file_yields_no_entries(self, tmp_tree):
        mgr = UserMountManager(
            fstab_path=tmp_tree["fstab"],
            mtab_path=os.path.join(tmp_tree["tmp"], "absent"),
        )
        assert mgr._read_mtab_entries() == []
