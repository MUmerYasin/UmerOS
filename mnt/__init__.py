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
UmerOS /mnt - Temporary Mount Subsystem
========================================

Compliant temporary mount-point management for sysadmin use.

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


def _selftest() -> bool:
    """Verify every public name in ``__all__`` is importable from this package."""
    import importlib as _il
    import sys as _sys
    pkg = _il.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(
            f"{__name__} selftest FAIL: missing {missing}",
            file=_sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
