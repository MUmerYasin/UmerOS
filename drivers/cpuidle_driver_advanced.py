"""Advanced CPU Idle Driver for UmerOS.

This module implements kernel-like advanced CPU idle management features:
- PM QoS wakeup latency constraints per CPU
- Coupled idle state handling for multi-CPU coordination
- State flags (CPUIDLE_FLAG_POLLING, etc.)
- Dynamic state updates with pause/resume locks
- Per-CPU device registration with governor integration
- Governor selection with accuracy tracking and reflection

Mirrors the Linux kernel's cpuidle driver architecture as documented in
Documentation/admin-guide/pm/cpuidle.rst (kernel 7.2.0-rc6).
"""

from typing import Callable, List, Optional, Dict, Any, Set
try:
    from .cpuidle import (
        CpuidleState,
        CpuidleDevice,
        CpuidleDriver,
        CpuidleGovernor,
        cpuidle_register_driver,
        cpuidle_unregister_driver,
        cpuidle_register_governor,
        get_active_cpuidle_governor,
        get_active_cpuidle_driver,
        _CPUIDLE_DRIVERS,
        _CPUIDLE_GOVERNORS,
    )
except ImportError:
    from cpuidle import (
        CpuidleState,
        CpuidleDevice,
        CpuidleDriver,
        CpuidleGovernor,
        cpuidle_register_driver,
        cpuidle_unregister_driver,
        cpuidle_register_governor,
        get_active_cpuidle_governor,
        get_active_cpuidle_driver,
        _CPUIDLE_DRIVERS,
        _CPUIDLE_GOVERNORS,
    )


# ============================================================================
# State Flags (mirroring kernel cpuidle flags)
# ============================================================================

CPUIDLE_FLAG_POLLING = 1 << 0
"""State entry polls the idle time and does not indicate a real idle state."""


# ============================================================================
# PM QoS Latency Constraint Manager
# ============================================================================

class PmQosLatencyConstraint:
    """Manages per-CPU PM QoS wakeup latency constraints.

    In the kernel, PM QoS (Quality of Service) constraints limit the maximum
    wakeup latency the system can tolerate. This affects which idle states
    are available for selection by the governor.

    Each CPU can have its own constraint, and the effective constraint is
    the minimum of all active constraints for that CPU.
    """

    def __init__(self):
        self._constraints: Dict[int, List[int]] = {}
        self._global_constraint: int = 0

    def add_constraint(self, cpu_id: int, latency_us: int) -> None:
        """Add a PM QoS latency constraint for a CPU."""
        if cpu_id not in self._constraints:
            self._constraints[cpu_id] = []
        self._constraints[cpu_id].append(latency_us)

    def remove_constraint(self, cpu_id: int, latency_us: int) -> None:
        """Remove a specific PM QoS latency constraint for a CPU."""
        if cpu_id in self._constraints:
            try:
                self._constraints[cpu_id].remove(latency_us)
            except ValueError:
                pass

    def get_effective_latency(self, cpu_id: int) -> int:
        """Get the effective PM QoS latency constraint for a CPU.

        Returns the minimum of all active constraints for the CPU,
        or the global constraint if no CPU-specific constraints exist.
        """
        if cpu_id in self._constraints and self._constraints[cpu_id]:
            return min(self._constraints[cpu_id])
        return self._global_constraint

    def set_global_constraint(self, latency_us: int) -> None:
        """Set the global PM QoS latency constraint."""
        self._global_constraint = latency_us

    def clear_constraints(self, cpu_id: Optional[int] = None) -> None:
        """Clear PM QoS constraints for a specific CPU or all CPUs."""
        if cpu_id is not None:
            self._constraints.pop(cpu_id, None)
        else:
            self._constraints.clear()
            self._global_constraint = 0


# ============================================================================
# Advanced Governor
# ============================================================================

