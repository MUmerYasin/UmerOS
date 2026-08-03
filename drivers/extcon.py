"""
UmerOS Extcon Subsystem
=======================
Linux kernel-like External Connector (extcon) framework.
Implements connector state tracking, cable detection,
and state change notifications for USB, audio, and power connectors.

Reference: drivers/extcon/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntFlag, auto
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# Extcon Cable Types (mirrors extcon.h)
# ============================================================================

EXTCON_USB: int = 0
EXTCON_USB_HOST: int = 1
EXTCON_DP: int = 2
EXTCON_USB_VBUS: int = 3
EXTCON_USB_CC1: int = 4
EXTCON_USB_CC2: int = 5
EXTCON_AUDIO_HEADPHONE: int = 6
EXTCON_AUDIO_MICROPHONE: int = 7
EXTCON_JACK_NO_DEVICE: int = 8
EXTCON_JACK_HEADPHONE: int = 9
EXTCON_JACK_MICROPHONE: int = 10
EXTCON_JACKdıklar_IN: int = 11
EXTCON_JACK_OUT: int = 12
EXTCON_CHG_USB_SDP: int = 13
EXTCON_CHG_USB_CDP: int = 14
EXTCON_CHG_USB_DCP: int = 15
EXTCON_CHG_USB_PD: int = 16
EXTCON_CHG_USB_FAST: int = 17
EXTCON_CHG_USB_FLOAT: int = 18
EXTCON_PTP_USB: int = 19

NUM_EXTCON_CABLES: int = 32


# ============================================================================
# Extcon Cable
# ============================================================================

@dataclass
class ExtconCable:
    """Single cable/connector state entry."""
    name: str
    cable_id: int
    state: bool = False
    _callbacks: List[Callable] = field(default_factory=list, repr=False)

    def set_state(self, state: bool) -> None:
        if self.state != state:
            self.state = state
            for cb in self._callbacks:
                cb(self.cable_id, state)

    def register_callback(self, callback: Callable) -> None:
        self._callbacks.append(callback)


# ============================================================================
# Extcon Device
# ============================================================================

@dataclass
class ExtconDevice:
    """Extcon device (mirrors struct extcon_dev).

    Represents a physical connector capable of detecting
    one or more cable states.
    """
    name: str
    dev_type: str = "extcon"
    cables: List[ExtconCable] = field(default_factory=list)
    _state: int = 0
    _notifiers: List[Callable] = field(default_factory=list, repr=False)

    def get_cable(self, cable_id: int) -> Optional[ExtconCable]:
        for c in self.cables:
            if c.cable_id == cable_id:
                return c
        return None

    def set_cable_state(self, cable_id: int, state: bool) -> None:
        """Set cable state and notify listeners."""
        cable = self.get_cable(cable_id)
        if cable:
            cable.set_state(state)
            if state:
                self._state |= (1 << cable_id)
            else:
                self._state &= ~(1 << cable_id)
            self._notify(cable_id, state)

    def get_state(self) -> int:
        return self._state

    def get_state_bit(self, cable_id: int) -> bool:
        return bool(self._state & (1 << cable_id))

    def register_notifier(self, callback: Callable) -> None:
        self._notifiers.append(callback)

    def _notify(self, cable_id: int, state: bool) -> None:
        for cb in self._notifiers:
            cb(self.name, cable_id, state)


# ============================================================================
# Extcon Driver
# ============================================================================

@dataclass
class ExtconDriver:
    """Extcon driver for handling cable events."""
    name: str
    callbacks: Dict[int, Callable] = field(default_factory=dict)

    def event_handler(self, device: ExtconDevice, cable_id: int, state: bool) -> None:
        if cable_id in self.callbacks:
            self.callbacks[cable_id](device, cable_id, state)


# ============================================================================
# Extcon Subsystem Manager
# ============================================================================

class ExtconSubsystem:
    """Central extcon subsystem managing devices and cable state."""

    def __init__(self) -> None:
        self._devices: Dict[str, ExtconDevice] = {}
        self._drivers: List[ExtconDriver] = []
        self._state_listeners: List[Callable] = []

    def register_device(self, device: ExtconDevice) -> int:
        self._devices[device.name] = device
        device.register_notifier(self._on_state_change)
        return 0

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return 0

    def get_device(self, name: str) -> Optional[ExtconDevice]:
        return self._devices.get(name)

    def register_driver(self, driver: ExtconDriver) -> int:
        self._drivers.append(driver)
        return 0

    def set_cable_state(self, device_name: str, cable_id: int, state: bool) -> int:
        device = self._devices.get(device_name)
        if not device:
            return -1
        device.set_cable_state(cable_id, state)
        return 0

    def get_cable_state(self, device_name: str, cable_id: int) -> Optional[bool]:
        device = self._devices.get(device_name)
        if not device:
            return None
        return device.get_state_bit(cable_id)

    def get_all_states(self, device_name: str) -> Optional[int]:
        device = self._devices.get(device_name)
        return device.get_state() if device else None

    def register_state_listener(self, callback: Callable) -> None:
        self._state_listeners.append(callback)

    def _on_state_change(self, device_name: str, cable_id: int, state: bool) -> None:
        for listener in self._state_listeners:
            listener(device_name, cable_id, state)
        for driver in self._drivers:
            device = self._devices.get(device_name)
            if device:
                driver.event_handler(device, cable_id, state)

    def find_device_by_cable(self, cable_id: int, state: bool) -> List[ExtconDevice]:
        """Find all devices with a given cable in a given state."""
        result = []
        for dev in self._devices.values():
            if dev.get_state_bit(cable_id) == state:
                result.append(dev)
        return result


# ============================================================================
# Global Extcon Instance
# ============================================================================

_global_extcon: Optional[ExtconSubsystem] = None


def get_global_extcon() -> ExtconSubsystem:
    global _global_extcon
    if _global_extcon is None:
        _global_extcon = ExtconSubsystem()
    return _global_extcon


def register_extcon_device(device: ExtconDevice) -> int:
    return get_global_extcon().register_device(device)


def set_extcon_cable(device_name: str, cable_id: int, state: bool) -> int:
    return get_global_extcon().set_cable_state(device_name, cable_id, state)
