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
UmerOS /media/bluetooth - rfkill State
===========================================

Reads the Linux ``rfkill`` subsystem state for Bluetooth
(``/sys/class/rfkill``).  Each ``rfkillN`` entry exposes:

* ``name``   - the device the switch controls (e.g. ``hci0``)
* ``type``   - switch type (``bluetooth``, ``wlan``, ...)
* ``state``  - deprecated aggregate state (0 = unblocked)
* ``soft``   - 1 when software-blocked (user / driver)
* ``hard``   - 1 when hardware-blocked (physical switch)

The deprecated ``state`` attribute is still read for
completeness; :attr:`RfkillEntry.blocked` is the
authoritative value (``soft or hard``).

Pure Python (standard library only), with the same
real-sysfs / simulation split used across ``media``.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Media.Bluetooth.Rfkill")

SYS_CLASS_RFKILL = Path("/sys/class/rfkill")

TYPE_BLUETOOTH = "bluetooth"


@dataclass
class RfkillEntry:
    """A single ``/sys/class/rfkill/rfkillN`` switch."""

    name: str
    device_name: Optional[str] = None
    type: Optional[str] = None
    soft: Optional[bool] = None
    hard: Optional[bool] = None
    state: Optional[int] = None

    @property
    def is_bluetooth(self) -> bool:
        """True when this switch controls a Bluetooth device."""
        return self.type == TYPE_BLUETOOTH

    @property
    def blocked(self) -> bool:
        """True when software- or hardware-blocked."""
        return bool(self.soft or self.hard)

    @property
    def sysfs_path(self) -> str:
        return f"/sys/class/rfkill/{self.name}"


def _read_attr(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, IOError):
        return None


def _read_bool(path: Path) -> Optional[bool]:
    raw = _read_attr(path)
    if raw is None:
        return None
    return raw in ("1", "true", "yes")


