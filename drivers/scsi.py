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
UmerOS SCSI Subsystem
=====================
Kernel-like SCSI (Small Computer System Interface) subsystem.
Implements host adapter management, SCSI devices, command processing,
tagged queuing, and error recovery.

Reference: drivers/scsi/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# SCSI Constants
# ============================================================================

SCSI_SUCCESS: int = 0
SCSI_ERROR: int = 1
SCSI_TIMEOUT: int = 2
SCSI_BUSY: int = 3
SCSI_INVALID: int = 4
SCSI_MEDIUM_ERROR: int = 5
SCSI_CHECK_CONDITION: int = 6

SCSI_MAX_DEVICES: int = 256
SCSI_MAX_HOSTS: int = 32
SCSI_MAX_CMD_LEN: int = 16
SCSI_SENSE_LEN: int = 32
SCSI_TIMEOUT_MS: int = 30000
SCSI_DEFAULT_QUEUE_DEPTH: int = 32


class SCSIDeviceType(IntEnum):
    """SCSI device types."""
    DISK: int = 0x00
    TAPE: int = 0x01
    PRINTER: int = 0x02
    PROCESSOR: int = 0x03
    WRITE_ONCE: int = 0x04
    CDROM: int = 0x05
    SCANNER: int = 0x06
    OPTICAL: int = 0x07
    CHANGER: int = 0x08
    COMM: int = 0x09
    ENCLOSURE: int = 0x0D
    ZBC: int = 0x14
    UNKNOWN: int = 0x1F


class SCSIStatus(IntEnum):
    """SCSI status codes."""
    GOOD: int = 0x00
    CONDITION_MET: int = 0x04
    INTERMEDIATE: int = 0x08
    INTERMEDIATE_CONDITION_MET: int = 0x0C
    BUSY: int = 0x08
    RESERVATION_CONFLICT: int = 0x18
    TASK_SET_FULL: int = 0x28
    ACA_ACTIVE: int = 0x30
    CHECK_CONDITION: int = 0x02


class SCSI SenseKey(IntEnum):
    """SCSI sense keys."""
    NO_SENSE: int = 0x00
    RECOVERED_ERROR: int = 0x01
    NOT_READY: int = 0x02
    MEDIUM_ERROR: int = 0x03
    HARDWARE_ERROR: int = 0x04
    ILLEGAL_REQUEST: int = 0x05
    UNIT_ATTENTION: int = 0x06
    DATA_PROTECT: int = 0x07
    BLANK_CHECK: int = 0x08
    COPY_ABORTED: int = 0x0A
    ABORTED_COMMAND: int = 0x0B


# ============================================================================
# SCSI CDB (Command Descriptor Block)
# ============================================================================

@dataclass
class SCSICmd:
    """SCSI command descriptor block."""
    opcode: int = 0
    data: List[int] = field(default_factory=lambda: [0] * SCSI_MAX_CMD_LEN)
    data_len: int = 16
    data_in: bytes = b''
    data_out: bytes = b''
    transfer_len: int = 0
    timeout_ms: int = SCSI_TIMEOUT_MS
    tag: int = -1  # -1 = untagged

    @property
    def cdb_bytes(self) -> bytes:
        return bytes(self.data[:self.data_len])


# ============================================================================
# SCSI Sense Data
# ============================================================================

@dataclass
class SCSISense:
    """SCSI sense response."""
    response_code: int = 0x70
    sense_key: SCSI SenseKey = SCSI SenseKey.NO_SENSE
    asc: int = 0  # Additional Sense Code
    ascq: int = 0  # Additional Sense Code Qualifier
    additional_data: bytes = b''

    @property
    def is_valid(self) -> bool:
        return self.sense_key != SCSI SenseKey.NO_SENSE

    def set_check_condition(self, key: SCSI SenseKey, asc: int = 0, ascq: int = 0) -> None:
        self.response_code = 0x70
        self.sense_key = key
        self.asc = asc
        self.ascq = ascq


# ============================================================================
# SCSI Device
# ============================================================================

@dataclass
class SCSIDevice:
    """SCSI device (mirrors struct scsi_device)."""
    name: str
    index: int
    host_no: int = 0
    channel: int = 0
    id: int = 0
    lun: int = 0
    device_type: SCSIDeviceType = SCSIDeviceType.UNKNOWN
    vendor: str = ""
    model: str = ""
    rev: str = ""
    capacity: int = 0
    block_size: int = 512
    queue_depth: int = SCSI_DEFAULT_QUEUE_DEPTH
    tagged_support: bool = False
    removable: bool = False
    write_protected: bool = False
    state: str = "running"
    _cmd_queue: List[SCSICmd] = field(default_factory=list, repr=False)
    _sense: SCSISense = field(default_factory=SCSISense, repr=False)
    _stats: Dict[str, int] = field(default_factory=dict, repr=False)

    def send_command(self, cmd: SCSICmd) -> int:
        self._cmd_queue.append(cmd)
        self._stats["commands"] = self._stats.get("commands", 0) + 1
        if cmd.tag >= 0:
            self._stats["tagged_commands"] = self._stats.get("tagged_commands", 0) + 1
        return SCSI_SUCCESS

    def test_unit_ready(self) -> int:
        return SCSI_SUCCESS

    def read_capacity(self) -> Dict[str, int]:
        return {
            "block_size": self.block_size,
            "last_lba": (self.capacity // self.block_size) - 1 if self.capacity else 0,
        }

    def read(self, lba: int, count: int = 1) -> bytes:
        self._stats["reads"] = self._stats.get("reads", 0) + 1
        return b'\x00' * (count * self.block_size)

    def write(self, lba: int, data: bytes) -> int:
        self._stats["writes"] = self._stats.get("writes", 0) + 1
        return SCSI_SUCCESS

    def sync_cache(self) -> int:
        return SCSI_SUCCESS

    def start_stop(self, start: bool = True) -> int:
        self.state = "running" if start else "stopped"
        return SCSI_SUCCESS

    def inquiry(self) -> Dict[str, str]:
        return {
            "vendor": self.vendor,
            "model": self.model,
            "rev": self.rev,
            "type": self.device_type.name,
        }

    def get_sense(self) -> SCSISense:
        return self._sense

    def clear_sense(self) -> None:
        self._sense = SCSISense()

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)


