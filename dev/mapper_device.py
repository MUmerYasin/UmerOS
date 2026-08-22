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
UmerOS /dev/mapper — Device-mapper (LVM, dm-crypt).

FHS 3.0 /dev/mapper:
  /dev/mapper/ — Device-mapper control and logical volumes.
  /dev/mapper/control — Device-mapper control node.

 major:minor: control = 10:236

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.MapperDevice")


class MapperDevice:
    """Device-mapper manager — /dev/mapper/.

    Provides:
      /dev/mapper/        — Mapper directory
      /dev/mapper/control — Device-mapper control node
      /dev/mapper/vg-lv   — Logical volume nodes
    """

    MAPPER_CONTROL_MAJOR = 10
    MAPPER_CONTROL_MINOR = 236

    def __init__(self):
        self._volumes: Dict[str, Dict[str, Any]] = {}
        self._register_directory()
        self._register_control()
        log.info("MapperDevice created")

    def _register_directory(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="mapper", path="/dev/mapper", dev_type=DeviceType.DIRECTORY,
            description="Device-mapper",
        ))

    def _register_control(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="control", path="/dev/mapper/control",
            dev_type=DeviceType.CHAR,
            major=self.MAPPER_CONTROL_MAJOR,
            minor=self.MAPPER_CONTROL_MINOR,
            mode=0o660,
            description="Device-mapper control",
            ioctl_callback=self._on_control_ioctl,
        ))

    def _on_control_ioctl(self, cmd: int, arg: Any) -> int:
        return 0

    def create_volume(self, name: str, size_sectors: int = 2048,
                      mode: str = "linear") -> bool:
        """Create a device-mapper logical volume."""
        if name in self._volumes:
            return False
        path = f"/dev/mapper/{name}"
        mgr = DeviceManager.get_instance()
        # Assign minor dynamically (starting from 0)
        minor = len(self._volumes)
        node = DeviceNode(
            name=name, path=path, dev_type=DeviceType.BLOCK,
            major=self.MAPPER_CONTROL_MAJOR, minor=minor,
            mode=0o660, description=f"DM volume {name}",
        )
        if mgr.create_node(node):
            self._volumes[name] = {
                "path": path, "size": size_sectors,
                "mode": mode, "minor": minor,
            }
            log.info("Mapper volume created: %s (%s, %d sectors)",
                     name, mode, size_sectors)
            return True
        return False

    def remove_volume(self, name: str) -> bool:
        if name not in self._volumes:
            return False
        path = self._volumes[name]["path"]
        mgr = DeviceManager.get_instance()
        mgr.remove_node(path)
        del self._volumes[name]
        log.info("Mapper volume removed: %s", name)
        return True

    def list_volumes(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._volumes)

    def get_volume_info(self, name: str) -> Optional[Dict[str, Any]]:
        return self._volumes.get(name)

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/mapper",
            "control": f"/dev/mapper/control ({self.MAPPER_CONTROL_MAJOR}:{self.MAPPER_CONTROL_MINOR})",
            "volume_count": len(self._volumes),
            "volumes": list(self._volumes.keys()),
        }

    def __repr__(self) -> str:
        return f"<MapperDevice volumes={len(self._volumes)}>"
