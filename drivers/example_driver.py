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

#!/usr/bin/env python3
"""
Umer OS Driver Framework

Provides a base class for hardware drivers and a DriverManager that
loads, unloads, and queries drivers at runtime.

Equivalent to drivers/ subsystem and modprobe.
"""


from typing import Protocol, runtime_checkable, Dict, Any

from .device import Device

# Import the global device registry
from .device_registry import DEVICE_REGISTRY

from .bus import BUS_REGISTRY

# Global registry for character devices
CHAR_DEVICES: Dict[str, Any] = {}
# Note: DEVICE_REGISTRY is now imported from device_registry module

@runtime_checkable
class FileOperations(Protocol):
    """Mimic file_operations for character devices."""
    def open(self, mode: str = "r") -> None: ...
    def read(self, size: int = -1) -> str: ...
    def write(self, data: str) -> int: ...
    def release(self) -> None: ...

class DriverBase:
    """Abstract base class for all Umer OS drivers."""

    def __init__(self, name: str, version: str, hardware_type: str):
        self.name = name
        self.version = version
        self.hardware_type = hardware_type
        self.loaded = False
        # Optional file operations for character devices
        self.file_ops: FileOperations | None = None

    # Existing methods (load, unload, status) remain unchanged

    # ----- New driver‑bus interaction hooks -----
    def can_bind(self, device: Device) -> bool:
        """Return True if this driver can manage the given device.
        Subclasses (e.g., PlatformDriver) should override this.
        """
        return False

    def bind(self, device: Device) -> None:
        """Bind this driver to the device. Called after can_bind returns True.
        Subclasses may implement driver‑specific initialization.
        """
        device.bind_driver(self)

    def unbind(self, device: Device) -> None:
        """Unbind this driver from the device (cleanup)."""
        device.unbind_driver()

    # ----- End of driver‑bus hooks -----

    # ... (rest of class definitions unchanged) ...

    # ── Driver Manager ───────────────────────────────────────────────────

class DriverManager:
    """Manages loading, unloading, and querying of hardware drivers, and device binding."""

    def __init__(self):
        self._drivers = {}
        self._available = {
            "umer-display": DisplayDriver,
            "umer-storage": StorageDriver,
            "umer-nic": NetworkDriver,
            "umer-audio": AudioDriver,
        }
        print(f"[DRIVER-MGR] Driver manager initialized ({len(self._available)} drivers available).")

    # ... load_driver unchanged ...

    def unload_driver(self, name: str) -> bool:
        if name not in self._drivers:
            print(f"[DRIVER-MGR] '{name}' is not loaded.")
            return False
        driver = self._drivers[name]
        driver.unload()
        # Unbind driver from any devices it managed and unregister those devices
        for dev in list(DEVICE_REGISTRY.values()):
            if dev.driver == driver:
                dev.unbind_driver()
                # Optionally unregister the device if it is no longer needed
                dev.unregister()
                # Remove from registry
                DEVICE_REGISTRY.pop(dev.dev_id, None)
        del self._drivers[name]
        # Remove from CHAR_DEVICES if present
        CHAR_DEVICES.pop(name, None)
        return True

    # ... remaining methods unchanged ...

@runtime_checkable
class FileOperations(Protocol):
    """Mimic file_operations for character devices."""
    def open(self, mode: str = "r") -> None: ...
    def read(self, size: int = -1) -> str: ...
    def write(self, data: str) -> int: ...
    def release(self) -> None: ...

class DriverBase:
    """Abstract base class for all Umer OS drivers."""

    def __init__(self, name: str, version: str, hardware_type: str):
        self.name = name
        self.version = version
        self.hardware_type = hardware_type
        self.loaded = False
        # Optional file operations for character devices
        self.file_ops: FileOperations | None = None

    # Existing methods (load, unload, status) remain unchanged

    # ----- New driver‑bus interaction hooks -----
    def can_bind(self, device: Device) -> bool:
        """Return True if this driver can manage the given device.
        Subclasses (e.g., PlatformDriver) should override this.
        """
        return False

    def bind(self, device: Device) -> None:
        """Bind this driver to the device. Called after can_bind returns True.
        Subclasses may implement driver‑specific initialization.
        """
        device.bind_driver(self)

    def unbind(self, device: Device) -> None:
        """Unbind this driver from the device (cleanup)."""
        device.unbind_driver()



