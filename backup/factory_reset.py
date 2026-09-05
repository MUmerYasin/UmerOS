# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS Backup Subsystem - Factory Reset
=======================================

Handles the 'Factory Reset' lifecycle. A factory reset typically restores
the OS to its pristine baseline state. In UmerOS, this is achieved by
taking a protected SnapshotLevel.FACTORY backup immediately after installation
and locking it against deletion.
"""

import logging
from pathlib import Path

from .models import SnapshotLevel
from .restore import RestoreEngine
from .snapshot_engine import SnapshotEngine

log = logging.getLogger("UmerOS.Backup.FactoryReset")


class FactoryResetManager:
    def __init__(self, backup_dir: Path, system_root: Path = Path("/")):
        self.backup_dir = Path(backup_dir).resolve()
        self.system_root = Path(system_root).resolve()
        self.engine = SnapshotEngine(self.backup_dir, self.system_root)
        self.restorer = RestoreEngine(self.system_root)
        
    def get_factory_snapshot(self) -> Path:
        """Finds the designated Factory snapshot."""
        if not self.backup_dir.exists():
            return None
            
        import json
        
        for p in self.backup_dir.iterdir():
            info_file = p / "info.json"
            if p.is_dir() and info_file.exists():
                try:
                    with open(info_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("level") == SnapshotLevel.FACTORY.value:
                        return p
                except json.JSONDecodeError:
                    continue
        return None

    def create_factory_baseline(self, sys_version: str) -> bool:
        """
        Creates the factory baseline. Fails if one already exists.
        This should be called by the UmerOS installer upon first boot.
        """
        existing = self.get_factory_snapshot()
        if existing:
            log.warning(f"Factory baseline already exists at {existing}. Refusing to overwrite.")
            return False
            
        log.info("Creating pristine Factory Baseline snapshot...")
        snap = self.engine.create_snapshot(
            level=SnapshotLevel.FACTORY,
            description="Pristine Factory Baseline",
            sys_version=sys_version
        )
        log.info(f"Factory Baseline created: {snap.id}")
        return True

    def perform_factory_reset(self) -> bool:
        """
        Rolls back the entire system to the factory baseline snapshot.
        """
        baseline = self.get_factory_snapshot()
        if not baseline:
            log.error("No factory baseline snapshot found. Cannot perform factory reset.")
            return False
            
        log.critical("INITIATING FACTORY RESET!")
        log.critical("All system configurations, installed applications, and updates will be lost.")
        
        success = self.restorer.restore_snapshot(baseline)
        if success:
            log.info("Factory reset completed successfully. Reboot is recommended.")
        else:
            log.error("Factory reset encountered errors.")
        return success
