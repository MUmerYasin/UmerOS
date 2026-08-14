"""
UmerOS RTC Framework
=====================
Kernel Real-Time Clock subsystem.
Implements RTC devices, alarms, periodic interrupts,
and hardware/simulated RTC chips.
"""

from __future__ import annotations

import logging
import time
import datetime
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RTC Constants
# ---------------------------------------------------------------------------
RTC_VL_READ: int = 0x01
RTC_VL_CLR: int = 0x02
RTC_VL_INVALID: int = 0x04

RTC_AF: int = 0x01  # Alarm flag
RTC_UF: int = 0x02  # Update flag
RTC_PF: int = 0x04  # Periodic flag
RTC_SQW: int = 0x08  # Square wave

RTC_IRQF: int = 0x10

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_devices: Dict[str, RtcDevice] = {}
_classes: Dict[str, RtcClass] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class RtcTime:
    """RTC time representation"""
    year: int = 1970
    month: int = 1
    day: int = 1
    hour: int = 0
    minute: int = 0
    second: int = 0
    wday: int = 0  # weekday (0=Sunday)
    yday: int = 0  # day of year
    is_dst: bool = False

    @classmethod
    def from_epoch(cls, epoch: float) -> RtcTime:
        """Create from Unix timestamp"""
        t = datetime.datetime.fromtimestamp(epoch)
        return cls(
            year=t.year,
            month=t.month,
            day=t.day,
            hour=t.hour,
            minute=t.minute,
            second=t.second,
            wday=t.weekday(),
            yday=t.timetuple().tm_yday,
        )

    def to_epoch(self) -> float:
        """Convert to Unix timestamp"""
        dt = datetime.datetime(self.year, self.month, self.day,
                               self.hour, self.minute, self.second)
        return dt.timestamp()


@dataclass
class RtcAlarm:
    """RTC alarm setting"""
    time: RtcTime = field(default_factory=RtcTime)
    enabled: bool = False
    pending: bool = False
    repeat: int = 0  # 0=once, else bitmask of RTC_*F
    callback: Optional[Callable] = None


@dataclass
class RtcDevice:
    """Real-Time Clock device"""
    name: str
    class_name: str = "simulated"
    max_user_freq: int = 256
    is_registered: bool = False
    has_irq: bool = True
    _time: RtcTime = field(default_factory=RtcTime)
    _alarm: RtcAlarm = field(default_factory=RtcAlarm)
    _irq_enabled: int = 0
    _irq_handler: Optional[Callable] = None
    _ops: Dict[str, Callable] = field(default_factory=dict)
    _last_update: float = 0.0


@dataclass
class RtcClass:
    """RTC device class for bus-level operations"""
    name: str
    is_registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def register_class(name: str) -> RtcClass:
    """Register an RTC class"""
    if name in _classes:
        log.warning("RTC class %s already registered", name)
        return _classes[name]

    cls = RtcClass(name=name, is_registered=True)
    _classes[name] = cls
    log.info("Registered RTC class: %s", name)
    return cls


def register_device(name: str, class_name: str = "simulated") -> RtcDevice:
    """Register an RTC device"""
    if name in _devices:
        log.warning("RTC device %s already registered", name)
        return _devices[name]

    device = RtcDevice(
        name=name,
        class_name=class_name,
        is_registered=True,
        _time=RtcTime.from_epoch(time.time()),
        _last_update=time.time(),
    )
    _devices[name] = device
    log.info("Registered RTC device: %s (class=%s)", name, class_name)
    return device


def unregister_device(name: str) -> bool:
    """Unregister an RTC device"""
    if name not in _devices:
        log.warning("RTC device %s not found", name)
        return False
    del _devices[name]
    log.info("Unregistered RTC device: %s", name)
    return True


def get_device(name: str) -> Optional[RtcDevice]:
    """Get a registered RTC device"""
    return _devices.get(name)


def list_devices() -> List[str]:
    """List all registered RTC devices"""
    return list(_devices.keys())


# ---------------------------------------------------------------------------
# Time Operations
# ---------------------------------------------------------------------------
def read_time(device_name: str) -> Optional[RtcTime]:
    """Read current time from RTC"""
    device = get_device(device_name)
    if device is None:
        log.error("RTC device %s not found", device_name)
        return None

    # Update time based on elapsed time since last read
    now = time.time()
    elapsed = now - device._last_update
    device._last_update = now

    # Update internal time
    current_epoch = device._time.to_epoch() + elapsed
    device._time = RtcTime.from_epoch(current_epoch)

    log.debug("Read time from %s: %04d-%02d-%02d %02d:%02d:%02d",
              device_name, device._time.year, device._time.month,
              device._time.day, device._time.hour, device._time.minute,
              device._time.second)
    return device._time


