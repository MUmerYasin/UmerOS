from typing import Dict, List, Optional
from .device import Device

# Global bus registry: maps bus name to Bus instance
BUS_REGISTRY: Dict[str, "Bus"] = {}

class Bus:
    """Represents a communication bus in the driver model (e.g., PCI, I2C).
    Drivers can register to a bus, and devices can be attached to it.
    """

    def __init__(self, name: str):
        self.name = name
        self.drivers: List["DriverBase"] = []  # type: ignore
        self.devices: List["Device"] = []
        BUS_REGISTRY[name] = self

    def register_driver(self, driver):
        """Register a driver with this bus."""
        self.drivers.append(driver)
        # Attempt to bind driver to any existing devices on this bus
        for dev in self.devices:
            if driver.can_bind(dev):
                driver.bind(dev)

    def register_device(self, device):
        """Register a device on this bus and try to bind an appropriate driver."""
        self.devices.append(device)
        for drv in self.drivers:
            if drv.can_bind(device):
                drv.bind(device)
                break

    def unregister_device(self, device):
        """Unregister a device from this bus and trigger its release."""
        if device in self.devices:
            self.devices.remove(device)
            from .device_registry import device_unregister
            device_unregister(device)

    def __repr__(self):
        return f"<Bus {self.name}: {len(self.drivers)} drivers, {len(self.devices)} devices>"

# Default platform bus instance for platform devices
platform_bus = Bus('platform')
