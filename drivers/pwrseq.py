"""
UmerOS Power Sequence Subsystem
================================
Linux kernel-like power sequence framework for managing device
power-on/off sequences with optional delays and GPIO control.

Reference: drivers/pwrseq/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# Power Sequence Constants
# ============================================================================

PWRSEQ_SUCCESS: int = 0
PWRSEQ_ERROR: int = 1
PWRSEQ_TIMEOUT: int = 2

PWRSEQ_MAX_GPIOS: int = 8
PWRSEQ_MAX_STEPS: int = 16


class PWRSEQState(IntEnum):
    """Power sequence state."""
    OFF: int = 0
    ON: int = 1
    PRE_ON: int = 2
    POST_ON: int = 3
    PRE_OFF: int = 4
    POST_OFF: int = 5


# ============================================================================
# Power Sequence Step
# ============================================================================

@dataclass
class PWRSEQStep:
    """Single step in a power sequence."""
    name: str
    gpio: int = -1  # GPIO number, -1 = none
    value: int = 0  # GPIO value (0 or 1)
    delay_ms: int = 0  # delay after setting
    state: PWRSEQState = PWRSEQState.OFF
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def execute(self) -> int:
        """Execute this power sequence step."""
        if self.gpio >= 0:
            if "set_gpio" in self._ops:
                self._ops["set_gpio"](self.gpio, self.value)
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)
        return PWRSEQ_SUCCESS


# ============================================================================
# Power Sequence
# ============================================================================

@dataclass
class PWRSEQSequence:
    """Power sequence (mirrors struct pwrseq)."""
    name: str
    index: int
    steps: List[PWRSEQStep] = field(default_factory=list)
    state: PWRSEQState = PWRSEQState.OFF
    on_delay_ms: int = 0
    off_delay_ms: int = 0
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def add_step(self, step: PWRSEQStep) -> int:
        if len(self.steps) >= PWRSEQ_MAX_STEPS:
            return PWRSEQ_ERROR
        self.steps.append(step)
        return 0

    def remove_step(self, index: int) -> bool:
        if 0 <= index < len(self.steps):
            self.steps.pop(index)
            return True
        return False

    def power_on(self) -> int:
        """Execute power-on sequence."""
        self.state = PWRSEQState.PRE_ON
        for step in self.steps:
            result = step.execute()
            if result != PWRSEQ_SUCCESS:
                self.state = PWRSEQState.OFF
                return result
        if self.on_delay_ms > 0:
            time.sleep(self.on_delay_ms / 1000.0)
        self.state = PWRSEQState.ON
        self._notify("power_on")
        return PWRSEQ_SUCCESS

    def power_off(self) -> int:
        """Execute power-off sequence (reverse order)."""
        self.state = PWRSEQState.PRE_OFF
        for step in reversed(self.steps):
            result = step.execute()
            if result != PWRSEQ_SUCCESS:
                return result
        if self.off_delay_ms > 0:
            time.sleep(self.off_delay_ms / 1000.0)
        self.state = PWRSEQState.OFF
        self._notify("power_off")
        return PWRSEQ_SUCCESS

    def reset(self) -> int:
        """Execute power reset (off then on)."""
        self.power_off()
        return self.power_on()

    def register_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify(self, event: str) -> None:
        for cb in self._listeners:
            cb(self.name, event)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.name,
            "steps": len(self.steps),
            "on_delay": self.on_delay_ms,
            "off_delay": self.off_delay_ms,
        }


# ============================================================================
# Power Sequence Device
# ============================================================================

@dataclass
class PWRSEQDevice:
    """Power sequence device wrapping a sub-system power control."""
    name: str
    index: int
    sequence: Optional[PWRSEQSequence] = None
    ref_count: int = 0
    enabled: bool = False

    def enable(self) -> int:
        if self.ref_count == 0 and self.sequence:
            result = self.sequence.power_on()
            if result != PWRSEQ_SUCCESS:
                return result
        self.ref_count += 1
        self.enabled = True
        return PWRSEQ_SUCCESS

    def disable(self) -> int:
        if self.ref_count > 0:
            self.ref_count -= 1
        if self.ref_count == 0 and self.sequence:
            result = self.sequence.power_off()
            if result != PWRSEQ_SUCCESS:
                return result
            self.enabled = False
        return PWRSEQ_SUCCESS

    def is_enabled(self) -> bool:
        return self.enabled

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "ref_count": self.ref_count,
            "sequence": self.sequence.name if self.sequence else None,
        }


# ============================================================================
# Power Sequence Subsystem Manager
# ============================================================================

class PWRSEQSubsystem:
    """Central power sequence subsystem managing sequences and devices."""

    def __init__(self) -> None:
        self._sequences: Dict[str, PWRSEQSequence] = {}
        self._devices: Dict[str, PWRSEQDevice] = {}
        self._next_index: int = 0

    def register_sequence(self, seq: PWRSEQSequence) -> int:
        seq.index = self._next_index
        self._sequences[seq.name] = seq
        self._next_index += 1
        return 0

    def unregister_sequence(self, name: str) -> int:
        self._sequences.pop(name, None)
        return 0

    def get_sequence(self, name: str) -> Optional[PWRSEQSequence]:
        return self._sequences.get(name)

    def register_device(self, device: PWRSEQDevice) -> int:
        device.index = self._next_index
        self._devices[device.name] = device
        self._next_index += 1
        return 0

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return 0

    def get_device(self, name: str) -> Optional[PWRSEQDevice]:
        return self._devices.get(name)

    def power_on(self, device_name: str) -> int:
        device = self._devices.get(device_name)
        return device.enable() if device else PWRSEQ_ERROR

    def power_off(self, device_name: str) -> int:
        device = self._devices.get(device_name)
        return device.disable() if device else PWRSEQ_ERROR


# ============================================================================
# Global Power Sequence Instance
# ============================================================================

_global_pwrseq: Optional[PWRSEQSubsystem] = None


def get_global_pwrseq() -> PWRSEQSubsystem:
    global _global_pwrseq
    if _global_pwrseq is None:
        _global_pwrseq = PWRSEQSubsystem()
    return _global_pwrseq


def register_pwrseq_sequence(seq: PWRSEQSequence) -> int:
    return get_global_pwrseq().register_sequence(seq)


def pwrseq_power_on(device_name: str) -> int:
    return get_global_pwrseq().power_on(device_name)
