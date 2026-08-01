#!/usr/bin/env python3
"""
Umer OS Device Model

Defines a generic Device class representing a hardware device that can be bound to a driver.
"""

from typing import Optional

class Device:
    """Represents a hardware device (e.g., platform device, PCI device)."""

    def __init__(self, name: str, hardware_type: str, bus: Optional[object] = None):
        self.name = name
        self.hardware_type = hardware_type
        self.bus = bus  # Reference to Bus instance, if any
        self.driver: Optional[object] = None
        # Register with bus if provided
        if bus is not None:
            from .bus import BUS_REGISTRY
            if isinstance(bus, str):
                if bus in BUS_REGISTRY:
                    bus_obj = BUS_REGISTRY[bus]
                else:
                    from .bus import Bus
                    bus_obj = Bus(bus)
                self.bus = bus_obj
            else:
                bus_obj = bus
            bus_obj.register_device(self)

    def bind_driver(self, driver: object) -> None:
        """Bind a driver to this device."""
        self.driver = driver
        print(f"[DEVICE] {self.name} bound to driver {driver.name}")

    def unbind_driver(self) -> None:
        """Unbind any driver from this device."""
        if self.driver:
            print(f"[DEVICE] {self.name} unbound from driver {self.driver.name}")
        self.driver = None

    def __repr__(self) -> str:
        return f"<Device {self.name} ({self.hardware_type}) driver={self.driver.name if self.driver else None}>"
