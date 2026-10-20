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
Test suite for media.usb package.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Bootstrap path for media package imports
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from media.usb.device import (
    CLASS_MASS_STORAGE,
    CLASS_HUB,
    KIND_DEVICE,
    KIND_INTERFACE,
    KIND_ROOT_HUB,
    USBDeviceInfo,
    classify_usb_name,
    device_of_interface,
    discover_usb_devices,
    find_by_vid_pid,
    interfaces_of,
    interface_class,
    is_mass_storage_device,
    parse_lsusb,
    parse_lsusb_tree,
    parse_lsusb_verbose,
    read_usb_device,
    set_simulation,
    clear_simulation,
    get_simulation,
)
from media.usb.storage import (
    USBStorageDevice,
    discover_usb_storage,
    read_storage_device,
    set_storage_simulation,
    clear_storage_simulation,
    usb_backing_device,
)
from media.usb.cli import (
    UsbCLIError,
    list_devices,
    list_tree,
    verbose_device,
    set_authorized,
    remove_device,
    reset_device,
)


class TestUSBNameClassification(unittest.TestCase):
    """Tests for classify_usb_name and device_of_interface."""

    def test_root_hub_names(self):
        self.assertEqual(classify_usb_name("usb1"), KIND_ROOT_HUB)
        self.assertEqual(classify_usb_name("usb42"), KIND_ROOT_HUB)
        self.assertEqual(classify_usb_name("usb0"), KIND_ROOT_HUB)

    def test_device_names(self):
        self.assertEqual(classify_usb_name("1-2"), KIND_DEVICE)
        self.assertEqual(classify_usb_name("1-2.4"), KIND_DEVICE)
        self.assertEqual(classify_usb_name("10-3.1.7"), KIND_DEVICE)
        self.assertEqual(classify_usb_name("3-1"), KIND_DEVICE)

    def test_interface_names(self):
        self.assertEqual(classify_usb_name("1-2:1.0"), KIND_INTERFACE)
        self.assertEqual(classify_usb_name("1-2.4:2.1"), KIND_INTERFACE)
        self.assertEqual(classify_usb_name("3-1:1.0"), KIND_INTERFACE)

    def test_non_usb_names(self):
        self.assertIsNone(classify_usb_name("sdb"))
        self.assertIsNone(classify_usb_name("hci0"))
        self.assertIsNone(classify_usb_name("nvme0n1"))
        self.assertIsNone(classify_usb_name(""))
        self.assertIsNone(classify_usb_name("1-2:"))
        self.assertIsNone(classify_usb_name("usb"))
        self.assertIsNone(classify_usb_name("1--2"))

    def test_device_of_interface(self):
        self.assertEqual(device_of_interface("1-2:1.0"), "1-2")
        self.assertEqual(device_of_interface("1-2.4:2.1"), "1-2.4")
        self.assertEqual(device_of_interface("3-1:1.0"), "3-1")
        # Non-interface names return None
        self.assertIsNone(device_of_interface("1-2"))
        self.assertIsNone(device_of_interface("usb1"))


