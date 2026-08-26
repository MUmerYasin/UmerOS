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
UmerOS /dev Virtualization & Passthrough Devices.

Modern mainline techniques adopted here (previously absent from UmerOS):

  VFIODevice    /dev/vfio/vfio + /dev/vfio/<group>
                IOMMU-agnostic secure userspace device passthrough.
  DmaBufHeap    /dev/dma_heap/{system,cma,secure}
                Explicit cross-driver buffer sharing heaps; since Linux
                6.19 vfio-pci can even export MMIO BARs as dma-bufs.
  MdevDevice    /dev/mdevctl + mediated group nodes
                Mediated (vGPU-style) device lifecycle management.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Virtualization")


class VFIODevice:
    """VFIO — Virtual Function I/O.

    /dev/vfio/vfio     IOMMU container fd (misc major 10)
    /dev/vfio/<group>  one node per IOMMU group, e.g. /dev/vfio/42

    Userspace drivers bind a group fd with a container fd and map DMA
    through the IOMMU, giving VMs safe direct device access (GPU, NIC,
    NVMe) without host kernel drivers. Modern deployments use the
    iommufd backend instead of the legacy type1 container.
    """

    CONTAINER_PATH = "/dev/vfio/vfio"
    GROUPS_DIR = "/dev/vfio"
    DEFAULT_GROUPS = (12, 14, 18, 26, 27)

    def __init__(self, groups: tuple = DEFAULT_GROUPS):
        self._groups = list(groups)
        self._containers_open = 0
        self._register()

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="vfio", path=self.GROUPS_DIR, dev_type=DeviceType.DIRECTORY,
            description="VFIO IOMMU groups",
        ))
        mgr.create_node(DeviceNode(
            name="vfio", path=self.CONTAINER_PATH,
            dev_type=DeviceType.CHAR, major=10, minor=196, mode=0o660,
            description="VFIO IOMMU container (userspace passthrough)",
            ioctl_callback=lambda req, arg: 0,
        ))
        for g in self._groups:
            mgr.create_node(DeviceNode(
                name=str(g), path=f"{self.GROUPS_DIR}/{g}",
                dev_type=DeviceType.CHAR, major=10, minor=g, mode=0o660,
                description=f"IOMMU group {g} (vfio-pci bound)",
            ))
        log.info("VFIODevice created (%d groups)", len(self._groups))

    def open_container(self) -> int:
        self._containers_open += 1
        return self._containers_open

    def get_info(self) -> Dict[str, Any]:
        return {
            "container": self.CONTAINER_PATH,
            "groups": list(self._groups),
            "containers_open": self._containers_open,
            "backend": "iommufd",
        }

    def __repr__(self) -> str:
        return f"<VFIODevice groups={self._groups}>"


class DmaBufHeap:
    """DMA-BUF heaps — explicit cross-device zero-copy buffer sharing.

    /dev/dma_heap/system  cached system-memory heap
    /dev/dma_heap/cma     contiguous-allocator heap
    /dev/dma_heap/secure  protected-content heap

    Exporters (GPU, VPU, camera — and since Linux 6.19 vfio-pci MMIO
    regions) hand out dma-buf fds which importers map without copies.
    """

    HEAP_DIR = "/dev/dma_heap"
    HEAPS = (
        ("system", "System RAM heap (cached)", 511),
        ("cma", "Contiguous memory heap", 512),
        ("secure", "Protected content heap", 513),
    )

    def __init__(self):
        self._allocations: List[Dict[str, Any]] = []
        self._next_id = 1
        self._register()

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="dma_heap", path=self.HEAP_DIR, dev_type=DeviceType.DIRECTORY,
            description="DMA-BUF allocation heaps",
        ))
        for name, desc, minor in self.HEAPS:
            mgr.create_node(DeviceNode(
                name=name, path=f"{self.HEAP_DIR}/{name}",
                dev_type=DeviceType.CHAR, major=254, minor=minor, mode=0o600,
                description=f"DMA-BUF {desc}",
                ioctl_callback=lambda req, arg: 0,
            ))
        log.info("DmaBufHeap created (%d heaps)", len(self.HEAPS))

    def allocate(self, heap: str, size_bytes: int, exporter: str) -> Dict[str, Any]:
        alloc = {
            "id": self._next_id,
            "heap": f"{self.HEAP_DIR}/{heap}",
            "size": size_bytes,
            "exporter": exporter,
        }
        self._next_id += 1
        self._allocations.append(alloc)
        log.debug("dma-buf allocated: %s", alloc)
        return alloc

    def get_info(self) -> Dict[str, Any]:
        return {
            "heaps": [h[0] for h in self.HEAPS],
            "active_allocations": len(self._allocations),
            "total_bytes": sum(a["size"] for a in self._allocations),
        }

    def __repr__(self) -> str:
        return f"<DmaBufHeap allocations={len(self._allocations)}>"


class MdevDevice:
    """Mediated devices — hardware slice virtualization (vGPU style).

    /dev/mctl                 lifecycle control node (mdevctl-compatible)
    /dev/<mdev_uuid>          one char node per created instance

    A parent PCI device (GPU, NIC with SR-IOV) is carved into mediated
    instances, each surfaced to one VM. UUID-based create/stop mirrors
    modern mdevctl workflows.
    """

    CONTROL_PATH = "/dev/mctl"
    MAX_INSTANCES_PER_PARENT = 4

    def __init__(self):
        self._instances: Dict[str, Dict[str, Any]] = {}
        self._register()

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="mctl", path=self.CONTROL_PATH,
            dev_type=DeviceType.CHAR, major=10, minor=240, mode=0o600,
            description="Mediated device control (mdevctl compatible)",
            ioctl_callback=lambda req, arg: 0,
        ))
        log.info("MdevDevice created")

    def create_instance(self, uuid: str, parent: str, mdev_type: str) -> bool:
        if uuid in self._instances:
            log.warning("mdev %s already exists", uuid)
            return False
        same_parent = sum(1 for i in self._instances.values() if i["parent"] == parent)
        if same_parent >= self.MAX_INSTANCES_PER_PARENT:
            log.warning("parent %s at capacity", parent)
            return False
        mgr = DeviceManager.get_instance()
        node_ok = mgr.create_node(DeviceNode(
            name=uuid, path=f"/dev/{uuid}", dev_type=DeviceType.CHAR,
            major=243, minor=len(self._instances) + 1, mode=0o600,
            description=f"mdev {mdev_type} on {parent}",
        ))
        self._instances[uuid] = {
            "uuid": uuid, "parent": parent, "type": mdev_type,
            "node_created": node_ok,
        }
        return True

    def stop_instance(self, uuid: str) -> bool:
        inst = self._instances.pop(uuid, None)
        if inst is None:
            return False
        DeviceManager.get_instance().remove_node(f"/dev/{uuid}")
        return True

    def get_info(self) -> Dict[str, Any]:
        return {"control": self.CONTROL_PATH, "instances": list(self._instances.values())}

    def __repr__(self) -> str:
        return f"<MdevDevice instances={len(self._instances)}>"
