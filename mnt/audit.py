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
UmerOS /mnt - Mount History and Audit Trail
=============================================

Provides a persistent audit log for all mount/unmount operations
performed under ``/mnt/``.  Used for:

* Security auditing (who mounted what, when).
* Debugging stale mount issues.
* Compliance with TLDP mount logging conventions.
* Tracking mount point lifecycle for cleanup.

The TLDP spec doesn't define a formal audit format, but
``/var/log/`` and ``/var/run/`` are the standard locations
for mount-related state.  This module uses a structured JSON
audit log for machine readability.

FHS 3.0 /mnt interaction:

    The content of /mnt is a local issue.  Auditing ensures
    that temporary admin mounts are tracked and cleaned up.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Mnt.Audit")

DEFAULT_AUDIT_LOG = "/var/log/umeos-mnt-audit.jsonl"


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

class AuditEvent(str, Enum):
    """Types of mount-related events."""
    MOUNT          = "mount"
    UNMOUNT        = "unmount"
    REMOUNT        = "remount"
    MOUNT_CREATE   = "mount_point_create"
    MOUNT_REMOVE   = "mount_point_remove"
    MOUNT_STALE    = "mount_point_stale"
    USER_MOUNT     = "user_mount"
    USER_UNMOUNT   = "user_umount"
    PERMISSION_DENY = "permission_deny"
    ERROR          = "error"
    CLEANUP        = "cleanup"


# ---------------------------------------------------------------------------
# Audit record
# ---------------------------------------------------------------------------

