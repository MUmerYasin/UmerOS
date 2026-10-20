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
UmerOS /media/usb - USB Device Discovery (sysfs)
==================================================

Discovers USB devices through ``/sys/bus/usb/devices``
(Linux sysfs) and parses ``lsusb`` output.  Pure Python
(standard library only) - no third-party packages.

The module works in two modes, mirroring the rest of the
``media`` package:

1. **Real-system mode** - reads sysfs attributes from
   ``/sys/bus/usb/devices`` (root hubs ``usbN``, devices
   on the topology chain ``N-M[.x]*`` and their
   interfaces ``N-M:y.z``).
2. **Simulated mode** - ``set_simulation()`` installs an
   in-memory device table so UmerOS can exercise the USB
   subsystem on any host (Windows/macOS CI, unit tests)
   without physical hardware.

Entry naming follows the kernel convention:

* ``usb1``        root hub (the host controller itself)
* ``1-2``         device on bus 1, hub port chain 2
* ``1-2.4``       device one level deeper (port 4 of the
                  device at ``1-2``)
* ``1-2:1.0``     interface 0, alternate setting 0 of
                  the device at ``1-2``

sysfs attribute reference (kernel ``drivers/usb/core/
sysfs.c`` + ``Documentation/ABI/stable/sysfs-bus-usb``):

* ``busnum``            bus number
* ``devnum``            device number on the bus
* ``devpath``           topology path (e.g. ``1/2``)
* ``idVendor``          vendor ID (4 hex digits)
* ``idProduct``         product ID (4 hex digits)
* ``bcdDevice``         device release number (hex)
* ``bDeviceClass``      device class code (hex)
* ``bDeviceSubClass``   device subclass (hex)
* ``bDeviceProtocol``   device protocol (hex)
* ``bNumConfigurations``
* ``bMaxPacketSize0``   endpoint 0 max packet size
* ``speed``             link speed in Mbps (``1.5``,
                        ``12``, ``480``, ``5000``,
                        ``10000``)
* ``version``           USB specification version
* ``manufacturer``, ``product``, ``serial``
                        string descriptors (only present
                        when the device provides them)
* ``maxchild``          number of downstream ports
                        (hubs only)
* ``authorized``        1/0 - (de)authorize the device
                        (writable, privileged)
* ``remove``            writing 1 triggers unplug
                        (writable, privileged)

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Media.USB.Device")

SYS_BUS_USB_DEVICES = Path("/sys/bus/usb/devices")

# Entry kinds within /sys/bus/usb/devices
KIND_ROOT_HUB = "root_hub"
KIND_DEVICE = "device"
KIND_INTERFACE = "interface"

# USB standard device class codes (USB 2.0 spec,
# Table 9-4 "Standard Class Codes").
CLASS_PER_INTERFACE = 0x00
CLASS_AUDIO = 0x01
CLASS_COMMUNICATIONS = 0x02
CLASS_HID = 0x03
CLASS_PHYSICAL = 0x05
CLASS_IMAGE = 0x06
CLASS_PRINTER = 0x07
CLASS_MASS_STORAGE = 0x08
CLASS_HUB = 0x09
CLASS_CDC_DATA = 0x0A
CLASS_SMART_CARD = 0x0B
CLASS_CONTENT_SECURITY = 0x0D
CLASS_VIDEO = 0x0E
CLASS_PERSONAL_HEALTHCARE = 0x0F
CLASS_AUDIO_VIDEO = 0x10
CLASS_BILLBOARD = 0x11
CLASS_TYPE_C_BRIDGE = 0x12
CLASS_WIRELESS_CONTROLLER = 0xE0
CLASS_MISC = 0xEF
CLASS_APPLICATION_SPECIFIC = 0xFE
CLASS_VENDOR_SPECIFIC = 0xFF

CLASS_NAMES: Dict[int, str] = {
    CLASS_PER_INTERFACE: "per-interface",
    CLASS_AUDIO: "audio",
    CLASS_COMMUNICATIONS: "communications",
    CLASS_HID: "hid",
    CLASS_PHYSICAL: "physical",
    CLASS_IMAGE: "image",
    CLASS_PRINTER: "printer",
    CLASS_MASS_STORAGE: "mass-storage",
    CLASS_HUB: "hub",
    CLASS_CDC_DATA: "cdc-data",
    CLASS_SMART_CARD: "smart-card",
    CLASS_CONTENT_SECURITY: "content-security",
    CLASS_VIDEO: "video",
    CLASS_PERSONAL_HEALTHCARE: "personal-healthcare",
    CLASS_AUDIO_VIDEO: "audio-video",
    CLASS_BILLBOARD: "billboard",
    CLASS_TYPE_C_BRIDGE: "type-c-bridge",
    CLASS_WIRELESS_CONTROLLER: "wireless-controller",
    CLASS_MISC: "misc",
    CLASS_APPLICATION_SPECIFIC: "application-specific",
    CLASS_VENDOR_SPECIFIC: "vendor-specific",
}