class TestUSBDeviceInfoProperties(unittest.TestCase):
    """Tests for USBDeviceInfo computed properties."""

    def test_vendor_id_product_id(self):
        info = USBDeviceInfo(name="1-2", vid="0781", pid="5581")
        self.assertEqual(info.vendor_id, 0x0781)
        self.assertEqual(info.product_id, 0x5581)

    def test_vendor_id_product_id_no_prefix(self):
        info = USBDeviceInfo(name="1-2", vid="781", pid="581")
        self.assertEqual(info.vendor_id, 0x0781)
        self.assertEqual(info.product_id, 0x0581)

    def test_vendor_id_product_id_none(self):
        info = USBDeviceInfo(name="1-2")
        self.assertIsNone(info.vendor_id)
        self.assertIsNone(info.product_id)

    def test_speed_name_mapping(self):
        self.assertEqual(USBDeviceInfo(name="1-2", speed="1.5").speed_name, "low_speed")
        self.assertEqual(USBDeviceInfo(name="1-2", speed="12").speed_name, "full_speed")
        self.assertEqual(USBDeviceInfo(name="1-2", speed="480").speed_name, "high_speed")
        self.assertEqual(USBDeviceInfo(name="1-2", speed="5000").speed_name, "super_speed")
        self.assertEqual(USBDeviceInfo(name="1-2", speed="10000").speed_name, "super_speed_plus")
        self.assertEqual(USBDeviceInfo(name="1-2", speed="unknown").speed_name, "unknown")

    def test_device_class_name(self):
        self.assertEqual(
            USBDeviceInfo(name="1-2", device_class=0x08).device_class_name,
            "mass-storage",
        )
        self.assertEqual(
            USBDeviceInfo(name="1-2", device_class=0x09).device_class_name,
            "hub",
        )
        self.assertEqual(
            USBDeviceInfo(name="1-2", device_class=0xFF).device_class_name,
            "vendor-specific",
        )
        # Explicit 0 -> per-interface; None -> unknown
        self.assertEqual(
            USBDeviceInfo(name="1-2", device_class=0).device_class_name,
            "per-interface",
        )
        self.assertIsNone(USBDeviceInfo(name="1-2").device_class_name)
        self.assertTrue(USBDeviceInfo(name="1-2", device_class=0x09).is_hub)
        self.assertFalse(USBDeviceInfo(name="1-2", device_class=0x08).is_hub)

    def test_is_mass_storage(self):
        self.assertTrue(USBDeviceInfo(name="1-2", device_class=0x08).is_mass_storage)
        self.assertFalse(USBDeviceInfo(name="1-2", device_class=0x09).is_mass_storage)

    def test_device_path(self):
        info = USBDeviceInfo(name="1-2")
        # Path uses OS-specific separator
        expected = Path("/sys/bus/usb/devices/1-2")
        self.assertEqual(info.device_path, str(expected))


class TestSimulationMode(unittest.TestCase):
    """Tests for the simulation mode."""

    def setUp(self):
        clear_simulation()

    def tearDown(self):
        clear_simulation()

    def test_set_get_clear_simulation(self):
        sim_data = {"1-2": {"idVendor": "0781"}}
        set_simulation(sim_data)
        self.assertEqual(get_simulation(), sim_data)
        clear_simulation()
        self.assertIsNone(get_simulation())

    def test_discover_with_simulation(self):
        set_simulation({
            "usb1": {"busnum": "1", "devnum": "1", "bDeviceClass": "9", "speed": "480"},
            "1-2": {"busnum": "1", "devnum": "5", "idVendor": "0781", "idProduct": "5581",
                    "speed": "480", "product": "Ultra Fit"},
            "1-2:1.0": {"bInterfaceClass": "8"},
        })
        devices = discover_usb_devices()
        self.assertEqual(len(devices), 2)
        names = {d.name for d in devices}
        self.assertEqual(names, {"usb1", "1-2"})
        # Check properties
        stick = next(d for d in devices if d.name == "1-2")
        self.assertEqual(stick.product, "Ultra Fit")
        self.assertEqual(stick.vendor_id, 0x0781)

    def test_find_by_vid_pid_normalization(self):
        set_simulation({
            "1-2": {"idVendor": "0781", "idProduct": "5581", "product": "Test"},
        })
        # Various input formats
        found = find_by_vid_pid("0x0781", "5581")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "1-2")

        found = find_by_vid_pid("0781", "0x5581")
        self.assertEqual(len(found), 1)

        found = find_by_vid_pid("781", "5581")
        self.assertEqual(len(found), 1)

        found = find_by_vid_pid("0x781", "0x5581")
        self.assertEqual(len(found), 1)

        # Not found
        found = find_by_vid_pid("1234", "5678")
        self.assertEqual(found, [])


