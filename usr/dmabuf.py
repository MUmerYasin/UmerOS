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
UmerOS DMA-BUF Module
======================
kernel DMA buffer sharing interface.
Implements DMA-BUF allocation, export, import, and sync.

Reference: docs.kernel.org/userspace-api/dma-buf.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple
import threading


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOMEM: int = 12
EBADF: int = 9
EOPNOTSUPP: int = 95


class DMABufFlags(IntEnum):
    """DMA-BUF flags."""
    O_CLOEXEC: int = 0o2000000
    O_NONBLOCK: int = 0o4000
    O_RDWR: int = 2
    O_RDONLY: int = 0
    O_WRONLY: int = 1


class DMABufOps(IntEnum):
    """DMA-BUF operation types."""
    DMA_BUF_OP_EXPORT: int = 0
    DMA_BUF_OP_IMPORT: int = 1
    DMA_BUF_OP_SYNC: int = 2
    DMA_BUF_OP_ATTACH: int = 3
    DMA_BUF_OP_DETACH: int = 4
    DMA_BUF_OP_BEGIN_CPU_ACCESS: int = 5
    DMA_BUF_OP_END_CPU_ACCESS: int = 6
    DMA_BUF_OP_MAP_DMA_BUF: int = 7
    DMA_BUF_OP_UNMAP_DMA_BUF: int = 8
    DMA_BUF_OP_RELEASE: int = 9
    DMA_BUF_OP_PIN: int = 10
    DMA_BUF_OP_UNPIN: int = 11
    DMA_BUF_OP_IOCTL: int = 12


class DMABufSyncFlags(IntEnum):
    """DMA-BUF sync flags."""
    DMA_BUF_SYNC_START: int = 0
    DMA_BUF_SYNC_END: int = 1
    DMA_BUF_SYNC_READ: int = 1 << 0
    DMA_BUF_SYNC_WRITE: int = 1 << 1
    DMA_BUF_SYNC_RW: int = 3


class DMAAttachDirection(IntEnum):
    """DMA attach direction."""
    DMA_BIDIRECTIONAL: int = 0
    DMA_TO_DEVICE: int = 1
    DMA_FROM_DEVICE: int = 2
    DMA_NONE: int = 3


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class DMABufAttachment:
    """DMA-BUF attachment to a device."""
    attachment_id: int = 0
    device_id: str = ""
    direction: DMAAttachDirection = DMAAttachDirection.DMA_BIDIRECTIONAL
    sg_table: List[int] = field(default_factory=list)
    attached: bool = False
    pinned: bool = False

    def attach(self, device_id: str, direction: DMAAttachDirection) -> int:
        """Attach buffer to a device."""
        self.device_id = device_id
        self.direction = direction
        self.attached = True
        self.sg_table = [0x1000, 0x2000, 0x3000]
        return SUCCESS

    def detach(self) -> int:
        """Detach buffer from device."""
        self.attached = False
        self.pinned = False
        self.sg_table = []
        return SUCCESS

    def pin(self) -> int:
        """Pin the attachment."""
        if not self.attached:
            return ERROR
        self.pinned = True
        return SUCCESS

    def unpin(self) -> int:
        """Unpin the attachment."""
        self.pinned = False
        return SUCCESS


@dataclass
class DMABuf:
    """DMA buffer descriptor."""
    buf_id: int = 0
    size: int = 0
    fd: int = -1
    exp_device: str = ""
    flags: DMABufFlags = DMABufFlags.O_RDWR
    exported: bool = False
    mmap_addr: int = 0
    ref_count: int = 1
    lock: threading.Lock = field(default_factory=threading.Lock)
    attachments: List[DMABufAttachment] = field(default_factory=list)
    ops: DMABufOps = DMABufOps.DMA_BUF_OP_EXPORT

    def export_buf(self, device_id: str, size: int) -> int:
        """Export a DMA buffer."""
        with self.lock:
            self.size = size
            self.exp_device = device_id
            self.exported = True
            self.ref_count = 1
            self.fd = 1024 + self.buf_id
        return SUCCESS

    def import_buf(self, fd: int) -> int:
        """Import a DMA buffer from fd."""
        with self.lock:
            self.fd = fd
            self.ref_count += 1
        return SUCCESS

    def attach(self, device_id: str, direction: DMAAttachDirection = DMAAttachDirection.DMA_BIDIRECTIONAL) -> DMABufAttachment:
        """Attach to a device."""
        att = DMABufAttachment(attachment_id=len(self.attachments), device_id=device_id, direction=direction)
        att.attach(device_id, direction)
        with self.lock:
            self.attachments.append(att)
        return att

    def detach(self, device_id: str) -> int:
        """Detach from a device."""
        with self.lock:
            for att in self.attachments:
                if att.device_id == device_id and att.attached:
                    return att.detach()
        return ERROR

    def sync(self, start: int, end: int, flags: DMABufSyncFlags) -> int:
        """Sync buffer for CPU access."""
        if not self.exported:
            return ERROR
        return SUCCESS

    def release(self) -> int:
        """Release the DMA buffer."""
        with self.lock:
            self.ref_count -= 1
            if self.ref_count == 0:
                self.exported = False
                self.mmap_addr = 0
                for att in self.attachments:
                    att.detach()
                self.attachments = []
        return SUCCESS