@dataclass
class AuditRecord:
    """One audit event in the log.

    Attributes:
        timestamp:     Event time (Unix seconds).
        event:         Event type string.
        device:        Block device involved.
        mount_point:   Mount point path.
        fstype:        Filesystem type.
        options:       Mount options string.
        user:          Username (or ``root``).
        uid:           User ID.
        success:       Whether the operation succeeded.
        message:       Human-readable detail.
        extra:         Additional metadata dict.
    """
    timestamp: float = field(default_factory=time.time)
    event: str = ""
    device: str = ""
    mount_point: str = ""
    fstype: str = ""
    options: str = ""
    user: str = "root"
    uid: int = 0
    success: bool = True
    message: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event": self.event,
            "device": self.device,
            "mount_point": self.mount_point,
            "fstype": self.fstype,
            "options": self.options,
            "user": self.user,
            "uid": self.uid,
            "success": self.success,
            "message": self.message,
            "extra": self.extra,
        }

    def to_json_line(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False)

    @classmethod
    def from_json_line(cls, line: str) -> AuditRecord:
        data = json.loads(line)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AuditLog:
    """Persistent append-only audit log for /mnt operations.

    Uses JSONL (one JSON object per line) for easy tailing
    and querying.

    Usage::

        audit = AuditLog()
        audit.log_mount("/dev/sdb1", "/mnt/usb", "vfat", user="alice")
        audit.log_umount("/mnt/usb", user="alice")

        # Query
        recent = audit.recent(limit=10)
        usb_events = audit.for_mount_point("/mnt/usb")
        alice_events = audit.for_user("alice")
    """

    def __init__(self, log_path: str | Path = DEFAULT_AUDIT_LOG) -> None:
        self._log_path = str(log_path)
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        log_dir = os.path.dirname(self._log_path)
        if log_dir and not os.path.isdir(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except PermissionError:
                log.warning("Cannot create audit log directory: %s", log_dir)

    # -- Write ---------------------------------------------------------------

    def _append(self, record: AuditRecord) -> None:
        """Append a record to the log file."""
        line = record.to_json_line() + "\n"
        try:
            with open(self._log_path, "a", encoding="utf-8") as fh:
                fh.write(line)
        except PermissionError:
            log.error("Cannot write audit log: %s", self._log_path)
        except OSError as exc:
            log.error("Audit log write error: %s", exc)

    def log_event(
        self,
        event: AuditEvent,
        *,
        device: str = "",
        mount_point: str = "",
        fstype: str = "",
        options: str = "",
        user: str = "root",
        uid: int = 0,
        success: bool = True,
        message: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        """Log an arbitrary mount event."""
        record = AuditRecord(
            timestamp=time.time(),
            event=event.value,
            device=device,
            mount_point=mount_point,
            fstype=fstype,
            options=options,
            user=user,
            uid=uid,
            success=success,
            message=message,
            extra=extra or {},
        )
        self._append(record)
        log.debug("Audit: %s %s -> %s", event.value, device, mount_point)
        return record

    def log_mount(
        self,
        device: str,
        mount_point: str,
        fstype: str = "",
        options: str = "",
        user: str = "root",
        uid: int = 0,
        success: bool = True,
        message: str = "",
    ) -> AuditRecord:
        return self.log_event(
            AuditEvent.MOUNT,
            device=device, mount_point=mount_point,
            fstype=fstype, options=options,
            user=user, uid=uid, success=success, message=message,
        )

    def log_umount(
        self,
        mount_point: str,
        device: str = "",
        user: str = "root",
        uid: int = 0,
        success: bool = True,
        message: str = "",
    ) -> AuditRecord:
        return self.log_event(
            AuditEvent.UNMOUNT,
            device=device, mount_point=mount_point,
            user=user, uid=uid, success=success, message=message,
        )

    def log_user_mount(
        self,
        device: str,
        mount_point: str,
        fstype: str = "",
        user: str = "",
        uid: int = 0,
    ) -> AuditRecord:
        return self.log_event(
            AuditEvent.USER_MOUNT,
            device=device, mount_point=mount_point,
            fstype=fstype, user=user, uid=uid,
            message=f"User {user} mounted {device}",
        )

    def log_user_umount(
        self,
        mount_point: str,
        user: str = "",
        uid: int = 0,
    ) -> AuditRecord:
        return self.log_event(
            AuditEvent.USER_UNMOUNT,
            mount_point=mount_point,
            user=user, uid=uid,
            message=f"User {user} unmounted {mount_point}",
        )

    def log_permission_deny(
        self,
        device: str,
        mount_point: str,
        user: str = "",
        uid: int = 0,
        reason: str = "",
    ) -> AuditRecord:
        return self.log_event(
            AuditEvent.PERMISSION_DENY,
            device=device, mount_point=mount_point,
            user=user, uid=uid, success=False,
            message=reason,
        )

    def log_cleanup(
        self,
        paths: List[str],
        user: str = "root",
        message: str = "",
    ) -> AuditRecord:
        return self.log_event(
            AuditEvent.CLEANUP,
            user=user,
            message=message or f"Cleaned up {len(paths)} mount points",
            extra={"removed_paths": paths},
        )

    # -- Read ----------------------------------------------------------------

    def _read_all(self) -> List[AuditRecord]:
        """Read all records from the log."""
        records: List[AuditRecord] = []
        try:
            with open(self._log_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            records.append(AuditRecord.from_json_line(line))
                        except (json.JSONDecodeError, TypeError) as exc:
                            log.warning("Skipping malformed audit line: %s", exc)
        except FileNotFoundError:
            pass
        return records

    @property
    def records(self) -> List[AuditRecord]:
        return self._read_all()

    def recent(self, limit: int = 20) -> List[AuditRecord]:
        """Most recent *limit* events."""
        return self._read_all()[-limit:]

    def for_mount_point(self, mount_point: str) -> List[AuditRecord]:
        """All events for a given mount point."""
        return [r for r in self._read_all() if r.mount_point == mount_point]

    def for_user(self, username: str) -> List[AuditRecord]:
        """All events by a given user."""
        return [r for r in self._read_all() if r.user == username]

    def for_device(self, device: str) -> List[AuditRecord]:
        """All events for a given device."""
        return [r for r in self._read_all() if r.device == device]

    def failed(self) -> List[AuditRecord]:
        """All failed operations."""
        return [r for r in self._read_all() if not r.success]

    def time_range(
        self,
        start: float,
        end: float,
    ) -> List[AuditRecord]:
        """Events within a time range."""
        return [
            r for r in self._read_all()
            if start <= r.timestamp <= end
        ]

    # -- Stats ---------------------------------------------------------------

    @property
    def stats(self) -> Dict[str, int]:
        records = self._read_all()
        return {
            "total": len(records),
            "mounts": sum(1 for r in records if r.event == AuditEvent.MOUNT.value),
            "unmounts": sum(1 for r in records if r.event == AuditEvent.UNMOUNT.value),
            "user_mounts": sum(1 for r in records if r.event == AuditEvent.USER_MOUNT.value),
            "permission_denials": sum(1 for r in records if r.event == AuditEvent.PERMISSION_DENY.value),
            "failed": sum(1 for r in records if not r.success),
        }

    # -- Maintenance ---------------------------------------------------------

    def rotate(self, max_records: int = 10000) -> int:
        """Truncate log to the most recent *max_records* entries.

        Returns the number of records removed.
        """
        records = self._read_all()
        if len(records) <= max_records:
            return 0

        to_keep = records[-max_records:]
        removed = len(records) - len(to_keep)

        try:
            with open(self._log_path, "w", encoding="utf-8") as fh:
                for record in to_keep:
                    fh.write(record.to_json_line() + "\n")
            log.info("Rotated audit log: removed %d records", removed)
        except PermissionError:
            log.error("Cannot rotate audit log: %s", self._log_path)
            return 0

        return removed


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Validate audit log operations."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "audit.jsonl")
        audit = AuditLog(log_path)

        # Log some events
        audit.log_mount("/dev/sdb1", "/mnt/usb", "vfat", user="alice")
        audit.log_umount("/mnt/usb", user="alice")
        audit.log_user_mount("/dev/fd0", "/mnt/floppy", "msdos", user="bob", uid=1001)
        audit.log_permission_deny("/dev/sda1", "/", user="alice", reason="no fstab entry")
        audit.log_mount("/dev/sdc1", "/mnt/backup", "ext4", success=False, message="device busy")

        # Read back
        records = audit.records
        if len(records) != 5:
            print(f"Expected 5 records, got {len(records)}")
            return False

        # Recent
        recent = audit.recent(limit=3)
        if len(recent) != 3:
            print(f"Expected 3 recent, got {len(recent)}")
            return False

        # Filter by mount point
        usb = audit.for_mount_point("/mnt/usb")
        if len(usb) != 2:
            print(f"Expected 2 /mnt/usb events, got {len(usb)}")
            return False

        # Filter by user
        alice = audit.for_user("alice")
        if len(alice) != 3:
            print(f"Expected 3 alice events, got {len(alice)}")
            return False

        # Failed operations
        failed = audit.failed()
        if len(failed) != 2:
            print(f"Expected 2 failed, got {len(failed)}")
            return False

        # Stats
        stats = audit.stats
        if stats["total"] != 5:
            print(f"Stats total wrong: {stats['total']}")
            return False
        if stats["mounts"] != 2:
            print(f"Stats mounts wrong: {stats['mounts']}")
            return False

        # Rotate
        removed = audit.rotate(max_records=3)
        if removed != 2:
            print(f"Expected 2 removed, got {removed}")
            return False
        if len(audit.records) != 3:
            print(f"After rotate expected 3, got {len(audit.records)}")
            return False

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("audit selftest:", "OK" if _selftest() else "FAIL")
