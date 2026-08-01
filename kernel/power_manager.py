from . import cpuidle

class PowerManager:
    """Manages power‑related actions for the kernel.

    Currently it provides a simple ``cpu_idle`` method which invokes the
    registered ``cpuidle`` driver (if any) and returns the name of the idle
    state entered.
    """
    def cpu_idle(self):
        state_name = cpuidle.cpuidle_enter()
        if state_name is None:
            return 'No cpuidle driver registered – idle skipped.'
        return f'CPU entered idle state: {state_name}'

# Export a singleton instance used by the shell command.
POWER_MANAGER = PowerManager()
