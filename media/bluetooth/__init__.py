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
UmerOS /media/bluetooth - Bluetooth Support
=================================================

Bluetooth support for UmerOS.  The package is
self-contained (standard library only) and exposes
four sub-modules:

* :mod:`media.bluetooth.device` - sysfs discovery of
  HCI adapters (``hciN``) and known remote devices
  (BD addresses), with a simulation mode for hosts
  without Bluetooth hardware.
* :mod:`media.bluetooth.rfkill` - Linux rfkill
  switch state (soft/hard block) for Bluetooth.
* :mod:`media.bluetooth.bluez` - read-only model of
  the BlueZ D-Bus API (``org.bluez.Adapter1`` /
  ``org.bluez.Device1``) read via ``busctl`` or
  ``gdbus``, plus the BlueZ persistent-storage
  (``/var/lib/bluetooth``) ``info`` file parser.
* :mod:`media.bluetooth.cli` - capability-gated
  wrapper around ``bluetoothctl`` (list / show /
  devices / info / paired-devices / power / scan /
  pair / trust / remove / connect / disconnect).

Quick start::

    from media.bluetooth.device import discover_adapters
    from media.bluetooth.rfkill import bluetooth_rfkill_summary

    for adapter in discover_adapters():
        print(adapter.name, adapter.address)
    print(bluetooth_rfkill_summary()["blocked"])

This package is ``[REFERENCE-ONLY]`` - it is not
imported by ``main.py``.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

from .bluez import (
    ADAPTER_IFACE,
    Adapter1,
    BLUEZ_PATH,
    BLUEZ_SERVICE,
    BLUEZ_STATE_DIR,
    DEVICE_IFACE,
    Device1,
    BluezError,
    discover_adapters_dbus,
    discover_devices_dbus,
    discover_paired_devices,
    list_object_paths,
    paired_devices_dir,
    parse_device_info_file,
    read_properties,
    read_property,
)
from .cli import (
    BLUETOOTHCTL_BIN,
    BluetoothctlError,
    connect,
    disconnect,
    devices,
    info,
    list_controllers,
    paired_devices,
    pair,
    parse_controller_line,
    parse_device_line,
    parse_devices_output,
    parse_info_output,
    parse_list_output,
    parse_show_output,
    power,
    remove,
    scan,
    show,
    trust,
    untrust,
)
from .device import (
    KIND_ADAPTER,
    KIND_DEVICE,
    SYS_CLASS_BT,
    BluetoothAdapterInfo,
    BluetoothDeviceInfo,
    available,
    bdaddr_to_dbus_suffix,
    classify_bt_name,
    clear_simulation,
    discover_adapters,
    discover_all,
    discover_devices,
    get_simulation,
    is_bdaddr,
    normalize_bdaddr,
    read_adapter_info,
    read_device_info,
    set_simulation,
)
from .rfkill import (
    SYS_CLASS_RFKILL,
    TYPE_BLUETOOTH,
    RfkillEntry,
    available as rfkill_available,
    bluetooth_rfkill_summary,
    discover_bluetooth_rfkill,
    discover_rfkill,
    read_rfkill_entry,
    set_simulation as rfkill_set_simulation,
    get_simulation as rfkill_get_simulation,
    clear_simulation as rfkill_clear_simulation,
)

__all__ = [
    "ADAPTER_IFACE",
    "BLUETOOTHCTL_BIN",
    "BLUEZ_PATH",
    "BLUEZ_SERVICE",
    "BLUEZ_STATE_DIR",
    "BluetoothAdapterInfo",
    "BluetoothDeviceInfo",
    "BluetoothctlError",
    "BluezError",
    "DEVICE_IFACE",
    "Device1",
    "Adapter1",
    "KIND_ADAPTER",
    "KIND_DEVICE",
    "RfkillEntry",
    "SYS_CLASS_BT",
    "SYS_CLASS_RFKILL",
    "TYPE_BLUETOOTH",
    "available",
    "bdaddr_to_dbus_suffix",
    "bluetooth_rfkill_summary",
    "classify_bt_name",
    "clear_simulation",
    "connect",
    "discover_adapters",
    "discover_adapters_dbus",
    "discover_all",
    "discover_bluetooth_rfkill",
    "discover_devices",
    "discover_devices_dbus",
    "discover_paired_devices",
    "discover_rfkill",
    "devices",
    "disconnect",
    "get_simulation",
    "info",
    "is_bdaddr",
    "list_controllers",
    "list_object_paths",
    "normalize_bdaddr",
    "paired_devices",
    "paired_devices_dir",
    "pair",
    "parse_controller_line",
    "parse_device_line",
    "parse_device_info_file",
    "parse_devices_output",
    "parse_info_output",
    "parse_list_output",
    "parse_show_output",
    "power",
    "read_adapter_info",
    "read_device_info",
    "read_properties",
    "read_property",
    "read_rfkill_entry",
    "remove",
    "rfkill_available",
    "rfkill_clear_simulation",
    "rfkill_get_simulation",
    "rfkill_set_simulation",
    "scan",
    "set_simulation",
    "show",
    "trust",
    "untrust",
]


def _selftest() -> bool:
    """Run a basic self-test for this package (synthetic data only)."""
    from . import bluez as _bluez
    from . import cli as _cli
    from . import device as _device
    from . import rfkill as _rfkill

    assert classify_bt_name("hci0") == KIND_ADAPTER
    assert classify_bt_name("00:11:22:33:44:55") == KIND_DEVICE
    assert classify_bt_name("sda") is None
    assert normalize_bdaddr("00-1a-7d-da-71-13") == (
        "00:1A:7D:DA:71:13"
    )
    assert bdaddr_to_dbus_suffix(
        "00:1a:7d:da:71:13"
    ) == "dev_00_1A_7D_DA_71_13"
    assert _device.SYS_CLASS_BT.name == "bluetooth"
    assert _rfkill.SYS_CLASS_RFKILL.name == "rfkill"
    assert _bluez.BLUEZ_SERVICE == "org.bluez"
    assert _bluez.ADAPTER_IFACE == "org.bluez.Adapter1"
    assert _bluez.DEVICE_IFACE == "org.bluez.Device1"
    assert _cli.BLUETOOTHCTL_BIN == "bluetoothctl"

    adapter = Adapter1.from_properties(
        {"Address": "00:1A:7D:DA:71:13", "Powered": True}
    )
    assert adapter.address == "00:1A:7D:DA:71:13"
    assert adapter.powered is True
    device = Device1.from_properties(
        {"Address": "00:11:22:33:44:55", "Paired": True}
    )
    assert device.address == "00:11:22:33:44:55"
    assert device.paired is True

    entry = RfkillEntry(
        name="rfkill0",
        device_name="hci0",
        type=TYPE_BLUETOOTH,
        soft=True,
        hard=False,
    )
    assert entry.is_bluetooth is True
    assert entry.blocked is True

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
