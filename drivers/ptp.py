"""
UmerOS PTP Hardware Clock Subsystem
====================================
Kernel-like PTP (Precision Time Protocol) clock framework.
Implements PHC devices, clock operations, time counters,
and hardware timestamping for IEEE 1588 PTP.

Reference: Documentation/driver-api/ptp/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# PTP Constants
# ============================================================================

PTP_MAX_SENSORS: int = 256
PTP_MAX_ALARM: int = 4
PTP_CLK_MAGIC: int = 'P'

PTP_CLOCK_GETTIME: int = 0
PTP_CLOCK_SETTIME: int = 1
PTP_CLOCK_ADJTIME: int = 2
PTP_CLOCK_GETOFFSET: int = 3

PTP_RISING_EDGE: int = 0x01
PTP_FALLING_EDGE: int = 0x02
PTP_STRICT_FLAGS: int = 0x04


class PTPClockType(IntEnum):
    """PTP clock type."""
    EXTERNAL = 0
    INTERNAL = 1


# ============================================================================
# PTP Clock Time
# ============================================================================

@dataclass
class PTPClockTime:
    """PTP clock time representation (mirrors struct ptp_clock_time)."""
    seconds: int = 0
    nanoseconds: int = 0

    def to_ns(self) -> int:
        return self.seconds * 1_000_000_000 + self.nanoseconds

    @classmethod
    def from_ns(cls, ns: int) -> PTPClockTime:
        return cls(seconds=ns // 1_000_000_000, nanoseconds=ns % 1_000_000_000)


@dataclass
class PTPTimespec:
    """PTP timespec (mirrors struct ptp_clock_spec)."""
    sec: int = 0
    nsec: int = 0


# ============================================================================
# PTP Clock Operations
# ============================================================================

@dataclass
class PTPClockOps:
    """PTP hardware clock operations (mirrors struct ptp_clock_operations).

    Implementations provide the actual hardware interactions.
    """
    gettime: Optional[Callable] = None
    settime: Optional[Callable] = None
    adjtime: Optional[Callable] = None
    adjfreq: Optional[Callable] = None
    getcounter: Optional[Callable] = None
    enable: Optional[Callable] = None
    verify: Optional[Callable] = None
    pps_init: Optional[Callable] = None
    pps_configure: Optional[Callable] = None
    pps_enable: Optional[Callable] = None


# ============================================================================
# PTP Alarm
# ============================================================================

@dataclass
class PTPAlarm:
    """PTP alarm for scheduled events."""
    index: int
    enabled: bool = False
    target_time: PTPClockTime = field(default_factory=PTPClockTime)
    callback: Optional[Callable] = None


# ============================================================================
# PTP Clock (PHC)
# ============================================================================

@dataclass
class PTPClock:
    """PTP Hardware Clock (PHC) device (mirrors struct ptp_clock).

    Each PHC provides a high-precision time source that can
    be disciplined by external PTP messages.
    """
    name: str
    index: int
    clock_type: PTPClockType = PTPClockType.INTERNAL
    ops: PTPClockOps = field(default_factory=PTPClockOps)
    alarms: List[PTPAlarm] = field(default_factory=list)
    time: PTPClockTime = field(default_factory=PTPClockTime)
    _listeners: List[Callable] = field(default_factory=list, repr=False)
    _pps_frequency: int = 0
    _pps_enabled: bool = False

    def get_time(self) -> PTPClockTime:
        """Get current PHC time."""
        if self.ops.gettime:
            return self.ops.gettime(self)
        return self.time

    def set_time(self, ts: PTPClockTime) -> int:
        """Set PHC time."""
        if self.ops.settime:
            return self.ops.settime(self, ts)
        self.time = ts
        return 0

    def adjtime(self, delta_ns: int) -> int:
        """Adjust PHC time by delta (mirrors ptp_clock_adjtime)."""
        if self.ops.adjtime:
            return self.ops.adjtime(self, delta_ns)
        self.time = PTPClockTime.from_ns(self.time.to_ns() + delta_ns)
        return 0

    def adjfreq(self, ppb: int) -> int:
        """Adjust PHC frequency in parts-per-billion."""
        if self.ops.adjfreq:
            return self.ops.adjfreq(self, ppb)
        return 0

    def get_counter(self, channel: int = 0) -> int:
        """Get hardware counter value."""
        if self.ops.getcounter:
            return self.ops.getcounter(self, channel)
        return 0

    def enable_alarm(self, alarm_index: int, enable: bool) -> int:
        if alarm_index >= len(self.alarms):
            return -1
        self.alarms[alarm_index].enabled = enable
        return 0

    def set_alarm(self, alarm_index: int, target: PTPClockTime) -> int:
        if alarm_index >= len(self.alarms):
            return -1
        self.alarms[alarm_index].target_time = target
        return 0

    def register_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _fire_event(self, event_type: str, data: Any = None) -> None:
        for cb in self._listeners:
            cb(self.index, event_type, data)

    def pps_configure(self, pin_index: int, func: int, chan: int) -> int:
        """Configure PPS output pin."""
        if self.ops.pps_configure:
            return self.ops.pps_configure(self, pin_index, func, chan)
        return 0

    def pps_enable(self, enable: bool) -> int:
        self._pps_enabled = enable
        if self.ops.pps_enable:
            return self.ops.pps_enable(self, enable)
        return 0


# ============================================================================
# PTP Pin Configuration
# ============================================================================

@dataclass
class PTPPin:
    """PTP pin configuration for external signals."""
    name: str
    index: int
    function: int = 0  # 0=disabled, 1=input, 2=output
    channel: int = 0
    ab_index: int = 0


# ============================================================================
# PTP Subsystem Manager
# ============================================================================

class PTPSubsystem:
    """Central PTP subsystem managing clocks, pins, and alarms."""

    def __init__(self) -> None:
        self._clocks: Dict[int, PTPClock] = {}
        self._next_index: int = 0
        self._pins: Dict[str, PTPPin] = {}

    def register_clock(self, clock: PTPClock) -> int:
        """Register a PHC device."""
        clock.index = self._next_index
        self._clocks[self._next_index] = clock
        self._next_index += 1
        return clock.index

    def unregister_clock(self, index: int) -> int:
        self._clocks.pop(index, None)
        return 0

    def get_clock(self, index: int) -> Optional[PTPClock]:
        return self._clocks.get(index)

    def get_clock_by_name(self, name: str) -> Optional[PTPClock]:
        for clock in self._clocks.values():
            if clock.name == name:
                return clock
        return None

    def enumerate_clocks(self) -> List[PTPClock]:
        return list(self._clocks.values())

    def configure_pin(self, pin: PTPPin) -> int:
        self._pins[pin.name] = pin
        return 0

    def get_pin(self, name: str) -> Optional[PTPin]:
        return self._pins.get(name)

    def read_time(self, clock_index: int) -> Optional[PTPClockTime]:
        clock = self.get_clock(clock_index)
        return clock.get_time() if clock else None

    def write_time(self, clock_index: int, ts: PTPClockTime) -> int:
        clock = self.get_clock(clock_index)
        return clock.set_time(ts) if clock else -1

    def adjust_time(self, clock_index: int, delta_ns: int) -> int:
        clock = self.get_clock(clock_index)
        return clock.adjtime(delta_ns) if clock else -1


# ============================================================================
# Global PTP Instance
# ============================================================================

_global_ptp: Optional[PTPSubsystem] = None


def get_global_ptp() -> PTPSubsystem:
    global _global_ptp
    if _global_ptp is None:
        _global_ptp = PTPSubsystem()
    return _global_ptp


def register_ptp_clock(clock: PTPClock) -> int:
    return get_global_ptp().register_clock(clock)


def get_ptp_time(clock_index: int) -> Optional[PTPClockTime]:
    return get_global_ptp().read_time(clock_index)
