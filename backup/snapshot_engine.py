# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS Backup Subsystem - Snapshot Engine
=========================================

Core engine for creating Rsync-style incremental snapshots using hardlinks.
If a file exists in the previous snapshot and is unmodified, a hardlink is
created to save disk space. Otherwise, the file is copied.
"""

import json
import logging
import os
import shutil
import stat
from pathlib import Path
from typing import Optional

from .filters import PathFilter
from .models import Snapshot, SnapshotLevel

log = logging.getLogger("UmerOS.Backup.Engine")


class SnapshotEngine:
    def __init__(self, backup_dir: Path, source_root: Path = Path("/")):
        self.backup_dir = Path(backup_dir).resolve()
        self.source_root = Path(source_root).resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.filter = PathFilter()
        
    def _files_are_identical(self, src: Path, prev: Path) -> bool:
        """
        Quick check if files are identical based on size and mtime.
        (Similar to rsync's default behavior).
        """
        try:
            st_src = src.stat()
            st_prev = prev.stat()
            # Compare size and modification time
            return (st_src.st_size == st_prev.st_size and 
                    int(st_src.st_mtime) == int(st_prev.st_mtime))
        except OSError:
            return False

    def get_latest_snapshot(self) -> Optional[Path]:
        """Finds the most recent snapshot directory."""
        snapshots = []
        for p in self.backup_dir.iterdir():
            if p.is_dir() and (p / "info.json").exists():
                snapshots.append(p)
        if not snapshots:
            return None
        # Sort by folder name which is a timestamp
        snapshots.sort(key=lambda x: x.name, reverse=True)
        return snapshots[0]

    def create_snapshot(self, level: SnapshotLevel, description: str = "", sys_version: str = "2.0.0") -> Snapshot:
        """
        Creates a new incremental snapshot.
        """
        snap = Snapshot.create_new(level, self.backup_dir, sys_version, description)
        snap.path.mkdir(parents=True, exist_ok=False)
        
        prev_snap_dir = self.get_latest_snapshot()
        if prev_snap_dir:
            log.info(f"Creating incremental snapshot against: {prev_snap_dir.name}")
        else:
            log.info("No previous snapshot found. Creating initial full backup.")

        # Save metadata
        info_path = snap.path / "info.json"
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(snap.to_dict(), f, indent=4)

        copied_count = 0
        linked_count = 0

        # Note: on Windows/NTFS, os.link requires admin privileges or Developer Mode.
        # Since UmerOS targets a hybrid Unix/Linux-like architecture, we implement standard POSIX hardlinks.
        
        for root, dirs, files in os.walk(self.source_root):
            current_dir = Path(root)
            
            # Filter directories
            dirs[:] = [d for d in dirs if self.filter.should_include(current_dir / d)]
            
            if not self.filter.should_include(current_dir):
                continue
                
            # Create corresponding directory structure in the snapshot
            rel_path = current_dir.relative_to(self.source_root)
            dest_dir = snap.path / "data" / rel_path
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            for f in files:
                src_file = current_dir / f
                if not self.filter.should_include(src_file):
                    continue
                    
                dest_file = dest_dir / f
                
                # If we have a previous snapshot, try to hardlink
                hardlinked = False
                if prev_snap_dir:
                    prev_file = prev_snap_dir / "data" / rel_path / f
                    if prev_file.exists() and self._files_are_identical(src_file, prev_file):
                        try:
                            os.link(prev_file, dest_file)
                            hardlinked = True
                            linked_count += 1
                        except OSError as e:
                            log.debug(f"Hardlink failed for {f}: {e}. Falling back to copy.")
                
                if not hardlinked:
                    try:
                        shutil.copy2(src_file, dest_file)
                        copied_count += 1
                    except OSError as e:
                        log.warning(f"Failed to copy {src_file}: {e}")

        log.info(f"Snapshot complete. Copied: {copied_count}, Hardlinked: {linked_count}")
        return snap
