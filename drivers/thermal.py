"""
UmerOS Thermal Subsystem
========================
Kernel-like thermal management framework.
Implements thermal zones, cooling devices, governors,
and temperature monitoring with trip point management.

Mirrors the kernel's Documentation/driver-api/thermal/
and drivers/thermal/thermal_core.c (kernel 7.2.0-rc6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# Thermal Events (mirroring kernel thermal_event_id)
# ============================================================================

THERMAL_EVENT_NONE: int = 0
THERMAL_EVENT_TRIP_CHANGED: int = 1
THERMAL_EVENT_ENABLE: int = 2
THERMAL_EVENT_DISABLE: int = 3
THERMAL_EVENT_SENSOR_ERROR: int = 4

# Valid thermal governor policies
_THERMAL_POLICIES: List[str] = ["step_wise", "power_allocator", "bang_bang"]


# ============================================================================
# ThermalZone
# ============================================================================

@dataclass
class ThermalZone:
    """Represents a thermal zone (like /sys/class/thermal/thermal_zone*).

    Each zone wraps a temperature sensor and exposes trip points that
    trigger cooling actions through bound cooling devices.  The kernel
    maps this to ``struct thermal_zone_device``.

    Attributes:
        id: Unique numeric identifier.
        name: Human-readable label (e.g. "CPU Thermal").
        type: Sensor type string ("cpu", "gpu", "battery", "skin").
        temperature: Current temperature in millidegrees Celsius.
        passive: Passive cooling trip point (millideg C).
        active: Active cooling trip point (millideg C).
        hot: Hot trip point.
        critical: Critical trip point (emergency shutdown).
        policy: Current governor policy name.
        mode: "enabled" or "disabled".
    """

    id: int
    name: str
    type: str
    temperature: float = 0.0
    passive: int = 0
    active: int = 0
    hot: int = 0
    critical: int = 0
    policy: str = "step_wise"
    mode: str = "enabled"
    _trips: List[Dict[str, Any]] = field(default_factory=list)
    _devices: List[int] = field(default_factory=list)
    _event_log: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# ThermalCoolingDevice
# ============================================================================

@dataclass
class ThermalCoolingDevice:
    """Cooling device (fan, throttle, etc.).

    Mirrors ``struct thermal_cooling_device``.  Each device exposes a
    number of states (0 = off, max_state = maximum cooling effort) and
    the governor adjusts ``cur_state`` to reduce temperature.

    Attributes:
        id: Unique numeric identifier.
        name: Human-readable label.
        type: Device kind ("fan", "cpu_freq", "gpu_freq", "battery").
        max_state: Maximum cooling state (0 = no cooling).
        cur_state: Currently active cooling state.
    """

    id: int
    name: str
    type: str
    max_state: int
    cur_state: int = 0


# ============================================================================
# ThermalGovernor
# ============================================================================

@dataclass
class ThermalGovernor:
    """Thermal governor - decides cooling action.

    Mirrors ``struct thermal_governor``.  The governor is the policy
    engine that evaluates zone temperatures and adjusts bound cooling
    device states accordingly.

    Attributes:
        name: Governor name (must match a policy string).
        bind_to_zone: Optional callback invoked when bound to a zone.
        throttle: Optional callback invoked to perform cooling.
    """

    name: str
    bind_to_zone: Optional[Callable[..., Any]] = None
    throttle: Optional[Callable[..., Any]] = None


# ============================================================================
# Built-in Governors
# ============================================================================

class StepWiseGovernor(ThermalGovernor):
    """Step-wise governor - steps through cooling states.

    When temperature crosses a trip point the governor increments the
    cooling device state by one step; when temperature drops below the
    trip point it decrements by one step.  Simple and deterministic.
    """

    def __init__(self, name: str = "step_wise") -> None:
        super().__init__(name=name, bind_to_zone=self._bind, throttle=self._throttle)

    @staticmethod
    def _bind(zone: ThermalZone) -> None:
        """Bind callback - records that this governor manages *zone*."""
        pass

    @staticmethod
    def _throttle(zone: ThermalZone, devices: List[ThermalCoolingDevice]) -> None:
        """Step-wise throttling logic.

        For each bound cooling device, increase the state by 1 when
        temperature is above passive, decrease by 1 when below active.
        """
        for dev in devices:
            if zone.temperature >= zone.passive and zone.passive > 0:
                if dev.cur_state < dev.max_state:
                    dev.cur_state += 1
            elif zone.temperature < zone.active and zone.active > 0:
                if dev.cur_state > 0:
                    dev.cur_state -= 1


class PowerAllocatorGovernor(ThermalGovernor):
    """Power allocator - PID-based power budgeting.

    Distributes a total power budget across multiple cooling devices
    using a simple PID controller.  When temperature rises the budget
    is reduced, causing CPU/GPU frequency to drop proportionally.
    """

    def __init__(self, name: str = "power_allocator") -> None:
        super().__init__(name=name, bind_to_zone=self._bind, throttle=self._throttle)
        self._pid_integral: float = 0.0
        self._pid_prev_error: float = 0.0
        self._kp: float = 0.5
        self._ki: float = 0.1
        self._kd: float = 0.05
        self._sustainable_power: float = 15000.0  # milliwatts

    @staticmethod
    def _bind(zone: ThermalZone) -> None:
        pass

    def _throttle(self, zone: ThermalZone, devices: List[ThermalCoolingDevice]) -> None:
        """PID-based power budget allocation.

        Computes a correction factor based on the error between the
        desired temperature (midpoint between passive and critical) and
        the current temperature, then distributes that proportionally.
        """
        if not devices:
            return

        target = float(zone.passive) if zone.passive > 0 else float(zone.hot)
        if target <= 0.0:
            return

        error = zone.temperature - target
        self._pid_integral += error
        derivative = error - self._pid_prev_error
        self._pid_prev_error = error

        correction = (
            self._kp * error
            + self._ki * self._pid_integral
            + self._kd * derivative
        )

        # Map correction to a fraction (clamp to [0, 1])
        fraction = max(0.0, min(1.0, correction / target))

        for dev in devices:
            target_state = int(fraction * dev.max_state)
            dev.cur_state = max(0, min(dev.max_state, target_state))


class BangBangGovernor(ThermalGovernor):
    """Bang-bang governor - hysteresis-based on/off.

    When temperature exceeds the active trip the cooling device is set
    to maximum; when temperature drops below passive the device is
    turned off.  Simple on/off hysteresis control.
    """

    def __init__(self, name: str = "bang_bang") -> None:
        super().__init__(name=name, bind_to_zone=self._bind, throttle=self._throttle)

    @staticmethod
    def _bind(zone: ThermalZone) -> None:
        pass

    @staticmethod
    def _throttle(zone: ThermalZone, devices: List[ThermalCoolingDevice]) -> None:
        """Bang-bang hysteresis: full-on above active, full-off below passive."""
        for dev in devices:
            if zone.temperature >= zone.active and zone.active > 0:
                dev.cur_state = dev.max_state
            elif zone.temperature < zone.passive and zone.passive > 0:
                dev.cur_state = 0


# ============================================================================
# Global Registries
# ============================================================================

_zones: Dict[int, ThermalZone] = {}
_devices: Dict[int, ThermalCoolingDevice] = {}
_governors: Dict[str, ThermalGovernor] = {}
_zone_counter: int = 0
_device_counter: int = 0
_initialized: bool = False


def _next_zone_id() -> int:
    global _zone_counter
    _zone_counter += 1
    return _zone_counter


def _next_device_id() -> int:
    global _device_counter
    _device_counter += 1
    return _device_counter


# ============================================================================
# Zone Registration
# ============================================================================

def thermal_zone_register(
    name: str,
    type_: str,
    temp: float,
    passive: int = 0,
    active: int = 0,
    hot: int = 0,
    critical: int = 0,
    policy: str = "step_wise",
) -> ThermalZone:
    """Register a thermal zone - like thermal_zone_device_register().

    Creates a new ``ThermalZone``, assigns it a unique id, and stores
    it in the global zone registry.

    Returns:
        The newly created ``ThermalZone``.

    Raises:
        ValueError: If *policy* is not a recognised governor name.
    """
    if policy not in _THERMAL_POLICIES:
        raise ValueError(
            f"Unknown policy '{policy}'; expected one of {_THERMAL_POLICIES}"
        )

    zone = ThermalZone(
        id=_next_zone_id(),
        name=name,
        type=type_,
        temperature=temp,
        passive=passive,
        active=active,
        hot=hot,
        critical=critical,
        policy=policy,
    )
    _zones[zone.id] = zone
    return zone


def thermal_zone_unregister(zone_id: int) -> None:
    """Unregister - like thermal_zone_device_unregister().

    Removes the zone from the global registry and unbinds all cooling
    devices.
    """
    zone = _zones.pop(zone_id, None)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    zone._devices.clear()
    zone._trips.clear()


# ============================================================================
# Cooling Device Registration
# ============================================================================

def thermal_cooling_device_register(
    name: str, type_: str, max_state: int,
) -> ThermalCoolingDevice:
    """Register cooling device - like thermal_cooling_device_register().

    Returns:
        The newly created ``ThermalCoolingDevice``.
    """
    dev = ThermalCoolingDevice(
        id=_next_device_id(),
        name=name,
        type=type_,
        max_state=max_state,
    )
    _devices[dev.id] = dev
    return dev


def thermal_cooling_device_unregister(dev_id: int) -> None:
    """Unregister a cooling device from the global registry."""
    dev = _devices.pop(dev_id, None)
    if dev is None:
        raise KeyError(f"Cooling device {dev_id} not registered")


# ============================================================================
# Zone <-> Cooling Device Binding
# ============================================================================

def thermal_zone_bind_cooling_device(
    zone_id: int,
    dev_id: int,
    lower: int = 0,
    upper: int = 0,
) -> None:
    """Bind cooling device to zone.

    Mirrors the kernel's ``thermal_zone_bind_cooling_device()``.
    *lower* and *upper* represent the trip-point range within which
    this cooling device should operate.
    """
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    dev = _devices.get(dev_id)
    if dev is None:
        raise KeyError(f"Cooling device {dev_id} not registered")
    if dev_id not in zone._devices:
        zone._devices.append(dev_id)


def thermal_zone_unbind_cooling_device(zone_id: int, dev_id: int) -> None:
    """Unbind cooling device from zone."""
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    try:
        zone._devices.remove(dev_id)
    except ValueError:
        raise KeyError(
            f"Cooling device {dev_id} not bound to zone {zone_id}"
        )


# ============================================================================
# Temperature Queries
# ============================================================================

def thermal_zone_get_temp(zone_id: int) -> float:
    """Get temperature - like thermal_zone_get_temp().

    Returns the current temperature in millidegrees Celsius.
    """
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    return zone.temperature


# ============================================================================
# Trip Point Management
# ============================================================================

def thermal_zone_set_trips(zone_id: int, trips_dict: Dict[str, int]) -> None:
    """Set trip points for a zone.

    *trips_dict* may contain any of: "passive", "active", "hot", "critical".
    """
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    for key in ("passive", "active", "hot", "critical"):
        if key in trips_dict:
            setattr(zone, key, trips_dict[key])
    zone._event_log.append({
        "event": THERMAL_EVENT_TRIP_CHANGED,
        "time": time.time(),
        "trips": dict(trips_dict),
    })


# ============================================================================
# Zone Enable / Disable
# ============================================================================

def thermal_zone_device_enable(zone_id: int) -> None:
    """Enable zone."""
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    zone.mode = "enabled"
    zone._event_log.append({
        "event": THERMAL_EVENT_ENABLE,
        "time": time.time(),
    })


def thermal_zone_device_disable(zone_id: int) -> None:
    """Disable zone."""
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    zone.mode = "disabled"
    zone._event_log.append({
        "event": THERMAL_EVENT_DISABLE,
        "time": time.time(),
    })


# ============================================================================
# Governor Registration
# ============================================================================

def thermal_register_governor(governor: ThermalGovernor) -> None:
    """Register a thermal governor."""
    _governors[governor.name] = governor


# ============================================================================
# Policy Get / Set
# ============================================================================

def thermal_zone_get_policy(zone_id: int) -> str:
    """Get current policy."""
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    return zone.policy


def thermal_zone_set_policy(zone_id: int, policy: str) -> None:
    """Set policy for a zone.

    Raises:
        ValueError: If *policy* is not a recognised governor name.
    """
    if policy not in _THERMAL_POLICIES:
        raise ValueError(
            f"Unknown policy '{policy}'; expected one of {_THERMAL_POLICIES}"
        )
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    zone.policy = policy


# ============================================================================
# Netlink Event Simulation
# ============================================================================

def thermal_generate_netlink_event(zone_id: int, event: int) -> Dict[str, Any]:
    """Simulate thermal netlink event.

    In the real kernel this sends a ``THERMAL_NETLINK_EVENT`` to
    userspace.  Here we record the event in the zone's event log and
    return the payload.
    """
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    payload: Dict[str, Any] = {
        "zone_id": zone_id,
        "event": event,
        "time": time.time(),
    }
    zone._event_log.append(payload)
    return payload


# ============================================================================
# Cooling Device State Get / Set
# ============================================================================

def thermal_cooling_get_state(dev_id: int) -> int:
    """Get current cooling state."""
    dev = _devices.get(dev_id)
    if dev is None:
        raise KeyError(f"Cooling device {dev_id} not registered")
    return dev.cur_state


def thermal_cooling_set_state(dev_id: int, state: int) -> None:
    """Set cooling state (clamped to [0, max_state])."""
    dev = _devices.get(dev_id)
    if dev is None:
        raise KeyError(f"Cooling device {dev_id} not registered")
    dev.cur_state = max(0, min(dev.max_state, state))


# ============================================================================
# Emergency Shutdown
# ============================================================================

def thermal_shutdown_all() -> List[int]:
    """Emergency shutdown all zones above critical.

    Returns the list of zone ids that were shut down.
    """
    shutdown: List[int] = []
    for zone_id, zone in _zones.items():
        if zone.temperature >= zone.critical and zone.critical > 0:
            zone.mode = "disabled"
            zone._event_log.append({
                "event": THERMAL_EVENT_SENSOR_ERROR,
                "time": time.time(),
                "reason": "critical_temperature_exceeded",
            })
            # Set all bound cooling devices to maximum
            for dev_id in zone._devices:
                dev = _devices.get(dev_id)
                if dev is not None:
                    dev.cur_state = dev.max_state
            shutdown.append(zone_id)
    return shutdown


# ============================================================================
# Sysfs Interface (simulated)
# ============================================================================

def thermal_sys_get_temperature(zone_id: int) -> str:
    """Sysfs interface: /sys/class/thermal/thermal_zone*/temp

    Returns the temperature as a string matching the kernel's sysfs
    format (millidegrees Celsius, no decimal point).
    """
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    return str(int(zone.temperature))


def thermal_sys_get_type(zone_id: int) -> str:
    """Sysfs interface: /sys/class/thermal/thermal_zone*/type

    Returns the sensor type string.
    """
    zone = _zones.get(zone_id)
    if zone is None:
        raise KeyError(f"Thermal zone {zone_id} not registered")
    return zone.type


# ============================================================================
# Core Init / Shutdown
# ============================================================================

def thermal_core_init() -> None:
    """Initialize thermal core subsystem.

    Clears all registries and marks the subsystem as initialised.
    """
    global _initialized
    _zones.clear()
    _devices.clear()
    _governors.clear()
    global _zone_counter, _device_counter
    _zone_counter = 0
    _device_counter = 0
    _initialized = True


def thermal_core_shutdown() -> None:
    """Shutdown thermal core.

    Unregisters all zones, cooling devices, and governors.
    """
    global _initialized
    _zones.clear()
    _devices.clear()
    _governors.clear()
    _initialized = False


# ============================================================================
# Demo
# ============================================================================

if __name__ == "__main__":
    print("=== UmerOS Thermal Subsystem Demo ===\n")

    # Initialise the thermal core
    thermal_core_init()
    print(f"[Thermal] Core initialised: {_initialized}")

    # ------------------------------------------------------------------
    # 1. Register thermal zones
    # ------------------------------------------------------------------
    print("\n--- Registering Thermal Zones ---")
    cpu_zone = thermal_zone_register(
        name="CPU Thermal",
        type_="cpu",
        temp=45000,
        passive=70000,
        active=80000,
        hot=90000,
        critical=100000,
    )
    gpu_zone = thermal_zone_register(
        name="GPU Thermal",
        type_="gpu",
        temp=50000,
        passive=75000,
        active=85000,
        hot=95000,
        critical=105000,
    )
    battery_zone = thermal_zone_register(
        name="Battery Thermal",
        type_="battery",
        temp=35000,
        passive=45000,
        active=50000,
        hot=55000,
        critical=60000,
    )
    skin_zone = thermal_zone_register(
        name="Skin Thermal",
        type_="skin",
        temp=32000,
        passive=40000,
        active=42000,
        hot=45000,
        critical=50000,
    )
    for z in [cpu_zone, gpu_zone, battery_zone, skin_zone]:
        print(
            f"  Zone {z.id}: {z.name} type={z.type} "
            f"temp={z.temperature:.0f} passive={z.passive} "
            f"active={z.active} hot={z.hot} critical={z.critical}"
        )

    # ------------------------------------------------------------------
    # 2. Register cooling devices
    # ------------------------------------------------------------------
    print("\n--- Registering Cooling Devices ---")
    cpu_freq = thermal_cooling_device_register(
        name="CPU Freq Throttle", type_="cpu_freq", max_state=10,
    )
    gpu_freq = thermal_cooling_device_register(
        name="GPU Freq Throttle", type_="gpu_freq", max_state=8,
    )
    fan = thermal_cooling_device_register(
        name="System Fan", type_="fan", max_state=5,
    )
    for d in [cpu_freq, gpu_freq, fan]:
        print(f"  Device {d.id}: {d.name} type={d.type} max_state={d.max_state}")

    # ------------------------------------------------------------------
    # 3. Bind cooling devices to zones
    # ------------------------------------------------------------------
    print("\n--- Binding Cooling Devices to Zones ---")
    thermal_zone_bind_cooling_device(cpu_zone.id, cpu_freq.id)
    thermal_zone_bind_cooling_device(cpu_zone.id, fan.id)
    thermal_zone_bind_cooling_device(gpu_zone.id, gpu_freq.id)
    thermal_zone_bind_cooling_device(gpu_zone.id, fan.id)
    thermal_zone_bind_cooling_device(battery_zone.id, cpu_freq.id)
    thermal_zone_bind_cooling_device(skin_zone.id, fan.id)

    for z in [cpu_zone, gpu_zone, battery_zone, skin_zone]:
        bound_names = [
            _devices[did].name for did in z._devices if did in _devices
        ]
        print(f"  Zone {z.id} ({z.name}): bound devices = {bound_names}")

    # ------------------------------------------------------------------
    # 4. Register governors and set policies
    # ------------------------------------------------------------------
    print("\n--- Registering Governors ---")
    step_gov = StepWiseGovernor()
    palloc_gov = PowerAllocatorGovernor()
    bang_gov = BangBangGovernor()
    thermal_register_governor(step_gov)
    thermal_register_governor(palloc_gov)
    thermal_register_governor(bang_gov)
    print(f"  Registered governors: {list(_governors.keys())}")

    thermal_zone_set_policy(cpu_zone.id, "step_wise")
    thermal_zone_set_policy(gpu_zone.id, "power_allocator")
    thermal_zone_set_policy(battery_zone.id, "bang_bang")
    thermal_zone_set_policy(skin_zone.id, "step_wise")
    for z in [cpu_zone, gpu_zone, battery_zone, skin_zone]:
        print(f"  Zone {z.id} ({z.name}): policy = {thermal_zone_get_policy(z.id)}")

    # ------------------------------------------------------------------
    # 5. Update trip points
    # ------------------------------------------------------------------
    print("\n--- Updating Trip Points ---")
    thermal_zone_set_trips(cpu_zone.id, {"passive": 68000, "critical": 105000})
    print(
        f"  CPU zone updated: passive={cpu_zone.passive} "
        f"critical={cpu_zone.critical}"
    )

    # ------------------------------------------------------------------
    # 6. Simulate temperature updates and throttling
    # ------------------------------------------------------------------
    print("\n--- Temperature Updates & Throttling ---")
    scenarios = [
        ("CPU normal", cpu_zone.id, 50000),
        ("CPU passive reached", cpu_zone.id, 71000),
        ("CPU hot", cpu_zone.id, 91000),
        ("GPU warming", gpu_zone.id, 80000),
        ("Battery hot", battery_zone.id, 52000),
        ("Skin critical", skin_zone.id, 51000),
    ]

    for label, zone_id, temp in scenarios:
        zone = _zones[zone_id]
        zone.temperature = temp
        print(f"\n  [{label}] temp={temp}")

        # Get bound devices
        bound = [_devices[did] for did in zone._devices if did in _devices]
        gov = _governors.get(zone.policy)

        if gov and gov.throttle:
            gov.throttle(zone, bound)

        for d in bound:
            print(
                f"    {d.name}: state {d.cur_state}/{d.max_state}"
            )

    # ------------------------------------------------------------------
    # 7. Sysfs interface
    # ------------------------------------------------------------------
    print("\n--- Sysfs Interface ---")
    for z in [cpu_zone, gpu_zone, battery_zone, skin_zone]:
        temp_str = thermal_sys_get_temperature(z.id)
        type_str = thermal_sys_get_type(z.id)
        print(
            f"  /sys/class/thermal/thermal_zone{z.id}/temp  = {temp_str}"
        )
        print(
            f"  /sys/class/thermal/thermal_zone{z.id}/type   = {type_str}"
        )

    # ------------------------------------------------------------------
    # 8. Netlink events
    # ------------------------------------------------------------------
    print("\n--- Netlink Events ---")
    evt = thermal_generate_netlink_event(cpu_zone.id, THERMAL_EVENT_TRIP_CHANGED)
    print(f"  Event payload: {evt}")

    # ------------------------------------------------------------------
    # 9. Zone enable/disable
    # ------------------------------------------------------------------
    print("\n--- Zone Enable/Disable ---")
    thermal_zone_device_disable(gpu_zone.id)
    print(f"  GPU zone mode: {gpu_zone.mode}")
    thermal_zone_device_enable(gpu_zone.id)
    print(f"  GPU zone mode: {gpu_zone.mode}")

    # ------------------------------------------------------------------
    # 10. Emergency shutdown
    # ------------------------------------------------------------------
    print("\n--- Emergency Shutdown ---")
    # Push CPU zone above critical
    cpu_zone.temperature = 110000
    # Push battery zone above critical
    battery_zone.temperature = 65000
    # Push skin zone above critical
    skin_zone.temperature = 55000

    shutdown_zones = thermal_shutdown_all()
    print(f"  Zones shut down: {shutdown_zones}")
    for zid in shutdown_zones:
        z = _zones[zid]
        bound = [_devices[did].cur_state for did in z._devices if did in _devices]
        print(
            f"  Zone {zid} ({z.name}): mode={z.mode} "
            f"cooling_states={bound}"
        )

    # ------------------------------------------------------------------
    # 11. Cleanup
    # ------------------------------------------------------------------
    print("\n--- Cleanup ---")
    thermal_core_shutdown()
    print(f"  Core shutdown complete: initialized={_initialized}")
    print(f"  Remaining zones: {len(_zones)}, devices: {len(_devices)}")

    print("\n=== Demo Complete ===")
