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
UmerOS /dev Modern Peripheral & Storage Devices.

Modern mainline techniques adopted here (previously absent from UmerOS):

  GpioCharDevice   /dev/gpiochipN          line-based GPIO chardev ABI
  ZramDevice       /dev/zram-control + /dev/zramN   compressed RAM block
  UserfaultfdNode  /dev/userfaultfd        k6.1+ device-node entry point
  UsbGadgetDevice  /dev/hidgN, /dev/functionfs      device-side USB
  NvmeGenericDev   /dev/ngXnY              NVMe per-namespace char nodes
  PtpClockDevice   /dev/ptpN               PTP hardware clock nodes
  RfKillDevice     /dev/rfkill             radio kill-switch multiplexer
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.ModernDevices")


class GpioCharDevice:
    """GPIO character-device ABI — /dev/gpiochip0..N.

    Replaces the deprecated /sys/class/gpio interface: lines are claimed
    by offset via GPIO_GET_LINEHANDLE_IOCTL, enabling event-driven edge
    monitoring and safe multi-consumer semantics (gpiod tooling).
    """

    CHIP_MAJOR = 254
    LINES_PER_CHIP = 32

    def __init__(self, chips: int = 2):
        self._chips = [self._chip_info(i) for i in range(chips)]
        mgr = DeviceManager.get_instance()
        for i in range(chips):
            mgr.create_node(DeviceNode(
                name=f"gpiochip{i}", path=f"/dev/gpiochip{i}",
                dev_type=DeviceType.CHAR,
                major=self.CHIP_MAJOR, minor=i, mode=0o660,
                description=f"GPIO controller chip {i} ({self.LINES_PER_CHIP} lines)",
                ioctl_callback=lambda req, arg: 0,
            ))
        log.info("GpioCharDevice created (%d chips)", chips)

    @staticmethod
    def _chip_info(index: int) -> Dict[str, Any]:
        return {
            "path": f"/dev/gpiochip{index}",
            "label": f"umeros-gpio-{index}",
            "lines": 32,
            "used_lines": [],
        }

    def request_line(self, chip: int, offset: int, consumer: str) -> bool:
        info = self._chips[chip]
        if offset in info["used_lines"]:
            return False
        info["used_lines"].append(offset)
        log.debug("gpio line %s.%d claimed by %s", info["path"], offset, consumer)
        return True

    def get_info(self) -> Dict[str, Any]:
        return {"chips": self._chips}


class ZramDevice:
    """ZRAM — compressed RAM block devices.

    /dev/zram-control   hot-add/remove control node
    /dev/zram0..N       compressed block devices typically used as swap

    Modern default swap strategy (zram-generator): pages swapped to RAM
    are compressed with lz4/zstd, trading cheap CPU for avoided disk I/O.
    """

    ZRAM_MAJOR = 230
    COMPRESSION_ALGO = "lz4"

    def __init__(self, devices: int = 1):
        self._devices: List[Dict[str, Any]] = []
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="zram-control", path="/dev/zram-control",
            dev_type=DeviceType.CHAR, major=self.ZRAM_MAJOR, minor=254,
            mode=0o600, description="zram hot-add/remove control",
            ioctl_callback=lambda req, arg: 0,
        ))
        for i in range(devices):
            mgr.create_node(DeviceNode(
                name=f"zram{i}", path=f"/dev/zram{i}",
                dev_type=DeviceType.BLOCK, major=self.ZRAM_MAJOR, minor=i,
                mode=0o660, description=f"Compressed RAM disk {i}",
                read_callback=lambda size: b"\x00" * min(size, 4096),
                write_callback=lambda data: len(data),
            ))
            self._devices.append({
                "path": f"/dev/zram{i}",
                "algo": self.COMPRESSION_ALGO,
                "disksize_bytes": 2 * 1024 * 1024 * 1024,
                "orig_data_bytes": 0,
                "compr_data_bytes": 0,
            })
        log.info("ZramDevice created (%d devices)", devices)

    def stat(self, index: int = 0) -> Dict[str, Any]:
        dev = self._devices[index]
        orig, compr = dev["orig_data_bytes"], dev["compr_data_bytes"]
        ratio = round(orig / compr, 2) if compr else 0.0
        return {**dev, "ratio": ratio}

    def record_swap(self, orig: int, compressed: int) -> None:
        dev = self._devices[0]
        dev["orig_data_bytes"] += orig
        dev["compr_data_bytes"] += compressed

    def get_info(self) -> Dict[str, Any]:
        return {"devices": self._devices, "algo": self.COMPRESSION_ALGO}

    def __repr__(self) -> str:
        return f"<ZramDevice n={len(self._devices)}>"


