from .cpuidle import CpuidleGovernor, CpuidleState, CpuidleDriver

class SimpleGovernor(CpuidleGovernor):
    """Select the idle state with the lowest power usage within a latency budget.

    The default max_latency is 1000 microseconds. It can be overridden by setting the
    ``max_latency`` attribute on the instance.
    """
    def __init__(self, max_latency: int = 1000):
        self.max_latency = max_latency

    def select_state(self, driver: CpuidleDriver) -> CpuidleState:
        eligible = [s for s in driver.states if s.latency <= self.max_latency]
        if not eligible:
            return min(driver.states, key=lambda s: s.latency)
        return min(eligible, key=lambda s: s.power_usage)
