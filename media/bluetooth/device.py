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
UmerOS /media/bluetooth - Bluetooth Device Discovery (sysfs)
=============================================================

Discovers Bluetooth host controllers (HCI adapters) and known
remote devices through ``/sys/class/bluetooth`` (Linux sysfs).
Pure Python (standard library only) - no third-party packages.

The module works in two modes, mirroring the rest of the
``media`` package:

1. **Real-system mode** - reads sysfs attributes from
   ``/sys/class/bluetooth`` (adapters ``hciN``, remote devices
   ``<BD address>``).
2. **Simulated mode** - ``set_simulation()`` installs an
   in-memory device table so UmerOS can exercise the Bluetooth
   subsystem on any host (Windows/macOS CI, unit tests)
   without physical hardware.

Kernel naming conventions:

* ``hci0``              HCI controller (adapter)
* ``00:1A:7D:DA:71:13`` remote device (BD address)

sysfs attributes (``/sys/class/bluetooth/hciN``):

* ``address``       BD address (``00:1A:7D:DA:71:13``)
* ``name``          local controller name (e.g. ``BlueZ 5.54``)
* ``type``          ``BR/EDR`` or ``AMP``
* ``bus``           ``USB``, ``UART``, ``PCI`` or ``platform``
* ``features``      8 raw bytes (HCI LMP features)
* ``manufacturer``  HCI manufacturer id (decimal)
* ``rfkill``        0/1 (deprecated power state)
* ``ertm``          0/1 (enhanced retransmission mode)

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Media.Bluetooth.Device")

SYS_CLASS_BT = Path("/sys/class/bluetooth")

KIND_ADAPTER = "adapter"
KIND_DEVICE = "device"

_HCI_RE = re.compile(r"^hci[0-9]+$")
_BDADDR_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


def normalize_bdaddr(address: str) -> str:
    """Normalize a Bluetooth Device (BD) address.

    Accepts colon (``00:1A:7D:DA:71:13``) or dash
    (``00-1A-7D-DA-71-13``) separated forms and returns the
    canonical uppercase colon-separated form.

    Raises:
        ValueError: when *address* is not a valid 6-byte BD
            address.
    """
    raw = str(address).strip()
    if not _BDADDR_RE.match(raw):
        raise ValueError(f"invalid Bluetooth device address: {address!r}")
    return raw.upper().replace("-", ":")


def is_bdaddr(address: str) -> bool:
    """True when *address* is a valid BD address (any separator)."""
    try:
        normalize_bdaddr(address)
    except ValueError:
        return False
    return True


def bdaddr_to_dbus_suffix(address: str) -> str:
    """Return the D-Bus path suffix for a BD address.

    ``00:1A:7D:DA:71:13`` becomes ``dev_00_1A_7D_DA_71_13``
    (the form BlueZ uses in object paths such as
    ``/org/bluez/hci0/dev_00_1A_7D_DA_71_13``).
    """
    return "dev_" + normalize_bdaddr(address).replace(":", "_")


def classify_bt_name(name: str) -> Optional[str]:
    """Classify a kernel Bluetooth name.

    Returns :data:`KIND_ADAPTER` (``hciN``),
    :data:`KIND_DEVICE` (BD address) or ``None``.
    """
    raw = str(name).strip()
    if _HCI_RE.match(raw):
        return KIND_ADAPTER
    if _BDADDR_RE.match(raw):
        return KIND_DEVICE
    return None


@dataclass
class BluetoothAdapterInfo:
    """A single Bluetooth host controller (``/sys/class/bluetooth/hciN``)."""

    name: str
    address: Optional[str] = None
    local_name: Optional[str] = None
    controller_type: Optional[str] = None
    bus: Optional[str] = None
    features: Optional[str] = None
    manufacturer: Optional[int] = None
    rfkill: Optional[int] = None
    ertm: Optional[bool] = None

    @property
    def sysfs_path(self) -> str:
        return f"/sys/class/bluetooth/{self.name}"


@dataclass
class BluetoothDeviceInfo:
    """A known remote Bluetooth device (``/sys/class/bluetooth/<bdaddr>``)."""

    name: str
    address: Optional[str] = None
    local_name: Optional[str] = None
    controller_type: Optional[str] = None
    features: Optional[str] = None

    @property
    def sysfs_path(self) -> str:
        return f"/sys/class/bluetooth/{self.name}"


def _read_attr(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, IOError):
        return None


