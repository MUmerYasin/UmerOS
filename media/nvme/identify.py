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
UmerOS /media/nvme - NVMe Identify Data Parser
==============================================

Parses the 4096-byte payloads returned by the NVMe admin
commands *Identify Controller* (CNS 0) and *Identify Namespace*
(CNS 1), as defined in the NVM Express specification (offsets
per NVM Express 1.4 / 2.0 - these fields are stable across
both revisions).

Pure Python (``struct`` free - only ``int.from_bytes``), no
third-party packages.  Feed the raw bytes from ``nvme id-ctrl``
/ ``nvme id-ns`` (``--output-format=binary``) or from a direct
``NVME_IOCTL_ADMIN_CMD`` passthrough.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .smart import kelvin_to_celsius

IDENTIFY_SIZE = 4096


def _u16(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 2], "little")


def _u32(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 4], "little")


def _u64(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 8], "little")


def _ascii(data: bytes, start: int, end: int) -> str:
    return data[start:end].decode("ascii", errors="replace").rstrip("\x00").strip()


def spec_version_str(version: int) -> str:
    """Render the NVMe specification version word (e.g. 0x00010400 -> "1.4")."""
    return f"{version >> 16}.{(version >> 8) & 0xFF}"


@dataclass
class LBFormat:
    """One LBA format entry (LBAF) from Identify Namespace."""

    metadata_size: int = 0
    data_size_exp: int = 0
    relative_performance: int = 0

    @property
    def block_size(self) -> int:
        """Block size in bytes (2 ** LBADS)."""
        return 1 << self.data_size_exp


@dataclass
class IdentifyController:
    """Parsed Identify Controller data (4096 bytes)."""

    vid: int = 0
    ssvid: int = 0
    sn: str = ""
    mn: str = ""
    fr: str = ""
    rab: int = 0
    ieee_oui: str = ""
    cmic: int = 0
    mdt: int = 0
    cntlid: int = 0
    ver: int = 0
    rtd3r: int = 0
    rtd3e: int = 0
    oaes: int = 0
    ctratt: int = 0
    rrls: int = 0
    wctemp_k: int = 0
    cctemp_k: int = 0
    mtfa: int = 0
    hmpre: int = 0
    hmmin: int = 0
    sqes: int = 0
    cqes: int = 0
    nn: int = 0
    oncs: int = 0
    fuses: int = 0
    vwc: int = 0

    @property
    def spec_version(self) -> str:
        return spec_version_str(self.ver)

    @property
    def wctemp_c(self) -> float:
        return kelvin_to_celsius(self.wctemp_k)

    @property
    def cctemp_c(self) -> float:
        return kelvin_to_celsius(self.cctemp_k)


@dataclass
class IdentifyNamespace:
    """Parsed Identify Namespace data (4096 bytes)."""

    nsize: int = 0
    ncap: int = 0
    nuse: int = 0
    nsfeat: int = 0
    nlbaf: int = 0
    flbas: int = 0
    mc: int = 0
    dpc: int = 0
    dps: int = 0
    nmic: int = 0
    rescap: int = 0
    fpi: int = 0
    dlfeat: int = 0
    nawun: int = 0
    nawupf: int = 0
    nacwu: int = 0
    nabsn: int = 0
    nabo: int = 0
    nabspf: int = 0
    noiob: int = 0
    lbaf: List[LBFormat] = field(default_factory=list)

    @property
    def active_lba_format(self) -> LBFormat:
        """The LBA format selected by the FLBAS field."""
        index = self.flbas & 0x0F
        if self.lbaf and index < len(self.lbaf):
            return self.lbaf[index]
        return LBFormat()

    @property
    def block_size(self) -> int:
        return self.active_lba_format.block_size

    @property
    def capacity_bytes(self) -> int:
        """Total capacity in bytes (NSIZE x active block size)."""
        return self.nsize * self.block_size

    @property
    def used_bytes(self) -> int:
        """Used capacity in bytes (NUSE x active block size)."""
        return self.nuse * self.block_size


def parse_identify_controller(data: bytes) -> IdentifyController:
    """Parse a raw Identify Controller payload (exactly 4096 bytes)."""
    if len(data) < IDENTIFY_SIZE:
        raise ValueError(
            f"Identify Controller data must be at least {IDENTIFY_SIZE} bytes, "
            f"got {len(data)}"
        )
    ctrl = IdentifyController()
    ctrl.vid = _u16(data, 0)
    ctrl.ssvid = _u16(data, 2)
    ctrl.sn = _ascii(data, 4, 24)
    ctrl.mn = _ascii(data, 24, 64)
    ctrl.fr = _ascii(data, 64, 72)
    ctrl.rab = data[72]
    ctrl.ieee_oui = "%02x-%02x-%02x" % (data[73], data[74], data[75])
    ctrl.cmic = data[76]
    ctrl.mdt = data[77]
    ctrl.cntlid = _u16(data, 78)
    ctrl.ver = _u32(data, 80)
    ctrl.rtd3r = _u32(data, 84)
    ctrl.rtd3e = _u32(data, 88)
    ctrl.oaes = _u32(data, 92)
    ctrl.ctratt = _u32(data, 96)
    ctrl.rrls = _u16(data, 100)
    ctrl.wctemp_k = _u16(data, 236)
    ctrl.cctemp_k = _u16(data, 238)
    ctrl.mtfa = _u16(data, 240)
    ctrl.hmpre = _u16(data, 242)
    ctrl.hmmin = _u16(data, 244)
    ctrl.sqes = data[512]
    ctrl.cqes = data[513]
    ctrl.nn = _u32(data, 516)
    ctrl.oncs = _u16(data, 520)
    ctrl.fuses = data[522]
    ctrl.vwc = data[524]
    return ctrl


