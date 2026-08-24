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
UmerOS /media - UDisks2 Interface
==================================

Simulation of the UDisks2 D-Bus interface for querying and
managing block devices, drives, and filesystems.

UDisks2 reference:
    UDisks2 is a D-Bus service for managing storage devices.
    It provides high-level APIs for mount/unmount, format,
    partitioning, and SMART monitoring.

Modules
-------
- ``UDisks2Client`` - client for querying/managing devices.
- ``UDisks2Object`` - representation of a UDisks2 object.
- ``UDisks2Drive`` - drive (physical device) representation.
- ``UDisks2Block`` - block device representation.

Quick start::

    from media.udisks2 import UDisks2Client

    client = UDisks2Client()
    client.scan()
    for dev in client.block_devices:
        print(dev.device, dev.id_type, dev.mount_points)
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from .mount_ops import MountResult, mount, unmount, is_mounted, mount_status

log = logging.getLogger("UmerOS.Media.UDisks2")


# ---------------------------------------------------------------------------
#  Enums
# ---------------------------------------------------------------------------

@unique
class UDisks2ObjectType(Enum):
    """UDisks2 object types."""
    MANAGER = "manager"
    DRIVE = "drive"
    BLOCK = "block"
    FILESYSTEM = "filesystem"
    PARTITION = "partition"
    PARTITION_TABLE = "partition_table"
    SWAP = "swap"
    RAID = "raid"
    SMART = "smart"


# ---------------------------------------------------------------------------
#  UDisks2 Object (base)
# ---------------------------------------------------------------------------

@dataclass
class UDisks2Object:
    """Base UDisks2 object with D-Bus path and properties."""
    object_path: str
    obj_type: UDisks2ObjectType = UDisks2ObjectType.BLOCK
    properties: Dict[str, Any] = field(default_factory=dict)

    def get_property(self, iface: str, name: str) -> Any:
        key = f"{iface}.{name}"
        return self.properties.get(key)

    def set_property(self, iface: str, name: str, value: Any) -> None:
        key = f"{iface}.{name}"
        self.properties[key] = value

    def get_all_properties(self, iface: str) -> Dict[str, Any]:
        prefix = f"{iface}."
        return {k[len(prefix):]: v for k, v in self.properties.items()
                if k.startswith(prefix)}


# ---------------------------------------------------------------------------
#  Drive
# ---------------------------------------------------------------------------

@dataclass
class UDisks2Drive(UDisks2Object):
    """A physical drive (HDD, SSD, USB stick, optical)."""
    model: str = ""
    vendor: str = ""
    serial: str = ""
    revision: str = ""
    size: int = 0  # bytes
    media: str = ""  # e.g. "usb", "optical", "flash"
    media_compatibility: List[str] = field(default_factory=list)
    connection_bus: str = ""
    seat: str = ""
    removable: bool = False
    ejectable: bool = False
    optical: bool = False
    rotation_rate: int = 0
    wwn: str = ""
    partitions: List[str] = field(default_factory=list)  # object paths

    def __post_init__(self) -> None:
        if self.obj_type == UDisks2ObjectType.BLOCK:
            self.obj_type = UDisks2ObjectType.DRIVE

    @property
    def display_name(self) -> str:
        if self.model:
            return f"{self.vendor} {self.model}".strip()
        return self.serial or self.object_path

    @property
    def size_human(self) -> str:
        if self.size <= 0:
            return "unknown"
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if self.size < 1024:
                return f"{self.size:.1f} {unit}"
            self.size /= 1024
        return f"{self.size:.1f} PiB"


# ---------------------------------------------------------------------------
#  Block Device
# ---------------------------------------------------------------------------

@dataclass
class UDisks2Block(UDisks2Object):
    """A block device (partition or whole-disk)."""
    device: str = ""  # e.g. /dev/sdb1
    device_file: str = ""
    preferred_device: str = ""
    symlinks: List[str] = field(default_factory=list)
    id_type: str = ""  # e.g. "vfat", "ext4", "crypto_LUKS"
    id_usage: str = ""  # e.g. "filesystem", "filesystem"
    id_version: str = ""
    id_label: str = ""
    id_uuid: str = ""
    size: int = 0  # bytes
    partition: int = 0  # partition number
    partition_table: str = ""
    drive_object_path: str = ""
    mount_points: List[str] = field(default_factory=list)
    hint_system: bool = False
    hint_auto: bool = True
    hint_name: str = ""
    configuration: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.device and not self.device_file:
            self.device_file = self.device

    @property
    def is_filesystem(self) -> bool:
        return self.id_usage == "filesystem"

    @property
    def is_mounted(self) -> bool:
        return len(self.mount_points) > 0

    @property
    def is_crypto(self) -> bool:
        return "crypto" in self.id_type.lower()

    @property
    def display_name(self) -> str:
        if self.id_label:
            return self.id_label
        return os.path.basename(self.device) or self.object_path


