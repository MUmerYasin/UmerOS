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
UmerOS tests - media.bluetooth
=====================================

Unit tests for the Bluetooth support package:
sysfs adapter / remote-device discovery (real
fake trees + simulation), rfkill switch state,
the BlueZ D-Bus model (busctl / gdbus value
parsing, Adapter1 / Device1 construction,
persistent-storage info files) and the
capability-gated bluetoothctl wrapper.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from core.capability_gate import gate

from media.bluetooth import bluez as bt_bluez
from media.bluetooth import cli as bt_cli
from media.bluetooth import device as bt_device
from media.bluetooth import rfkill as bt_rfkill


class BluetoothAddressTests(unittest.TestCase):
    """BD-address normalisation and name classification."""

    def test_normalize_colon(self):
        self.assertEqual(
            bt_device.normalize_bdaddr("00:1A:7D:DA:71:13"),
            "00:1A:7D:DA:71:13",
        )

    def test_normalize_lowercase(self):
        self.assertEqual(
            bt_device.normalize_bdaddr("00:1a:7d:da:71:13"),
            "00:1A:7D:DA:71:13",
        )

    def test_normalize_dash(self):
        self.assertEqual(
            bt_device.normalize_bdaddr("00-1a-7d-da-71-13"),
            "00:1A:7D:DA:71:13",
        )

    def test_normalize_strips_whitespace(self):
        self.assertEqual(
            bt_device.normalize_bdaddr("  00:1A:7D:DA:71:13  "),
            "00:1A:7D:DA:71:13",
        )

    def test_normalize_invalid(self):
        for bad in ("", "00:11:22:33:44", "00:11:22:33:44:5",
                    "not-an-addr", "00:11:22:33:44:GG",
                    "hci0"):
            with self.assertRaises(ValueError):
                bt_device.normalize_bdaddr(bad)

    def test_is_bdaddr(self):
        self.assertTrue(
            bt_device.is_bdaddr("00:11:22:33:44:55")
        )
        self.assertTrue(
            bt_device.is_bdaddr("00-11-22-33-44-55")
        )
        self.assertFalse(bt_device.is_bdaddr("00:11:22:33:44"))
        self.assertFalse(bt_device.is_bdaddr("hci0"))

    def test_bdaddr_to_dbus_suffix(self):
        self.assertEqual(
            bt_device.bdaddr_to_dbus_suffix("00:1a:7d:da:71:13"),
            "dev_00_1A_7D_DA_71_13",
        )

    def test_classify_bt_name(self):
        self.assertEqual(
            bt_device.classify_bt_name("hci0"),
            bt_device.KIND_ADAPTER,
        )
        self.assertEqual(
            bt_device.classify_bt_name("hci12"),
            bt_device.KIND_ADAPTER,
        )
        self.assertEqual(
            bt_device.classify_bt_name("00:11:22:33:44:55"),
            bt_device.KIND_DEVICE,
        )
        self.assertIsNone(bt_device.classify_bt_name("sda"))
        self.assertIsNone(bt_device.classify_bt_name(""))


