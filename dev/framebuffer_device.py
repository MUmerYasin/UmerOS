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

"""
UmerOS /dev — Framebuffer devices.

Framebuffer device files:
  /dev/fb0-31 — Framebuffer display devices

Major 29: fb0 = 29:0, fb1 = 29:32, fb2 = 29:64, ...

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.FramebufferDevice")


class FramebufferDevice:
    """Framebuffer devices — /dev/fb*.

    Legacy framebuffer interface for display output.
    Predates DRM/KMS but still used by:
      - Embedded systems without DRM
      - Boot splash screens (Plymouth)
      - Legacy X11 drivers (fbdev)
      - Console rendering (fbcon)

    Major 29: fb0 = 29:0, fb1 = 29:32, fb2 = 29:64, ...
    Minor encoding: (index * 32) + channel
    """

    FB_MAJOR = 29
    MAX_DEVICES = 8
    MINORS_PER_DEVICE = 32

    # ioctl commands
    FBIOGET_VSCREENINFO = 0x4600
    FBIOPUT_VSCREENINFO = 0x4601
    FBIOGET_FSCREENINFO = 0x4602
    FBIOBLANK = 0x4611

    def __init__(self):
        self._device_info: Dict[str, Dict[str, Any]] = {}
        self._create_devices()
        log.info("FramebufferDevice created (%d devices)", self.MAX_DEVICES)

    def _create_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_DEVICES):
            name = f"fb{i}"
            path = f"/dev/{name}"
            minor = i * self.MINORS_PER_DEVICE
            mgr.create_node(DeviceNode(
                name=name, path=path, dev_type=DeviceType.CHAR,
                major=self.FB_MAJOR, minor=minor,
                mode=0o660,
                description=f"Framebuffer display {i}",
                ioctl_callback=lambda req, arg, n=name: self._on_ioctl(n, req, arg),
            ))
            self._device_info[name] = {
                "xres": 1920, "yres": 1080,
                "bpp": 32, "stride": 7680,
                "type": 0, "visual": 2,
                "line_length": 7680,
            }

    def _on_ioctl(self, device: str, request: int, arg: Any) -> int:
        """Handle framebuffer ioctl commands."""
        if request == self.FBIOGET_VSCREENINFO:
            return 0
        elif request == self.FBIOPUT_VSCREENINFO:
            return 0
        elif request == self.FBIOGET_FSCREENINFO:
            return 0
        elif request == self.FBIOBLANK:
            return 0
        return 0

    def set_resolution(self, device: str, xres: int, yres: int, bpp: int = 32) -> None:
        """Set framebuffer resolution."""
        if device in self._device_info:
            self._device_info[device]["xres"] = xres
            self._device_info[device]["yres"] = yres
            self._device_info[device]["bpp"] = bpp
            self._device_info[device]["stride"] = xres * (bpp // 8)
            log.debug("Set %s resolution: %dx%d@%d", device, xres, yres, bpp)

    def get_info(self) -> Dict[str, Any]:
        return {
            "major": self.FB_MAJOR,
            "max_devices": self.MAX_DEVICES,
            "minors_per_device": self.MINORS_PER_DEVICE,
        }

    def __repr__(self) -> str:
        return f"<FramebufferDevice devices={self.MAX_DEVICES}>"
