# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS Backup Subsystem - Models
================================

Defines the core data structures for system snapshots.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional


class SnapshotLevel(Enum):
    HOURLY = "H"
    DAILY = "D"
    WEEKLY = "W"
    MONTHLY = "M"
    BOOT = "B"
    ONDEMAND = "O"
    FACTORY = "F"  # Special level for Factory Reset baseline


@dataclass
class Snapshot:
    """Represents a single incremental system backup."""
    id: str  # Format: YYYY-MM-DD_HH-MM-SS
    timestamp: datetime
    level: SnapshotLevel
    path: Path  # Where this snapshot is stored on disk
    sys_version: str
    description: str = ""
    tags: List[str] = field(default_factory=list)

    @classmethod
    def create_new(cls, level: SnapshotLevel, base_dir: Path, sys_version: str, description: str = "") -> "Snapshot":
        now = datetime.now()
        ts_str = now.strftime("%Y-%m-%d_%H-%M-%S")
        snap_id = ts_str
        path = base_dir / snap_id
        
        return cls(
            id=snap_id,
            timestamp=now,
            level=level,
            path=path,
            sys_version=sys_version,
            description=description,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "path": str(self.path),
            "sys_version": self.sys_version,
            "description": self.description,
            "tags": self.tags,
        }