# ---------------------------------------------------------------------------
#  Client
# ---------------------------------------------------------------------------

class UDisks2Client:
    """High-level client for querying and managing UDisks2 devices.

    On Linux this would be a D-Bus proxy; here we simulate using
    /proc/mounts and /sys/block or accept manual registration.
    """

    def __init__(self, *, simulate: bool = True) -> None:
        self._simulate = simulate
        self._drives: Dict[str, UDisks2Drive] = {}
        self._blocks: Dict[str, UDisks2Block] = {}
        self._listeners: List[Callable[[str, UDisks2Object], None]] = []

    # -- Scan -----------------------------------------------------------------

    def scan(self) -> int:
        """Scan for devices.  Returns total count found."""
        count = 0
        if not self._simulate:
            count = self._scan_real()
        log.info("UDisks2 scan found %d devices", count)
        return count

    def _scan_real(self) -> int:
        """Scan using /proc/mounts and /sys/block."""
        count = 0
        # Discover block devices from /sys/block
        sys_block = Path("/sys/block")
        if sys_block.exists():
            for dev_dir in sys_block.iterdir():
                if dev_dir.name.startswith(("loop", "ram", "dm-")):
                    continue
                self._scan_sysblock_device(dev_dir)
                count += 1
        # Discover mounts from /proc/mounts
        mounts = self._read_proc_mounts()
        for mount in mounts:
            dev = mount.get("device", "")
            for blk in self._blocks.values():
                if blk.device == dev:
                    blk.mount_points.append(mount.get("mount_point", ""))
                    break
        return count

    def _scan_sysblock_device(self, dev_dir: Path) -> None:
        """Scan a /sys/block/<device> entry."""
        dev_name = dev_dir.name
        device_path = f"/dev/{dev_name}"
        obj_path = f"/org/freedesktop/UDisks2/block_devices/{dev_name}"

        # Read size
        size_file = dev_dir / "size"
        size_sectors = 0
        if size_file.exists():
            try:
                size_sectors = int(size_file.read_text().strip())
            except (ValueError, OSError):
                pass

        # Read removable
        removable = False
        rem_file = dev_dir / "removable"
        if rem_file.exists():
            removable = rem_file.read_text().strip() == "1"

        # Create drive
        drive_path = f"/org/freedesktop/UDisks2/drives/{dev_name}"
        drive = UDisks2Drive(
            object_path=drive_path,
            model=dev_name,
            size=size_sectors * 512,
            removable=removable,
            media="unknown",
        )
        self._drives[drive_path] = drive

        # Create block device
        block = UDisks2Block(
            object_path=obj_path,
            device=device_path,
            size=size_sectors * 512,
            drive_object_path=drive_path,
        )
        self._blocks[obj_path] = block
        drive.partitions.append(obj_path)

    @staticmethod
    def _read_proc_mounts() -> List[Dict[str, str]]:
        """Read /proc/mounts."""
        mounts: List[Dict[str, str]] = []
        try:
            with open("/proc/mounts", "r") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) >= 3:
                        mounts.append({
                            "device": parts[0],
                            "mount_point": parts[1],
                            "fs_type": parts[2],
                            "options": parts[3] if len(parts) > 3 else "",
                        })
        except FileNotFoundError:
            pass
        return mounts

    # -- Manual registration --------------------------------------------------

    def register_drive(self, drive: UDisks2Drive) -> None:
        """Manually register a drive."""
        self._drives[drive.object_path] = drive

    def register_block(self, block: UDisks2Block) -> None:
        """Manually register a block device."""
        self._blocks[block.object_path] = block
        if block.drive_object_path and block.drive_object_path in self._drives:
            drive = self._drives[block.drive_object_path]
            if block.object_path not in drive.partitions:
                drive.partitions.append(block.object_path)

    # -- Query ----------------------------------------------------------------

    @property
    def drives(self) -> List[UDisks2Drive]:
        return list(self._drives.values())

    @property
    def block_devices(self) -> List[UDisks2Block]:
        return list(self._blocks.values())

    def get_drive(self, object_path: str) -> Optional[UDisks2Drive]:
        return self._drives.get(object_path)

    def get_block(self, object_path: str) -> Optional[UDisks2Block]:
        return self._blocks.get(object_path)

    def get_block_by_device(self, device: str) -> Optional[UDisks2Block]:
        for blk in self._blocks.values():
            if blk.device == device:
                return blk
        return None

    def get_mounted_devices(self) -> List[UDisks2Block]:
        return [b for b in self._blocks.values() if b.is_mounted]

    def get_removable_drives(self) -> List[UDisks2Drive]:
        return [d for d in self._drives.values() if d.removable]

    def get_drive_partitions(self, drive_path: str) -> List[UDisks2Block]:
        drive = self._drives.get(drive_path)
        if not drive:
            return []
        return [self._blocks[p] for p in drive.partitions
                if p in self._blocks]

    def get_object(self, object_path: str) -> Optional[UDisks2Object]:
        return self._drives.get(object_path) or self._blocks.get(object_path)

    def get_all_objects(self) -> List[UDisks2Object]:
        result: List[UDisks2Object] = []
        result.extend(self._drives.values())
        result.extend(self._blocks.values())
        return result

    # -- Actions --------------------------------------------------------------

    def mount(self, block_path: str, options: Optional[str] = None) -> MountResult:
        """Mount a block device."""
        # [FIX H156] Privileged mount is enforced in media.mount_ops.mount, which
        # gates the fs.admin capability at the single integration seam.
        blk = self._blocks.get(block_path)
        if not blk:
            return MountResult(success=False, error=MountResult.Error.DEVICE_NOT_FOUND,
                               message=f"Unknown block: {block_path}")
        if blk.is_mounted:
            return MountResult(success=True, mount_point=blk.mount_points[0],
                               message="Already mounted")
        mount_point = f"/media/{blk.id_label or os.path.basename(blk.device)}"
        result = mount(blk.device, mount_point, create_dir=True)
        if result.success:
            blk.mount_points.append(mount_point)
        return result

    def unmount(self, block_path: str) -> MountResult:
        """Unmount a block device."""
        blk = self._blocks.get(block_path)
        if not blk:
            return MountResult(success=False, error=MountResult.Error.DEVICE_NOT_FOUND,
                               message=f"Unknown block: {block_path}")
        if not blk.mount_points:
            return MountResult(success=False, error=MountResult.Error.NOT_MOUNTED,
                               message="Not mounted")
        mp = blk.mount_points[0]
        result = unmount(mp)
        if result.success:
            blk.mount_points = [m for m in blk.mount_points if m != mp]
        return result

    # -- Listeners ------------------------------------------------------------

    def on_event(self, callback: Callable[[str, UDisks2Object], None]) -> None:
        self._listeners.append(callback)

    def _emit(self, action: str, obj: UDisks2Object) -> None:
        for cb in self._listeners:
            try:
                cb(action, obj)
            except Exception:
                log.exception("UDisks2 listener error")