def set_time(device_name: str, rtc_time: RtcTime) -> bool:
    """Set time on RTC"""
    device = get_device(device_name)
    if device is None:
        log.error("RTC device %s not found", device_name)
        return False

    device._time = rtc_time
    device._last_update = time.time()
    log.info("Set time on %s: %04d-%02d-%02d %02d:%02d:%02d",
             device_name, rtc_time.year, rtc_time.month, rtc_time.day,
             rtc_time.hour, rtc_time.minute, rtc_time.second)
    return True


def set_epoch(device_name: str, epoch: float) -> bool:
    """Set time from Unix timestamp"""
    return set_time(device_name, RtcTime.from_epoch(epoch))


# ---------------------------------------------------------------------------
# Alarm Operations
# ---------------------------------------------------------------------------
def set_alarm(device_name: str, alarm_time: RtcTime,
              callback: Optional[Callable] = None) -> bool:
    """Set an alarm"""
    device = get_device(device_name)
    if device is None:
        log.error("RTC device %s not found", device_name)
        return False

    device._alarm = RtcAlarm(
        time=alarm_time,
        enabled=True,
        pending=False,
        callback=callback,
    )
    log.info("Set alarm on %s: %04d-%02d-%02d %02d:%02d:%02d",
             device_name, alarm_time.year, alarm_time.month, alarm_time.day,
             alarm_time.hour, alarm_time.minute, alarm_time.second)
    return True


def cancel_alarm(device_name: str) -> bool:
    """Cancel an alarm"""
    device = get_device(device_name)
    if device is None:
        return False

    device._alarm.enabled = False
    device._alarm.pending = False
    log.info("Cancelled alarm on %s", device_name)
    return True


def read_alarm(device_name: str) -> Optional[RtcAlarm]:
    """Read current alarm setting"""
    device = get_device(device_name)
    if device is None:
        return None
    return device._alarm


def check_alarm(device_name: str) -> bool:
    """Check if alarm has triggered"""
    device = get_device(device_name)
    if device is None:
        return False

    if not device._alarm.enabled:
        return False

    current = read_time(device_name)
    if current is None:
        return False

    alarm_epoch = device._alarm.time.to_epoch()
    current_epoch = current.to_epoch()

    if current_epoch >= alarm_epoch:
        device._alarm.pending = True
        if device._alarm.callback:
            device._alarm.callback(device_name)
        log.info("Alarm triggered on %s", device_name)
        return True

    return False


# ---------------------------------------------------------------------------
# IRQ Operations
# ---------------------------------------------------------------------------
def enable_irq(device_name: str, irq_type: int) -> bool:
    """Enable RTC interrupt"""
    device = get_device(device_name)
    if device is None:
        return False

    device._irq_enabled |= irq_type
    log.debug("Enabled IRQ 0x%02X on %s", irq_type, device_name)
    return True


def disable_irq(device_name: str, irq_type: int) -> bool:
    """Disable RTC interrupt"""
    device = get_device(device_name)
    if device is None:
        return False

    device._irq_enabled &= ~irq_type
    log.debug("Disabled IRQ 0x%02X on %s", irq_type, device_name)
    return True


def set_irq_handler(device_name: str, handler: Callable) -> bool:
    """Set IRQ handler"""
    device = get_device(device_name)
    if device is None:
        return False

    device._irq_handler = handler
    return True


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def get_offset(device_name: str) -> int:
    """Get RTC offset in seconds from epoch"""
    device = get_device(device_name)
    if device is None:
        return 0

    return int(device._time.to_epoch())


def set_offset(device_name: str, offset: int) -> bool:
    """Set RTC offset"""
    return set_epoch(device_name, float(offset))


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== UmerOS RTC Framework Demo ===\n")

    # Register device
    rtc = register_device("rtc0")
    print(f"Registered: {rtc.name} (class={rtc.class_name})")

    # Read current time
    t = read_time("rtc0")
    print(f"Current time: {t.year:04d}-{t.month:02d}-{t.day:02d} "
          f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}")

    # Set time
    new_time = RtcTime(year=2025, month=1, day=15, hour=10, minute=30, second=0)
    set_time("rtc0", new_time)

    # Read back
    t = read_time("rtc0")
    print(f"After set: {t.year:04d}-{t.month:02d}-{t.day:02d} "
          f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}")

    # Set alarm
    alarm_time = RtcTime(year=2025, month=1, day=15, hour=10, minute=31, second=0)
    set_alarm("rtc0", alarm_time, callback=lambda n: print(f"  Alarm triggered on {n}!"))

    alarm = read_alarm("rtc0")
    print(f"Alarm enabled: {alarm.enabled}")

    # List devices
    print(f"\nDevices: {list_devices()}")
