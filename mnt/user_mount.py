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
UmerOS /mnt - User-Mountable Filesystem Support
================================================

Implements the defined user-mount mechanism that allows
non-root users to mount and unmount removable media.

From the ``mount`` man page:

    user    Allow an ordinary user to mount the filesystem.  The
    name of the mounting user is written to /etc/mtab so that he
    can unmount the filesystem again.

    users    Like user, but anyone may unmount (not only the user
    who mounted).

This module:

1. Validates that a user is allowed to mount a given device.
2. Enforces ``noauto`` + ``user`` option requirements.
3. Manages per-user mount ownership via ``/etc/mtab``.
4. Provides ``user-mount`` / ``user-umount`` CLI helpers.
5. Checks UID/GID constraints for vfat/msdos mounts.

 /mnt interaction:

    Temporary admin mounts under /mnt can be user-mountable if
    configured in ``/etc/fstab`` with the ``user`` option.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import stat
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set

try:  # POSIX advisory locking
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]
try:  # Windows advisory locking
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None  # type: ignore[assignment]

from .audit import AuditEvent, AuditLog
from .fstab import Fstab, FstabEntry
from .mount_ops import MountManager, MountRecord, MountError, parse_options

log = logging.getLogger("UmerOS.Mnt.UserMount")

MTAB_PATH = "/etc/mtab"


# ---------------------------------------------------------------------------
# Mtab entry (tracks who mounted what)
# ---------------------------------------------------------------------------

@dataclass
class MtabEntry:
    """Record of who mounted a filesystem.

    Mirrors ``/etc/mtab`` entry with an extra ``mounted_by`` field.
    """
    device: str
    mount_point: str
    fstype: str
    options: str
    mounted_by: str         # username or "root"
    mounted_at: float = field(default_factory=time.time)
    uid: int = 0

    def to_mtab_line(self) -> str:
        """Render for ``/etc/mtab`` format.

        Standard mtab readers ignore trailing ``#`` comments, so the
        ownership (who mounted it, with which uid) is preserved on disk
        and recoverable by :meth:`UserMountManager._load_mtab`.
        """
        base = f"{self.device} {self.mount_point} {self.fstype} {self.options} 0 0"
        return f"{base} # umeros mounted_by={self.mounted_by} uid={self.uid}"


# ---------------------------------------------------------------------------
# mtab merging
# ---------------------------------------------------------------------------

def merge_mtab_entries(
    local: Sequence[MtabEntry],
    on_disk: Sequence[MtabEntry],
    removed: Optional[Set[str]] = None,
) -> List[MtabEntry]:
    """Merge this manager's view with the current on-disk mtab.

    ``/etc/mtab`` is shared state: ``mount(8)``, the udisks2 daemon and any
    other ``UserMountManager`` write to it too.  A manager can only ever see
    the rows that existed when it was constructed, so rewriting the file from
    its in-memory list silently deletes every row it never loaded.  This
    merge is the fix:

    * on-disk order is preserved, so the file keeps its shape and only the
      rows that actually changed are touched;
    * a row whose mount point this manager knows about is replaced by the
      local version (local wins -- it reflects the operation just performed);
    * a row whose mount point is in *removed* is dropped (the tombstone that
      lets :meth:`UserMountManager.user_umount` delete a row without
      resurrecting it on the next save);
    * every other on-disk row is carried through untouched;
    * local rows not present on disk are appended.

    Args:
        local:     This manager's entries.
        on_disk:   Entries currently in the file.
        removed:   Mount points this manager unmounted.

    Returns:
        The list to write back, in on-disk order followed by new rows.
    """
    tombstones = removed or set()

    local_by_point: Dict[str, MtabEntry] = {}
    for entry in local:
        local_by_point.setdefault(entry.mount_point, entry)

    merged: List[MtabEntry] = []
    seen: Set[str] = set()

    for entry in on_disk:
        point = entry.mount_point
        if point in seen:
            continue
        seen.add(point)
        if point in tombstones:
            continue
        merged.append(local_by_point.get(point, entry))

    for entry in local:
        point = entry.mount_point
        if point in seen:
            continue
        seen.add(point)
        merged.append(entry)

    return merged


