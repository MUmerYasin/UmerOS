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
UmerOS tests - media.nvme
=============================

Unit tests for the NVMe / M.2 support package:
sysfs discovery (real + simulated), Identify
Controller / Namespace parsing, SMART/Health log
parsing and health assessment, M.2 form factor /
keying / PCIe link model, and the capability-gated
nvme-cli wrapper.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from media.nvme import cli as nvme_cli
from media.nvme import device as nvme_device
from media.nvme import identify as nvme_identify
from media.nvme import m2 as nvme_m2
from media.nvme import smart as nvme_smart

from core.capability_gate import gate

from media.nvme.device import (
    KIND_ALIAS,
    KIND_CONTROLLER,
    KIND_NAMESPACE,
    KIND_PARTITION,
    classify_nvme_name,
    clear_simulation,
    controller_of,
    discover,
    discover_namespaces,
    get_simulation,
    set_simulation,
)
from media.nvme.identify import (
    IDENTIFY_SIZE,
    LBFormat,
    parse_identify_controller,
    parse_identify_namespace,
)
from media.nvme.m2 import (
    M2DriveInfo,
    M2FormFactor,
    M2Keying,
    form_factor_from_dims,
    keying_supports_nvme,
    lanes_from_link_width,
    pcie_link_from_sysfs,
)
from media.nvme.smart import (
    HealthLevel,
    SMART_LOG_SIZE,
    assess_health,
    critical_warning_reasons,
    kelvin_to_celsius,
    parse_smart_log,
)


def _build_controller_blob() -> bytes:
    blob = bytearray(IDENTIFY_SIZE)
    blob[0:2] = (0x1CC8).to_bytes(2, "little")
    blob[4:24] = b"S1234567890ABCDEF".ljust(20, b" ")
    blob[24:64] = b"WDC WD SN770 1TB".ljust(40, b" ")
    blob[64:72] = b"111070WD"
    blob[72] = 6
    blob[73:76] = bytes([0x00, 0xA0, 0xB8])
    blob[78:80] = (7).to_bytes(2, "little")
    blob[80:84] = (0x00010400).to_bytes(4, "little")
    blob[236:238] = (328).to_bytes(2, "little")
    blob[238:240] = (343).to_bytes(2, "little")
    blob[516:520] = (8).to_bytes(4, "little")
    blob[520:522] = (0x4F).to_bytes(2, "little")
    return bytes(blob)


def _build_namespace_blob() -> bytes:
    blob = bytearray(IDENTIFY_SIZE)
    blob[0:8] = (1000).to_bytes(8, "little")
    blob[8:16] = (1000).to_bytes(8, "little")
    blob[16:24] = (500).to_bytes(8, "little")
    blob[24] = 0
    blob[25] = 1
    blob[26] = 0
    blob[128:130] = (8).to_bytes(2, "little")
    blob[130] = 12
    blob[131] = 2
    blob[132:134] = (16).to_bytes(2, "little")
    blob[134] = 9
    blob[135] = 0
    return bytes(blob)


def _build_smart_blob() -> bytes:
    blob = bytearray(SMART_LOG_SIZE)
    blob[0] = 0
    blob[1:3] = (300).to_bytes(2, "little")
    blob[3] = 100
    blob[4] = 10
    blob[5] = 0
    blob[32:48] = (12345).to_bytes(16, "little")
    blob[48:64] = (6789).to_bytes(16, "little")
    blob[112:128] = (42).to_bytes(16, "little")
    blob[128:144] = (9999).to_bytes(16, "little")
    blob[224:240] = (301).to_bytes(2, "little") * 8
    return bytes(blob)