class TestParseLsusb(unittest.TestCase):
    """Tests for plain lsusb output parsing."""

    def test_parse_basic(self):
        parsed = parse_lsusb(
            "Bus 001 Device 007: ID 05e3:0610 "
            "Genesys Logic, Inc. 4-port hub"
        )
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["bus"], "001")
        self.assertEqual(parsed[0]["device"], "007")
        self.assertEqual(parsed[0]["vid"], "05e3")
        self.assertEqual(parsed[0]["pid"], "0610")
        self.assertIn("hub", parsed[0]["description"].lower())

    def test_parse_multiple_lines(self):
        text = (
            "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub\n"
            "Bus 001 Device 002: ID 8087:0024 Intel Corp. Integrated Rate Matching Hub\n"
        )
        parsed = parse_lsusb(text)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["vid"], "1d6b")
        self.assertEqual(parsed[1]["vid"], "8087")


class TestParseLsusbVerbose(unittest.TestCase):
    """Tests for lsusb -v output parsing."""

    def test_parse_device_descriptor(self):
        text = (
            "  Device Descriptor:\n"
            "    bcdUSB               2.00\n"
            "    idVendor           0x0781 SanDisk Corp.\n"
            "    idProduct          0x5581 Ultra Fit\n"
            "    bDeviceClass         0 (Defined at Interface level)\n"
        )
        verbose = parse_lsusb_verbose(text)
        self.assertEqual(len(verbose), 1)
        self.assertEqual(verbose[0]["idVendor"], "0781")
        self.assertEqual(verbose[0]["idVendor_name"], "SanDisk Corp.")
        self.assertEqual(verbose[0]["idProduct"], "5581")
        self.assertEqual(verbose[0]["idProduct_name"], "Ultra Fit")
        self.assertEqual(verbose[0]["bDeviceClass"], "0")

    def test_parse_multiple_devices(self):
        text = (
            "  Device Descriptor:\n"
            "    idVendor           0x0781\n"
            "  Device Descriptor:\n"
            "    idVendor           0x0951\n"
        )
        verbose = parse_lsusb_verbose(text)
        self.assertEqual(len(verbose), 2)
        self.assertEqual(verbose[0]["idVendor"], "0781")
        self.assertEqual(verbose[1]["idVendor"], "0951")


class TestParseLsusbTree(unittest.TestCase):
    """Tests for lsusb -t tree output parsing."""

    def test_parse_root_line(self):
        text = "/:  Bus 02.Port 1: Dev 1, Class=root_hub, Driver=uhci_hcd/2p, 12M"
        tree = parse_lsusb_tree(text)
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]["bus"], "02")
        self.assertEqual(tree[0]["port"], "1")
        self.assertEqual(tree[0]["dev"], "1")
        self.assertEqual(tree[0]["class"], "root_hub")
        self.assertEqual(tree[0]["driver"], "uhci_hcd/2p")
        self.assertEqual(tree[0]["speed_mb"], "12")

    def test_parse_child_lines_with_inherited_bus(self):
        text = (
            "/:  Bus 02.Port 1: Dev 1, Class=root_hub, Driver=uhci_hcd/2p, 12M\n"
            "    |__ Port 1: Dev 2, If 0, Class=Mass Storage, Driver=usb-storage, 480M"
        )
        tree = parse_lsusb_tree(text)
        self.assertEqual(len(tree), 2)
        self.assertEqual(tree[0]["bus"], "02")
        self.assertEqual(tree[1]["bus"], "02")  # inherited
        self.assertEqual(tree[1]["port"], "1")
        self.assertEqual(tree[1]["dev"], "2")
        self.assertEqual(tree[1]["if"], "0")
        self.assertEqual(tree[1]["class"], "Mass Storage")
        self.assertEqual(tree[1]["driver"], "usb-storage")
        self.assertEqual(tree[1]["speed_mb"], "480")