# Link speeds reported by the kernel (Mbps).
SPEED_LOW = "1.5"
SPEED_FULL = "12"
SPEED_HIGH = "480"
SPEED_SUPER = "5000"
SPEED_SUPER_PLUS = "10000"

SPEED_NAMES: Dict[str, str] = {
    SPEED_LOW: "low_speed",
    SPEED_FULL: "full_speed",
    SPEED_HIGH: "high_speed",
    SPEED_SUPER: "super_speed",
    SPEED_SUPER_PLUS: "super_speed_plus",
}

_ROOT_HUB_RE = re.compile(r"^usb[0-9]+$")
_DEVICE_RE = re.compile(r"^[0-9]+-[0-9]+(?:\.[0-9]+)*$")
_INTERFACE_RE = re.compile(
    r"^[0-9]+-[0-9]+(?:\.[0-9]+)*:[0-9]+\.[0-9]+$"
)

# "Bus 001 Device 007: ID 05e3:0610 Genesys Logic, Inc. 4-port hub"
_LSUSB_RE = re.compile(
    r"^Bus\s+(\d{3})\s+Device\s+(\d{3}):\s+"
    r"ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s*(.*)$"
)

# lsusb -t tree lines.  Root line:
# "/:  Bus 02.Port 1: Dev 1, Class=root_hub, Driver=uhci_hcd/2p, 12M"
# Child line (no "Bus" prefix - the bus is inherited
# from the enclosing root line):
# "    |__ Port 1: Dev 2, If 0, Class=Mass Storage, Driver=usb-storage, 480M"
_ROOT_TREE_RE = re.compile(
    r"Bus\s+(\d+)\.Port\s+(\d+):\s+Dev\s+(\d+)"
    r"(?:,\s*Class=([^,\n]*))?"
    r"(?:,\s*Driver=([^,\n]*))?"
    r"(?:,\s*(\d+)M)?"
)
_CHILD_TREE_RE = re.compile(
    r"Port\s+(\d+):\s+Dev\s+(\d+)"
    r"(?:,\s*If\s+(\d+))?"
    r"(?:,\s*Class=([^,\n]*))?"
    r"(?:,\s*Driver=([^,\n]*))?"
    r"(?:,\s*(\d+)M)?"
)

# "    bcdUSB               2.00"   (4 leading spaces in lsusb -v)
# "    idVendor           0x0781 SanDisk Corp."
_DESCRIPTOR_FIELD_RE = re.compile(
    r"^\s{4}(\w+)\s+(\S+)(?:\s+(.*))?$"
)

_DESCRIPTOR_FIELDS = (
    "bLength",
    "bDescriptorType",
    "bcdUSB",
    "bDeviceClass",
    "bDeviceSubClass",
    "bDeviceProtocol",
    "bMaxPacketSize0",
    "idVendor",
    "idProduct",
    "bcdDevice",
    "iManufacturer",
    "iProduct",
    "iSerial",
    "bNumConfigurations",
)


def classify_usb_name(name: str) -> Optional[str]:
    """Classify a kernel USB sysfs entry name.

    Returns ``"root_hub"``, ``"device"``, ``"interface"``
    - or ``None`` when *name* is not a USB sysfs name.
    """
    name = name.strip()
    if _INTERFACE_RE.match(name):
        return KIND_INTERFACE
    if _ROOT_HUB_RE.match(name):
        return KIND_ROOT_HUB
    if _DEVICE_RE.match(name):
        return KIND_DEVICE
    return None


def device_of_interface(interface_name: str) -> Optional[str]:
    """Return the device entry (``1-2``) owning an
    interface entry (``1-2:1.0``)."""
    if classify_usb_name(interface_name) != KIND_INTERFACE:
        return None
    return interface_name.split(":", 1)[0]


