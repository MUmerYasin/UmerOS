"""Core CPU Idle Management for UmerOS.

This module implements kernel-like CPU idle state management as documented in
Documentation/admin-guide/pm/cpuidle.rst (kernel 7.2.0-rc6).

Provides:
- CpuidleState: Kernel-like idle state with target_residency, exit_latency, flags
- CpuidleDevice: Per-CPU device with governor association
- CpuidleDriver: Driver managing idle states, CPU masks, coupled states, PM QoS
- CpuidleGovernor: Governor callbacks (enable/disable/select/reflect) with ratings
- Global registries for drivers and governors
- Registration/unregistration functions mirroring kernel behavior
- Backward-compatible SimpleGovernor
"""

from typing import Callable, List, Optional, Dict, Any
import time


# ============================================================================
# State Flags (mirroring kernel cpuidle flags)
# ============================================================================

CPUIDLE_FLAG_POLLING = 1 << 0
"""State entry polls the idle time and does not indicate a real idle state."""


# ============================================================================
# CpuidleState
# ============================================================================

class CpuidleState:
    """Represents an idle state for the CPU.

    Attributes:
        name (str): Human readable name of the state.
        target_residency (int): Minimum time to spend in this idle state
            including enter time to save more energy than shallower state,
            in microseconds.
        exit_latency (int): Maximum time to start executing after wakeup,
            in microseconds.
        flags (int): Flags representing idle state properties (CPUIDLE_FLAG_*).
        enter (Callable[[], None]): Function to enter this idle state.
        enter_s2idle (Optional[Callable[[], None]]): Function for suspend-to-idle.
        latency (int): Backward-compatible alias for exit_latency.
        power_usage (float): Backward-compatible power consumption field.
    """
    def __init__(
        self,
        name: str,
        target_residency: int = 0,
        exit_latency: int = 0,
        flags: int = 0,
        enter: Optional[Callable[[], None]] = None,
        enter_s2idle: Optional[Callable[[], None]] = None,
        # Backward-compatible parameters
        latency: Optional[int] = None,
        power_usage: Optional[float] = None,
    ):
        self.name = name
        # Kernel-like fields
        self.target_residency = target_residency
        self.exit_latency = exit_latency if exit_latency is not None else (latency or 0)
        self.flags = flags
        self.enter = enter or (lambda: None)
        self.enter_s2idle = enter_s2idle
        # Backward-compatible fields
        self.latency = self.exit_latency
        self.power_usage = power_usage or 0.0

    def __repr__(self) -> str:
        return (
            f"CpuidleState(name={self.name}, "
            f"target_residency={self.target_residency}, "
            f"exit_latency={self.exit_latency})"
        )


# ============================================================================
# CpuidleDevice
# ============================================================================

class CpuidleDevice:
    """Represents a logical CPU device managed by a cpuidle driver.

    This mirrors the kernel's struct cpuidle_device, providing per-CPU context
    for governor operations and state selection.
    """
    def __init__(self, cpu_id: int, driver: 'CpuidleDriver'):
        self.cpu_id = cpu_id
        self.driver = driver
        self.active = False
        self.governor: Optional['CpuidleGovernor'] = None
        self.last_state_idx: int = -1

    def enable(self, governor: Optional['CpuidleGovernor'] = None) -> int:
        """Prepare governor for handling this CPU.

        Return 0 on success, negative error code on failure.
        """
        self.active = True
        if governor:
            self.governor = governor
        return 0

    def disable(self) -> None:
        """Stop handling this CPU.

        Reverse any changes made by enable().
        """
        self.active = False
        self.governor = None

    def __repr__(self) -> str:
        return f"CpuidleDevice(cpu={self.cpu_id}, driver={self.driver.name})"


# ============================================================================
# CpuidleGovernor
# ============================================================================

