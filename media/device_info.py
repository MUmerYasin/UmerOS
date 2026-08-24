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
UmerOS /media - Device Detection and Information
=================================================

Provides an abstraction layer over device-node inspection to
identify removable-media devices and populate
:class:`~media.media_types.MediaDescriptor` objects.

The module works in two modes:

1. **Real-system mode** (default when ``/sys`` and ``/dev`` are
   accessible) – reads sysfs attributes andblkid output.
2. **Simulated mode** – accepts explicitly-provided device metadata
   so that UmerOS can exercise the media subsystem without physical
   hardware.

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

from .media_types import MediaDescriptor, MediaType

log = logging.getLogger("UmerOS.Media.DeviceInfo")


# ---------------------------------------------------------------------------
# Sysfs / procfs helpers
# ---------------------------------------------------------------------------

_SYSBlock = Path("/sys/block")
_PROCMounts = Path("/proc/mounts")
_PROCPartitions = Path("/proc/partitions")


def _read_sysfs(path: Path) -> Optional[str]:
    """Read a single-value sysfs attribute, return *None* on failure."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, IOError):
        return None


def _read_proc_mounts() -> List[Dict[str, str]]:
    """Parse ``/proc/mounts`` into a list of dicts."""
    entries: List[Dict[str, str]] = []
    if not _PROCMounts.exists():
        return entries
    try:
        text = _PROCMounts.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entries
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            entries.append({
                "device": parts[0],
                "mount_point": parts[1],
                "fstype": parts[2],
                "options": parts[3],
            })
    return entries


# ---------------------------------------------------------------------------
# Device classification heuristics
# ---------------------------------------------------------------------------

def _is_removable_sysfs(device_name: str) -> bool:
    """Check the sysfs ``removable`` attribute."""
    val = _read_sysfs(_SYSBlock / device_name / "removable")
    return val == "1"


def _is_ro_sysfs(device_name: str) -> bool:
    """Check the sysfs ``ro`` (read-only) attribute."""
    val = _read_sysfs(_SYSBlock / device_name / "ro")
    return val == "1"


def _get_model(device_name: str) -> Optional[str]:
    return _read_sysfs(_SYSBlock / device_name / "device" / "model")


def _get_vendor(device_name: str) -> Optional[str]:
    return _read_sysfs(_SYSBlock / device_name / "device" / "vendor")


def _get_size_sectors(device_name: str) -> Optional[int]:
    val = _read_sysfs(_SYSBlock / device_name / "size")
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return None


def _get_partition_uuid(partition_path: str) -> Optional[str]:
    """Best-effort UUID extraction via ``blkid``."""
    try:
        import subprocess
        result = subprocess.run(
            ["blkid", "-s", "UUID", "-o", "value", partition_path],
            capture_output=True, text=True, timeout=5,
        )
        uuid = result.stdout.strip()
        return uuid if uuid else None
    except Exception:
        return None


def _get_partition_label(partition_path: str) -> Optional[str]:
    """Best-effort label extraction via ``blkid``."""
    try:
        import subprocess
        result = subprocess.run(
            ["blkid", "-s", "LABEL", "-o", "value", partition_path],
            capture_output=True, text=True, timeout=5,
        )
        label = result.stdout.strip()
        return label if label else None
    except Exception:
        return None


def _get_partition_fs(partition_path: str) -> Optional[str]:
    """Best-effort filesystem-type extraction via ``blkid``."""
    try:
        import subprocess
        result = subprocess.run(
            ["blkid", "-s", "TYPE", "-o", "value", partition_path],
            capture_output=True, text=True, timeout=5,
        )
        fs = result.stdout.strip()
        return fs if fs else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Type classification from device name / model / fs
# ---------------------------------------------------------------------------

def _classify_device(
    device_name: str,
    model: Optional[str],
    fs: Optional[str],
) -> MediaType:
    """Heuristic mapping from device metadata to :class:`MediaType`."""
    name_lower = device_name.lower()
    model_lower = (model or "").lower()

    # Optical
    if "sr" in name_lower or "cdrom" in name_lower:
        return MediaType.CDROM
    if "cd" in name_lower and ("writer" in model_lower or "recorder" in model_lower):
        return MediaType.CDRECORD

    # Floppy
    if "fd" in name_lower or "floppy" in name_lower:
        return MediaType.FLOPPY

    # Zip
    if "zip" in name_lower or "zip" in model_lower:
        return MediaType.ZIP

    # MMC / SD
    if "mmc" in name_lower or "mmcblk" in name_lower:
        return MediaType.MMC

    # NVMe (removable)
    if "nvme" in name_lower:
        return MediaType.NVME

    # Tape
    if "st" == name_lower[:2] or "tape" in model_lower:
        return MediaType.TAPE

    # FireWire
    if "firewire" in model_lower or "1394" in model_lower:
        return MediaType.FIREWIRE

    # Default: generic USB-like removable
    return MediaType.USB


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class DeviceScanResult:
    """Result of a device scan operation."""

    descriptors: List[MediaDescriptor] = field(default_factory=list)
    mount_entries: List[Dict[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.descriptors)


def scan_devices(
    *,
    include_partitions: bool = True,
    simulated: Optional[List[MediaDescriptor]] = None,
) -> DeviceScanResult:
    """Scan for removable-media devices.

    Args:
        include_partitions: If *True*, scan individual partitions
                            (e.g. ``/dev/sdb1``) in addition to whole
                            disks (``/dev/sdb``).
        simulated:          If provided, return these descriptors
                            directly instead of probing the system.

    Returns:
        A :class:`DeviceScanResult` with all detected descriptors.
    """
    result = DeviceScanResult()

    if simulated is not None:
        result.descriptors = list(simulated)
        return result

    # If sysfs is unavailable, fall back to /proc/mounts only
    if not _SYSBlock.exists():
        log.info("sysfs not available at %s; using /proc/mounts fallback", _SYSBlock)
        for entry in _read_proc_mounts():
            result.mount_entries.append(entry)
            desc = MediaDescriptor(
                media_type=MediaType.NETWORK
                if entry["fstype"] in ("nfs", "cifs", "smbfs")
                else MediaType.USB,
                device_path=entry["device"],
                mount_point=entry["mount_point"],
                filesystem=entry["fstype"],
                mounted=True,
            )
            result.descriptors.append(desc)
        return result

    try:
        block_devices = sorted(os.listdir(_SYSBlock))
    except OSError as exc:
        result.errors.append(f"Cannot list {_SYSBlock}: {exc}")
        return result

    mounts = {e["device"]: e for e in _read_proc_mounts()}

    for dev_name in block_devices:
        # Skip loop, ram, dm- devices
        if dev_name.startswith(("loop", "ram", "dm-")):
            continue

        removable = _is_removable_sysfs(dev_name)
        if not removable and not include_partitions:
            continue

        model = _get_model(dev_name)
        ro = _is_ro_sysfs(dev_name)
        size_sectors = _get_size_sectors(dev_name)
        size_bytes = (size_sectors or 0) * 512

        dev_path = f"/dev/{dev_name}"
        media_type = _classify_device(dev_name, model, None)

        # Whole-disk descriptor
        mount_info = mounts.get(dev_path)
        desc = MediaDescriptor(
            media_type=media_type,
            device_path=dev_path,
            mount_point=mount_info["mount_point"] if mount_info else None,
            filesystem=mount_info["fstype"] if mount_info else None,
            size_bytes=size_bytes,
            read_only=ro,
            mounted=mount_info is not None,
        )
        result.descriptors.append(desc)

        # Partitions
        if include_partitions:
            for i in range(1, 32):
                part_name = f"{dev_name}{i}"
                part_path = f"/dev/{part_name}"
                part_sysfs = _SYSBlock / dev_name / part_name
                if not part_sysfs.exists():
                    continue

                fs = _get_partition_fs(part_path)
                label = _get_partition_label(part_path)
                uuid = _get_partition_uuid(part_path)
                mount_info = mounts.get(part_path)

                part_desc = MediaDescriptor(
                    media_type=_classify_device(part_name, model, fs),
                    device_path=part_path,
                    mount_point=mount_info["mount_point"] if mount_info else None,
                    filesystem=fs,
                    label=label,
                    uuid=uuid,
                    size_bytes=0,  # partition size not easily read from sysfs
                    read_only=ro,
                    mounted=mount_info is not None,
                )
                result.descriptors.append(part_desc)

    return result


def detect_media_type(device_path: str) -> MediaType:
    """Quick classification of a single device path.

    Uses the device name and, if available, sysfs attributes to
    determine the most likely :class:`MediaType`.
    """
    dev_name = Path(device_path).name
    model = _get_model(dev_name)
    return _classify_device(dev_name, model, None)


def get_mount_info(device_path: str) -> Optional[Dict[str, str]]:
    """Look up mount information for *device_path* from ``/proc/mounts``."""
    for entry in _read_proc_mounts():
        if entry["device"] == device_path:
            return entry
    return None


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    result = detect_device("/dev/sda1")
    assert result is not None, "detect_device should return a MediaType"

    print("selftest OK")


if __name__ == "__main__":
    _selftest()
