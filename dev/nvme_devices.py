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
UmerOS /dev — NVMe (Non-Volatile Memory Express) devices.

 /dev structure:
  /dev/nvme0, /dev/nvme1, ...       — NVMe controller char devices (240:0+)
  /dev/nvme0n1, /dev/nvme0n2, ...   — NVMe namespaces (block 259:0+)
  /dev/nvme0n1p1, ...p16            — NVMe namespace partitions

Major:Minor numbers:
  nvme*     = 243:0+ (char, controller admin)
  nvme*n*   = 259:0+ (block, namespaces)
  nvme*n*p* = 259:0+ (block, partitions, sequential)

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.NVMeDevices")


class NVMeController:
    """/dev/nvme* — NVMe controller character devices.

    Provides administrative access to NVMe controllers.
    Each controller has its own char device for ioctl-based
    management (firmware update, namespace management, etc.).
    """

    MAJOR = 243
    MAX_CONTROLLERS = 16

    def __init__(self):
        self._controllers: Dict[int, Dict[str, Any]] = {}
        self._register_controllers()
        log.info("NVMeController: registered %d controllers", self.MAX_CONTROLLERS)

    def _register_controllers(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_CONTROLLERS):
            mgr.create_node(DeviceNode(
                name=f"nvme{i}", path=f"/dev/nvme{i}",
                dev_type=DeviceType.CHAR,
                major=self.MAJOR, minor=i, mode=0o600,
                description=f"NVMe controller {i}",
                ioctl_callback=lambda r, a, n=i: self._on_ioctl(r, a, n),
            ))
            self._controllers[i] = {
                "namespaces": [],
                "model": f"Simulated NVMe Controller {i}",
                "serial": f"SIM{i:04d}",
                "firmware": "1.0.0",
            }

    def _on_ioctl(self, request: int, arg: Any, ctrl_id: int) -> int:
        # NVME_IOCTL_ADMIN_CMD = 0x4E41
        if request == 0x4E41:
            return 0
        # NVME_IOCTL_IDENTIFY = 0x4E42
        if request == 0x4E42:
            return 0
        return -1

    def add_controller(self, controller_id: int = -1) -> int:
        if controller_id < 0:
            controller_id = max(self._controllers.keys(), default=-1) + 1
        if controller_id >= self.MAX_CONTROLLERS:
            return -1
        if controller_id not in self._controllers:
            mgr = DeviceManager.get_instance()
            mgr.create_node(DeviceNode(
                name=f"nvme{controller_id}",
                path=f"/dev/nvme{controller_id}",
                dev_type=DeviceType.CHAR,
                major=self.MAJOR, minor=controller_id, mode=0o600,
                description=f"NVMe controller {controller_id}",
            ))
            self._controllers[controller_id] = {
                "namespaces": [],
                "model": f"NVMe Controller {controller_id}",
            }
        log.info("NVMe: added controller %d", controller_id)
        return controller_id

    def remove_controller(self, ctrl_id: int) -> bool:
        if ctrl_id not in self._controllers:
            return False
        mgr = DeviceManager.get_instance()
        mgr.remove_node(f"/dev/nvme{ctrl_id}")
        del self._controllers[ctrl_id]
        log.info("NVMe: removed controller %d", ctrl_id)
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "max_controllers": self.MAX_CONTROLLERS,
            "active": list(self._controllers.keys()),
        }


class NVMeNamespace:
    """/dev/nvme*n* — NVMe namespace block devices.

    Each NVMe namespace is exposed as a block device.
    Partitions are automatically created for each namespace.

    namespace N on controller C = nvme{C}n{N}
    partition P of namespace N on controller C = nvme{C}n{N}p{P}
    """

    BLOCK_MAJOR = 259
    MAX_NAMESPACES_PER_CTRL = 16
    MAX_PARTITIONS = 16
    _minor_counter = 0

    def __init__(self):
        self._namespaces: Dict[str, Dict[str, Any]] = {}
        self._partitions: Dict[str, Dict[str, Any]] = {}
        self._register_default_namespaces()
        log.info("NVMeNamespace: registered default namespaces")

    def _alloc_minor(self) -> int:
        minor = NVMeNamespace._minor_counter
        NVMeNamespace._minor_counter += 1
        return minor

    def _register_default_namespaces(self) -> None:
        self.add_namespace(0, 1)

    def add_namespace(self, ctrl_id: int, ns_id: int,
                      size_bytes: int = 500 * 1024 * 1024) -> str:
        name = f"nvme{ctrl_id}n{ns_id}"
        if name in self._namespaces:
            return name
        minor = self._alloc_minor()
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name=name, path=f"/dev/{name}",
            dev_type=DeviceType.BLOCK,
            major=self.BLOCK_MAJOR, minor=minor, mode=0o660,
            description=f"NVMe namespace {ns_id} on controller {ctrl_id}",
            read_callback=lambda sz, m=minor: b"\x00" * sz,
            write_callback=lambda d, m=minor: len(d),
            ioctl_callback=lambda r, a, m=minor: self._on_ioctl(r, a),
        ))
        self._namespaces[name] = {
            "controller": ctrl_id,
            "namespace_id": ns_id,
            "size": size_bytes,
            "partitions": [],
        }
        # Create partitions
        for p in range(1, self.MAX_PARTITIONS + 1):
            pname = f"{name}p{p}"
            pminor = self._alloc_minor()
            mgr.create_node(DeviceNode(
                name=pname, path=f"/dev/{pname}",
                dev_type=DeviceType.BLOCK,
                major=self.BLOCK_MAJOR, minor=pminor, mode=0o660,
                description=f"NVMe namespace {ns_id} partition {p}",
                read_callback=lambda sz, m=pminor: b"\x00" * sz,
                write_callback=lambda d, m=pminor: len(d),
            ))
            self._partitions[pname] = {"namespace": name, "partition": p}
            self._namespaces[name]["partitions"].append(pname)
        log.info("NVMe: added namespace %s (%d bytes, %d partitions)",
                 name, size_bytes, self.MAX_PARTITIONS)
        return name

    def remove_namespace(self, ctrl_id: int, ns_id: int) -> bool:
        name = f"nvme{ctrl_id}n{ns_id}"
        if name not in self._namespaces:
            return False
        mgr = DeviceManager.get_instance()
        for pname in self._namespaces[name]["partitions"]:
            mgr.remove_node(f"/dev/{pname}")
            self._partitions.pop(pname, None)
        mgr.remove_node(f"/dev/{name}")
        del self._namespaces[name]
        log.info("NVMe: removed namespace %s", name)
        return True

    def _on_ioctl(self, request: int, arg: Any) -> int:
        # NVME_IOCTL_ID_NS = 0x4E40
        if request == 0x4E40:
            return 1
        return -1

    def get_info(self) -> Dict[str, Any]:
        return {
            "namespaces": list(self._namespaces.keys()),
            "partitions": list(self._partitions.keys()),
            "total_namespaces": len(self._namespaces),
            "total_partitions": len(self._partitions),
        }