class CpuidleGovernor:
    """Abstract governor that selects an idle state.

    This implements the kernel's cpuidle_governor structure with callbacks
    enable, disable, select, and reflect.
    """
    def __init__(self, name: str, rating: int = 0):
        self.name = name
        self.rating = rating
        self.devices: List[CpuidleDevice] = []

    def enable(self, driver: 'CpuidleDriver', device: CpuidleDevice) -> int:
        """Prepare governor for handling a CPU.

        Return 0 on success, negative error code on failure.
        """
        self.devices.append(device)
        return 0

    def disable(self, driver: 'CpuidleDriver', device: CpuidleDevice) -> None:
        """Stop handling a CPU.

        Remove device from governor's tracking and cleanup.
        """
        if device in self.devices:
            self.devices.remove(device)

    def select(
        self,
        driver: 'CpuidleDriver',
        device: Optional[CpuidleDevice],
        stop_tick: bool,
    ) -> int:
        """Select an idle state index for the given device.

        Return the index into driver.states, or negative error code.
        Override in subclasses.
        """
        raise NotImplementedError("Subclasses must implement select")

    def reflect(self, device: Optional[CpuidleDevice], index: int) -> None:
        """Evaluate and possibly improve accuracy of state selection.

        Called after a select() to allow governor to adjust for accuracy.
        """
        pass

    def get_latency_req(self, cpu_id: int) -> int:
        """Return the current effective PM QoS wakeup latency constraint.

        This is a placeholder implementation. Platforms should override.
        """
        return 0

    def __repr__(self) -> str:
        return f"CpuidleGovernor(name={self.name}, rating={self.rating})"


# ============================================================================
# CpuidleDriver
# ============================================================================

class CpuidleDriver:
    """Driver that owns a list of idle states and manages per-CPU devices.

    This provides the kernel-like driver interface with states,
    safe_state_index, cpumask, and device registration support.
    """
    def __init__(
        self,
        name: str,
        states: List[CpuidleState],
        cpu_mask: Optional[List[int]] = None,
        coupled_states: Optional[List[List[int]]] = None,
    ):
        self.name = name
        self.states = states
        self.state_count = len(states)
        self.safe_state_index = self._find_safe_state()
        self.cpumask = cpu_mask
        self.coupled_states = coupled_states or []
        self.devices: List[CpuidleDevice] = []
        self._active = False
        self._paused = False

    @property
    def active(self) -> bool:
        return self._active and not self._paused

    def _find_safe_state(self) -> int:
        """Find an idle state that is not "coupled".

        For simplicity, returns 0 unless overridden.
        """
        return 0

    def start(self) -> None:
        """Start the driver."""
        self._active = True

    def stop(self) -> None:
        """Stop the driver."""
        self._active = False

    def register_devices(self, cpu_list: List[int]) -> None:
        """Register cpuidle_device objects for the given CPU list.

        This mirrors the kernel's cpuidle_register_device pattern.
        """
        for cpu_id in cpu_list:
            dev = CpuidleDevice(cpu_id, self)
            self.devices.append(dev)
        self._active = True

    def unregister_devices(self) -> None:
        """Unregister all devices managed by this driver.

        In the kernel, this is done before unregistering the driver.
        """
        for dev in self.devices:
            dev.disable()
        self.devices.clear()
        self._active = False

    def pause_and_lock(self) -> None:
        """Temporarily disable CPUIdle for this driver.

        In the kernel, this is used when system configuration changes.
        """
        self._paused = True
        for dev in self.devices:
            dev.disable()

    def resume_and_unlock(self) -> None:
        """Resume CPUIdle after configuration changes.

        Re-enable devices after state updates.
        """
        self._paused = False
        for dev in self.devices:
            if dev.governor:
                dev.enable(dev.governor)

    def update_states(self, new_states: List[CpuidleState]) -> None:
        """Update the driver's idle states (e.g., after system config change).

        In the kernel, this is called with cpuidle_pause_and_lock and
        cpuidle_resume_and_unlock around it.
        """
        self.states = new_states
        self.state_count = len(new_states)
        self.safe_state_index = self._find_safe_state()

    def __repr__(self) -> str:
        return f"CpuidleDriver(name={self.name}, states={self.state_count})"


# ============================================================================
# Global Registries
# ============================================================================

_CPUIDLE_GOVERNORS: List[CpuidleGovernor] = []
_CPUIDLE_DRIVERS: List[CpuidleDriver] = []


