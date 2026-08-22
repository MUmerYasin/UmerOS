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
UmerOS PCI Endpoint Framework
==============================
Kernel PCI Endpoint subsystem.
Implements PCI endpoint controllers, functions,
and operations for endpoint mode operation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PCI Endpoint Constants
# ---------------------------------------------------------------------------
PCI_EP_BUS_MAX: int = 255
PCI_EP_DEV_MAX: int = 31
PCI_EP_FUNC_MAX: int = 7
PCI_EP_BAR_MAX: int = 6

PCI_EP_BAR_0: int = 0
PCI_EP_BAR_1: int = 1
PCI_EP_BAR_2: int = 2
PCI_EP_BAR_3: int = 3
PCI_EP_BAR_4: int = 4
PCI_EP_BAR_5: int = 5

PCI_EP_STATUS_DISCONNECTED: int = 0
PCI_EP_STATUS_CONNECTED: int = 1
PCI_EP_STATUS_SUSPENDED: int = 2

PCI_EP_CLASS_VENDOR_SPEC: int = 0x00
PCI_EP_CLASS_MASS_STORAGE: int = 0x01
PCI_EP_CLASS_NETWORK: int = 0x02
PCI_EP_CLASS_DISPLAY: int = 0x03
PCI_EP_CLASS_MULTIMEDIA: int = 0x04
PCI_EP_CLASS_MEMORY: int = 0x05
PCI_EP_CLASS_BRIDGE: int = 0x06

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_controllers: Dict[str, PciEpController] = {}
_functions: Dict[str, PciEpFunction] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class PciEpBar:
    """PCI Endpoint BAR (Base Address Register)"""
    index: int
    size: int = 0
    phys_addr: int = 0
    virt_addr: int = 0
    is_mapped: bool = False
    is_enabled: bool = False


@dataclass
class PciEpMsix:
    """MSI-X capability"""
    is_enabled: bool = False
    table_size: int = 0
    table_phys: int = 0
    pba_phys: int = 0


@dataclass
class PciEpFunction:
    """PCI Endpoint Function"""
    name: str
    func_id: int = 0
    device_id: int = 0x1000
    vendor_id: int = 0x1AF4
    revision: int = 0x01
    class_code: int = PCI_EP_CLASS_VENDOR_SPEC
    subsystem_vendor_id: int = 0
    subsystem_id: int = 0
    is_registered: bool = False
    is_bound: bool = False
    _bars: Dict[int, PciEpBar] = field(default_factory=dict)
    _msix: Optional[PciEpMsix] = None
    _ops: Dict[str, Callable] = field(default_factory=dict)
    _private_data: Any = None


@dataclass
class PciEpController:
    """PCI Endpoint Controller"""
    name: str
    is_registered: bool = False
    is_initialized: bool = False
    status: int = PCI_EP_STATUS_DISCONNECTED
    max_functions: int = PCI_EP_FUNC_MAX
    _functions: List[str] = field(default_factory=list)
    _ops: Dict[str, Callable] = field(default_factory=dict)
    _start_time: float = 0.0


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def register_controller(name: str, max_functions: int = PCI_EP_FUNC_MAX) -> PciEpController:
    """Register a PCI endpoint controller"""
    if name in _controllers:
        log.warning("PCI EP controller %s already registered", name)
        return _controllers[name]

    ctrl = PciEpController(
        name=name,
        max_functions=max_functions,
        is_registered=True,
    )
    _controllers[name] = ctrl
    log.info("Registered PCI EP controller: %s (max_func=%d)", name, max_functions)
    return ctrl


def register_function(name: str, func_id: int = 0,
                      device_id: int = 0x1000,
                      vendor_id: int = 0x1AF4,
                      class_code: int = PCI_EP_CLASS_VENDOR_SPEC) -> PciEpFunction:
    """Register a PCI endpoint function"""
    if name in _functions:
        log.warning("PCI EP function %s already registered", name)
        return _functions[name]

    func = PciEpFunction(
        name=name,
        func_id=func_id,
        device_id=device_id,
        vendor_id=vendor_id,
        class_code=class_code,
        is_registered=True,
    )

    # Initialize BARs
    for i in range(PCI_EP_BAR_MAX):
        func._bars[i] = PciEpBar(index=i)

    _functions[name] = func
    log.info("Registered PCI EP function: %s (dev=%04X, ven=%04X)",
             name, device_id, vendor_id)
    return func


