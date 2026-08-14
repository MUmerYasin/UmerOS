"""
UmerOS ATA Subsystem
====================
Kernel-like ATA (Advanced Technology Attachment) subsystem.
Implements PATA/SATA host controller, disk device management,
command queue, and power management.

Reference: Documentation/driver-api/libata.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# ATA Constants
# ============================================================================

ATA_STATUS_BSY: int = 0x80
ATA_STATUS_DRDY: int = 0x40
ATA_STATUS_DF: int = 0x20
ATA_STATUS_DRQ: int = 0x08
ATA_STATUS_ERR: int = 0x01

ATA_DEV_MASTER: int = 0
ATA_DEV_SLAVE: int = 1

ATA_ID_WORDS: int = 256
ATA_MAX_DEVICES: int = 4
ATA_MAX_PORTS: int = 8
ATA_SECTOR_SIZE: int = 512
ATA_MAX_SECTORS: int = 256


class ATADevType(IntEnum):
    """ATA device type."""
    NONE: int = 0
    UNKNOWN: int = 1
    PATA: int = 2
    SATA: int = 3
    ATAPI: int = 4
    PMP: int = 5


class ATACommand(IntEnum):
    """ATA commands."""
    IDENTIFY_DEVICE: int = 0xEC
    IDENTIFY_PACKET: int = 0xA1
    READ_SECTORS: int = 0x20
    READ_SECTORS_EXT: int = 0x24
    WRITE_SECTORS: int = 0x30
    WRITE_SECTORS_EXT: int = 0x34
    STANDBY_IMMEDIATE: int = 0xE0
    SLEEP: int = 0xE6
    FLUSH_CACHE: int = 0xE7
    SET_FEATURES: int = 0xEF


# ============================================================================
# ATA Taskfile
# ============================================================================

@dataclass
class ATATaskfile:
    """ATA taskfile (command register set)."""
    command: int = 0
    feature: int = 0
    nsect: int = 0
    lbal: int = 0
    lbam: int = 0
    lbah: int = 0
    device: int = 0
    control: int = 0
    hob_nsect: int = 0
    hob_lbal: int = 0
    hob_lbam: int = 0
    hob_lbah: int = 0
    protocol: int = 0


# ============================================================================
# ATA Device Identity
# ============================================================================

@dataclass
class ATAIdentity:
    """ATA device identification data (from IDENTIFY DEVICE)."""
    words: List[int] = field(default_factory=lambda: [0] * ATA_ID_WORDS)

    @property
    def serial_number(self) -> str:
        raw = self.words[10:20]
        return ''.join(chr((w >> 8) & 0xFF) + chr(w & 0xFF) for w in raw).strip()

    @property
    def firmware_revision(self) -> str:
        raw = self.words[23:27]
        return ''.join(chr((w >> 8) & 0xFF) + chr(w & 0xFF) for w in raw).strip()

    @property
    def model_number(self) -> str:
        raw = self.words[27:47]
        return ''.join(chr((w >> 8) & 0xFF) + chr(w & 0xFF) for w in raw).strip()

    @property
    def sectors_48(self) -> int:
        return (self.words[100] << 32) | (self.words[101] << 16) | self.words[102] | self.words[103]

    @property
    def sectors_28(self) -> int:
        return (self.words[61] << 16) | self.words[60]

    @property
    def is_lba_supported(self) -> bool:
        return bool(self.words[49] & 0x0200)

    @property
    def is_48bit_supported(self) -> bool:
        return bool(self.words[83] & 0x0400)

    @property
    def media_type(self) -> str:
        return "HDD" if self.words[0] & 0x0080 == 0 else "ATAPI"

    @property
    def transfer_rate_mbit(self) -> int:
        return self.words[49] & 0xFFFF

    def capacity_bytes(self) -> int:
        if self.is_48bit_supported:
            return self.sectors_48 * ATA_SECTOR_SIZE
        return self.sectors_28 * ATA_SECTOR_SIZE


# ============================================================================
# ATA Port
# ============================================================================

@dataclass
class ATAPort:
    """ATA port (mirrors struct ata_port)."""
    name: str
    index: int
    port_no: int = 0
    ioaddr: int = 0x1F0
    ioaddr2: int = 0x3F6
    irq: int = 14
    status: int = ATA_STATUS_DRDY
    error: int = 0
    device: Optional[ATADevice] = None
    _cmd_queue: List[ATATaskfile] = field(default_factory=list, repr=False)

    def send_command(self, tf: ATATaskfile) -> int:
        self._cmd_queue.append(tf)
        self.status = ATA_STATUS_BSY
        return 0

    def poll_ready(self, timeout_ms: int = 30000) -> bool:
        self.status = ATA_STATUS_DRDY
        return True

    def read_sector(self, lba: int) -> bytes:
        return b'\x00' * ATA_SECTOR_SIZE

    def write_sector(self, lba: int, data: bytes) -> int:
        return 0

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ioaddr": self.ioaddr,
            "irq": self.irq,
            "status": self.status,
            "has_device": self.device is not None,
        }


# ============================================================================
# ATA Device
# ============================================================================

@dataclass
class ATADevice:
    """ATA device (mirrors struct ata_device)."""
    name: str
    index: int
    dev_no: int = 0
    dev_type: ATADevType = ATADevType.UNKNOWN
    port: Optional[ATAPort] = None
    identity: Optional[ATAIdentity] = None
    capacity: int = 0
    lba_mode: int = 48  # 28 or 48
    spindle_speed: int = 7200
    power_state: str = "active"
   SMART_data: Dict[str, Any] = field(default_factory=dict)

    def identify(self) -> int:
        if not self.port:
            return -1
        self.identity = ATAIdentity()
        if self.identity.is_48bit_supported:
            self.capacity = self.identity.sectors_48 * ATA_SECTOR_SIZE
        else:
            self.capacity = self.identity.sectors_28 * ATA_SECTOR_SIZE
        return 0

    def read(self, lba: int, count: int = 1) -> bytes:
        if not self.port:
            return b''
        result = b''
        for i in range(count):
            result += self.port.read_sector(lba + i)
        return result

    def write(self, lba: int, data: bytes) -> int:
        if not self.port:
            return -1
        sectors = len(data) // ATA_SECTOR_SIZE
        for i in range(sectors):
            chunk = data[i * ATA_SECTOR_SIZE:(i + 1) * ATA_SECTOR_SIZE]
            self.port.write_sector(lba + i, chunk)
        return 0

    def standby(self) -> int:
        self.power_state = "standby"
        return 0

    def sleep(self) -> int:
        self.power_state = "sleep"
        return 0

    def flush(self) -> int:
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.dev_type.name,
            "capacity": self.capacity,
            "lba_mode": self.lba_mode,
            "power_state": self.power_state,
            "spindle_speed": self.spindle_speed,
        }


# ============================================================================
# ATA Host
# ============================================================================

@dataclass
class ATAHost:
    """ATA host controller (mirrors struct ata_host)."""
    name: str
    index: int
    ports: List[ATAPort] = field(default_factory=list)
    n_ports: int = 1
    irq: int = 14
    mmio_base: int = 0
    registered: bool = False

    def setup_port(self, port_no: int, ioaddr: int, irq: int) -> ATAPort:
        port = ATAPort(name=f"{self.name}-port{port_no}", index=port_no, port_no=port_no, ioaddr=ioaddr, irq=irq)
        self.ports.append(port)
        return port

    def get_device(self, port_no: int, dev_no: int) -> Optional[ATADevice]:
        for port in self.ports:
            if port.port_no == port_no and port.device and port.device.dev_no == dev_no:
                return port.device
        return None

    def get_all_devices(self) -> List[ATADevice]:
        return [p.device for p in self.ports if p.device]

    def scan_ports(self) -> int:
        detected = 0
        for port in self.ports:
            dev = ATADevice(name=f"{self.name}-dev{port.port_no}", index=port.port_no, dev_no=0, port=port)
            port.device = dev
            detected += 1
        return detected


# ============================================================================
# ATA Subsystem Manager
# ============================================================================

class ATASubsystem:
    """Central ATA subsystem managing hosts and devices."""

    def __init__(self) -> None:
        self._hosts: Dict[str, ATAHost] = {}
        self._next_index: int = 0

    def register_host(self, host: ATAHost) -> int:
        host.index = self._next_index
        host.registered = True
        self._hosts[host.name] = host
        self._next_index += 1
        return 0

    def unregister_host(self, name: str) -> int:
        self._hosts.pop(name, None)
        return 0

    def get_host(self, name: str) -> Optional[ATAHost]:
        return self._hosts.get(name)

    def enumerate_hosts(self) -> List[ATAHost]:
        return list(self._hosts.values())

    def enumerate_devices(self) -> List[ATADevice]:
        devices = []
        for host in self._hosts.values():
            devices.extend(host.get_all_devices())
        return devices

    def get_all_devices(self) -> List[ATADevice]:
        return self.enumerate_devices()


# ============================================================================
# Global ATA Instance
# ============================================================================

_global_ata: Optional[ATASubsystem] = None


def get_global_ata() -> ATASubsystem:
    global _global_ata
    if _global_ata is None:
        _global_ata = ATASubsystem()
    return _global_ata


def register_ata_host(host: ATAHost) -> int:
    return get_global_ata().register_host(host)


def ata_get_all_devices() -> List[ATADevice]:
    return get_global_ata().enumerate_devices()
