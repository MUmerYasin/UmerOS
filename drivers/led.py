"""
UmerOS LED Subsystem
=====================
Kernel-like LED subsystem for LED management.
Implements LED devices, triggers, and brightness control.

Reference: drivers/leds/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# LED Constants
# ============================================================================

LED_SUCCESS: int = 0
LED_ERROR: int = 1
LED_NOT_FOUND: int = 2
LED_BUSY: int = 3

LED_MAX_DEVICES: int = 64
LED_MAX_BRIGHTNESS: int = 255


class LEDState(IntEnum):
    """LED state."""
    OFF: int = 0
    ON: int = 1
    BLINK: int = 2
    BREATH: int = 3


class LEDTrigger(IntEnum):
    """LED trigger types."""
    NONE: int = 0
    HEARTBEAT: int = 1
    DISK: int = 2
    CPU: int = 3
    NETDEV: int = 4
    TIMER: int = 5
    ONESHOT: int = 6
    BACKLIGHT: int = 7
    DEFAULT_ON: int = 8


class LEDColor(IntEnum):
    """LED color types."""
    UNKNOWN: int = 0
    RED: int = 1
    GREEN: int = 2
    BLUE: int = 3
    AMBER: int = 4
    WHITE: int = 5
    RGB: int = 6


# ============================================================================
# LED Device
# ============================================================================

@dataclass
class LEDDevice:
    """LED device (mirrors struct led_classdev)."""
    name: str
    index: int
    brightness: int = 0
    max_brightness: int = LED_MAX_BRIGHTNESS
    state: LEDState = LEDState.OFF
    trigger: LEDTrigger = LEDTrigger.NONE
    color: LEDColor = LEDColor.UNKNOWN
    default_state: LEDState = LEDState.OFF
    blink_delay_on: int = 500
    blink_delay_off: int = 500
    brightness_set: Optional[Callable] = field(default=None, repr=False)
    blink_set: Optional[Callable] = field(default=None, repr=False)
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def set_brightness(self, value: int) -> int:
        if value < 0 or value > self.max_brightness:
            return LED_ERROR
        self.brightness = value
        self.state = LEDState.ON if value > 0 else LEDState.OFF
        if self.brightness_set:
            self.brightness_set(self, value)
        self._notify("brightness")
        return LED_SUCCESS

    def get_brightness(self) -> int:
        return self.brightness

    def set_state(self, state: LEDState) -> int:
        self.state = state
        if state == LEDState.OFF:
            self.brightness = 0
        elif state == LEDState.ON:
            self.brightness = self.max_brightness
        self._notify("state")
        return LED_SUCCESS

    def blink(self, delay_on: int, delay_off: int) -> int:
        self.state = LEDState.BLINK
        self.blink_delay_on = delay_on
        self.blink_delay_off = delay_off
        if self.blink_set:
            self.blink_set(self, delay_on, delay_off)
        self._notify("blink")
        return LED_SUCCESS

    def breathe(self) -> int:
        self.state = LEDState.BREATH
        self._notify("breathe")
        return LED_SUCCESS

    def set_trigger(self, trigger: LEDTrigger) -> int:
        self.trigger = trigger
        self._notify("trigger")
        return LED_SUCCESS

    def set_color(self, color: LEDColor) -> int:
        self.color = color
        return LED_SUCCESS

    def register_ops(self, ops: Dict[str, Callable]) -> None:
        self._ops.update(ops)

    def set_callback(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify(self, event: str) -> None:
        for cb in self._listeners:
            cb(self.name, event)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "brightness": self.brightness,
            "max_brightness": self.max_brightness,
            "state": self.state.name,
            "trigger": self.trigger.name,
            "color": self.color.name,
        }


# ============================================================================
# LED Subsystem
# ============================================================================

class LEDSubsystem:
    """Central LED subsystem managing LED devices."""

    def __init__(self) -> None:
        self._devices: Dict[str, LEDDevice] = {}
        self._next_index: int = 0

    def register_device(self, device: LEDDevice) -> int:
        device.index = self._next_index
        device.registered = True
        self._devices[device.name] = device
        self._next_index += 1
        return LED_SUCCESS

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return LED_SUCCESS

    def get_device(self, name: str) -> Optional[LEDDevice]:
        return self._devices.get(name)

    def enumerate_devices(self) -> List[LEDDevice]:
        return list(self._devices.values())

    def set_brightness_all(self, value: int) -> int:
        for dev in self._devices.values():
            dev.set_brightness(value)
        return LED_SUCCESS

    def trigger_all(self, state: LEDState) -> int:
        for dev in self._devices.values():
            dev.set_state(state)
        return LED_SUCCESS

    def get_topology(self) -> Dict[str, Any]:
        return {
            "devices": len(self._devices),
            "device_names": list(self._devices.keys()),
        }


# ============================================================================
# Global LED Instance
# ============================================================================

_global_led: Optional[LEDSubsystem] = None


def get_global_led() -> LEDSubsystem:
    global _global_led
    if _global_led is None:
        _global_led = LEDSubsystem()
    return _global_led


def register_led_device(device: LEDDevice) -> int:
    return get_global_led().register_device(device)


def led_set_brightness(name: str, value: int) -> int:
    dev = get_global_led().get_device(name)
    return dev.set_brightness(value) if dev else LED_ERROR


def led_set_state(name: str, state: LEDState) -> int:
    dev = get_global_led().get_device(name)
    return dev.set_state(state) if dev else LED_ERROR
