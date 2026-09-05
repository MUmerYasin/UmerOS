# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS Backup Subsystem - Restore Engine
========================================

Logic for rolling back the live filesystem to a previous snapshot state.
Restoration operates by copying files from the snapshot back to the root,
and removing files that exist on the root but not in the snapshot.
"""

import logging
import os
import shutil
from pathlib import Path

from .filters import PathFilter

log = logging.getLogger("UmerOS.Backup.Restore")


class RestoreEngine:
    def __init__(self, target_root: Path = Path("/")):
        self.target_root = Path(target_root).resolve()
        self.filter = PathFilter()
        
    def restore_snapshot(self, snapshot_dir: Path) -> bool:
        """
        Restores a snapshot to the target root.
        """
        snap_path = Path(snapshot_dir).resolve()
        data_dir = snap_path / "data"
        
        if not data_dir.exists():
            log.error(f"Invalid snapshot directory: {snap_path}")
            return False
            
        log.info(f"Starting restoration from {snap_path} to {self.target_root}")
        
        # Phase 1: Copy from snapshot to live system
        restored_files = 0
        for root, dirs, files in os.walk(data_dir):
            current_snap_dir = Path(root)
            rel_path = current_snap_dir.relative_to(data_dir)
            target_dir = self.target_root / rel_path
            
            # Ensure directory exists on target
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
                
            for f in files:
                src_file = current_snap_dir / f
                dest_file = target_dir / f
                
                try:
                    # Remove destination if it exists (to break hardlinks to the backup)
                    if dest_file.exists():
                        dest_file.unlink()
                    shutil.copy2(src_file, dest_file)
                    restored_files += 1
                except OSError as e:
                    log.error(f"Failed to restore {dest_file}: {e}")

        # Phase 2: Delete files on live system that are NOT in the snapshot
        # This ensures a perfect rollback of system state.
        deleted_files = 0
        for root, dirs, files in os.walk(self.target_root):
            current_live_dir = Path(root)
            
            # Filter directories (don't delete user data during system restore)
            dirs[:] = [d for d in dirs if self.filter.should_include(current_live_dir / d)]
            
            if not self.filter.should_include(current_live_dir):
                continue
                
            rel_path = current_live_dir.relative_to(self.target_root)
            snap_equiv_dir = data_dir / rel_path
            
            for f in files:
                live_file = current_live_dir / f
                if not self.filter.should_include(live_file):
                    continue
                    
                snap_equiv_file = snap_equiv_dir / f
                if not snap_equiv_file.exists():
                    try:
                        live_file.unlink()
                        deleted_files += 1
                    except OSError as e:
                        log.warning(f"Failed to delete {live_file}: {e}")
                        
        log.info(f"Restore complete. Restored: {restored_files}, Deleted: {deleted_files}")
        return True
