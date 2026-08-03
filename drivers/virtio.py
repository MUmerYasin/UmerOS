"""
UmerOS Virtio Framework
========================
Linux kernel Virtio virtual I/O subsystem.
Implements virtio devices, drivers, virtqueues,
and transport layers (PCI, MMIO, channel I/O).
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Virtio Constants
# ---------------------------------------------------------------------------
VIRTIO_F_VERSION_1: int = 32
VIRTIO_F_IOMMU_PLATFORM: int = 33
VIRTIO_F_ORDER_PLATFORM: int = 34

# Device IDs
VIRTIO_ID_NET: int = 1
VIRTIO_ID_BLOCK: int = 2
VIRTIO_ID_CONSOLE: int = 3
VIRTIO_ID_RNG: int = 4
VIRTIO_ID_BALLOON: int = 5
VIRTIO_ID_SCSI: int = 8
VIRTIO_ID_9P: int = 16

# Status bits
VIRTIO_STATUS_ACKNOWLEDGE: int = 0x01
VIRTIO_STATUS_DRIVER: int = 0x02
VIRTIO_STATUS_DRIVER_OK: int = 0x04
VIRTIO_STATUS_FEATURES_OK: int = 0x08
VIRTIO_STATUS_DRIVER_FEATURES_OK: int = 0x10
VIRTIO_STATUS_FAILED: int = 0x80

# Queue constants
VIRTIO_QUEUE_SIZE: int = 256
VIRTIO_VRING_DESC_F_NEXT: int = 1
VIRTIO_VRING_DESC_F_WRITE: int = 2
VIRTIO_VRING_DESC_F_INDIRECT: int = 4

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_devices: Dict[str, VirtioDevice] = {}
_drivers: Dict[str, VirtioDriver] = {}
_virtqueues: Dict[str, Virtqueue] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class VirtioDevice:
    """Virtio virtual device"""
    name: str
    device_id: int
    device_name: str = ""
    vendor_id: int = 0x1AF4  # Red Hat
    device_version: int = 1
    status: int = 0
    features: int = 0
    driver_features: int = 0
    is_registered: bool = False
    transport: str = "pci"  # pci, mmio, ccw
    _queues: List[str] = field(default_factory=list)
    _config: Dict[int, bytes] = field(default_factory=dict)
    _isr: int = 0
    _ops: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class VirtioDriver:
    """Virtio device driver"""
    name: str
    device_id: int
    features_required: int = 0
    features_optional: int = 0
    is_registered: bool = False
    _probe: Optional[Callable] = None
    _remove: Optional[Callable] = None
    _config_changed: Optional[Callable] = None


@dataclass
class Virtqueue:
    """Virtio virtqueue"""
    name: str
    device_name: str
    index: int
    size: int = VIRTIO_QUEUE_SIZE
    is_enabled: bool = False
    is_running: bool = False
    _num_free: int = VIRTIO_QUEUE_SIZE
    _num_used: int = 0
    _callbacks: Dict[int, Callable] = field(default_factory=dict)
    _data: Dict[int, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def register_device(name: str, device_id: int, transport: str = "pci") -> VirtioDevice:
    """Register a virtio device"""
    if name in _devices:
        log.warning("Device %s already registered", name)
        return _devices[name]

    device_names = {
        VIRTIO_ID_NET: "network",
        VIRTIO_ID_BLOCK: "block",
        VIRTIO_ID_CONSOLE: "console",
        VIRTIO_ID_RNG: "random",
        VIRTIO_ID_BALLOON: "memory-balloon",
        VIRTIO_ID_SCSI: "scsi",
        VIRTIO_ID_9P: "9p",
    }

    device = VirtioDevice(
        name=name,
        device_id=device_id,
        device_name=device_names.get(device_id, "unknown"),
        transport=transport,
        is_registered=True,
    )
    device.status = VIRTIO_STATUS_ACKNOWLEDGE
    _devices[name] = device
    log.info("Registered virtio device: %s (id=%d, transport=%s)",
             name, device_id, transport)
    return device


def register_driver(name: str, device_id: int,
                    features_required: int = 0) -> VirtioDriver:
    """Register a virtio driver"""
    if name in _drivers:
        log.warning("Driver %s already registered", name)
        return _drivers[name]

    driver = VirtioDriver(
        name=name,
        device_id=device_id,
        features_required=features_required,
        is_registered=True,
    )
    _drivers[name] = driver
    log.info("Registered virtio driver: %s (id=%d)", name, device_id)
    return driver


def unregister_device(name: str) -> bool:
    """Unregister a virtio device"""
    if name not in _devices:
        log.warning("Device %s not found", name)
        return False
    del _devices[name]
    log.info("Unregistered virtio device: %s", name)
    return True


def unregister_driver(name: str) -> bool:
    """Unregister a virtio driver"""
    if name not in _drivers:
        log.warning("Driver %s not found", name)
        return False
    del _drivers[name]
    log.info("Unregistered virtio driver: %s", name)
    return True


def get_device(name: str) -> Optional[VirtioDevice]:
    """Get a registered virtio device"""
    return _devices.get(name)


def get_driver(name: str) -> Optional[VirtioDriver]:
    """Get a registered virtio driver"""
    return _drivers.get(name)


def list_devices() -> List[str]:
    """List all registered virtio devices"""
    return list(_devices.keys())


def list_drivers() -> List[str]:
    """List all registered virtio drivers"""
    return list(_drivers.keys())


# ---------------------------------------------------------------------------
# Virtqueue Operations
# ---------------------------------------------------------------------------
def create_virtqueue(device_name: str, queue_index: int,
                     queue_size: int = VIRTIO_QUEUE_SIZE) -> Virtqueue:
    """Create a virtqueue for a device"""
    vq_name = f"{device_name}.vq{queue_index}"

    if vq_name in _virtqueues:
        log.warning("Virtqueue %s already exists", vq_name)
        return _virtqueues[vq_name]

    vq = Virtqueue(
        name=vq_name,
        device_name=device_name,
        index=queue_index,
        size=queue_size,
        _num_free=queue_size,
    )
    _virtqueues[vq_name] = vq

    device = get_device(device_name)
    if device is not None:
        device._queues.append(vq_name)

    log.info("Created virtqueue: %s (size=%d)", vq_name, queue_size)
    return vq


def enable_virtqueue(vq_name: str) -> bool:
    """Enable a virtqueue"""
    vq = _virtqueues.get(vq_name)
    if vq is None:
        log.error("Virtqueue %s not found", vq_name)
        return False

    vq.is_enabled = True
    vq.is_running = True
    log.info("Enabled virtqueue: %s", vq_name)
    return True


def add_buf(vq_name: str, data: bytes, callback: Optional[Callable] = None) -> int:
    """Add a buffer to the virtqueue, returns descriptor index"""
    vq = _virtqueues.get(vq_name)
    if vq is None:
        log.error("Virtqueue %s not found", vq_name)
        return -1

    if vq._num_free == 0:
        log.warning("Virtqueue %s full", vq_name)
        return -1

    desc_idx = vq.size - vq._num_free
    vq._num_free -= 1
    vq._data[desc_idx] = data

    if callback is not None:
        vq._callbacks[desc_idx] = callback

    log.debug("Added buffer to %s: desc=%d, size=%d", vq_name, desc_idx, len(data))
    return desc_idx


def get_buf(vq_name: str) -> Optional[Tuple[int, bytes]]:
    """Get a used buffer from the virtqueue"""
    vq = _virtqueues.get(vq_name)
    if vq is None:
        return None

    if vq._num_used == 0:
        return None

    # Simulated used buffer
    vq._num_used -= 1
    return (0, b"\x00" * 64)


# ---------------------------------------------------------------------------
# Device Operations
# ---------------------------------------------------------------------------
def set_status(device_name: str, status: int) -> bool:
    """Set device status"""
    device = get_device(device_name)
    if device is None:
        return False

    device.status = status
    log.debug("Device %s status: 0x%02X", device_name, status)
    return True


def get_status(device_name: str) -> int:
    """Get device status"""
    device = get_device(device_name)
    if device is None:
        return 0
    return device.status


def negotiate_features(device_name: str, driver_features: int) -> bool:
    """Negotiate device/driver features"""
    device = get_device(device_name)
    if device is None:
        return False

    device.driver_features = driver_features & device.features
    device.status |= VIRTIO_STATUS_FEATURES_OK
    log.info("Device %s features negotiated: 0x%08X",
             device_name, device.driver_features)
    return True


def read_config(device_name: str, offset: int, size: int) -> bytes:
    """Read device configuration space"""
    device = get_device(device_name)
    if device is None:
        return b"\x00" * size

    data = b""
    for i in range(size):
        data += bytes([device._config.get(offset + i, 0)])
    return data


def write_config(device_name: str, offset: int, data: bytes) -> bool:
    """Write to device configuration space"""
    device = get_device(device_name)
    if device is None:
        return False

    for i, byte in enumerate(data):
        device._config[offset + i] = byte
    return True


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== UmerOS Virtio Framework Demo ===\n")

    # Register devices
    net_dev = register_device("eth0", VIRTIO_ID_NET)
    blk_dev = register_device("vda", VIRTIO_ID_BLOCK)
    rng_dev = register_device("rng0", VIRTIO_ID_RNG)

    # Register drivers
    register_driver("virtio_net", VIRTIO_ID_NET)
    register_driver("virtio_blk", VIRTIO_ID_BLOCK)
    register_driver("virtio_rng", VIRTIO_ID_RNG)

    print(f"Devices: {list_devices()}")
    print(f"Drivers: {list_drivers()}")

    # Create virtqueues
    vq = create_virtqueue("eth0", 0)
    enable_virtqueue(vq.name)

    # Negotiate features
    negotiate_features("eth0", 0xFFFFFFFF)

    # Add buffer
    desc = add_buf(vq.name, b"Hello Virtio!", callback=lambda d: print(f"  Callback: {d}"))
    print(f"\nAdded buffer: desc={desc}")
    print(f"Device eth0 status: 0x{get_status('eth0'):02X}")