class TestMassStorageDetection(unittest.TestCase):
    """Tests for is_mass_storage_device using mocked sysfs."""

    def test_device_class_mass_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb_root = Path(tmp)
            # Create device dir with bDeviceClass = 8 (decimal)
            dev_dir = usb_root / "1-2"
            dev_dir.mkdir()
            (dev_dir / "bDeviceClass").write_text("8")
            (dev_dir / "idVendor").write_text("0781")
            (dev_dir / "idProduct").write_text("5581")
            # No interfaces needed
            with mock.patch("media.usb.device.SYS_BUS_USB_DEVICES", usb_root):
                self.assertTrue(is_mass_storage_device("1-2", root=usb_root))

    @unittest.skipIf(os.name == "nt", "Colon in directory name invalid on Windows")
    def test_interface_class_mass_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb_root = Path(tmp)
            # Device with class 00 (per-interface)
            dev_dir = usb_root / "1-2"
            dev_dir.mkdir()
            (dev_dir / "bDeviceClass").write_text("0")
            (dev_dir / "idVendor").write_text("0781")
            (dev_dir / "idProduct").write_text("5581")
            # Interface with bInterfaceClass = 08
            iface_dir = usb_root / "1-2:1.0"
            iface_dir.mkdir()
            (iface_dir / "bInterfaceClass").write_text("8")
            with mock.patch("media.usb.device.SYS_BUS_USB_DEVICES", usb_root):
                self.assertTrue(is_mass_storage_device("1-2", root=usb_root))

    def test_hub_not_mass_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb_root = Path(tmp)
            dev_dir = usb_root / "1-2"
            dev_dir.mkdir()
            (dev_dir / "bDeviceClass").write_text("9")  # Hub
            (dev_dir / "idVendor").write_text("05e3")
            (dev_dir / "idProduct").write_text("0610")
            with mock.patch("media.usb.device.SYS_BUS_USB_DEVICES", usb_root):
                self.assertFalse(is_mass_storage_device("1-2", root=usb_root))

    def test_unknown_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb_root = Path(tmp)
            with mock.patch("media.usb.device.SYS_BUS_USB_DEVICES", usb_root):
                self.assertFalse(is_mass_storage_device("9-9", root=usb_root))


class TestUSBStorageSimulation(unittest.TestCase):
    """Tests for USB storage simulation and discovery."""

    def setUp(self):
        clear_storage_simulation()

    def tearDown(self):
        clear_storage_simulation()

    def test_storage_simulation_roundtrip(self):
        set_storage_simulation({"sdb": "1-2"})
        devices = discover_usb_storage()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].block_name, "sdb")
        self.assertEqual(devices[0].usb_name, "1-2")
        self.assertEqual(devices[0].device_path, "/dev/sdb")
        clear_storage_simulation()
        self.assertEqual(discover_usb_storage(), [])

    def test_read_storage_device_with_usb_sim(self):
        # Set both simulations
        set_simulation({
            "1-2": {"idVendor": "0781", "idProduct": "5581",
                    "product": "Ultra Fit", "speed": "480"},
        })
        set_storage_simulation({"sdb": "1-2"})
        devices = discover_usb_storage()
        self.assertEqual(len(devices), 1)
        disk = devices[0]
        self.assertIsNotNone(disk.usb)
        self.assertEqual(disk.usb.product, "Ultra Fit")
        self.assertEqual(disk.usb.vendor_id, 0x0781)
        clear_storage_simulation()
        clear_simulation()


@unittest.skipIf(os.name == "nt", "Symlink resolution test requires POSIX")
class TestUSBBackingResolution(unittest.TestCase):
    """Test usb_backing_device symlink resolution."""

    def test_backing_device_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            block_root = Path(tmp) / "block"
            usb_root = Path(tmp) / "usb"
            block_root.mkdir()
            usb_root.mkdir()
            # USB device directory with idVendor/idProduct
            usb_dev = usb_root / "1-2"
            usb_dev.mkdir()
            (usb_dev / "idVendor").write_text("0781")
            (usb_dev / "idProduct").write_text("5581")
            # Interface directory (chain)
            iface = usb_dev / "1-2:1.0"
            iface.mkdir()
            # SCSI target chain
            host = iface / "host2"
            host.mkdir()
            target = host / "target2:0:0"
            target.mkdir()
            scsi_dev = target / "2:0:0:0"
            scsi_dev.mkdir()
            # Block device symlink
            block_dev = block_root / "sdb"
            block_dev.mkdir()
            (block_dev / "device").symlink_to(scsi_dev)
            # Call with mocked roots
            result = usb_backing_device("sdb", sys_block=block_root)
            self.assertEqual(result, "1-2")


