"""
UmerOS /dev/disk — Disk device symlinks.

FHS 3.0 /dev/disk:
  /dev/disk/by-id/         — Symlinks by disk ID (e.g. ata-WDC_WD10EZEX-...)
  /dev/disk/by-label/      — Symlinks by filesystem label
  /dev/disk/by-uuid/       — Symlinks by UUID
  /dev/disk/by-path/       — Symlinks by physical path
  /dev/disk/by-name/       — Symlinks by partition name (GPT PARTNAME)
  /dev/disk/by-partlabel/  — Symlinks by GPT partition label

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.DiskDevice")


class DiskDeviceLinks:
    """Disk device symlinks — /dev/disk/.

    Provides:
      /dev/disk/by-id/         — Disk by ID
      /dev/disk/by-label/      — Disk by label
      /dev/disk/by-uuid/       — Disk by UUID
      /dev/disk/by-path/       — Disk by path
      /dev/disk/by-name/       — Disk by partition name (GPT PARTNAME attribute)
      /dev/disk/by-partlabel/  — Disk by GPT partition label
    """

    def __init__(self):
        self._links: Dict[str, Dict[str, str]] = {}
        self._register_directories()
        self._create_default_links()
        log.info("DiskDeviceLinks created")

    def _register_directories(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="disk", path="/dev/disk", dev_type=DeviceType.DIRECTORY,
            description="Disk symlinks",
        ))
        for sub in ("by-id", "by-label", "by-uuid", "by-path", "by-name", "by-partlabel"):
            mgr.create_node(DeviceNode(
                name=sub, path=f"/dev/disk/{sub}", dev_type=DeviceType.DIRECTORY,
                description=f"Disk symlinks by {sub.replace('by-', '')}",
            ))

    def _create_default_links(self) -> None:
        defaults = {
            "by-id": [
                ("ata-WDC_WD10EZEX-08WN4A0_WD-WCC1T0123456", "/dev/sda"),
                ("scsi-0:0:0:0", "/dev/sdb"),
            ],
            "by-label": [
                ("root", "/dev/sda1"),
                ("data", "/dev/sdb1"),
            ],
            "by-uuid": [
                ("1234-5678-ABCD-EF01", "/dev/sda1"),
                ("ABCD-EF01-1234-5678", "/dev/sdb1"),
            ],
            "by-path": [
                ("pci-0000:00:1f.2-ata-1.0", "/dev/sda"),
                ("pci-0000:00:1f.2-ata-2.0", "/dev/sdb"),
            ],
            "by-name": [
                ("boot", "/dev/sda1"),
                ("swap", "/dev/sda2"),
                ("root", "/dev/sda3"),
                ("home", "/dev/sdb1"),
            ],
            "by-partlabel": [
                ("EFI System Partition", "/dev/sda1"),
                ("swap", "/dev/sda2"),
                ("filesystem", "/dev/sda3"),
                ("home", "/dev/sdb1"),
            ],
        }
        for category, pairs in defaults.items():
            for name, target in pairs:
                self.add_link(category, name, target)

    def add_link(self, category: str, name: str, target_path: str) -> bool:
        """Create a disk device symlink."""
        path = f"/dev/disk/{category}/{name}"
        if path in self._links:
            return False
        mgr = DeviceManager.get_instance()
        node = DeviceNode(
            name=name, path=path, dev_type=DeviceType.SYMLINK,
            symlink_target=target_path,
            description=f"Disk {category}/{name} → {target_path}",
        )
        if mgr.create_node(node):
            self._links[path] = {"category": category, "name": name, "target": target_path}
            return True
        return False

    def remove_link(self, category: str, name: str) -> bool:
        path = f"/dev/disk/{category}/{name}"
        if path not in self._links:
            return False
        mgr = DeviceManager.get_instance()
        mgr.remove_node(path)
        del self._links[path]
        return True

    def list_by_category(self, category: str) -> Dict[str, str]:
        return {
            v["name"]: v["target"]
            for v in self._links.values()
            if v["category"] == category
        }

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/disk",
            "total_links": len(self._links),
            "categories": list({v["category"] for v in self._links.values()}),
        }

    def __repr__(self) -> str:
        return f"<DiskDeviceLinks links={len(self._links)}>"
