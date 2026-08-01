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
