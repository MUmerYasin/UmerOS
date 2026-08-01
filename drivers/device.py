#!/usr/bin/env python3
"""
Umer OS Device Model – extended with registration API
"""

from typing import Optional

# Import registration helpers (will be created)
from .device_registry import device_register, device_unregister

class Device:
    """Represents a hardware device (e.g., platform device, PCI device)."""

    def __init__(self, name: str, hardware_type: str, bus: Optional[object] = None):
        self.name = name
        self.hardware_type = hardware_type
        self.bus = bus  # Reference to Bus instance, if any
        self.driver: Optional[object] = None
        # Unique identifier used in the global registry (default to name)
        self.dev_id = name
        # Allocate a list for device‑managed resources
        self._dev_resources = []  # populated by devm_* helpers
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
        # Finally register the device with the driver core
        device_register(self)

    # ---------------------------------------------------------------------
    # Core registration / un‑registration API (mirrors Linux driver model)
    # ---------------------------------------------------------------------
    def register(self) -> None:
        """Explicitly register the device with the driver core.
        The constructor already performs registration, but this method allows
        re‑registration after a temporary unregister.
        """
        device_register(self)

    def unregister(self) -> None:
        """Unregister the device from the driver core and invoke cleanup.
        Calls the global ``device_unregister`` helper which will also trigger the
        ``release`` callback.
        """
        device_unregister(self)

    # ---------------------------------------------------------------------
    # Driver binding helpers – unchanged from previous version
    # ---------------------------------------------------------------------
    def bind_driver(self, driver: object) -> None:
        """Bind a driver to this device."""
        self.driver = driver
        print(f"[DEVICE] {self.name} bound to driver {driver.name}")

    def unbind_driver(self) -> None:
        """Unbind any driver from this device."""
        if self.driver:
            print(f"[DEVICE] {self.name} unbound from driver {self.driver.name}")
        self.driver = None

    # ---------------------------------------------------------------------
    # Release hook – called when the device is finally removed.  Sub‑classes may
    # override this to free custom resources.
    # ---------------------------------------------------------------------
    def release(self) -> None:
        """Default release implementation (no‑op)."""
        pass

    def __repr__(self) -> str:
        return f"<Device {self.name} ({self.hardware_type}) driver={self.driver.name if self.driver else None}>"