class AdapterSimulationTests(unittest.TestCase):
    """Simulated adapter / device discovery."""

    def setUp(self):
        bt_device.clear_simulation()

    def tearDown(self):
        bt_device.clear_simulation()

    def test_discover_adapters(self):
        bt_device.set_simulation({
            "hci0": {
                "address": "00:1A:7D:DA:71:13",
                "name": "BlueZ 5.54",
                "type": "BR/EDR",
                "bus": "USB",
                "features": "fffef00000000000",
                "manufacturer": "15",
                "rfkill": "0",
                "ertm": "1",
            },
            "hci1": {
                "address": "A4:50:46:99:11:22",
                "type": "AMP",
                "bus": "UART",
            },
            "00:11:22:33:44:55": {"name": "MyPhone"},
        })
        adapters = bt_device.discover_adapters()
        self.assertEqual(len(adapters), 2)
        self.assertEqual([a.name for a in adapters], ["hci0", "hci1"])
        hci0 = adapters[0]
        self.assertEqual(hci0.address, "00:1A:7D:DA:71:13")
        self.assertEqual(hci0.local_name, "BlueZ 5.54")
        self.assertEqual(hci0.controller_type, "BR/EDR")
        self.assertEqual(hci0.bus, "USB")
        self.assertEqual(hci0.features, "fffef00000000000")
        self.assertEqual(hci0.manufacturer, 15)
        self.assertEqual(hci0.rfkill, 0)
        self.assertTrue(hci0.ertm)
        self.assertEqual(
            hci0.sysfs_path, "/sys/class/bluetooth/hci0"
        )
        # second adapter leaves optional fields unset
        self.assertIsNone(adapters[1].ertm)

    def test_discover_devices(self):
        bt_device.set_simulation({
            "hci0": {"address": "00:1A:7D:DA:71:13"},
            "00:11:22:33:44:55": {
                "address": "00:11:22:33:44:55",
                "name": "MyPhone",
                "features": "0000000000000000",
            },
            "11:22:33:44:55:66": {"name": "Headphones"},
        })
        devices = bt_device.discover_devices()
        self.assertEqual(len(devices), 2)
        self.assertEqual(
            [d.name for d in devices],
            ["00:11:22:33:44:55", "11:22:33:44:55:66"],
        )
        self.assertEqual(devices[0].local_name, "MyPhone")
        self.assertEqual(devices[0].features, "0000000000000000")

    def test_discover_all(self):
        bt_device.set_simulation({
            "hci0": {"address": "00:1A:7D:DA:71:13"},
            "00:11:22:33:44:55": {"name": "MyPhone"},
        })
        adapters, devices = bt_device.discover_all()
        self.assertEqual(len(adapters), 1)
        self.assertEqual(len(devices), 1)

    def test_simulation_lifecycle(self):
        self.assertIsNone(bt_device.get_simulation())
        bt_device.set_simulation({"hci0": {}})
        self.assertIsNotNone(bt_device.get_simulation())
        self.assertTrue(bt_device.available())
        bt_device.clear_simulation()
        self.assertIsNone(bt_device.get_simulation())

    def test_simulation_ignores_malformed_keys(self):
        bt_device.set_simulation({"sda": {"address": "x"}})
        self.assertEqual(bt_device.discover_adapters(), [])
        self.assertEqual(bt_device.discover_devices(), [])


class AdapterSysfsTests(unittest.TestCase):
    """Real-sysfs reads against a fake /sys tree."""

    # Remote-device directories in /sys/class/bluetooth use
    # colon-form BD addresses, which Windows cannot create as
    # directory names.  The sysfs layout itself is Linux-only.
    _device_dir_skip = unittest.skipIf(
        os.name == "nt",
        "colon-form BD-address directories cannot exist on Windows",
    )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        hci0 = self.root / "hci0"
        hci0.mkdir()
        (hci0 / "address").write_text("00:1A:7D:DA:71:13\n")
        (hci0 / "name").write_text("BlueZ 5.54\n")
        (hci0 / "type").write_text("BR/EDR\n")
        (hci0 / "bus").write_text("USB\n")
        (hci0 / "features").write_bytes(b"\xff\xfe\x0f\x00\x00\x00\x00\x00")
        (hci0 / "manufacturer").write_text("15\n")
        (hci0 / "rfkill").write_text("0\n")
        (hci0 / "ertm").write_text("1\n")

    def tearDown(self):
        self._tmp.cleanup()

    def _add_device_dir(self):
        dev = self.root / "00:11:22:33:44:55"
        dev.mkdir()
        (dev / "name").write_text("MyPhone\n")

    def test_read_adapter_info(self):
        info = bt_device.read_adapter_info("hci0", self.root)
        self.assertIsNotNone(info)
        self.assertEqual(info.name, "hci0")
        self.assertEqual(info.address, "00:1A:7D:DA:71:13")
        self.assertEqual(info.local_name, "BlueZ 5.54")
        self.assertEqual(info.controller_type, "BR/EDR")
        self.assertEqual(info.bus, "USB")
        self.assertEqual(info.features, "fffe0f0000000000")
        self.assertEqual(info.manufacturer, 15)
        self.assertEqual(info.rfkill, 0)
        self.assertTrue(info.ertm)

    @_device_dir_skip
    def test_read_device_info(self):
        self._add_device_dir()
        info = bt_device.read_device_info(
            "00:11:22:33:44:55", self.root
        )
        self.assertIsNotNone(info)
        self.assertEqual(info.local_name, "MyPhone")

    def test_read_missing_entry(self):
        self.assertIsNone(
            bt_device.read_adapter_info("hci9", self.root)
        )
        self.assertIsNone(
            bt_device.read_device_info("99:99:99:99:99:99", self.root)
        )

    def test_discover_adapters_sysfs(self):
        adapters = bt_device.discover_adapters(self.root)
        self.assertEqual(len(adapters), 1)
        self.assertEqual(adapters[0].name, "hci0")
        self.assertEqual(adapters[0].features, "fffe0f0000000000")

    @_device_dir_skip
    def test_discover_devices_sysfs(self):
        self._add_device_dir()
        devices = bt_device.discover_devices(self.root)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].name, "00:11:22:33:44:55")
        self.assertEqual(devices[0].local_name, "MyPhone")

    def test_discover_missing_root(self):
        missing = self.root / "nope"
        self.assertEqual(bt_device.discover_adapters(missing), [])
        self.assertEqual(bt_device.discover_devices(missing), [])


