"""
UmerOS /dev — HID raw devices.

HID raw device files:
  /dev/hidraw0-15 — Raw HID access (gamepads, keyboards, special devices)

Major 246: hidraw0 = 246:0, hidraw1 = 246:1, ...

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any, Dict, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.HidrawDevice")


class HidrawDevice:
    """HID raw devices — /dev/hidraw*.

    Provides raw access to HID devices without going through
    the input subsystem. Used for gamepads, special keyboards,
    and vendor-specific HID reports.

    Major 246: hidraw0 = 246:0, hidraw1 = 246:1, ...
    """

    HIDRAW_MAJOR = 246
    MAX_DEVICES = 16

    def __init__(self):
        self._buffers: Dict[str, deque] = {}
        self._device_info: Dict[str, Dict[str, Any]] = {}
        self._create_devices()
        log.info("HidrawDevice created (%d devices)", self.MAX_DEVICES)

    def _create_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_DEVICES):
            name = f"hidraw{i}"
            path = f"/dev/{name}"
            mgr.create_node(DeviceNode(
                name=name, path=path, dev_type=DeviceType.CHAR,
                major=self.HIDRAW_MAJOR, minor=i,
                mode=0o660,
                description=f"HID raw device {i}",
                read_callback=lambda size, n=name: self._on_read(n, size),
                write_callback=lambda data, n=name: self._on_write(n, data),
                ioctl_callback=lambda req, arg, n=name: self._on_ioctl(n, req, arg),
            ))
            self._buffers[name] = deque(maxlen=2048)
            self._device_info[name] = {
                "bus": 0, "vendor": 0, "product": 0,
                "name": "", "phys": "",
            }

    def _on_read(self, device: str, size: int) -> bytes:
        buf = self._buffers.get(device, deque())
        data = b""
        while buf and len(data) < size:
            data += buf.popleft()
        return data

    def _on_write(self, device: str, data: bytes) -> int:
        return len(data)

    def _on_ioctl(self, device: str, request: int, arg: Any) -> int:
        """Handle HIDRAW ioctl commands."""
        # HIDRAWIoctl ioctl numbers
        HIDRAW_GET_REPORT = 0xC0484801
        HIDRAW_SET_REPORT = 0x40484802
        HIDRAW_GET_FEATURE = 0xC0484807
        HIDRAW_SET_FEATURE = 0x40484806
        return 0

    def inject_data(self, device: str, data: bytes) -> None:
        """Inject HID report data into a device's read buffer."""
        buf = self._buffers.setdefault(device, deque(maxlen=2048))
        buf.append(data)
        log.debug("Injected %d bytes into %s", len(data), device)

    def set_device_info(self, device: str, bus: int = 0, vendor: int = 0,
                        product: int = 0, name: str = "", phys: str = "") -> None:
        """Set device identification info (for HIDRAWGETINFO ioctl)."""
        if device in self._device_info:
            self._device_info[device] = {
                "bus": bus, "vendor": vendor, "product": product,
                "name": name, "phys": phys,
            }

    def get_info(self) -> Dict[str, Any]:
        return {
            "major": self.HIDRAW_MAJOR,
            "max_devices": self.MAX_DEVICES,
        }

    def __repr__(self) -> str:
        return f"<HidrawDevice devices={self.MAX_DEVICES}>"