class AdvancedCpuidleGovernor(CpuidleGovernor):
    """Advanced governor implementing kernel-like idle state selection.

    Features:
    - PM QoS wakeup latency constraints
    - State selection with latency/power tradeoff
    - Selection accuracy tracking and reflection
    - Governor rating system for automatic selection
    """

    def __init__(self, name: str = "AdvancedGovernor", rating: int = 100,
                 max_latency: int = 1000):
        super().__init__(name=name, rating=rating)
        self.max_latency = max_latency
        self.pm_qos = PmQosLatencyConstraint()
        self.pm_qos.set_global_constraint(max_latency)
        self._selection_history: Dict[int, Dict[str, int]] = {}

    def select(
        self, driver: CpuidleDriver, device: Optional[CpuidleDevice],
        stop_tick: bool,
    ) -> int:
        """Select an idle state index for the given device.

        Algorithm (mirrors kernel menu governor):
        1. Query PM QoS latency constraint for the CPU
        2. Filter states that meet the latency requirement
        3. Among eligible states, prefer deeper states (lower power)
        4. If no eligible states, fallback to shallowest (lowest latency)
        5. Skip polling states unless stop_tick is True

        Returns:
            Index into driver.states, or -1 on error.
        """
        if device is None:
            return -1

        cpu_id = device.cpu_id
        pm_qos_latency = self.pm_qos.get_effective_latency(cpu_id)

        # Filter eligible states by PM QoS latency constraint
        eligible = []
        for i, state in enumerate(driver.states):
            # Skip polling states unless stop_tick is True
            if (state.flags & CPUIDLE_FLAG_POLLING) and not stop_tick:
                continue
            if state.exit_latency <= pm_qos_latency:
                eligible.append((i, state))

        if not eligible:
            # No states meet constraints - fallback to shallowest (lowest exit latency)
            fallback_idx = min(
                range(len(driver.states)),
                key=lambda i: driver.states[i].exit_latency,
            )
            self._record_selection(cpu_id, fallback_idx, accurate=False)
            return fallback_idx

        # Select the deepest eligible state (lowest target_residency = most power saving)
        # among states with acceptable exit latency
        best_idx, best_state = min(
            eligible, key=lambda pair: pair[1].target_residency,
        )

        self._record_selection(cpu_id, best_idx, accurate=True)
        return best_idx

    def reflect(self, device: CpuidleDevice, index: int) -> None:
        """Evaluate and improve selection accuracy after idle exit.

        Called after the CPU exits the idle state. The governor can use
        this to adjust its selection strategy based on actual residency
        vs predicted residency.
        """
        if device is None:
            return

        cpu_id = device.cpu_id
        if cpu_id not in self._selection_history:
            return

        stats = self._selection_history[cpu_id]
        total = stats.get("total", 0)
        if total > 100:
            accuracy = stats.get("accurate", 0) / total
            if accuracy < 0.7:
                # Low accuracy: bias toward shallower states
                self.max_latency = max(100, self.max_latency // 2)
                self.pm_qos.set_global_constraint(self.max_latency)
            elif accuracy > 0.95:
                # High accuracy: bias toward deeper states
                self.max_latency = min(10000, self.max_latency * 2)
                self.pm_qos.set_global_constraint(self.max_latency)

    def get_latency_req(self, cpu_id: int) -> int:
        """Return the current effective PM QoS wakeup latency constraint."""
        return self.pm_qos.get_effective_latency(cpu_id)

    def _record_selection(self, cpu_id: int, index: int, accurate: bool) -> None:
        """Record selection for accuracy tracking."""
        if cpu_id not in self._selection_history:
            self._selection_history[cpu_id] = {"total": 0, "accurate": 0}
        self._selection_history[cpu_id]["total"] += 1
        if accurate:
            self._selection_history[cpu_id]["accurate"] += 1


# ============================================================================
# Advanced Driver
# ============================================================================

class AdvancedCpuidleDriver(CpuidleDriver):
    """Advanced driver implementing kernel-like CPU idle management.

    Features:
    - Per-CPU device management with governor integration
    - Coupled idle state handling for multi-CPU coordination
    - Dynamic state updates with pause/resume locks
    - CPU mask support for CPU hotplug
    - PM QoS integration
    """

    def __init__(
        self,
        name: str,
        states: List[CpuidleState],
        cpu_mask: Optional[List[int]] = None,
        coupled_states: Optional[List[List[int]]] = None,
    ):
        super().__init__(name=name, states=states, cpu_mask=cpu_mask)
        self.coupled_states: List[List[int]] = coupled_states or []
        self._coupled_locks: Dict[int, bool] = {}
        self._pm_qos = PmQosLatencyConstraint()

    def register_devices_with_governor(
        self, cpu_list: List[int], governor: CpuidleGovernor,
    ) -> None:
        """Register devices for the given CPUs and associate with a governor.

        This mirrors the kernel's cpuidle_register_device() which creates
        the per-CPU cpuidle_device and invokes the governor's enable callback.
        """
        for cpu_id in cpu_list:
            device = CpuidleDevice(cpu_id, self)
            result = governor.enable(self, device)
            if result == 0:
                device.governor = governor
                self.devices.append(device)
        self.active = True

    def unregister_devices(self) -> None:
        """Unregister all devices managed by this driver.

        Invokes each device's disable callback before removal.
        """
        for dev in self.devices:
            dev.disable()
        self.devices.clear()
        self.active = False

    def pause_and_lock(self) -> None:
        """Temporarily disable CPUIdle for state updates.

        In the kernel, this prevents the governor from selecting states
        while the driver is being reconfigured.
        """
        self._paused = True
        for dev in self.devices:
            dev.disable()

    def resume_and_unlock(self) -> None:
        """Resume CPUIdle after state updates complete.

        Re-enables all devices and their governor associations.
        """
        self._paused = False
        for dev in self.devices:
            if dev.governor:
                dev.enable(dev.governor)

    def update_states_with_constraints(
        self,
        new_states: List[CpuidleState],
        cpu_latency_map: Optional[Dict[int, int]] = None,
    ) -> None:
        """Update idle states and optionally PM QoS constraints.

        This mirrors the kernel's response to runtime changes in idle state
        availability (e.g., CPU hotplug, thermal events).
        """
        self.pause_and_lock()
        self.update_states(new_states)
        if cpu_latency_map:
            for cpu_id, latency in cpu_latency_map.items():
                self._pm_qos.add_constraint(cpu_id, latency)
        self.resume_and_unlock()

    def enter_coupled_state(self, cpu_id: int, state_idx: int) -> bool:
        """Attempt to enter a coupled idle state.

        Coupled states require all CPUs in the coupling group to enter
        idle simultaneously. Returns True if the state was entered.
        """
        # Find the coupling group for this CPU
        coupling_group = None
        for group in self.coupled_states:
            if cpu_id in group:
                coupling_group = group
                break

        if coupling_group is None:
            return False

        # Check if all CPUs in the group are ready
        for other_cpu in coupling_group:
            if other_cpu == cpu_id:
                continue
            if self._coupled_locks.get(other_cpu, False):
                continue
            # Other CPU not ready - cannot enter coupled state
            return False

        # All CPUs ready - mark as entered
        self._coupled_locks[cpu_id] = True
        return True

    def exit_coupled_state(self, cpu_id: int) -> None:
        """Exit a coupled idle state."""
        self._coupled_locks[cpu_id] = False

    def get_effective_max_latency(self, cpu_id: int) -> int:
        """Get the effective max latency for a CPU from PM QoS."""
        return self._pm_qos.get_effective_latency(cpu_id)


# ============================================================================
# Backward-compatible SimpleGovernor
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
        self, driver: CpuidleDriver, device: Optional[CpuidleDevice],
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
# Module-level convenience functions
# ============================================================================

def cpuidle_pause_and_lock() -> None:
    """Temporarily disable CPUIdle for configuration changes."""
    driver = get_active_cpuidle_driver()
    if driver and hasattr(driver, 'pause_and_lock'):
        driver.pause_and_lock()


def cpuidle_resume_and_unlock() -> None:
    """Resume CPUIdle after configuration changes."""
    driver = get_active_cpuidle_driver()
    if driver and hasattr(driver, 'resume_and_unlock'):
        driver.resume_and_unlock()


# ============================================================================
# Demo
# ============================================================================

if __name__ == "__main__":
    import time

    print("=== UmerOS Advanced CPU Idle Driver Demo ===\n")

    # Define idle state entry functions
    def wfi_enter():
        time.sleep(0.001)
        print("[CPUIdle] Entered WFI state")

    def stop_enter():
        time.sleep(0.005)
        print("[CPUIdle] Entered STOP state")

    def polling_enter():
        time.sleep(0.0001)
        print("[CPUIdle] Entered POLLING state")

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
    polling_state = CpuidleState(
        name="POLL", target_residency=10, exit_latency=1,
        flags=CPUIDLE_FLAG_POLLING, enter=polling_enter,
    )
    s2idle_state = CpuidleState(
        name="S2IDLE", target_residency=2000, exit_latency=500,
        flags=0, enter=s2idle_enter, enter_s2idle=s2idle_enter,
    )

    # Create advanced driver with coupled states
    driver = AdvancedCpuidleDriver(
        name="AdvancedCpuidleDriver",
        states=[wfi_state, stop_state, s2idle_state, polling_state],
        cpu_mask=[0, 1],
        coupled_states=[[0, 1]],  # CPUs 0 and 1 are coupled for STOP
    )

    # Create advanced governor with PM QoS
    governor = AdvancedCpuidleGovernor(
        name="AdvancedGovernor", rating=100, max_latency=1000,
    )

    # Register governor and driver
    cpuidle_register_governor(governor)
    cpuidle_register_driver(driver)

    # Register devices for CPUs 0 and 1
    driver.register_devices_with_governor([0, 1], governor)

    print(f"Driver: {driver.name} ({driver.state_count} states)")
    print(f"Governor: {governor.name} (rating={governor.rating})")
    print(f"States: {[s.name for s in driver.states]}")
    print(f"Coupled groups: {driver.coupled_states}")
    print()

    # Demonstrate PM QoS constraints
    print("--- PM QoS Latency Constraints ---")
    for cpu_id in [0, 1]:
        latency = governor.get_latency_req(cpu_id)
        print(f"  CPU {cpu_id}: max wakeup latency = {latency} us")
    print()

    # Demonstrate state selection
    print("--- State Selection ---")
    for cpu_id in [0, 1]:
        device = next((d for d in driver.devices if d.cpu_id == cpu_id), None)
        if device:
            idx = governor.select(driver, device, stop_tick=False)
            if idx >= 0:
                state = driver.states[idx]
                print(f"  CPU {cpu_id} -> {state.name} "
                      f"(residency={state.target_residency}, exit={state.exit_latency})")
    print()

    # Demonstrate dynamic state update
    print("--- Dynamic State Update ---")
    new_states = [
        CpuidleState("IDLE0", 50, 5, 0, lambda: None),
        CpuidleState("IDLE1", 200, 50, 0, lambda: None),
        CpuidleState("IDLE2", 1000, 300, 0, lambda: None),
    ]
    driver.update_states_with_constraints(new_states, {0: 100, 1: 200})
    print(f"  Updated states: {[s.name for s in driver.states]}")
    for cpu_id in [0, 1]:
        latency = driver.get_effective_max_latency(cpu_id)
        print(f"  CPU {cpu_id} effective max latency = {latency} us")
    print()

    # Demonstrate pause/resume
    print("--- Pause/Resume ---")
    driver.pause_and_lock()
    print("  Driver paused (all devices disabled)")
    driver.resume_and_unlock()
    print("  Driver resumed (all devices re-enabled)")
    print()

    # Demonstrate governor reflection
    print("--- Governor Reflection ---")
    for cpu_id in [0, 1]:
        device = next((d for d in driver.devices if d.cpu_id == cpu_id), None)
        if device:
            governor.reflect(device, 0)
            print(f"  CPU {cpu_id} reflection complete")
    print()

    # Cleanup
    print("--- Cleanup ---")
    driver.unregister_devices()
    print("  Devices unregistered")
    print("\n=== Demo Complete ===")