@dataclass
class USBDeviceInfo:
    """A single USB device (``/sys/bus/usb/devices/N-M``)."""

    name: str
    bus_num: Optional[int] = None
    dev_num: Optional[int] = None
    devpath: Optional[str] = None
    vid: Optional[str] = None
    pid: Optional[str] = None
    bcd_device: Optional[str] = None
    device_class: Optional[int] = None
    device_subclass: Optional[int] = None
    device_protocol: Optional[int] = None
    num_configs: Optional[int] = None
    max_packet_size0: Optional[int] = None
    speed: Optional[str] = None
    version: Optional[str] = None
    manufacturer: Optional[str] = None
    product: Optional[str] = None
    serial: Optional[str] = None
    max_child: Optional[int] = None
    num_interfaces: Optional[int] = None
    modalias: Optional[str] = None

    @property
    def vendor_id(self) -> Optional[int]:
        """Vendor ID as an integer (e.g. ``0x05e3`` -> 1507)."""
        if self.vid is None:
            return None
        try:
            return int(self.vid, 16)
        except ValueError:
            return None

    @property
    def product_id(self) -> Optional[int]:
        """Product ID as an integer."""
        if self.pid is None:
            return None
        try:
            return int(self.pid, 16)
        except ValueError:
            return None

    @property
    def speed_name(self) -> Optional[str]:
        """Symbolic link-speed name (``high_speed`` ...)."""
        if self.speed is None:
            return None
        return SPEED_NAMES.get(self.speed, self.speed)

    @property
    def device_class_name(self) -> Optional[str]:
        """Symbolic device-class name (``hub`` ...)."""
        if self.device_class is None:
            return None
        return CLASS_NAMES.get(self.device_class)

    @property
    def is_hub(self) -> bool:
        return self.device_class == CLASS_HUB

    @property
    def is_mass_storage(self) -> bool:
        """Device-level mass-storage class.  Most USB
        drives report class 0x00 with the mass-storage
        class on their *interface* instead - use
        :func:`is_mass_storage_device` for the full
        check."""
        return self.device_class == CLASS_MASS_STORAGE

    @property
    def device_path(self) -> str:
        return str(SYS_BUS_USB_DEVICES / self.name)


def _read_attr(entry: Path, attr: str) -> Optional[str]:
    """Read a single sysfs attribute, *None* on failure."""
    try:
        return (entry / attr).read_text(
            encoding="utf-8", errors="replace"
        ).strip()
    except (OSError, IOError):
        return None


def _read_attr_int(entry: Path, attr: str) -> Optional[int]:
    raw = _read_attr(entry, attr)
    if raw is None:
        return None
    try:
        return int(raw, 0) if raw.lower().startswith("0x") else int(raw)
    except ValueError:
        return None


def read_usb_device(
    name: str,
    root: Path = SYS_BUS_USB_DEVICES,
) -> Optional[USBDeviceInfo]:
    """Read one USB device entry from sysfs.

    Returns ``None`` when *name* is not a USB device
    entry or the sysfs tree is unavailable.
    """
    kind = classify_usb_name(name)
    if kind not in (KIND_ROOT_HUB, KIND_DEVICE):
        return None
    # Simulation mode
    if _SIM_DEVICES is not None:
        return _read_sim(name)
    entry = root / name
    if not entry.is_dir():
        return None
    info = USBDeviceInfo(name=name)
    info.bus_num = _read_attr_int(entry, "busnum")
    info.dev_num = _read_attr_int(entry, "devnum")
    info.devpath = _read_attr(entry, "devpath")
    raw_vid = _read_attr(entry, "idVendor")
    info.vid = raw_vid.lower() if raw_vid is not None else None
    raw_pid = _read_attr(entry, "idProduct")
    info.pid = raw_pid.lower() if raw_pid is not None else None
    info.bcd_device = _read_attr(entry, "bcdDevice")
    info.device_class = _read_attr_int(entry, "bDeviceClass")
    info.device_subclass = _read_attr_int(entry, "bDeviceSubClass")
    info.device_protocol = _read_attr_int(entry, "bDeviceProtocol")
    info.num_configs = _read_attr_int(entry, "bNumConfigurations")
    info.max_packet_size0 = _read_attr_int(entry, "bMaxPacketSize0")
    info.speed = _read_attr(entry, "speed")
    info.version = _read_attr(entry, "version")
    info.manufacturer = _read_attr(entry, "manufacturer")
    info.product = _read_attr(entry, "product")
    info.serial = _read_attr(entry, "serial")
    info.max_child = _read_attr_int(entry, "maxchild")
    info.num_interfaces = _read_attr_int(entry, "bNumInterfaces")
    info.modalias = _read_attr(entry, "modalias")
    return info


