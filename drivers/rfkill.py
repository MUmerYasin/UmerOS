"""
UmerOS Rfkill Subsystem
=======================
Kernel-like rfkill (radio frequency kill) framework.
Implements wireless transmitter kill switches for WiFi, Bluetooth,
WWAN, and other RF devices.

Reference: net/rfkill/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# Rfkill Constants
# ============================================================================

RFKILL_STATE_SOFT_BLOCKED: int = 0
RFKILL_STATE_UNBLOCKED: int = 1

RFKILL_OP_ADD: int = 0
RFKILL_OP_DEL: int = 1
RFKILL_OP_CHANGE: int = 2
RFKILL_OP_CHANGE_ALL: int = 3

RFKILL_CMD_MAX: int = 6


class RfkillType(IntEnum):
    """Rfkill device types (mirrors enum rfkill_type)."""
    WLAN = 0
    BLUETOOTH = 1
    UWB = 2
    WIMAX = 3
    WWAN = 4
    GPS = 5
    FM = 6
    NFC = 7
    AIRPLANE = 8
    RFKILL_ALL = 9  # wildcard
    MAX = 10


# ============================================================================
# Rfkill Device
# ============================================================================

@dataclass
class RfkillDevice:
    """Represents an rfkill-controlled wireless transmitter.

    Mirrors struct rfkill_dev / struct rfkill.
    """
    name: str
    index: int
    rf_type: RfkillType
    soft_block: bool = False
    hard_block: bool = False
    claim_read: bool = False
    registered: bool = False
    persistent: bool = False
    _callbacks: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    @property
    def blocked(self) -> bool:
        return self.soft_block or self.hard_block

    def soft_block_set(self, blocked: bool) -> int:
        """Set soft block state."""
        if self.hard_block:
            return -1  # hard block overrides
        self.soft_block = blocked
        self._emit_change()
        return 0

    def hard_block_set(self, blocked: bool) -> int:
        """Set hard block state (hardware switch)."""
        self.hard_block = blocked
        self._emit_change()
        return 0

    def _emit_change(self) -> None:
        for cb in self._listeners:
            cb(self)

    def register_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)


# ============================================================================
# Rfkill Switch (Platform-level kill switch)
# ============================================================================

@dataclass
class RfkillSwitch:
    """Platform rfkill switch (mirrors struct rfkill_ops)."""
    name: str
    rf_type: RfkillType
    block_cb: Optional[Callable] = None  # called to block
    unblock_cb: Optional[Callable] = None  # called to unblock
    data: Any = None

    def block(self) -> int:
        if self.block_cb:
            return self.block_cb(self.data)
        return 0

    def unblock(self) -> int:
        if self.unblock_cb:
            return self.unblock_cb(self.data)
        return 0


# ============================================================================
# Rfkill Subsystem Manager
# ============================================================================

class RfkillSubsystem:
    """Central rfkill subsystem managing wireless kill switches."""

    def __init__(self) -> None:
        self._devices: Dict[int, RfkillDevice] = {}
        self._switches: List[RfkillSwitch] = []
        self._next_index: int = 0
        self._global_listeners: List[Callable] = []

    def register_device(self, device: RfkillDevice) -> int:
        device.index = self._next_index
        device.registered = True
        self._devices[self._next_index] = device
        self._next_index += 1
        return device.index

    def unregister_device(self, index: int) -> int:
        self._devices.pop(index, None)
        return 0

    def get_device(self, index: int) -> Optional[RfkillDevice]:
        return self._devices.get(index)

    def find_devices_by_type(self, rf_type: RfkillType) -> List[RfkillDevice]:
        return [d for d in self._devices.values() if d.rf_type == rf_type]

    def soft_block_all(self, rf_type: Optional[RfkillType] = None) -> int:
        """Soft-block all devices (or of a specific type)."""
        for dev in self._devices.values():
            if rf_type is None or dev.rf_type == rf_type:
                dev.soft_block_set(True)
        return 0

    def soft_unblock_all(self, rf_type: Optional[RfkillType] = None) -> int:
        """Soft-unblock all devices (or of a specific type)."""
        for dev in self._devices.values():
            if rf_type is None or dev.rf_type == rf_type:
                dev.soft_block_set(False)
        return 0

    def register_switch(self, switch: RfkillSwitch) -> None:
        self._switches.append(switch)

    def register_global_listener(self, callback: Callable) -> None:
        self._global_listeners.append(callback)

    def enumerate_devices(self) -> List[RfkillDevice]:
        return list(self._devices.values())


# ============================================================================
# Global Rfkill Instance
# ============================================================================

_global_rfkill: Optional[RfkillSubsystem] = None


def get_global_rfkill() -> RfkillSubsystem:
    global _global_rfkill
    if _global_rfkill is None:
        _global_rfkill = RfkillSubsystem()
    return _global_rfkill


def register_rfkill_device(device: RfkillDevice) -> int:
    return get_global_rfkill().register_device(device)


def soft_block_rfkill(rf_type: Optional[RfkillType] = None) -> int:
    return get_global_rfkill().soft_block_all(rf_type)
