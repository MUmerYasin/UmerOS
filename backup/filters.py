# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS Backup Subsystem - Filters
=================================

Handles path exclusions and inclusions for snapshots.
Ensures we only snapshot system files and avoid user data, temp files,
and virtual file systems, mirroring the Timeshift design.
"""

import os
from pathlib import Path
from typing import List

# Default exclusions for a UNIX-like UmerOS hierarchy
DEFAULT_EXCLUDES = [
    "/dev",
    "/proc",
    "/sys",
    "/tmp",
    "/run",
    "/mnt",
    "/media",
    "/cdrom",
    "/lost+found",
    "/home",      # User data is excluded to prevent overwriting documents on restore
    "/root",      # Root's home is usually excluded
    "/var/tmp",
    "/var/run",
    "/.safety_backups", # Prevent infinite recursion with our own backups
    "/timeshift", # Exclude timeshift/backup folders
    "/backup",    # Our own backup directory
]

class PathFilter:
    """Evaluates whether a given path should be included in the snapshot."""

    def __init__(self, excludes: List[str] = None, includes: List[str] = None):
        self.excludes = [Path(p).resolve() for p in (excludes or DEFAULT_EXCLUDES)]
        self.includes = [Path(p).resolve() for p in (includes or [])]

    def should_include(self, target_path: Path) -> bool:
        """
        Returns True if the path should be backed up.
        """
        resolved = target_path.resolve()
        
        # Check explicit includes first (overrides excludes)
        for inc in self.includes:
            if resolved == inc or inc in resolved.parents:
                return True
                
        # Check excludes
        for exc in self.excludes:
            if resolved == exc or exc in resolved.parents:
                return False
                
        # Default include
        return True