class _FakeCompleted:
    """Mimics subprocess.CompletedProcess."""

    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class TestClassifyNvmeName(unittest.TestCase):
    """Kernel NVMe device-name classification."""

    def test_controller_names(self):
        self.assertEqual(classify_nvme_name("nvme0"), KIND_CONTROLLER)
        self.assertEqual(classify_nvme_name("nvme12"), KIND_CONTROLLER)

    def test_namespace_names(self):
        self.assertEqual(classify_nvme_name("nvme0n1"), KIND_NAMESPACE)
        self.assertEqual(classify_nvme_name("nvme3n42"), KIND_NAMESPACE)

    def test_partition_names(self):
        self.assertEqual(classify_nvme_name("nvme0n1p1"), KIND_PARTITION)
        self.assertEqual(classify_nvme_name("nvme2n9p15"), KIND_PARTITION)

    def test_alias_names(self):
        self.assertEqual(classify_nvme_name("nvme0c1n1"), KIND_ALIAS)

    def test_non_nvme_names(self):
        for name in ("sda", "nvme", "nvme0x", "nvme-0", "", "mmcblk0"):
            self.assertIsNone(classify_nvme_name(name), name)

    def test_whitespace_tolerated(self):
        self.assertEqual(classify_nvme_name("  nvme0  "), KIND_CONTROLLER)

    def test_controller_of(self):
        self.assertEqual(controller_of("nvme0n1"), "nvme0")
        self.assertEqual(controller_of("nvme3n42"), "nvme3")
        self.assertEqual(controller_of("nvme0n1p2"), "nvme0")
        self.assertIsNone(controller_of("sda"))
        self.assertIsNone(controller_of("nvme0"))