def interfaces_of(
    device_name: str,
    root: Path = SYS_BUS_USB_DEVICES,
) -> List[str]:
    """Return the interface entries (``N-M:y.z``) of the
    device *device_name* (``N-M``)."""
    if classify_usb_name(device_name) != KIND_DEVICE:
        return []
    # Simulation mode
    if _SIM_DEVICES is not None:
        prefix = device_name + ":"
        return sorted(
            name
            for name in _SIM_DEVICES
            if name.startswith(prefix)
            and classify_usb_name(name) == KIND_INTERFACE
        )
    if not (root / device_name).is_dir():
        return []
    prefix = device_name + ":"
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return []
    return [
        entry
        for entry in entries
        if entry.startswith(prefix)
        and classify_usb_name(entry) == KIND_INTERFACE
    ]


def interface_class(
    interface_name: str,
    root: Path = SYS_BUS_USB_DEVICES,
) -> Optional[int]:
    """Read ``bInterfaceClass`` of an interface entry."""
    if classify_usb_name(interface_name) != KIND_INTERFACE:
        return None
    # Simulation mode
    if _SIM_DEVICES is not None:
        raw = _SIM_DEVICES.get(interface_name, {}).get("bInterfaceClass")
        if raw is not None and raw != "":
            try:
                return int(raw, 0) if raw.lower().startswith("0x") else int(raw)
            except ValueError:
                return None
        return None
    return _read_attr_int(root / interface_name, "bInterfaceClass")


def is_mass_storage_device(
    device_name: str,
    root: Path = SYS_BUS_USB_DEVICES,
) -> bool:
    """True when *device_name* is a USB mass-storage
    device (class 0x08 at device level, or on any of
    its interfaces - the common layout for USB drives)."""
    info = read_usb_device(device_name, root)
    if info is not None and info.is_mass_storage:
        return True
    for iface in interfaces_of(device_name, root):
        if interface_class(iface, root) == CLASS_MASS_STORAGE:
            return True
    return False


def available() -> bool:
    """True when the Linux USB sysfs tree is present."""
    return SYS_BUS_USB_DEVICES.exists()


# ---------------------------------------------------------------------------
# lsusb output parsers
# ---------------------------------------------------------------------------

def parse_lsusb(text: str) -> List[Dict[str, str]]:
    """Parse plain ``lsusb`` output.

    Example line::

        Bus 001 Device 007: ID 05e3:0610 Genesys Logic, Inc. 4-port hub

    Returns a list of dicts with ``bus``, ``device``,
    ``vid``, ``pid`` and ``description`` keys.
    """
    devices: List[Dict[str, str]] = []
    for line in text.splitlines():
        match = _LSUSB_RE.match(line)
        if match is None:
            continue
        devices.append({
            "bus": match.group(1),
            "device": match.group(2),
            "vid": match.group(3).lower(),
            "pid": match.group(4).lower(),
            "description": match.group(5).strip(),
        })
    return devices


def parse_lsusb_verbose(text: str) -> List[Dict[str, str]]:
    """Parse ``lsusb -v`` output into one dict of
    descriptor fields per ``Device Descriptor:`` block.

    Field values are returned verbatim (hex fields keep
    their ``0x`` prefix stripped where the kernel emits
    one, e.g. ``idVendor`` -> ``067b``).  When the
    trailing human-readable name is present (e.g.
    ``idVendor  0x067b Prolific Technology, Inc.``) it
    is stored in ``idVendor_name`` / ``idProduct_name``.
    """
    descriptors: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None
    for line in text.splitlines():
        if "Device Descriptor:" in line:
            if current is not None:
                descriptors.append(current)
            current = {}
            continue
        if current is None:
            continue
        stripped = line.strip()
        if (
            not stripped
            or "Descriptor:" in stripped
            or _LSUSB_RE.match(stripped)
        ):
            descriptors.append(current)
            current = None
            continue
        match = _DESCRIPTOR_FIELD_RE.match(line)
        if match is None:
            continue
        field_name, value, extra = match.groups()
        if field_name not in _DESCRIPTOR_FIELDS:
            continue
        value = value.lower()
        if value.startswith("0x"):
            value = value[2:]
        current[field_name] = value
        if field_name in ("idVendor", "idProduct") and extra:
            current[field_name + "_name"] = extra.strip()
    if current is not None:
        descriptors.append(current)
    return descriptors