# ============================================================================
# SCSI Host
# ============================================================================

@dataclass
class SCSIHost:
    """SCSI host adapter (mirrors struct Scsi_Host)."""
    name: str
    index: int
    host_no: int = 0
    max_channel: int = 0
    max_id: int = 16
    max_lun: int = 8
    cmd_per_lun: int = 1
    can_queue: int = 32
    sg_tablesize: int = 16
    max_sectors: int = 256
    irq: int = 0
    mmio_base: int = 0
    transport: str = ""
    devices: Dict[int, SCSIDevice] = field(default_factory=dict)
    registered: bool = False
    _stats: Dict[str, int] = field(default_factory=dict, repr=False)

    def add_device(self, dev: SCSIDevice) -> int:
        key = (dev.channel << 16) | (dev.id << 8) | dev.lun
        self.devices[key] = dev
        return 0

    def remove_device(self, channel: int, dev_id: int, lun: int) -> bool:
        key = (channel << 16) | (dev_id << 8) | lun
        return self.devices.pop(key, None) is not None

    def get_device(self, channel: int, dev_id: int, lun: int) -> Optional[SCSIDevice]:
        key = (channel << 16) | (dev_id << 8) | lun
        return self.devices.get(key)

    def scan_bus(self) -> List[SCSIDevice]:
        detected = []
        for dev_id in range(min(self.max_id, 8)):
            dev = SCSIDevice(
                name=f"scsi{self.host_no}:0:{dev_id}:0",
                index=dev_id,
                host_no=self.host_no,
                channel=0,
                id=dev_id,
                lun=0,
                device_type=SCSIDeviceType.DISK,
                vendor="UmerOS",
                model="VirtSCSI",
                rev="1.0",
            )
            self.add_device(dev)
            detected.append(dev)
        return detected

    def abort_command(self, cmd: SCSICmd) -> int:
        return SCSI_SUCCESS

    def device_reset(self, channel: int, dev_id: int, lun: int) -> int:
        return SCSI_SUCCESS

    def bus_reset(self) -> int:
        return SCSI_SUCCESS

    def host_reset(self) -> int:
        return SCSI_SUCCESS

    def get_all_devices(self) -> List[SCSIDevice]:
        return list(self.devices.values())

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "host_no": self.host_no,
            "transport": self.transport,
            "max_channel": self.max_channel,
            "max_id": self.max_id,
            "devices": len(self.devices),
        }


# ============================================================================
# SCSI Subsystem Manager
# ============================================================================

class SCSISubsystem:
    """Central SCSI subsystem managing hosts and devices."""

    def __init__(self) -> None:
        self._hosts: Dict[str, SCSIHost] = {}
        self._next_index: int = 0
        self._next_host_no: int = 0

    def register_host(self, host: SCSIHost) -> int:
        host.index = self._next_index
        host.host_no = self._next_host_no
        host.registered = True
        self._hosts[host.name] = host
        self._next_index += 1
        self._next_host_no += 1
        return 0

    def unregister_host(self, name: str) -> int:
        self._hosts.pop(name, None)
        return 0

    def get_host(self, name: str) -> Optional[SCSIHost]:
        return self._hosts.get(name)

    def enumerate_hosts(self) -> List[SCSIHost]:
        return list(self._hosts.values())

    def enumerate_devices(self) -> List[SCSIDevice]:
        devices = []
        for host in self._hosts.values():
            devices.extend(host.get_all_devices())
        return devices

    def get_device(self, host_name: str, channel: int, dev_id: int, lun: int) -> Optional[SCSIDevice]:
        host = self._hosts.get(host_name)
        return host.get_device(channel, dev_id, lun) if host else None


# ============================================================================
# Global SCSI Instance
# ============================================================================

_global_scsi: Optional[SCSISubsystem] = None


def get_global_scsi() -> SCSISubsystem:
    global _global_scsi
    if _global_scsi is None:
        _global_scsi = SCSISubsystem()
    return _global_scsi


def register_scsi_host(host: SCSIHost) -> int:
    return get_global_scsi().register_host(host)


def scsi_enumerate_devices() -> List[SCSIDevice]:
    return get_global_scsi().enumerate_devices()