class TestDeviceControl(unittest.TestCase):
    """Tests for privileged device control operations."""

    def setUp(self):
        # Patch gate to avoid capability checks
        self.gate_patcher = mock.patch("media.usb.cli.gate")
        self.mock_gate = self.gate_patcher.start()

    def tearDown(self):
        self.gate_patcher.stop()

    def test_set_authorized_writes_sysfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb_root = Path(tmp)
            dev = usb_root / "1-2"
            dev.mkdir()
            (dev / "authorized").write_text("1")
            set_authorized("1-2", False, root=usb_root)
            self.assertEqual((dev / "authorized").read_text(), "0")
            self.mock_gate.require.assert_called()
            set_authorized("1-2", True, root=usb_root)
            self.assertEqual((dev / "authorized").read_text(), "1")

    def test_remove_device_writes_sysfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb_root = Path(tmp)
            dev = usb_root / "1-2"
            dev.mkdir()
            remove_device("1-2", root=usb_root)
            self.assertEqual((dev / "remove").read_text(), "1")
            self.mock_gate.require.assert_called()

    def test_reset_device_toggles_authorized(self):
        with tempfile.TemporaryDirectory() as tmp:
            usb_root = Path(tmp)
            dev = usb_root / "1-2"
            dev.mkdir()
            (dev / "authorized").write_text("1")
            with mock.patch("media.usb.cli.time.sleep"):  # avoid delay
                reset_device("1-2", root=usb_root, delay=0)
            self.assertEqual((dev / "authorized").read_text(), "1")
            self.assertEqual(self.mock_gate.require.call_count, 1)

    def test_invalid_name_raises(self):
        with self.assertRaises(UsbCLIError):
            set_authorized("not-a-usb-name", True)
        with self.assertRaises(UsbCLIError):
            remove_device("not-a-usb-name")
        with self.assertRaises(UsbCLIError):
            reset_device("not-a-usb-name")


class TestLSUSBCliWrapper(unittest.TestCase):
    """Tests for lsusb command wrappers."""

    @mock.patch("media.usb.cli.shutil.which", return_value="/usr/bin/lsusb")
    @mock.patch("media.usb.cli.subprocess.run")
    def test_list_devices(self, mock_run, mock_which):
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout=("Bus 001 Device 002: ID 0781:5581 SanDisk\n"
                    "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation\n"),
            stderr="",
        )
        devices = list_devices()
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["vid"], "0781")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args, ["lsusb"])

    @mock.patch("media.usb.cli.shutil.which", return_value="/usr/bin/lsusb")
    @mock.patch("media.usb.cli.subprocess.run")
    def test_list_tree(self, mock_run, mock_which):
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout=("/:  Bus 02.Port 1: Dev 1, Class=root_hub\n"
                    "    |__ Port 1: Dev 2, If 0, Class=Mass Storage\n"),
            stderr="",
        )
        tree = list_tree()
        self.assertEqual(len(tree), 2)
        args = mock_run.call_args[0][0]
        self.assertIn("-t", args)

    @mock.patch("media.usb.cli.shutil.which", return_value="/usr/bin/lsusb")
    @mock.patch("media.usb.cli.subprocess.run")
    def test_verbose_device_selector_format(self, mock_run, mock_which):
        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        verbose_device(1, 4)
        args = mock_run.call_args[0][0]
        # Should use -s bus:dev with zero-padded 3-digit format
        self.assertIn("-s", args)
        self.assertIn("001:004", args)

    @mock.patch("media.usb.cli.shutil.which", return_value=None)
    def test_missing_lsusb_raises(self, mock_which):
        with self.assertRaises(UsbCLIError):
            list_devices()

    @mock.patch("media.usb.cli.shutil.which", return_value="/usr/bin/lsusb")
    @mock.patch("media.usb.cli.subprocess.run")
    def test_nonzero_exit_raises(self, mock_run, mock_which):
        mock_run.return_value = mock.Mock(returncode=1, stdout="", stderr="error")
        with self.assertRaises(UsbCLIError):
            list_devices()


if __name__ == "__main__":
    unittest.main()