def _read_int(path: Path) -> Optional[int]:
    raw = _read_attr(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def read_rfkill_entry(
    name: str, root: Path = SYS_CLASS_RFKILL
) -> Optional[RfkillEntry]:
    """Read sysfs attributes for rfkill switch *name* (``rfkillN``)."""
    base = Path(root) / name
    if not base.exists():
        return None
    entry = RfkillEntry(name=name)
    entry.device_name = _read_attr(base / "name") or None
    entry.type = _read_attr(base / "type") or None
    entry.soft = _read_bool(base / "soft")
    entry.hard = _read_bool(base / "hard")
    entry.state = _read_int(base / "state")
    return entry


_SIM_RFKILL: Optional[Dict[str, Dict[str, str]]] = None


def set_simulation(
    entries: Optional[Dict[str, Dict[str, str]]],
) -> None:
    """Install an in-memory rfkill table for simulated reads.

    *entries* maps rfkill switch names (``rfkillN``) to a
    dict of sysfs attribute names to string values, e.g.::

        set_simulation({"rfkill0": {"type": "bluetooth", "soft": "1"}})

    Pass ``None`` (or use :func:`clear_simulation`) to
    return to real sysfs reads.
    """
    global _SIM_RFKILL
    _SIM_RFKILL = entries
    if entries:
        log.info(
            "rfkill simulation active with %d switch(es)", len(entries)
        )
    else:
        log.info("rfkill simulation cleared")


def get_simulation() -> Optional[Dict[str, Dict[str, str]]]:
    """Return the active rfkill simulation table, or ``None``."""
    return _SIM_RFKILL


def clear_simulation() -> None:
    """Clear the simulation table (back to real sysfs)."""
    set_simulation(None)


def _sim_read(name: str, attr: str) -> Optional[str]:
    if _SIM_RFKILL is None:
        return None
    raw = _SIM_RFKILL.get(name, {}).get(attr)
    return raw if raw not in (None, "") else None


def _sim_bool(name: str, attr: str) -> Optional[bool]:
    raw = _sim_read(name, attr)
    if raw is None:
        return None
    return raw in ("1", "true", "yes")


def _sim_int(name: str, attr: str) -> Optional[int]:
    raw = _sim_read(name, attr)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _read_entry_sim(name: str) -> Optional[RfkillEntry]:
    if _SIM_RFKILL is None or name not in _SIM_RFKILL:
        return None
    entry = RfkillEntry(name=name)
    entry.device_name = _sim_read(name, "name")
    entry.type = _sim_read(name, "type")
    entry.soft = _sim_bool(name, "soft")
    entry.hard = _sim_bool(name, "hard")
    entry.state = _sim_int(name, "state")
    return entry


def discover_rfkill(
    root: Path = SYS_CLASS_RFKILL,
) -> List[RfkillEntry]:
    """Discover all rfkill switches.

    Returns a list of :class:`RfkillEntry` sorted by name.
    """
    if _SIM_RFKILL is not None:
        return sorted(
            (
                entry
                for entry in (
                    _read_entry_sim(n) for n in _SIM_RFKILL
                )
                if entry is not None
            ),
            key=lambda e: e.name,
        )
    if not root.exists():
        log.debug("no rfkill sysfs at %s", root)
        return []
    entries: List[RfkillEntry] = []
    for entry in sorted(os.listdir(root)):
        if not entry.startswith("rfkill"):
            continue
        info = read_rfkill_entry(entry, root)
        if info is not None:
            entries.append(info)
    return entries


def discover_bluetooth_rfkill(
    root: Path = SYS_CLASS_RFKILL,
) -> List[RfkillEntry]:
    """Discover only the Bluetooth rfkill switches."""
    return [e for e in discover_rfkill(root) if e.is_bluetooth]


def bluetooth_rfkill_summary(
    root: Path = SYS_CLASS_RFKILL,
) -> Dict[str, object]:
    """Summarise the Bluetooth rfkill state of the host.

    Returns a dict with:

    * ``count``       - number of Bluetooth switches
    * ``any_soft``    - True when any is software-blocked
    * ``any_hard``    - True when any is hardware-blocked
    * ``blocked``     - True when any switch is blocked
    * ``entries``     - the :class:`RfkillEntry` list
    """
    entries = discover_bluetooth_rfkill(root)
    return {
        "count": len(entries),
        "any_soft": any(e.soft for e in entries),
        "any_hard": any(e.hard for e in entries),
        "blocked": any(e.blocked for e in entries),
        "entries": entries,
    }


def available() -> bool:
    """True when rfkill reads can run (sysfs present or simulation active)."""
    return _SIM_RFKILL is not None or SYS_CLASS_RFKILL.exists()


def _selftest() -> bool:
    """Run a basic self-test for this module (simulation based)."""
    assert SYS_CLASS_RFKILL.name == "rfkill"

    sim = {
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
            "state": "0",
            "soft": "0",
            "hard": "0",
        },
        "rfkill2": {
            "name": "phy0",
            "type": "wlan",
            "soft": "0",
            "hard": "1",
        },
    }
    set_simulation(sim)
    try:
        all_switches = discover_rfkill()
        assert len(all_switches) == 3

        bt = discover_bluetooth_rfkill()
        assert len(bt) == 2
        assert [e.name for e in bt] == ["rfkill0", "rfkill1"]
        assert bt[0].device_name == "hci0"
        assert bt[0].is_bluetooth is True
        assert bt[0].blocked is True
        assert bt[0].soft is True
        assert bt[0].hard is False
        assert bt[0].state == 1
        assert bt[0].sysfs_path == "/sys/class/rfkill/rfkill0"
        assert bt[1].blocked is False
        assert bt[1].is_bluetooth is True
        assert all_switches[2].is_bluetooth is False
        assert all_switches[2].blocked is True

        summary = bluetooth_rfkill_summary()
        assert summary["count"] == 2
        assert summary["any_soft"] is True
        assert summary["any_hard"] is False
        assert summary["blocked"] is True
        assert summary["entries"] == bt

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