# ---------------------------------------------------------------------------
#  Convenience
# ---------------------------------------------------------------------------

def get_removable_media_info() -> List[Dict[str, Any]]:
    """Quick helper: scan and return info dicts for removable media."""
    client = UDisks2Client()
    client.scan()
    result = []
    for drive in client.get_removable_drives():
        partitions = client.get_drive_partitions(drive.object_path)
        for part in partitions:
            result.append({
                "device": part.device,
                "label": part.id_label,
                "uuid": part.id_uuid,
                "fs_type": part.id_type,
                "size": drive.size,
                "size_human": drive.size_human,
                "mounted": part.is_mounted,
                "mount_points": part.mount_points,
            })
    return result


def _selftest() -> bool:
    """Run self-diagnostics.  Returns True on success."""
    from .mount_ops import set_simulation, clear_sim_mounts

    set_simulation(True)
    clear_sim_mounts()

    # Create client
    client = UDisks2Client(simulate=True)
    assert len(client.drives) == 0  # may have no devices after scan

    # Register manual devices
    drive = UDisks2Drive(
        object_path="/org/freedesktop/UDisks2/drives/usb_sdb",
        model="USB Drive",
        vendor="Generic",
        size=32_000_000_000,
        removable=True,
        media="usb",
    )
    block = UDisks2Block(
        object_path="/org/freedesktop/UDisks2/block_devices/sdb1",
        device="/dev/sdb1",
        id_type="vfat",
        id_usage="filesystem",
        id_label="MYUSB",
        id_uuid="ABCD-1234",
        size=32_000_000_000,
        drive_object_path="/org/freedesktop/UDisks2/drives/usb_sdb",
    )
    client.register_drive(drive)
    client.register_block(block)

    # Query
    assert len(client.drives) == 1
    assert len(client.block_devices) == 1
    assert client.get_drive(drive.object_path) is drive
    assert client.get_block(block.object_path) is block
    assert client.get_block_by_device("/dev/sdb1") is block
    removable = client.get_removable_drives()
    assert len(removable) == 1
    assert removable[0].removable
    partitions = client.get_drive_partitions(drive.object_path)
    assert len(partitions) == 1

    # Block properties
    assert block.is_filesystem
    assert not block.is_mounted
    assert not block.is_crypto
    assert block.display_name == "MYUSB"

    # Drive properties
    assert drive.display_name == "Generic USB Drive"
    assert "32" in drive.size_human or drive.size_human != "unknown"

    # Mount (sim)
    result = client.mount(block.object_path)
    assert result.success
    assert block.is_mounted
    assert client.get_mounted_devices()

    # Unmount (sim)
    result2 = client.unmount(block.object_path)
    assert result2.success
    assert not block.is_mounted

    # Listener
    events: List[tuple] = []
    client.on_event(lambda a, o: events.append((a, o.object_path)))
    client._emit("test", block)
    assert len(events) == 1

    clear_sim_mounts()
    return True
