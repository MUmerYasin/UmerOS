#!/usr/bin/env python3
"""
Umer OS Device Model – extended with registration API
"""

from typing import Optional, List

# Import registration helpers (will be created)
from .device_registry import device_register, device_unregister
# Import device link utilities (will be created)
from .device_link import DeviceLink, DL_FLAG_STATELESS, DL_FLAG_PM_RUNTIME

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
        # Device link management
        self._supplier_links: List[DeviceLink] = []  # Devices this device supplies to
        self._consumer_links: List[DeviceLink] = []  # Devices this device depends on
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
    # Device link management
    # ---------------------------------------------------------------------
    def add_device_link(self, supplier: 'Device', flags: int = 0) -> DeviceLink:
        """Create a link where *supplier* provides resources to *self*.

        *flags* can include ``DL_FLAG_STATELESS`` or ``DL_FLAG_PM_RUNTIME``.
        """
        link = DeviceLink(supplier=supplier, consumer=self, flags=flags)
        self._consumer_links.append(link)
        supplier._supplier_links.append(link)
        return link

    def remove_device_link(self, link: DeviceLink) -> None:
        """Remove a previously added link."""
        if link in self._consumer_links:
            self._consumer_links.remove(link)
        if link in link.supplier._supplier_links:
            link.supplier._supplier_links.remove(link)

    def get_supplier_devices(self) -> List['Device']:
        """Return a list of supplier devices for this device."""
        return [link.supplier for link in self._consumer_links]

    def get_consumer_devices(self) -> List['Device']:
        """Return a list of consumer devices that depend on this device."""
        return [link.consumer for link in self._supplier_links]

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
        # Release device‑managed resources
        from .devres import devm_release_all
        devm_release_all(self)
        # Remove all device links
        for link in list(self._consumer_links):
            self.remove_device_link(link)
        for link in list(self._supplier_links):
            link.consumer.remove_device_link(link)

    def __repr__(self) -> str:
        return f"<Device {self.name} ({self.hardware_type}) driver={self.driver.name if self.driver else None}>"
