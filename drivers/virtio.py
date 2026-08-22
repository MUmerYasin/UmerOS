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
UmerOS VirtIO Subsystem
========================
Kernel-like VirtIO subsystem for para-virtualized drivers.
Implements VirtIO devices, virtqueues, and guest-host communication.

Reference: drivers/virtio/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# VirtIO Constants
# ============================================================================

VIRTIO_SUCCESS: int = 0
VIRTIO_ERROR: int = 1
VIRTIO_NOT_FOUND: int = 2
VIRTIO_BUSY: int = 3

VIRTIO_MAX_DEVICES: int = 32
VIRTIO_MAX_VIRTQUEUES: int = 32
VIRTIO_MAX_FEATURES: int = 64
VIRTIO_QUEUE_SIZE: int = 128
VIRTIO_QUEUE_ALIGN: int = 4096


class VirtIODeviceType(IntEnum):
    """VirtIO device types (virtio_ids.h)."""
    NET: int = 1
    BLOCK: int = 2
    CONSOLE: int = 3
    RNG: int = 4
    BALLOON: int = 5
    INPUT: int = 6
    TIMER: int = 7
    GPIO: int = 18
    FS: int = 26
    GPU: int = 16
    I2C: int = 34
    PMEM: int = 27
    VIDEO_ENCODER: int = 20
    VIDEO_DECODER: int = 21
    CRYPTO: int = 22


class VirtIOStatus(IntEnum):
    """VirtIO device status bits."""
    RESET: int = 0
    ACKNOWLEDGE: int = 1
    DRIVER: int = 2
    FEATURES_OK: int = 8
    DRIVER_OK: int = 4
    FEATURES_FAILED: int = 128


class VirtqueueState(IntEnum):
    """Virtqueue state."""
    FREE: int = 0
    ACTIVE: int = 1
    STOPPED: int = 2


# ============================================================================
# VirtIO Buffer
# ============================================================================

@dataclass
class VirtIOBuffer:
    """VirtIO buffer (mirrors struct vring_desc)."""
    addr: int = 0
    length: int = 0
    flags: int = 0
    next: int = 0
    data: bytes = b''

    def set_data(self, data: bytes) -> None:
        self.data = data
        self.length = len(data)

    def get_data(self) -> bytes:
        return self.data


# ============================================================================
# Virtqueue
# ============================================================================

@dataclass
class Virtqueue:
    """Virtqueue (mirrors struct vring_virtqueue)."""
    index: int
    size: int = VIRTIO_QUEUE_SIZE
    state: VirtqueueState = VirtqueueState.FREE
    vring_desc: List[VirtIOBuffer] = field(default_factory=list)
    vring_avail: List[int] = field(default_factory=list)
    vring_used: List[VirtIOBuffer] = field(default_factory=list)
    avail_idx: int = 0
    used_idx: int = 0
    free_head: int = 0
    num_free: int = 0
    callback: Optional[Callable] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.vring_desc = [VirtIOBuffer() for _ in range(self.size)]
        self.num_free = self.size
        for i in range(self.size - 1):
            self.vring_desc[i].next = i + 1

    def alloc_buffer(self) -> Optional[VirtIOBuffer]:
        if self.num_free == 0:
            return None
        buf = self.vring_desc[self.free_head]
        self.free_head = buf.next
        self.num_free -= 1
        return buf

    def free_buffer(self, buf: VirtIOBuffer) -> None:
        buf.next = self.free_head
        self.free_head = buf.index if hasattr(buf, 'index') else 0
        self.num_free += 1

    def add_buf(self, buf: VirtIOBuffer) -> int:
        if self.num_free == 0:
            return VIRTIO_ERROR
        self.vring_avail.append(self.avail_idx)
        self.avail_idx = (self.avail_idx + 1) % self.size
        return VIRTIO_SUCCESS

    def get_buf(self) -> Optional[VirtIOBuffer]:
        if self.used_idx == self.used_idx:
            return None
        buf = self.vring_used[0] if self.vring_used else None
        if self.vring_used:
            self.vring_used.pop(0)
        self.used_idx = (self.used_idx + 1) % self.size
        return buf

    def kick(self) -> int:
        if self.callback:
            self.callback(self.index)
        return VIRTIO_SUCCESS

    def notify(self) -> None:
        if self.callback:
            self.callback(self.index)

    def get_info(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "size": self.size,
            "state": self.state.name,
            "free": self.num_free,
            "avail_idx": self.avail_idx,
            "used_idx": self.used_idx,
        }


