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
UmerOS /media/bluetooth - BlueZ D-Bus Model
=================================================

Read-only model of the BlueZ daemon's D-Bus API
(``org.bluez``).  The BlueZ API is D-Bus based; this
module reads properties without any third-party D-Bus
binding by shelling out to the standard system tools
``busctl`` (systemd) or ``gdbus`` (GLib), whichever
is available.

Key objects:

* ``/org/bluez/hciN``
  ``org.bluez.Adapter1`` - host controller
  (Address, Name, Alias, Powered, Discoverable,
  Pairable, Discovering, UUIDs, Modalias, ...)
* ``/org/bluez/hciN/dev_XX_...``
  ``org.bluez.Device1`` - remote device
  (Address, Name, Paired, Trusted, Connected,
  UUIDs, Adapter, ...)

Also parses BlueZ's persistent storage at
``/var/lib/bluetooth/<adapter>/<device>/info``
(paired-device keys, INI format).

State-changing operations (pair, trust, connect, ...)
live in :mod:`media.bluetooth.cli` behind the
capability gate.

Pure Python (standard library only).

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import configparser
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Media.Bluetooth.BlueZ")

BLUEZ_SERVICE = "org.bluez"
BLUEZ_PATH = "/org/bluez"
ADAPTER_IFACE = "org.bluez.Adapter1"
DEVICE_IFACE = "org.bluez.Device1"
BLUEZ_STATE_DIR = Path("/var/lib/bluetooth")

DEFAULT_TIMEOUT = 10.0

BUSCTL_BIN = "busctl"
GDBUS_BIN = "gdbus"


class BluezError(RuntimeError):
    """Raised when busctl/gdbus is missing, times out or fails."""


@dataclass
class Adapter1:
    """BlueZ ``org.bluez.Adapter1`` (a host controller)."""

    path: Optional[str] = None
    address: Optional[str] = None
    address_type: Optional[str] = None
    name: Optional[str] = None
    alias: Optional[str] = None
    class_of_device: Optional[int] = None
    powered: Optional[bool] = None
    discoverable: Optional[bool] = None
    discoverable_timeout: Optional[int] = None
    pairable: Optional[bool] = None
    pairable_timeout: Optional[int] = None
    discovering: Optional[bool] = None
    uuids: List[str] = field(default_factory=list)
    modalias: Optional[str] = None

    @classmethod
    def from_properties(
        cls, props: Dict[str, Any], path: Optional[str] = None
    ) -> "Adapter1":
        """Build an :class:`Adapter1` from D-Bus properties."""
        return cls(
            path=path,
            address=props.get("Address"),
            address_type=props.get("AddressType"),
            name=props.get("Name"),
            alias=props.get("Alias"),
            class_of_device=props.get("Class"),
            powered=props.get("Powered"),
            discoverable=props.get("Discoverable"),
            discoverable_timeout=props.get("DiscoverableTimeout"),
            pairable=props.get("Pairable"),
            pairable_timeout=props.get("PairableTimeout"),
            discovering=props.get("Discovering"),
            uuids=list(props.get("UUIDs") or []),
            modalias=props.get("Modalias"),
        )


@dataclass
class Device1:
    """BlueZ ``org.bluez.Device1`` (a remote device)."""

    path: Optional[str] = None
    address: Optional[str] = None
    address_type: Optional[str] = None
    name: Optional[str] = None
    alias: Optional[str] = None
    class_of_device: Optional[int] = None
    appearance: Optional[int] = None
    icon: Optional[str] = None
    paired: Optional[bool] = None
    trusted: Optional[bool] = None
    blocked: Optional[bool] = None
    connected: Optional[bool] = None
    uuids: List[str] = field(default_factory=list)
    modalias: Optional[str] = None
    adapter: Optional[str] = None

    @classmethod
    def from_properties(
        cls, props: Dict[str, Any], path: Optional[str] = None
    ) -> "Device1":
        """Build a :class:`Device1` from D-Bus properties."""
        return cls(
            path=path,
            address=props.get("Address"),
            address_type=props.get("AddressType"),
            name=props.get("Name"),
            alias=props.get("Alias"),
            class_of_device=props.get("Class"),
            appearance=props.get("Appearance"),
            icon=props.get("Icon"),
            paired=props.get("Paired"),
            trusted=props.get("Trusted"),
            blocked=props.get("Blocked"),
            connected=props.get("Connected"),
            uuids=list(props.get("UUIDs") or []),
            modalias=props.get("Modalias"),
            adapter=props.get("Adapter"),
        )


