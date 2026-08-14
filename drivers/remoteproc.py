"""
UmerOS Remoteproc Subsystem
============================
Kernel-like remoteproc subsystem for remote processor management.
Implements remote processor lifecycle, firmware loading, and crash recovery.

Reference: drivers/remoteproc/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# Remoteproc Constants
# ============================================================================

RPROC_SUCCESS: int = 0
RPROC_ERROR: int = 1
RPROC_NOT_FOUND: int = 2
RPROC_BUSY: int = 3

RPROC_MAX_DEVICES: int = 16
RPROC_MAX_RESOURCES: int = 128
RPROC_MAX_VRINGS: int = 4
RPROC_MAX_CARRIERS: int = 32


class RprocState(IntEnum):
    """Remote processor state."""
    OFFLINE: int = 0
    SUSPENDED: int = 1
    RUNNING: int = 2
    CRASHED: int = 3
    RECOVERING: int = 4


class RprocCrashType(IntEnum):
    """Remote processor crash type."""
    UNKNOWN: int = 0
    PANIC: int = 1
    WATCHDOG: int = 2
    FIRMWARE: int = 3


class RprocMemType(IntEnum):
    """Remote processor memory region type."""
    DEVICE: int = 0
    IRAM: int = 1
    DRAM: int = 2
    VEPA: int = 3


# ============================================================================
# Remoteproc Resource Table
# ============================================================================

@dataclass
class RprocResource:
    """Remote processor resource (mirrors struct fw_rsc)."""
    offset: int = 0
    rtype: int = 0
    data: bytes = b''


@dataclass
class RprocVring:
    """Remote processor vring (mirrors struct fw_rsc_vdev)."""
    vring_id: int
    num: int = 256
    notifyid: int = 0
    pa: int = 0
    da: int = 0
    align: int = 0
    node: str = ''
    registered: bool = False

    def get_info(self) -> Dict[str, Any]:
        return {
            "id": self.vring_id,
            "num": self.num,
            "notifyid": self.notifyid,
        }


@dataclass
class RprocResourceTable:
    """Remote processor resource table (mirrors struct fw_rsc_table)."""
    ver: int = 1
    num: int = 0
    resources: List[RprocResource] = field(default_factory=list)
    vdevs: List[RprocVring] = field(default_factory=list)

    def add_resource(self, res: RprocResource) -> int:
        self.resources.append(res)
        self.num = len(self.resources)
        return RPROC_SUCCESS

    def add_vdev(self, vdev: RprocVring) -> int:
        self.vdevs.append(vdev)
        return RPROC_SUCCESS


# ============================================================================
# Remoteproc Memory
# ============================================================================

@dataclass
class RprocMemory:
    """Remote processor memory region (mirrors struct rproc_mem)."""
    name: str
    base: int
    size: int
    mem_type: RprocMemType = RprocMemType.DRAM
    cached: bool = False
    iommu_domain: Optional[int] = None

    def map(self) -> int:
        return RPROC_SUCCESS

    def unmap(self) -> int:
        return RPROC_SUCCESS

    def read(self, offset: int, length: int) -> bytes:
        return b'\x00' * length

    def write(self, offset: int, data: bytes) -> int:
        return RPROC_SUCCESS

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base": hex(self.base),
            "size": hex(self.size),
            "type": self.mem_type.name,
        }


# ============================================================================
# Remoteproc Device
# ============================================================================

@dataclass
class RprocDevice:
    """Remote processor device (mirrors struct rproc)."""
    name: str
    index: int
    state: RprocState = RprocState.OFFLINE
    firmware: str = ""
    crash_type: RprocCrashType = RprocCrashType.UNKNOWN
    crash_count: int = 0
    memory: Dict[str, RprocMemory] = field(default_factory=dict)
    resources: RprocResourceTable = field(default_factory=RprocResourceTable)
    vrings: List[RprocVring] = field(default_factory=list)
    name_table: Dict[int, str] = field(default_factory=dict)
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def boot(self) -> int:
        if self.state != RprocState.OFFLINE:
            return RPROC_ERROR
        self.state = RprocState.RUNNING
        self._notify("boot")
        return RPROC_SUCCESS

    def shutdown(self) -> int:
        if self.state != RprocState.RUNNING:
            return RPROC_ERROR
        self.state = RprocState.OFFLINE
        self._notify("shutdown")
        return RPROC_SUCCESS

    def suspend(self) -> int:
        if self.state != RprocState.RUNNING:
            return RPROC_ERROR
        self.state = RprocState.SUSPENDED
        self._notify("suspend")
        return RPROC_SUCCESS

    def resume(self) -> int:
        if self.state != RprocState.SUSPENDED:
            return RPROC_ERROR
        self.state = RprocState.RUNNING
        self._notify("resume")
        return RPROC_SUCCESS

    def crash(self, crash_type: RprocCrashType) -> int:
        self.state = RprocState.CRASHED
        self.crash_type = crash_type
        self.crash_count += 1
        self._notify("crash")
        return RPROC_SUCCESS

    def recover(self) -> int:
        if self.state != RprocState.CRASHED:
            return RPROC_ERROR
        self.state = RprocState.RECOVERING
        self._notify("recovering")
        return RPROC_SUCCESS

    def add_memory(self, mem: RprocMemory) -> int:
        self.memory[mem.name] = mem
        return RPROC_SUCCESS

    def get_memory(self, name: str) -> Optional[RprocMemory]:
        return self.memory.get(name)

    def add_vring(self, vring: RprocVring) -> int:
        if len(self.vrings) >= RPROC_MAX_VRINGS:
            return RPROC_ERROR
        self.vrings.append(vring)
        return RPROC_SUCCESS

    def register_ops(self, ops: Dict[str, Callable]) -> None:
        self._ops.update(ops)

    def register_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify(self, event: str) -> None:
        for cb in self._listeners:
            cb(self.name, event)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.name,
            "firmware": self.firmware,
            "crash_count": self.crash_count,
            "memory": len(self.memory),
            "vrings": len(self.vrings),
        }


# ============================================================================
# Remoteproc Subsystem
# ============================================================================

class RprocSubsystem:
    """Central remoteproc subsystem managing remote processors."""

    def __init__(self) -> None:
        self._devices: Dict[str, RprocDevice] = {}
        self._next_index: int = 0

    def register_device(self, device: RprocDevice) -> int:
        device.index = self._next_index
        device.registered = True
        self._devices[device.name] = device
        self._next_index += 1
        return RPROC_SUCCESS

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return RPROC_SUCCESS

    def get_device(self, name: str) -> Optional[RprocDevice]:
        return self._devices.get(name)

    def enumerate_devices(self) -> List[RprocDevice]:
        return list(self._devices.values())

    def get_topology(self) -> Dict[str, Any]:
        return {
            "devices": len(self._devices),
            "running": sum(1 for d in self._devices.values()
                          if d.state == RprocState.RUNNING),
            "crashed": sum(1 for d in self._devices.values()
                          if d.state == RprocState.CRASHED),
        }


# ============================================================================
# Global Remoteproc Instance
# ============================================================================

_global_rproc: Optional[RprocSubsystem] = None


def get_global_rproc() -> RprocSubsystem:
    global _global_rproc
    if _global_rproc is None:
        _global_rproc = RprocSubsystem()
    return _global_rproc


def register_rproc_device(device: RprocDevice) -> int:
    return get_global_rproc().register_device(device)


def rproc_boot(name: str) -> int:
    dev = get_global_rproc().get_device(name)
    return dev.boot() if dev else RPROC_ERROR


def rproc_shutdown(name: str) -> int:
    dev = get_global_rproc().get_device(name)
    return dev.shutdown() if dev else RPROC_ERROR