class UserfaultfdNode:
    """/dev/userfaultfd — device-node entry to userfaultfd (kernel 6.1+).

    Sandboxes/containers can be granted this single node instead of the
    userfaultfd(2) syscall; opening it yields an fd whose USERFAULTFD_IOC_NEW
    ioctl creates real userfaultfd handles for post-copy live migration
    and QEMU demand paging.
    """

    PATH = "/dev/userfaultfd"

    def __init__(self):
        DeviceManager.get_instance().create_node(DeviceNode(
            name="userfaultfd", path=self.PATH,
            dev_type=DeviceType.CHAR, major=10, minor=126, mode=0o600,
            description="userfaultfd entry point (syscall-free)",
            ioctl_callback=lambda req, arg: 0,
        ))
        self._handles = 0
        log.info("UserfaultfdNode created")

    def new_handle(self) -> int:
        self._handles += 1
        return self._handles

    def get_info(self) -> Dict[str, Any]:
        return {"path": self.PATH, "open_handles": self._handles}

    def __repr__(self) -> str:
        return f"<UserfaultfdNode handles={self._handles}>"


class UsbGadgetDevice:
    """USB gadget — device-side USB interfaces.

    /dev/hidg0..N     HID gadget keyboards/mice (configfs-composed)
    /dev/functionfs   userspace function transport for custom gadgets

    Lets UmerOS present itself as a USB peripheral (keyboard emulation,
    network, mass-storage) through configfs-defined compositions.
    """

    def __init__(self, hid_devices: int = 1):
        mgr = DeviceManager.get_instance()
        for i in range(hid_devices):
            mgr.create_node(DeviceNode(
                name=f"hidg{i}", path=f"/dev/hidg{i}",
                dev_type=DeviceType.CHAR, major=248, minor=i, mode=0o660,
                description=f"HID gadget endpoint {i}",
                write_callback=lambda data: len(data),
            ))
        mgr.create_node(DeviceNode(
            name="functionfs", path="/dev/functionfs",
            dev_type=DeviceType.CHAR, major=10, minor=239, mode=0o600,
            description="Userspace USB function transport (ffs)",
            read_callback=lambda size: b"",
            write_callback=lambda data: len(data),
        ))
        self._hid_count = hid_devices
        log.info("UsbGadgetDevice created")

    def send_hid_report(self, index: int, report: bytes) -> int:
        log.debug("hidg%d <- %d byte report", index, len(report))
        return len(report)

    def get_info(self) -> Dict[str, Any]:
        return {"hidg_nodes": self._hid_count, "functionfs": "/dev/functionfs"}

    def __repr__(self) -> str:
        return f"<UsbGadgetDevice hidg={self._hid_count}>"


