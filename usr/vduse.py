"""
UmerOS vduse Module
====================
Kernel VDUSE (vDPA Device in Userspace) subsystem.

Reference: docs.kernel.org/driver-api/vduse.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import threading


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOENT: int = 2
ENOMEM: int = 12
EBUSY: int = 16
ENODEV: int = 19
EOPNOTSUPP: int = 95
ENOSPC: int = 28

VIRTIO_ID_NETWORK: int = 1
VIRTIO_ID_BLOCK: int = 2
VIRTIO_ID_CONSOLE: int = 3
VIRTIO_ID_SCSI: int = 8
VIRTIO_ID_9P: int = 9
VIRTIO_ID_VSOCK: int = 19

VIRTIO_CONFIG_S_ACKNOWLEDGE: int = 0x01
VIRTIO_CONFIG_S_DRIVER: int = 0x02
VIRTIO_CONFIG_S_DRIVER_OK: int = 0x04
VIRTIO_CONFIG_S_FEATURES_OK: int = 0x08

VDUSE_CONFIG_BUF_SIZE: int = 256
VDUSE_QUEUE_SIZE_MAX: int = 1024
VDUSE_STRING_LEN_MAX: int = 256


# ============================================================================
# VDUSE Enums
# ============================================================================

class VDPADeviceType(IntEnum):
    """vDPA device types."""
    VDUSE_NET: int = VIRTIO_ID_NETWORK
    VDUSE_BLK: int = VIRTIO_ID_BLOCK
    VDUSE_CONSOLE: int = VIRTIO_ID_CONSOLE
    VDUSE_SCSI: int = VIRTIO_ID_SCSI
    VDUSE_9P: int = VIRTIO_ID_9P
    VDUSE_VSOCK: int = VIRTIO_ID_VSOCK


# Module-level aliases for enum values used as defaults
VDUSE_NET = VDPADeviceType.VDUSE_NET
VDUSE_BLK = VDPADeviceType.VDUSE_BLK
VDUSE_CONSOLE = VDPADeviceType.VDUSE_CONSOLE
VDUSE_SCSI = VDPADeviceType.VDUSE_SCSI
VDUSE_9P = VDPADeviceType.VDUSE_9P
VDUSE_VSOCK = VDPADeviceType.VDUSE_VSOCK


class VDPALinkStatus(IntEnum):
    """vDPA link status."""
    VDPA_ADMIN_CONFIG_NOT_READY: int = 0
    VDPA_ADMIN_CONFIG_READY: int = 1


class VDPADriverStatus(IntEnum):
    """vDPA driver status."""
    VDPA_REG_DRIVER: int = 0
    VDPA_UNREG_DRIVER: int = 1


class VDPAFeatureBits(IntEnum):
    """vDPA device feature bits."""
    VIRTIO_NET_F_CSUM: int = 0
    VIRTIO_NET_F_GUEST_CSUM: int = 1
    VIRTIO_NET_F_MAC: int = 5
    VIRTIO_NET_F_GSO: int = 6
    VIRTIO_NET_F_GUEST_TSO4: int = 7
    VIRTIO_NET_F_GUEST_TSO6: int = 8
    VIRTIO_NET_F_GUEST_ECN: int = 9
    VIRTIO_NET_F_GUEST_UFO: int = 10
    VIRTIO_NET_F_HOST_TSO4: int = 11
    VIRTIO_NET_F_HOST_TSO6: int = 12
    VIRTIO_NET_F_HOST_ECN: int = 13
    VIRTIO_NET_F_HOST_UFO: int = 14
    VIRTIO_NET_F_MRG_RXBUF: int = 15
    VIRTIO_F_NOTIFY_ON_EMPTY: int = 24
    VIRTIO_RING_F_INDIRECT_DESC: int = 28
    VIRTIO_RING_F_EVENT_IDX: int = 29


class VDUSEIOTYPE(IntEnum):
    """VHost data plane IOTYPE."""
    VDUSE_IOTYPE_CALL: int = 0
    VDUSE_IOTYPE_RETURN: int = 1


class VDUSEMsgType(IntEnum):
    """VHost data plane message types."""
    VDUSE_MSG_GET_FEATURES: int = 1
    VDUSE_MSG_SET_FEATURES: int = 2
    VDUSE_MSG_GET_STATUS: int = 3
    VDUSE_MSG_SET_STATUS: int = 4
    VDUSE_MSG_GET_CONFIG: int = 5
    VDUSE_MSG_SET_CONFIG: int = 6
    VDUSE_MSG_GET_VQ_NUM: int = 7
    VDUSE_MSG_GET_VQ_SIZE: int = 8
    VDUSE_MSG_SET_VQ_STATE: int = 9
    VDUSE_MSG_GET_VQ_STATE: int = 10
    VDUSE_MSG_SET_VQ_CALLFD: int = 11
    VDUSE_MSG_SET_VQ_READY: int = 12
    VDUSE_MSG_GET_VQ_READY: int = 13
    VDUSE_MSG_SET_CONFIG_CALLFD: int = 14
    VDUSE_MSG_RESET_DEVICE: int = 15


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class VQueueState:
    """Virtqueue state."""
    num: int = 256
    ready: bool = False
    call_fd: int = -1
    enable: bool = False
    vring_desc: Optional[Any] = None
    vring_avail: Optional[Any] = None
    vring_used: Optional[Any] = None
    last_used_idx: int = 0
    last_avail_idx: int = 0


@dataclass
class VDPADeviceConfig:
    """vDPA device configuration."""
    device_type: int = VDUSE_NET
    num_queues: int = 2
    vendor_id: int = 0
    device_id: int = 0
    feature_bits: int = 0
    config_space: bytes = b""

    def get_feature(self, bit: int) -> bool:
        """Check if a feature bit is set."""
        return bool(self.feature_bits & (1 << bit))

    def set_feature(self, bit: int, value: bool = True) -> None:
        """Set or clear a feature bit."""
        if value:
            self.feature_bits |= (1 << bit)
        else:
            self.feature_bits &= ~(1 << bit)


@dataclass
class VDPACallbacks:
    """vDPA device callbacks."""
    get_features: Optional[Callable[[], int]] = None
    set_features: Optional[Callable[[int], None]] = None
    get_status: Optional[Callable[[], int]] = None
    set_status: Optional[Callable[[int], None]] = None
    get_config: Optional[Callable[[int, int], bytes]] = None
    set_config: Optional[Callable[[int, bytes], None]] = None
    get_vq_num: Optional[Callable[[], int]] = None
    get_vq_size: Optional[Callable[[int], int]] = None
    set_vq_state: Optional[Callable[[int, int], None]] = None
    get_vq_state: Optional[Callable[[int], Optional[int]]] = None
    set_vq_callfd: Optional[Callable[[int, int], None]] = None
    set_vq_ready: Optional[Callable[[int, bool], None]] = None
    get_vq_ready: Optional[Callable[[int], bool]] = None
    reset_device: Optional[Callable[[], None]] = None


@dataclass
class VDUSEDevice:
    """VDUSE device instance."""
    name: str = ""
    device_type: int = VDUSE_NET
    config: VDPADeviceConfig = field(default_factory=VDPADeviceConfig)
    callbacks: VDPACallbacks = field(default_factory=VDPACallbacks)
    status: int = 0
    features: int = 0
    queues: List[VQueueState] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    started: bool = False

    def init_queues(self, num_queues: int, queue_size: int = 256) -> None:
        """Initialize virtqueues."""
        with self.lock:
            self.queues = []
            for _ in range(num_queues):
                self.queues.append(VQueueState(num=queue_size))

    def start(self) -> int:
        """Start the device."""
        with self.lock:
            if self.started:
                return EBUSY
            self.started = True
            self.status |= VIRTIO_CONFIG_S_ACKNOWLEDGE | VIRTIO_CONFIG_S_DRIVER | VIRTIO_CONFIG_S_DRIVER_OK
            return SUCCESS

    def stop(self) -> int:
        """Stop the device."""
        with self.lock:
            if not self.started:
                return EBUSY
            self.started = False
            self.status = 0
            return SUCCESS

    def get_feature(self, bit: int) -> bool:
        """Check if a feature is negotiated."""
        return bool(self.features & (1 << bit))

    def negotiate_features(self, device_features: int, driver_features: int) -> int:
        """Negotiate features."""
        with self.lock:
            self.features = device_features & driver_features
            return self.features


@dataclass
class VDUSEMsg:
    """VHost data plane message."""
    request: int = 0
    size: int = 0
    data: bytes = b""
    fd: int = -1

    def __init__(self, request: int = 0, size: int = 0, data: bytes = b"",
                 fd: int = -1) -> None:
        self.request = request
        self.size = size
        self.data = data
        self.fd = fd


@dataclass
class VDUSEIOMMU:
    """VHost IOMMU."""
    iommu_domain: int = 0
    mr_list: List['VHostMemoryRegion'] = field(default_factory=list)

    def map_range(self, guest_addr: int, size: int, userspace_addr: int,
                  flags: int = 0) -> Optional['VHostMemoryRegion']:
        """Map a memory region."""
        region = VHostMemoryRegion(
            guest_phys_addr=guest_addr,
            memory_size=size,
            userspace_addr=userspace_addr,
            flags=flags
        )
        self.mr_list.append(region)
        return region

    def unmap_range(self, guest_addr: int) -> bool:
        """Unmap a memory region."""
        for i, mr in enumerate(self.mr_list):
            if mr.guest_phys_addr == guest_addr:
                del self.mr_list[i]
                return True
        return False


@dataclass
class VHostMemoryRegion:
    """vHost memory region."""
    guest_phys_addr: int = 0
    memory_size: int = 0
    userspace_addr: int = 0
    flags: int = 0
    log_addr: int = 0

    def contains(self, addr: int, size: int = 1) -> bool:
        """Check if an address is within this region."""
        return (self.guest_phys_addr <= addr <
                self.guest_phys_addr + self.memory_size)


# ============================================================================
# VDUSE Subsystem
# ============================================================================

class VDUSE:
    """ VDUSE Subsystem."""
    def __init__(self) -> None:
        self.devices: Dict[str, VDUSEDevice] = {}
        self.iommus: Dict[str, VDUSEIOMMU] = {}
        self.lock: threading.Lock = threading.Lock()

    def create_device(self, name: str, device_type: int = VDUSE_NET,
                      num_queues: int = 2, queue_size: int = 256) -> VDUSEDevice:
        """Create a VDUSE device."""
        with self.lock:
            if name in self.devices:
                raise ValueError(f"Device {name} already exists")

            config = VDPADeviceConfig(
                device_type=device_type,
                num_queues=num_queues
            )
            device = VDUSEDevice(name=name, device_type=device_type, config=config)
            device.init_queues(num_queues, queue_size)
            self.devices[name] = device
            self.iommus[name] = VDUSEIOMMU()
        return device

    def destroy_device(self, name: str) -> int:
        """Destroy a VDUSE device."""
        with self.lock:
            device = self.devices.pop(name, None)
            if device:
                device.stop()
                self.iommus.pop(name, None)
                return SUCCESS
        return ENOENT

    def get_device(self, name: str) -> Optional[VDUSEDevice]:
        """Get a VDUSE device."""
        return self.devices.get(name)

    def set_device_features(self, name: str, features: int) -> int:
        """Set device features."""
        device = self.devices.get(name)
        if device:
            device.features = features
            return SUCCESS
        return ENOENT

    def get_device_features(self, name: str) -> Optional[int]:
        """Get device features."""
        device = self.devices.get(name)
        if device:
            return device.features
        return None

    def set_device_status(self, name: str, status: int) -> int:
        """Set device status."""
        device = self.devices.get(name)
        if device:
            device.status = status
            return SUCCESS
        return ENOENT

    def get_device_status(self, name: str) -> Optional[int]:
        """Get device status."""
        device = self.devices.get(name)
        if device:
            return device.status
        return None

    def set_vq_state(self, name: str, vq_index: int, state: int) -> int:
        """Set virtqueue state."""
        device = self.devices.get(name)
        if not device:
            return ENOENT
        if vq_index >= len(device.queues):
            return EINVAL
        device.queues[vq_index].last_used_idx = state
        return SUCCESS

    def get_vq_state(self, name: str, vq_index: int) -> Optional[int]:
        """Get virtqueue state."""
        device = self.devices.get(name)
        if not device:
            return None
        if vq_index >= len(device.queues):
            return None
        return device.queues[vq_index].last_used_idx

    def set_vq_ready(self, name: str, vq_index: int, ready: bool) -> int:
        """Set virtqueue ready state."""
        device = self.devices.get(name)
        if not device:
            return ENOENT
        if vq_index >= len(device.queues):
            return EINVAL
        device.queues[vq_index].ready = ready
        device.queues[vq_index].enable = ready
        return SUCCESS

    def get_vq_ready(self, name: str, vq_index: int) -> Optional[bool]:
        """Get virtqueue ready state."""
        device = self.devices.get(name)
        if not device:
            return None
        if vq_index >= len(device.queues):
            return None
        return device.queues[vq_index].ready

    def map_iommu(self, name: str, guest_addr: int, size: int,
                  userspace_addr: int, flags: int = 0) -> int:
        """Map a memory region in the IOMMU."""
        iommu = self.iommus.get(name)
        if iommu:
            region = iommu.map_range(guest_addr, size, userspace_addr, flags)
            return SUCCESS if region else ERROR
        return ENOENT

    def unmap_iommu(self, name: str, guest_addr: int) -> int:
        """Unmap a memory region from the IOMMU."""
        iommu = self.iommus.get(name)
        if iommu:
            return SUCCESS if iommu.unmap_range(guest_addr) else ERROR
        return ENOENT

    def get_device_config(self, name: str, offset: int, size: int) -> Optional[bytes]:
        """Read device config space."""
        device = self.devices.get(name)
        if not device:
            return None
        if offset + size > len(device.config.config_space):
            return None
        return device.config.config_space[offset:offset + size]

    def set_device_config(self, name: str, offset: int, data: bytes) -> int:
        """Write device config space."""
        device = self.devices.get(name)
        if not device:
            return ENOENT
        cs = bytearray(device.config.config_space)
        end = offset + len(data)
        if end > len(cs):
            cs.extend(b'\x00' * (end - len(cs)))
        cs[offset:end] = data
        device.config.config_space = bytes(cs)
        return SUCCESS

    def reset_device(self, name: str) -> int:
        """Reset a VDUSE device."""
        device = self.devices.get(name)
        if device:
            return device.stop()
        return ENOENT

    def list_devices(self) -> List[str]:
        """List all VDUSE device names."""
        return list(self.devices.keys())

    def get_stats(self) -> Dict[str, int]:
        """Get VDUSE statistics."""
        return {
            "devices": len(self.devices),
            "iommus": len(self.iommus),
        }


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_vduse: Optional[VDUSE] = None


def get_global_vduse() -> VDUSE:
    """Get global VDUSE instance."""
    global _global_vduse
    if _global_vduse is None:
        _global_vduse = VDUSE()
    return _global_vduse
