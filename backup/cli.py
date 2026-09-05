# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS Backup Subsystem - CLI
=============================

Command line interface (similar to timeshift) to create, restore,
and list snapshots, as well as trigger factory resets.

Usage:
    python -m backup.cli --create [--comments "description"] [--tags O,B,H,D,W,M]
    python -m backup.cli --restore [snapshot_id]
    python -m backup.cli --list
    python -m backup.cli --factory-reset
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from .factory_reset import FactoryResetManager
from .models import SnapshotLevel
from .restore import RestoreEngine
from .snapshot_engine import SnapshotEngine

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("backup_cli")

BACKUP_DIR = Path("/backup")
SOURCE_ROOT = Path("/")


def create_parser():
    parser = argparse.ArgumentParser(description="UmerOS Backup & System Restore Utility")
    
    parser.add_argument("--create", action="store_true", help="Create a new snapshot")
    parser.add_argument("--comments", type=str, default="", help="Description for the snapshot")
    parser.add_argument("--tags", type=str, default="O", choices=["O", "B", "H", "D", "W", "M"], 
                        help="Snapshot level (O=Ondemand, B=Boot, H=Hourly, D=Daily, W=Weekly, M=Monthly)")
    
    parser.add_argument("--restore", type=str, nargs='?', const='LATEST', help="Restore a snapshot (defaults to latest)")
    parser.add_argument("--list", action="store_true", help="List all available snapshots")
    
    parser.add_argument("--create-factory", action="store_true", help="Initialize the factory baseline snapshot")
    parser.add_argument("--factory-reset", action="store_true", help="Restore the system to the factory baseline")
    
    # Internal dev overrides
    parser.add_argument("--backup-dir", type=str, help="Override backup destination directory")
    parser.add_argument("--source-root", type=str, help="Override source root directory")
    
    return parser


def print_list(backup_dir: Path):
    if not backup_dir.exists():
        print(f"Backup directory {backup_dir} does not exist.")
        return
        
    import json
    
    print(f"{'Snapshot ID':<25} {'Level':<10} {'Description'}")
    print("-" * 60)
    
    snaps = []
    for p in backup_dir.iterdir():
        info_file = p / "info.json"
        if p.is_dir() and info_file.exists():
            try:
                with open(info_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    snaps.append(data)
            except Exception:
                pass
                
    snaps.sort(key=lambda x: x["id"])
    for s in snaps:
        print(f"{s['id']:<25} {s['level']:<10} {s['description']}")


def main(argv=None):
    parser = create_parser()
    args = parser.parse_args(argv)
    
    backup_dir = Path(args.backup_dir) if args.backup_dir else BACKUP_DIR
    source_root = Path(args.source_root) if args.source_root else SOURCE_ROOT
    
    if args.list:
        print_list(backup_dir)
        return 0
        
    if args.create:
        engine = SnapshotEngine(backup_dir, source_root)
        level = SnapshotLevel(args.tags)
        log.info(f"Creating snapshot (Level: {level.name})...")
        snap = engine.create_snapshot(level, description=args.comments)
        log.info(f"Snapshot created successfully: {snap.id}")
        return 0
        
    if args.restore:
        engine = SnapshotEngine(backup_dir, source_root)
        restorer = RestoreEngine(source_root)
        
        target = args.restore
        if target == 'LATEST':
            latest = engine.get_latest_snapshot()
            if not latest:
                log.error("No snapshots available to restore.")
                return 1
            snapshot_path = latest
        else:
            snapshot_path = backup_dir / target
            
        if not snapshot_path.exists():
            log.error(f"Snapshot {target} not found in {backup_dir}.")
            return 1
            
        restorer.restore_snapshot(snapshot_path)
        return 0
        
    if args.create_factory:
        frm = FactoryResetManager(backup_dir, source_root)
        if frm.create_factory_baseline("2.0.0"):
            return 0
        return 1
        
    if args.factory_reset:
        frm = FactoryResetManager(backup_dir, source_root)
        print("WARNING: This will erase all system changes and revert to the factory baseline.")
        ans = input("Are you sure? (Type 'I AGREE' to proceed): ")
        if ans == "I AGREE":
            frm.perform_factory_reset()
            return 0
        else:
            print("Aborted.")
            return 1

    parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main())
