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
UmerOS Framebuffer Subsystem
============================
Kernel-like framebuffer and DRM (Direct Rendering Manager)
interface for display output management.

Reference: Documentation/driver-api/fbdev/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# Framebuffer Constants
# ============================================================================

FBIOGET_VSCREENINFO: int = 0x4600
FBIOPUT_VSCREENINFO: int = 0x4601
FBIOGET_FSCREENINFO: int = 0x4602
FBIOGETCMAP: int = 0x4604
FBIOPUTCMAP: int = 0x4605
FBIOBLANK: int = 0x4611

FB_BLANK_UNBLANK: int = 0
FB_BLANK_NORMAL: int = 1
FB_BLANK_VSYNC_SUSPEND: int = 2
FB_BLANK_HSYNC_SUSPEND: int = 3
FB_BLANK_POWERDOWN: int = 4


class FBPixelFmt(IntEnum):
    """Framebuffer pixel format."""
    RGB565 = 0
    RGB888 = 1
    BGR888 = 2
    RGBA8888 = 3
    ARGB8888 = 4


# ============================================================================
# Framebuffer Video Mode
# ============================================================================

@dataclass
class FBVideoMode:
    """Framebuffer video mode (mirrors struct fb_var_screeninfo)."""
    xres: int = 640
    yres: int = 480
    xres_virtual: int = 640
    yres_virtual: int = 480
    bits_per_pixel: int = 32
    pixel_format: FBPixelFmt = FBPixelFmt.RGBA8888
    hsync_len: int = 96
    vsync_len: int = 2
    left_margin: int = 48
    right_margin: int = 16
    upper_margin: int = 33
    lower_margin: int = 10
    pixclock: int = 0
    width: int = 0
    height: int = 0

    @property
    def stride(self) -> int:
        return self.xres * (self.bits_per_pixel // 8)

    @property
    def buffer_size(self) -> int:
        return self.stride * self.yres


@dataclass
class FBFixScreeninfo:
    """Framebuffer fixed info (mirrors struct fb_fix_screeninfo)."""
    id: str = "UmerOS-FB"
    smem_start: int = 0
    smem_len: int = 0
    line_length: int = 0
    accel: int = 0
    capabilities: int = 0


# ============================================================================
# Framebuffer Device
# ============================================================================

@dataclass
class FBDevice:
    """Framebuffer device (mirrors struct fb_info / struct fb_deferred_open).

    Manages a display output with pixel buffer and control.
    """
    name: str
    index: int
    var_info: FBVideoMode = field(default_factory=FBVideoMode)
    fix_info: FBFixScreeninfo = field(default_factory=FBFixScreeninfo)
    buffer: bytearray = field(default_factory=bytearray)
    cmap: List[int] = field(default_factory=list)
    blank: int = FB_BLANK_UNBLANK
    state: int = 0
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._init_buffer()

    def _init_buffer(self) -> None:
        size = self.var_info.buffer_size
        if len(self.buffer) != size:
            self.buffer = bytearray(size)
        self.fix_info.line_length = self.var_info.stride
        self.fix_info.smem_len = size

    def set_mode(self, mode: FBVideoMode) -> int:
        """Set video mode."""
        self.var_info = mode
        self._init_buffer()
        self._notify("mode_changed")
        return 0

    def set_pixel(self, x: int, y: int, color: int) -> int:
        """Set a single pixel."""
        if x < 0 or x >= self.var_info.xres or y < 0 or y >= self.var_info.yres:
            return -1
        bpp = self.var_info.bits_per_pixel // 8
        offset = (y * self.var_info.xres + x) * bpp
        if offset + bpp > len(self.buffer):
            return -1
        for i in range(bpp):
            self.buffer[offset + i] = (color >> (i * 8)) & 0xFF
        return 0

    def get_pixel(self, x: int, y: int) -> int:
        if x < 0 or x >= self.var_info.xres or y < 0 or y >= self.var_info.yres:
            return 0
        bpp = self.var_info.bits_per_pixel // 8
        offset = (y * self.var_info.xres + x) * bpp
        color = 0
        for i in range(bpp):
            color |= self.buffer[offset + i] << (i * 8)
        return color

    def clear(self, color: int = 0) -> None:
        self.buffer[:] = bytearray(len(self.buffer))
        if color:
            bpp = self.var_info.bits_per_pixel // 8
            for i in range(0, len(self.buffer), bpp):
                for j in range(bpp):
                    self.buffer[i + j] = (color >> (j * 8)) & 0xFF

    def fill_rect(self, x: int, y: int, w: int, h: int, color: int) -> int:
        for dy in range(h):
            for dx in range(w):
                self.set_pixel(x + dx, y + dy, color)
        return 0

    def blank_screen(self, blank_mode: int) -> int:
        self.blank = blank_mode
        self._notify("blank")
        return 0

    def register_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify(self, event: str) -> None:
        for cb in self._listeners:
            cb(self.name, event)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "resolution": f"{self.var_info.xres}x{self.var_info.yres}",
            "bpp": self.var_info.bits_per_pixel,
            "blank": self.blank,
            "buffer_size": len(self.buffer),
        }


# ============================================================================
# Framebuffer Subsystem Manager
# ============================================================================

class FramebufferSubsystem:
    """Central framebuffer subsystem managing display devices."""

    def __init__(self) -> None:
        self._devices: Dict[str, FBDevice] = {}
        self._next_index: int = 0

    def register_device(self, device: FBDevice) -> int:
        device.index = self._next_index
        device.registered = True
        self._devices[device.name] = device
        self._next_index += 1
        return 0

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return 0

    def get_device(self, name: str) -> Optional[FBDevice]:
        return self._devices.get(name)

    def enumerate_devices(self) -> List[FBDevice]:
        return list(self._devices.values())

    def set_mode(self, name: str, mode: FBVideoMode) -> int:
        device = self._devices.get(name)
        return device.set_mode(mode) if device else -1

    def blank(self, name: str, blank_mode: int) -> int:
        device = self._devices.get(name)
        return device.blank_screen(blank_mode) if device else -1


# ============================================================================
# Global Framebuffer Instance
# ============================================================================

_global_fb: Optional[FramebufferSubsystem] = None


def get_global_framebuffer() -> FramebufferSubsystem:
    global _global_fb
    if _global_fb is None:
        _global_fb = FramebufferSubsystem()
    return _global_fb


def register_framebuffer(device: FBDevice) -> int:
    return get_global_framebuffer().register_device(device)


def fb_set_pixel(device_name: str, x: int, y: int, color: int) -> int:
    device = get_global_framebuffer().get_device(device_name)
    return device.set_pixel(x, y, color) if device else -1