def cpuidle_register_governor(governor: CpuidleGovernor) -> int:
    """Register a new cpuidle governor.

    The governor is added to the global list. If it is the only one (list was
    empty before), or its rating is greater than the current governor's rating,
    it becomes the active governor.
    """
    _CPUIDLE_GOVERNORS.append(governor)
    # Simple selection: first registered becomes active unless a higher-rated one exists.
    if len(_CPUIDLE_GOVERNORS) == 1 or governor.rating > max(
        g.rating for g in _CPUIDLE_GOVERNORS[:-1]
    ):
        set_active_governor(governor)
    return 0


def set_active_governor(governor: CpuidleGovernor) -> None:
    """Set the active governor.

    In the kernel, this is done during registration when conditions are met.
    """
    pass  # Active governor is determined by get_active_cpuidle_governor()


def get_active_cpuidle_governor() -> Optional[CpuidleGovernor]:
    """Return the currently active cpuidle governor, if any.

    In the kernel, this is determined by the registration logic.
    Returns the governor with the highest rating.
    """
    if _CPUIDLE_GOVERNORS:
        return max(_CPUIDLE_GOVERNORS, key=lambda g: g.rating)
    return None


def cpuidle_register_driver(driver: CpuidleDriver) -> int:
    """Register a new cpuidle driver.

    The driver is added to the global list and started immediately.
    """
    _CPUIDLE_DRIVERS.append(driver)
    driver.start()
    return 0


def cpuidle_unregister_driver(driver: CpuidleDriver) -> int:
    """Unregister a cpuidle driver.

    All devices for this driver must be unregistered first.
    """
    if driver in _CPUIDLE_DRIVERS:
        _CPUIDLE_DRIVERS.remove(driver)
        driver.stop()
    return 0


def cpuidle_register_device(
    governor: CpuidleGovernor,
    driver: CpuidleDriver,
    cpu_id: int,
) -> Optional[CpuidleDevice]:
    """Register a cpuidle_device object for a CPU.

    This creates the device and invokes the governor's enable callback.
    """
    device = CpuidleDevice(cpu_id, driver)
    result = governor.enable(driver, device)
    if result == 0:
        device.governor = governor
        driver.devices.append(device)
        return device
    return None


def cpuidle_unregister_device(
    governor: CpuidleGovernor,
    driver: CpuidleDriver,
    device: CpuidleDevice,
) -> None:
    """Unregister a cpuidle_device.

    This invokes the governor's disable callback and removes the device.
    """
    governor.disable(driver, device)
    if device in driver.devices:
        driver.devices.remove(device)


def cpuidle_pause_and_lock() -> None:
    """Temporarily disable CPUIdle for configuration changes.

    In the kernel, this is called before a driver updates its states.
    """
    driver = get_active_cpuidle_driver()
    if driver:
        driver.pause_and_lock()


def cpuidle_resume_and_unlock() -> None:
    """Resume CPUIdle after configuration changes.

    This is called after a driver has updated its states.
    """
    driver = get_active_cpuidle_driver()
    if driver:
        driver.resume_and_unlock()


def cpuidle_register(driver: CpuidleDriver) -> int:
    """Register a driver and its devices (simplified kernel interface).

    This mirrors the kernel's cpuidle_register() which registers both the driver
    and its devices in one call.
    """
    return cpuidle_register_driver(driver)


def cpuidle_unregister(driver: CpuidleDriver) -> int:
    """Unregister a driver and its devices.

    This is the opposite of cpuidle_register.
    """
    driver.unregister_devices()
    return cpuidle_unregister_driver(driver)


def cpuidle_select_state() -> Optional[CpuidleState]:
    """Select an idle state for the active driver.

    This is the core function used by the example driver.
    """
    driver = get_active_cpuidle_driver()
    if driver is None:
        return None
    governor = get_active_cpuidle_governor()
    if governor is None:
        return None
    device = driver.devices[0] if driver.devices else None
    idx = governor.select(driver, device, False)
    if idx < 0 or idx >= len(driver.states):
        return None
    return driver.states[idx]


def cpuidle_enter() -> Optional[str]:
    """Enter the selected idle state.

    Returns the name of the state entered, or None if no driver is present.
    """
    state = cpuidle_select_state()
    if state is None:
        return None
    state.enter()
    return state.name


