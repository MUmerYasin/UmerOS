from typing import Callable, List, Optional, Dict, Any


class CpuidleState:
    """Represents an idle state for the CPU.

    Attributes:
        name (str): Human readable name of the state.
        target_residency (int): Minimum time to spend in this idle state
            including enter time to save more energy than shallower state,
            in microseconds.
        exit_latency (int): Maximum time to start executing after wakeup,
            in microseconds.
        flags (int): Flags representing idle state properties.
        enter (Callable[[], None]): Function to enter this idle state.
        enter_s2idle (Optional[Callable[[], None]]): Function for suspend-to-idle.
    """
    def __init__(
        self,
        name: str,
        target_residency: int,
        exit_latency: int,
        flags: int,
        enter: Callable[[], None],
        enter_s2idle: Optional[Callable[[], None]] = None,
    ):
        self.name = name
        self.target_residency = target_residency
        self.exit_latency = exit_latency
        self.flags = flags
        self.enter = enter
        self.enter_s2idle = enter_s2idle

    def __repr__(self) -> str:
        return f"CpuidleState(name={self.name}, residency={self.target_residency}, exit={self.exit_latency})"


class CpuidleDevice:
    """Represents a logical CPU device managed by a cpuidle driver.

    This mirrors the kernel's struct cpuidle_device, providing per-CPU context
    for governor operations and state selection.
    """
    def __init__(self, cpu_id: int, driver: 'CpuidleDriver'):
        self.cpu_id = cpu_id
        self.driver = driver
        self.active = False

    def enable(self):
        """Prepare governor for handling this CPU.
        
        To be implemented by the governor.
        """
        self.active = True

    def disable(self):
        """Stop handling this CPU.
        
        Reverse any changes made by enable().
        """
        self.active = False

    def __repr__(self) -> str:
        return f"CpuidleDevice(cpu={self.cpu_id}, driver={self.driver.name})"


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
    ):
        self.name = name
        self.states = states
        self.state_count = len(states)
        self.safe_state_index = self._find_safe_state()
        self.cpumask = cpu_mask
        self.devices: List[CpuidleDevice] = []
        self.active = False

    def _find_safe_state(self) -> int:
        """Find an idle state that is not "coupled".
        
        For simplicity, returns 0 if states[0].flags doesn't have a coupling flag.
        """
        # Assuming a flag bit indicates coupling; this is platform-specific.
        # Here we just return the first state as safe unless otherwise noted.
        return 0

    def register_devices(self, cpu_list: List[int]):
        """Register cpuidle_device objects for the given CPU list.
        
        This mirrors the kernel's cpuidle_register_device pattern.
        """
        for cpu_id in cpu_list:
            dev = CpuidleDevice(cpu_id, self)
            self.devices.append(dev)
        self.active = True

    def unregister_devices(self):
        """Unregister all devices managed by this driver.
        
        In the kernel, this is done before unregistering the driver.
        """
        self.devices.clear()
        self.active = False

    def pause_and_lock(self):
        """Temporarily disable CPUIdle for this driver.
        
        In the kernel, this is used when system configuration changes.
        """
        self.active = False

    def resume_and_unlock(self):
        """Resume CPUIdle after configuration changes.
        
        Re-enable devices after state updates.
        """
        self.active = True
        for dev in self.devices:
            dev.enable()

    def update_states(self, new_states: List[CpuidleState]):
        """Update the driver's idle states (e.g., after system config change).
        
        In the kernel, this is called with cpuidle_pause_and_lock and
        cpuidle_resume_and_unlock around it.
        """
        self.states = new_states
        self.state_count = len(new_states)

    def __repr__(self) -> str:
        return f"CpuidleDriver(name={self.name}, states={self.state_count})"


class CpuidleGovernor:
    """Abstract governor that selects an idle state.

    This implements the kernel's cpuidle_governor structure with callbacks
    enable, disable, select, and reflect.
    """
    def __init__(self, name: str, rating: int = 0):
        self.name = name
        self.rating = rating
        self.devices: List[CpuidleDevice] = []

    def enable(self, driver: CpuidleDriver, device: CpuidleDevice) -> int:
        """Prepare governor for handling a CPU.
        
        Return 0 on success, negative error code on failure.
        """
        self.devices.append(device)
        return 0

    def disable(self, driver: CpuidleDriver, device: CpuidleDevice):
        """Stop handling a CPU.
        
        Remove device from governor's tracking and cleanup.
        """
        if device in self.devices:
            self.devices.remove(device)

    def select(
        self, driver: CpuidleDriver, device: CpuidleDevice, stop_tick: bool
    ) -> int:
        """Select an idle state index for the given device.

        Return the index into driver.states, or negative error code.
        Override in subclasses.
        """
        raise NotImplementedError("Subclasses must implement select")

    def reflect(self, device: CpuidleDevice, index: int):
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


# Global registries mirroring kernel behavior
_CPUIDLE_GOVERNORS: List[CpuidleGovernor] = []
_CPUIDLE_DRIVERS: List[CpuidleDriver] = []


