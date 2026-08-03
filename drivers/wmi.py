"""
UmerOS WMI Subsystem
====================
Linux kernel-like WMI (Windows Management Instrumentation) subsystem.
Implements WMI device enumeration, method evaluation, event handling,
and data block access for ACPI/WMI interfaces.

Reference: drivers/acpi/wmi.c
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import uuid


# ============================================================================
# WMI Constants
# ============================================================================

WMI_SUCCESS: int = 0
WMI_ERROR: int = 1
WMI_NOT_FOUND: int = 2
WMI_INVALID_GUID: int = 3
WMI_METHOD_NOT_FOUND: int = 4
WMI_ACCESS_DENIED: int = 5

WMI_MAX_INSTANCES: int = 256
WMI_MAX_METHODS: int = 256
WMI_MAX_EVENTS: int = 128
WMI_MAX_DATA_BLOCKS: int = 64


class WMIStatus(IntEnum):
    """WMI status codes."""
    SUCCESS: int = 0
    NOT_FOUND: int = 1
    INVALID_PARAMETER: int = 2
    ACCESS_DENIED: int = 3
    NOT_SUPPORTED: int = 4
    ALREADY_INITIALIZED: int = 5
    NOT_INITIALIZED: int = 6


# ============================================================================
# WMI GUID
# ============================================================================

@dataclass
class WMIGuid:
    """WMI GUID registration entry."""
    guid_string: str
    instance_count: int = 1
    flags: int = 0
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    @property
    def guid_hex(self) -> str:
        return self.guid_string.replace('-', '').upper()

    def register_method(self, name: str, callback: Callable) -> None:
        self._ops[name] = callback

    def call_method(self, name: str, *args: Any) -> Any:
        if name not in self._ops:
            return WMI_METHOD_NOT_FOUND
        return self._ops[name](*args)


# ============================================================================
# WMI Data Block
# ============================================================================

@dataclass
class WMIDataBlock:
    """WMI data block (mirrors wmi_data_block)."""
    guid: str
    instance: int = 0
    flags: int = 0
    data: bytes = b''
    length: int = 0
    timestamp: float = 0.0

    def set_data(self, data: bytes) -> None:
        self.data = data
        self.length = len(data)

    def get_data(self) -> bytes:
        return self.data


# ============================================================================
# WMI Method Call
# ============================================================================

@dataclass
class WMIMethodCall:
    """WMI method call context."""
    guid: str
    instance_id: int = 0
    method_id: int = 0
    in_params: Dict[str, Any] = field(default_factory=dict)
    out_params: Dict[str, Any] = field(default_factory=dict)
    status: WMIStatus = WMIStatus.SUCCESS
    return_value: Any = None


# ============================================================================
# WMI Event
# ============================================================================

@dataclass
class WMIEvent:
    """WMI event notification."""
    guid: str
    event_type: int = 0
    instance_id: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


# ============================================================================
# WMI Device
# ============================================================================

@dataclass
class WMIDevice:
    """WMI device (mirrors struct wmi_device)."""
    name: str
    index: int
    acpi_device: str = ""
    guid_list: List[str] = field(default_factory=list)
    flags: int = 0
    registered: bool = False
    _data_blocks: Dict[str, List[WMIDataBlock]] = field(default_factory=dict, repr=False)
    _event_handlers: List[Callable] = field(default_factory=list, repr=False)

    def add_guid(self, guid_str: str) -> None:
        if guid_str not in self.guid_list:
            self.guid_list.append(guid_str)

    def evaluate_method(self, guid: str, method_id: int, in_params: Dict[str, Any] = None) -> WMIMethodCall:
        call = WMIMethodCall(guid=guid, method_id=method_id, in_params=in_params or {})
        if guid not in self.guid_list:
            call.status = WMIStatus.NOT_FOUND
            return call
        call.status = WMIStatus.SUCCESS
        call.out_params = {"result": 0}
        call.return_value = 0
        return call

    def query_data_block(self, guid: str, instance: int = 0) -> Optional[WMIDataBlock]:
        blocks = self._data_blocks.get(guid, [])
        for b in blocks:
            if b.instance == instance:
                return b
        return None

    def set_data_block(self, guid: str, instance: int, data: bytes) -> None:
        if guid not in self._data_blocks:
            self._data_blocks[guid] = []
        block = WMIDataBlock(guid=guid, instance=instance, data=data)
        self._data_blocks[guid].append(block)

    def register_event_handler(self, callback: Callable) -> None:
        self._event_handlers.append(callback)

    def fire_event(self, event: WMIEvent) -> None:
        for handler in self._event_handlers:
            handler(event)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "acpi_device": self.acpi_device,
            "guids": self.guid_list,
            "data_blocks": sum(len(v) for v in self._data_blocks.values()),
        }


# ============================================================================
# WMI Subsystem Manager
# ============================================================================

class WMISubsystem:
    """Central WMI subsystem managing devices, GUIDs, and events."""

    def __init__(self) -> None:
        self._devices: Dict[str, WMIDevice] = {}
        self._guids: Dict[str, WMIGuid] = {}
        self._global_events: List[WMIEvent] = []
        self._next_index: int = 0

    def register_device(self, device: WMIDevice) -> int:
        device.index = self._next_index
        device.registered = True
        self._devices[device.name] = device
        self._next_index += 1
        return 0

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return 0

    def get_device(self, name: str) -> Optional[WMIDevice]:
        return self._devices.get(name)

    def enumerate_devices(self) -> List[WMIDevice]:
        return list(self._devices.values())

    def register_guid(self, guid: WMIGuid) -> int:
        self._guids[guid.guid_string] = guid
        return 0

    def unregister_guid(self, guid_string: str) -> int:
        self._guids.pop(guid_string, None)
        return 0

    def get_guid(self, guid_string: str) -> Optional[WMIGuid]:
        return self._guids.get(guid_string)

    def evaluate_method(self, device_name: str, guid: str, method_id: int, params: Dict[str, Any] = None) -> WMIMethodCall:
        device = self._devices.get(device_name)
        if not device:
            call = WMIMethodCall(guid=guid, method_id=method_id)
            call.status = WMIStatus.NOT_FOUND
            return call
        return device.evaluate_method(guid, method_id, params)

    def post_event(self, event: WMIEvent) -> None:
        self._global_events.append(event)

    def get_events(self, limit: int = 100) -> List[WMIEvent]:
        return self._global_events[-limit:]

    def get_all_status(self) -> Dict[str, Any]:
        return {
            "devices": len(self._devices),
            "guids": len(self._guids),
            "events": len(self._global_events),
        }


# ============================================================================
# Global WMI Instance
# ============================================================================

_global_wmi: Optional[WMISubsystem] = None


def get_global_wmi() -> WMISubsystem:
    global _global_wmi
    if _global_wmi is None:
        _global_wmi = WMISubsystem()
    return _global_wmi


def register_wmi_device(device: WMIDevice) -> int:
    return get_global_wmi().register_device(device)


def wmi_evaluate_method(device_name: str, guid: str, method_id: int, params: Dict[str, Any] = None) -> WMIMethodCall:
    return get_global_wmi().evaluate_method(device_name, guid, method_id, params)