def get_active_cpuidle_driver() -> Optional[CpuidleDriver]:
    """Return the currently active cpuidle driver, if any.

    In the kernel, this iterates over registered drivers and returns the first
    active one. Here we return the first active registered driver.
    """
    for d in _CPUIDLE_DRIVERS:
        if d.active:
            return d
    return None


# ============================================================================
# Backward-Compatible SimpleGovernor
# ============================================================================

class SimpleGovernor(CpuidleGovernor):
    """Simple governor selecting lowest-power state within latency budget.

    This is a backward-compatible governor that mirrors the kernel's
    simple_idle governor behavior.
    """
    def __init__(self, name: str = "SimpleGovernor", rating: int = 20,
                 max_latency: int = 1000):
        super().__init__(name=name, rating=rating)
        self.max_latency = max_latency

    def select(
        self,
        driver: CpuidleDriver,
        device: Optional[CpuidleDevice],
        stop_tick: bool,
    ) -> int:
        """Select lowest power state within latency budget."""
        eligible = [
            (i, s) for i, s in enumerate(driver.states)
            if s.exit_latency <= self.max_latency
            and not (s.flags & CPUIDLE_FLAG_POLLING and not stop_tick)
        ]
        if not eligible:
            return min(
                range(len(driver.states)),
                key=lambda i: driver.states[i].exit_latency,
            )
        return min(eligible, key=lambda pair: pair[1].target_residency)[0]


# ============================================================================
# Example Demo
# ============================================================================

if __name__ == "__main__":
    print("=== UmerOS CPU Idle Core Demo ===\n")

    # Define idle state entry functions
    def wfi_enter():
        time.sleep(0.001)
        print("[CPUIdle] Entered WFI state")

    def stop_enter():
        time.sleep(0.005)
        print("[CPUIdle] Entered STOP state")

    def s2idle_enter():
        time.sleep(0.01)
        print("[CPUIdle] Entered S2IDLE state")

    # Create idle states with kernel-like attributes
    wfi_state = CpuidleState(
        name="WFI", target_residency=100, exit_latency=10,
        flags=0, enter=wfi_enter,
    )
    stop_state = CpuidleState(
        name="STOP", target_residency=500, exit_latency=200,
        flags=0, enter=stop_enter,
    )
    s2idle_state = CpuidleState(
        name="S2IDLE", target_residency=2000, exit_latency=500,
        flags=0, enter=s2idle_enter, enter_s2idle=s2idle_enter,
    )

    # Create driver
    driver = CpuidleDriver(
        name="ExampleCpuidleDriver",
        states=[wfi_state, stop_state, s2idle_state],
        cpu_mask=[0, 1],
    )

    # Create governor
    governor = SimpleGovernor(name="SimpleGovernor", rating=100, max_latency=1000)

    # Register governor and driver
    cpuidle_register_governor(governor)
    cpuidle_register_driver(driver)

    # Register devices for CPUs 0 and 1
    driver.register_devices([0, 1])

    print(f"Driver: {driver.name} ({driver.state_count} states)")
    print(f"Governor: {governor.name} (rating={governor.rating})")
    print(f"States: {[s.name for s in driver.states]}")
    print(f"Devices: {[d.cpu_id for d in driver.devices]}")
    print()

    # Test state selection and entry
    print("--- State Selection and Entry ---")
    for i in range(3):
        result = cpuidle_enter()
        if result:
            print(f"  Iteration {i+1}: Entered state = {result}")
    print()

    # Test pause/resume
    print("--- Pause/Resume ---")
    cpuidle_pause_and_lock()
    print("  Driver paused")
    cpuidle_resume_and_unlock()
    print("  Driver resumed")
    print()

    # Test dynamic state update
    print("--- Dynamic State Update ---")
    new_states = [
        CpuidleState("IDLE0", 50, 5, 0, lambda: None),
        CpuidleState("IDLE1", 200, 50, 0, lambda: None),
    ]
    driver.pause_and_lock()
    driver.update_states(new_states)
    driver.resume_and_unlock()
    print(f"  Updated states: {[s.name for s in driver.states]}")
    print()

    # Cleanup
    print("--- Cleanup ---")
    cpuidle_unregister(driver)
    print("  Driver unregistered")
    print("\n=== Demo Complete ===")
