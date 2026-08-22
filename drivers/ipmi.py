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
UmerOS IPMI Subsystem
=====================
Kernel-like IPMI (Intelligent Platform Management Interface).
Implements BMC (Baseboard Management Controller) communication,
sensor reading, event logging, and SOL (Serial Over LAN).

Reference: drivers/char/ipmi/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# IPMI Constants
# ============================================================================

IPMI_MAX_NAME_LENGTH: int = 32
IPMI_INVALID_CHANNEL: int = 0xFF
IPMI BMC LUN: int = 0

# NetFn definitions
IPMI_NETFN_CHassis: int = 0x00
IPMI_NETFN_SENSOR_EVENT: int = 0x04
IPMI_NETFN_APP: int = 0x06
IPMI_NETFN_STORAGE: int = 0x0A
IPMI_NETFN_transport: int = 0x0C

# Command definitions
IPMI_GET_DEVICE_ID_CMD: int = 0x01
IPMI_COLD_RESET_CMD: int = 0x03
IPMI_GET_EVENT_RECEIVER_CMD: int = 0x01
IPMI_GET_SEL_INFO_CMD: int = 0x40
IPMI_GET_SENSOR_READING_CMD: int = 0x2D


class IPMICompletionCode(IntEnum):
    """IPMI completion codes."""
    SUCCESS: int = 0
    NODE_BUSY: int = 0xC0
    INVALID_COMMAND: int = 0xCC
    INVALID_LUN: int = 0xCD
    TIMEOUT: int = 0xC3
    NOT_FOUND: int = 0xCC
    INVALID_RESERVATION: int = 0xC5
    DESTINATION_UNAVAILABLE: int = 0xD3
    INSUFFICIENT_RESOURCES: int = 0xD1


class IPMISensorType(IntEnum):
    """IPMI sensor types."""
    TEMPERATURE: int = 0x01
    VOLTAGE: int = 0x02
    CURRENT: int = 0x03
    FAN: int = 0x04
    PHYSICAL_SECURITY: int = 0x05
    POWER_UNIT: int = 0x09
    PROCESSOR: int = 0x07
    MEMORY: int = 0x0C
    SYSTEM_EVENT: int = 0x12


# ============================================================================
# IPMI Message
# ============================================================================

@dataclass
class IPMIMessage:
    """IPMI message (mirrors struct ipmi_msg)."""
    netfn: int = 0
    lun: int = 0
    cmd: int = 0
    data: List[int] = field(default_factory=list)
    data_len: int = 0
    completion_code: int = 0
    response_data: List[int] = field(default_factory=list)


# ============================================================================
# IPMI Sensor
# ============================================================================

@dataclass
class IPMISensor:
    """IPMI sensor reading."""
    number: int
    name: str
    sensor_type: IPMISensorType = IPMISensorType.TEMPERATURE
    value: float = 0.0
    units: str = ""
    lower_critical: float = 0.0
    upper_critical: float = 100.0
    threshold_high: float = 85.0
    threshold_low: float = -10.0
    status: int = 0  # 0=ok, 1=warning, 2=critical

    def update_value(self, val: float) -> None:
        self.value = val
        if val < self.lower_critical or val > self.upper_critical:
            self.status = 2
        elif val < self.threshold_low or val > self.threshold_high:
            self.status = 1
        else:
            self.status = 0


# ============================================================================
# IPMI Event
# ============================================================================

@dataclass
class IPMIEvent:
    """IPMI event (SEL entry)."""
    record_id: int = 0
    timestamp: float = 0.0
    generator_id: int = 0
    event_msg_format: int = 0
    sensor_type: int = 0
    sensor_number: int = 0
    event_direction: int = 0
    event_data: List[int] = field(default_factory=list)
    description: str = ""


# ============================================================================
# IPMI BMC Device
# ============================================================================