def available_tool(tool: Optional[str] = None) -> Optional[str]:
    """Return the D-Bus CLI tool to use (``busctl`` or ``gdbus``)."""
    if tool is None:
        for candidate in (BUSCTL_BIN, GDBUS_BIN):
            if shutil.which(candidate) is not None:
                return candidate
        return None
    if tool not in (BUSCTL_BIN, GDBUS_BIN):
        raise ValueError("tool must be 'busctl' or 'gdbus'")
    return tool if shutil.which(tool) is not None else None


def _run_tool(args: List[str], timeout: float = DEFAULT_TIMEOUT) -> str:
    """Run a D-Bus CLI tool and return stdout."""
    tool = args[0]
    if shutil.which(tool) is None:
        raise BluezError(f"{tool} is not installed or not on PATH")
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BluezError(
            f"{tool} timed out after {timeout}s: {' '.join(args)}"
        ) from exc
    except OSError as exc:
        raise BluezError(f"failed to execute {tool}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise BluezError(
            f"{tool} failed (exit {result.returncode}): {detail}"
        )
    return result.stdout


def _parse_busctl_value(raw: str) -> Any:
    """Parse a single ``busctl get-property`` value.

    Handles the common wire formats: ``b true``,
    ``s "text"``, ``u 123``, ``x -5``, ``ay 00 11``,
    ``as [a b]``.  Structured types (``a{sv}``) are
    returned as the raw string.
    """
    text = raw.strip()
    parts = text.split(None, 1)
    if len(parts) != 2:
        return text
    kind, value = parts
    if kind == "b":
        return value.strip() == "true"
    if kind == "s":
        stripped = value.strip()
        if len(stripped) >= 2 and stripped.startswith('"'):
            return stripped[1:-1]
        return stripped
    if kind in ("u", "x", "i", "n", "q", "t"):
        try:
            return int(value.strip())
        except ValueError:
            return value.strip()
    if kind == "ay":
        hexdigits = value.split()
        return bytes(int(h, 16) for h in hexdigits if h)
    if kind.startswith("as") or kind.startswith("a("):
        inner = value.strip()
        if inner.startswith("[") and inner.endswith("]"):
            inner = inner[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"') for item in inner.split()]
    return text


def _parse_gdbus_value(raw: str) -> Any:
    """Parse a single ``gdbus call`` return value ``(value,)``."""
    text = raw.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip().rstrip(",").strip()
    if text == "true":
        return True
    if text == "false":
        return False
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        return text


def read_property(
    service: str,
    object_path: str,
    interface: str,
    prop: str,
    tool: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """Read one D-Bus property via busctl or gdbus."""
    selected = available_tool(tool)
    if selected is None:
        raise BluezError(
            "no D-Bus CLI tool available (busctl/gdbus)"
        )
    if selected == BUSCTL_BIN:
        out = _run_tool(
            [
                BUSCTL_BIN,
                "get-property",
                service,
                object_path,
                interface,
                prop,
            ],
            timeout=timeout,
        )
        return _parse_busctl_value(out)
    out = _run_tool(
        [
            GDBUS_BIN,
            "call",
            "--system",
            "--dest",
            service,
            "--object-path",
            object_path,
            "--method",
            "org.freedesktop.DBus.Properties.Get",
            interface,
            prop,
        ],
        timeout=timeout,
    )
    return _parse_gdbus_value(out)


def read_properties(
    service: str,
    object_path: str,
    interface: str,
    props: List[str],
    tool: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Read several D-Bus properties of one object."""
    return {
        prop: read_property(
            service, object_path, interface, prop,
            tool=tool, timeout=timeout,
        )
        for prop in props
    }


def list_object_paths(
    service: str,
    tool: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> List[str]:
    """List the D-Bus object paths exposed by *service*."""
    selected = available_tool(tool)
    if selected is None:
        raise BluezError(
            "no D-Bus CLI tool available (busctl/gdbus)"
        )
    if selected == BUSCTL_BIN:
        out = _run_tool(
            [BUSCTL_BIN, "tree", service], timeout=timeout
        )
        paths: List[str] = []
        for line in out.splitlines():
            stripped = line.strip()
            if stripped.startswith("/"):
                paths.append(stripped)
        return paths
    out = _run_tool(
        [
            GDBUS_BIN,
            "call",
            "--system",
            "--dest",
            service,
            "--object-path",
            "/",
            "--method",
            "org.freedesktop.DBus.ObjectManager.GetManagedObjects",
        ],
        timeout=timeout,
    )
    # gdbus returns a huge a{oa{sa{sv}}} blob; object
    # paths are the top-level keys, which a simple scan
    # can recover from the flattened text.
    paths = []
    for token in out.replace("{", " ").replace("}", " ").split():
        if token.startswith("/"):
            paths.append(token.strip("'\""))
    return paths


def discover_adapters_dbus(
    tool: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> List[Adapter1]:
    """Discover BlueZ host controllers over D-Bus."""
    paths = list_object_paths(BLUEZ_SERVICE, tool=tool, timeout=timeout)
    adapters: List[Adapter1] = []
    for path in paths:
        parts = path.strip("/").split("/")
        if len(parts) != 2 or not parts[1].startswith("hci"):
            continue
        props = read_properties(
            BLUEZ_SERVICE, path, ADAPTER_IFACE,
            [
                "Address", "AddressType", "Name", "Alias", "Class",
                "Powered", "Discoverable", "DiscoverableTimeout",
                "Pairable", "PairableTimeout", "Discovering",
                "UUIDs", "Modalias",
            ],
            tool=tool,
            timeout=timeout,
        )
        adapters.append(Adapter1.from_properties(props, path=path))
    return adapters


def discover_devices_dbus(
    tool: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> List[Device1]:
    """Discover BlueZ remote devices over D-Bus."""
    paths = list_object_paths(BLUEZ_SERVICE, tool=tool, timeout=timeout)
    devices: List[Device1] = []
    for path in paths:
        parts = path.strip("/").split("/")
        if len(parts) != 3 or not parts[2].startswith("dev_"):
            continue
        props = read_properties(
            BLUEZ_SERVICE, path, DEVICE_IFACE,
            [
                "Address", "AddressType", "Name", "Alias", "Class",
                "Appearance", "Icon", "Paired", "Trusted", "Blocked",
                "Connected", "UUIDs", "Modalias", "Adapter",
            ],
            tool=tool,
            timeout=timeout,
        )
        devices.append(Device1.from_properties(props, path=path))
    return devices


def paired_devices_dir(adapter_address: str) -> Path:
    """BlueZ persistent-storage directory for an adapter."""
    from .device import normalize_bdaddr

    return BLUEZ_STATE_DIR / normalize_bdaddr(adapter_address)


def parse_device_info_file(path: Path) -> Dict[str, Dict[str, str]]:
    """Parse a BlueZ ``info`` file (INI, sections of hex keys).

    Returns a dict of section name -> key -> value, e.g.::

        {"General": {"Name": "MyPhone", "Class": "0x200404"}}
    """
    parser = configparser.ConfigParser(
        interpolation=None, strict=False
    )
    # BlueZ info files use mixed-case keys (Name, Class,
    # Key, ...); ConfigParser lowercases by default.
    parser.optionxform = str  # type: ignore[assignment]
    parser.read(path, encoding="utf-8")
    return {section: dict(parser.items(section)) for section in parser.sections()}


def discover_paired_devices(
    adapter_address: str,
) -> List[Tuple[str, Dict[str, Dict[str, str]]]]:
    """List devices paired with *adapter_address*.

    Returns ``(device_address, sections)`` tuples parsed
    from the ``info`` files under the adapter's BlueZ
    storage directory.
    """
    from .device import (
        KIND_DEVICE,
        classify_bt_name,
        normalize_bdaddr,
    )

    base = paired_devices_dir(adapter_address)
    if not base.exists():
        log.debug("no BlueZ storage at %s", base)
        return []
    results: List[Tuple[str, Dict[str, Dict[str, str]]]] = []
    for entry in sorted(os.listdir(base)):
        if classify_bt_name(entry) != KIND_DEVICE:
            continue
        info_file = base / entry / "info"
        if not info_file.exists():
            continue
        results.append(
            (normalize_bdaddr(entry), parse_device_info_file(info_file))
        )
    return results


def _selftest() -> bool:
    """Run a basic self-test for this module (pure parsing)."""
    assert BLUEZ_SERVICE == "org.bluez"
    assert ADAPTER_IFACE == "org.bluez.Adapter1"
    assert DEVICE_IFACE == "org.bluez.Device1"

    # busctl value parsing
    assert _parse_busctl_value("b true") is True
    assert _parse_busctl_value("b false") is False
    assert _parse_busctl_value('s "MyHost"') == "MyHost"
    assert _parse_busctl_value("u 123") == 123
    assert _parse_busctl_value("x -5") == -5
    assert _parse_busctl_value("ay 00 11 ff") == b"\x00\x11\xff"
    assert _parse_busctl_value("as [a b c]") == ["a", "b", "c"]
    assert _parse_busctl_value("as []") == []
    raw = _parse_busctl_value('a{sv} {"Powered" b true}')
    assert isinstance(raw, str)

    # gdbus value parsing
    assert _parse_gdbus_value("(true,)") is True
    assert _parse_gdbus_value("(false,)") is False
    assert _parse_gdbus_value("('MyHost',)") == "MyHost"
    assert _parse_gdbus_value("(123,)") == 123

    # dataclass construction
    adapter = Adapter1.from_properties({
        "Address": "00:1A:7D:DA:71:13",
        "Name": "MyHost",
        "Class": 0x10010C,
        "Powered": True,
        "Discoverable": False,
        "UUIDs": ["0000110a-0000-1000-8000-00805f9b34fb"],
        "Modalias": "usb:v1D6Bp0246d0539",
    }, path="/org/bluez/hci0")
    assert adapter.address == "00:1A:7D:DA:71:13"
    assert adapter.name == "MyHost"
    assert adapter.class_of_device == 0x10010C
    assert adapter.powered is True
    assert adapter.discoverable is False
    assert adapter.uuids == ["0000110a-0000-1000-8000-00805f9b34fb"]
    assert adapter.modalias == "usb:v1D6Bp0246d0539"

    device = Device1.from_properties({
        "Address": "00:11:22:33:44:55",
        "Name": "MyPhone",
        "Paired": True,
        "Trusted": True,
        "Connected": False,
        "Adapter": "/org/bluez/hci0",
    })
    assert device.address == "00:11:22:33:44:55"
    assert device.paired is True
    assert device.connected is False
    assert device.adapter == "/org/bluez/hci0"

    # object-path filtering
    try:
        available_tool("bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid tool must raise ValueError")

    # paired-device info file parsing
    import tempfile

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
        sections = parse_device_info_file(info)
        assert sections["General"]["Name"] == "MyPhone"
        assert sections["General"]["Class"] == "0x200404"
        assert (
            sections["IdentityResolvingKey"]["Key"]
            == "00112233445566778899aabbccddeeff"
        )
        assert paired_devices_dir("00-1a-7d-da-71-13") == Path(
            "/var/lib/bluetooth/00:1A:7D:DA:71:13"
        )

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
