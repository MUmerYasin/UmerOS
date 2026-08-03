"""
UmerOS Devfreq Framework
========================
Linux kernel Dynamic Voltage and Frequency Scaling (DVFS) subsystem.
Implements devfreq devices, governors (simple_ondemand, userspace,
powersave, performance), frequency tables, and power statistics.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Devfreq Constants
# ---------------------------------------------------------------------------
DEVFREQ_GOV_SIMPLE_ONDEMAND: str = "simple_ondemand"
DEVFREQ_GOV_USERSPACE: str = "userspace"
DEVFREQ_GOV_POWERSAVE: str = "powersave"
DEVFREQ_GOV_PERFORMANCE: str = "performance"

DEVFREQ_FLAG_LEAST_UPPER_BOUND: int = 0x01

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_devices: Dict[str, DevfreqDevice] = {}
_governors: Dict[str, DevfreqGovernor] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class FreqTable:
    """Frequency table entry"""
    freq: int  # Hz
    power: float  # mW
    latency_us: int = 0  # transition latency


@dataclass
class DevfreqDevice:
    """Dynamic voltage/frequency scaling device"""
    name: str
    governor_name: str = DEVFREQ_GOV_SIMPLE_ONDEMAND
    min_freq: int = 0
    max_freq: int = 0
    cur_freq: int = 0
    polling_interval_ms: int = 50
    is_registered: bool = False
    _freq_table: List[FreqTable] = field(default_factory=list)
    _total_transitions: int = 0
    _total_time_ns: int = 0
    _busy_time_ns: int = 0
    _suspend_time_ns: int = 0
    _last_update: float = 0.0
    _target_freq: int = 0
    _governor: Optional[DevfreqGovernor] = None
    _ops: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class DevfreqGovernor:
    """Devfreq governor for frequency selection"""
    name: str
    is_registered: bool = False
    _get_target_freq: Optional[Callable] = None
    _init: Optional[Callable] = None
    _exit: Optional[Callable] = None
    _event_handler: Optional[Callable] = None


@dataclass
class DevfreqStats:
    """Device frequency statistics"""
    total_transitions: int = 0
    total_time_ns: int = 0
    busy_time_ns: int = 0
    suspend_time_ns: int = 0
    current_freq: int = 0
    max_freq: int = 0
    min_freq: int = 0

    @property
    def load_percent(self) -> float:
        if self.total_time_ns == 0:
            return 0.0
        return (self.busy_time_ns / self.total_time_ns) * 100.0


# ---------------------------------------------------------------------------
# Governor Implementations
# ---------------------------------------------------------------------------
def _simple_ondemand_get_target(device: DevfreqDevice) -> int:
    """Simple ondemand governor: scale up when busy, down when idle"""
    stats = get_devfreq_stats(device.name)
    if stats.total_time_ns == 0:
        return device.cur_freq if device.cur_freq > 0 else device.max_freq

    load = stats.load_percent
    if load > 80:
        target = min(device.cur_freq * 2, device.max_freq)
    elif load < 20:
        target = max(device.cur_freq // 2, device.min_freq)
    else:
        target = device.cur_freq

    return target


def _userspace_get_target(device: DevfreqDevice) -> int:
    """Userspace governor: use externally set target"""
    return device._target_freq if device._target_freq > 0 else device.cur_freq


def _powersave_get_target(device: DevfreqDevice) -> int:
    """Powersave governor: always minimum frequency"""
    return device.min_freq


def _performance_get_target(device: DevfreqDevice) -> int:
    """Performance governor: always maximum frequency"""
    return device.max_freq


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def register_governor(name: str, get_target: Optional[Callable] = None) -> DevfreqGovernor:
    """Register a devfreq governor"""
    if name in _governors:
        log.warning("Governor %s already registered", name)
        return _governors[name]

    gov = DevfreqGovernor(name=name, is_registered=True)
    if get_target is not None:
        gov._get_target_freq = get_target
    elif name == DEVFREQ_GOV_SIMPLE_ONDEMAND:
        gov._get_target_freq = _simple_ondemand_get_target
    elif name == DEVFREQ_GOV_USERSPACE:
        gov._get_target_freq = _userspace_get_target
    elif name == DEVFREQ_GOV_POWERSAVE:
        gov._get_target_freq = _powersave_get_target
    elif name == DEVFREQ_GOV_PERFORMANCE:
        gov._get_target_freq = _performance_get_target

    _governors[name] = gov
    log.info("Registered devfreq governor: %s", name)
    return gov


def register_device(name: str, min_freq: int, max_freq: int,
                    governor_name: str = DEVFREQ_GOV_SIMPLE_ONDEMAND,
                    freq_table: Optional[List[FreqTable]] = None) -> DevfreqDevice:
    """Register a devfreq device"""
    if name in _devices:
        log.warning("Device %s already registered", name)
        return _devices[name]

    gov = _governors.get(governor_name)
    if gov is None:
        log.warning("Governor %s not found, using simple_ondemand", governor_name)
        gov = _governors.get(DEVFREQ_GOV_SIMPLE_ONDEMAND)

    device = DevfreqDevice(
        name=name,
        governor_name=governor_name,
        min_freq=min_freq,
        max_freq=max_freq,
        cur_freq=max_freq,
        is_registered=True,
        _freq_table=freq_table or [],
        _governor=gov,
        _last_update=time.time(),
    )
    _devices[name] = device
    log.info("Registered devfreq device: %s (%d-%d Hz)", name, min_freq, max_freq)
    return device


def unregister_device(name: str) -> bool:
    """Unregister a devfreq device"""
    if name not in _devices:
        log.warning("Device %s not found", name)
        return False
    del _devices[name]
    log.info("Unregistered devfreq device: %s", name)
    return True


def get_device(name: str) -> Optional[DevfreqDevice]:
    """Get a registered devfreq device"""
    return _devices.get(name)


def list_devices() -> List[str]:
    """List all registered devfreq devices"""
    return list(_devices.keys())


def list_governors() -> List[str]:
    """List all registered governors"""
    return list(_governors.keys())


# ---------------------------------------------------------------------------
# Device Operations
# ---------------------------------------------------------------------------
def set_frequency(device_name: str, freq: int) -> bool:
    """Set device frequency (clamp to min/max)"""
    device = get_device(device_name)
    if device is None:
        log.error("Device %s not found", device_name)
        return False

    freq = max(device.min_freq, min(freq, device.max_freq))
    if freq != device.cur_freq:
        old_freq = device.cur_freq
        device.cur_freq = freq
        device._total_transitions += 1
        log.info("Device %s: %d -> %d Hz", device_name, old_freq, freq)
    return True


def set_target_frequency(device_name: str, freq: int) -> bool:
    """Set target frequency for userspace governor"""
    device = get_device(device_name)
    if device is None:
        log.error("Device %s not found", device_name)
        return False

    device._target_freq = max(device.min_freq, min(freq, device.max_freq))
    return True


def update_stats(device_name: str, busy_ns: int) -> bool:
    """Update device statistics"""
    device = get_device(device_name)
    if device is None:
        log.error("Device %s not found", device_name)
        return False

    now = time.time()
    elapsed_ns = int((now - device._last_update) * 1e9)
    device._total_time_ns += elapsed_ns
    device._busy_time_ns += busy_ns
    device._last_update = now
    return True


def get_devfreq_stats(device_name: str) -> DevfreqStats:
    """Get device frequency statistics"""
    device = get_device(device_name)
    if device is None:
        return DevfreqStats()

    return DevfreqStats(
        total_transitions=device._total_transitions,
        total_time_ns=device._total_time_ns,
        busy_time_ns=device._busy_time_ns,
        suspend_time_ns=device._suspend_time_ns,
        current_freq=device.cur_freq,
        max_freq=device.max_freq,
        min_freq=device.min_freq,
    )


def get_available_frequencies(device_name: str) -> List[int]:
    """Get available frequencies for a device"""
    device = get_device(device_name)
    if device is None:
        return []

    if device._freq_table:
        return [entry.freq for entry in device._freq_table]
    return [device.min_freq, device.max_freq]


def get_transition_latency(device_name: str) -> int:
    """Get transition latency in microseconds"""
    device = get_device(device_name)
    if device is None:
        return 0

    if device._freq_table:
        return max(entry.latency_us for entry in device._freq_table)
    return 0


def resume(device_name: str) -> bool:
    """Resume a devfreq device from suspend"""
    device = get_device(device_name)
    if device is None:
        return False

    device._suspend_time_ns = 0
    device._last_update = time.time()
    log.info("Device %s resumed", device_name)
    return True


def suspend(device_name: str) -> bool:
    """Suspend a devfreq device"""
    device = get_device(device_name)
    if device is None:
        return False

    device._suspend_time_ns = int((time.time() - device._last_update) * 1e9)
    log.info("Device %s suspended", device_name)
    return True


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== UmerOS Devfreq Demo ===\n")

    # Register governors
    register_governor(DEVFREQ_GOV_SIMPLE_ONDEMAND)
    register_governor(DEVFREQ_GOV_USERSPACE)
    register_governor(DEVFREQ_GOV_POWERSAVE)
    register_governor(DEVFREQ_GOV_PERFORMANCE)
    print(f"Governors: {list_governors()}")

    # Create frequency table
    gpu_table = [
        FreqTable(freq=200_000_000, power=50.0, latency_us=100),
        FreqTable(freq=400_000_000, power=120.0, latency_us=100),
        FreqTable(freq=600_000_000, power=200.0, latency_us=150),
        FreqTable(freq=800_000_000, power=350.0, latency_us=200),
    ]

    # Register device
    gpu = register_device(
        name="gpu",
        min_freq=200_000_000,
        max_freq=800_000_000,
        governor_name=DEVFREQ_GOV_SIMPLE_ONDEMAND,
        freq_table=gpu_table,
    )
    print(f"Registered: {gpu.name}, freq range: {gpu.min_freq//1_000_000}-{gpu.max_freq//1_000_000} MHz")

    # Simulate load
    print("\n--- Simulating load ---")
    for i in range(5):
        update_stats("gpu", busy_ns=40_000_000 if i < 3 else 5_000_000)
        target = _simple_ondemand_get_target(gpu)
        set_frequency("gpu", target)
        stats = get_devfreq_stats("gpu")
        print(f"  Update {i+1}: load={stats.load_percent:.1f}%, freq={stats.current_freq//1_000_000} MHz")

    # Get stats
    stats = get_devfreq_stats("gpu")
    print(f"\nFinal: transitions={stats.total_transitions}, load={stats.load_percent:.1f}%")
    print(f"Frequencies: {[f//1_000_000 for f in get_available_frequencies('gpu')]} MHz")
    print(f"Latency: {get_transition_latency('gpu')} us")
