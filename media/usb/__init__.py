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

"""
UmerOS /media/usb - USB Drive Support
=========================================

USB drive support for UmerOS.  The package
is self-contained (standard library only)
and exposes three sub-modules:

* :mod:`media.usb.device`  - sysfs discovery
  of USB devices (root hubs ``usbN``, chain
  devices ``N-M[.x]*`` and interfaces
  ``N-M:y.z``), device-class decoding, link
  speed names, and parsers for plain, verbose
  and tree ``lsusb`` output, with a
  simulation mode for hosts without USB
  hardware.
* :mod:`media.usb.storage` - maps block
  devices (``/dev/sdX``) to their backing
  USB device by resolving the sysfs symlink
  chain, and gathers capacity, removability,
  read-only state and filesystem metadata.
* :mod:`media.usb.cli`     - read-only
  wrapper around ``lsusb`` plus privileged
  device-control operations (authorize /
  remove / reset) gated behind the
  zero-trust capability bridge
  (``CAP_SYS_ADMIN``).

Quick start::

    from media.usb.device import discover_usb_devices
    from media.usb.storage import discover_usb_storage

    for dev in discover_usb_devices():
        print(dev.name, dev.product, dev.speed_name)

    for disk in discover_usb_storage():
        print(disk.device_path, disk.usb.product,
              disk.size_bytes)

This package is ``[REFERENCE-ONLY]`` - it is
not imported by ``main.py``.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

from .device import (
    CLASS_AUDIO,
    CLASS_AUDIO_VIDEO,
    CLASS_BILLBOARD,
    CLASS_COMMUNICATIONS,
    CLASS_CONTENT_SECURITY,
    CLASS_CDC_DATA,
    CLASS_HID,
    CLASS_HUB,
    CLASS_IMAGE,
    CLASS_MASS_STORAGE,
    CLASS_MISC,
    CLASS_PER_INTERFACE,
    CLASS_PHYSICAL,
    CLASS_PRINTER,
    CLASS_PERSONAL_HEALTHCARE,
    CLASS_SMART_CARD,
    CLASS_TYPE_C_BRIDGE,
    CLASS_VENDOR_SPECIFIC,
    CLASS_VIDEO,
    CLASS_WIRELESS_CONTROLLER,
    CLASS_APPLICATION_SPECIFIC,
    CLASS_NAMES,
    KIND_DEVICE,
    KIND_INTERFACE,
    KIND_ROOT_HUB,
    SPEED_FULL,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_NAMES,
    SPEED_SUPER,
    SPEED_SUPER_PLUS,
    SYS_BUS_USB_DEVICES,
    USBDeviceInfo,
    available,
    classify_usb_name,
    clear_simulation,
    device_of_interface,
    discover_usb_devices,
    find_by_vid_pid,
    get_simulation,
    interface_class,
    interfaces_of,
    is_mass_storage_device,
    parse_lsusb,
    parse_lsusb_tree,
    parse_lsusb_verbose,
    read_usb_device,
    set_simulation,
)
from .storage import (
    SYS_BLOCK,
    USBStorageDevice,
    clear_storage_simulation,
    discover_usb_storage,
    get_storage_simulation,
    read_storage_device,
    set_storage_simulation,
    usb_backing_device,
)
from .cli import (
    DEFAULT_TIMEOUT,
    LSUSB_BIN,
    RESET_DELAY,
    UsbCLIError,
    list_devices,
    list_tree,
    remove_device,
    reset_device,
    set_authorized,
    verbose_device,
)

__all__ = [
    # device.py
    "CLASS_AUDIO",
    "CLASS_AUDIO_VIDEO",
    "CLASS_BILLBOARD",
    "CLASS_COMMUNICATIONS",
    "CLASS_CONTENT_SECURITY",
    "CLASS_CDC_DATA",
    "CLASS_HID",
    "CLASS_HUB",
    "CLASS_IMAGE",
    "CLASS_MASS_STORAGE",
    "CLASS_MISC",
    "CLASS_PER_INTERFACE",
    "CLASS_PHYSICAL",
    "CLASS_PRINTER",
    "CLASS_PERSONAL_HEALTHCARE",
    "CLASS_SMART_CARD",
    "CLASS_TYPE_C_BRIDGE",
    "CLASS_VENDOR_SPECIFIC",
    "CLASS_VIDEO",
    "CLASS_WIRELESS_CONTROLLER",
    "CLASS_APPLICATION_SPECIFIC",
    "CLASS_NAMES",
    "KIND_DEVICE",
    "KIND_INTERFACE",
    "KIND_ROOT_HUB",
    "SPEED_FULL",
    "SPEED_HIGH",
    "SPEED_LOW",
    "SPEED_NAMES",
    "SPEED_SUPER",
    "SPEED_SUPER_PLUS",
    "SYS_BUS_USB_DEVICES",
    "USBDeviceInfo",
    "available",
    "classify_usb_name",
    "clear_simulation",
    "device_of_interface",
    "discover_usb_devices",
    "find_by_vid_pid",
    "get_simulation",
    "interface_class",
    "interfaces_of",
    "is_mass_storage_device",
    "parse_lsusb",
    "parse_lsusb_tree",
    "parse_lsusb_verbose",
    "read_usb_device",
    "set_simulation",
    # storage.py
    "SYS_BLOCK",
    "USBStorageDevice",
    "clear_storage_simulation",
    "discover_usb_storage",
    "get_storage_simulation",
    "read_storage_device",
    "set_storage_simulation",
    "usb_backing_device",
    # cli.py
    "DEFAULT_TIMEOUT",
    "LSUSB_BIN",
    "RESET_DELAY",
    "UsbCLIError",
    "list_devices",
    "list_tree",
    "remove_device",
    "reset_device",
    "set_authorized",
    "verbose_device",
]


def _selftest() -> bool:
    """Run a basic self-test for this package."""
    from .device import _selftest as _device_st
    from .storage import _selftest as _storage_st
    from .cli import _selftest as _cli_st

    assert _device_st(), "media.usb.device selftest failed"
    assert _storage_st(), "media.usb.storage selftest failed"
    assert _cli_st(), "media.usb.cli selftest failed"

    # Cross-module round trip: a simulated USB
    # drive visible through both the device and
    # the storage views.
    set_simulation({
        "usb1": {"busnum": "1", "devnum": "1",
                 "bDeviceClass": "9",
                 "speed": "480"},
        "1-2": {"busnum": "1", "devnum": "6",
                "idVendor": "0781",
                "idProduct": "5581",
                "speed": "480",
                "version": "2.00",
                "product": "Ultra Fit"},
        "1-2:1.0": {"bInterfaceClass": "8"},
    })
    set_storage_simulation({"sdb": "1-2"})
    storage = discover_usb_storage()
    assert len(storage) == 1, storage
    disk = storage[0]
    assert disk.block_name == "sdb"
    assert disk.usb is not None
    assert disk.usb.product == "Ultra Fit", disk.usb
    assert disk.usb.vendor_id == 0x0781
    assert is_mass_storage_device("1-2")
    clear_storage_simulation()
    clear_simulation()

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
