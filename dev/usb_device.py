"""
UmerOS /dev/bus/usb — USB device nodes.

FHS 3.0 /dev/bus/usb:
  /dev/bus/usb/ — USB device directory.
  /dev/bus/usb/NNN/DDD — USB device at bus NNN, device DDD.

USB major:minor: 189:0 through 189:255

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.UsbDevice")


class UsbDevice:
    """USB device manager — /dev/bus/usb/.

    Provides:
      /dev/bus/usb/ — USB device directory
      /dev/bus/usb/001/001, etc. — USB device nodes
    """

    USB_MAJOR = 189
    MAX_BUS = 4
    MAX_DEV = 16

    def __init__(self):
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._register_directories()
        self._register_default_devices()
        log.info("UsbDevice created")

    def _register_directories(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="bus", path="/dev/bus", dev_type=DeviceType.DIRECTORY,
            description="Bus devices",
        ))
        mgr.create_node(DeviceNode(
            name="usb", path="/dev/bus/usb", dev_type=DeviceType.DIRECTORY,
            description="USB devices",
        ))

    def _register_default_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for bus in range(1, self.MAX_BUS + 1):
            bus_path = f"/dev/bus/usb/{bus:03d}"
            mgr.create_node(DeviceNode(
                name=str(bus), path=bus_path, dev_type=DeviceType.DIRECTORY,
                description=f"USB bus {bus}",
            ))
            for dev in range(1, self.MAX_DEV + 1):
                minor = (bus - 1) * self.MAX_DEV + dev - 1
                dev_path = f"{bus_path}/{dev:03d}"
                mgr.create_node(DeviceNode(
                    name=str(dev), path=dev_path, dev_type=DeviceType.CHAR,
                    major=self.USB_MAJOR, minor=minor, mode=0o664,
                    description=f"USB device {bus:03d}:{dev:03d}",
                ))
                self._devices[dev_path] = {
                    "bus": bus, "device": dev, "minor": minor,
                    "vendor": "0000", "product": "0000",
                }

    def add_device(self, bus: int, device: int, vendor: str = "0000",
                   product: str = "0000") -> bool:
        """Register a new USB device."""
        path = f"/dev/bus/usb/{bus:03d}/{device:03d}"
        if path in self._devices:
            return False
        mgr = DeviceManager.get_instance()
        minor = (bus - 1) * self.MAX_DEV + device - 1
        node = DeviceNode(
            name=str(device), path=path, dev_type=DeviceType.CHAR,
            major=self.USB_MAJOR, minor=minor, mode=0o664,
            description=f"USB device {bus:03d}:{device:03d}",
        )
        if mgr.create_node(node):
            self._devices[path] = {
                "bus": bus, "device": device, "minor": minor,
                "vendor": vendor, "product": product,
            }
            log.info("USB device added: %s", path)
            return True
        return False

    def remove_device(self, bus: int, device: int) -> bool:
        path = f"/dev/bus/usb/{bus:03d}/{device:03d}"
        if path not in self._devices:
            return False
        mgr = DeviceManager.get_instance()
        mgr.remove_node(path)
        del self._devices[path]
        return True

    def list_devices(self) -> List[Dict[str, Any]]:
        return list(self._devices.values())

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/bus/usb",
            "max_bus": self.MAX_BUS,
            "max_dev": self.MAX_DEV,
            "device_count": len(self._devices),
        }

    def __repr__(self) -> str:
        return f"<UsbDevice devices={len(self._devices)}>"