# ============================================================================
# DMA-BUF Heap
# ============================================================================

@dataclass
class DMABufHeap:
    """DMA-BUF heap for allocation."""
    heap_name: str = ""
    heap_type: str = ""
    total_size: int = 0
    allocated_size: int = 0
    buffers: List[DMABuf] = field(default_factory=list)

    def allocate(self, size: int, flags: int = 0) -> DMABuf:
        """Allocate a DMA buffer from this heap."""
        buf = DMABuf(buf_id=len(self.buffers), size=size, exp_device=self.heap_name)
        self.buffers.append(buf)
        self.allocated_size += size
        return buf

    def stats(self) -> Dict[str, int]:
        """Get heap statistics."""
        return {"total_size": self.total_size, "allocated_size": self.allocated_size, "buffer_count": len(self.buffers)}


# ============================================================================
# DMA-BUF Sync
# ============================================================================

class DMABufSync:
    """DMA-BUF CPU access synchronization."""
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def begin_cpu_access(self, buf: DMABuf) -> int:
        """Begin CPU access to buffer."""
        buf.sync(0, buf.size, DMABufSyncFlags.DMA_BUF_SYNC_READ | DMABufSyncFlags.DMA_BUF_SYNC_WRITE)
        return SUCCESS

    def end_cpu_access(self, buf: DMABuf) -> int:
        """End CPU access to buffer."""
        buf.sync(0, buf.size, DMABufSyncFlags.DMA_BUF_SYNC_END)
        return SUCCESS


# ============================================================================
# DMA-BUF Subsystem Manager
# ============================================================================

class DMABufManager:
    """DMA-BUF subsystem manager."""
    _instance: Optional[DMABufManager] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    heaps: Dict[str, DMABufHeap] = field(default_factory=dict)
    buffers: Dict[int, DMABuf] = field(default_factory=dict)
    sync: DMABufSync = field(default_factory=DMABufSync)
    next_buf_id: int = 0
    next_heap_id: int = 0

    def __new__(cls) -> DMABufManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def create_heap(self, name: str, heap_type: str = "system", total_size: int = 1024 * 1024 * 1024) -> DMABufHeap:
        """Create a DMA-BUF heap."""
        heap = DMABufHeap(heap_name=name, heap_type=heap_type, total_size=total_size)
        self.heaps[name] = heap
        return heap

    def allocate_buffer(self, heap_name: str, size: int, flags: int = 0) -> Optional[DMABuf]:
        """Allocate a buffer from a heap."""
        heap = self.heaps.get(heap_name)
        if not heap:
            return None
        buf = heap.allocate(size, flags)
        buf.buf_id = self.next_buf_id
        self.next_buf_id += 1
        self.buffers[buf.buf_id] = buf
        return buf

    def export_buffer(self, buf: DMABuf, device_id: str) -> int:
        """Export a buffer."""
        return buf.export_buf(device_id, buf.size)

    def import_buffer(self, fd: int) -> Optional[DMABuf]:
        """Import a buffer from fd."""
        for buf in self.buffers.values():
            if buf.fd == fd:
                buf.import_buf(fd)
                return buf
        return None

    def release_buffer(self, buf_id: int) -> int:
        """Release a buffer."""
        buf = self.buffers.get(buf_id)
        if buf:
            buf.release()
            if buf.ref_count == 0:
                del self.buffers[buf_id]
            return SUCCESS
        return ERROR

    def get_heap(self, name: str) -> Optional[DMABufHeap]:
        """Get a heap by name."""
        return self.heaps.get(name)

    def list_buffers(self) -> List[int]:
        """List all buffer IDs."""
        return list(self.buffers.keys())

    def list_heaps(self) -> List[str]:
        """List all heap names."""
        return list(self.heaps.keys())


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_dmabuf_manager: Optional[DMABufManager] = None


def get_global_dmabuf_manager() -> DMABufManager:
    """Get global DMA-BUF manager."""
    global _global_dmabuf_manager
    if _global_dmabuf_manager is None:
        _global_dmabuf_manager = DMABufManager()
    return _global_dmabuf_manager
