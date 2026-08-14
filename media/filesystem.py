"""
UmerOS /media - Filesystem Type Detection and Validation
=========================================================

Detects, validates, and maps filesystem types for removable media.
Supports all common filesystems plus optical disc formats.

Modules
-------
- ``FsType`` enum with per-type metadata (mount options, max size, read-only flag).
- ``detect_fs_type()`` - classify a device by name heuristic or magic bytes.
- ``validate_fs_type()`` - check if a filesystem type is supported.
- ``mount_options_for()`` - recommended default mount options for a type.
- ``SUPPORTED_FS`` - frozenset of all supported type strings.

Quick start::

    from media.filesystem import detect_fs_type, mount_options_for

    fs = detect_fs_type("/dev/sr0")          # -> FsType.ISO9660
    opts = mount_options_for(FsType.EXT4)     # -> ["noatime","data=ordered"]
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from enum import Enum, unique
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
#  Filesystem-type enumeration
# ---------------------------------------------------------------------------

@unique
class FsType(str, Enum):
    """Supported filesystem types with metadata."""

    #  Native
    EXT2 = "ext2"
    EXT3 = "ext3"
    EXT4 = "ext4"
    BTRFS = "btrfs"
    XFS = "xfs"
    F2FS = "f2fs"
    TMPFS = "tmpfs"

    # Windows-compatible
    VFAT = "vfat"
    FAT12 = "fat12"
    FAT16 = "fat16"
    FAT32 = "fat32"
    EXFAT = "exfat"
    NTFS = "ntfs"

    # Optical
    ISO9660 = "iso9660"
    UDF = "udf"

    # Apple
    HFS_PLUS = "hfsplus"
    APFS = "apfs"

    # Network / pseudo
    NFS = "nfs"
    CIFS = "cifs"
    SMBFS = "smbfs"
    PROC = "proc"
    SYSFS = "sysfs"
    DEVPTS = "devpts"

    # Other
    SQUASHFS = "squashfs"
    ROMFS = "romfs"
    MINIX = "minix"
    REISERFS = "reiserfs"
    NILFS2 = "nilfs2"
    OCFS2 = "ocfs2"
    GFS2 = "gfs2"
    JFS = "jfs"
    ZFS = "zfs"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        """Human-friendly name."""
        _names = {
            "ext2": "Ext2 (Linux)",
            "ext3": "Ext3 (Linux, journaled)",
            "ext4": "Ext4 (Linux, journaled)",
            "btrfs": "Btrfs (Linux, CoW)",
            "xfs": "XFS (Linux, high-perf)",
            "f2fs": "F2FS (Flash-friendly)",
            "tmpfs": "Tmpfs (RAM)",
            "vfat": "VFAT (Windows compat)",
            "fat12": "FAT12 (floppy)",
            "fat16": "FAT16",
            "fat32": "FAT32",
            "exfat": "exFAT (SD cards)",
            "ntfs": "NTFS (Windows)",
            "iso9660": "ISO 9660 (CD-ROM)",
            "udf": "UDF (DVD/Blu-ray)",
            "hfsplus": "HFS+ (Apple)",
            "apfs": "APFS (Apple)",
            "nfs": "NFS (network)",
            "cifs": "CIFS/SMB (network)",
            "smbfs": "SMBFS (network)",
            "proc": "Proc (pseudo)",
            "sysfs": "Sysfs (pseudo)",
            "devpts": "DevPts (pseudo)",
            "squashfs": "SquashFS (compressed)",
            "romfs": "ROMfs",
            "minix": "Minix",
            "reiserfs": "ReiserFS",
            "nilfs2": "NILFS2",
            "ocfs2": "OCFS2",
            "gfs2": "GFS2",
            "jfs": "JFS (IBM)",
            "zfs": "ZFS",
            "unknown": "Unknown",
        }
        return _names.get(self.value, self.value)

    @property
    def is_read_only(self) -> bool:
        """True if the filesystem is inherently read-only."""
        return self in {
            FsType.ISO9660,
            FsType.ROMFS,
            FsType.SQUASHFS,
            FsType.SYSFS,
            FsType.PROC,
        }

    @property
    def max_size_bytes(self) -> Optional[int]:
        """Maximum filesystem size in bytes, or None if unlimited."""
        _limits = {
            FsType.FAT12: 2**32 - 1,         # ~4 GB
            FsType.FAT16: 2**32 - 1,          # ~4 GB
            FsType.FAT32: 4 * 1024**3 - 1,    # ~4 GB (FAT32 spec)
            FsType.VFAT: 4 * 1024**3 - 1,
            FsType.EXT2: 4 * 1024**4,          # 4 TiB (1k blocks)
            FsType.EXT3: 4 * 1024**4,
            FsType.EXT4: 1 * 1024**5,          # 1 EiB
            FsType.XFS: 8 * 1024**5,           # 8 EiB
            FsType.BTRFS: 16 * 1024**5,        # 16 EiB
            FsType.NTFS: 256 * 1024**4,        # 256 TiB
            FsType.EXFAT: 128 * 1024**4,       # 128 TiB
            FsType.ISO9660: 8 * 1024**4,       # 8 TiB
            FsType.UDF: 2 * 1024**5,           # 2 EiB
            FsType.HFS_PLUS: 8 * 1024**4,      # 8 TiB
        }
        return _limits.get(self)

    @property
    def typical_fs(self) -> List[str]:
        """Filesystem types typically found on this media (by name)."""
        _typical: Dict[str, List[str]] = {
            "ext2": ["ext2", "ext3", "ext4"],
            "ext3": ["ext2", "ext3", "ext4"],
            "ext4": ["ext2", "ext3", "ext4"],
            "btrfs": ["btrfs"],
            "xfs": ["xfs"],
            "vfat": ["vfat", "fat32", "exfat"],
            "fat32": ["vfat", "fat32", "exfat"],
            "exfat": ["exfat", "vfat"],
            "ntfs": ["ntfs"],
            "iso9660": ["iso9660", "udf"],
            "udf": ["udf", "iso9660"],
            "hfsplus": ["hfsplus"],
        }
        return _typical.get(self.value, [self.value])


# ---------------------------------------------------------------------------
#  Magic-byte signatures for detection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _MagicSignature:
    """A filesystem magic-byte signature."""
    offset: int
    magic: bytes
    mask: Optional[bytes] = None


_MAGIC_TABLE: Dict[FsType, List[_MagicSignature]] = {
    FsType.EXT2: [
        _MagicSignature(offset=0x438, magic=b"\x53\xef"),           # super block magic
    ],
    FsType.EXT3: [
        _MagicSignature(offset=0x438, magic=b"\x53\xef"),
    ],
    FsType.EXT4: [
        _MagicSignature(offset=0x438, magic=b"\x53\xef"),
    ],
    FsType.BTRFS: [
        _MagicSignature(offset=0x40, magic=b"_BHRfS_M"),
    ],
    FsType.XFS: [
        _MagicSignature(offset=0, magic=b"XFSB"),
    ],
    FsType.VFAT: [
        _MagicSignature(offset=0, magic=b"MSDOS"),
        _MagicSignature(offset=0, magic=b"FAT12 "),
        _MagicSignature(offset=0, magic=b"FAT16 "),
        _MagicSignature(offset=0, magic=b"FAT32 "),
    ],
    FsType.NTFS: [
        _MagicSignature(offset=3, magic=b"NTFS    "),
    ],
    FsType.EXFAT: [
        _MagicSignature(offset=3, magic=b"EXFAT   "),
    ],
    FsType.ISO9660: [
        _MagicSignature(offset=0x8001, magic=b"CD001"),
        _MagicSignature(offset=0x8801, magic=b"CD001"),   # Enhanced VD
    ],
    FsType.UDF: [
        _MagicSignature(offset=1, magic=b"BEA01"),
        _MagicSignature(offset=1, magic=b"NSR02"),
        _MagicSignature(offset=1, magic=b"NSR03"),
        _MagicSignature(offset=1, magic=b"TEA01"),
    ],
    FsType.HFS_PLUS: [
        _MagicSignature(offset=0, magic=b"H+" , mask=None),
        _MagicSignature(offset=0, magic=b"BD" , mask=None),
    ],
    FsType.SQUASHFS: [
        _MagicSignature(offset=0, magic=b"hsqs"),
        _MagicSignature(offset=0, magic=b"sqsh"),
        _MagicSignature(offset=0, magic=b"shsq"),
        _MagicSignature(offset=0, magic=b"qshs"),
    ],
    FsType.ROMFS: [
        _MagicSignature(offset=0, magic=b"-rom1fs-"),
    ],
    FsType.REISERFS: [
        _MagicSignature(offset=0x34, magic=b"ReIsErFs"),
        _MagicSignature(offset=0x34, magic=b"ReIsEr2Fs"),
        _MagicSignature(offset=0x34, magic=b"ReIsEr3Fs"),
    ],
    FsType.JFS: [
        _MagicSignature(offset=0, magic=b"JFS1"),
    ],
    FsType.NILFS2: [
        _MagicSignature(offset=0x400, magic=b"NILFS"),
    ],
    FsType.OCFS2: [
        _MagicSignature(offset=0, magic=b"OCFS2"),
    ],
    FsType.GFS2: [
        _MagicSignature(offset=0, magic=b"HB20"),
    ],
    FsType.MINIX: [
        _MagicSignature(offset=0x410, magic=b"\x13\x7f"),
        _MagicSignature(offset=0x418, magic=b"\x13\x8f"),
        _MagicSignature(offset=0x410, magic=b"\x24\x78"),
    ],
    FsType.F2FS: [
        _MagicSignature(offset=0x400, magic=b"\x10\x20\xf5\xf2"),
    ],
}


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

SUPPORTED_FS: FrozenSet[str] = frozenset(
    t.value for t in FsType if t != FsType.UNKNOWN
)


@dataclass
class FsInfo:
    """Detailed information about a detected filesystem."""
    fs_type: FsType
    label: Optional[str] = None
    uuid: Optional[str] = None
    size_bytes: int = 0
    free_bytes: int = 0
    block_size: int = 0
    mount_options: List[str] = field(default_factory=list)


def detect_fs_type(
    device_path: str,
    *,
    probe_magic: bool = True,
    fallback: FsType = FsType.UNKNOWN,
) -> FsType:
    """Classify the filesystem on *device_path*.

    Detection order:
    1. Name-based heuristic (e.g. ``/dev/sr0`` -> ISO9660).
    2. Magic-byte probe if *probe_magic* is True.
    3. Return *fallback* if nothing matches.

    Args:
        device_path: Kernel device node (e.g. ``"/dev/sdb1"``).
        probe_magic: Read magic bytes from the device.
        fallback: Return value when detection fails.

    Returns:
        Best-guess ``FsType``.
    """
    name = os.path.basename(device_path).lower()

    # --- 1. Name heuristics ---
    if name.startswith("sr") or name.startswith("cdrom"):
        return FsType.ISO9660
    if name.startswith("fd"):
        return FsType.VFAT
    if name.startswith("loop"):
        # Could be anything; try magic
        pass
    if name.startswith("nvme"):
        return FsType.NVME  # type: ignore[attr-defined]

    # --- 2. Magic-byte probe ---
    if probe_magic and os.path.exists(device_path):
        detected = _probe_magic(device_path)
        if detected is not None:
            return detected

    return fallback


def _probe_magic(device_path: str) -> Optional[FsType]:
    """Read magic bytes from *device_path* and match against known signatures."""
    try:
        with open(device_path, "rb") as fh:
            for fs_type, sigs in _MAGIC_TABLE.items():
                for sig in sigs:
                    try:
                        fh.seek(sig.offset)
                        data = fh.read(len(sig.magic))
                        if data == sig.magic:
                            return fs_type
                    except (OSError, ValueError):
                        continue
    except (OSError, PermissionError, ValueError):
        pass
    return None


def validate_fs_type(fs_type: str) -> bool:
    """Return True if *fs_type* is a supported filesystem string."""
    return fs_type.lower() in SUPPORTED_FS


def mount_options_for(
    fs_type: FsType,
    *,
    read_only: bool = False,
    removable: bool = False,
    user_mount: bool = False,
) -> List[str]:
    """Recommended default mount options for *fs_type*.

    Args:
        fs_type: Target filesystem type.
        read_only: Add ``ro`` if True.
        removable: Add ``noexec,nosuid,nodev`` for removable media.
        user_mount: Add ``user`` / ``users`` for non-root mounting.

    Returns:
        List of mount-option strings.
    """
    opts: List[str] = []

    # Per-FS defaults
    _defaults: Dict[FsType, List[str]] = {
        FsType.EXT2: ["noatime"],
        FsType.EXT3: ["noatime", "data=ordered"],
        FsType.EXT4: ["noatime", "data=ordered"],
        FsType.BTRFS: ["noatime", "compress=zstd"],
        FsType.XFS: ["noatime"],
        FsType.F2FS: ["noatime"],
        FsType.VFAT: ["uid=1000", "gid=1000", "umask=022"],
        FsType.FAT12: ["uid=1000", "gid=1000", "umask=022"],
        FsType.FAT16: ["uid=1000", "gid=1000", "umask=022"],
        FsType.FAT32: ["uid=1000", "gid=1000", "umask=022"],
        FsType.EXFAT: ["uid=1000", "gid=1000", "umask=022"],
        FsType.NTFS: ["uid=1000", "gid=1000", "umask=022", "dmask=022"],
        FsType.ISO9660: ["uid=1000", "gid=1000", "umask=022"],
        FsType.UDF: ["uid=1000", "gid=1000", "umask=022"],
        FsType.HFS_PLUS: ["uid=1000", "gid=1000"],
        FsType.SQUASHFS: ["uid=1000", "gid=1000"],
        FsType.NFS: ["rw", "hard", "intr"],
        FsType.CIFS: ["rw", "credentials=/etc/samba/creds"],
    }
    opts.extend(_defaults.get(fs_type, []))

    if read_only or fs_type.is_read_only:
        opts.append("ro")
    else:
        opts.append("rw")

    if removable:
        for extra in ("noexec", "nosuid", "nodev"):
            if extra not in opts:
                opts.append(extra)

    if user_mount:
        if "users" not in opts:
            opts.append("users")

    return opts


def fs_type_from_name(name: str) -> FsType:
    """Convert a filesystem name string to ``FsType``.

    Returns ``FsType.UNKNOWN`` for unrecognized names.
    """
    _map = {t.value: t for t in FsType}
    return _map.get(name.lower().strip(), FsType.UNKNOWN)


def list_removable_fs() -> List[FsType]:
    """Return filesystem types typically found on removable media."""
    return [
        FsType.VFAT, FsType.FAT32, FsType.EXFAT, FsType.NTFS,
        FsType.ISO9660, FsType.UDF, FsType.HFS_PLUS, FsType.EXT2,
        FsType.EXT3, FsType.EXT4, FsType.EXT4, FsType.BTRFS,
        FsType.XFS, FsType.SQUASHFS,
    ]


def _selftest() -> bool:
    """Run self-diagnostics.  Returns True on success."""
    assert FsType.EXT4.display_name
    assert FsType.ISO9660.is_read_only
    assert not FsType.EXT4.is_read_only
    assert FsType.NTFS.max_size_bytes is not None
    assert validate_fs_type("ext4")
    assert not validate_fs_type("bogus")
    assert fs_type_from_name("ext4") == FsType.EXT4
    assert fs_type_from_name("BOGUS") == FsType.UNKNOWN
    opts = mount_options_for(FsType.EXT4, read_only=True, removable=True)
    assert "ro" in opts
    assert "noexec" in opts
    assert len(list_removable_fs()) > 0
    return True