@contextlib.contextmanager
def _mtab_lock(lock_path: str):
    """Hold an exclusive advisory lock around the mtab read-modify-write.

    Without it two concurrent mounters both read the old file and the second
    ``os.replace()`` wins, dropping the first one's row -- the race half of
     ``fcntl.flock`` is used on POSIX and ``msvcrt.locking`` on Windows;
    if neither is available the merge still happens, just unserialised.
    """
    handle = open(lock_path, "a+b")
    locked = False
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            locked = True
        elif msvcrt is not None:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            locked = True
        yield
    finally:
        if locked:
            try:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                elif msvcrt is not None:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:  # pragma: no cover - best-effort unlock
                pass
        handle.close()

    def as_dict(self) -> Dict[str, object]:
        return {
            "device": self.device,
            "mount_point": self.mount_point,
            "fstype": self.fstype,
            "options": self.options,
            "mounted_by": self.mounted_by,
            "mounted_at": self.mounted_at,
            "uid": self.uid,
        }


# ---------------------------------------------------------------------------
# User mount manager
# ---------------------------------------------------------------------------

class UserMountManager:
    """Manages user-mountable filesystems.

    Validates fstab ``user`` options, enforces noauto requirements,
    and tracks mount ownership.

    Usage::

        mgr = UserMountManager()
        allowed = mgr.can_user_mount(username, "/mnt/usb")
        if allowed:
            record = mgr.user_mount(username, "/dev/sdb1", "/mnt/usb",
                                    "vfat", "uid=1000,gid=100")
    """

    def __init__(
        self,
        fstab_path: str | Path = "/etc/fstab",
        mount_mgr: Optional[MountManager] = None,
        mtab_path: str | Path = MTAB_PATH,
        *,
        audit: Optional[AuditLog] = None,
    ) -> None:
        self._fstab_path = str(fstab_path)
        self._mtab_path = str(mtab_path)
        self._audit = audit
        # User mounts always carry noauto (they are on-demand), so the
        # underlying MountManager must not skip them: noauto only governs
        # boot-time `mount -a` behaviour.
        self._mount_mgr = mount_mgr or MountManager(enforce_noauto=False)
        self._mtab: List[MtabEntry] = []
        # mount points this manager unmounted, so the read-modify-write
        # in _save_mtab() cannot resurrect them from the on-disk file.
        self._removed: Set[str] = set()
        self._load_mtab()

    # -- Mtab I/O ------------------------------------------------------------

    @staticmethod
    def _parse_mtab_lines(lines: Sequence[str]) -> List[MtabEntry]:
        """Parse raw mtab lines into entries.

        Ownership written by :meth:`MtabEntry.to_mtab_line` rides in a
        trailing ``#`` comment that standard mtab readers ignore.
        """
        entries: List[MtabEntry] = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            comment = line.split("#", 1)[1] if "#" in line else ""
            by_match = re.search(r"mounted_by=(\S+)", comment)
            uid_match = re.search(r"uid=(\d+)", comment)
            entries.append(MtabEntry(
                device=parts[0],
                mount_point=parts[1],
                fstype=parts[2],
                options=parts[3],
                mounted_by=by_match.group(1) if by_match else "unknown",
                uid=int(uid_match.group(1)) if uid_match else 0,
            ))
        return entries

    def _read_mtab_entries(self) -> List[MtabEntry]:
        """Read the current on-disk mtab (empty when absent/unreadable)."""
        try:
            with open(self._mtab_path, "r", encoding="utf-8") as fh:
                return self._parse_mtab_lines(fh.readlines())
        except (FileNotFoundError, PermissionError):
            return []

    def _load_mtab(self) -> None:
        """Load ``/etc/mtab`` into memory."""
        self._mtab = self._read_mtab_entries()

    def _write_mtab_atomic(self, entries: Sequence[MtabEntry]) -> None:
        """Replace the mtab file atomically.

        Writes a sibling temp file, fsyncs it and ``os.replace()``s it into
        place, so a reader (or a crash) never observes a half-written mtab.
        The existing file mode is preserved rather than inheriting
        ``mkstemp``'s 0600.
        """
        parent = os.path.dirname(os.path.abspath(self._mtab_path)) or "."
        try:
            mode = stat.S_IMODE(os.stat(self._mtab_path).st_mode)
        except OSError:
            mode = 0o644

        fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".mtab-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                for entry in entries:
                    fh.write(entry.to_mtab_line() + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp_path, mode)
            os.replace(tmp_path, self._mtab_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:  # pragma: no cover - already gone
                pass
            raise

    def _save_mtab(self) -> None:
        """Persist mtab entries.

        This used to truncate the file and rewrite it from this
        process's in-memory list, which deleted every row the manager had not
        loaded (another process's mount, a ``mount(8)`` run after
        construction) and lost whole writes when two mounters raced.  It is
        now a locked read-modify-write merge (:func:`merge_mtab_entries`)
        followed by an atomic replace, so concurrent writers compose instead
        of overwriting each other.
        """
        if os.path.islink(self._mtab_path):
            # Modern Linux ships /etc/mtab as a symlink to
            # /proc/self/mounts.  os.replace() would swap that symlink for a
            # stale regular file and break mount(8)/df, and the kernel
            # already maintains the real table -- there is nothing to write.
            log.warning(
                "mtab %s is a symlink (kernel-managed); not rewriting",
                self._mtab_path,
            )
            return

        try:
            with _mtab_lock(self._mtab_path + ".lock"):
                merged = merge_mtab_entries(
                    self._mtab,
                    self._read_mtab_entries(),
                    self._removed,
                )
                self._write_mtab_atomic(merged)
                self._mtab = merged
                # The tombstones have been honoured on disk; a later save
                # must not keep suppressing a row someone else re-created.
                self._removed.clear()
        except OSError as exc:
            log.error("Cannot write mtab %s: %s", self._mtab_path, exc)

    # -- Fstab lookups -------------------------------------------------------

    def _get_fstab_entry(self, mount_point: str) -> Optional[FstabEntry]:
        """Look up the fstab entry for a mount point."""
        fstab = Fstab.from_file(self._fstab_path)
        return fstab.find_by_mount(mount_point)

    # -- Permission checks ---------------------------------------------------

    def can_user_mount(
        self,
        username: str,
        mount_point: str,
        *,
        uid: Optional[int] = None,
    ) -> bool:
        """Check if *username* is allowed to mount at *mount_point*.

        Returns True if:

        1. An fstab entry exists for *mount_point*.
        2. The entry has ``user`` or ``users`` option.
        3. The entry has ``noauto`` option.
        """
        entry = self._get_fstab_entry(mount_point)
        if entry is None:
            log.info("No fstab entry for %s — user mount denied", mount_point)
            return False

        opts = parse_options(entry.options)

        # Must be noauto (user mounts are always noauto)
        if "noauto" not in opts:
            log.info(
                "fstab entry for %s lacks noauto — user mount denied",
                mount_point,
            )
            return False

        # Must have user or users
        if "user" not in opts and "users" not in opts:
            log.info(
                "fstab entry for %s lacks user/users option — denied",
                mount_point,
            )
            return False

        # Check UID constraint if specified
        if uid is not None:
            uid_opt = [o for o in opts if o.startswith("uid=")]
            if uid_opt:
                required_uid = int(uid_opt[0].split("=")[1])
                if uid != required_uid:
                    log.info(
                        "UID mismatch: expected %d, got %d for %s",
                        required_uid, uid, mount_point,
                    )
                    return False

        log.info("User %s allowed to mount at %s", username, mount_point)
        return True

    def can_user_umount(
        self,
        username: str,
        mount_point: str,
    ) -> bool:
        """Check if *username* can unmount at *mount_point*.

        With ``users`` option, any user who mounted it (or anyone
        at all) can unmount.  With ``user`` only the original
        mounting user may unmount.
        """
        # Find who mounted it
        for entry in self._mtab:
            if entry.mount_point == mount_point:
                if entry.mounted_by == username:
                    return True
                # Check if users option allows anyone
                if "users" in parse_options(entry.options):
                    return True
                return False
        return False

    # -- Mount/Unmount -------------------------------------------------------

    def user_mount(
        self,
        username: str,
        device: str,
        mount_point: str,
        fstype: str = "auto",
        extra_options: str = "",
        *,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
    ) -> MountRecord:
        """Mount as a user (non-root).

        Automatically adds ``user,noauto`` and ``uid=``/``gid=``
        options from the fstab entry.

        Raises:
            MountError: If permission denied or fstab misconfigured.
        """
        entry = self._get_fstab_entry(mount_point)
        if entry is None:
            raise MountError(
                f"No fstab entry for {mount_point} — cannot user-mount"
            )

        # Enforce the fstab user/users permission before touching the
        # mount table: without this check any caller could mount any
        # device that merely has an fstab entry.
        if not self.can_user_mount(username, mount_point, uid=uid):
            reason = f"User {username!r} is not allowed to mount {mount_point}"
            if self._audit is not None:
                self._audit.log_permission_deny(
                    device, mount_point, user=username, uid=uid or 0,
                    reason=reason,
                )
            raise MountError(reason)

        # Build options from fstab + overrides
        opts = list(parse_options(entry.options))

        # Ensure user-mount flags are present
        if "user" not in opts and "users" not in opts:
            opts.append("user")
        if "noauto" not in opts:
            opts.append("noauto")

        # Add uid/gid if provided
        if uid is not None:
            # Remove existing uid= option
            opts = [o for o in opts if not o.startswith("uid=")]
            opts.append(f"uid={uid}")
        if gid is not None:
            opts = [o for o in opts if not o.startswith("gid=")]
            opts.append(f"gid={gid}")

        # Append any extra options
        if extra_options:
            for o in extra_options.split(","):
                o = o.strip()
                if o and o not in opts:
                    opts.append(o)

        options_str = ",".join(opts)

        # Mount through the manager
        record = self._mount_mgr.mount(
            device, mount_point, fstype, options_str,
        )

        # Record in mtab
        mtab_entry = MtabEntry(
            device=device,
            mount_point=mount_point,
            fstype=fstype,
            options=options_str,
            mounted_by=username,
            uid=uid or 0,
        )
        self._mtab.append(mtab_entry)
        self._removed.discard(mount_point)
        self._save_mtab()

        log.info(
            "User mount: %s mounted %s at %s (%s)",
            username, device, mount_point, fstype,
        )
        if self._audit is not None:
            self._audit.log_user_mount(
                device, mount_point, fstype, user=username, uid=uid or 0,
            )
        return record

    def user_umount(
        self,
        username: str,
        mount_point: str,
        *,
        force: bool = False,
    ) -> MountRecord:
        """Unmount as a user.

        Raises:
            MountError: If permission denied or not currently mounted.
        """
        if not self.can_user_umount(username, mount_point):
            raise MountError(
                f"User {username} cannot unmount {mount_point}"
            )

        record = self._mount_mgr.umount(mount_point, force=force)

        # Remove from mtab
        self._mtab = [
            e for e in self._mtab if e.mount_point != mount_point
        ]
        # tombstone the removal so the merge in _save_mtab() cannot
        # bring the row back from the on-disk file.
        self._removed.add(mount_point)
        self._save_mtab()

        log.info("User umount: %s unmounted %s", username, mount_point)
        if self._audit is not None:
            self._audit.log_user_umount(mount_point, user=username)
        return record

    # -- Query ---------------------------------------------------------------

    @property
    def mtab(self) -> List[MtabEntry]:
        return list(self._mtab)

    def find_by_user(self, username: str) -> List[MtabEntry]:
        return [e for e in self._mtab if e.mounted_by == username]

    def find_mounted_by(self, mount_point: str) -> Optional[MtabEntry]:
        for e in self._mtab:
            if e.mount_point == mount_point:
                return e
        return None

    # -- Helper: create fstab user-mount entry ------------------------------

    @staticmethod
    def make_fstab_entry(
        device: str,
        mount_point: str,
        fstype: str,
        *,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
        umask: Optional[str] = None,
        ro: bool = False,
        noexec: bool = True,
    ) -> FstabEntry:
        """Create a standard user-mount fstab entry.

        Equivalent to::

            /dev/fd0 /floppy msdos user,noauto 0 0

        This used to apply ``noexec`` by default (see
        :func:`mnt.fstab.make_user_mount`); pass ``noexec=False`` for
        a deliberately executable mount.
        """
        opts = ["user", "noauto", "nosuid", "nodev"]
        if noexec:
            opts.append("noexec")
        if ro:
            opts.append("ro")
        if uid is not None:
            opts.append(f"uid={uid}")
        if gid is not None:
            opts.append(f"gid={gid}")
        if umask is not None:
            opts.append(f"umask={umask}")

        return FstabEntry(
            device=device,
            mount_point=mount_point,
            fstype=fstype,
            options=",".join(opts),
            dump=0,
            pass_num=0,
        )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class UserMountError(Exception):
    """Raised when a user mount operation fails."""
    pass


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Validate user mount logic."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        fstab_path = os.path.join(tmpdir, "fstab")
        mtab_path = os.path.join(tmpdir, "mtab")
        mnt = os.path.join(tmpdir, "mnt")
        os.makedirs(mnt)

        # Create a test fstab
        with open(fstab_path, "w") as fh:
            fh.write(
                "/dev/sdb1 /mnt/usb vfat user,noauto,uid=1000,gid=100 0 0\n"
                "/dev/fd0 /mnt/floppy msdos user,noauto 0 0\n"
                "/dev/sda1 / ext4 defaults 0 1\n"
            )

        mgr = UserMountManager(
            fstab_path=fstab_path,
            mtab_path=mtab_path,
        )

        # can_user_mount checks
        if not mgr.can_user_mount("alice", "/mnt/usb"):
            print("alice should be able to mount /mnt/usb")
            return False

        if not mgr.can_user_mount("alice", "/mnt/floppy"):
            print("alice should be able to mount /mnt/floppy")
            return False

        # Root mount (no user option) should be denied
        if mgr.can_user_mount("alice", "/"):
            print("alice should NOT be able to mount /")
            return False

        # Non-existent mount point
        if mgr.can_user_mount("alice", "/mnt/nonexistent"):
            print("alice should NOT be able to mount /mnt/nonexistent")
            return False

        # UID check
        if not mgr.can_user_mount("alice", "/mnt/usb", uid=1000):
            print("UID 1000 should match")
            return False
        if mgr.can_user_mount("alice", "/mnt/usb", uid=999):
            print("UID 999 should NOT match")
            return False

        # make_fstab_entry helper
        entry = UserMountManager.make_fstab_entry(
            "/dev/sdb1", "/mnt/usb", "vfat",
            uid=1000, gid=100,
        )
        if "user" not in entry.options:
            print("make_fstab_entry missing user option")
            return False
        if "noauto" not in entry.options:
            print("make_fstab_entry missing noauto option")
            return False
        if "uid=1000" not in entry.options:
            print("make_fstab_entry missing uid")
            return False
        if "noexec" not in entry.options:
            print("make_fstab_entry missing noexec")
            return False

        # mtab writes merge with the on-disk file instead of
        # clobbering it, and tombstones suppress unmounted rows.
        disk = [
            MtabEntry("/dev/sdb1", "/mnt/usb", "vfat", "user", "alice"),
            MtabEntry("/dev/sdc1", "/mnt/other", "ext4", "rw", "root"),
        ]
        merged = merge_mtab_entries(disk[:1], disk)
        if [e.mount_point for e in merged] != ["/mnt/usb", "/mnt/other"]:
            print(f"merge_mtab_entries dropped on-disk rows: {merged}")
            return False

        if merge_mtab_entries([], disk[1:], {"/mnt/other"}):
            print("merge_mtab_entries ignored a tombstone")
            return False

        merged = merge_mtab_entries(
            [MtabEntry("/dev/sdb1", "/mnt/usb", "vfat", "user,noexec", "bob")],
            disk[:1],
        )
        if len(merged) != 1 or merged[0].mounted_by != "bob":
            print(f"local entry should win: {merged}")
            return False

        # End-to-end: a row appended by "another process" after this
        # manager loaded the file must survive the next save.
        with open(mtab_path, "w", encoding="utf-8") as fh:
            fh.write(disk[0].to_mtab_line() + "\n")
        writer = UserMountManager(fstab_path=fstab_path, mtab_path=mtab_path)
        with open(mtab_path, "a", encoding="utf-8") as fh:
            fh.write(disk[1].to_mtab_line() + "\n")
        writer._mtab.append(
            MtabEntry("/dev/sdd1", "/mnt/new", "xfs", "rw", "root")
        )
        writer._save_mtab()
        with open(mtab_path, "r", encoding="utf-8") as fh:
            points = sorted(ln.split()[1] for ln in fh if ln.strip())
        if points != ["/mnt/new", "/mnt/other", "/mnt/usb"]:
            print(f"mtab merge clobbered rows: {points}")
            return False

        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("user_mount selftest:", "OK" if _selftest() else "FAIL")