def unregister_controller(name: str) -> bool:
    """Unregister a PCI endpoint controller"""
    if name not in _controllers:
        log.warning("PCI EP controller %s not found", name)
        return False

    ctrl = _controllers[name]
    if ctrl._functions:
        log.warning("Cannot unregister controller with bound functions")
        return False

    del _controllers[name]
    log.info("Unregistered PCI EP controller: %s", name)
    return True


def unregister_function(name: str) -> bool:
    """Unregister a PCI endpoint function"""
    if name not in _functions:
        log.warning("PCI EP function %s not found", name)
        return False

    func = _functions[name]
    if func.is_bound:
        log.warning("Cannot unregister bound function %s", name)
        return False

    del _functions[name]
    log.info("Unregistered PCI EP function: %s", name)
    return True


def get_controller(name: str) -> Optional[PciEpController]:
    """Get a registered PCI endpoint controller"""
    return _controllers.get(name)


def get_function(name: str) -> Optional[PciEpFunction]:
    """Get a registered PCI endpoint function"""
    return _functions.get(name)


def list_controllers() -> List[str]:
    """List all registered PCI endpoint controllers"""
    return list(_controllers.keys())


def list_functions() -> List[str]:
    """List all registered PCI endpoint functions"""
    return list(_functions.keys())


# ---------------------------------------------------------------------------
# Controller Operations
# ---------------------------------------------------------------------------
def initialize_controller(name: str) -> bool:
    """Initialize PCI endpoint controller"""
    ctrl = get_controller(name)
    if ctrl is None:
        log.error("PCI EP controller %s not found", name)
        return False

    ctrl.is_initialized = True
    ctrl._start_time = time.time()
    log.info("Initialized PCI EP controller: %s", name)
    return True


def start_controller(name: str) -> bool:
    """Start PCI endpoint controller"""
    ctrl = get_controller(name)
    if ctrl is None:
        return False

    if not ctrl.is_initialized:
        log.error("Controller %s not initialized", name)
        return False

    ctrl.status = PCI_EP_STATUS_CONNECTED
    log.info("Started PCI EP controller: %s", name)
    return True


def stop_controller(name: str) -> bool:
    """Stop PCI endpoint controller"""
    ctrl = get_controller(name)
    if ctrl is None:
        return False

    ctrl.status = PCI_EP_STATUS_DISCONNECTED
    log.info("Stopped PCI EP controller: %s", name)
    return True


def get_controller_status(name: str) -> int:
    """Get controller status"""
    ctrl = get_controller(name)
    if ctrl is None:
        return PCI_EP_STATUS_DISCONNECTED
    return ctrl.status


# ---------------------------------------------------------------------------
# Function Binding
# ---------------------------------------------------------------------------
def bind_function(controller_name: str, function_name: str) -> bool:
    """Bind a function to a controller"""
    ctrl = get_controller(controller_name)
    if ctrl is None:
        log.error("PCI EP controller %s not found", controller_name)
        return False

    func = get_function(function_name)
    if func is None:
        log.error("PCI EP function %s not found", function_name)
        return False

    if len(ctrl._functions) >= ctrl.max_functions:
        log.error("Controller %s at max functions", controller_name)
        return False

    ctrl._functions.append(function_name)
    func.is_bound = True
    log.info("Bound function %s to controller %s", function_name, controller_name)
    return True


def unbind_function(controller_name: str, function_name: str) -> bool:
    """Unbind a function from a controller"""
    ctrl = get_controller(controller_name)
    if ctrl is None:
        return False

    func = get_function(function_name)
    if func is None:
        return False

    if function_name in ctrl._functions:
        ctrl._functions.remove(function_name)
        func.is_bound = False
        log.info("Unbound function %s from controller %s", function_name, controller_name)
        return True
    return False


# ---------------------------------------------------------------------------
# BAR Operations
# ---------------------------------------------------------------------------
def map_bar(function_name: str, bar_index: int, size: int,
            phys_addr: int = 0) -> bool:
    """Map a BAR"""
    func = get_function(function_name)
    if func is None:
        log.error("PCI EP function %s not found", function_name)
        return False

    if bar_index not in func._bars:
        log.error("Invalid BAR index: %d", bar_index)
        return False

    bar = func._bars[bar_index]
    bar.size = size
    bar.phys_addr = phys_addr
    bar.is_mapped = True
    bar.is_enabled = True
    log.info("Mapped BAR %d on %s: size=%d, addr=0x%X",
             bar_index, function_name, size, phys_addr)
    return True


