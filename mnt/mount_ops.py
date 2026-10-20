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
UmerOS /mnt - Mount/Unmount Operations
=======================================

Wraps mount(2) and umount(2) semantics with safety checks, flag
management, and filesystem type detection.

The spec describes the ``mount`` command and syscall:

    mount [-t type] [-o options] device dir

Options include:

    ro, rw, noauto, user, users, noexec, nosuid, nodev,
    sync, async, noatime, nodiratime, relatime, etc.

This module provides a Pythonic interface that:

1. Validates mount arguments before calling the kernel.
2. Parses mount option strings into typed flag sets.
3. Provides remount, bind, and loop-mount helpers.
4. Tracks which devices are currently mounted.

/mnt interaction:

    /mnt is the designated directory for temporary admin mounts.
    All mount operations targeting paths under /mnt go through
    :class:`MountManager` which enforces the temporary-use policy.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Flag, auto
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from .audit import AuditEvent, AuditLog
# the /mnt validator is a leaf module (stdlib only), so importing
# it here cannot create a cycle with mnt/__init__.py.
from .validation import MntValidator, Severity

log = logging.getLogger("UmerOS.Mnt.MountOps")

# Gate privileged /mnt mount/unmount/remount behind the zero-trust
# capability bridge (core/capability_gate). Mounting a filesystem, changing the
# system mount table, and remounting are privileged operations that must require
# the `fs.admin` capability when a CapabilityManager is wired (fail-closed); when
# no manager is wired the gate stays permissive (warning) so existing flows work.
try:
    from core.capability_gate import gate, CAP_FS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    import sys
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    # A failed first attempt may have cached an unrelated "core"
    # package in sys.modules; drop it so the retry resolves
    # against the project root.
    sys.modules.pop("core", None)
    sys.modules.pop("core.capability_gate", None)
    from core.capability_gate import gate, CAP_FS_ADMIN


# ---------------------------------------------------------------------------
# Mount flags
# ---------------------------------------------------------------------------

class MountOpt(Flag):
    """Standard mount option flags (subset)."""
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


#: (hardening flag, explicit opt-out) pairs applied to user mounts.
_HARDEN_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("noexec", "exec"),
    ("nosuid", "suid"),
    ("nodev", "dev"),
)


def format_mount_intent(operation: str, **fields: str) -> str:
    """Render a structured log line describing a *simulated* mount op.

    ``mount()``, ``umount()`` and ``remount()`` used to build
    shell-shaped command strings -- ``"mount /dev/sdb1 /mnt/usb -t vfat"``
    -- purely to log them.  That pattern is misleading twice over:

    * it reads as though the code shells out to ``mount(8)``.  It does
      not -- UmerOS records the request in memory, and the real path is
      the kernel's; a reader auditing the log cannot tell that from the
      line itself.
    * the fields are space-separated, so a device path or mount point
      containing a space silently splits into what looks like two
      arguments, and a path containing ``$(...)`` or ``;`` reads like a
      shell injection attempt to anyone who later copies the line.

    Logging *intent* with ``repr()``-quoted fields keeps every value's
    boundaries visible, stays copy-paste safe, and states plainly that
    the operation is simulated.  ``MountRecord.__repr__`` already uses
    the same convention, so log lines and record reprs now agree.
    """
    body = ", ".join(f"{key}={value!r}" for key, value in fields.items())
    return f"{operation} [{body}] (simulated)"


