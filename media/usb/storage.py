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
UmerOS /media/usb - USB Mass-Storage Mapping
==================================================

Maps Linux block devices (``/dev/sdX``) to their
backing USB devices by resolving the sysfs symlink
chain:

::

    /sys/block/sdb
      └── device -> ../../devices/.../usb1/1-2/1-2:1.0/
                      host2/target2:0:0/2:0:0:0

A block device is USB-backed when one of its
ancestors in that chain is a USB device entry
(a directory carrying ``idVendor`` / ``idProduct``
attributes, e.g. ``1-2``).

The module also gathers per-device capacity,
removability, read-only state and (best-effort,
via ``blkid``) filesystem / label / UUID - the
same metadata the rest of the ``media`` package
uses for mounting decisions.

Pure Python (standard library only).

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .device import (
    SYS_BUS_USB_DEVICES,
    USBDeviceInfo,
    classify_usb_name,
    read_usb_device,
)

log = logging.getLogger("UmerOS.Media.USB.Storage")

SYS_BLOCK = Path("/sys/block")

# Block-device names that are never USB storage.
_BLOCK_SKIP_PREFIXES = ("loop", "ram", "dm-", "sr", "md")

# Simulation table: block name -> USB device name.
_STORAGE_SIM: Optional[Dict[str, str]] = None


@dataclass
class USBStorageDevice:
    """A block device (``/dev/sdX``) backed by a
    USB device."""

    block_name: str
    usb_name: Optional[str] = None
    device_path: str = ""
    size_bytes: Optional[int] = None
    removable: bool = False
    read_only: bool = False
    filesystem: Optional[str] = None
    label: Optional[str] = None
    uuid: Optional[str] = None
    usb: Optional[USBDeviceInfo] = None

    @property
    def mounted_name(self) -> str:
        """Suggested mount base name (the block
        device, e.g. ``sdb``)."""
        return self.block_name


def _read_sysfs_attr(path: Path) -> Optional[str]:
    try:
        return path.read_text(
            encoding="utf-8", errors="replace"
        ).strip()
    except (OSError, IOError):
        return None


def _read_sysfs_int(path: Path) -> Optional[int]:
    raw = _read_sysfs_attr(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _blkid_field(partition_path: str, option: str) -> Optional[str]:
    """Best-effort single-field extraction via
    ``blkid`` (``-s TYPE|LABEL|UUID``)."""
    try:
        result = subprocess.run(
            ["blkid", "-s", option, "-o", "value",
             partition_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if value else None


def usb_backing_device(
    block_name: str,
    sys_block: Path = SYS_BLOCK,
) -> Optional[str]:
    """Return the USB sysfs entry name (e.g.
    ``1-2``) backing the block device *block_name*
    (e.g. ``sdb``), or ``None`` when the device is
    not USB-backed (or sysfs is unavailable).

    The ``device`` symlink of the block device is
    resolved and its ancestor chain walked until a
    directory carrying ``idVendor`` / ``idProduct``
    (a USB device entry) is found.
    """
    device_link = sys_block / block_name / "device"
    if not device_link.exists():
        return None
    try:
        current = device_link.resolve()
    except OSError:
        return None
    seen = 0
    while current != current.parent and seen < 64:
        if (current / "idVendor").exists() and (
            current / "idProduct"
        ).exists():
            name = current.name
            if classify_usb_name(name) in (
                "root_hub",
                "device",
            ):
                return name
        current = current.parent
        seen += 1
    # Fall back: no symlink resolution - the link
    # target text itself may name the USB entry.
    return None


def read_storage_device(
    block_name: str,
    usb_name: str,
    sys_block: Path = SYS_BLOCK,
    usb_root: Path = SYS_BUS_USB_DEVICES,
) -> USBStorageDevice:
    """Build a :class:`USBStorageDevice` for the
    block device *block_name* backed by the USB
    entry *usb_name*."""
    device = USBStorageDevice(
        block_name=block_name,
        usb_name=usb_name,
        device_path=f"/dev/{block_name}",
    )
    block_dir = sys_block / block_name
    device.size_bytes = (
        _read_sysfs_int(block_dir / "size")
    )
    if device.size_bytes is not None:
        device.size_bytes *= 512
    device.removable = (
        _read_sysfs_int(block_dir / "removable") == 1
    )
    device.read_only = (
        _read_sysfs_int(block_dir / "ro") == 1
    )
    device.filesystem = _blkid_field(
        device.device_path, "TYPE"
    )
    device.label = _blkid_field(
        device.device_path, "LABEL"
    )
    device.uuid = _blkid_field(
        device.device_path, "UUID"
    )
    device.usb = read_usb_device(usb_name, usb_root)
    return device


def discover_usb_storage(
    sys_block: Path = SYS_BLOCK,
    usb_root: Path = SYS_BUS_USB_DEVICES,
) -> List[USBStorageDevice]:
    """Discover block devices backed by USB
    devices.

    Returns a list of :class:`USBStorageDevice`
    sorted by block name.  On non-Linux hosts (no
    sysfs) the result is empty unless a storage
    simulation is active.
    """
    global _STORAGE_SIM
    if _STORAGE_SIM is not None:
        devices: List[USBStorageDevice] = []
        for block_name in sorted(_STORAGE_SIM):
            usb_name = _STORAGE_SIM[block_name]
            devices.append(
                read_storage_device(
                    block_name, usb_name, sys_block,
                    usb_root,
                )
            )
        return devices
    if not sys_block.exists():
        log.debug("no block sysfs at %s", sys_block)
        return []
    devices = []
    try:
        entries = sorted(os.listdir(sys_block))
    except OSError as exc:
        log.warning("cannot list %s: %s", sys_block, exc)
        return []
    for block_name in entries:
        if block_name.startswith(_BLOCK_SKIP_PREFIXES):
            continue
        usb_name = usb_backing_device(
            block_name, sys_block
        )
        if usb_name is None:
            continue
        devices.append(
            read_storage_device(
                block_name, usb_name, sys_block,
                usb_root,
            )
        )
    return devices


def set_storage_simulation(
    mapping: Optional[Dict[str, str]],
) -> None:
    """Install a block-name -> USB-device-name
    simulation table, e.g. ``{"sdb": "1-2"}``.

    Pass ``None`` (or use
    :func:`clear_storage_simulation`) to return to
    real sysfs discovery.
    """
    global _STORAGE_SIM
    _STORAGE_SIM = mapping
    if mapping:
        log.info(
            "USB storage simulation active with %d "
            "device(s)",
            len(mapping),
        )
    else:
        log.info("USB storage simulation cleared")


def get_storage_simulation() -> Optional[Dict[str, str]]:
    """Return the active storage simulation table,
    or ``None``."""
    return _STORAGE_SIM


def clear_storage_simulation() -> None:
    """Clear the storage simulation table."""
    set_storage_simulation(None)


def _selftest() -> bool:
    """Run a basic self-test for this module."""
    set_storage_simulation({"sdb": "1-2"})
    devices = discover_usb_storage()
    assert len(devices) == 1, devices
    assert devices[0].block_name == "sdb"
    assert devices[0].usb_name == "1-2"
    assert devices[0].device_path == "/dev/sdb"
    clear_storage_simulation()

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
