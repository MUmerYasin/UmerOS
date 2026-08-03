"""CPU Idle Governor for UmerOS.

This module provides the advanced CPU idle governor with PM QoS support,
selection accuracy tracking, and governor rating system.

Re-exports:
- AdvancedCpuidleGovernor: Governor with PM QoS, accuracy tracking, reflection
- SimpleGovernor: Backward-compatible governor (from cpuidle.py)
- CpuidleGovernor: Base governor class (from cpuidle.py)
"""

try:
    from .cpuidle import CpuidleGovernor, CpuidleState, CpuidleDriver, CpuidleDevice, SimpleGovernor
    from .cpuidle_driver_advanced import (
        AdvancedCpuidleGovernor,
        PmQosLatencyConstraint,
        CPUIDLE_FLAG_POLLING,
    )
except ImportError:
    from cpuidle import CpuidleGovernor, CpuidleState, CpuidleDriver, CpuidleDevice, SimpleGovernor
    from cpuidle_driver_advanced import (
        AdvancedCpuidleGovernor,
        PmQosLatencyConstraint,
        CPUIDLE_FLAG_POLLING,
    )

__all__ = [
    "CpuidleGovernor",
    "SimpleGovernor",
    "AdvancedCpuidleGovernor",
    "PmQosLatencyConstraint",
    "CPUIDLE_FLAG_POLLING",
]