def parse_identify_namespace(data: bytes) -> IdentifyNamespace:
    """Parse a raw Identify Namespace payload (exactly 4096 bytes)."""
    if len(data) < IDENTIFY_SIZE:
        raise ValueError(
            f"Identify Namespace data must be at least {IDENTIFY_SIZE} bytes, "
            f"got {len(data)}"
        )
    ns = IdentifyNamespace()
    ns.nsize = _u64(data, 0)
    ns.ncap = _u64(data, 8)
    ns.nuse = _u64(data, 16)
    ns.nsfeat = data[24]
    ns.nlbaf = data[25]
    ns.flbas = data[26]
    ns.mc = data[27]
    ns.dpc = data[28]
    ns.dps = data[29]
    ns.nmic = data[30]
    ns.rescap = data[31]
    ns.fpi = data[32]
    ns.dlfeat = data[33]
    ns.nawun = _u16(data, 34)
    ns.nawupf = _u16(data, 36)
    ns.nacwu = _u16(data, 38)
    ns.nabsn = _u16(data, 40)
    ns.nabo = _u16(data, 42)
    ns.nabspf = _u16(data, 44)
    ns.noiob = _u16(data, 46)
    ns.lbaf = []
    for index in range(ns.nlbaf + 1):
        off = 128 + index * 4
        if off + 4 > len(data):
            break
        ms = _u16(data, off)
        lbads = data[off + 2]
        rp = data[off + 3]
        ns.lbaf.append(
            LBFormat(metadata_size=ms, data_size_exp=lbads, relative_performance=rp)
        )
    return ns


def _selftest() -> bool:
    """Run a basic self-test for this module (synthetic payloads)."""
    ctrl_blob = bytearray(IDENTIFY_SIZE)
    ctrl_blob[0:2] = (0x1CC8).to_bytes(2, "little")
    ctrl_blob[4:24] = b"S1234567890ABCDEF".ljust(20, b" ")
    ctrl_blob[24:64] = b"WDC WD SN770 1TB".ljust(40, b" ")
    ctrl_blob[64:72] = b"111070WD"
    ctrl_blob[78:80] = (7).to_bytes(2, "little")
    ctrl_blob[80:84] = (0x00010400).to_bytes(4, "little")
    ctrl_blob[236:238] = (328).to_bytes(2, "little")
    ctrl_blob[238:240] = (343).to_bytes(2, "little")
    ctrl_blob[516:520] = (8).to_bytes(4, "little")

    ctrl = parse_identify_controller(bytes(ctrl_blob))
    assert ctrl.vid == 0x1CC8, hex(ctrl.vid)
    assert ctrl.sn == "S1234567890ABCDEF"
    assert ctrl.mn == "WDC WD SN770 1TB"
    assert ctrl.fr == "111070WD"
    assert ctrl.cntlid == 7
    assert ctrl.spec_version == "1.4"
    assert ctrl.nn == 8
    assert ctrl.wctemp_c == 328 - 273.15
    assert ctrl.cctemp_c == 343 - 273.15

    ns_blob = bytearray(IDENTIFY_SIZE)
    ns_blob[0:8] = (1000).to_bytes(8, "little")
    ns_blob[16:24] = (500).to_bytes(8, "little")
    ns_blob[25] = 1
    ns_blob[26] = 0
    ns_blob[128:130] = (8).to_bytes(2, "little")
    ns_blob[130] = 12
    ns_blob[131] = 2
    ns_blob[132:134] = (16).to_bytes(2, "little")
    ns_blob[134] = 9
    ns_blob[135] = 0

    ns = parse_identify_namespace(bytes(ns_blob))
    assert ns.nsize == 1000
    assert ns.nuse == 500
    assert ns.nlbaf == 1
    assert len(ns.lbaf) == 2
    assert ns.lbaf[0].block_size == 4096
    assert ns.lbaf[0].metadata_size == 8
    assert ns.lbaf[1].block_size == 512
    assert ns.active_lba_format.block_size == 4096
    assert ns.capacity_bytes == 1000 * 4096
    assert ns.used_bytes == 500 * 4096

    try:
        parse_identify_controller(b"short")
    except ValueError:
        pass
    else:
        raise AssertionError("short controller payload must raise ValueError")

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
