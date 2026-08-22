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
