"""
UmerOS Counter Framework
=========================
Kernel Hardware Counter subsystem.
Implements counter devices, channels, and operations
for counting events, encoder positions, and timer inputs.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Counter Constants
# ---------------------------------------------------------------------------
COUNTER_COUNT_MODE_WRAP: str = "wrap"
COUNTER_COUNT_MODE_SATURATE: str = "saturate"

COUNTER_EDGE_RISING: str = "rising"
COUNTER_EDGE_FALLING: str = "falling"
COUNTER_EDGE_BOTH: str = "both"

COUNTER_FUNCTION_NONE: str = "none"
COUNTER_FUNCTION_QUADRATURE_X1: str = "quadrature_x1"
COUNTER_FUNCTION_QUADRATURE_X2: str = "quadrature_x2"
COUNTER_FUNCTION_QUADRATURE_X4: str = "quadrature_x4"

COUNTER_ACTION_NONE: str = "none"
COUNTER_ACTION_SET: str = "set"
COUNTER_ACTION_CLEAR: str = "clear"
COUNTER_ACTION_CAPTURE: str = "capture"

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_devices: Dict[str, CounterDevice] = {}
_channels: Dict[str, CounterChannel] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class CounterCountPreset:
    """Counter preset value"""
    count: int = 0
    function: str = COUNTER_FUNCTION_NONE


@dataclass
class CounterWatchChannel:
    """Counter watch channel for event detection"""
    channel_id: int
    event: str = ""
    action: str = COUNTER_ACTION_NONE
    threshold: int = 0
    enable: bool = False
    _callback: Optional[Callable] = None


@dataclass
class CounterChannel:
    """Counter channel"""
    device_name: str
    index: int
    name: str = ""
    count: int = 0
    count_mode: str = COUNTER_COUNT_MODE_WRAP
    function: str = COUNTER_FUNCTION_NONE
    direction: int = 1  # +1 or -1
    min_count: int = 0
    max_count: int = 0xFFFFFFFF
    is_enabled: bool = True
    _ops: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class CounterDevice:
    """Hardware counter device"""
    name: str
    label: str = ""
    num_channels: int = 1
    is_registered: bool = False
    _channels: List[str] = field(default_factory=list)
    _ops: Dict[str, Callable] = field(default_factory=dict)
    _timestamp: float = 0.0


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def register_device(name: str, label: str = "", num_channels: int = 1) -> CounterDevice:
    """Register a counter device"""
    if name in _devices:
        log.warning("Counter device %s already registered", name)
        return _devices[name]

    device = CounterDevice(
        name=name,
        label=label or name,
        num_channels=num_channels,
        is_registered=True,
        _timestamp=time.time(),
    )
    _devices[name] = device

    # Create channels
    for i in range(num_channels):
        ch_name = f"{name}:{i}"
        channel = CounterChannel(device_name=name, index=i, name=ch_name)
        _channels[ch_name] = channel
        device._channels.append(ch_name)

    log.info("Registered counter device: %s (%d channels)", name, num_channels)
    return device


def unregister_device(name: str) -> bool:
    """Unregister a counter device"""
    if name not in _devices:
        log.warning("Counter device %s not found", name)
        return False

    device = _devices[name]
    for ch_name in device._channels:
        _channels.pop(ch_name, None)

    del _devices[name]
    log.info("Unregistered counter device: %s", name)
    return True


def get_device(name: str) -> Optional[CounterDevice]:
    """Get a registered counter device"""
    return _devices.get(name)


def get_channel(device_name: str, index: int) -> Optional[CounterChannel]:
    """Get a counter channel"""
    ch_name = f"{device_name}:{index}"
    return _channels.get(ch_name)


def list_devices() -> List[str]:
    """List all registered counter devices"""
    return list(_devices.keys())


# ---------------------------------------------------------------------------
# Counter Operations
# ---------------------------------------------------------------------------
def read_count(device_name: str, index: int) -> int:
    """Read counter value"""
    channel = get_channel(device_name, index)
    if channel is None:
        log.error("Counter channel %s:%d not found", device_name, index)
        return 0

    return channel.count


def write_count(device_name: str, index: int, count: int) -> bool:
    """Write counter value"""
    channel = get_channel(device_name, index)
    if channel is None:
        log.error("Counter channel %s:%d not found", device_name, index)
        return False

    # Apply direction
    if channel.direction < 0:
        count = -count

    # Handle wrap/saturate
    if channel.count_mode == COUNTER_COUNT_MODE_WRAP:
        count = count & ((1 << 32) - 1)  # Wrap to 32-bit
    elif channel.count_mode == COUNTER_COUNT_MODE_SATURATE:
        count = max(channel.min_count, min(count, channel.max_count))

    channel.count = count
    log.debug("Wrote count to %s:%d: %d", device_name, index, count)
    return True


def increment_count(device_name: str, index: int, steps: int = 1) -> bool:
    """Increment counter value"""
    channel = get_channel(device_name, index)
    if channel is None:
        return False

    count = channel.count + (steps * channel.direction)
    return write_count(device_name, index, count)


def decrement_count(device_name: str, index: int, steps: int = 1) -> bool:
    """Decrement counter value"""
    return increment_count(device_name, index, -steps)


def reset_count(device_name: str, index: int) -> bool:
    """Reset counter to zero"""
    return write_count(device_name, index, 0)


def set_count_mode(device_name: str, index: int, mode: str) -> bool:
    """Set counter mode (wrap/saturate)"""
    channel = get_channel(device_name, index)
    if channel is None:
        return False

    if mode not in (COUNTER_COUNT_MODE_WRAP, COUNTER_COUNT_MODE_SATURATE):
        log.error("Invalid count mode: %s", mode)
        return False

    channel.count_mode = mode
    log.debug("Set count mode on %s:%d: %s", device_name, index, mode)
    return True


def set_function(device_name: str, index: int, function: str) -> bool:
    """Set counter function"""
    channel = get_channel(device_name, index)
    if channel is None:
        return False

    channel.function = function
    log.debug("Set function on %s:%d: %s", device_name, index, function)
    return True


def set_direction(device_name: str, index: int, direction: int) -> bool:
    """Set counter direction (+1 or -1)"""
    channel = get_channel(device_name, index)
    if channel is None:
        return False

    if direction not in (-1, 1):
        log.error("Invalid direction: %d", direction)
        return False

    channel.direction = direction
    log.debug("Set direction on %s:%d: %d", device_name, index, direction)
    return True


def get_count(device_name: str, index: int) -> int:
    """Get counter value (alias for read_count)"""
    return read_count(device_name, index)


def get_count_mode(device_name: str, index: int) -> str:
    """Get counter mode"""
    channel = get_channel(device_name, index)
    if channel is None:
        return COUNTER_COUNT_MODE_WRAP
    return channel.count_mode


def get_function(device_name: str, index: int) -> str:
    """Get counter function"""
    channel = get_channel(device_name, index)
    if channel is None:
        return COUNTER_FUNCTION_NONE
    return channel.function


def get_direction(device_name: str, index: int) -> int:
    """Get counter direction"""
    channel = get_channel(device_name, index)
    if channel is None:
        return 1
    return channel.direction


# ---------------------------------------------------------------------------
# Encoder Functions
# ---------------------------------------------------------------------------
def configure_quadrature(device_name: str, index: int,
                         mode: str = COUNTER_FUNCTION_QUADRATURE_X4) -> bool:
    """Configure counter for quadrature encoder"""
    return set_function(device_name, index, mode)


def read_encoder_position(device_name: str, index: int) -> int:
    """Read encoder position (signed)"""
    channel = get_channel(device_name, index)
    if channel is None:
        return 0

    # For quadrature, return signed count
    if channel.function.startswith("quadrature"):
        if channel.count > channel.max_count // 2:
            return channel.count - (channel.max_count + 1)
        return channel.count
    return channel.count


def reset_encoder(device_name: str, index: int) -> bool:
    """Reset encoder to zero"""
    return reset_count(device_name, index)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== UmerOS Counter Framework Demo ===\n")

    # Register devices
    encoder = register_device("encoder0", label="Rotary Encoder", num_channels=1)
    timer = register_device("timer0", label="Hardware Timer", num_channels=4)

    print(f"Devices: {list_devices()}")

    # Configure encoder
    configure_quadrature("encoder0", 0, COUNTER_FUNCTION_QUADRATURE_X4)
    set_direction("encoder0", 0, +1)

    # Simulate encoder movement
    for i in range(10):
        increment_count("encoder0", 0, 100)
        pos = read_encoder_position("encoder0", 0)
        print(f"  Encoder position: {pos}")

    # Configure timer channels
    for i in range(4):
        set_count_mode("timer0", i, COUNTER_COUNT_MODE_WRAP)
        set_function("timer0", i, COUNTER_FUNCTION_NONE)

    # Simulate timer counting
    for i in range(4):
        for _ in range(10):
            increment_count("timer0", i, 1000)
        print(f"  Timer channel {i}: {get_count('timer0', i)}")

    # Reset
    reset_count("encoder0", 0)
    print(f"\nAfter reset: encoder0 position = {read_encoder_position('encoder0', 0)}")
