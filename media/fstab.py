"""
UmerOS /media - /etc/fstab Integration
=========================================

Parses, validates, and manipulates fstab entries for removable media.

FHS/TLDP reference:
    Mounting and unmounting requires super user privileges.  The
    ``/etc/fstab`` file stores permanent mount configurations.  For
    removable media, the ``user`` and ``noauto`` options allow
    non-root users to mount/unmount devices.

Modules
-------
- ``FstabEntry`` - parsed fstab line with all fields.
- ``FstabManager`` - read/write/query ``/etc/fstab``.
- ``FstabValidator`` - validate entries before adding.

Quick start::

    from media.fstab import FstabManager, FstabEntry

    mgr = FstabManager()
    entry = FstabEntry(
        device="/dev/sdb1",
        mount_point="/media/usb0",
        fs_type="vfat",
        options="uid=1000,noauto,user",
    )
    mgr.add(entry)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum, unique
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

log = logging.getLogger("UmerOS.Media.Fstab")

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

FSTAB_PATH = "/etc/fstab"
FSTAB_BACKUP_SUFFIX = ".umer.bak"

# Options that conflict with user-mount
INCOMPATIBLE_WITH_USER: Set[str] = {"owner", "nouser"}
# Options that are security-sensitive for user mounts
SECURITY_SENSITIVE: Set[str] = {"suid", "dev", "exec"}


# ---------------------------------------------------------------------------
#  Entry
# ---------------------------------------------------------------------------

@dataclass
class FstabEntry:
    """A single parsed ``/etc/fstab`` entry."""
    device: str
    mount_point: str
    fs_type: str = "auto"
    options: str = "defaults"
    dump: int = 0
    passno: int = 0
    line_number: int = 0
    comment: str = ""

    @property
    def is_comment(self) -> bool:
        return self.device.startswith("#")

    @property
    def is_empty(self) -> bool:
        return not self.device.strip() and not self.mount_point.strip()

    @property
    def is_user_mount(self) -> bool:
        """True if the ``user`` option is set."""
        return "user" in self.option_set

    @property
    def is_noauto(self) -> bool:
        return "noauto" in self.option_set

    @property
    def option_set(self) -> Set[str]:
        """Parse options into a set."""
        return {o.strip() for o in self.options.split(",") if o.strip()}

    @property
    def is_removable_media(self) -> bool:
        """Heuristic: is this entry for removable media?"""
        mp_lower = self.mount_point.lower()
        return any(mp_lower.startswith(p) for p in (
            "/media/", "/mnt/",
        )) or self.fs_type in {"iso9660", "udf", "vfat", "exfat"}

    def get_option(self, key: str) -> Optional[str]:
        """Get value for key=value option, or None."""
        for part in self.options.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                if k.strip() == key:
                    return v.strip()
        return None

    def set_option(self, key: str, value: Optional[str] = None) -> None:
        """Set or remove an option."""
        opts = list(self.option_set)
        # Remove existing
        opts = [o for o in opts if o.split("=")[0] != key]
        # Add new
        if value is not None:
            opts.append(f"{key}={value}")
        self.options = ",".join(opts)

    def has_option(self, key: str) -> bool:
        return key in self.option_set or any(
            o.startswith(f"{key}=") for o in self.option_set
        )

    def to_line(self) -> str:
        """Serialize back to fstab format."""
        parts = [self.device, self.mount_point, self.fs_type, self.options,
                 str(self.dump), str(self.passno)]
        return "  ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device": self.device,
            "mount_point": self.mount_point,
            "fs_type": self.fs_type,
            "options": self.options,
            "dump": self.dump,
            "passno": self.passno,
            "line_number": self.line_number,
        }


# ---------------------------------------------------------------------------
#  Validator
# ---------------------------------------------------------------------------

@unique
class FstabIssue(Enum):
    """Validation issue type."""
    MISSING_DEVICE = "missing_device"
    MISSING_MOUNT_POINT = "missing_mount_point"
    MISSING_FS_TYPE = "missing_fs_type"
    INVALID_FS_TYPE = "invalid_fs_type"
    INVALID_DUMP = "invalid_dump"
    INVALID_PASSNO = "invalid_passno"
    CONFLICTING_OPTIONS = "conflicting_options"
    INSECURE_USER_MOUNT = "insecure_user_mount"
    MOUNT_POINT_EXISTS = "mount_point_exists"
    DUPLICATE_MOUNT_POINT = "duplicate_mount_point"
    NON_ABSOLUTE_PATH = "non_absolute_path"


@dataclass
class FstabIssueEntry:
    """A validation issue with context."""
    issue: FstabIssue
    message: str
    line_number: int = 0
    severity: str = "warning"

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


class FstabValidator:
    """Validate fstab entries before adding."""

    VALID_FS_TYPES = {
        "ext2", "ext3", "ext4", "vfat", "exfat", "ntfs", "ntfs-3g",
        "iso9660", "udf", "hfs+", "apfs", "btrfs", "xfs", "reiserfs",
        "jfs", "f2fs", "nilfs2", "tmpfs", "devpts", "sysfs", "proc",
        "squashfs", "cramfs", "romfs",
    }

    def __init__(self, existing_entries: Optional[List[FstabEntry]] = None) -> None:
        self._existing = existing_entries or []

    def validate(self, entry: FstabEntry) -> List[FstabIssueEntry]:
        """Validate a single entry.  Returns list of issues."""
        issues: List[FstabIssueEntry] = []
        ln = entry.line_number

        if not entry.device.strip():
            issues.append(FstabIssueEntry(
                FstabIssue.MISSING_DEVICE,
                "Device (spec) is empty",
                ln, "error",
            ))
        if not entry.mount_point.strip():
            issues.append(FstabIssueEntry(
                FstabIssue.MISSING_MOUNT_POINT,
                "Mount point is empty",
                ln, "error",
            ))
        elif not entry.mount_point.startswith("/"):
            issues.append(FstabIssueEntry(
                FstabIssue.NON_ABSOLUTE_PATH,
                f"Mount point '{entry.mount_point}' is not absolute",
                ln, "warning",
            ))
        if entry.fs_type == "auto":
            pass  # auto is allowed
        elif entry.fs_type not in self.VALID_FS_TYPES:
            issues.append(FstabIssueEntry(
                FstabIssue.INVALID_FS_TYPE,
                f"Unknown fs_type '{entry.fs_type}'",
                ln, "warning",
            ))
        if entry.dump not in (0, 1, 2):
            issues.append(FstabIssueEntry(
                FstabIssue.INVALID_DUMP,
                f"dump value {entry.dump} is not 0/1/2",
                ln, "warning",
            ))
        if entry.passno not in (0, 1, 2):
            issues.append(FstabIssueEntry(
                FstabIssue.INVALID_PASSNO,
                f"passno value {entry.passno} is not 0/1/2",
                ln, "warning",
            ))

        # Options
        opts = entry.option_set
        if "user" in opts and "nouser" in opts:
            issues.append(FstabIssueEntry(
                FstabIssue.CONFLICTING_OPTIONS,
                "Cannot have both 'user' and 'nouser'",
                ln, "error",
            ))
        if "user" in opts:
            conflicts = opts & INCOMPATIBLE_WITH_USER
            if conflicts:
                issues.append(FstabIssueEntry(
                    FstabIssue.CONFLICTING_OPTIONS,
                    f"'user' conflicts with {conflicts}",
                    ln, "error",
                ))
            insecure = opts & SECURITY_SENSITIVE
            if insecure:
                issues.append(FstabIssueEntry(
                    FstabIssue.INSECURE_USER_MOUNT,
                    f"Insecure options with user mount: {insecure}",
                    ln, "warning",
                ))

        # Duplicate mount point
        for existing in self._existing:
            if existing.mount_point == entry.mount_point and existing.device != entry.device:
                issues.append(FstabIssueEntry(
                    FstabIssue.DUPLICATE_MOUNT_POINT,
                    f"Mount point '{entry.mount_point}' already used by {existing.device}",
                    ln, "warning",
                ))

        return issues

    def validate_all(self, entries: List[FstabEntry]) -> List[FstabIssueEntry]:
        """Validate a list of entries."""
        all_issues: List[FstabIssueEntry] = []
        seen_mounts: Dict[str, int] = {}
        for entry in entries:
            all_issues.extend(self.validate(entry))
            if entry.mount_point in seen_mounts:
                all_issues.append(FstabIssueEntry(
                    FstabIssue.DUPLICATE_MOUNT_POINT,
                    f"Duplicate mount point '{entry.mount_point}'",
                    entry.line_number, "warning",
                ))
            seen_mounts[entry.mount_point] = entry.line_number
        return all_issues


# ---------------------------------------------------------------------------
#  Manager
# ---------------------------------------------------------------------------

class FstabManager:
    """Read, write, and query ``/etc/fstab``."""

    def __init__(self, fstab_path: str = FSTAB_PATH, *, simulate: bool = False) -> None:
        self._path = fstab_path
        self._simulate = simulate
        self._entries: List[FstabEntry] = []
        self._dirty = False
        if not simulate and os.path.exists(fstab_path):
            self.load()

    # -- Load / Save ----------------------------------------------------------

    def load(self) -> int:
        """Load entries from fstab.  Returns count."""
        self._entries.clear()
        try:
            with open(self._path, "r", encoding="utf-8", errors="replace") as fh:
                for ln, line in enumerate(fh, 1):
                    entry = self._parse_line(line, ln)
                    self._entries.append(entry)
        except FileNotFoundError:
            log.warning("fstab not found: %s", self._path)
        self._dirty = False
        return len(self._entries)

    def save(self) -> bool:
        """Write entries back to fstab."""
        if self._simulate:
            log.info("[sim] Would write %d entries to %s",
                     len(self._entries), self._path)
            self._dirty = False
            return True
        try:
            # Backup
            if os.path.exists(self._path):
                backup = self._path + FSTAB_BACKUP_SUFFIX
                with open(self._path, "r", encoding="utf-8") as src:
                    with open(backup, "w", encoding="utf-8") as dst:
                        dst.write(src.read())
            # Write
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                for entry in self._entries:
                    if not entry.is_comment and not entry.is_empty:
                        fh.write(entry.to_line() + "\n")
            self._dirty = False
            log.info("Saved %d entries to %s", len(self._entries), self._path)
            return True
        except OSError as exc:
            log.error("Failed to save fstab: %s", exc)
            return False

    # -- Query ----------------------------------------------------------------

    @property
    def entries(self) -> List[FstabEntry]:
        return list(self._entries)

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def count(self) -> int:
        return len(self._entries)

    def get_by_mount(self, mount_point: str) -> Optional[FstabEntry]:
        """Find entry by mount point."""
        for e in self._entries:
            if e.mount_point == mount_point and not e.is_comment:
                return e
        return None

    def get_by_device(self, device: str) -> List[FstabEntry]:
        """Find entries by device path."""
        return [e for e in self._entries
                if e.device == device and not e.is_comment]

    def get_removable(self) -> List[FstabEntry]:
        """Get entries for removable media."""
        return [e for e in self._entries
                if not e.is_comment and e.is_removable_media]

    def get_user_mounts(self) -> List[FstabEntry]:
        """Get entries with the ``user`` option."""
        return [e for e in self._entries
                if not e.is_comment and e.is_user_mount]

    def get_noauto(self) -> List[FstabEntry]:
        """Get entries with ``noauto``."""
        return [e for e in self._entries
                if not e.is_comment and e.is_noauto]

    # -- Mutate ---------------------------------------------------------------

    def add(self, entry: FstabEntry, *, position: Optional[int] = None) -> None:
        """Add an entry."""
        if position is not None:
            self._entries.insert(position, entry)
        else:
            self._entries.append(entry)
        self._dirty = True
        log.info("Added fstab entry: %s -> %s", entry.device, entry.mount_point)

    def remove(self, mount_point: str) -> bool:
        """Remove entries matching *mount_point*.  Returns True if removed."""
        before = len(self._entries)
        self._entries = [
            e for e in self._entries
            if e.mount_point != mount_point or e.is_comment
        ]
        removed = len(self._entries) < before
        if removed:
            self._dirty = True
        return removed

    def update(self, mount_point: str, **kwargs: Any) -> bool:
        """Update fields of an existing entry."""
        for entry in self._entries:
            if entry.mount_point == mount_point and not entry.is_comment:
                for k, v in kwargs.items():
                    if hasattr(entry, k):
                        setattr(entry, k, v)
                self._dirty = True
                return True
        return False

    def clear(self) -> int:
        """Remove all non-comment entries.  Returns count removed."""
        count = sum(1 for e in self._entries if not e.is_comment)
        self._entries = [e for e in self._entries if e.is_comment]
        self._dirty = count > 0
        return count

    # -- Parse ----------------------------------------------------------------

    @staticmethod
    def _parse_line(line: str, line_number: int = 0) -> FstabEntry:
        """Parse a single fstab line."""
        stripped = line.strip()
        if not stripped:
            return FstabEntry(device="", mount_point="", line_number=line_number)
        if stripped.startswith("#"):
            return FstabEntry(device=stripped, mount_point="", line_number=line_number,
                              comment=stripped)
        parts = stripped.split()
        if len(parts) < 4:
            # Pad with defaults
            parts.extend(["auto", "defaults", "0", "0"])
        elif len(parts) == 5:
            parts.append("0")
        elif len(parts) == 6:
            parts.append("0")
        return FstabEntry(
            device=parts[0],
            mount_point=parts[1],
            fs_type=parts[2],
            options=parts[3],
            dump=int(parts[4]) if parts[4].isdigit() else 0,
            passno=int(parts[5]) if parts[5].isdigit() else 0,
            line_number=line_number,
        )


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def make_removable_entry(
    device: str,
    mount_point: str,
    *,
    fs_type: str = "auto",
    uid: Optional[int] = None,
    extra_options: Optional[List[str]] = None,
) -> FstabEntry:
    """Create an fstab entry for a removable device with safe defaults."""
    opts = ["noauto", "user"]
    if uid is not None:
        opts.append(f"uid={uid}")
    if extra_options:
        opts.extend(extra_options)
    if fs_type in ("iso9660", "udf"):
        opts.append("ro")
    return FstabEntry(
        device=device,
        mount_point=mount_point,
        fs_type=fs_type,
        options=",".join(opts),
        dump=0,
        passno=0,
    )


def _selftest() -> bool:
    """Run self-diagnostics.  Returns True on success."""
    # Parse a line
    e = FstabManager._parse_line("/dev/sdb1  /media/usb0  vfat  uid=1000,noauto,user  0  0", 1)
    assert e.device == "/dev/sdb1"
    assert e.mount_point == "/media/usb0"
    assert e.fs_type == "vfat"
    assert e.is_user_mount
    assert e.is_noauto
    assert e.get_option("uid") == "1000"

    # Serialize
    line = e.to_line()
    assert "/dev/sdb1" in line
    assert "uid=1000" in line

    # Validator
    validator = FstabValidator()
    issues = validator.validate(e)
    # noauto+user is fine; uid=1000 is fine
    errors = [i for i in issues if i.is_error]
    assert len(errors) == 0

    # Conflicting options
    bad = FstabEntry("/dev/x", "/m", "ext4", "user,nouser")
    issues2 = validator.validate(bad)
    assert any(i.issue == FstabIssue.CONFLICTING_OPTIONS for i in issues2)

    # Manager (sim)
    mgr = FstabManager(simulate=True)
    mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "user,noauto"))
    mgr.add(FstabEntry("/dev/sr0", "/media/cdrom", "iso9660", "user,noauto,ro"))
    assert mgr.count == 2
    found = mgr.get_by_mount("/media/usb0")
    assert found is not None
    assert found.device == "/dev/sdb1"
    removable = mgr.get_removable()
    assert len(removable) == 2
    user_m = mgr.get_user_mounts()
    assert len(user_m) == 2
    assert mgr.remove("/media/cdrom")
    assert mgr.count == 1
    mgr.save()  # sim

    # Helper
    entry = make_removable_entry("/dev/sdb1", "/media/usb0", uid=1000)
    assert entry.is_user_mount
    assert entry.get_option("uid") == "1000"
    assert "ro" in entry.option_set or entry.fs_type != "iso9660"

    return True
