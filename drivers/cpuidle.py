import threading
from typing import Callable, List, Optional

class CpuidleState:
    """Represents an idle state for the CPU.

    Attributes:
        name (str): Human readable name of the state.
        latency (int): Maximum latency (in microseconds) entering this state incurs.
        power_usage (float): Approximate power consumption while in this state (mW).
        enter (Callable[[], None]): Function called to actually put the CPU in this state.
    """
    def __init__(self, name: str, latency: int, power_usage: float, enter: Callable[[], None]):
        self.name = name
        self.latency = latency
        self.power_usage = power_usage
        self.enter = enter

    def __repr__(self) -> str:
        return f"CpuidleState(name={self.name}, latency={self.latency}, power={self.power_usage})"

class CpuidleGovernor:
    """Abstract governor that selects an idle state.

    Sub‑classes must implement :meth:`select_state`.
    """
    def select_state(self, driver: "CpuidleDriver") -> CpuidleState:
        raise NotImplementedError

class SimpleGovernor(CpuidleGovernor):
    """Select the state with the lowest power usage while staying under a latency budget.

    The latency budget can be overridden by setting ``max_latency`` on the instance.
    """
    def __init__(self, max_latency: int = 1000):
        self.max_latency = max_latency

    def select_state(self, driver: "CpuidleDriver") -> CpuidleState:
        eligible = [s for s in driver.states if s.latency <= self.max_latency]
        if not eligible:
            return min(driver.states, key=lambda s: s.latency)
        return min(eligible, key=lambda s: s.power_usage)

class CpuidleDriver:
    """Driver that owns a list of idle states and a governor.

    The driver must be registered via :func:`cpuidle_register_driver`.
    """
    def __init__(self, name: str, states: List[CpuidleState], governor: Optional[CpuidleGovernor] = None):
        self.name = name
        self.states = states
        self.governor = governor or SimpleGovernor()
        self._active = False

    def start(self):
        self._active = True

    def stop(self):
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

# Registry for cpuidle drivers – only one active driver is expected for the primary CPU.
_CPUIDLE_DRIVERS: List[CpuidleDriver] = []

def cpuidle_register_driver(driver: CpuidleDriver):
    """Register a new cpuidle driver.

    The driver is added to the global list and started immediately.
    """
    _CPUIDLE_DRIVERS.append(driver)
    driver.start()

def get_active_cpuidle_driver() -> Optional[CpuidleDriver]:
    for d in _CPUIDLE_DRIVERS:
        if d.active:
            return d
    return None

def cpuidle_select_state() -> Optional[CpuidleState]:
    driver = get_active_cpuidle_driver()
    if driver is None:
        return None
    return driver.governor.select_state(driver)

def cpuidle_enter():
    """Enter the selected idle state.

    Returns the name of the state entered, or ``None`` if no driver is present.
    """
    state = cpuidle_select_state()
    if state is None:
        return None
    state.enter()
    return state.name