# ============================================================================
# VirtIO Device
# ============================================================================

@dataclass
class VirtIODevice:
    """VirtIO device (mirrors struct virtio_device)."""
    name: str
    index: int
    device_type: VirtIODeviceType = VirtIODeviceType.NET
    status: VirtIOStatus = VirtIOStatus.RESET
    features: int = 0
    feature_bits: List[int] = field(default_factory=list)
    virtqueues: Dict[int, Virtqueue] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def reset(self) -> int:
        self.status = VirtIOStatus.RESET
        self._notify("reset")
        return VIRTIO_SUCCESS

    def acknowledge(self) -> int:
        self.status = VirtIOStatus.ACKNOWLEDGE
        return VIRTIO_SUCCESS

    def set_driver(self) -> int:
        self.status = VirtIOStatus.DRIVER
        return VIRTIO_SUCCESS

    def set_features_ok(self) -> int:
        self.status = VirtIOStatus.FEATURES_OK
        return VIRTIO_SUCCESS

    def set_driver_ok(self) -> int:
        self.status = VirtIOStatus.DRIVER_OK
        self._notify("driver_ok")
        return VIRTIO_SUCCESS

    def set_features_failed(self) -> int:
        self.status = VirtIOStatus.FEATURES_FAILED
        return VIRTIO_SUCCESS

    def get_status(self) -> int:
        return int(self.status)

    def has_feature(self, feature: int) -> bool:
        return (self.features & (1 << feature)) != 0

    def set_feature(self, feature: int) -> None:
        self.features |= (1 << feature)

    def clear_feature(self, feature: int) -> None:
        self.features &= ~(1 << feature)

    def negotiate_features(self, driver_features: int) -> int:
        self.features = driver_features & self.features
        self.feature_bits = [i for i in range(VIRTIO_MAX_FEATURES) if self.has_feature(i)]
        return VIRTIO_SUCCESS

    def add_virtqueue(self, vq: Virtqueue) -> int:
        if len(self.virtqueues) >= VIRTIO_MAX_VIRTQUEUES:
            return VIRTIO_ERROR
        self.virtqueues[vq.index] = vq
        return VIRTIO_SUCCESS

    def get_virtqueue(self, index: int) -> Optional[Virtqueue]:
        return self.virtqueues.get(index)

    def find_virtqueue(self) -> Optional[Virtqueue]:
        for vq in self.virtqueues.values():
            if vq.state == VirtqueueState.FREE:
                return vq
        return None

    def read_config(self, offset: int, size: int) -> bytes:
        if "read_config" in self._ops:
            return self._ops["read_config"](offset, size)
        return b'\x00' * size

    def write_config(self, offset: int, data: bytes) -> int:
        if "write_config" in self._ops:
            return self._ops["write_config"](offset, data)
        return VIRTIO_ERROR

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
            "type": self.device_type.name,
            "status": self.status.name,
            "features": hex(self.features),
            "virtqueues": len(self.virtqueues),
        }


# ============================================================================
# VirtIO Subsystem
# ============================================================================

class VirtIOSubsystem:
    """Central VirtIO subsystem managing devices."""

    def __init__(self) -> None:
        self._devices: Dict[str, VirtIODevice] = {}
        self._next_index: int = 0

    def register_device(self, device: VirtIODevice) -> int:
        device.index = self._next_index
        device.registered = True
        self._devices[device.name] = device
        self._next_index += 1
        return VIRTIO_SUCCESS

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return VIRTIO_SUCCESS

    def get_device(self, name: str) -> Optional[VirtIODevice]:
        return self._devices.get(name)

    def enumerate_devices(self) -> List[VirtIODevice]:
        return list(self._devices.values())

    def get_topology(self) -> Dict[str, Any]:
        return {
            "devices": len(self._devices),
            "device_names": list(self._devices.keys()),
        }


# ============================================================================
# Global VirtIO Instance
# ============================================================================

_global_virtio: Optional[VirtIOSubsystem] = None


def get_global_virtio() -> VirtIOSubsystem:
    global _global_virtio
    if _global_virtio is None:
        _global_virtio = VirtIOSubsystem()
    return _global_virtio


def register_virtio_device(device: VirtIODevice) -> int:
    return get_global_virtio().register_device(device)


def virtio_get_info(device_name: str) -> Optional[Dict[str, Any]]:
    dev = get_global_virtio().get_device(device_name)
    return dev.get_info() if dev else None