def parse_lsusb_tree(text: str) -> List[Dict[str, str]]:
    """Parse ``lsusb -t`` (tree) output.

    Returns a list of dicts with ``bus``, ``port``,
    ``dev`` and optionally ``if``, ``class``, ``driver``
    and ``speed_mb`` keys.  Child lines (no "Bus"
    prefix) inherit the bus number from the most
    recent root line.
    """
    nodes: List[Dict[str, str]] = []
    current_bus: Optional[str] = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Root line (contains "Bus")
        root_match = _ROOT_TREE_RE.search(stripped)
        if root_match is not None:
            current_bus = root_match.group(1)
            node: Dict[str, str] = {
                "bus": current_bus,
                "port": root_match.group(2),
                "dev": root_match.group(3),
            }
            if root_match.group(4) is not None and root_match.group(4).strip():
                node["class"] = root_match.group(4).strip()
            if root_match.group(5) is not None and root_match.group(5).strip():
                node["driver"] = root_match.group(5).strip()
            if root_match.group(6) is not None:
                node["speed_mb"] = root_match.group(6)
            nodes.append(node)
            continue
        # Child line (no "Bus" prefix)
        child_match = _CHILD_TREE_RE.search(stripped)
        if child_match is not None:
            node = {
                "port": child_match.group(1),
                "dev": child_match.group(2),
            }
            if child_match.group(3) is not None:
                node["if"] = child_match.group(3)
            if child_match.group(4) is not None and child_match.group(4).strip():
                node["class"] = child_match.group(4).strip()
            if child_match.group(5) is not None and child_match.group(5).strip():
                node["driver"] = child_match.group(5).strip()
            if child_match.group(6) is not None:
                node["speed_mb"] = child_match.group(6)
            if current_bus is not None:
                node["bus"] = current_bus
            nodes.append(node)
    return nodes


# ---------------------------------------------------------------------------
# Simulation mode
# ---------------------------------------------------------------------------

_SIM_DEVICES: Optional[Dict[str, Dict[str, str]]] = None


def set_simulation(
    devices: Optional[Dict[str, Dict[str, str]]],
) -> None:
    """Install an in-memory device table keyed by sysfs
    entry name (e.g. ``{"1-2": {"idVendor": "0781",
    ...}}``).

    Pass ``None`` (or use :func:`clear_simulation`) to
    return to real sysfs discovery.
    """
    global _SIM_DEVICES
    _SIM_DEVICES = devices
    if devices:
        log.info(
            "USB discovery simulation active with %d device(s)",
            len(devices),
        )
    else:
        log.info("USB discovery simulation cleared")


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
        return int(raw, 0) if raw.lower().startswith("0x") else int(raw)
    except ValueError:
        return None


def _read_sim(name: str) -> Optional[USBDeviceInfo]:
    if _SIM_DEVICES is None or name not in _SIM_DEVICES:
        return None
    if classify_usb_name(name) not in (KIND_ROOT_HUB, KIND_DEVICE):
        return None
    info = USBDeviceInfo(name=name)
    info.bus_num = _sim_read_int(name, "busnum")
    info.dev_num = _sim_read_int(name, "devnum")
    info.devpath = _sim_read(name, "devpath")
    info.vid = _sim_read(name, "idVendor")
    info.pid = _sim_read(name, "idProduct")
    info.bcd_device = _sim_read(name, "bcdDevice")
    info.device_class = _sim_read_int(name, "bDeviceClass")
    info.device_subclass = _sim_read_int(name, "bDeviceSubClass")
    info.device_protocol = _sim_read_int(name, "bDeviceProtocol")
    info.num_configs = _sim_read_int(name, "bNumConfigurations")
    info.max_packet_size0 = _sim_read_int(name, "bMaxPacketSize0")
    info.speed = _sim_read(name, "speed")
    info.version = _sim_read(name, "version")
    info.manufacturer = _sim_read(name, "manufacturer")
    info.product = _sim_read(name, "product")
    info.serial = _sim_read(name, "serial")
    info.max_child = _sim_read_int(name, "maxchild")
    info.num_interfaces = _sim_read_int(name, "bNumInterfaces")
    info.modalias = _sim_read(name, "modalias")
    return info


