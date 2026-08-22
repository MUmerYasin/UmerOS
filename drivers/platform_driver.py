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
