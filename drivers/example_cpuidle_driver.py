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

"""Example CPU Idle Driver for UmerOS.

This module demonstrates the kernel-like CPU idle management API with
proper idle state definitions, governor integration, and device registration.
"""

try:
    from .cpuidle import (
        CpuidleState,
        CpuidleDriver,
        SimpleGovernor,
        cpuidle_register_driver,
        cpuidle_register_governor,
        cpuidle_register,
    )
except ImportError:
    from cpuidle import (
        CpuidleState,
        CpuidleDriver,
        SimpleGovernor,
        cpuidle_register_driver,
        cpuidle_register_governor,
        cpuidle_register,
    )
import time


# ============================================================================
# Idle State Entry Functions
# ============================================================================

def wfi_enter(dev, drv, idx):
    """Wait For Interrupt - shallowest idle state."""
    time.sleep(0.001)
    print(f'[CPUIdle] Entered WFI state (cpu={dev.cpu_id})')


def stop_enter(dev, drv, idx):
    """STOP - deeper idle state with higher entry/exit latency."""
    time.sleep(0.005)
    print(f'[CPUIdle] Entered STOP state (cpu={dev.cpu_id})')


def s2idle_enter(dev, drv, idx):
    """Suspend-to-idle - deepest idle state."""
    time.sleep(0.01)
    print(f'[CPUIdle] Entered S2IDLE state (cpu={dev.cpu_id})')


# ============================================================================
# Idle State Definitions (kernel-like)
# ============================================================================

wfi_state = CpuidleState(
    name='WFI',
    target_residency=100,    # Minimum residency to save energy (us)
    exit_latency=10,         # Max time to start executing after wakeup (us)
    flags=0,                 # No special flags
    enter=wfi_enter,
)

stop_state = CpuidleState(
    name='STOP',
    target_residency=500,    # Needs 500us to be worth entering
    exit_latency=200,        # Takes up to 200us to wake up
    flags=0,
    enter=stop_enter,
)

s2idle_state = CpuidleState(
    name='S2IDLE',
    target_residency=2000,   # Needs 2ms to be worth entering
    exit_latency=500,        # Takes up to 500us to wake up
    flags=0,
    enter=s2idle_enter,
    enter_s2idle=s2idle_enter,
)


# ============================================================================
# Governor and Driver Registration
# ============================================================================

# Create governor with latency budget
governor = SimpleGovernor(
    name='SimpleGovernor',
    rating=100,
    max_latency=1000,  # Max wakeup latency budget (us)
)

# Create driver with all idle states
example_driver = CpuidleDriver(
    name='ExampleCpuidleDriver',
    states=[wfi_state, stop_state, s2idle_state],
    cpu_mask=[0],  # CPU 0 only
)

# Register governor first (it will become active)
cpuidle_register_governor(governor)

# Register the driver
cpuidle_register(example_driver)

# Register device for CPU 0
example_driver.register_devices([0])

# Export for external use
__all__ = ['example_driver', 'governor']
