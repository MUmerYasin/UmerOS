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
Umer OS Device Tree Helper

Provides a very simple API to register platform devices using a compatible string list.
"""

from .device import Device
from .bus import BUS_REGISTRY


def register_platform_device(name: str, hardware_type: str, compatible: list, bus_name: str = "platform"):
    """Create a Device with compatible strings and register it on the given bus.

    Args:
        name: Human readable name of the device.
        hardware_type: Type identifier used by drivers (e.g., "gpio", "i2c").
        compatible: List of compatible strings (e.g., ["vendor,device"]).
        bus_name: Name of the bus to attach the device to (defaults to "platform").
    """
    bus = BUS_REGISTRY.get(bus_name)
    if bus is None:
        raise ValueError(f"Bus '{bus_name}' not found. Ensure it is created before registering devices.")
    dev = Device(name=name, hardware_type=hardware_type, bus=bus, compatible=compatible)
    print(f"[DEVICETREE] Registered platform device '{name}' on bus '{bus_name}' with compatible {compatible}")
    return dev
