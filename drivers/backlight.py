"""
UmerOS Backlight Subsystem
==========================
Kernel-like backlight framework.
Implements backlight device registration, brightness control,
power state management, and sysfs attributes.

Reference: drivers/video/backlight/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# Backlight Constants
# ============================================================================

BACKLIGHT_RAW: int = 1
BACKLIGHT_PLATFORM: int = 2
BACKLIGHT_FIRMWARE: int = 3

BACKLIGHT_POWER_ON: int = 0
BACKLIGHT_POWER_OFF: int = 1
BACKLIGHT_POWER_DIM: int = 2

BACKLIGHT_STATUS_OK: int = 0
BACKLIGHT_STATUS_ERROR: int = 1
BACKLIGHT_STATUS_NO_UPDATE: int = 2


class BacklightType(IntEnum):
    """Backlight device type."""
    RAW = BACKLIGHT_RAW
    PLATFORM = BACKLIGHT_PLATFORM
    FIRMWARE = BACKLIGHT_FIRMWARE


# ============================================================================
# Backlight Operations
# ============================================================================

@dataclass
class BacklightOps:
    """Backlight device operations (mirrors struct backlight_ops)."""
    get_brightness: Optional[Callable] = None
    update_status: Optional[Callable] = None


# ============================================================================
# Backlight Device
# ============================================================================

@dataclass
class BacklightDevice:
    """Backlight device (mirrors struct backlight_device).

    Controls display backlight brightness.
    """
    name: str
    index: int
    dev_type: BacklightType = BacklightType.PLATFORM
    max_brightness: int = 100
    brightness: int = 0
    power: int = BACKLIGHT_POWER_ON
    state: int = BACKLIGHT_STATUS_OK
    props: int = 0
    ops: BacklightOps = field(default_factory=BacklightOps)
    _users: int = 0
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    @property
    def actual_brightness(self) -> int:
        if self.ops.get_brightness:
            result = self.ops.get_brightness(self)
            if result is not None:
                return result
        return self.brightness

    def update_brightness(self, value: int) -> int:
        """Update backlight brightness."""
        self.brightness = max(0, min(value, self.max_brightness))
        if self.ops.update_status:
            return self.ops.update_status(self)
        self._notify_listeners()
        return 0

    def set_power(self, power_state: int) -> int:
        self.power = power_state
        return 0

    def register_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify_listeners(self) -> None:
        for cb in self._listeners:
            cb(self.name, self.brightness)

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.dev_type.name,
            "brightness": self.brightness,
            "actual_brightness": self.actual_brightness,
            "max_brightness": self.max_brightness,
            "power": self.power,
            "status": self.state,
        }


# ============================================================================
# Backlight Subsystem Manager
# ============================================================================

class BacklightSubsystem:
    """Central backlight subsystem managing display backlights."""

    def __init__(self) -> None:
        self._devices: Dict[str, BacklightDevice] = {}
        self._next_index: int = 0

    def register_device(self, device: BacklightDevice) -> int:
        device.index = self._next_index
        self._devices[device.name] = device
        self._next_index += 1
        return device.index

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return 0

    def get_device(self, name: str) -> Optional[BacklightDevice]:
        return self._devices.get(name)

    def enumerate_devices(self) -> List[BacklightDevice]:
        return list(self._devices.values())

    def set_brightness(self, name: str, value: int) -> int:
        device = self._devices.get(name)
        return device.update_brightness(value) if device else -1

    def get_brightness(self, name: str) -> Optional[int]:
        device = self._devices.get(name)
        return device.actual_brightness if device else None

    def set_power(self, name: str, power_state: int) -> int:
        device = self._devices.get(name)
        return device.set_power(power_state) if device else -1

    def get_all_status(self) -> List[Dict[str, Any]]:
        return [d.get_status() for d in self._devices.values()]


# ============================================================================
# Global Backlight Instance
# ============================================================================

_global_backlight: Optional[BacklightSubsystem] = None


def get_global_backlight() -> BacklightSubsystem:
    global _global_backlight
    if _global_backlight is None:
        _global_backlight = BacklightSubsystem()
    return _global_backlight


def register_backlight_device(device: BacklightDevice) -> int:
    return get_global_backlight().register_device(device)


def set_backlight_brightness(name: str, value: int) -> int:
    return get_global_backlight().set_brightness(name, value)
