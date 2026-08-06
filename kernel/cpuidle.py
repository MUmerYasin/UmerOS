# kernel/cpuidle.py
"""Stub cpuidle driver for UmerOS simulation.

A real implementation would talk to ACPI C-states or platform firmware.
This stub always returns a simulated idle state name.
"""

_IDLE_STATES = ["C1", "C2", "C3"]


def cpuidle_enter():
    """Enter a simulated CPU idle state.  Returns the state name or None."""
    import random
    return random.choice(_IDLE_STATES)