# ── Built-in Drivers ─────────────────────────────────────────────────

class DisplayDriver(DriverBase):
    def __init__(self):
        super().__init__("umer-display", "1.0.0", "GPU/Display")

    def load(self):
        super().load()
        print(f"[DRIVER:{self.name}] Display framebuffer initialized (1920x1080).")
        return True


class StorageDriver(DriverBase):
    def __init__(self):
        super().__init__("umer-storage", "1.0.0", "Block/NVMe")

    def load(self):
        super().load()
        print(f"[DRIVER:{self.name}] NVMe controller detected (simulated).")
        return True


class NetworkDriver(DriverBase):
    def __init__(self):
        super().__init__("umer-nic", "1.0.0", "Network/Ethernet")

    def load(self):
        super().load()
        print(f"[DRIVER:{self.name}] Ethernet adapter initialized (1 Gbps).")
        return True


class AudioDriver(DriverBase):
    def __init__(self):
        super().__init__("umer-audio", "1.0.0", "Audio/HDA")

    def load(self):
        super().load()
        print(f"[DRIVER:{self.name}] High Definition Audio codec initialized.")
        return True


# ── Driver Manager ───────────────────────────────────────────────────

class DriverManager:
    """Manages loading, unloading, and querying of hardware drivers, and device binding."""

    def __init__(self):
        self._drivers = {}
        self._available = {
            "umer-display": DisplayDriver,
            "umer-storage": StorageDriver,
            "umer-nic": NetworkDriver,
            "umer-audio": AudioDriver,
        }
        print(f"[DRIVER-MGR] Driver manager initialized ({len(self._available)} drivers available).")
    """Manages loading, unloading, and querying of hardware drivers."""



    def load_driver(self, name: str) -> bool:
        if name in self._drivers:
            print(f"[DRIVER-MGR] '{name}' is already loaded.")
            return True
        cls = self._available.get(name)
        if not cls:
            print(f"[DRIVER-MGR] ERROR: Driver '{name}' not found.")
            return False
        driver = cls()
        driver.load()
        # Register driver with any existing bus for potential device binding
        for bus in BUS_REGISTRY.values():
            bus.register_driver(driver)
        self._drivers[name] = driver
        # If driver provides character device ops, ensure it's in CHAR_DEVICES
        if hasattr(driver, 'file_ops') and driver.file_ops:
            CHAR_DEVICES[driver.name] = driver
        return True

    def unload_driver(self, name: str) -> bool:
        if name not in self._drivers:
            print(f"[DRIVER-MGR] '{name}' is not loaded.")
            return False
        driver = self._drivers[name]
        driver.unload()
        # Unbind driver from any devices it managed
        for dev in DEVICE_REGISTRY.values():
            if dev.driver == driver:
                dev.unbind_driver()
        del self._drivers[name]
        # Remove from CHAR_DEVICES if present
        CHAR_DEVICES.pop(name, None)
        return True

    def list_loaded(self) -> list:
        return [d.status() for d in self._drivers.values()]

    def list_available(self) -> list:
        return list(self._available.keys())

    def load_all_defaults(self):
        """Load all default drivers during boot."""
        for name in self._available:
            self.load_driver(name)
        # Bind devices to drivers after all drivers are loaded
        for dev in DEVICE_REGISTRY.values():
            if dev.bus:
                for drv in dev.bus.drivers:
                    if drv.can_bind(dev):
                        drv.bind(dev)
                        break
        # Ensure any char devices from loaded drivers are registered
        for drv in self._drivers.values():
            if hasattr(drv, 'file_ops') and drv.file_ops:
                CHAR_DEVICES[drv.name] = drv