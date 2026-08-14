"""
UmerOS /mnt - Temporary Mount Subsystem
========================================

FHS/TLDP-compliant temporary mount-point management for sysadmin use.

The ``/mnt`` directory is reserved for temporary mount points that sysadmins
may need to mount by hand. Unlike ``/media``, it is not managed by the system
and is intended for short-lived, administrator-initiated mounts.

Modules
-------
- **fstab** – ``/etc/fstab`` parser and writer.
- **mount_ops** – mount/unmount operations with flag support.
- **mount_point** – temporary mount-point lifecycle management.
- **user_mount** – user-mountable filesystem support (via ``user`` fstab option).
- **audit** – mount history and audit trail (JSONL append-only).
- **validation** – FHS ``/mnt`` validation checks.

Quick start::

    from mnt import MountManager, MountPointManager, Fstab

    # Parse /etc/fstab
    fstab = Fstab.from_file("/etc/fstab")

    # Manage mount operations
    mgr = MountManager()
    mgr.mount("/dev/sdb1", "/mnt/usb", "vfat", "rw,user")

    # Manage mount points
    pmgr = MountPointManager()
    mp = pmgr.create("usb", device="/dev/sdb1", purpose="USB drive")
"""

from __future__ import annotations

from .audit import AuditEvent, AuditLog, AuditRecord
from .fstab import Fstab, FstabEntry
from .mount_ops import (
    KNOWN_FS_TYPES,
    MountError,
    MountManager,
    MountOpt,
    MountRecord,
    flags_to_options,
    options_to_flags,
    parse_options,
)
from .mount_point import MNT_ROOT, MountPoint, MountPointManager
from .user_mount import MtabEntry, UserMountManager
from .validation import Finding, MntValidator, Severity

__all__ = [
    # fstab
    "FstabEntry",
    "Fstab",
    # mount_ops
    "MountOpt",
    "MountRecord",
    "MountManager",
    "MountError",
    "KNOWN_FS_TYPES",
    "parse_options",
    "options_to_flags",
    "flags_to_options",
    # mount_point
    "MNT_ROOT",
    "MountPoint",
    "MountPointManager",
    # user_mount
    "MtabEntry",
    "UserMountManager",
    # audit
    "AuditEvent",
    "AuditRecord",
    "AuditLog",
    # validation
    "Severity",
    "Finding",
    "MntValidator",
]
