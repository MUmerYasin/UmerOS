# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS Disk Tools
=================

Disk and partition management utilities.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Tools.Disk")


@dataclass
class PartitionInfo:
    device: str
    mount_point: str
    fs_type: str
    size_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    percent_used: float = 0.0


@dataclass
class DiskInfo:
    device: str
    size_bytes: int = 0
    model: str = "Unknown"
    partitions: List[PartitionInfo] = field(default_factory=list)


class DiskManager:
    """Manages disk and partition information."""

    def __init__(self) -> None:
        self._partitions: List[PartitionInfo] = []

    def scan(self) -> List[PartitionInfo]:
        """Scan for mounted partitions."""
        self._partitions = []
        # Try /proc/mounts
        try:
            with open("/proc/mounts") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 4:
                        device = parts[0]
                        mount_point = parts[1]
                        fs_type = parts[2]
                        # Get size info
                        try:
                            total, used, free = shutil.disk_usage(mount_point)
                            pct = (used / total * 100) if total > 0 else 0.0
                        except OSError:
                            total, used, free, pct = 0, 0, 0, 0.0
                        self._partitions.append(PartitionInfo(
                            device=device,
                            mount_point=mount_point,
                            fs_type=fs_type,
                            size_bytes=total,
                            used_bytes=used,
                            free_bytes=free,
                            percent_used=pct,
                        ))
        except (FileNotFoundError, PermissionError):
            # Fallback: use shutil for root
            try:
                total, used, free = shutil.disk_usage("/")
                self._partitions.append(PartitionInfo(
                    device="/",
                    mount_point="/",
                    fs_type="unknown",
                    size_bytes=total,
                    used_bytes=used,
                    free_bytes=free,
                    percent_used=(used / total * 100) if total > 0 else 0.0,
                ))
            except Exception as e:
                log.warning("Failed to get disk usage: %s", e)
        return self._partitions

    def get_disk_usage(self, path: str = "/") -> Dict[str, int]:
        """Get disk usage for a path."""
        try:
            total, used, free = shutil.disk_usage(path)
            return {
                "total": total,
                "used": used,
                "free": free,
                "percent_used": (used / total * 100) if total > 0 else 0.0,
            }
        except Exception as e:
            log.warning("Failed to get disk usage for %s: %s", path, e)
            return {"total": 0, "used": 0, "free": 0, "percent_used": 0.0}

    @property
    def partitions(self) -> List[PartitionInfo]:
        return list(self._partitions)


def get_disk_usage(path: str = "/") -> Dict[str, int]:
    return DiskManager().get_disk_usage(path)


def list_partitions() -> List[PartitionInfo]:
    return DiskManager().scan()