class TestDeviceDiscoverySimulation(unittest.TestCase):
    """Simulated sysfs discovery (no real hardware)."""

    SIM = {
        "nvme0": {
            "model": "WDC WD SN770 1TB",
            "serial": "20234A805352",
            "firmware_rev": "111070WD",
            "transport": "pcie",
            "address": "0000:01:00.0",
            "cntlid": "1",
            "state": "live",
            "numa_node": "0",
            "queue_count": "64",
            "sqsize": "1023",
            "subsysnqn": "nqn.2014-08.org.nvmexpress:uuid:1",
        },
        "nvme0n1": {
            "nsid": "1",
            "size": str(1024 * 1024 * 1024 // 512),
            "uuid": "00000000-0000-0000-0000-000000000001",
            "fmt_lba_size": "512",
        },
        "nvme0n1p1": {
            "nsid": "1",
            "size": str(512 * 1024 * 1024 // 512),
        },
    }

    def setUp(self):
        set_simulation(self.SIM)

    def tearDown(self):
        clear_simulation()

    def test_discovery_finds_controller(self):
        ctrls = discover()
        self.assertEqual(len(ctrls), 1)
        ctrl = ctrls[0]
        self.assertEqual(ctrl.name, "nvme0")
        self.assertEqual(ctrl.model, "WDC WD SN770 1TB")
        self.assertEqual(ctrl.serial, "20234A805352")
        self.assertEqual(ctrl.firmware, "111070WD")
        self.assertEqual(ctrl.transport, "pcie")
        self.assertEqual(ctrl.pci_address, "0000:01:00.0")
        self.assertEqual(ctrl.cntlid, 1)
        self.assertEqual(ctrl.state, "live")
        self.assertEqual(ctrl.numa_node, 0)
        self.assertEqual(ctrl.queue_count, 64)
        self.assertEqual(ctrl.sqsize, 1023)
        self.assertEqual(
            ctrl.subsysnqn, "nqn.2014-08.org.nvmexpress:uuid:1"
        )
        self.assertEqual(ctrl.device_path, "/dev/nvme0")

    def test_namespace_attached_to_controller(self):
        ctrls = discover()
        self.assertEqual(ctrls[0].namespaces, ["nvme0n1"])

    def test_namespace_fields(self):
        ns_list = discover_namespaces()
        self.assertEqual(len(ns_list), 2)
        ns = next(n for n in ns_list if n.name == "nvme0n1")
        self.assertEqual(ns.controller, "nvme0")
        self.assertEqual(ns.nsid, 1)
        self.assertEqual(ns.size_bytes, 1024 ** 3)
        self.assertEqual(ns.fmt_lba_size, 512)
        self.assertEqual(ns.uuid, "00000000-0000-0000-0000-000000000001")
        self.assertEqual(ns.device_path, "/dev/nvme0n1")

    def test_simulation_registry(self):
        self.assertIs(get_simulation(), self.SIM)
        self.assertTrue(nvme_device.available())
        clear_simulation()
        self.assertIsNone(get_simulation())
        if not nvme_device.SYS_CLASS_NVME.exists():
            self.assertFalse(nvme_device.available())

    def test_empty_simulation(self):
        set_simulation({})
        self.assertEqual(discover(), [])
        self.assertEqual(discover_namespaces(), [])


class TestSysfsDiscovery(unittest.TestCase):
    """Real sysfs-tree discovery against a temp directory."""

    def _make_tree(self, root: Path) -> None:
        ctrl = root / "nvme0"
        ctrl.mkdir()
        (ctrl / "model").write_text("Samsung SSD 980 PRO\n")
        (ctrl / "serial").write_text("S5J7NX0R123456A\n")
        (ctrl / "firmware_rev").write_text("4B6QCXP7\n")
        (ctrl / "transport").write_text("pcie\n")
        (ctrl / "address").write_text("0000:03:00.0\n")
        (ctrl / "cntlid").write_text("2\n")
        (ctrl / "state").write_text("live\n")
        (ctrl / "numa_node").write_text("0\n")
        (ctrl / "queue_count").write_text("32\n")
        (ctrl / "sqsize").write_text("1023\n")
        ns = root / "nvme0n1"
        ns.mkdir()
        (ns / "nsid").write_text("1\n")
        (ns / "size").write_text(str(2 * 1024 * 1024 * 1024 // 512) + "\n")
        (ns / "uuid").write_text("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n")
        (ns / "fmt_lba_size").write_text("512\n")

    def test_discovery_from_temp_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_tree(root)
            ctrls = discover(root=root)
            self.assertEqual(len(ctrls), 1)
            ctrl = ctrls[0]
            self.assertEqual(ctrl.model, "Samsung SSD 980 PRO")
            self.assertEqual(ctrl.serial, "S5J7NX0R123456A")
            self.assertEqual(ctrl.firmware, "4B6QCXP7")
            self.assertEqual(ctrl.pci_address, "0000:03:00.0")
            self.assertEqual(ctrl.cntlid, 2)
            self.assertEqual(ctrl.namespaces, ["nvme0n1"])
            ns = discover_namespaces(root=root)
            self.assertEqual(len(ns), 1)
            self.assertEqual(ns[0].size_bytes, 2 * 1024 ** 3)

    def test_missing_root_returns_empty(self):
        self.assertEqual(discover(root=Path("/nonexistent/path")), [])
        self.assertEqual(discover_namespaces(root=Path("/nonexistent")), [])

    def test_empty_root_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(discover(root=Path(tmp)), [])

    def test_read_controller_info_missing(self):
        self.assertIsNone(nvme_device.read_controller_info("nvme9"))

    def test_read_namespace_info_missing(self):
        self.assertIsNone(nvme_device.read_namespace_info("nvme9n1"))

    def test_read_subsystem_info_missing(self):
        self.assertIsNone(nvme_device.read_subsystem_info("nvme-subsys9"))


class TestIdentifyController(unittest.TestCase):
    """Identify Controller (CNS 0, 4096 bytes) parsing."""

    def test_parse_fields(self):
        ctrl = parse_identify_controller(_build_controller_blob())
        self.assertEqual(ctrl.vid, 0x1CC8)
        self.assertEqual(ctrl.sn, "S1234567890ABCDEF")
        self.assertEqual(ctrl.mn, "WDC WD SN770 1TB")
        self.assertEqual(ctrl.fr, "111070WD")
        self.assertEqual(ctrl.rab, 6)
        self.assertEqual(ctrl.ieee_oui, "00-a0-b8")
        self.assertEqual(ctrl.cntlid, 7)
        self.assertEqual(ctrl.ver, 0x00010400)
        self.assertEqual(ctrl.spec_version, "1.4")
        self.assertEqual(ctrl.wctemp_k, 328)
        self.assertEqual(ctrl.cctemp_k, 343)
        self.assertAlmostEqual(ctrl.wctemp_c, 328 - 273.15)
        self.assertAlmostEqual(ctrl.cctemp_c, 343 - 273.15)
        self.assertEqual(ctrl.nn, 8)
        self.assertEqual(ctrl.oncs, 0x4F)

    def test_short_payload_raises(self):
        with self.assertRaises(ValueError):
            parse_identify_controller(b"short")

    def test_empty_payload_raises(self):
        with self.assertRaises(ValueError):
            parse_identify_controller(b"")


class TestIdentifyNamespace(unittest.TestCase):
    """Identify Namespace (CNS 1, 4096 bytes) parsing."""

    def test_parse_fields(self):
        ns = parse_identify_namespace(_build_namespace_blob())
        self.assertEqual(ns.nsize, 1000)
        self.assertEqual(ns.ncap, 1000)
        self.assertEqual(ns.nuse, 500)
        self.assertEqual(ns.nlbaf, 1)
        self.assertEqual(ns.flbas, 0)
        self.assertEqual(len(ns.lbaf), 2)
        self.assertEqual(ns.lbaf[0].metadata_size, 8)
        self.assertEqual(ns.lbaf[0].data_size_exp, 12)
        self.assertEqual(ns.lbaf[0].block_size, 4096)
        self.assertEqual(ns.lbaf[0].relative_performance, 2)
        self.assertEqual(ns.lbaf[1].metadata_size, 16)
        self.assertEqual(ns.lbaf[1].data_size_exp, 9)
        self.assertEqual(ns.lbaf[1].block_size, 512)

    def test_active_lba_format(self):
        ns = parse_identify_namespace(_build_namespace_blob())
        self.assertEqual(ns.active_lba_format.block_size, 4096)
        self.assertEqual(ns.block_size, 4096)
        self.assertEqual(ns.capacity_bytes, 1000 * 4096)
        self.assertEqual(ns.used_bytes, 500 * 4096)

    def test_flbas_selects_second_format(self):
        blob = bytearray(_build_namespace_blob())
        blob[26] = 1  # FLBAS low nibble selects lbaf[1]
        ns = parse_identify_namespace(bytes(blob))
        self.assertEqual(ns.active_lba_format.block_size, 512)
        self.assertEqual(ns.capacity_bytes, 1000 * 512)

    def test_short_payload_raises(self):
        with self.assertRaises(ValueError):
            parse_identify_namespace(b"short")

    def test_lbformat_block_size(self):
        self.assertEqual(LBFormat(data_size_exp=12).block_size, 4096)
        self.assertEqual(LBFormat(data_size_exp=9).block_size, 512)
        self.assertEqual(LBFormat(data_size_exp=0).block_size, 1)


class TestSmartLog(unittest.TestCase):
    """SMART/Health log (Log ID 0x02, 512 bytes) parsing."""

    def test_parse_fields(self):
        smart = parse_smart_log(_build_smart_blob())
        self.assertEqual(smart.critical_warning, 0)
        self.assertEqual(smart.temperature_k, 300)
        self.assertAlmostEqual(smart.temperature_c, 300 - 273.15)
        self.assertEqual(smart.available_spare, 100)
        self.assertEqual(smart.available_spare_threshold, 10)
        self.assertEqual(smart.percent_used, 0)
        self.assertEqual(smart.remaining_life_pct, 100)
        self.assertEqual(smart.data_units_read, 12345)
        self.assertEqual(smart.data_units_written, 6789)
        self.assertEqual(smart.power_cycles, 42)
        self.assertEqual(smart.power_on_hours, 9999)
        self.assertEqual(smart.temperature_sensors_k, [301] * 8)

    def test_kelvin_to_celsius(self):
        self.assertAlmostEqual(kelvin_to_celsius(273.15), 0.0)
        self.assertAlmostEqual(kelvin_to_celsius(300), 26.85)

    def test_critical_warning_reasons(self):
        self.assertEqual(critical_warning_reasons(0), [])
        self.assertEqual(
            critical_warning_reasons(0x01),
            ["available spare below threshold"],
        )
        self.assertEqual(
            critical_warning_reasons(0x1F),
            [
                "available spare below threshold",
                "temperature above threshold",
                "NVM subsystem reliability degraded",
                "media in read-only mode",
                "volatile memory backup failed",
            ],
        )

    def test_short_payload_raises(self):
        with self.assertRaises(ValueError):
            parse_smart_log(b"short")


class TestHealthAssessment(unittest.TestCase):
    """Threshold-based health assessment."""

    def test_healthy_drive(self):
        smart = parse_smart_log(_build_smart_blob())
        report = assess_health(smart, wctemp_k=343, cctemp_k=358)
        self.assertEqual(report.level, HealthLevel.OK)
        self.assertEqual(report.reasons, [])
        self.assertEqual(report.remaining_life_pct, 100)

    def test_media_errors_warning(self):
        blob = bytearray(_build_smart_blob())
        blob[160:176] = (3).to_bytes(16, "little")
        smart = parse_smart_log(bytes(blob))
        report = assess_health(smart)
        self.assertEqual(report.level, HealthLevel.WARNING)
        self.assertTrue(any("media" in r for r in report.reasons))

    def test_unsafe_shutdowns_warning(self):
        blob = bytearray(_build_smart_blob())
        blob[144:160] = (7).to_bytes(16, "little")
        smart = parse_smart_log(bytes(blob))
        report = assess_health(smart)
        self.assertEqual(report.level, HealthLevel.WARNING)
        self.assertTrue(any("unsafe shutdown" in r for r in report.reasons))

    def test_spare_below_threshold_critical(self):
        blob = bytearray(_build_smart_blob())
        blob[3] = 5
        smart = parse_smart_log(bytes(blob))
        report = assess_health(smart)
        self.assertEqual(report.level, HealthLevel.CRITICAL)
        self.assertTrue(any("spare" in r for r in report.reasons))

    def test_spare_warning_bit_only(self):
        blob = bytearray(_build_smart_blob())
        blob[0] = 0x02  # temperature warning bit, spare still fine
        smart = parse_smart_log(bytes(blob))
        report = assess_health(smart)
        self.assertEqual(report.level, HealthLevel.WARNING)
        self.assertTrue(any("temperature" in r for r in report.reasons))

    def test_critical_temperature(self):
        blob = bytearray(_build_smart_blob())
        blob[1:3] = (360).to_bytes(2, "little")
        smart = parse_smart_log(bytes(blob))
        report = assess_health(smart, wctemp_k=343, cctemp_k=358)
        self.assertEqual(report.level, HealthLevel.CRITICAL)
        self.assertTrue(any("temperature" in r for r in report.reasons))

    def test_warning_temperature(self):
        blob = bytearray(_build_smart_blob())
        blob[1:3] = (350).to_bytes(2, "little")
        smart = parse_smart_log(bytes(blob))
        report = assess_health(smart, wctemp_k=343, cctemp_k=358)
        self.assertEqual(report.level, HealthLevel.WARNING)

    def test_remaining_life_warning(self):
        blob = bytearray(_build_smart_blob())
        blob[5] = 85  # 15% remaining
        smart = parse_smart_log(bytes(blob))
        report = assess_health(smart)
        self.assertEqual(report.level, HealthLevel.WARNING)

    def test_remaining_life_critical(self):
        blob = bytearray(_build_smart_blob())
        blob[5] = 95  # 5% remaining
        smart = parse_smart_log(bytes(blob))
        report = assess_health(smart)
        self.assertEqual(report.level, HealthLevel.CRITICAL)

    def test_custom_thresholds(self):
        blob = bytearray(_build_smart_blob())
        blob[5] = 80  # 20% remaining
        smart = parse_smart_log(bytes(blob))
        from media.nvme.smart import HealthThresholds
        report = assess_health(
            smart, thresholds=HealthThresholds(remaining_life_warn_pct=50)
        )
        self.assertEqual(report.level, HealthLevel.WARNING)

    def test_reasons_deduplicated(self):
        blob = bytearray(_build_smart_blob())
        blob[0] = 0x02  # temperature warning bit
        blob[1:3] = (350).to_bytes(2, "little")
        smart = parse_smart_log(bytes(blob))
        report = assess_health(smart, wctemp_k=343)
        temp_reasons = [r for r in report.reasons if "temperature" in r]
        self.assertEqual(len(temp_reasons), 1)


class TestM2FormFactors(unittest.TestCase):
    """M.2 form factor and keying model."""

    def test_known_form_factors(self):
        self.assertEqual(form_factor_from_dims(22, 30), M2FormFactor.M2_2230)
        self.assertEqual(form_factor_from_dims(22, 42), M2FormFactor.M2_2242)
        self.assertEqual(form_factor_from_dims(22, 60), M2FormFactor.M2_2260)
        self.assertEqual(form_factor_from_dims(22, 80), M2FormFactor.M2_2280)
        self.assertEqual(
            form_factor_from_dims(22, 110), M2FormFactor.M2_22110
        )

    def test_unknown_dims(self):
        self.assertIsNone(form_factor_from_dims(22, 99))
        self.assertIsNone(form_factor_from_dims(30, 80))

    def test_form_factor_properties(self):
        self.assertEqual(M2FormFactor.M2_2280.dims, (22, 80))
        self.assertEqual(M2FormFactor.M2_2280.width_mm, 22)
        self.assertEqual(M2FormFactor.M2_2280.length_mm, 80)
        self.assertEqual(M2FormFactor.M2_2280.name_mm, "2280")

    def test_keying(self):
        self.assertTrue(keying_supports_nvme(M2Keying.KEY_M))
        self.assertFalse(keying_supports_nvme(M2Keying.KEY_B))
        self.assertFalse(keying_supports_nvme(M2Keying.KEY_BM))
        self.assertEqual(M2Keying.KEY_M.value, "M")
        self.assertEqual(M2Keying.KEY_BM.value, "B+M")

    def test_lanes_from_link_width(self):
        self.assertEqual(lanes_from_link_width("x4"), 4)
        self.assertEqual(lanes_from_link_width("x1"), 1)
        self.assertEqual(lanes_from_link_width("x16"), 16)
        self.assertEqual(lanes_from_link_width(" X2 "), 2)
        self.assertEqual(lanes_from_link_width(4), 4)
        self.assertIsNone(lanes_from_link_width("x0"))
        self.assertIsNone(lanes_from_link_width(0))
        self.assertIsNone(lanes_from_link_width("unknown"))
        self.assertIsNone(lanes_from_link_width(None))

    def test_build_m2_drive(self):
        drive = build = M2DriveInfo(
            form_factor=M2FormFactor.M2_2280,
            keying=M2Keying.KEY_M,
            lanes=4,
            link_speed="8.0 GT/s",
        )
        self.assertEqual(drive.form_factor_name, "M.2 2280")
        self.assertTrue(drive.is_nvme_capable)
        self.assertEqual(drive.transport, "pcie")

        sata = M2DriveInfo(keying=M2Keying.KEY_B)
        self.assertFalse(sata.is_nvme_capable)
        self.assertIsNone(sata.form_factor_name)

    def test_build_helper(self):
        from media.nvme.m2 import build_m2_drive
        drive = build_m2_drive(
            form_factor=M2FormFactor.M2_2280, keying=M2Keying.KEY_M
        )
        self.assertTrue(drive.is_nvme_capable)
        self.assertIsNone(drive.lanes)


class TestM2PCIeLink(unittest.TestCase):
    """PCIe link detection from sysfs."""

    def _make_pci_tree(self, root: Path) -> Path:
        dev = root / "0000:01:00.0"
        dev.mkdir(parents=True)
        (dev / "current_link_speed").write_text("8.0 GT/s\n")
        (dev / "current_link_width").write_text("x4\n")
        return dev

    def test_reads_current_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_pci_tree(root)
            speed, lanes = pcie_link_from_sysfs(
                "0000:01:00.0", bus_root=root
            )
            self.assertEqual(speed, "8.0 GT/s")
            self.assertEqual(lanes, 4)

    def test_falls_back_to_max_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            dev = Path(tmp) / "0000:02:00.0"
            dev.mkdir()
            (dev / "max_link_speed").write_text("16.0 GT/s\n")
            (dev / "max_link_width").write_text("x2\n")
            speed, lanes = pcie_link_from_sysfs(
                "0000:02:00.0", bus_root=Path(tmp)
            )
            self.assertEqual(speed, "16.0 GT/s")
            self.assertEqual(lanes, 2)

    def test_missing_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            speed, lanes = pcie_link_from_sysfs(
                "0000:09:00.0", bus_root=Path(tmp)
            )
            self.assertIsNone(speed)
            self.assertIsNone(lanes)

    def test_garbage_width(self):
        with tempfile.TemporaryDirectory() as tmp:
            dev = Path(tmp) / "0000:03:00.0"
            dev.mkdir()
            (dev / "current_link_speed").write_text("2.5 GT/s\n")
            (dev / "current_link_width").write_text("unknown\n")
            speed, lanes = pcie_link_from_sysfs(
                "0000:03:00.0", bus_root=Path(tmp)
            )
            self.assertEqual(speed, "2.5 GT/s")
            self.assertIsNone(lanes)


class TestNvmeCLI(unittest.TestCase):
    """nvme-cli wrapper (with nvme-cli absent or faked)."""

    def setUp(self):
        self._orig_which = nvme_cli.shutil.which
        self._orig_run = nvme_cli.subprocess.run

    def tearDown(self):
        nvme_cli.shutil.which = self._orig_which
        nvme_cli.subprocess.run = self._orig_run

    def _patch_missing_binary(self):
        nvme_cli.shutil.which = lambda name: None

    def _patch_fake_run(self, run=None):
        nvme_cli.shutil.which = lambda name: "/usr/sbin/nvme"
        if run is not None:
            nvme_cli.subprocess.run = run

    def test_build_args(self):
        self.assertEqual(
            nvme_cli._build_args(["list"], json_output=True),
            ["nvme", "list", "--output-format=json"],
        )
        self.assertEqual(
            nvme_cli._build_args(["id-ctrl", "/dev/nvme0"], json_output=False),
            ["nvme", "id-ctrl", "/dev/nvme0"],
        )

    def test_normalize_device(self):
        normalized = nvme_cli._normalize_device(
            {"DevicePath": "/dev/nvme0", "ModelNumber": "WD"}
        )
        self.assertEqual(
            normalized, {"devicepath": "/dev/nvme0", "modelnumber": "WD"}
        )

    def test_missing_binary_raises(self):
        self._patch_missing_binary()
        for call in (
            lambda: nvme_cli.list_devices(),
            lambda: nvme_cli.identify_controller("/dev/nvme0"),
            lambda: nvme_cli.identify_namespace("/dev/nvme0"),
            lambda: nvme_cli.smart_log("/dev/nvme0"),
            lambda: nvme_cli.self_test_log("/dev/nvme0"),
            lambda: nvme_cli.get_log("/dev/nvme0", 2),
        ):
            with self.assertRaises(nvme_cli.NvmeCLIError):
                call()

    def test_list_devices(self):
        def fake_run(command, **kwargs):
            return _FakeCompleted(
                stdout='{"devices": [{"Device": "/dev/nvme0", '
                       '"DevicePath": "/dev/nvme0", '
                       '"ModelNumber": "WDC WD SN770 1TB", '
                       '"SerialNumber": "20234A805352", '
                       '"FirmwareRevision": "111070WD", '
                       '"Transport": "pcie", "NamespaceId": 1, '
                       '"NamespaceSize": 2097152}]}'
            )
        self._patch_fake_run(fake_run)
        devices = nvme_cli.list_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["devicepath"], "/dev/nvme0")
        self.assertEqual(devices[0]["modelnumber"], "WDC WD SN770 1TB")
        self.assertEqual(devices[0]["transport"], "pcie")

    def test_list_devices_empty(self):
        def fake_run(command, **kwargs):
            return _FakeCompleted(stdout='{"devices": []}')
        self._patch_fake_run(fake_run)
        self.assertEqual(nvme_cli.list_devices(), [])

    def test_identify_commands(self):
        def fake_run(command, **kwargs):
            return _FakeCompleted(stdout='{"vid": 7368}')
        self._patch_fake_run(fake_run)
        ctrl = nvme_cli.identify_controller("/dev/nvme0")
        self.assertEqual(ctrl["vid"], 7368)
        ns = nvme_cli.identify_namespace("/dev/nvme0", nsid=1)
        self.assertEqual(ns["vid"], 7368)
        log = nvme_cli.smart_log("/dev/nvme0", namespace=1)
        self.assertEqual(log["vid"], 7368)
        dlog = nvme_cli.self_test_log("/dev/nvme0")
        self.assertEqual(dlog["vid"], 7368)

    def test_get_log_binary(self):
        def fake_run(command, **kwargs):
            self.assertNotIn("text", kwargs)
            return _FakeCompleted(stdout=b"\x01\x00\x00")
        self._patch_fake_run(fake_run)
        raw = nvme_cli.get_log("/dev/nvme0", 2, log_len=512)
        self.assertEqual(raw, b"\x01\x00\x00")

    def test_nonzero_exit_raises(self):
        def fake_run(command, **kwargs):
            return _FakeCompleted(stderr="boom", returncode=1)
        self._patch_fake_run(fake_run)
        with self.assertRaises(nvme_cli.NvmeCLIError):
            nvme_cli.list_devices()

    def test_timeout_raises(self):
        def fake_run(command, **kwargs):
            raise subprocess.TimeoutExpired(cmd=command, timeout=1)
        self._patch_fake_run(fake_run)
        with self.assertRaises(nvme_cli.NvmeCLIError):
            nvme_cli.list_devices()

    def test_malformed_json_raises(self):
        def fake_run(command, **kwargs):
            return _FakeCompleted(stdout="not json")
        self._patch_fake_run(fake_run)
        with self.assertRaises(nvme_cli.NvmeCLIError):
            nvme_cli.list_devices()

    def test_self_test_start_validation(self):
        self._patch_fake_run(lambda command, **kwargs: _FakeCompleted())
        with self.assertRaises(ValueError):
            nvme_cli.self_test_start("/dev/nvme0", test="bogus")

    def test_fw_commit_validation(self):
        self._patch_fake_run(lambda command, **kwargs: _FakeCompleted())
        with self.assertRaises(ValueError):
            nvme_cli.fw_commit("/dev/nvme0", slot=1, action="bogus")

    def test_fw_download_missing_file(self):
        self._patch_fake_run(lambda command, **kwargs: _FakeCompleted())
        with self.assertRaises(nvme_cli.NvmeCLIError):
            nvme_cli.fw_download("/dev/nvme0", "/nonexistent/fw.bin")

    def test_fw_download_and_commit_runs(self):
        def fake_run(command, **kwargs):
            return _FakeCompleted(stdout="OK")
        self._patch_fake_run(fake_run)
        with tempfile.TemporaryDirectory() as tmp:
            fw = Path(tmp) / "fw.bin"
            fw.write_bytes(b"\x00")
            out = nvme_cli.fw_download("/dev/nvme0", str(fw), slot=0)
            self.assertEqual(out, "OK")
        out = nvme_cli.fw_commit("/dev/nvme0", slot=0, action="activate")
        self.assertEqual(out, "OK")

    def test_reset_commands_run(self):
        def fake_run(command, **kwargs):
            return _FakeCompleted(stdout="Resetting controller")
        self._patch_fake_run(fake_run)
        self.assertEqual(
            nvme_cli.reset_controller("/dev/nvme0"), "Resetting controller"
        )
        self.assertEqual(
            nvme_cli.subsystem_reset("/dev/nvme0"), "Resetting controller"
        )

    def test_self_test_start_runs(self):
        def fake_run(command, **kwargs):
            return _FakeCompleted(stdout="")
        self._patch_fake_run(fake_run)
        self.assertEqual(nvme_cli.self_test_start("/dev/nvme0"), "")


class TestCapabilityGating(unittest.TestCase):
    """Privileged NVMe admin commands are capability-gated."""

    def setUp(self):
        self._state = gate.snapshot()
        self._orig_which = nvme_cli.shutil.which
        self._orig_run = nvme_cli.subprocess.run
        nvme_cli.shutil.which = lambda name: "/usr/sbin/nvme"
        nvme_cli.subprocess.run = lambda command, **kwargs: _FakeCompleted()
        gate.set_strict(True)

    def tearDown(self):
        nvme_cli.shutil.which = self._orig_which
        nvme_cli.subprocess.run = self._orig_run
        gate.restore(self._state)

    def test_strict_mode_denies_privileged_ops(self):
        for call in (
            lambda: nvme_cli.self_test_start("/dev/nvme0"),
            lambda: nvme_cli.reset_controller("/dev/nvme0"),
            lambda: nvme_cli.subsystem_reset("/dev/nvme0"),
            lambda: nvme_cli.fw_commit("/dev/nvme0", slot=1),
            lambda: nvme_cli.fw_download("/dev/nvme0", "/tmp/fw.bin"),
        ):
            with self.assertRaises(PermissionError):
                call()

    def test_gate_require_works_in_strict_mode(self):
        with self.assertRaises(PermissionError):
            gate.require("sys.admin")

    def test_permissive_mode_allows_privileged_ops(self):
        gate.set_strict(False)
        self.assertIsNone(gate.require("sys.admin"))
        self.assertEqual(nvme_cli.reset_controller("/dev/nvme0"), "")

    def test_gate_restored(self):
        # sanity: tearDown restores the original posture
        gate.restore(self._state)
        self.assertEqual(gate.strict, self._state.get("strict", False))


class TestPackageSelfTest(unittest.TestCase):
    """Module and package self-tests run clean."""

    def test_module_selftests(self):
        self.assertTrue(nvme_device._selftest())
        self.assertTrue(nvme_identify._selftest())
        self.assertTrue(nvme_smart._selftest())
        self.assertTrue(nvme_m2._selftest())
        self.assertTrue(nvme_cli._selftest())

    def test_package_selftest(self):
        from media import nvme as nvme_pkg
        self.assertTrue(nvme_pkg._selftest())

    def test_package_exports(self):
        from media import nvme as nvme_pkg
        for name in (
            "discover", "classify_nvme_name", "parse_identify_controller",
            "parse_identify_namespace", "parse_smart_log", "assess_health",
            "M2FormFactor", "M2Keying", "NvmeCLIError", "list_devices",
        ):
            self.assertTrue(hasattr(nvme_pkg, name), name)


if __name__ == "__main__":
    unittest.main()