def discover_usb_devices(
    root: Path = SYS_BUS_USB_DEVICES,
) -> List[USBDeviceInfo]:
    """Discover all USB devices (root hubs and chain
    devices, interfaces excluded).

    Returns a list of :class:`USBDeviceInfo` sorted by
    name.  Empty when the host has no USB sysfs tree
    (non-Linux hosts) and no simulation is active.
    """
    if _SIM_DEVICES is not None:
        return sorted(
            (
                info
                for info in (
                    _read_sim(name)
                    for name in _SIM_DEVICES
                    if classify_usb_name(name) in (KIND_ROOT_HUB, KIND_DEVICE)
                )
                if info is not None
            ),
            key=lambda info: info.name,
        )
    if not root.exists():
        log.debug("no USB sysfs at %s", root)
        return []
    devices: List[USBDeviceInfo] = []
    for entry in sorted(os.listdir(root)):
        if classify_usb_name(entry) in (KIND_ROOT_HUB, KIND_DEVICE):
            info = read_usb_device(entry, root)
            if info is not None:
                devices.append(info)
    return devices


def find_by_vid_pid(
    vid: str,
    pid: str,
    root: Path = SYS_BUS_USB_DEVICES,
) -> List[USBDeviceInfo]:
    """Find devices by vendor/product ID.

    IDs may be passed with or without the ``0x`` prefix
    and in any case (``"0x0781"``, ``"0781"``).
    """
    def _normalize(raw: str) -> str:
        text = raw.strip().lower()
        if text.startswith("0x"):
            text = text[2:]
        return text.zfill(4)

    want_vid = _normalize(vid)
    want_pid = _normalize(pid)
    return [
        info
        for info in discover_usb_devices(root)
        if (info.vid or "").zfill(4) == want_vid
        and (info.pid or "").zfill(4) == want_pid
    ]


def _selftest() -> bool:
    """Run a basic self-test for this module."""
    # Name classification
    assert classify_usb_name("usb1") == KIND_ROOT_HUB
    assert classify_usb_name("1-2") == KIND_DEVICE
    assert classify_usb_name("1-2.4") == KIND_DEVICE
    assert classify_usb_name("1-2:1.0") == KIND_INTERFACE
    assert classify_usb_name("sdb") is None
    assert device_of_interface("1-2:1.0") == "1-2"

    # lsusb parsing
    parsed = parse_lsusb(
        "Bus 001 Device 007: ID 05e3:0610 "
        "Genesys Logic, Inc. 4-port hub"
    )
    assert parsed[0]["vid"] == "05e3", parsed
    assert parsed[0]["pid"] == "0610", parsed
    assert "hub" in parsed[0]["description"]

    verbose = parse_lsusb_verbose(
        "  Device Descriptor:\n"
        "    bcdUSB               2.00\n"
        "    idVendor           0x0781 SanDisk Corp.\n"
        "    idProduct          0x5581 Ultra Fit\n"
        "    bDeviceClass         0 (Defined at Interface level)\n"
    )
    assert verbose[0]["idVendor"] == "0781", verbose
    assert verbose[0]["idVendor_name"] == "SanDisk Corp.", verbose
    assert verbose[0]["idProduct"] == "5581", verbose

    tree = parse_lsusb_tree(
        "    |__ Port 1: Dev 2, If 0, Class=Mass Storage, "
        "Driver=usb-storage, 480M"
    )
    assert tree[0]["class"] == "Mass Storage", tree
    assert tree[0]["driver"] == "usb-storage", tree
    assert tree[0]["speed_mb"] == "480", tree

    # Simulation round-trip
    set_simulation({
        "usb1": {"busnum": "1", "devnum": "1",
                 "bDeviceClass": "9", "speed": "480"},
        "1-2": {"busnum": "1", "devnum": "5",
                "idVendor": "0781", "idProduct": "5581",
                "speed": "480", "version": "2.00",
                "product": "Ultra Fit"},
        "1-2:1.0": {"bInterfaceClass": "8"},
    })
    devices = discover_usb_devices()
    assert len(devices) == 2, devices
    # Sorted: "1-2" < "usb1" lexicographically
    stick = next(d for d in devices if d.name == "1-2")
    hub = next(d for d in devices if d.name == "usb1")
    assert stick.vendor_id == 0x0781
    assert stick.product_id == 0x5581
    assert stick.speed_name == "high_speed"
    assert stick.is_hub is False
    assert hub.is_hub is True
    found = find_by_vid_pid("0x0781", "5581")
    assert len(found) == 1 and found[0].name == "1-2"
    clear_simulation()
    assert discover_usb_devices() == [] or available()

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
