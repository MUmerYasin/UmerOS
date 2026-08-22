"""
UmerOS /tmp — Automated Garbage Collection & Reaper Engine
==========================================================

Implements tmpwatch and systemd-tmpfiles cleanup semantics for UmerOS.

Capabilities:
-------------
* Age-based Reaper (atime/mtime threshold pruning).
* Boot-time Cleaner (clean_on_boot).
* Size-based High-Water Mark Reaper (quota enforcement).
* Socket & Protected Directory Exclusion (.X11-unix, .ICE-unix, etc.).
* Dry-run simulation mode.

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import fnmatch
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .fhs import DEFAULT_TMP_ROOT, PROTECTED_SOCKET_DIRS

log = logging.getLogger("UmerOS.Tmp.Reaper")

# Default expiration: 10 days in seconds
DEFAULT_MAX_AGE_SEC = 10 * 86400


@dataclass
class ReapReport:
    """Summary report of a cleanup execution."""
    reaped_files: List[str] = field(default_factory=list)
    reaped_dirs: List[str] = field(default_factory=list)
    bytes_freed: int = 0
    skipped_items: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False

    def summary(self) -> str:
        mode_str = " (DRY-RUN)" if self.dry_run else ""
        return (
            f"TmpReaper Report{mode_str}:\n"
            f"  - Files reaped:   {len(self.reaped_files)}\n"
            f"  - Dirs reaped:    {len(self.reaped_dirs)}\n"
            f"  - Space freed:    {self.bytes_freed} bytes\n"
            f"  - Skipped items:  {len(self.skipped_items)}\n"
            f"  - Errors:         {len(self.errors)}"
        )


class TmpReaper:
    """
    Automated temporary file cleanup and reaper controller.
    """

    def __init__(
        self,
        tmp_root: Path | str = DEFAULT_TMP_ROOT,
        default_max_age_sec: float = DEFAULT_MAX_AGE_SEC,
        protected_dirs: Optional[Set[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> None:
        self.tmp_root = Path(tmp_root).resolve()
        self.default_max_age_sec = default_max_age_sec
        self.protected_dirs = protected_dirs or PROTECTED_SOCKET_DIRS
        self.exclude_patterns = exclude_patterns or ["*.keep", ".gitignore"]

    def _is_excluded(self, item: Path) -> bool:
        """Checks if a file or directory is protected or matches exclusion globs."""
        if item.name in self.protected_dirs:
            return True
        for pat in self.exclude_patterns:
            if fnmatch.fnmatch(item.name, pat):
                return True
        return False

    def clean_by_age(
        self,
        max_age_seconds: Optional[float] = None,
        dry_run: bool = False,
    ) -> ReapReport:
        """
        Removes files in /tmp that have not been accessed/modified within max_age_seconds.
        """
        max_age = max_age_seconds if max_age_seconds is not None else self.default_max_age_sec
        now = time.time()
        report = ReapReport(dry_run=dry_run)

        if not self.tmp_root.exists():
            return report

        for root, dirs, files in os.walk(self.tmp_root, topdown=False):
            root_path = Path(root)

            # Skip protected directories
            if root_path.name in self.protected_dirs or any(p in root_path.parts for p in self.protected_dirs):
                report.skipped_items.append(str(root_path))
                continue

            # Check and clean files
            for f in files:
                fp = root_path / f
                if self._is_excluded(fp):
                    report.skipped_items.append(str(fp))
                    continue

                try:
                    st = fp.stat()
                    last_active = max(st.st_mtime, st.st_atime)
                    age = now - last_active

                    if age >= max_age:
                        report.bytes_freed += st.st_size
                        report.reaped_files.append(str(fp))
                        if not dry_run:
                            fp.unlink()
                except Exception as e:
                    report.errors.append(f"Error removing {fp}: {e}")

            # Check and clean empty directories (except root)
            if root_path != self.tmp_root:
                try:
                    if not any(root_path.iterdir()):
                        report.reaped_dirs.append(str(root_path))
                        if not dry_run:
                            root_path.rmdir()
                except Exception as e:
                    report.errors.append(f"Error removing dir {root_path}: {e}")

        return report

    def clean_on_boot(self, dry_run: bool = False) -> ReapReport:
        """
        Emulates boot-time cleanup of /tmp: wipes all transient files while
        preserving protected sockets (.X11-unix, etc.).
        """
        return self.clean_by_age(max_age_seconds=0.0, dry_run=dry_run)

    def clean_by_quota(
        self,
        max_total_bytes: int,
        dry_run: bool = False,
    ) -> ReapReport:
        """
        High-water mark cleaner: if total /tmp size exceeds max_total_bytes,
        reaps oldest files first until size is under threshold.
        """
        report = ReapReport(dry_run=dry_run)
        if not self.tmp_root.exists():
            return report

        # Collect all eligible files sorted by age (oldest first)
        file_entries = []
        total_size = 0

        for root, _, files in os.walk(self.tmp_root):
            root_path = Path(root)
            if root_path.name in self.protected_dirs or any(p in root_path.parts for p in self.protected_dirs):
                continue

            for f in files:
                fp = root_path / f
                if self._is_excluded(fp):
                    continue
                try:
                    st = fp.stat()
                    total_size += st.st_size
                    file_entries.append((st.st_mtime, st.st_size, fp))
                except OSError:
                    pass

        if total_size <= max_total_bytes:
            return report

        # Sort oldest first
        file_entries.sort(key=lambda x: x[0])

        bytes_to_free = total_size - max_total_bytes
        freed = 0

        for _, size, fp in file_entries:
            if freed >= bytes_to_free:
                break
            try:
                report.bytes_freed += size
                report.reaped_files.append(str(fp))
                if not dry_run:
                    fp.unlink()
                freed += size
            except Exception as e:
                report.errors.append(f"Error removing {fp}: {e}")

        return report