class NvmeGenericDevice:
    """NVMe generic character nodes — /dev/ngXnY (+ /dev/nvmeX for ctrl).

    Exposes admin + per-namespace passthrough commands without claiming
    the block namespace; required by nvme-cli modern commands and used
    alongside /dev/nvme*n block nodes.
    """

    GENERIC_MAJOR = 245

    def __init__(self, controllers: int = 1):
        self._nodes: List[str] = []
        mgr = DeviceManager.get_instance()
        for c in range(controllers):
            mgr.create_node(DeviceNode(
                name=f"nvme{c}c", path=f"/dev/nvme{c}c",
                dev_type=DeviceType.CHAR, major=self.GENERIC_MAJOR,
                minor=c * 16, mode=0o600,
                description=f"NVMe controller {c} char node",
            ))
            self._nodes.append(f"/dev/nvme{c}c")
            for ns in range(1, 3):
                name = f"ng{c}n{ns}"
                mgr.create_node(DeviceNode(
                    name=name, path=f"/dev/{name}",
                    dev_type=DeviceType.CHAR, major=self.GENERIC_MAJOR,
                    minor=c * 16 + ns, mode=0o600,
                    description=f"NVMe generic namespace node {name}",
                ))
                self._nodes.append(f"/dev/{name}")
        log.info("NvmeGenericDevice created (%d nodes)", len(self._nodes))

    def get_info(self) -> Dict[str, Any]:
        return {"generic_nodes": self._nodes}

    def __repr__(self) -> str:
        return f"<NvmeGenericDevice nodes={len(self._nodes)}>"


class PtpClockDevice:
    """PTP hardware clocks — /dev/ptp0..N.

    Provides nanosecond-grade timestamps to time stacks (linuxptp,
    chrony, TSN). Each NIC with PHC support exposes one node; clock_gettime
    on the fd's clockid reads hardware time directly.
    """

    PTP_MAJOR = 247

    def __init__(self, clocks: int = 1):
        self._clocks: List[Dict[str, Any]] = []
        mgr = DeviceManager.get_instance()
        for i in range(clocks):
            mgr.create_node(DeviceNode(
                name=f"ptp{i}", path=f"/dev/ptp{i}",
                dev_type=DeviceType.CHAR, major=self.PTP_MAJOR, minor=i,
                mode=0o600, description=f"PTP hardware clock {i}",
                ioctl_callback=lambda req, arg: 0,
            ))
            self._clocks.append({"path": f"/dev/ptp{i}", "freq_hz": 1_000_000_000})
        log.info("PtpClockDevice created (%d clocks)", clocks)

    def hw_time_ns(self, index: int = 0) -> int:
        return time.time_ns()

    def get_info(self) -> Dict[str, Any]:
        return {"clocks": self._clocks}

    def __repr__(self) -> str:
        return f"<PtpClockDevice clocks={len(self._clocks)}>"


class RfKillDevice:
    """/dev/rfkill — radio transmit-kill multiplexer.

    One node multiplexing wifi/bt/wwan/nfc soft+hard kill state as a
    stream of `rfkill_event` structs; NetworkManager and desktop shells
    consume it instead of poking each radio subsystem separately.
    """

    PATH = "/dev/rfkill"

    RFKILL_TYPE_NAMES = ("wlan", "bluetooth", "wwan", "gps", "fm", "nfc")

    def __init__(self):
        DeviceManager.get_instance().create_node(DeviceNode(
            name="rfkill", path=self.PATH,
            dev_type=DeviceType.CHAR, major=10, minor=59, mode=0o660,
            description="Radio kill switch event multiplexer",
            read_callback=self._on_read,
        ))
        self._radios = [
            {"idx": 0, "type": "wlan", "soft": False, "hard": False},
            {"idx": 1, "type": "bluetooth", "soft": False, "hard": False},
        ]
        log.info("RfKillDevice created")

    def _on_read(self, size: int) -> bytes:
        return b"\x00" * min(size, 8)

    def set_soft_block(self, type_name: str, blocked: bool) -> bool:
        for r in self._radios:
            if r["type"] == type_name:
                r["soft"] = blocked
                log.debug("rfkill %s soft=%s", type_name, blocked)
                return True
        return False

    def list_radios(self) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._radios]

    def get_info(self) -> Dict[str, Any]:
        return {"path": self.PATH, "radios": self.list_radios()}

    def __repr__(self) -> str:
        return f"<RfKillDevice radios={len(self._radios)}>"
