#!/usr/bin/env python3
"""
Umer OS Platform Driver Base

Defines a base class for drivers that bind to platform devices.
"""

from .example_driver import DriverBase
from .device import Device

class PlatformDriver(DriverBase):
    """Base class for platform drivers that can bind to devices.

    Subclasses should override :meth:`can_bind` to provide matching logic based on the
    device's ``hardware_type`` or other attributes.
    """

    def __init__(self, name: str, version: str, hardware_type: str):
        super().__init__(name, version, hardware_type)

    def can_bind(self, device: Device) -> bool:
        """Return ``True`` if this driver can manage the given device.

        The default implementation matches the driver's ``hardware_type`` with the
        device's ``hardware_type``. Sub‑classes may provide more sophisticated checks.
        """
        return device.hardware_type == self.hardware_type

    def bind(self, device: Device) -> None:
        """Bind the driver to the device and invoke ``probe``."""
        super().bind(device)
        self.probe(device)

    def probe(self, device: Device) -> None:
        """Driver‑specific initialization. Must be overridden by subclasses."""
        raise NotImplementedError(f"{self.__class__.__name__}.probe must be implemented")

    def remove(self, device: Device) -> None:
        """Optional clean‑up when the device is removed."""
        # Default implementation does nothing.
        pass
