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

#!/usr/bin/env python3
"""Example driver using the ioctl interface in UmerOS.

This script demonstrates how to register ioctl command handlers for a
`Device` instance and invoke them via the new `Device.ioctl` method.
It can be executed directly to see the workflow in action.
"""

# The script resides in the drivers package, so relative imports are used.
from .device import Device
from .ioctl import register_ioctl, _IOR, _IOW

# Define ioctl command numbers using simple encoding macros.
# For illustration we use a custom type 'M' (0x4d) and command numbers 1 and 2.
MY_IOCTL_GET_VALUE = _IOR(ord('M'), 1, 4)  # Read a 4‑byte integer.
MY_IOCTL_SET_VALUE = _IOW(ord('M'), 2, 4)  # Write a 4‑byte integer.

# Simple in‑memory state that the ioctl handlers will operate on.
_device_state = {"value": 0}


def _get_value(dev: Device) -> int:
    """Return the stored integer value for the device."""
    return _device_state["value"]


def _set_value(dev: Device, new_val: int) -> int:
    """Set a new integer value for the device.

    Returns 0 on success, matching typical ioctl conventions.
    """
    _device_state["value"] = new_val
    return 0


def main() -> None:
    # Create a device instance – this automatically registers the device.
    dev = Device(name="example_ioctl_dev", hardware_type="custom")

    # Register the ioctl handlers for this device.
    register_ioctl(dev, MY_IOCTL_GET_VALUE, _get_value)
    register_ioctl(dev, MY_IOCTL_SET_VALUE, _set_value)

    # Demonstrate reading the default value.
    print("[demo] Initial value via ioctl:", dev.ioctl(MY_IOCTL_GET_VALUE))

    # Update the value using the set ioctl.
    dev.ioctl(MY_IOCTL_SET_VALUE, 42)

    # Verify the new value.
    print("[demo] Value after ioctl set:", dev.ioctl(MY_IOCTL_GET_VALUE))

    # Clean‑up: unregister the commands (optional but tidy).
    from .ioctl import unregister_ioctl
    unregister_ioctl(dev, MY_IOCTL_GET_VALUE)
    unregister_ioctl(dev, MY_IOCTL_SET_VALUE)

    # Unregister the device from the global registry.
    from .device_registry import device_unregister
    device_unregister(dev)


if __name__ == "__main__":
    main()
