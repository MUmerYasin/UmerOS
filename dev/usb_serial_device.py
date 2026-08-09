"""
UmerOS /dev — USB serial devices.

Linux USB serial device files:
  /dev/ttyUSB0-7  — USB-serial adapters (CP210x, FTDI, Prolific)
  /dev/ttyACM0-7  — USB CDC ACM (Arduino, modems, phones)

Major 188: ttyUSB0 = 188:0, ttyACM0 = 188:0 (same major, different naming)

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any, Dict, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.UsbSerialDevice")


class USBSerialDevice:
    """USB serial devices — /dev/ttyUSB* and /dev/ttyACM*.

    Manages USB-serial adapter device nodes:
      /dev/ttyUSB0-7  — Generic USB-serial (CP210x, FTDI, Prolific PL2303)
      /dev/ttyACM0-7  — USB CDC ACM (Arduino, 3G/4G modems, Android)

    Major 188 (USB-serial):
      ttyUSB0 = 188:0, ttyUSB1 = 188:1, ...
      ttyACM0 = 188:0 (shared numbering via separate naming)
    """

    USB_SERIAL_MAJOR = 188
    MAX_TTY_USB = 8
    MAX_TTY_ACM = 8

    def __init__(self):
        self._buffers: Dict[str, deque] = {}
        self._create_devices()
        log.info("USBSerialDevice created (%d ttyUSB, %d ttyACM)",
                 self.MAX_TTY_USB, self.MAX_TTY_ACM)

    def _create_devices(self) -> None:
        mgr = DeviceManager.get_instance()

        # /dev/ttyUSB0-7
        for i in range(self.MAX_TTY_USB):
            minor = i
            name = f"ttyUSB{i}"
            path = f"/dev/{name}"
            mgr.create_node(DeviceNode(
                name=name, path=path, dev_type=DeviceType.CHAR,
                major=self.USB_SERIAL_MAJOR, minor=minor,
                mode=0o660,
                description=f"USB-serial adapter {i} (CP210x/FTDI/PL2303)",
                read_callback=lambda size, n=name: self._on_read(n, size),
                write_callback=lambda data, n=name: self._on_write(n, data),
            ))
            self._buffers[name] = deque(maxlen=1024)

        # /dev/ttyACM0-7
        for i in range(self.MAX_TTY_ACM):
            minor = i
            name = f"ttyACM{i}"
            path = f"/dev/{name}"
            mgr.create_node(DeviceNode(
                name=name, path=path, dev_type=DeviceType.CHAR,
                major=self.USB_SERIAL_MAJOR, minor=minor,
                mode=0o660,
                description=f"USB CDC ACM device {i} (Arduino/modem)",
                read_callback=lambda size, n=name: self._on_read(n, size),
                write_callback=lambda data, n=name: self._on_write(n, data),
            ))
            self._buffers[name] = deque(maxlen=1024)

    def _on_read(self, device: str, size: int) -> bytes:
        buf = self._buffers.get(device, deque())
        data = b""
        while buf and len(data) < size:
            data += buf.popleft()
        return data

    def _on_write(self, device: str, data: bytes) -> int:
        buf = self._buffers.setdefault(device, deque(maxlen=1024))
        buf.append(data)
        return len(data)

    def inject_data(self, device: str, data: bytes) -> None:
        """Inject data into a USB serial device's read buffer."""
        buf = self._buffers.setdefault(device, deque(maxlen=1024))
        buf.append(data)
        log.debug("Injected %d bytes into %s", len(data), device)

    def get_info(self) -> Dict[str, Any]:
        return {
            "major": self.USB_SERIAL_MAJOR,
            "ttyUSB_count": self.MAX_TTY_USB,
            "ttyACM_count": self.MAX_TTY_ACM,
            "total_devices": self.MAX_TTY_USB + self.MAX_TTY_ACM,
        }

    def __repr__(self) -> str:
        return f"<USBSerialDevice ttyUSB={self.MAX_TTY_USB} ttyACM={self.MAX_TTY_ACM}>"