def cpuidle_register_governor(governor: CpuidleGovernor) -> int:
    """Register a new cpuidle governor.

    The governor is added to the global list. If it is the only one (list was
    empty before), or its rating is greater than the current governor's rating,
    or its name was passed via the cpuidle.governor= kernel command line,
    it becomes the active governor.
    """
    _CPUIDLE_GOVERNORS.append(governor)
    # Simple selection: first registered becomes active unless a higher-rated one exists.
    if len(_CPUIDLE_GOVERNORS) == 1 or governor.rating > max(g.rating for g in _CPUIDLE_GOVERNORS[:-1]):
        set_active_governor(governor)
    return 0


def set_active_governor(governor: CpuidleGovernor):
    """Set the active governor.

    In the kernel, this is done during registration when conditions are met.
    Here we just store the active governor reference.
    """
    # For simplicity, we don't have a separate active governor variable;
    # instead, we'll rely on get_active_cpuidle_governor() returning the first registered.
    pass


def get_active_cpuidle_governor() -> Optional[CpuidleGovernor]:
    """Return the currently active cpuidle governor, if any.

    In the kernel, this is determined by the registration logic.
    """
    if _CPUIDLE_GOVERNORS:
        return _CPUIDLE_GOVERNORS[0]
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


def cpuidle_register_device(governor: CpuidleGovernor, driver: CpuidleDriver, cpu_id: int) -> Optional[CpuidleDevice]:
    """Register a cpuidle_device object for a CPU.

    This creates the sysfs interface and invokes the governor's enable callback.
    """
    # Simple implementation: create device and register with governor.
    device = CpuidleDevice(cpu_id, driver)
    result = governor.enable(driver, device)
    if result == 0:
        driver.devices.append(device)
        return device
    return None


def cpuidle_unregister_device(governor: CpuidleGovernor, driver: CpuidleDriver, device: CpuidleDevice) -> None:
    """Unregister a cpuidle_device.

    This invokes the governor's disable callback and removes the device.
    """
    governor.disable(driver, device)
    if device in driver.devices:
        driver.devices.remove(device)


def cpuidle_pause_and_lock() -> None:
    """Temporarily disable CPUIdle for configuration changes.

    In the kernel, this is called before a driver updates its states.
    Here we just provide a placeholder.
    """
    pass


def cpuidle_resume_and_unlock() -> None:
    """Resume CPUIdle after configuration changes.

    This is called after a driver has updated its states.
    """
    pass

# Alias for backward compatibility with existing example code
def cpuidle_register(driver: CpuidleDriver) -> int:
    """Register a driver and its devices (simplified kernel interface).

    This mirrors the kernel's cpuidle_register() which registers both the driver
    and its devices in one call.
    """
    result = cpuidle_register_driver(driver)
    if result != 0:
        return result
    # For simplicity, we assume the driver manages its own device registration.
    return result


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
    idx = governor.select(driver, driver.devices[0] if driver.devices else None, False)
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
    active one. Here we return the first registered driver as a simplification.
    """
    if _CPUIDLE_DRIVERS:
        return _CPUIDLE_DRIVERS[0]
    return None


# Example usage (to be moved to a separate example file)
if __name__ == "__main__":
    # Define entry functions for idle states
    def wfi_enter():
        print("[CPUIdle] Entered WFI state")
        return "WFI"

    def stop_enter():
        print("[CPUIdle] Entered STOP state")
        return "STOP"

    # Create idle states with proper fields
    wfi_state = CpuidleState(
        name="WFI",
        target_residency=100,
        exit_latency=10,
        flags=0,  # Example flags
        enter=wfi_enter,
    )
    stop_state = CpuidleState(
        name="STOP",
        target_residency=500,
        exit_latency=200,
        flags=0,
        enter=stop_enter,
    )

    # Create and register the driver
    driver = CpuidleDriver(name="ExampleCpuidleDriver", states=[wfi_state, stop_state])
    cpuidle_register(driver)

    # Create a governor (use the kernel's SimpleGovernor equivalent)
    # For simplicity, we'll just use a basic governor that selects the lowest power state.
    class BasicGovernor(CpuidleGovernor):
        def __init__(self):
            super().__init__(name="BasicGovernor", rating=100)

        def select(
            self, driver: CpuidleDriver, device: CpuidleDevice, stop_tick: bool
        ) -> int:
            # Simple logic: return the lowest power usage state within latency budget.
            # This is a simplified version of the kernel's SimpleGovernor.
            eligible = [
                s for s in driver.states if s.exit_latency <= 1000
            ]
            if not eligible:
                return min(range(len(driver.states)), key=lambda i: driver.states[i].exit_latency)
            return min(
                range(len(eligible)),
                key=lambda i: eligible[i].target_residency,
            )

    basic_governor = BasicGovernor()
    cpuidle_register_governor(basic_governor)

    # Simulate device registration for CPU 0
    cpuidle_register_device(basic_governor, driver, 0)

    # Test entering an idle state
    result = cpuidle_enter()
    print(f"Entered state: {result}")
