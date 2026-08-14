"""
UmerOS DMAEngine Subsystem
==========================
Kernel-like DMA Engine framework.
Implements DMA channels, descriptors, slave/memcpy/scatter-gather
transfers, and virtual channels.

Reference: Documentation/driver-api/dmaengine/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# DMAEngine Constants
# ============================================================================

DMA_SUCCESS: int = 0
DMA_IN_PROGRESS: int = 1
DMA_PAUSE: int = 2
DMA_ERROR: int = 3
DMA_COMPLETE: int = 4


class DMADirection(IntEnum):
    """DMA transfer direction (mirrors DMA_MEM_TO_MEM)."""
    MEM_TO_MEM = 0
    MEM_TO_DEV = 1
    DEV_TO_MEM = 2
    DEV_TO_DEV = 3
    PRIVATE = 4
    INLINE = 5


class DMAStatus(IntEnum):
    """DMA channel/transfer status."""
    IDLE = 0
    ACTIVE = 1
    PAUSED = 2
    ERROR = 3
    COMPLETE = 4


class DMAType(IntEnum):
    """DMA transfer type (mirrors DMA_TYPE_*)."""
    MEMCPY = 0
    SLAVE = 1
    CYCLIC = 2
    INTERLEAVE = 3
    SG = 4
    DEVICE_TO_MEM = 5
    MEM_TO_DEVICE = 6


# ============================================================================
# DMA Scatter-Gather Entry
# ============================================================================

@dataclass
class ScatterGatherEntry:
    """Single scatter-gather entry (mirrors struct scatterlist)."""
    addr: int
    length: int
    offset: int = 0
    flags: int = 0


# ============================================================================
# DMA Descriptor
# ============================================================================

@dataclass
class DMADescriptor:
    """DMA transfer descriptor (mirrors struct dma_async_tx_descriptor).

    Each descriptor represents a single DMA transfer operation.
    """
    cookie: int = 0
    dma_dir: DMADirection = DMADirection.MEM_TO_MEM
    src_addr: int = 0
    dst_addr: int = 0
    src_sg: List[ScatterGatherEntry] = field(default_factory=list)
    dst_sg: List[ScatterGatherEntry] = field(default_factory=list)
    length: int = 0
    callback: Optional[Callable] = None
    callback_param: Any = None
    status: DMAStatus = DMAStatus.IDLE
    chan_id: int = 0
    flags: int = 0

    @property
    def result(self) -> int:
        if self.status == DMAStatus.COMPLETE:
            return DMA_SUCCESS
        elif self.status == DMAStatus.ERROR:
            return DMA_ERROR
        elif self.status == DMAStatus.ACTIVE:
            return DMA_IN_PROGRESS
        return DMA_SUCCESS


# ============================================================================
# DMA Channel
# ============================================================================

@dataclass
class DMAChannel:
    """Represents a DMA channel (mirrors struct dma_chan).

    A channel is a requestor for DMA services.  Drivers request
    channels by name or capability and submit descriptors to them.
    """
    id: int
    name: str
    device_id: str = ""
    cap_mask: int = 0
    max_burst: int = 0
    status: DMAStatus = DMAStatus.IDLE
    descriptors: List[DMADescriptor] = field(default_factory=list)
    _pending: List[DMADescriptor] = field(default_factory=list)
    _completed: List[DMADescriptor] = field(default_factory=list)
    _cookie_counter: int = 0

    def has_capability(self, cap: int) -> bool:
        return bool(self.cap_mask & (1 << cap))

    def submit(self, desc: DMADescriptor) -> int:
        """Submit a descriptor for DMA (mirrors dmaengine_submit)."""
        self._cookie_counter += 1
        desc.cookie = self._cookie_counter
        desc.chan_id = self.id
        desc.status = DMAStatus.ACTIVE
        self._pending.append(desc)
        return desc.cookie

    def issue_pending(self) -> int:
        """Issue pending descriptors (mirrors dma_async_issue_pending)."""
        self._pending, self.descriptors = self.descriptors, self._pending
        self._pending.clear()
        self.status = DMAStatus.ACTIVE
        return DMA_SUCCESS

    def pause(self) -> int:
        self.status = DMAStatus.PAUSED
        for d in self.descriptors:
            if d.status == DMAStatus.ACTIVE:
                d.status = DMAStatus.PAUSED
        return DMA_SUCCESS

    def resume(self) -> int:
        self.status = DMAStatus.ACTIVE
        for d in self.descriptors:
            if d.status == DMAStatus.PAUSED:
                d.status = DMAStatus.ACTIVE
        return DMA_SUCCESS

    def terminate_all(self) -> int:
        """Terminate all transfers on channel."""
        self.descriptors.clear()
        self._pending.clear()
        self.status = DMAStatus.IDLE
        return DMA_SUCCESS

    def poll_complete(self) -> List[DMADescriptor]:
        """Poll for completed descriptors."""
        completed = [d for d in self.descriptors if d.status in (DMAStatus.COMPLETE, DMAStatus.ERROR)]
        return completed

    def descriptor_complete(self, desc: DMADescriptor) -> None:
        desc.status = DMAStatus.COMPLETE
        if desc.callback:
            desc.callback(desc.callback_param)


# ============================================================================
# DMA Device (Controller)
# ============================================================================

@dataclass
class DMADevice:
    """DMA controller device (mirrors struct dma_device).

    Manages channels and capabilities of a hardware DMA controller.
    """
    name: str
    dev_id: int = 0
    channels: List[DMAChannel] = field(default_factory=list)
    max_channels: int = 128
    cap_mask: int = 0
    mem_align: int = 1
    max_seg_size: int = 0xFFFFFFFF
    max_burst: int = 255
    copy_align: int = 0
    src_addr_widths: int = 0xFF
    dst_addr_widths: int = 0xFF
    directions: int = 0x0F
    descriptor_reuse: bool = False
    has_realloc: bool = False

    def add_channel(self, channel: DMAChannel) -> None:
        if len(self.channels) < self.max_channels:
            self.channels.append(channel)

    def allocate_channel(self, name: str = "", cap: int = 0) -> Optional[DMAChannel]:
        """Allocate a DMA channel by name or capability."""
        for ch in self.channels:
            if ch.status == DMAStatus.IDLE:
                if name and ch.name == name:
                    return ch
                if cap and ch.has_capability(cap):
                    return ch
        return None

    def free_channel(self, channel: DMAChannel) -> None:
        channel.terminate_all()
        channel.status = DMAStatus.IDLE

    def device_control(self, chan: DMAChannel, cmd: int, arg: int = 0) -> int:
        """Device control operations (mirrors dma_device::device_control)."""
        return DMA_SUCCESS

    def device_terminate_all(self, chan: DMAChannel) -> int:
        return chan.terminate_all()


# ============================================================================
# DMA Virtual Channel
# ============================================================================

@dataclass
class DMAVirtualChannel(DMAChannel):
    """Virtual channel that multiplexes through a physical channel.

    Mirrors struct virt_dma_chan in the kernel.
    """
    physical_chan: Optional[DMAChannel] = None

    def submit(self, desc: DMADescriptor) -> int:
        cookie = super().submit(desc)
        if self.physical_chan:
            self.physical_chan.submit(desc)
        return cookie


# ============================================================================
# DMAEngine Subsystem Manager
# ============================================================================

class DMAEngineSubsystem:
    """Central DMA engine managing devices, channels, and transfers."""

    def __init__(self) -> None:
        self._devices: Dict[str, DMADevice] = {}
        self._allocated_channels: Dict[int, DMAChannel] = {}
        self._cookie: int = 0

    def register_device(self, device: DMADevice) -> int:
        self._devices[device.name] = device
        return DMA_SUCCESS

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return DMA_SUCCESS

    def get_device(self, name: str) -> Optional[DMADevice]:
        return self._devices.get(name)

    def request_channel(self, device_name: str, name: str = "",
                        cap: int = 0) -> Optional[DMAChannel]:
        """Request a channel from a device."""
        device = self._devices.get(device_name)
        if not device:
            return None
        ch = device.allocate_channel(name=name, cap=cap)
        if ch:
            self._allocated_channels[ch.id] = ch
        return ch

    def release_channel(self, channel: DMAChannel) -> int:
        device = self._devices.get(channel.device_id)
        if device:
            device.free_channel(channel)
        self._allocated_channels.pop(channel.id, None)
        return DMA_SUCCESS

    def prepare_memcpy(self, chan: DMAChannel, src: int, dst: int,
                       length: int, callback: Optional[Callable] = None,
                       param: Any = None) -> DMADescriptor:
        """Prepare a memcpy DMA transfer."""
        desc = DMADescriptor(
            dma_dir=DMADirection.MEM_TO_MEM,
            src_addr=src,
            dst_addr=dst,
            length=length,
            callback=callback,
            callback_param=param,
        )
        return desc

    def prepare_slave_sg(self, chan: DMAChannel,
                         sg: List[ScatterGatherEntry],
                         direction: DMADirection,
                         callback: Optional[Callable] = None,
                         param: Any = None) -> DMADescriptor:
        """Prepare a scatter-gather slave transfer."""
        desc = DMADescriptor(
            dma_dir=direction,
            dst_sg=sg if direction in (DMADirection.DEV_TO_MEM, DMADirection.DEV_TO_DEV) else [],
            src_sg=sg if direction in (DMADirection.MEM_TO_DEV, DMADirection.DEV_TO_DEV) else [],
            length=sum(e.length for e in sg),
            callback=callback,
            callback_param=param,
        )
        return desc

    def prepare_dma_memcpy_sg(self, chan: DMAChannel,
                               src_sg: List[ScatterGatherEntry],
                               dst_sg: List[ScatterGatherEntry],
                               callback: Optional[Callable] = None,
                               param: Any = None) -> DMADescriptor:
        """Prepare scatter-gather memcpy."""
        desc = DMADescriptor(
            dma_dir=DMADirection.MEM_TO_MEM,
            src_sg=src_sg,
            dst_sg=dst_sg,
            length=sum(e.length for e in src_sg),
            callback=callback,
            callback_param=param,
        )
        return desc


# ============================================================================
# Global DMAEngine Instance
# ============================================================================

_global_dma: Optional[DMAEngineSubsystem] = None


def get_global_dma() -> DMAEngineSubsystem:
    global _global_dma
    if _global_dma is None:
        _global_dma = DMAEngineSubsystem()
    return _global_dma


def register_dma_device(device: DMADevice) -> int:
    return get_global_dma().register_device(device)


def request_dma_channel(device_name: str, name: str = "", cap: int = 0) -> Optional[DMAChannel]:
    return get_global_dma().request_channel(device_name, name=name, cap=cap)
