"""
UmerOS /dev — Parallel port devices.

Linux parallel port device files:
  /dev/lp0-2      — Parallel printer devices
  /dev/parport0-2 — Parallel port control

Major 6: lp0 = 6:0, lp1 = 6:1, lp2 = 6:2
Major 99: parport0 = 99:0, parport1 = 99:1, ...

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.ParallelDevice")


class ParallelDevice:
    """Parallel port devices — /dev/lp*, /dev/parport*.

    Legacy IEEE 1284 parallel port interface:
      /dev/lp0-2      — Printer device (write-only)
      /dev/parport0-2 — Port control (ioctl for mode setting)

    Major 6:  lp0 = 6:0, lp1 = 6:1, lp2 = 6:2
    Major 99: parport0 = 99:0, parport1 = 99:1, ...

    Still used by:
      - Legacy printers
      - CNC machines
      - Industrial controllers
      - Some scientific instruments
    """

    LP_MAJOR = 6
    PARPORT_MAJOR = 99
    MAX_LP = 3
    MAX_PARPORT = 3

    # ioctl commands
    PPCLAIM = 0x40047085
    PPRELEASE = 0x40047086
    PPDATA = 0x40047080
    PPSTATUS = 0x40047081
    PPCONTROL = 0x40047082
    PPSETMODE = 0x40047083

    def __init__(self):
        self._buffers: Dict[str, bytes] = {}
        self._create_devices()
        log.info("ParallelDevice created (%d lp, %d parport)",
                 self.MAX_LP, self.MAX_PARPORT)

    def _create_devices(self) -> None:
        mgr = DeviceManager.get_instance()

        # /dev/lp0-2 (printer devices)
        for i in range(self.MAX_LP):
            name = f"lp{i}"
            path = f"/dev/{name}"
            mgr.create_node(DeviceNode(
                name=name, path=path, dev_type=DeviceType.CHAR,
                major=self.LP_MAJOR, minor=i,
                mode=0o660,
                description=f"Parallel printer {i}",
                write_callback=lambda data, n=name: self._on_write(n, data),
                ioctl_callback=lambda req, arg, n=name: self._on_ioctl(n, req, arg),
            ))
            self._buffers[name] = b""

        # /dev/parport0-2 (port control)
        for i in range(self.MAX_PARPORT):
            name = f"parport{i}"
            path = f"/dev/{name}"
            mgr.create_node(DeviceNode(
                name=name, path=path, dev_type=DeviceType.CHAR,
                major=self.PARPORT_MAJOR, minor=i,
                mode=0o660,
                description=f"Parallel port control {i}",
                ioctl_callback=lambda req, arg, n=name: self._on_ioctl(n, req, arg),
            ))

    def _on_write(self, device: str, data: bytes) -> int:
        """Write data to the parallel printer buffer."""
        self._buffers[device] = data
        return len(data)

    def _on_ioctl(self, device: str, request: int, arg: Any) -> int:
        """Handle parallel port ioctl commands."""
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {
            "lp_major": self.LP_MAJOR,
            "parport_major": self.PARPORT_MAJOR,
            "lp_count": self.MAX_LP,
            "parport_count": self.MAX_PARPORT,
        }

    def __repr__(self) -> str:
        return f"<ParallelDevice lp={self.MAX_LP} parport={self.MAX_PARPORT}>"