@dataclass
class IPMIBMC:
    """IPMI BMC device (mirrors struct ipmi_smi).

    Manages communication with the baseboard management controller.
    """
    name: str
    index: int
    addr: int = 0x20  # default BMC address
    channel: int = 0
    max_msg_len: int = 64
    sensors: Dict[int, IPMISensor] = field(default_factory=dict)
    events: List[IPMIEvent] = field(default_factory=list)
    event_receiver: int = 0
    registered: bool = False
    _next_event_id: int = 0
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def add_sensor(self, sensor: IPMISensor) -> None:
        self.sensors[sensor.number] = sensor

    def remove_sensor(self, number: int) -> bool:
        return self.sensors.pop(number, None) is not None

    def read_sensor(self, number: int) -> Optional[IPMISensor]:
        return self.sensors.get(number)

    def read_all_sensors(self) -> List[IPMISensor]:
        return list(self.sensors.values())

    def log_event(self, event: IPMIEvent) -> int:
        self._next_event_id += 1
        event.record_id = self._next_event_id
        event.timestamp = time.time()
        self.events.append(event)
        self._fire_event(event)
        return 0

    def get_sel_info(self) -> Dict[str, Any]:
        return {
            "entries": len(self.events),
            "capacity": 1024,
            "version": "1.5",
        }

    def cold_reset(self) -> int:
        """Issue BMC cold reset."""
        self.sensors.clear()
        self.events.clear()
        return 0

    def get_device_id(self) -> Dict[str, Any]:
        return {
            "device_id": 0x20,
            "device_revision": 0x01,
            "firmware_revision": "1.0.0",
            "ipmi_version": "2.0",
            "manufacturer_id": "UmerOS",
            "product_id": 0x0001,
        }

    def register_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _fire_event(self, event: IPMIEvent) -> None:
        for cb in self._listeners:
            cb(self.name, event)


# ============================================================================
# IPMI Subsystem Manager
# ============================================================================

class IPMISubsystem:
    """Central IPMI subsystem managing BMCs and sensor data."""

    def __init__(self) -> None:
        self._bmcs: Dict[str, IPMIBMC] = {}
        self._next_index: int = 0

    def register_bmc(self, bmc: IPMIBMC) -> int:
        bmc.index = self._next_index
        bmc.registered = True
        self._bmcs[bmc.name] = bmc
        self._next_index += 1
        return 0

    def unregister_bmc(self, name: str) -> int:
        self._bmcs.pop(name, None)
        return 0

    def get_bmc(self, name: str) -> Optional[IPMIBMC]:
        return self._bmcs.get(name)

    def enumerate_bmcs(self) -> List[IPMIBMC]:
        return list(self._bmcs.values())

    def read_sensor(self, bmc_name: str, sensor_num: int) -> Optional[IPMISensor]:
        bmc = self._bmcs.get(bmc_name)
        return bmc.read_sensor(sensor_num) if bmc else None

    def read_all_sensors(self, bmc_name: str) -> List[IPMISensor]:
        bmc = self._bmcs.get(bmc_name)
        return bmc.read_all_sensors() if bmc else []

    def get_events(self, bmc_name: str, limit: int = 100) -> List[IPMIEvent]:
        bmc = self._bmcs.get(bmc_name)
        if not bmc:
            return []
        return bmc.events[-limit:]


# ============================================================================
# Global IPMI Instance
# ============================================================================

_global_ipmi: Optional[IPMISubsystem] = None


def get_global_ipmi() -> IPMISubsystem:
    global _global_ipmi
    if _global_ipmi is None:
        _global_ipmi = IPMISubsystem()
    return _global_ipmi


def register_ipmi_bmc(bmc: IPMIBMC) -> int:
    return get_global_ipmi().register_bmc(bmc)


def ipmi_read_sensor(bmc_name: str, sensor_num: int) -> Optional[IPMISensor]:
    return get_global_ipmi().read_sensor(bmc_name, sensor_num)
