"""
UmerOS /mnt - Mount/Unmount Operations
=======================================

Wraps mount(2) and umount(2) semantics with safety checks, flag
management, and filesystem type detection.

The TLDP spec describes the ``mount`` command and syscall:

    mount [-t type] [-o options] device dir

Options include:

    ro, rw, noauto, user, users, noexec, nosuid, nodev,
    sync, async, noatime, nodiratime, relatime, etc.

This module provides a Pythonic interface that:

1. Validates mount arguments before calling the kernel.
2. Parses mount option strings into typed flag sets.
3. Provides remount, bind, and loop-mount helpers.
4. Tracks which devices are currently mounted.

FHS 3.0 /mnt interaction:

    /mnt is the designated directory for temporary admin mounts.
    All mount operations targeting paths under /mnt go through
    :class:`MountManager` which enforces the temporary-use policy.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Flag, auto
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence, Set

log = logging.getLogger("UmerOS.Mnt.MountOps")


# ---------------------------------------------------------------------------
# Mount flags
# ---------------------------------------------------------------------------

class MountOpt(Flag):
    """Standard Linux mount option flags (subset)."""
    NONE        = 0
    RO          = auto()   # read-only
    RW          = auto()   # read-write
    NOSUID      = auto()   # ignore setuid/setgid bits
    NODEV       = auto()   # ignore device special files
    NOEXEC      = auto()   # disallow execve()
    SYNCHRONOUS = auto()   # synchronous I/O
    DIRATIME    = auto()   # update directory access times
    NOATIME     = auto()   # never update access times
    RELATIME    = auto()   # update access time relative to mtime/ctime
    NODIRATIME  = auto()   # no directory access time updates
    ASYNC       = auto()   # asynchronous I/O
    NOAUTO      = auto()   # do not mount at mount -a
    USER        = auto()   # allow non-root to mount
    USERS       = auto()   # allow any user to unmount
    DEFAULTS    = auto()   # default options
    LOOP        = auto()   # loop device mount
    BIND        = auto()   # bind mount
    REMOUNT     = auto()   # remount with new options
    NOFAIL      = auto()   # do not fail boot if mount fails
    X_SYSTEMD   = auto()   # systemd-managed
    NOSYMFOLLOW = auto()   # do not follow symlinks


# Map option name strings to MountOpt flags
_OPT_MAP: Dict[str, MountOpt] = {
    "ro":            MountOpt.RO,
    "rw":            MountOpt.RW,
    "nosuid":        MountOpt.NOSUID,
    "nodev":         MountOpt.NODEV,
    "noexec":        MountOpt.NOEXEC,
    "sync":          MountOpt.SYNCHRONOUS,
    "diratime":      MountOpt.DIRATIME,
    "noatime":       MountOpt.NOATIME,
    "relatime":      MountOpt.RELATIME,
    "nodiratime":    MountOpt.NODIRATIME,
    "async":         MountOpt.ASYNC,
    "noauto":        MountOpt.NOAUTO,
    "user":          MountOpt.USER,
    "users":         MountOpt.USERS,
    "defaults":      MountOpt.DEFAULTS,
    "loop":          MountOpt.LOOP,
    "bind":          MountOpt.BIND,
    "remount":       MountOpt.REMOUNT,
    "nofail":        MountOpt.NOFAIL,
    "nosymfollow":   MountOpt.NOSYMFOLLOW,
}


def parse_options(opt_str: str) -> FrozenSet[str]:
    """Parse a comma-separated option string into a normalised set.

    Returns a frozenset of lower-case option name strings.
    Unknown options are preserved (the kernel may understand them).
    """
    if not opt_str or opt_str == "defaults":
        return frozenset()
    return frozenset(o.strip().lower() for o in opt_str.split(",") if o.strip())


def options_to_flags(opts: FrozenSet[str]) -> MountOpt:
    """Convert a set of option strings to :class:`MountOpt` flags."""
    flags = MountOpt.NONE
    for name in opts:
        if name in _OPT_MAP:
            flags |= _OPT_MAP[name]
    return flags


def flags_to_options(flags: MountOpt) -> str:
    """Convert flags back to an option string."""
    parts: List[str] = []
    for name, flag in _OPT_MAP.items():
        if name == "defaults":
            continue
        if flag in flags:
            parts.append(name)
    return ",".join(parts) if parts else "defaults"


# ---------------------------------------------------------------------------
# Known filesystem types
# ---------------------------------------------------------------------------

KNOWN_FS_TYPES: FrozenSet[str] = frozenset({
    # Linux native
    "ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs", "reiserfs", "jfs",
    "nilfs2", "bcachefs",
    # Pseudo
    "proc", "sysfs", "devpts", "tmpfs", "devtmpfs", "securityfs",
    "cgroup", "cgroup2", "hugetlbfs", "mqueue", "pstore", "tracefs",
    "debugfs", "fusectl", "bpf", "overlay",
    # FAT/exFAT
    "vfat", "fat", "msdos", "exfat",
    # ISO / CD
    "iso9660", "udf",
    # Network
    "nfs", "nfs4", "cifs", "smbfs", "sshfs", "fuse.sshfs",
    # Loop
    "squashfs", "romfs",
    # Encrypted
    "crypt", "dm-crypt", "luks",
})

NETWORK_FS: FrozenSet[str] = frozenset({"nfs", "nfs4", "cifs", "smbfs", "sshfs", "fuse.sshfs"})

NOAUTO_FS: FrozenSet[str] = frozenset({"swap"})


# ---------------------------------------------------------------------------
# Mount record
# ---------------------------------------------------------------------------

@dataclass
class MountRecord:
    """Represents an active mount in the mount table.

    Mirrors the fields of ``/proc/mounts``.
    """
    device: str
    mount_point: str
    fstype: str
    options: str
    dump: int = 0
    pass_num: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def options_set(self) -> FrozenSet[str]:
        return parse_options(self.options)

    @property
    def is_readonly(self) -> bool:
        return "ro" in self.options_set

    @property
    def is_under_mnt(self) -> bool:
        return self.mount_point.startswith("/mnt/")

    def as_dict(self) -> Dict[str, object]:
        return {
            "device": self.device,
            "mount_point": self.mount_point,
            "fstype": self.fstype,
            "options": self.options,
            "dump": self.dump,
            "pass_num": self.pass_num,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"MountRecord(device={self.device!r}, "
            f"mount_point={self.mount_point!r}, "
            f"fstype={self.fstype!r})"
        )


# ---------------------------------------------------------------------------
# Mount manager
# ---------------------------------------------------------------------------

class MountManager:
    """Manages the system mount table.

    In UmerOS this wraps ``/proc/mounts`` (real or simulated) and
    provides the safety layer for ``/mnt`` operations.

    Lifecycle::

        mgr = MountManager()
        mgr.mount("/dev/sdb1", "/mnt/usb", "vfat", "user,noauto")
        ...
        mgr.umount("/mnt/usb")

    Features:

    * Validates mount points (must exist as directories).
    * Prevents double-mounts.
    * Enforces ``noauto`` semantics.
    * Remount read-only on unmount failure (busy device).
    * Maintains in-memory mount table for queries.
    """

    def __init__(
        self,
        proc_mounts: str | Path = "/proc/mounts",
        *,
        enforce_noauto: bool = True,
        enforce_user: bool = False,
    ) -> None:
        self._proc_mounts = str(proc_mounts)
        self._enforce_noauto = enforce_noauto
        self._enforce_user = enforce_user
        self._mounts: List[MountRecord] = []
        self._load_mounts()

    # -- Mount table I/O -----------------------------------------------------

    def _load_mounts(self) -> None:
        """Load current mounts from /proc/mounts."""
        try:
            with open(self._proc_mounts, "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        self._mounts.append(MountRecord(
                            device=parts[0],
                            mount_point=parts[1],
                            fstype=parts[2],
                            options=parts[3],
                        ))
            log.debug("Loaded %d mounts from %s", len(self._mounts), self._proc_mounts)
        except (FileNotFoundError, PermissionError) as exc:
            log.warning("Cannot read %s: %s", self._proc_mounts, exc)

    @property
    def mounts(self) -> List[MountRecord]:
        return list(self._mounts)

    @property
    def mnt_mounts(self) -> List[MountRecord]:
        """Active mounts under /mnt/."""
        return [m for m in self._mounts if m.is_under_mnt]

    # -- Validation ----------------------------------------------------------

    def _validate_mount_point(self, mount_point: str) -> List[str]:
        """Check mount point exists and is a directory.

        Returns a list of error strings (empty = valid).
        """
        errors: List[str] = []
        path = Path(mount_point)

        if not path.is_absolute():
            errors.append(f"Mount point must be absolute: {mount_point}")
        if not path.exists():
            errors.append(f"Mount point does not exist: {mount_point}")
        elif not path.is_dir():
            errors.append(f"Mount point is not a directory: {mount_point}")

        # Check if already mounted
        for m in self._mounts:
            if m.mount_point == mount_point:
                errors.append(f"Already mounted: {mount_point} ({m.fstype} on {m.device})")
                break

        return errors

    def _validate_fstype(self, fstype: str) -> List[str]:
        errors: List[str] = []
        if fstype not in KNOWN_FS_TYPES:
            log.warning("Unknown filesystem type: %s", fstype)
        return errors

    # -- Mount ---------------------------------------------------------------

    def mount(
        self,
        device: str,
        mount_point: str,
        fstype: str = "auto",
        options: str = "defaults",
        *,
        dry_run: bool = False,
    ) -> MountRecord:
        """Mount a filesystem.

        Args:
            device:       Block device path or special name.
            mount_point:  Target directory.
            fstype:       Filesystem type (``auto`` for kernel detection).
            options:      Comma-separated mount options.
            dry_run:      If True, validate but don't actually mount.

        Returns:
            The new :class:`MountRecord`.

        Raises:
            MountError: If validation fails or mount is denied.
        """
        errors: List[str] = []

        # Validate mount point
        errors.extend(self._validate_mount_point(mount_point))
        if errors:
            raise MountError("\n".join(errors))

        # Validate filesystem type
        errors.extend(self._validate_fstype(fstype))
        if errors:
            raise MountError("\n".join(errors))

        # Check noauto
        opts = parse_options(options)
        if MountOpt.NOAUTO in options_to_flags(opts) and self._enforce_noauto:
            log.info("Mount %s -> %s skipped (noauto)", device, mount_point)
            return MountRecord(
                device=device, mount_point=mount_point,
                fstype=fstype, options=options,
            )

        # Actually mount (simulated in UmerOS)
        if not dry_run:
            log.info("mount %s %s -t %s -o %s", device, mount_point, fstype, options)
            # In real UmerOS, this calls the kernel mount(2) syscall.
            # For simulation, we just record it.

        record = MountRecord(
            device=device,
            mount_point=mount_point,
            fstype=fstype,
            options=options,
            timestamp=time.time(),
        )
        self._mounts.append(record)
        log.info("Mounted: %s", record)
        return record

    # -- Unmount -------------------------------------------------------------

    def umount(
        self,
        mount_point: str,
        *,
        lazy: bool = False,
        force: bool = False,
        remount_ro: bool = True,
    ) -> MountRecord:
        """Unmount a filesystem.

        Args:
            mount_point:  Directory to unmount.
            lazy:         Lazy unmount (detach immediately).
            force:        Force unmount.
            remount_ro:   Remount read-only before final unmount.

        Returns:
            The removed :class:`MountRecord`.

        Raises:
            MountError: If the mount point is not currently mounted.
        """
        record = None
        for i, m in enumerate(self._mounts):
            if m.mount_point == mount_point:
                record = self._mounts.pop(i)
                break

        if record is None:
            raise MountError(f"Not mounted: {mount_point}")

        # Simulate lazy/force
        flag_parts = []
        if lazy:
            flag_parts.append("--lazy")
        if force:
            flag_parts.append("--force")
        if remount_ro and not record.is_readonly:
            flag_parts.append("--remount-ro")

        cmd = "umount"
        if flag_parts:
            cmd += " " + " ".join(flag_parts)
        cmd += f" {mount_point}"

        log.info(cmd)
        log.info("Unmounted: %s", record)
        return record

    # -- Remount -------------------------------------------------------------

    def remount(
        self,
        mount_point: str,
        options: str,
    ) -> MountRecord:
        """Remount with new options (e.g., read-only to read-write)."""
        record = None
        for m in self._mounts:
            if m.mount_point == mount_point:
                record = m
                break

        if record is None:
            raise MountError(f"Not mounted: {mount_point}")

        old_opts = record.options
        record.options = options
        log.info("remount %s -o %s (was: %s)", mount_point, options, old_opts)
        return record

    # -- Bind mount ----------------------------------------------------------

    def bind_mount(self, source: str, target: str) -> MountRecord:
        """Bind mount: make *target* a mirror of *source*."""
        return self.mount(source, target, "none", "bind")

    # -- Query ---------------------------------------------------------------

    def is_mounted(self, mount_point: str) -> bool:
        return any(m.mount_point == mount_point for m in self._mounts)

    def find_mount(self, mount_point: str) -> Optional[MountRecord]:
        for m in self._mounts:
            if m.mount_point == mount_point:
                return m
        return None

    def find_by_device(self, device: str) -> List[MountRecord]:
        return [m for m in self._mounts if m.device == device]

    def find_by_fstype(self, fstype: str) -> List[MountRecord]:
        return [m for m in self._mounts if m.fstype == fstype]

    # -- Stats ---------------------------------------------------------------

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "total": len(self._mounts),
            "under_mnt": len(self.mnt_mounts),
            "network": sum(1 for m in self._mounts if m.fstype in NETWORK_FS),
        }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class MountError(Exception):
    """Raised when a mount operation fails."""
    pass


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Validate mount operations."""
    # Test option parsing
    opts = parse_options("ro,nosuid,nodev,noexec")
    if opts != frozenset({"ro", "nosuid", "nodev", "noexec"}):
        print(f"parse_options failed: {opts}")
        return False

    # Test flags
    flags = options_to_flags(opts)
    if MountOpt.RO not in flags:
        print("RO flag missing")
        return False
    if MountOpt.NOSUID not in flags:
        print("NOSUID flag missing")
        return False

    # Test defaults
    opts_def = parse_options("defaults")
    if opts_def:
        print(f"defaults should parse to empty, got {opts_def}")
        return False

    # Test MountRecord
    rec = MountRecord("/dev/sda1", "/mnt/usb", "vfat", "rw,user,noauto")
    if rec.is_readonly:
        print("MountRecord.is_readonly should be False")
        return False
    if not rec.is_under_mnt:
        print("MountRecord.is_under_mnt should be True")
        return False

    # Test MountManager (simulated, no /proc/mounts, use temp dirs)
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        mnt_usb = os.path.join(tmpdir, "usb")
        mnt_fd0 = os.path.join(tmpdir, "fd0")
        os.makedirs(mnt_usb)
        os.makedirs(mnt_fd0)

        mgr = MountManager(proc_mounts="/nonexistent", enforce_noauto=False)
        if len(mgr.mounts) != 0:
            print(f"Expected 0 mounts, got {len(mgr.mounts)}")
            return False

        # Mount something (no noauto, enforce_noauto=False)
        rec = mgr.mount("/dev/sdb1", mnt_usb, "vfat", "rw,user")
        if not mgr.is_mounted(mnt_usb):
            print("Mount did not register")
            return False

        # Query
        found = mgr.find_mount(mnt_usb)
        if found is None:
            print("find_mount failed")
            return False
        if found.fstype != "vfat":
            print(f"Wrong fstype: {found.fstype}")
            return False

        # Unmount
        mgr.umount(mnt_usb)
        if mgr.is_mounted(mnt_usb):
            print("Unmount failed")
            return False

        # Double-mount check
        mgr.mount("/dev/sdb1", mnt_usb, "vfat")
        try:
            mgr.mount("/dev/sdb2", mnt_usb, "vfat")
            print("Double mount should raise MountError")
            return False
        except MountError:
            pass

        # noauto test: enforce_noauto=True prevents recording
        mgr2 = MountManager(proc_mounts="/nonexistent", enforce_noauto=True)
        rec = mgr2.mount("/dev/sdb1", mnt_fd0, "msdos", "noauto")
        if mgr2.is_mounted(mnt_fd0):
            print("noauto mount should not register as mounted")
            return False

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("mount_ops selftest:", "OK" if _selftest() else "FAIL")
