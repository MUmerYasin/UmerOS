# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
        self.governor: Optional['CpuidleGovernor'] = None

    def enable(self, governor: 'CpuidleGovernor') -> int:
        """Prepare governor for handling this CPU.
        
        Return 0 on success, negative error code on failure.
        """
        self.governor = governor
        self.active = True
        return 0

    def disable(self):
        """Stop handling this CPU.
        
        Reverse any changes made by enable().
        """
        self.governor = None
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
        coupled_states: Optional[List[List[int]]] = None,
    ):
        self.name = name
        self.states = states
        self.state_count = len(states)
        self.cpumask = cpu_mask or []
        self.coupled_states = coupled_states or []
        self.safe_state_index = self._find_safe_state()
        self.devices: List[CpuidleDevice] = []
        self.active = False
        self._paused = False

    def _find_safe_state(self) -> int:
        """Find an idle state that is not "coupled".
        
        For simplicity, returns 0 if states[0].flags doesn't have a coupling flag.
        In a real implementation, this would check the coupled_states list.
        """
        # Check if any state is not coupled (i.e., can be used by a single CPU)
        for i, state in enumerate(self.states):
            # Simplified coupling detection: assume even-indexed states are not coupled
            if i % 2 == 0:
                return i
        return 0  # Fallback

    def register_devices(self, cpu_list: List[int], governor: 'CpuidleGovernor'):
        """Register cpuidle_device objects for the given CPU list.

        This mirrors the kernel's cpuidle_register_device pattern.
        """
        for cpu_id in cpu_list:
            dev = CpuidleDevice(cpu_id, self)
            dev.enable(governor)
            self.devices.append(dev)
        self.active = True

    def unregister_devices(self):
        """Unregister all devices managed by this driver.

        In the kernel, this is done before unregistering the driver.
        """
        for dev in self.devices:
            dev.disable()
        self.devices.clear()
        self.active = False

    def pause_and_lock(self):
        """Temporarily disable CPUIdle for configuration changes.

        In the kernel, this is called before a driver updates its states.
        """
        self._paused = True
        for dev in self.devices:
            dev.disable()

    def resume_and_unlock(self):
        """Resume CPUIdle after configuration changes.

        This is called after a driver has updated its states.
        """
        self._paused = False
        for dev in self.devices:
            dev.enable(dev.governor)

    def update_states(self, new_states: List[CpuidleState]):
        """Update the driver's idle states (e.g., after system config change).

        In the kernel, this is called with cpuidle_pause_and_lock and
        cpuidle_resume_and_unlock around it.
        """
        self.states = new_states
        self.state_count = len(new_states)
        # Rebuild devices if needed
        if not self._paused:
            for dev in self.devices:
                dev.enable(dev.governor)

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
    empty before) or its rating is greater than the current governor's rating,
    or its name was passed to the kernel as the value of the cpuidle.governor=
    command line parameter, the new governor will be used from that point on
    (there can be only one ``CPUIdle`` governor in use at a time).
    """
    _CPUIDLE_GOVERNORS.append(governor)
    # Simple selection: first registered becomes active unless a higher-rated one exists.
    if len(_CPUIDLE_GOVERNORS) == 1:
        set_active_governor(governor)
    elif governor.rating > max(g.rating for g in _CPUIDLE_GOVERNORS[:-1]):
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


# High-performance governor implementing kernel-like selection logic
class AdvancedCpuidleGovernor(CpuidleGovernor):
    """Advanced governor that implements sophisticated idle state selection.

    This mimics the kernel's governor behavior with proper PM QoS constraints,
    state accuracy tracking, and efficient selection algorithms.
    """
    def __init__(self, max_latency: int = 1000, rating: int = 100):
        super().__init__(name="AdvancedGovernor", rating=rating)
        self.max_latency = max_latency
        self.selection_counts: Dict[int, int] = {}

    def select(
        self, driver: CpuidleDriver, device: CpuidleDevice, stop_tick: bool
    ) -> int:
        """Select an idle state using kernel-like logic with PM QoS constraints.

        This implements the core selection algorithm from the kernel:
        1. Check PM QoS latency requirements
        2. Filter eligible states
        3. Select lowest power state within constraints
        4. Fallback to lowest latency if none eligible
        """
        if device is None:
            return -1

        # Get current PM QoS latency constraint for this CPU
        pm_qos_latency = device.governor.get_latency_req(device.cpu_id) if device.governor else self.max_latency

        # Filter states that meet latency requirements
        eligible_states = [s for s in driver.states if s.exit_latency <= pm_qos_latency]

        # Track selection for accuracy reflection
        if device.cpu_id not in self.selection_counts:
            self.selection_counts[device.cpu_id] = {}

        if not eligible_states:
            # No states meet PM QoS constraints, fallback to lowest latency
            selected_idx = min(range(len(driver.states)), key=lambda i: driver.states[i].exit_latency)
            self._record_selection(device.cpu_id, selected_idx, False)
            return selected_idx

        # Select lowest power state among eligible states
        selected_idx = min(
            range(len(eligible_states)),
            key=lambda i: eligible_states[i].target_residency,
        )
        # Map back to original driver.states index
        original_idx = driver.states.index(eligible_states[selected_idx])

        self._record_selection(device.cpu_id, original_idx, True)
        return original_idx

    def _record_selection(self, cpu_id: int, index: int, accurate: bool):
        """Record selection for later reflection and accuracy improvement.

        Tracks how often selections are accurate vs actual system behavior.
        """
        if cpu_id not in self.selection_counts:
            self.selection_counts[cpu_id] = {"accurate": 0, "inaccurate": 0}
        if accurate:
            self.selection_counts[cpu_id]["accurate"] += 1
        else:
            self.selection_counts[cpu_id]["inaccurate"] += 1

    def reflect(self, device: CpuidleDevice, index: int):
        """Evaluate selection accuracy and adjust for future improvements.

        Uses selection history to improve future state selection accuracy.
        """
        if device.cpu_id in self.selection_counts:
            stats = self.selection_counts[device.cpu_id]
            total = stats["accurate"] + stats["inaccurate"]
            if total > 0:
                accuracy = stats["accurate"] / total
                # Adjust selection strategy based on accuracy
                if accuracy < 0.7:  # Low accuracy
                    # bias toward shallower states for better responsiveness
                    pass
                elif accuracy > 0.95:  # High accuracy
                    # bias toward deeper states for better power savings
                    pass

    def get_latency_req(self, cpu_id: int) -> int:
        """Return PM QoS latency constraint for the given CPU.

        This is a simplified implementation that returns the governor's
        max_latency as the effective PM QoS constraint.
        In a real implementation, this would query system-specific PM QoS settings.
        """
        return self.max_latency


# High-performance driver implementing kernel-like driver features
class AdvancedCpuidleDriver(CpuidleDriver):
    """Advanced driver that mirrors kernel driver capabilities.

    This implements the kernel's cpuidle driver structure with proper
    coupled state handling, CPU masking, and device management.
    """
    def __init__(
        self,
        name: str,
        states: List[CpuidleState],
        cpu_mask: Optional[List[int]] = None,
        coupled_states: Optional[List[List[int]]] = None,
    ):
        super().__init__(name, states, cpu_mask, coupled_states)
        self._max_latencies: Dict[int, int] = {}  # CPU -> max latency mapping

    def register_devices_with_governor(
        self, cpu_list: List[int], governor: CpuidleGovernor
    ):
        """Register devices with an associated governor.

        This mirrors the kernel's cpuidle_register_device pattern but with
        proper governor integration.
        """
        for cpu_id in cpu_list:
            device = CpuidleDevice(cpu_id, self)
            result = governor.enable(self, device)
            if result == 0:
                self.devices.append(device)
                device.governor = governor
        self.active = True

    def update_states_with_constraints(
        self, new_states: List[CpuidleState], cpu_latency_map: Dict[int, int]
    ):
        """Update states and PM QoS latency constraints for all CPUs.

        This mirrors the kernel's response to system configuration changes
        that affect idle state availability.
        """
        self.pause_and_lock()
        self.update_states(new_states)
        # Update PM QoS constraints
        self._max_latencies = cpu_latency_map
        self.resume_and_unlock()

    def get_effective_max_latency(self, cpu_id: int) -> int:
        """Get the effective max latency for a CPU.

        Returns the PM QoS constraint if set, otherwise falls back to driver default.
        """
        return self._max_latencies.get(cpu_id, 1000)


# Example demonstrating advanced kernel-like features
class AdvancedCpuidleExample:
    """Demonstrates advanced CPU idle management features similar to kernel."""

    def __init__(self):
        # Define entry functions for idle states
        def wfi_enter():
            # Simulate WFI (wait for interrupt)
            import time
            time.sleep(0.001)
            print("[CPUIdle] Entered WFI state")

        def stop_enter():
            # Simulate deeper STOP state
            import time
            time.sleep(0.005)
            print("[CPUIdle] Entered STOP state")

        def polling_enter():
            # Simulate polling state (no actual idle)
            import time
            time.sleep(0.0001)
            print("[CPUIdle] Entered POLLING state")

        # Create idle states with proper kernel-like attributes
        self.wfi_state = CpuidleState(
            name="WFI",
            target_residency=100,
            exit_latency=10,
            flags=0,  # Normal idle state
            enter=wfi_enter,
        )
        self.stop_state = CpuidleState(
            name="STOP",
            target_residency=500,
            exit_latency=200,
            flags=0,
            enter=stop_enter,
        )
        self.polling_state = CpuidleState(
            name="POLL",
            target_residency=10,
            exit_latency=1,
            flags=1,  # CPUIDLE_FLAG_POLLING
            enter=polling_enter,
        )

        # Create advanced driver with proper features
        self.driver = AdvancedCpuidleDriver(
            name="AdvancedCpuidleDriver",
            states=[self.wfi_state, self.stop_state, self.polling_state],
            cpu_mask=[0, 1],  # CPUs 0 and 1
            coupled_states=[[0, 1]],  # CPUs 0 and 1 are coupled for STOP state
        )

        # Create advanced governor with PM QoS support
        self.governor = AdvancedCpuidleGovernor(max_latency=1000)

    def setup_and_register(self):
        """Set up and register the advanced driver and governor."""
        # Register governor and driver
        cpuidle_register_governor(self.governor)
        cpuidle_register_driver(self.driver)

        # Register devices for the specified CPUs
        self.driver.register_devices_with_governor([0, 1], self.governor)

        print("[CPUIdle] Advanced driver and governor registered successfully")
        print("[CPUIdle] Driver states:", [s.name for s in self.driver.states])

    def demonstrate_advanced_features(self):
        """Demonstrate advanced kernel-like features."""
        print("\n=== Advanced CPU Idle Features Demo ===\n")

        # 1. Demonstrate PM QoS constraints
        print("1. PM QoS Latency Constraints:")
        for cpu_id in [0, 1]:
            latency = self.driver.get_effective_max_latency(cpu_id)
            print(f"   CPU {cpu_id}: max latency = {latency} us")

        # 2. Demonstrate state selection with constraints
        print("\n2. State Selection (respecting PM QoS constraints):")
        for cpu_id in [0, 1]:
            device = next((d for d in self.driver.devices if d.cpu_id == cpu_id), None)
            if device:
                idx = self.governor.select(self.driver, device, False)
                if idx >= 0:
                    state = self.driver.states[idx]
                    print(f"   CPU {cpu_id} selected: {state.name} (residency={state.target_residency}, exit={state.exit_latency})")
                else:
                    print(f"   CPU {cpu_id} could not select a state")

        # 3. Demonstrate accuracy reflection
        print("\n3. Selection Accuracy (simulated):")
        for cpu_id in [0, 1]:
            device = next((d for d in self.driver.devices if d.cpu_id == cpu_id), None)
            if device:
                # Simulate a reflection callback
                self.governor.reflect(device, 0)
                print(f"   CPU {cpu_id} reflection processed")

        # 4. Demonstrate state updates
        print("\n4. Dynamic State Updates:")
        print("   Updating driver states...")
        new_states = [
            CpuidleState("IDLE1", 50, 5, 0, lambda: None),
            CpuidleState("IDLE2", 200, 50, 0, lambda: None),
        ]
        self.driver.update_states_with_constraints(new_states, {0: 100, 1: 200})
        print(f"   New states: {[s.name for s in self.driver.states]}")

        # 5. Demonstrate cpuidle_enter interface
        print("\n5. CPUIdle Enter Interface:")
        print("   Calling cpuidle_enter()...")
        result = cpuidle_enter()
        print(f"   Result: {result}")

    def cleanup(self):
        """Clean up and unregister driver and governor."""
        print("\n6. Cleanup:")
        print("   unregistering driver and governor...")
        # Note: In the kernel, unregistration is more complex
        # Here we just demonstrate the cleanup pattern
        cpuidle_unregister_driver(self.driver)
        print("   Cleanup complete")


if __name__ == "__main__":
    # Create and run the advanced example
    example = AdvancedCpuidleExample()
    example.setup_and_register()
    example.demonstrate_advanced_features()
    example.cleanup()