def unmap_bar(function_name: str, bar_index: int) -> bool:
    """Unmap a BAR"""
    func = get_function(function_name)
    if func is None:
        return False

    if bar_index not in func._bars:
        return False

    bar = func._bars[bar_index]
    bar.is_mapped = False
    bar.is_enabled = False
    log.info("Unmapped BAR %d on %s", bar_index, function_name)
    return True


def get_bar_info(function_name: str, bar_index: int) -> Optional[PciEpBar]:
    """Get BAR information"""
    func = get_function(function_name)
    if func is None:
        return None

    return func._bars.get(bar_index)


# ---------------------------------------------------------------------------
# MSI-X Operations
# ---------------------------------------------------------------------------
def enable_msix(function_name: str, table_size: int) -> bool:
    """Enable MSI-X for a function"""
    func = get_function(function_name)
    if func is None:
        return False

    func._msix = PciEpMsix(
        is_enabled=True,
        table_size=table_size,
    )
    log.info("Enabled MSI-X on %s (table_size=%d)", function_name, table_size)
    return True


def disable_msix(function_name: str) -> bool:
    """Disable MSI-X for a function"""
    func = get_function(function_name)
    if func is None:
        return False

    func._msix = None
    log.info("Disabled MSI-X on %s", function_name)
    return True


def get_msix_info(function_name: str) -> Optional[PciEpMsix]:
    """Get MSI-X information"""
    func = get_function(function_name)
    if func is None:
        return None
    return func._msix


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def set_vendor_id(function_name: str, vendor_id: int) -> bool:
    """Set vendor ID"""
    func = get_function(function_name)
    if func is None:
        return False
    func.vendor_id = vendor_id
    return True


def set_device_id(function_name: str, device_id: int) -> bool:
    """Set device ID"""
    func = get_function(function_name)
    if func is None:
        return False
    func.device_id = device_id
    return True


def set_class_code(function_name: str, class_code: int) -> bool:
    """Set class code"""
    func = get_function(function_name)
    if func is None:
        return False
    func.class_code = class_code
    return True


def get_config_space(function_name: str) -> Dict[int, int]:
    """Get simulated config space"""
    func = get_function(function_name)
    if func is None:
        return {}

    return {
        0x00: func.vendor_id | (func.device_id << 16),
        0x04: 0x00000000,  # Status/Command
        0x08: (func.revision) | (func.class_code << 24),
        0x2C: func.subsystem_vendor_id | (func.subsystem_id << 16),
    }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== UmerOS PCI Endpoint Framework Demo ===\n")

    # Register controller
    ctrl = register_controller("pci_ep0", max_functions=4)
    initialize_controller("pci_ep0")
    start_controller("pci_ep0")

    # Register functions
    register_function("ep-net", device_id=0x1000, class_code=PCI_EP_CLASS_NETWORK)
    register_function("ep-storage", device_id=0x1001, class_code=PCI_EP_CLASS_MASS_STORAGE)

    print(f"Controllers: {list_controllers()}")
    print(f"Functions: {list_functions()}")

    # Bind functions
    bind_function("pci_ep0", "ep-net")
    bind_function("pci_ep0", "ep-storage")

    # Configure BARs
    map_bar("ep-net", 0, size=4096, phys_addr=0x80000000)
    map_bar("ep-net", 2, size=16384, phys_addr=0x80001000)

    # Enable MSI-X
    enable_msix("ep-net", table_size=16)

    # Get config space
    config = get_config_space("ep-net")
    print(f"\nep-net config space: {config}")

    bar0 = get_bar_info("ep-net", 0)
    print(f"ep-net BAR0: mapped={bar0.is_mapped}, size={bar0.size}, addr=0x{bar0.phys_addr:X}")

    msix = get_msix_info("ep-net")
    print(f"ep-net MSI-X: enabled={msix.is_enabled}, table_size={msix.table_size}")

    # Status
    print(f"\nController status: {get_controller_status('pci_ep0')}")
