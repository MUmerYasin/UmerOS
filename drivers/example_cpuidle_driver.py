from .cpuidle import CpuidleState, CpuidleDriver, cpuidle_register_driver
import time

# Define entry functions for idle states

def wfi_enter():
    # Simulate WFI (wait for interrupt) – just sleep a short time
    time.sleep(0.001)
    print('[CPUIdle] Entered WFI state')
    return 'WFI'

def stop_enter():
    # Simulate deeper STOP state – longer sleep
    time.sleep(0.005)
    print('[CPUIdle] Entered STOP state')
    return 'STOP'

# Create idle states
wfi_state = CpuidleState(name='WFI', latency=10, power_usage=0.5, enter=wfi_enter)
stop_state = CpuidleState(name='STOP', latency=200, power_usage=0.1, enter=stop_enter)

# Register the driver with the two states and default governor
example_driver = CpuidleDriver(name='ExampleCpuidleDriver', states=[wfi_state, stop_state])
cpuidle_register_driver(example_driver)