def harden_user_options(options: str) -> str:
    """Append ``noexec,nosuid,nodev`` to a user-mountable option string.

    A ``user``/``users`` fstab option lets an unprivileged account mount
    untrusted removable media, so the resulting mount must not honour
    setuid bits, device nodes or executable payloads planted on it (the
    same hardening the H157 fix applies to ``/media``).

    Each flag is appended only when the caller has not explicitly chosen
    its opposite (``exec``/``suid``/``dev``), so a deliberate override by
    a privileged caller is preserved.  Non-user mounts are returned
    unchanged.
    """
    parts = [p.strip() for p in options.split(",") if p.strip()]
    names = {p.lower() for p in parts}
    if "user" not in names and "users" not in names:
        return options
    for hard, soft in _HARDEN_PAIRS:
        if hard not in names and soft not in names:
            parts.append(hard)
            names.add(hard)
    return ",".join(parts)


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
    # native
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
    * Optionally enforces ``user``/``users`` semantics (``enforce_user``):
      when enabled, only user-mountable requests may proceed.
    * Remount read-only on unmount failure (busy device).
    * Maintains in-memory mount table for queries.
    """

    def __init__(
        self,
        proc_mounts: str | Path = "/proc/mounts",
        *,
        enforce_noauto: bool = True,
        enforce_user: bool = False,
        audit: Optional[AuditLog] = None,
        mnt_root: str | Path = "/mnt",
        validate_mounts: bool = True,
        validator: Optional[MntValidator] = None,
    ) -> None:
        self._proc_mounts = str(proc_mounts)
        self._mnt_root = str(mnt_root)
        self._enforce_noauto = enforce_noauto
        # `enforce_user` was stored and never read.  It now gates
        # `mount()` as the sibling of `enforce_noauto`: when set, a request
        # that lacks the fstab `user`/`users` option is refused.
        self._enforce_user = enforce_user
        self._audit = audit
        # every /mnt request is checked by MntValidator before it is
        # recorded, and error-severity findings abort the mount.  Previously
        # the validator's findings were advisory-only -- nothing on the mount
        # path ever consulted it (detect-but-don't-fail-closed).
        self._validate_mounts = validate_mounts
        self._validator = validator or MntValidator(mnt_root=self._mnt_root)
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

    def _check_mount_request(
        self,
        device: str,
        mount_point: str,
        fstype: str,
        options: str,
    ) -> None:
        """Consult :class:`MntValidator` for a pending mount request.

        Findings are request-scoped (see
        :meth:`MntValidator.validate_mount_request`), so an unrelated problem
        elsewhere in ``/mnt`` cannot block this mount.

        Raises:
            MountError: if the validator reports any ``ERROR`` finding.
        """
        if not self._validate_mounts or self._validator is None:
            return

        findings = self._validator.validate_mount_request(
            device=device,
            mount_point=mount_point,
            fstype=fstype,
            options=options,
        )
        if not findings:
            return

        errors = [f for f in findings if f.severity == Severity.ERROR]
        for finding in findings:
            if finding.severity != Severity.ERROR:
                log.warning("Mount request %s: %s", mount_point, finding)

        if errors:
            reason = "; ".join(f"{f.code}: {f.message}" for f in errors)
            log.error("Mount request %s refused: %s", mount_point, reason)
            if self._audit is not None:
                self._audit.log_mount(
                    device, mount_point, fstype, options,
                    success=False, message=f"denied: {reason}",
                )
            raise MountError("\n".join(f"{f.code}: {f.message}" for f in errors))

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
        # Require the fs.admin capability before mutating the mount
        # table (fail-closed when a CapabilityManager is wired).
        try:
            gate.require(CAP_FS_ADMIN)
        except PermissionError:
            if self._audit is not None:
                self._audit.log_permission_deny(
                    device, mount_point,
                    reason="CAP_FS_ADMIN required to mount",
                )
            raise

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
            if self._audit is not None:
                self._audit.log_mount(
                    device, mount_point, fstype, options,
                    message="skipped (noauto)",
                )
            return MountRecord(
                device=device, mount_point=mount_point,
                fstype=fstype, options=options,
            )

        # `enforce_user` is the sibling of `enforce_noauto`.  When
        # enabled, only user-mountable requests (fstab `user`/`users`) may
        # proceed.  `noauto` is an expected "don't mount now" condition and
        # is therefore skipped; this is a policy denial, so it fails closed.
        if self._enforce_user and not ({"user", "users"} & opts):
            reason = (
                f"{mount_point} is not user-mountable: mount() requires "
                f"the 'user' or 'users' option (enforce_user=True)"
            )
            log.warning("Mount %s -> %s denied: %s", device, mount_point, reason)
            if self._audit is not None:
                self._audit.log_permission_deny(
                    device, mount_point, reason=reason,
                )
            raise MountError(reason)

        # user-mountable filesystems get the removable-media
        # hardening (noexec,nosuid,nodev) before anything is recorded.
        options = harden_user_options(options)

        # validate the (already hardened) request and fail closed on
        # error-severity findings before the mount table is mutated.
        self._check_mount_request(device, mount_point, fstype, options)

        # Actually mount (simulated in UmerOS)
        if not dry_run:
            # log the intent, not a fake `mount(8)` argv.  A real
            # command line would fragment a device path or mount point
            # containing whitespace and make `$(...)`/`;` in a path look
            # like shell injection.  repr()-quoting keeps the boundaries
            # visible and says plainly that this is simulated.
            log.info(
                "%s",
                format_mount_intent(
                    "mount",
                    device=device, target=mount_point,
                    fstype=fstype, options=options,
                ),
            )
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
        if self._audit is not None:
            self._audit.log_mount(device, mount_point, fstype, options)
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
        # Require the fs.admin capability before unmounting.
        try:
            gate.require(CAP_FS_ADMIN)
        except PermissionError:
            if self._audit is not None:
                self._audit.log_permission_deny(
                    "", mount_point,
                    reason="CAP_FS_ADMIN required to unmount",
                )
            raise

        record = None
        for i, m in enumerate(self._mounts):
            if m.mount_point == mount_point:
                record = self._mounts.pop(i)
                break

        if record is None:
            raise MountError(f"Not mounted: {mount_point}")

        # these were `--lazy`/`--force`/`--remount-ro` argv flags.
        # They are not argv any more -- there is no argv -- so they are
        # recorded as the unmount *mode* instead of being joined into a
        # command string that was built only to be logged.
        mode_parts = []
        if lazy:
            mode_parts.append("lazy")
        if force:
            mode_parts.append("force")
        if remount_ro and not record.is_readonly:
            mode_parts.append("remount-ro")

        log.info(
            "%s",
            format_mount_intent(
                "umount",
                target=mount_point, device=record.device,
                mode=",".join(mode_parts) or "normal",
            ),
        )
        log.info("Unmounted: %s", record)
        if self._audit is not None:
            self._audit.log_umount(mount_point, device=record.device)
        return record

    def umount_all(self, *, lazy: bool = False, force: bool = False) -> List[MountRecord]:
        """Unmount every recorded mount (e.g. before a cleanup sweep)."""
        removed: List[MountRecord] = []
        for mount_point in [m.mount_point for m in self._mounts]:
            removed.append(self.umount(mount_point, lazy=lazy, force=force))
        return removed

    # -- Remount -------------------------------------------------------------

    def remount(
        self,
        mount_point: str,
        options: str,
    ) -> MountRecord:
        """Remount with new options (e.g., read-only to read-write)."""
        # Require the fs.admin capability before remounting.
        try:
            gate.require(CAP_FS_ADMIN)
        except PermissionError:
            if self._audit is not None:
                self._audit.log_permission_deny(
                    "", mount_point,
                    reason="CAP_FS_ADMIN required to remount",
                )
            raise

        record = None
        for m in self._mounts:
            if m.mount_point == mount_point:
                record = m
                break

        if record is None:
            raise MountError(f"Not mounted: {mount_point}")

        old_opts = record.options
        record.options = options
        log.info(
            "%s",
            format_mount_intent(
                "remount", target=mount_point,
                options=options, previous=old_opts,
            ),
        )
        if self._audit is not None:
            self._audit.log_remount(mount_point, options, device=record.device)
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

    # user mounts are hardened; non-user mounts are untouched.
    if harden_user_options("user,noauto") != "user,noauto,noexec,nosuid,nodev":
        print(f"harden_user_options(user,noauto) -> {harden_user_options('user,noauto')}")
        return False
    if harden_user_options("defaults") != "defaults":
        print("harden_user_options must not touch non-user mounts")
        return False
    if harden_user_options("users,exec") != "users,exec,nosuid,nodev":
        print(f"explicit exec must be preserved: {harden_user_options('users,exec')}")
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

        # enforce_user refuses requests without user/users ...
        strict = MountManager(
            proc_mounts="/nonexistent",
            enforce_noauto=False,
            enforce_user=True,
        )
        try:
            strict.mount("/dev/sdb1", mnt_fd0, "msdos", "rw")
            print("enforce_user should refuse a non-user mount")
            return False
        except MountError:
            pass
        if strict.is_mounted(mnt_fd0):
            print("refused mount must not be recorded")
            return False

        # ... and allows user-mountable ones through.
        strict.mount("/dev/sdb1", mnt_fd0, "msdos", "user,noexec,nosuid,nodev")
        if not strict.is_mounted(mnt_fd0):
            print("enforce_user should allow a user mount")
            return False

        # `users` is the shared variant and must be accepted too.
        strict.umount(mnt_fd0)
        strict.mount("/dev/sdb1", mnt_fd0, "msdos", "users,noexec,nosuid,nodev")
        if not strict.is_mounted(mnt_fd0):
            print("enforce_user should allow a 'users' mount")
            return False

        # The default stays permissive (behaviour-neutral for existing callers).
        lax = MountManager(proc_mounts="/nonexistent", enforce_noauto=False)
        lax.mount("/dev/sdb1", mnt_usb, "vfat", "rw")
        if not lax.is_mounted(mnt_usb):
            print("enforce_user=False must not restrict mounts")
            return False

    # H170: MntValidator findings gate /mnt requests (fail closed).
    with tempfile.TemporaryDirectory() as tmpdir:
        mnt_root = os.path.join(tmpdir, "mnt")
        os.makedirs(os.path.join(mnt_root, "good"))
        os.makedirs(os.path.join(mnt_root, "target"))
        os.makedirs(os.path.join(mnt_root, "plain"))
        with open(os.path.join(mnt_root, "afile"), "w") as fh:
            fh.write("x")

        gate_mgr = MountManager(proc_mounts="/nonexistent", mnt_root=mnt_root)

        # MNT003: a regular file is not a mount point.
        try:
            gate_mgr.mount("/dev/sdb1", os.path.join(mnt_root, "afile"), "vfat")
            print("file mount point should be refused")
            return False
        except MountError:
            pass

        # MNT005: unusual leaf name.
        try:
            gate_mgr.mount("/dev/sdb1", os.path.join(mnt_root, "bad name"), "vfat")
            print("unusual mount point name should be refused")
            return False
        except MountError:
            pass

        # MNT004: symlinked mount point (skipped where symlinks are
        # unavailable, e.g. an unprivileged Windows session).
        link = os.path.join(mnt_root, "link")
        try:
            os.symlink(os.path.join(mnt_root, "target"), link)
        except (OSError, NotImplementedError):
            link = ""
        if link:
            try:
                gate_mgr.mount("/dev/sdb1", link, "vfat")
                print("symlinked mount point should be refused")
                return False
            except MountError:
                pass

        # A sound request still succeeds, with H169 hardening applied.
        ok = gate_mgr.mount("/dev/sdb1", os.path.join(mnt_root, "good"), "vfat", "user")
        if "noexec" not in ok.options_set:
            print("hardening lost on validated mount")
            return False

        # Opt-out restores the permissive behaviour.
        lax = MountManager(
            proc_mounts="/nonexistent",
            mnt_root=mnt_root,
            validate_mounts=False,
        )
        lax.mount("/dev/sdb2", os.path.join(mnt_root, "plain"), "vfat")
        if not lax.is_mounted(os.path.join(mnt_root, "plain")):
            print("validate_mounts=False should not consult the validator")
            return False

    # log intent, never a shell-shaped fake argv.
    line = format_mount_intent(
        "mount", device="/dev/sdb1", target="/mnt/my usb",
        fstype="vfat", options="defaults",
    )
    if " /mnt/my usb " in line or "/mnt/my usb -" in line:
        print("space in a mount point still looks like an argv separator")
        return False
    if "'/mnt/my usb'" not in line:
        print("mount point is not repr-quoted")
        return False
    if "(simulated)" not in line:
        print("the log line does not say the op is simulated")
        return False
    for field in ("device=", "target=", "fstype=", "options="):
        if field not in line:
            print(f"{field!r} missing from the intent line")
            return False
    # The umount mode must survive the argv -> mode rename.
    if format_mount_intent("umount", target="/mnt/x", mode="normal") != (
        "umount [target='/mnt/x', mode='normal'] (simulated)"
    ):
        print("unexpected umount intent rendering")
        return False
    # No dead argv construction may be left behind: `cmd` must no longer be
    # a local of umount(), and the mode list must be the replacement.
    umount_locals = MountManager.umount.__code__.co_varnames
    if "cmd" in umount_locals:
        print("umount() still builds a command string")
        return False
    if "mode_parts" not in umount_locals:
        print("umount() lost its mode_parts list")
        return False

    return True

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("mount_ops selftest:", "OK" if _selftest() else "FAIL")
