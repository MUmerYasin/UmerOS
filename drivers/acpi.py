"""
UmerOS ACPI Subsystem
=====================
Kernel-like ACPI (Advanced Configuration and Power Interface) support.
Implements ACPI tables, devices, power management, thermal zones,
and event handling mirroring the kernel's drivers/acpi/.

Reference: Documentation/driver-api/acpi/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# ACPI Constants
# ============================================================================

ACPI_SUCCESS: int = 0
ACPI_FAILURE: int = 1
ACPI_PENDING: int = 2
ACPI_ABORTED: int = 3
ACPI_TIME_LIMIT: int = 4
ACPI_NO_HANDLER: int = 5

ACPI_BUS_CHECK: int = 0x00
ACPI_DEVICE_CHECK: int = 0x01
ACPI_BUS_NOTIFY_DEVICE_CHECK: int = 0x00
ACPI_BUS_NOTIFY_EJECT_REQUEST: int = 0x01
ACPI_BUS_NOTIFY_INSTALL: int = 0x01
ACPI_BUS_NOTIFY_REMOVAL: int = 0x03


class ACPIObject_type(IntEnum):
    """ACPI object types (mirrors acpi_object_type)."""
    ANY = 0
    NUMERIC = 1
    STRING = 2
    BUFFER = 3
    PACKAGE = 4
    DEVICE = 5
    EVENT = 6
    METHOD = 7
    POWER_RESOURCE = 8
    PROCESSOR = 9
    THERMAL_ZONE = 10
    BUFFER_FIELD = 11
    DDB_HANDLE = 12
    DEBUG_OBJECT = 13


class ACPIPowerState(IntEnum):
    """ACPI power states."""
    D0 = 0  # Full on
    D1 = 1  # Low power
    D2 = 2  # Deeper sleep
    D3_HOT = 3  # Off but can wake
    D3_COLD = 4  # Fully off


# ============================================================================
# ACPI Table Header
# ============================================================================

@dataclass
class ACPITableHeader:
    """ACPI table header (common to all SDT entries).

    Mirrors struct acpi_table_header in the kernel.
    """
    signature: str
    length: int
    revision: int
    checksum: int
    oem_id: str
    oem_table_id: str
    oem_revision: int
    creator_id: str
    creator_revision: int


# ============================================================================
# ACPI Device
# ============================================================================

@dataclass
class ACPIDevice:
    """Represents an ACPI device node.

    Mirrors struct acpi_device in the kernel.
    """
    device_id: str
    name: str
    handle: int
    status: int = 0
    flags: int = 0
    hardware_id: str = ""
    unique_id: str = ""
    class_id: str = ""
    power_state: ACPIPowerState = ACPIPowerState.D0
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def evaluate_method(self, method: str, *args: Any) -> Any:
        """Evaluate an ACPI method (like acpi_evaluate_object)."""
        if method in self._ops:
            return self._ops[method](*args)
        return None

    def set_power_state(self, state: ACPIPowerState) -> int:
        """Set device power state."""
        self.power_state = state
        return ACPI_SUCCESS

    def is_present(self) -> bool:
        return bool(self.status & 0x01)


# ============================================================================
# ACPI Driver
# ============================================================================

@dataclass
class ACPIDriver:
    """ACPI driver binding.

    Mirrors struct acpi_driver.
    """
    name: str
    class_id: str = ""
    ids: List[str] = field(default_factory=list)
    ops: Dict[str, Callable] = field(default_factory=dict)
    flags: int = 0

    def match(self, device: ACPIDevice) -> bool:
        """Check if driver matches a device."""
        if self.class_id and self.class_id == device.class_id:
            return True
        if self.ids:
            return device.hardware_id in self.ids
        return False

    def attach(self, device: ACPIDevice) -> int:
        """Attach driver to device."""
        if "attach" in self.ops:
            return self.ops["attach"](device)
        return ACPI_SUCCESS

    def detach(self, device: ACPIDevice) -> int:
        """Detach driver from device."""
        if "detach" in self.ops:
            return self.ops["detach"](device)
        return ACPI_SUCCESS


# ============================================================================
# ACPI Power Management
# ============================================================================

@dataclass
class ACPIPowerResource:
    """ACPI Power Resource.

    Mirrors struct acpi_power_resource.
    """
    name: str
    system_level: int = 0
    order: int = 0
    state: int = 0  # 0=off, 1=on
    _ref_count: int = 0

    def reference(self) -> int:
        self._ref_count += 1
        if self._ref_count == 1:
            self.state = 1
        return ACPI_SUCCESS

    def unreference(self) -> int:
        self._ref_count = max(0, self._ref_count - 1)
        if self._ref_count == 0:
            self.state = 0
        return ACPI_SUCCESS


@dataclass
class ACPIPowerSwitch:
    """Power switch zone grouping devices by power resource dependencies."""
    name: str
    resources: List[str] = field(default_factory=list)
    devices: List[str] = field(default_factory=list)


# ============================================================================
# ACPI Event Handler
# ============================================================================

@dataclass
class ACPIEventHandler:
    """ACPI event handler callback registration."""
    device_id: str
    type: int
    callback: Callable
    data: Any = None


# ============================================================================
# ACPI Subsystem Manager
# ============================================================================

class ACPISubsystem:
    """Central ACPI subsystem managing tables, devices, drivers, and events.

    Mirrors the kernel's acpi subsystem initialization and registration.
    """

    def __init__(self) -> None:
        self._tables: Dict[str, ACPITableHeader] = {}
        self._devices: Dict[str, ACPIDevice] = {}
        self._drivers: List[ACPIDriver] = []
        self._power_resources: Dict[str, ACPIPowerResource] = {}
        self._event_handlers: List[ACPIEventHandler] = []

    # --- Table management ---

    def install_table(self, table: ACPITableHeader) -> int:
        """Install an ACPI table."""
        self._tables[table.signature] = table
        return ACPI_SUCCESS

    def get_table(self, signature: str) -> Optional[ACPITableHeader]:
        return self._tables.get(signature)

    def enumerate_tables(self) -> List[str]:
        return list(self._tables.keys())

    # --- Device management ---

    def add_device(self, device: ACPIDevice) -> int:
        """Register an ACPI device."""
        self._devices[device.device_id] = device
        self._notify_bus_check(device)
        return ACPI_SUCCESS

    def remove_device(self, device_id: str) -> int:
        device = self._devices.pop(device_id, None)
        if device:
            for drv in self._drivers:
                if drv.match(device):
                    drv.detach(device)
        return ACPI_SUCCESS

    def get_device(self, device_id: str) -> Optional[ACPIDevice]:
        return self._devices.get(device_id)

    def enumerate_devices(self) -> List[ACPIDevice]:
        return list(self._devices.values())

    # --- Driver management ---

    def register_driver(self, driver: ACPIDriver) -> int:
        self._drivers.append(driver)
        for device in self._devices.values():
            if driver.match(device):
                driver.attach(device)
        return ACPI_SUCCESS

    def unregister_driver(self, driver: ACPIDriver) -> int:
        if driver in self._drivers:
            self._drivers.remove(driver)
        return ACPI_SUCCESS

    # --- Power resource management ---

    def add_power_resource(self, res: ACPIPowerResource) -> int:
        self._power_resources[res.name] = res
        return ACPI_SUCCESS

    def reference_power(self, name: str) -> int:
        res = self._power_resources.get(name)
        return res.reference() if res else ACPI_FAILURE

    def unreference_power(self, name: str) -> int:
        res = self._power_resources.get(name)
        return res.unreference() if res else ACPI_FAILURE

    # --- Event handling ---

    def register_event_handler(self, handler: ACPIEventHandler) -> None:
        self._event_handlers.append(handler)

    def emit_event(self, device_id: str, event_type: int) -> None:
        for h in self._event_handlers:
            if h.device_id == device_id or h.device_id == "*":
                h.callback(device_id, event_type, h.data)

    def _notify_bus_check(self, device: ACPIDevice) -> None:
        self.emit_event(device.device_id, ACPI_BUS_NOTIFY_DEVICE_CHECK)

    # --- Power transitions ---

    def transition_device(self, device_id: str, target: ACPIPowerState) -> int:
        device = self._devices.get(device_id)
        if not device:
            return ACPI_FAILURE
        return device.set_power_state(target)

    def sleep_devices(self, state: ACPIPowerState) -> int:
        for device in self._devices.values():
            device.set_power_state(state)
        return ACPI_SUCCESS


# ============================================================================
# Global ACPI Subsystem Instance
# ============================================================================

_global_acpi: Optional[ACPISubsystem] = None


def get_global_acpi() -> ACPISubsystem:
    global _global_acpi
    if _global_acpi is None:
        _global_acpi = ACPISubsystem()
    return _global_acpi


def register_acpi_device(device: ACPIDevice) -> int:
    return get_global_acpi().add_device(device)


def register_acpi_driver(driver: ACPIDriver) -> int:
    return get_global_acpi().register_driver(driver)
