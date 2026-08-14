"""
UmerOS NVMe Subsystem
======================
Kernel-like NVMe (Non-Volatile Memory Express) subsystem.
Implements NVMe controllers, namespaces, and I/O queues for
high-performance storage.

Reference: drivers/nvme/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# NVMe Constants
# ============================================================================

NVME_SUCCESS: int = 0
NVME_ERROR: int = 1
NVME_NOT_FOUND: int = 2
NVME_BUSY: int = 3
NVME_INVALID: int = 4

NVME_MAX_NAMESPACES: int = 1024
NVME_MAX_IO_QUEUES: int = 64
NVME_MAX_CMDS: int = 1024
NVME_MAX_LBA: int = 0xFFFFFFFF
NVME_BLOCK_SIZE: int = 512
NVME_PAGE_SIZE: int = 4096


class NVMEState(IntEnum):
    """NVMe controller state."""
    DISABLED: int = 0
    ENABLED: int = 1
    CONNECTED: int = 2
    ERROR: int = 3


class NVMEAdminOpcode(IntEnum):
    """NVMe admin opcodes."""
    DELETE_IO_SQ: int = 0x00
    CREATE_IO_SQ: int = 0x01
    DELETE_IO_CQ: int = 0x04
    CREATE_IO_CQ: int = 0x05
    IDENTIFY: int = 0x06
    SET_FEATURES: int = 0x09
    GET_FEATURES: int = 0x0A
    ASYNC_EVENT: int = 0x0C
    SHUTDOWN: int = 0x08


class NVMeIOOpcode(IntEnum):
    """NVMe I/O opcodes."""
    FLUSH: int = 0x00
    WRITE: int = 0x01
    READ: int = 0x02
    WRITE_ZEROES: int = 0x08
    DATASET_MANAGE: int = 0x09
    WRITE_UNCORRECTABLE: int = 0x0D
    VERIFY: int = 0x0E


class NVMEStatus(IntEnum):
    """NVMe status codes."""
    SUCCESS: int = 0x0
    INVALID_OPCODE: int = 0x1
    INVALID_FIELD: int = 0x2
    DATA_TRANSFER: int = 0x4
    ABORT_REQUESTED: int = 0x7
    INTERNAL_ERROR: int = 0x6
    namespace_unattached: int = 0x3C


# ============================================================================
# NVMe Command
# ============================================================================

@dataclass
class NVMeCommand:
    """NVMe command entry (mirrors nvme_command)."""
    opcode: int = 0
    flags: int = 0
    nsid: int = 0
    cdw10: int = 0
    cdw11: int = 0
    cdw12: int = 0
    cdw13: int = 0
    cdw14: int = 0
    cdw15: int = 0
    meta_ptr: int = 0
    data_ptr: int = 0
    command_id: int = 0
    metadata: bytes = b''
    data: bytes = b''


@dataclass
class NVMeCompletion:
    """NVMe completion entry."""
    command_id: int = 0
    status: int = 0
    result: int = 0
    phase: int = 1

    @property
    def is_success(self) -> bool:
        return (self.status & 0x7F) == 0


# ============================================================================
# NVMe Namespace
# ============================================================================

@dataclass
class NVMeNamespace:
    """NVMe namespace (mirrors struct nvme_ns)."""
    ns_id: int
    capacity: int = 0
    used: int = 0
    block_size: int = NVME_BLOCK_SIZE
    sector_count: int = 0
    enabled: bool = True
    readonly: bool = False
    write_protected: bool = False
    format_progress: int = 0

    def __post_init__(self) -> None:
        self.sector_count = self.capacity // self.block_size if self.capacity else 0

    def read_lba(self, lba: int, count: int = 1) -> bytes:
        """Simulate reading LBA sectors."""
        if lba < 0 or lba + count > self.sector_count:
            return b'\x00' * (count * self.block_size)
        return b'\x00' * (count * self.block_size)

    def write_lba(self, lba: int, data: bytes) -> int:
        """Simulate writing LBA sectors."""
        if self.readonly or self.write_protected:
            return NVME_ERROR
        if lba < 0 or lba + (len(data) + self.block_size - 1) // self.block_size > self.sector_count:
            return NVME_ERROR
        return NVME_SUCCESS

    def get_info(self) -> Dict[str, Any]:
        return {
            "ns_id": self.ns_id,
            "capacity": self.capacity,
            "used": self.used,
            "block_size": self.block_size,
            "sectors": self.sector_count,
            "enabled": self.enabled,
        }


# ============================================================================
# NVMe I/O Queue
# ============================================================================

@dataclass
class NVMeIOQueue:
    """NVMe I/O queue (mirrors struct nvme_queue)."""
    queue_id: int
    depth: int = 1024
    cq_head: int = 0
    sq_tail: int = 0
    phase: int = 1
    cmd_count: int = 0
    commands: List[NVMeCommand] = field(default_factory=list)
    completions: List[NVMeCompletion] = field(default_factory=list)

    def submit_command(self, cmd: NVMeCommand) -> int:
        if len(self.commands) >= self.depth:
            return NVME_ERROR
        cmd.command_id = self.cmd_count
        self.cmd_count += 1
        self.commands.append(cmd)
        self.sq_tail = (self.sq_tail + 1) % self.depth
        return NVME_SUCCESS

    def complete_command(self) -> Optional[NVMeCompletion]:
        if self.cq_head >= len(self.commands):
            return None
        comp = NVMeCompletion(
            command_id=self.commands[self.cq_head].command_id,
            status=NVMEStatus.SUCCESS,
            phase=self.phase,
        )
        self.completions.append(comp)
        self.cq_head = (self.cq_head + 1) % self.depth
        if self.cq_head == 0:
            self.phase ^= 1
        return comp

    def flush(self) -> int:
        self.commands.clear()
        self.completions.clear()
        self.cq_head = 0
        self.sq_tail = 0
        self.cmd_count = 0
        return NVME_SUCCESS

    def get_info(self) -> Dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "depth": self.depth,
            "sq_tail": self.sq_tail,
            "cq_head": self.cq_head,
            "phase": self.phase,
            "commands": len(self.commands),
        }


# ============================================================================
# NVMe Controller
# ============================================================================

@dataclass
class NVMeController:
    """NVMe controller (mirrors struct nvme_ctrl)."""
    name: str
    index: int
    state: NVMEState = NVMEState.DISABLED
    pci_bus: int = 0
    pci_device: int = 0
    pci_function: int = 0
    namespaces: Dict[int, NVMeNamespace] = field(default_factory=dict)
    io_queues: Dict[int, NVMeIOQueue] = field(default_factory=dict)
    admin_queue: Optional[NVMeIOQueue] = None
    max_queue_depth: int = 1024
    max_namespaces: int = 64
    max_transfer_size: int = NVME_PAGE_SIZE * 256
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.admin_queue = NVMeIOQueue(queue_id=0, depth=64)

    def enable(self) -> int:
        self.state = NVMEState.ENABLED
        self._notify("enabled")
        return NVME_SUCCESS

    def disable(self) -> int:
        self.state = NVMEState.DISABLED
        self._notify("disabled")
        return NVME_SUCCESS

    def reset(self) -> int:
        for q in self.io_queues.values():
            q.flush()
        if self.admin_queue:
            self.admin_queue.flush()
        self.state = NVMEState.ENABLED
        return NVME_SUCCESS

    def add_namespace(self, ns: NVMeNamespace) -> int:
        if len(self.namespaces) >= self.max_namespaces:
            return NVME_ERROR
        self.namespaces[ns.ns_id] = ns
        return NVME_SUCCESS

    def remove_namespace(self, ns_id: int) -> int:
        self.namespaces.pop(ns_id, None)
        return NVME_SUCCESS

    def get_namespace(self, ns_id: int) -> Optional[NVMeNamespace]:
        return self.namespaces.get(ns_id)

    def create_io_queue(self, queue_id: int) -> int:
        if len(self.io_queues) >= NVME_MAX_IO_QUEUES:
            return NVME_ERROR
        self.io_queues[queue_id] = NVMeIOQueue(queue_id=queue_id, depth=self.max_queue_depth)
        return NVME_SUCCESS

    def delete_io_queue(self, queue_id: int) -> int:
        self.io_queues.pop(queue_id, None)
        return NVME_SUCCESS

    def submit_admin_command(self, cmd: NVMeCommand) -> int:
        return self.admin_queue.submit_command(cmd) if self.admin_queue else NVME_ERROR

    def submit_io_command(self, queue_id: int, cmd: NVMeCommand) -> int:
        queue = self.io_queues.get(queue_id)
        return queue.submit_command(cmd) if queue else NVME_ERROR

    def read(self, ns_id: int, lba: int, count: int = 1) -> Optional[bytes]:
        ns = self.namespaces.get(ns_id)
        return ns.read_lba(lba, count) if ns else None

    def write(self, ns_id: int, lba: int, data: bytes) -> int:
        ns = self.namespaces.get(ns_id)
        return ns.write_lba(lba, data) if ns else NVME_ERROR

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
            "namespaces": len(self.namespaces),
            "io_queues": len(self.io_queues),
            "max_queue_depth": self.max_queue_depth,
        }


# ============================================================================
# NVMe Subsystem
# ============================================================================

class NVMeSubsystem:
    """Central NVMe subsystem managing controllers."""

    def __init__(self) -> None:
        self._controllers: Dict[str, NVMeController] = {}
        self._next_index: int = 0

    def register_controller(self, ctrl: NVMeController) -> int:
        ctrl.index = self._next_index
        ctrl.registered = True
        self._controllers[ctrl.name] = ctrl
        self._next_index += 1
        return NVME_SUCCESS

    def unregister_controller(self, name: str) -> int:
        self._controllers.pop(name, None)
        return NVME_SUCCESS

    def get_controller(self, name: str) -> Optional[NVMeController]:
        return self._controllers.get(name)

    def enumerate_controllers(self) -> List[NVMeController]:
        return list(self._controllers.values())

    def get_topology(self) -> Dict[str, Any]:
        return {
            "controllers": len(self._controllers),
            "namespaces": sum(len(c.namespaces) for c in self._controllers.values()),
        }


# ============================================================================
# Global NVMe Instance
# ============================================================================

_global_nvme: Optional[NVMeSubsystem] = None


def get_global_nvme() -> NVMeSubsystem:
    global _global_nvme
    if _global_nvme is None:
        _global_nvme = NVMeSubsystem()
    return _global_nvme


def register_nvme_controller(ctrl: NVMeController) -> int:
    return get_global_nvme().register_controller(ctrl)


def nvme_read(controller: str, ns_id: int, lba: int, count: int = 1) -> Optional[bytes]:
    ctrl = get_global_nvme().get_controller(controller)
    return ctrl.read(ns_id, lba, count) if ctrl else None