class RfkillSimulationTests(unittest.TestCase):
    """Simulated rfkill switch reads."""

    def setUp(self):
        bt_rfkill.clear_simulation()

    def tearDown(self):
        bt_rfkill.clear_simulation()

    def test_discover_and_summary(self):
        bt_rfkill.set_simulation({
            "rfkill0": {
                "name": "hci0",
                "type": "bluetooth",
                "state": "1",
                "soft": "1",
                "hard": "0",
            },
            "rfkill1": {
                "name": "hci1",
                "type": "bluetooth",
                "soft": "0",
                "hard": "0",
            },
            "rfkill2": {
                "name": "phy0",
                "type": "wlan",
                "soft": "0",
                "hard": "1",
            },
        })
        switches = bt_rfkill.discover_rfkill()
        self.assertEqual(len(switches), 3)

        bt = bt_rfkill.discover_bluetooth_rfkill()
        self.assertEqual(len(bt), 2)
        self.assertEqual([e.name for e in bt], ["rfkill0", "rfkill1"])
        self.assertEqual(bt[0].device_name, "hci0")
        self.assertTrue(bt[0].is_bluetooth)
        self.assertTrue(bt[0].blocked)
        self.assertTrue(bt[0].soft)
        self.assertFalse(bt[0].hard)
        self.assertEqual(bt[0].state, 1)
        self.assertEqual(
            bt[0].sysfs_path, "/sys/class/rfkill/rfkill0"
        )
        self.assertFalse(bt[1].blocked)
        self.assertFalse(switches[2].is_bluetooth)
        self.assertTrue(switches[2].blocked)

        summary = bt_rfkill.bluetooth_rfkill_summary()
        self.assertEqual(summary["count"], 2)
        self.assertTrue(summary["any_soft"])
        self.assertFalse(summary["any_hard"])
        self.assertTrue(summary["blocked"])
        self.assertEqual(summary["entries"], bt)

    def test_lifecycle(self):
        self.assertIsNone(bt_rfkill.get_simulation())
        bt_rfkill.set_simulation({"rfkill0": {}})
        self.assertIsNotNone(bt_rfkill.get_simulation())
        self.assertTrue(bt_rfkill.available())
        bt_rfkill.clear_simulation()
        self.assertIsNone(bt_rfkill.get_simulation())