def _read_int(path: Path) -> Optional[int]:
    raw = _read_attr(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _read_str(path: Path) -> Optional[str]:
    raw = _read_attr(path)
    return raw if raw else None


def _read_features(path: Path) -> Optional[str]:
    """Read the 8-byte ``features`` attribute as a hex string."""
    try:
        raw = path.read_bytes()
    except (OSError, IOError):
        return None
    return raw.hex() if raw else None


def _read_bool(path: Path) -> Optional[bool]:
    raw = _read_attr(path)
    if raw is None:
        return None
    return raw in ("1", "true", "yes")


def read_adapter_info(
    name: str, root: Path = SYS_CLASS_BT
) -> Optional[BluetoothAdapterInfo]:
    """Read sysfs attributes for adapter *name* (e.g. ``hci0``)."""
    base = Path(root) / name
    if not base.exists():
        return None
    info = BluetoothAdapterInfo(name=name)
    info.address = _read_str(base / "address")
    info.local_name = _read_str(base / "name")
    info.controller_type = _read_str(base / "type")
    info.bus = _read_str(base / "bus")
    info.features = _read_features(base / "features")
    info.manufacturer = _read_int(base / "manufacturer")
    info.rfkill = _read_int(base / "rfkill")
    info.ertm = _read_bool(base / "ertm")
    return info


def read_device_info(
    name: str, root: Path = SYS_CLASS_BT
) -> Optional[BluetoothDeviceInfo]:
    """Read sysfs attributes for remote device *name* (BD address)."""
    base = Path(root) / name
    if not base.exists():
        return None
    info = BluetoothDeviceInfo(name=name)
    info.address = _read_str(base / "address")
    info.local_name = _read_str(base / "name")
    info.controller_type = _read_str(base / "type")
    info.features = _read_features(base / "features")
    return info


_SIM_DEVICES: Optional[Dict[str, Dict[str, str]]] = None


def set_simulation(devices: Optional[Dict[str, Dict[str, str]]]) -> None:
    """Install an in-memory device table for simulated discovery.

    *devices* maps sysfs entry names (``hci0``, BD addresses) to a
    dict of sysfs attribute names to string values, e.g.::

        set_simulation({"hci0": {"address": "00:1A:7D:DA:71:13", ...}})

    Pass ``None`` (or use :func:`clear_simulation`) to return to
    real sysfs discovery.
    """
    global _SIM_DEVICES
    _SIM_DEVICES = devices
    if devices:
        log.info(
            "Bluetooth discovery simulation active with %d device(s)",
            len(devices),
        )
    else:
        log.info("Bluetooth discovery simulation cleared")


def get_simulation() -> Optional[Dict[str, Dict[str, str]]]:
    """Return the active simulation table, or ``None``."""
    return _SIM_DEVICES


def clear_simulation() -> None:
    """Clear the simulation table (back to real sysfs)."""
    set_simulation(None)


def _sim_read(name: str, attr: str) -> Optional[str]:
    if _SIM_DEVICES is None:
        return None
    raw = _SIM_DEVICES.get(name, {}).get(attr)
    return raw if raw not in (None, "") else None


def _sim_read_int(name: str, attr: str) -> Optional[int]:
    raw = _sim_read(name, attr)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _sim_read_bool(name: str, attr: str) -> Optional[bool]:
    raw = _sim_read(name, attr)
    if raw is None:
        return None
    return raw in ("1", "true", "yes")


def _read_adapter_sim(name: str) -> Optional[BluetoothAdapterInfo]:
    if _SIM_DEVICES is None or name not in _SIM_DEVICES:
        return None
    if classify_bt_name(name) != KIND_ADAPTER:
        return None
    info = BluetoothAdapterInfo(name=name)
    info.address = _sim_read(name, "address")
    info.local_name = _sim_read(name, "name")
    info.controller_type = _sim_read(name, "type")
    info.bus = _sim_read(name, "bus")
    info.features = _sim_read(name, "features")
    info.manufacturer = _sim_read_int(name, "manufacturer")
    info.rfkill = _sim_read_int(name, "rfkill")
    info.ertm = _sim_read_bool(name, "ertm")
    return info


def _read_device_sim(name: str) -> Optional[BluetoothDeviceInfo]:
    if _SIM_DEVICES is None or name not in _SIM_DEVICES:
        return None
    if classify_bt_name(name) != KIND_DEVICE:
        return None
    info = BluetoothDeviceInfo(name=name)
    info.address = _sim_read(name, "address")
    info.local_name = _sim_read(name, "name")
    info.controller_type = _sim_read(name, "type")
    info.features = _sim_read(name, "features")
    return info


def discover_adapters(
    root: Path = SYS_CLASS_BT,
) -> List[BluetoothAdapterInfo]:
    """Discover all Bluetooth host controllers (``hciN``).

    Returns a list of :class:`BluetoothAdapterInfo` sorted by name.
    Empty when the host has no Bluetooth controllers (or on
    non-Linux hosts without simulation).
    """
    if _SIM_DEVICES is not None:
        return sorted(
            (
                info
                for info in (
                    _read_adapter_sim(n) for n in _SIM_DEVICES
                )
                if info is not None
            ),
            key=lambda adapter: adapter.name,
        )
    if not root.exists():
        log.debug("no Bluetooth sysfs at %s", root)
        return []
    adapters: List[BluetoothAdapterInfo] = []
    for entry in sorted(os.listdir(root)):
        if classify_bt_name(entry) == KIND_ADAPTER:
            info = read_adapter_info(entry, root)
            if info is not None:
                adapters.append(info)
    return adapters


def discover_devices(
    root: Path = SYS_CLASS_BT,
) -> List[BluetoothDeviceInfo]:
    """Discover known remote devices (BD address entries)."""
    if _SIM_DEVICES is not None:
        return sorted(
            (
                info
                for info in (
                    _read_device_sim(n) for n in _SIM_DEVICES
                )
                if info is not None
            ),
            key=lambda device: device.name,
        )
    if not root.exists():
        return []
    devices: List[BluetoothDeviceInfo] = []
    for entry in sorted(os.listdir(root)):
        if classify_bt_name(entry) == KIND_DEVICE:
            info = read_device_info(entry, root)
            if info is not None:
                devices.append(info)
    return devices


def discover_all(
    root: Path = SYS_CLASS_BT,
) -> Tuple[List[BluetoothAdapterInfo], List[BluetoothDeviceInfo]]:
    """Discover adapters and remote devices in one call."""
    return discover_adapters(root), discover_devices(root)


def available() -> bool:
    """True when Bluetooth discovery can run (sysfs present or simulation active)."""
    return _SIM_DEVICES is not None or SYS_CLASS_BT.exists()


def _selftest() -> bool:
    """Run a basic self-test for this module (simulation based)."""
    assert SYS_CLASS_BT.name == "bluetooth"

    sim = {
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
            "name": "Second adapter",
            "type": "AMP",
            "bus": "UART",
            "manufacturer": "10",
            "rfkill": "1",
        },
        "00:11:22:33:44:55": {
            "address": "00:11:22:33:44:55",
            "name": "MyPhone",
            "features": "0000000000000000",
        },
    }
    set_simulation(sim)
    try:
        adapters = discover_adapters()
        assert len(adapters) == 2, f"expected 2 adapters, got {len(adapters)}"
        assert [a.name for a in adapters] == ["hci0", "hci1"]
        hci0 = adapters[0]
        assert hci0.address == "00:1A:7D:DA:71:13"
        assert hci0.local_name == "BlueZ 5.54"
        assert hci0.controller_type == "BR/EDR"
        assert hci0.bus == "USB"
        assert hci0.features == "fffef00000000000"
        assert hci0.manufacturer == 15
        assert hci0.rfkill == 0
        assert hci0.ertm is True
        assert hci0.sysfs_path == "/sys/class/bluetooth/hci0"
        assert adapters[1].ertm is None

        devs = discover_devices()
        assert len(devs) == 1, f"expected 1 device, got {len(devs)}"
        dev = devs[0]
        assert dev.name == "00:11:22:33:44:55"
        assert dev.address == "00:11:22:33:44:55"
        assert dev.local_name == "MyPhone"

        adapters2, devs2 = discover_all()
        assert adapters2 == adapters
        assert devs2 == devs

        assert normalize_bdaddr("00-1a-7d-da-71-13") == "00:1A:7D:DA:71:13"
        assert is_bdaddr("00:11:22:33:44:55") is True
        assert is_bdaddr("00:11:22:33:44") is False
        assert is_bdaddr("hci0") is False
        try:
            normalize_bdaddr("not-an-addr")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid address must raise ValueError")
        assert bdaddr_to_dbus_suffix("00:1a:7d:da:71:13") == (
            "dev_00_1A_7D_DA_71_13"
        )

        assert classify_bt_name("hci0") == KIND_ADAPTER
        assert classify_bt_name("hci12") == KIND_ADAPTER
        assert classify_bt_name("00:11:22:33:44:55") == KIND_DEVICE
        assert classify_bt_name("sda") is None

        assert available() is True
        assert get_simulation() is sim
    finally:
        clear_simulation()
    assert get_simulation() is None
    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
