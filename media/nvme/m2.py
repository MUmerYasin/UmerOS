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
UmerOS /media/nvme - M.2 Form Factor Model
============================================

Models the physical characteristics of M.2 NVMe SSDs:

* **Form factors** - the standard M.2 module sizes
  (2230, 2242, 2260, 2280, 22110) expressed as
  width x length in millimetres.
* **Edge-connector keying** - M-key (PCIe / NVMe),
  B-key and B+M key (SATA).  Only M-keyed modules
  carry the PCIe lanes required for NVMe.
* **PCIe link** - the negotiated link speed and lane
  count of the drive's PCIe interface, read from
  sysfs (``/sys/bus/pci/devices/<BDF>``).

Pure Python (standard library only), no third-party
packages.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger("UmerOS.Media.NVMe.M2")

PCI_DEVICES_ROOT = Path("/sys/bus/pci/devices")

_LINK_WIDTH_RE = re.compile(r"^\s*x\s*([0-9]+)\s*$", re.IGNORECASE)


class M2FormFactor(Enum):
    """Standard M.2 module form factors (width x length in mm)."""

    M2_2230 = (22, 30)
    M2_2242 = (22, 42)
    M2_2260 = (22, 60)
    M2_2280 = (22, 80)
    M2_22110 = (22, 110)

    def __init__(self, width_mm: int, length_mm: int) -> None:
        self.width_mm = width_mm
        self.length_mm = length_mm

    @property
    def dims(self) -> Tuple[int, int]:
        """Physical dimensions as ``(width_mm, length_mm)``."""
        return (self.width_mm, self.length_mm)

    @property
    def name_mm(self) -> str:
        """Compact dimension string (e.g. ``"2280"``)."""
        return f"{self.width_mm}{self.length_mm}"


def form_factor_from_dims(
    width_mm: int, length_mm: int
) -> Optional[M2FormFactor]:
    """Match raw dimensions to a standard M.2 form factor."""
    for form_factor in M2FormFactor:
        if form_factor.width_mm == width_mm and form_factor.length_mm == length_mm:
            return form_factor
    return None


class M2Keying(Enum):
    """M.2 edge-connector keying types."""

    KEY_M = "M"
    KEY_B = "B"
    KEY_BM = "B+M"


def keying_supports_nvme(keying: M2Keying) -> bool:
    """True when *keying* carries PCIe lanes usable by NVMe.

    M-key modules provide up to 4 PCIe lanes; B-key and
    B+M-key modules only expose the SATA interface.
    """
    return keying == M2Keying.KEY_M


def lanes_from_link_width(link_width: object) -> Optional[int]:
    """Parse a PCIe lane count from ``"x4"``-style strings or ints."""
    if isinstance(link_width, int):
        return link_width if link_width > 0 else None
    match = _LINK_WIDTH_RE.match(str(link_width))
    if match:
        lanes = int(match.group(1))
        return lanes if lanes > 0 else None
    return None


def pcie_link_from_sysfs(
    bdf: str, bus_root: Path = PCI_DEVICES_ROOT
) -> Tuple[Optional[str], Optional[int]]:
    """Read the PCIe link speed and lane count for a device (BDF).

    Args:
        bdf:      PCI bus/device/function address, e.g. ``"0000:01:00.0"``.
        bus_root: sysfs PCI devices directory.

    Returns:
        ``(link_speed, lanes)`` - either may be ``None`` when sysfs
        does not expose the attribute (e.g. non-PCIe transports).
    """
    base = Path(bus_root) / bdf

    def _read(path: Path) -> Optional[str]:
        try:
            return path.read_text(encoding="utf-8", errors="replace").strip()
        except (OSError, IOError):
            return None

    speed = _read(base / "current_link_speed")
    if not speed:
        speed = _read(base / "max_link_speed")
    width_raw = _read(base / "current_link_width")
    if not width_raw:
        width_raw = _read(base / "max_link_width")
    lanes = lanes_from_link_width(width_raw) if width_raw else None
    return speed, lanes


@dataclass
class M2DriveInfo:
    """Physical model of an M.2 drive."""

    form_factor: Optional[M2FormFactor] = None
    keying: Optional[M2Keying] = None
    lanes: Optional[int] = None
    link_speed: Optional[str] = None
    transport: str = "pcie"

    @property
    def form_factor_name(self) -> Optional[str]:
        """Human-readable form factor (e.g. ``"M.2 2280"``)."""
        if self.form_factor is None:
            return None
        return f"M.2 {self.form_factor.name_mm}"

    @property
    def is_nvme_capable(self) -> bool:
        """True when the keying provides PCIe lanes for NVMe."""
        if self.keying is None:
            return False
        return keying_supports_nvme(self.keying)


def build_m2_drive(
    form_factor: Optional[M2FormFactor] = None,
    keying: Optional[M2Keying] = None,
    lanes: Optional[int] = None,
    link_speed: Optional[str] = None,
    transport: str = "pcie",
) -> M2DriveInfo:
    """Assemble an :class:`M2DriveInfo` from its parts."""
    return M2DriveInfo(
        form_factor=form_factor,
        keying=keying,
        lanes=lanes,
        link_speed=link_speed,
        transport=transport,
    )


def _selftest() -> bool:
    """Run a basic self-test for this module."""
    assert form_factor_from_dims(22, 80) == M2FormFactor.M2_2280
    assert form_factor_from_dims(22, 30) == M2FormFactor.M2_2230
    assert form_factor_from_dims(22, 110) == M2FormFactor.M2_22110
    assert form_factor_from_dims(22, 99) is None
    assert M2FormFactor.M2_2280.dims == (22, 80)
    assert M2FormFactor.M2_2280.name_mm == "2280"

    assert keying_supports_nvme(M2Keying.KEY_M) is True
    assert keying_supports_nvme(M2Keying.KEY_B) is False
    assert keying_supports_nvme(M2Keying.KEY_BM) is False

    assert lanes_from_link_width("x4") == 4
    assert lanes_from_link_width("x1") == 1
    assert lanes_from_link_width(2) == 2
    assert lanes_from_link_width("x0") is None
    assert lanes_from_link_width("unknown") is None

    drive = build_m2_drive(
        form_factor=M2FormFactor.M2_2280,
        keying=M2Keying.KEY_M,
        lanes=4,
        link_speed="8.0 GT/s",
    )
    assert drive.form_factor_name == "M.2 2280"
    assert drive.is_nvme_capable is True

    sata = build_m2_drive(keying=M2Keying.KEY_B)
    assert sata.is_nvme_capable is False

    speed, lanes = pcie_link_from_sysfs("0000:01:00.0")
    assert speed is None or isinstance(speed, str)
    assert lanes is None or isinstance(lanes, int)

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