class RfkillSysfsTests(unittest.TestCase):
    """Real-sysfs rfkill reads against a fake tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        rf0 = self.root / "rfkill0"
        rf0.mkdir()
        (rf0 / "name").write_text("hci0\n")
        (rf0 / "type").write_text("bluetooth\n")
        (rf0 / "state").write_text("1\n")
        (rf0 / "soft").write_text("1\n")
        (rf0 / "hard").write_text("0\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_read_rfkill_entry(self):
        entry = bt_rfkill.read_rfkill_entry("rfkill0", self.root)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.device_name, "hci0")
        self.assertEqual(entry.type, "bluetooth")
        self.assertTrue(entry.soft)
        self.assertFalse(entry.hard)
        self.assertEqual(entry.state, 1)
        self.assertTrue(entry.blocked)
        self.assertTrue(entry.is_bluetooth)

    def test_discover_rfkill(self):
        entries = bt_rfkill.discover_rfkill(self.root)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "rfkill0")

    def test_discover_missing_root(self):
        missing = self.root / "nope"
        self.assertEqual(bt_rfkill.discover_rfkill(missing), [])
        self.assertEqual(bt_rfkill.discover_bluetooth_rfkill(missing), [])


class BluezValueParserTests(unittest.TestCase):
    """busctl / gdbus single-value parsing."""

    def test_busctl_bool(self):
        self.assertTrue(bt_bluez._parse_busctl_value("b true"))
        self.assertFalse(bt_bluez._parse_busctl_value("b false"))

    def test_busctl_string(self):
        self.assertEqual(
            bt_bluez._parse_busctl_value('s "MyHost"'), "MyHost"
        )

    def test_busctl_uint(self):
        self.assertEqual(bt_bluez._parse_busctl_value("u 123"), 123)
        self.assertEqual(bt_bluez._parse_busctl_value("x -5"), -5)

    def test_busctl_byte_array(self):
        self.assertEqual(
            bt_bluez._parse_busctl_value("ay 00 11 ff"),
            b"\x00\x11\xff",
        )

    def test_busctl_string_array(self):
        self.assertEqual(
            bt_bluez._parse_busctl_value("as [a b c]"),
            ["a", "b", "c"],
        )
        self.assertEqual(bt_bluez._parse_busctl_value("as []"), [])

    def test_busctl_structured_passthrough(self):
        raw = bt_bluez._parse_busctl_value('a{sv} {"Powered" b true}')
        self.assertIsInstance(raw, str)

    def test_gdbus_values(self):
        self.assertTrue(bt_bluez._parse_gdbus_value("(true,)"))
        self.assertFalse(bt_bluez._parse_gdbus_value("(false,)"))
        self.assertEqual(
            bt_bluez._parse_gdbus_value("('MyHost',)"), "MyHost"
        )
        self.assertEqual(bt_bluez._parse_gdbus_value("(123,)"), 123)


class BluezModelTests(unittest.TestCase):
    """Adapter1 / Device1 construction from D-Bus properties."""

    def test_adapter_from_properties(self):
        adapter = bt_bluez.Adapter1.from_properties({
            "Address": "00:1A:7D:DA:71:13",
            "AddressType": "public",
            "Name": "MyHost",
            "Alias": "MyHost",
            "Class": 0x10010C,
            "Powered": True,
            "Discoverable": False,
            "DiscoverableTimeout": 180,
            "Pairable": True,
            "PairableTimeout": 0,
            "Discovering": False,
            "UUIDs": ["0000110a-0000-1000-8000-00805f9b34fb"],
            "Modalias": "usb:v1D6Bp0246d0539",
        }, path="/org/bluez/hci0")
        self.assertEqual(adapter.path, "/org/bluez/hci0")
        self.assertEqual(adapter.address, "00:1A:7D:DA:71:13")
        self.assertEqual(adapter.address_type, "public")
        self.assertEqual(adapter.name, "MyHost")
        self.assertEqual(adapter.alias, "MyHost")
        self.assertEqual(adapter.class_of_device, 0x10010C)
        self.assertTrue(adapter.powered)
        self.assertFalse(adapter.discoverable)
        self.assertEqual(adapter.discoverable_timeout, 180)
        self.assertTrue(adapter.pairable)
        self.assertEqual(adapter.pairable_timeout, 0)
        self.assertFalse(adapter.discovering)
        self.assertEqual(
            adapter.uuids, ["0000110a-0000-1000-8000-00805f9b34fb"]
        )
        self.assertEqual(adapter.modalias, "usb:v1D6Bp0246d0539")

    def test_device_from_properties(self):
        device = bt_bluez.Device1.from_properties({
            "Address": "00:11:22:33:44:55",
            "Name": "MyPhone",
            "Class": 0x200404,
            "Appearance": 0x0404,
            "Icon": "phone",
            "Paired": True,
            "Trusted": True,
            "Blocked": False,
            "Connected": False,
            "UUIDs": ["0000110a-0000-1000-8000-00805f9b34fb"],
            "Adapter": "/org/bluez/hci0",
        }, path="/org/bluez/hci0/dev_00_11_22_33_44_55")
        self.assertEqual(device.path, "/org/bluez/hci0/dev_00_11_22_33_44_55")
        self.assertEqual(device.address, "00:11:22:33:44:55")
        self.assertEqual(device.name, "MyPhone")
        self.assertEqual(device.class_of_device, 0x200404)
        self.assertEqual(device.appearance, 0x0404)
        self.assertEqual(device.icon, "phone")
        self.assertTrue(device.paired)
        self.assertTrue(device.trusted)
        self.assertFalse(device.blocked)
        self.assertFalse(device.connected)
        self.assertEqual(device.adapter, "/org/bluez/hci0")

    def test_available_tool_validation(self):
        with self.assertRaises(ValueError):
            bt_bluez.available_tool("bogus")


class BluezInfoFileTests(unittest.TestCase):
    """BlueZ persistent-storage info file parsing."""

    def test_parse_device_info_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            info = Path(tmp) / "info"
            info.write_text(
                "[General]\n"
                "Name = MyPhone\n"
                "Class = 0x200404\n\n"
                "[IdentityResolvingKey]\n"
                "Key = 00112233445566778899aabbccddeeff\n",
                encoding="utf-8",
            )
            sections = bt_bluez.parse_device_info_file(info)
            self.assertEqual(sections["General"]["Name"], "MyPhone")
            self.assertEqual(sections["General"]["Class"], "0x200404")
            self.assertEqual(
                sections["IdentityResolvingKey"]["Key"],
                "00112233445566778899aabbccddeeff",
            )

    def test_paired_devices_dir(self):
        self.assertEqual(
            bt_bluez.paired_devices_dir("00-1a-7d-da-71-13"),
            Path("/var/lib/bluetooth/00:1A:7D:DA:71:13"),
        )

    def test_discover_paired_devices_missing_dir(self):
        self.assertEqual(
            bt_bluez.discover_paired_devices("00:1A:7D:DA:71:13"), []
        )


class BluetoothctlParserTests(unittest.TestCase):
    """bluetoothctl text-output parsing."""

    def test_parse_controller_line(self):
        self.assertEqual(
            bt_cli.parse_controller_line(
                "Controller 00:1A:7D:DA:71:13 MyHost [default]"
            ),
            {"address": "00:1A:7D:DA:71:13",
             "name": "MyHost", "default": True},
        )
        self.assertEqual(
            bt_cli.parse_controller_line(
                "Controller A4:50:46:99:11:22 Second"
            ),
            {"address": "A4:50:46:99:11:22",
             "name": "Second", "default": False},
        )
        self.assertIsNone(
            bt_cli.parse_controller_line("Device 00:11:22:33:44:55 Phone")
        )
        self.assertIsNone(bt_cli.parse_controller_line(""))

    def test_parse_device_line(self):
        self.assertEqual(
            bt_cli.parse_device_line("Device 00:11:22:33:44:55 MyPhone"),
            {"address": "00:11:22:33:44:55", "name": "MyPhone"},
        )
        self.assertIsNone(
            bt_cli.parse_device_line("Controller 00:1A:7D:DA:71:13")
        )

    def test_parse_list_output(self):
        controllers = bt_cli.parse_list_output(
            "Controller 00:1A:7D:DA:71:13 MyHost [default]\n"
            "Controller A4:50:46:99:11:22 Second\n"
        )
        self.assertEqual(len(controllers), 2)
        self.assertTrue(controllers[0]["default"])
        self.assertFalse(controllers[1]["default"])

    def test_parse_devices_output(self):
        devices = bt_cli.parse_devices_output(
            "Device 00:11:22:33:44:55 MyPhone\n"
            "Device 11:22:33:44:55:66 Headphones\n"
        )
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[1]["name"], "Headphones")

    def test_parse_show_output(self):
        show = bt_cli.parse_show_output(
            "Controller 00:1A:7D:DA:71:13 MyHost [default]\n"
            "\tPowered yes\n"
            "\tDiscoverable no\n"
            "\tUUIDs 0000110a-0000-1000-8000-00805f9b34fb\n"
            "\tModalias usb:v1D6Bp0246d0539\n"
        )
        self.assertEqual(show["address"], "00:1A:7D:DA:71:13")
        self.assertEqual(show["name"], "MyHost")
        self.assertTrue(show["default"])
        self.assertEqual(show["Powered"], "yes")
        self.assertEqual(show["Discoverable"], "no")
        self.assertEqual(
            show["UUIDs"], "0000110a-0000-1000-8000-00805f9b34fb"
        )
        self.assertEqual(show["Modalias"], "usb:v1D6Bp0246d0539")

    def test_parse_info_output(self):
        info = bt_cli.parse_info_output(
            "Device 00:11:22:33:44:55 MyPhone\n"
            "\tPaired yes\n"
            "\tTrusted yes\n"
            "\tConnected no\n"
        )
        self.assertEqual(info["address"], "00:11:22:33:44:55")
        self.assertEqual(info["name"], "MyPhone")
        self.assertEqual(info["Paired"], "yes")
        self.assertEqual(info["Connected"], "no")


class BluetoothctlGatingTests(unittest.TestCase):
    """Capability gating of privileged bluetoothctl commands."""

    def setUp(self):
        self._state = gate.snapshot()

    def tearDown(self):
        gate.restore(self._state)

    def _denied(self, call):
        try:
            call()
        except PermissionError:
            return
        self.fail("strict gate must deny privileged operations")

    def test_privileged_ops_denied_under_strict_gate(self):
        gate.set_strict(True)
        addr = "00:11:22:33:44:55"
        self._denied(lambda: bt_cli.power(True))
        self._denied(lambda: bt_cli.power(False))
        self._denied(lambda: bt_cli.scan(True))
        self._denied(lambda: bt_cli.pair(addr))
        self._denied(lambda: bt_cli.trust(addr))
        self._denied(lambda: bt_cli.untrust(addr))
        self._denied(lambda: bt_cli.remove(addr))
        self._denied(lambda: bt_cli.connect(addr))
        self._denied(lambda: bt_cli.disconnect(addr))

    def test_gate_checks_before_subprocess(self):
        gate.set_strict(True)
        with mock.patch.object(
            bt_cli.shutil, "which", return_value="/usr/bin/bluetoothctl"
        ), mock.patch.object(
            bt_cli.subprocess, "run"
        ) as run:
            self._denied(lambda: bt_cli.pair("00:11:22:33:44:55"))
            run.assert_not_called()

    def test_readonly_ops_not_gated(self):
        gate.set_strict(True)
        with mock.patch.object(
            bt_cli.shutil, "which", return_value="/usr/bin/bluetoothctl"
        ), mock.patch.object(bt_cli.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess(
                [], 0, stdout="", stderr=""
            )
            bt_cli.list_controllers()
            bt_cli.devices()
            bt_cli.show()
            bt_cli.info("00:11:22:33:44:55")
            bt_cli.paired_devices()
            self.assertEqual(run.call_count, 5)


class BluetoothctlExecutionTests(unittest.TestCase):
    """bluetoothctl execution paths (mocked subprocess)."""

    def setUp(self):
        self._state = gate.snapshot()

    def tearDown(self):
        gate.restore(self._state)

    def test_command_construction(self):
        with mock.patch.object(
            bt_cli.shutil, "which",
            return_value="/usr/bin/bluetoothctl",
        ), mock.patch.object(bt_cli.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess(
                [], 0, stdout="", stderr=""
            )
            bt_cli.pair("00:11:22:33:44:55")
            args = run.call_args[0][0]
        self.assertEqual(args[0], "bluetoothctl")
        self.assertEqual(args[1], "pair")
        self.assertEqual(args[2], "00:11:22:33:44:55")

    def test_missing_binary(self):
        with mock.patch.object(bt_cli.shutil, "which", return_value=None):
            with self.assertRaises(bt_cli.BluetoothctlError):
                bt_cli.list_controllers()

    def test_nonzero_exit(self):
        with mock.patch.object(
            bt_cli.shutil, "which",
            return_value="/usr/bin/bluetoothctl",
        ), mock.patch.object(bt_cli.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess(
                [], 1, stdout="", stderr="Failed to pair"
            )
            with self.assertRaises(bt_cli.BluetoothctlError):
                bt_cli.pair("00:11:22:33:44:55")

    def test_timeout(self):
        with mock.patch.object(
            bt_cli.shutil, "which",
            return_value="/usr/bin/bluetoothctl",
        ), mock.patch.object(
            bt_cli.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(
                ["bluetoothctl", "pair"], 10
            ),
        ):
            with self.assertRaises(bt_cli.BluetoothctlError):
                bt_cli.pair("00:11:22:33:44:55")

    def test_oserror(self):
        with mock.patch.object(
            bt_cli.shutil, "which",
            return_value="/usr/bin/bluetoothctl",
        ), mock.patch.object(
            bt_cli.subprocess, "run", side_effect=OSError("boom")
        ):
            with self.assertRaises(bt_cli.BluetoothctlError):
                bt_cli.pair("00:11:22:33:44:55")


if __name__ == "__main__":
    unittest.main()
