"""
UmerOS /mnt - User-Mountable Filesystem Support
================================================

Implements the TLDP-defined user-mount mechanism that allows
non-root users to mount and unmount removable media.

From the TLDP ``mount`` man page:

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

FHS 3.0 /mnt interaction:

    Temporary admin mounts under /mnt can be user-mountable if
    configured in ``/etc/fstab`` with the ``user`` option.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

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
        """Render for ``/etc/mtab`` format."""
        return f"{self.device} {self.mount_point} {self.fstype} {self.options} 0 0"

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
    ) -> None:
        self._fstab_path = str(fstab_path)
        self._mtab_path = str(mtab_path)
        self._mount_mgr = mount_mgr or MountManager()
        self._mtab: List[MtabEntry] = []
        self._load_mtab()

    # -- Mtab I/O ------------------------------------------------------------

    def _load_mtab(self) -> None:
        """Load ``/etc/mtab``."""
        try:
            with open(self._mtab_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        self._mtab.append(MtabEntry(
                            device=parts[0],
                            mount_point=parts[1],
                            fstype=parts[2],
                            options=parts[3],
                            mounted_by="unknown",
                        ))
        except (FileNotFoundError, PermissionError):
            pass

    def _save_mtab(self) -> None:
        """Persist mtab entries."""
        try:
            with open(self._mtab_path, "w", encoding="utf-8") as fh:
                for entry in self._mtab:
                    fh.write(entry.to_mtab_line() + "\n")
        except PermissionError:
            log.error("Cannot write mtab: %s", self._mtab_path)

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
        self._save_mtab()

        log.info(
            "User mount: %s mounted %s at %s (%s)",
            username, device, mount_point, fstype,
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
        self._save_mtab()

        log.info("User umount: %s unmounted %s", username, mount_point)
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
    ) -> FstabEntry:
        """Create a standard user-mount fstab entry.

        Equivalent to::

            /dev/fd0 /floppy msdos user,noauto 0 0
        """
        opts = ["user", "noauto", "nosuid", "nodev"]
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

        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("user_mount selftest:", "OK" if _selftest() else "FAIL")
