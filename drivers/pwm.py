"""
UmerOS PWM Framework
=====================
Linux kernel Pulse Width Modulation subsystem.
Implements PWM controllers, channels, devices,
and consumer/driver interfaces.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PWM Constants
# ---------------------------------------------------------------------------
PWM_DISABLE: int = 0
PWM_ENABLE: int = 1
PWM_KEEP_SHADOW: int = 2

PWM_POLARITY_NORMAL: int = 0
PWM_POLARITY_INVERSED: int = 1

PWM_BITS_DEFAULT: int = 32
PWM_MAX_PERIOD: int = 0xFFFFFFFF

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_controllers: Dict[str, PwmController] = {}
_channels: Dict[str, PwmChannel] = {}
_devices: Dict[str, PwmDevice] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class PwmChannel:
    """PWM channel within a controller"""
    controller_name: str
    index: int
    name: str = ""
    period_ns: int = 0
    duty_cycle_ns: int = 0
    polarity: int = PWM_POLARITY_NORMAL
    is_enabled: bool = False
    is_requested: bool = False
    consumer: str = ""
    _ops: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class PwmController:
    """PWM controller chip"""
    name: str
    label: str
    npwm: int  # number of PWM channels
    is_registered: bool = False
    can_sleep: bool = False
    _channels: List[str] = field(default_factory=list)
    _ops: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class PwmDevice:
    """Consumer PWM device"""
    name: str
    controller_name: str
    channel_index: int
    period_ns: int = 0
    duty_cycle_ns: int = 0
    polarity: int = PWM_POLARITY_NORMAL
    is_active: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def register_controller(name: str, label: str, npwm: int) -> PwmController:
    """Register a PWM controller"""
    if name in _controllers:
        log.warning("Controller %s already registered", name)
        return _controllers[name]

    ctrl = PwmController(
        name=name,
        label=label,
        npwm=npwm,
        is_registered=True,
    )
    _controllers[name] = ctrl

    # Create channels
    for i in range(npwm):
        ch_name = f"{name}:{i}"
        channel = PwmChannel(controller_name=name, index=i, name=ch_name)
        _channels[ch_name] = channel
        ctrl._channels.append(ch_name)

    log.info("Registered PWM controller: %s (%d channels)", name, npwm)
    return ctrl


def unregister_controller(name: str) -> bool:
    """Unregister a PWM controller"""
    if name not in _controllers:
        log.warning("Controller %s not found", name)
        return False

    ctrl = _controllers[name]
    for ch_name in ctrl._channels:
        _channels.pop(ch_name, None)

    del _controllers[name]
    log.info("Unregistered PWM controller: %s", name)
    return True


def get_controller(name: str) -> Optional[PwmController]:
    """Get a registered PWM controller"""
    return _controllers.get(name)


def get_channel(controller_name: str, index: int) -> Optional[PwmChannel]:
    """Get a PWM channel"""
    ch_name = f"{controller_name}:{index}"
    return _channels.get(ch_name)


def list_controllers() -> List[str]:
    """List all registered PWM controllers"""
    return list(_controllers.keys())


# ---------------------------------------------------------------------------
# PWM Consumer Operations
# ---------------------------------------------------------------------------
def request_channel(controller_name: str, index: int,
                    consumer: str = "") -> Optional[PwmChannel]:
    """Request a PWM channel"""
    channel = get_channel(controller_name, index)
    if channel is None:
        log.error("PWM channel %s:%d not found", controller_name, index)
        return None

    if channel.is_requested:
        log.warning("PWM channel %s:%d already requested", controller_name, index)
        return channel

    channel.is_requested = True
    channel.consumer = consumer
    log.info("Requested PWM channel %s:%d for %s", controller_name, index, consumer)
    return channel


def release_channel(controller_name: str, index: int) -> bool:
    """Release a PWM channel"""
    channel = get_channel(controller_name, index)
    if channel is None:
        return False

    if channel.is_enabled:
        channel.is_enabled = False

    channel.is_requested = False
    channel.consumer = ""
    log.info("Released PWM channel %s:%d", controller_name, index)
    return True


def set_period(controller_name: str, index: int, period_ns: int) -> bool:
    """Set PWM period in nanoseconds"""
    channel = get_channel(controller_name, index)
    if channel is None:
        log.error("PWM channel %s:%d not found", controller_name, index)
        return False

    channel.period_ns = period_ns
    log.debug("Set period on %s:%d: %d ns", controller_name, index, period_ns)
    return True


def set_duty_cycle(controller_name: str, index: int, duty_ns: int) -> bool:
    """Set PWM duty cycle in nanoseconds"""
    channel = get_channel(controller_name, index)
    if channel is None:
        log.error("PWM channel %s:%d not found", controller_name, index)
        return False

    if duty_ns > channel.period_ns:
        log.warning("Duty cycle %d exceeds period %d", duty_ns, channel.period_ns)
        duty_ns = channel.period_ns

    channel.duty_cycle_ns = duty_ns
    log.debug("Set duty cycle on %s:%d: %d ns", controller_name, index, duty_ns)
    return True


def set_polarity(controller_name: str, index: int, polarity: int) -> bool:
    """Set PWM polarity"""
    channel = get_channel(controller_name, index)
    if channel is None:
        return False

    if polarity not in (PWM_POLARITY_NORMAL, PWM_POLARITY_INVERSED):
        log.error("Invalid polarity: %d", polarity)
        return False

    channel.polarity = polarity
    log.debug("Set polarity on %s:%d: %d", controller_name, index, polarity)
    return True


def enable_channel(controller_name: str, index: int) -> bool:
    """Enable PWM output"""
    channel = get_channel(controller_name, index)
    if channel is None:
        log.error("PWM channel %s:%d not found", controller_name, index)
        return False

    if channel.period_ns == 0:
        log.error("Cannot enable PWM with zero period")
        return False

    channel.is_enabled = True
    log.info("Enabled PWM channel %s:%d (period=%d ns, duty=%d ns)",
             controller_name, index, channel.period_ns, channel.duty_cycle_ns)
    return True


def disable_channel(controller_name: str, index: int) -> bool:
    """Disable PWM output"""
    channel = get_channel(controller_name, index)
    if channel is None:
        return False

    channel.is_enabled = False
    log.info("Disabled PWM channel %s:%d", controller_name, index)
    return True


def get_period(controller_name: str, index: int) -> int:
    """Get PWM period in nanoseconds"""
    channel = get_channel(controller_name, index)
    if channel is None:
        return 0
    return channel.period_ns


def get_duty_cycle(controller_name: str, index: int) -> int:
    """Get PWM duty cycle in nanoseconds"""
    channel = get_channel(controller_name, index)
    if channel is None:
        return 0
    return channel.duty_cycle_ns


def get_polarity(controller_name: str, index: int) -> int:
    """Get PWM polarity"""
    channel = get_channel(controller_name, index)
    if channel is None:
        return PWM_POLARITY_NORMAL
    return channel.polarity


def is_enabled(controller_name: str, index: int) -> bool:
    """Check if PWM channel is enabled"""
    channel = get_channel(controller_name, index)
    if channel is None:
        return False
    return channel.is_enabled


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------
def set_frequency(controller_name: str, index: int, freq_hz: int) -> bool:
    """Set PWM frequency in Hz (convenience wrapper)"""
    if freq_hz <= 0:
        log.error("Invalid frequency: %d Hz", freq_hz)
        return False

    period_ns = 1_000_000_000 // freq_hz
    return set_period(controller_name, index, period_ns)


def set_duty_percent(controller_name: str, index: int, percent: float) -> bool:
    """Set duty cycle as percentage (convenience wrapper)"""
    if not (0.0 <= percent <= 100.0):
        log.error("Invalid duty percent: %.1f", percent)
        return False

    channel = get_channel(controller_name, index)
    if channel is None:
        return False

    duty_ns = int(channel.period_ns * percent / 100.0)
    return set_duty_cycle(controller_name, index, duty_ns)


def get_frequency(controller_name: str, index: int) -> float:
    """Get PWM frequency in Hz"""
    period_ns = get_period(controller_name, index)
    if period_ns <= 0:
        return 0.0
    return 1_000_000_000.0 / period_ns


def get_duty_percent(controller_name: str, index: int) -> float:
    """Get duty cycle as percentage"""
    channel = get_channel(controller_name, index)
    if channel is None or channel.period_ns == 0:
        return 0.0
    return (channel.duty_cycle_ns / channel.period_ns) * 100.0


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== UmerOS PWM Framework Demo ===\n")

    # Register controllers
    register_controller("pwm0", "STM32 PWM", npwm=4)
    register_controller("pwm1", "ESP32 LEDC", npwm=8)

    print(f"Controllers: {list_controllers()}")

    # Request and configure channel
    ch = request_channel("pwm0", 0, consumer="led-backlight")
    if ch:
        set_period("pwm0", 0, 1_000_000)  # 1 kHz
        set_duty_cycle("pwm0", 0, 500_000)  # 50%
        enable_channel("pwm0", 0)

        print(f"\npwm0:0 - period={get_period('pwm0', 0)} ns, "
              f"freq={get_frequency('pwm0', 0):.0f} Hz, "
              f"duty={get_duty_percent('pwm0', 0):.1f}%, "
              f"enabled={is_enabled('pwm0', 0)}")

    # Set frequency directly
    set_frequency("pwm0", 1, 1000)  # 1 kHz
    set_duty_percent("pwm0", 1, 75.0)
    enable_channel("pwm0", 1)

    print(f"pwm0:1 - freq={get_frequency('pwm0', 1):.0f} Hz, "
          f"duty={get_duty_percent('pwm0', 1):.1f}%")

    # Disable
    disable_channel("pwm0", 0)
    release_channel("pwm0", 0)
    print(f"\npwm0:0 enabled after disable/release: {is_enabled('pwm0', 0)}")
