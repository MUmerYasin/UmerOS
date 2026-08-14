"""
UmerOS /media - Media Type Definitions
======================================

Defines the removable-media types recognised by the FHS /media hierarchy
and the UmerOS hotplug subsystem.

According to TLDP/FHS 3.0:

  The following directories, or symbolic links to directories, must be
  in /media, if the corresponding subsystem is installed:

    floppy     Floppy drive (optional)
    cdrom      CD-ROM drive (optional)
    cdrecorder CD writer (optional)
    zip        Zip drive (optional)

  On systems where more than one device exists for mounting a certain
  type of media, mount directories can be created by appending a digit
  to the name of those available above starting with '0', but the
  unqualified name must also exist.

UmerOS extends this with modern hotplug media types (USB, MMC, NVMe
removable, etc.) while keeping the legacy FHS types as the canonical
set.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# FHS-mandated and extended media types
# ---------------------------------------------------------------------------

class MediaType(str, Enum):
    """Enumeration of removable-media types.

    The first four values are **mandatory** per the FHS if the
    corresponding hardware subsystem is present.  The rest are
    modern extensions that UmerOS supports out of the box.
    """

    # --- FHS-required (optional hardware) ---
    FLOPPY      = "floppy"          # /media/floppy
    CDROM       = "cdrom"           # /media/cdrom
    CDRECORD    = "cdrecorder"      # /media/cdrecorder
    ZIP         = "zip"             # /media/zip

    # --- Modern hotplug extensions ---
    USB         = "usb"             # /media/usb  (generic USB storage)
    MMC         = "mmc"             # /media/mmc  (SD / micro-SD)
    NVME        = "nvme"            # /media/nvme (removable NVMe)
    BLUETOOTH   = "bluetooth"       # /media/bluetooth
    FIREWIRE    = "firewire"        # /media/firewire (IEEE 1394)
    TAPE        = "tape"            # /media/tape
    NETWORK     = "network"         # /media/network (NFS/CIFS/SMB mounts)
    CUSTOM      = "custom"          # /media/<user-label>

    @property
    def display_name(self) -> str:
        """Human-friendly name for the media type."""
        _DISPLAY: Dict[str, str] = {
            "floppy":     "Floppy Disk",
            "cdrom":      "CD-ROM",
            "cdrecorder": "CD Writer",
            "zip":        "Zip Drive",
            "usb":        "USB Storage",
            "mmc":        "SD / MMC Card",
            "nvme":       "NVMe (Removable)",
            "bluetooth":  "Bluetooth Storage",
            "firewire":   "FireWire (IEEE 1394)",
            "tape":       "Magnetic Tape",
            "network":    "Network Share",
            "custom":     "Custom Label",
        }
        return _DISPLAY.get(self.value, self.value.title())

    @property
    def is_fhs_required(self) -> bool:
        """True for the four FHS-mandated media types."""
        return self in (
            MediaType.FLOPPY,
            MediaType.CDROM,
            MediaType.CDRECORD,
            MediaType.ZIP,
        )

    @property
    def typical_fs(self) -> List[str]:
        """List of filesystem types typically found on this media."""
        _FS: Dict[str, List[str]] = {
            "floppy":     ["vfat", "ext2"],
            "cdrom":      ["iso9660", "udf"],
            "cdrecorder": ["iso9660", "udf"],
            "zip":        ["vfat", "ext2"],
            "usb":        ["vfat", "ntfs", "exfat", "ext4", "ext3", "ext2"],
            "mmc":        ["vfat", "exfat", "ext4"],
            "nvme":       ["ext4", "xfs", "btrfs", "ntfs", "exfat"],
            "bluetooth":  ["vfat"],
            "firewire":   ["ext4", "hfs+", "ntfs"],
            "tape":       ["ext2"],
            "network":    ["nfs", "cifs", "smbfs"],
            "custom":     [],
        }
        return _FS.get(self.value, [])


# ---------------------------------------------------------------------------
# Mount-point naming conventions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MountNaming:
    """Naming convention for a media type's mount-point hierarchy.

    Attributes:
        base_name:    The unqualified directory name (e.g. ``"cdrom"``).
        media_type:   The corresponding :class:`MediaType`.
        numbered:     Whether numbered variants are allowed.
        max_count:    Maximum numbered instances (0 = unlimited).
        symlink_name: If set, a symlink with this name should point to
                      the most-recently-inserted numbered instance.
    """

    base_name: str
    media_type: MediaType
    numbered: bool = True
    max_count: int = 0     # 0 = unlimited
    symlink_name: Optional[str] = None


# Default naming rules for every FHS + extended media type.
MOUNT_NAMING: Dict[MediaType, MountNaming] = {
    MediaType.FLOPPY: MountNaming(
        base_name="floppy",
        media_type=MediaType.FLOPPY,
        numbered=True,
        max_count=4,
    ),
    MediaType.CDROM: MountNaming(
        base_name="cdrom",
        media_type=MediaType.CDROM,
        numbered=True,
        max_count=8,
        symlink_name="cdrom",      # /media/cdrom -> /media/cdrom0
    ),
    MediaType.CDRECORD: MountNaming(
        base_name="cdrecorder",
        media_type=MediaType.CDRECORD,
        numbered=True,
        max_count=4,
    ),
    MediaType.ZIP: MountNaming(
        base_name="zip",
        media_type=MediaType.ZIP,
        numbered=True,
        max_count=4,
    ),
    MediaType.USB: MountNaming(
        base_name="usb",
        media_type=MediaType.USB,
        numbered=True,
        max_count=0,       # unlimited USB devices
    ),
    MediaType.MMC: MountNaming(
        base_name="mmc",
        media_type=MediaType.MMC,
        numbered=True,
        max_count=4,
    ),
    MediaType.NVME: MountNaming(
        base_name="nvme",
        media_type=MediaType.NVME,
        numbered=True,
        max_count=0,
    ),
    MediaType.BLUETOOTH: MountNaming(
        base_name="bluetooth",
        media_type=MediaType.BLUETOOTH,
        numbered=False,
        max_count=1,
    ),
    MediaType.FIREWIRE: MountNaming(
        base_name="firewire",
        media_type=MediaType.FIREWIRE,
        numbered=True,
        max_count=4,
    ),
    MediaType.TAPE: MountNaming(
        base_name="tape",
        media_type=MediaType.TAPE,
        numbered=True,
        max_count=4,
    ),
    MediaType.NETWORK: MountNaming(
        base_name="network",
        media_type=MediaType.NETWORK,
        numbered=False,
        max_count=0,
    ),
}


# ---------------------------------------------------------------------------
# Media descriptor (a fully-resolved device on a mount point)
# ---------------------------------------------------------------------------

@dataclass
class MediaDescriptor:
    """Describes a detected or mounted piece of removable media.

    This is the primary data object returned by device detection and
    consumed by the mount manager.
    """

    media_type: MediaType
    device_path: str                     # e.g. "/dev/sr0", "/dev/sdb1"
    mount_point: Optional[str] = None    # e.g. "/media/cdrom0"
    filesystem: Optional[str] = None     # e.g. "iso9660", "vfat"
    label: Optional[str] = None          # volume label
    uuid: Optional[str] = None           # filesystem UUID
    size_bytes: int = 0
    read_only: bool = False
    mounted: bool = False
    user: Optional[str] = None           # owning user (for /run/media/$USER)
    options: List[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        """Human-readable summary line."""
        parts = [self.media_type.display_name, self.device_path]
        if self.label:
            parts.append(f'"{self.label}"')
        if self.mount_point:
            parts.append(f"-> {self.mount_point}")
        if self.filesystem:
            parts.append(f"[{self.filesystem}]")
        if self.read_only:
            parts.append("(ro)")
        return " ".join(parts)

    @property
    def is_fhs(self) -> bool:
        """True if this media type is FHS-required."""
        return self.media_type.is_fhs_required
