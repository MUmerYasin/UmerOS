"""
UmerOS MTD (Memory Technology Device) Framework
================================================
Linux kernel MTD subsystem.
Implements MTD devices (NOR, NAND, DataFlash), partitions,
OOB operations, bad block management, and read/write/erase.
"""

from __future__ import annotations

import os
import struct
import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Tuple, Set, Any

# ---------------------------------------------------------------------------
# MTD type constants
# ---------------------------------------------------------------------------
MTD_RAM: int = 0
MTD_ROM: int = 1
MTD_NORFLASH: int = 2
MTD_NANDFLASH: int = 3
MTD_DATAFLASH: int = 4
MTD_UBIVOLUME: int = 5
MTD_MLCNANDFLASH: int = 6
MTD_NANDSLC: int = 7

_MTD_TYPE_NAMES: Dict[int, str] = {
    MTD_RAM: "RAM",
    MTD_ROM: "ROM",
    MTD_NORFLASH: "NOR",
    MTD_NANDFLASH: "NAND",
    MTD_DATAFLASH: "DataFlash",
    MTD_UBIVOLUME: "UBI",
    MTD_MLCNANDFLASH: "MLC NAND",
    MTD_NANDSLC: "SLC NAND",
}

# ---------------------------------------------------------------------------
# MTD flag constants
# ---------------------------------------------------------------------------
MTD_WRITEABLE: int = 0x0001
MTD_BIT_WRITEABLE: int = 0x0002
MTD_NO_ERASE: int = 0x0004
MTD_STUPID_LOCK: int = 0x0008
MTD_XIP: int = 0x0010
MTD_ERASE_SUSPEND: int = 0x0020
MTD_DATAFLAGS: int = 0x0040
MTD_OOB_RETRIEVED: int = 0x0080
MTD_OTP: int = 0x0100
MTD_RAW: int = 0x0200

_MTD_FLAG_NAMES: Dict[int, str] = {
    MTD_WRITEABLE: "WRITEABLE",
    MTD_BIT_WRITEABLE: "BIT_WRITEABLE",
    MTD_NO_ERASE: "NO_ERASE",
    MTD_STUPID_LOCK: "STUPID_LOCK",
    MTD_XIP: "XIP",
    MTD_ERASE_SUSPEND: "ERASE_SUSPEND",
    MTD_DATAFLAGS: "DATAFLAGS",
    MTD_OOB_RETRIEVED: "OOB_RETRIEVED",
    MTD_OTP: "OTP",
    MTD_RAW: "RAW",
}

# ---------------------------------------------------------------------------
# OOB operation modes
# ---------------------------------------------------------------------------
MTD_OPS_AUTO_OOB: int = 0
MTD_OPS_PLACE_OOB: int = 1
MTD_OPS_RAW: int = 2

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MtdInfo:
    """Memory technology device info"""
    name: str
    type: int  # MTD_RAM=0, MTD_ROM=1, MTD_NORFLASH=2, MTD_NANDFLASH=3, MTD_DATAFLASH=4, MTD_UBIVOLUME=5
    flags: int = 0
    size: int = 0  # total size in bytes
    erasesize: int = 0  # erase block size
    writesize: int = 0  # write page size
    oobsize: int = 0  # OOB size per erase block
    oobavail: int = 0  # available OOB
    num_parts: int = 0
    index: int = 0
    _erase: Optional[Callable] = field(default=None, repr=False)
    _read: Optional[Callable] = field(default=None, repr=False)
    _write: Optional[Callable] = field(default=None, repr=False)
    _read_oob: Optional[Callable] = field(default=None, repr=False)
    _write_oob: Optional[Callable] = field(default=None, repr=False)
    _block_isbad: Optional[Callable] = field(default=None, repr=False)
    _block_markbad: Optional[Callable] = field(default=None, repr=False)
    _data: bytearray = field(default_factory=bytearray, repr=False)
    _bad_blocks: Set[int] = field(default_factory=set, repr=False)

@dataclass
class MtdPart:
    """MTD partition"""
    name: str
    mtd_name: str  # parent MTD device
    offset: int
    size: int
    index: int = 0
    mask_flags: int = 0
    _data: bytearray = field(default_factory=bytearray, repr=False)

@dataclass
class MtdPartition:
    """MTD partition table"""
    mtd_name: str
    parts: List[MtdPart] = field(default_factory=list)  # list of MtdPart

@dataclass
class MtdOobOps:
    """OOB operations"""
    mode: int = 0  # MTD_OPS_AUTO_OOB=0, MTD_OPS_PLACE_OOB=1, MTD_OPS_RAW=2
    ooblen: int = 0
    oobretlen: int = 0
    ooboffs: int = 0
    datbuf: bytes = b''
    oobbuf: bytes = b''

@dataclass
class MtdEraseInfo:
    """Erase info"""
    addr: int = 0
    len: int = 0

@dataclass
class MtdWriteReq:
    """Write request"""
    addr: int
    data: bytes
    oob: bytes = b''
    ooboffs: int = 0

@dataclass
class MtdReadReq:
    """Read request"""
    addr: int
    len: int
    oob: bool = False

# ---------------------------------------------------------------------------
# Global registries
# ---------------------------------------------------------------------------
_devices: Dict[str, MtdInfo] = {}
_partitions: Dict[str, MtdPartition] = {}
_device_index: int = 0

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _flags_to_str(flags: int) -> str:
    """Convert flags bitmask to human-readable string."""
    parts: List[str] = []
    for bit, name in sorted(_MTD_FLAG_NAMES.items()):
        if flags & bit:
            parts.append(name)
    return "|".join(parts) if parts else "NONE"


def _get_device(name: str) -> MtdInfo:
    """Retrieve device or raise KeyError."""
    if name not in _devices:
        raise KeyError(f"MTD device '{name}' not registered")
    return _devices[name]


def _simulate_nand_bad_block_scan(dev: MtdInfo) -> None:
    """Simulate bad block scanning for NAND devices (random ~2% bad blocks)."""
    if dev.type not in (MTD_NANDFLASH, MTD_MLCNANDFLASH, MTD_NANDSLC):
        return
    dev._bad_blocks.clear()
    if dev.erasesize == 0:
        return
    num_blocks = dev.size // dev.erasesize
    for blk in range(num_blocks):
        # Simulate ~2% bad blocks via deterministic hash
        h = hashlib.md5(f"{dev.name}:{blk}".encode()).digest()
        if h[0] < 6:  # ~2.3%
            dev._bad_blocks.add(blk * dev.erasesize)


def _oob_offset_for_block(dev: MtdInfo, block_addr: int) -> int:
    """Return OOB region start for a given erase block."""
    if dev.erasesize == 0:
        return 0
    block_idx = block_addr // dev.erasesize
    return block_idx * dev.oobsize


# ---------------------------------------------------------------------------
# Kernel API: Registration
# ---------------------------------------------------------------------------

def mtd_device_register(
    name: str,
    size: int,
    mtd_type: int,
    erasesize: int = 4096,
    writesize: int = 512,
    oobsize: int = 128,
    flags: int = MTD_WRITEABLE,
) -> MtdInfo:
    """Register MTD device.

    Parameters
    ----------
    name : str
        Device name (e.g. ``"nor0"``).
    size : int
        Total device size in bytes.
    mtd_type : int
        One of ``MTD_RAM``, ``MTD_NORFLASH``, ``MTD_NANDFLASH``, etc.
    erasesize : int
        Erase block size in bytes (default 4096).
    writesize : int
        Write page size in bytes (default 512).
    oobsize : int
        OOB size per erase block (default 128).
    flags : int
        Capability flags (default ``MTD_WRITEABLE``).

    Returns
    -------
    MtdInfo
        The newly registered device.
    """
    global _device_index

    if name in _devices:
        raise ValueError(f"MTD device '{name}' already registered")

    dev = MtdInfo(
        name=name,
        type=mtd_type,
        flags=flags,
        size=size,
        erasesize=erasesize,
        writesize=writesize,
        oobsize=oobsize,
        oobavail=oobsize,
        index=_device_index,
        _data=bytearray(size),
    )
    _device_index += 1
    _devices[name] = dev

    # For NAND types, auto-scan bad blocks
    if mtd_type in (MTD_NANDFLASH, MTD_MLCNANDFLASH, MTD_NANDSLC):
        _simulate_nand_bad_block_scan(dev)

    return dev


def mtd_device_unregister(name: str) -> None:
    """Unregister MTD device.

    Removes the device and all associated partitions.
    """
    _get_device(name)  # validate exists
    del _devices[name]
    # Remove associated partitions
    to_remove = [k for k in _partitions if _partitions[k].mtd_name == name]
    for k in to_remove:
        del _partitions[k]


def mtd_get_device(name: str) -> MtdInfo:
    """Get MTD device info."""
    return _get_device(name)


# ---------------------------------------------------------------------------
# Kernel API: Erase
# ---------------------------------------------------------------------------

def mtd_erase(name: str, offset: int, length: int) -> MtdEraseInfo:
    """Erase MTD region.

    Parameters
    ----------
    name : str
        Device name.
    offset : int
        Byte offset to start erasing.
    length : int
        Number of bytes to erase.

    Returns
    -------
    MtdEraseInfo
        Erase result info.
    """
    dev = _get_device(name)

    if offset + length > dev.size:
        raise ValueError(
            f"Erase range [{offset}, {offset + length}) exceeds device size {dev.size}"
        )

    # Align to erase boundary
    aligned_offset = offset - (offset % dev.erasesize) if dev.erasesize else offset
    aligned_length = length + (offset - aligned_offset)

    # Check bad blocks for NAND
    if dev.type in (MTD_NANDFLASH, MTD_MLCNANDFLASH, MTD_NANDSLC):
        if dev.erasesize > 0:
            blk_start = aligned_offset // dev.erasesize
            blk_end = (aligned_offset + aligned_length) // dev.erasesize
            for blk in range(blk_start, blk_end):
                if blk * dev.erasesize in dev._bad_blocks:
                    raise IOError(f"Bad block at offset 0x{blk * dev.erasesize:x}")

    # Perform erase: zero-fill region
    end = min(aligned_offset + aligned_length, dev.size)
    if dev._erase is not None:
        dev._erase(dev, aligned_offset, end - aligned_offset)
    else:
        for i in range(aligned_offset, end):
            dev._data[i] = 0xFF  # NOR convention: erased = 0xFF

    return MtdEraseInfo(addr=aligned_offset, len=end - aligned_offset)


# ---------------------------------------------------------------------------
# Kernel API: Read / Write
# ---------------------------------------------------------------------------

def mtd_read(name: str, offset: int, length: int) -> bytes:
    """Read from MTD device.

    Parameters
    ----------
    name : str
        Device name.
    offset : int
        Byte offset.
    length : int
        Number of bytes to read.

    Returns
    -------
    bytes
        Data read from device.
    """
    dev = _get_device(name)

    if offset + length > dev.size:
        raise ValueError(
            f"Read range [{offset}, {offset + length}) exceeds device size {dev.size}"
        )

    if dev._read is not None:
        return dev._read(dev, offset, length)

    return bytes(dev._data[offset:offset + length])


def mtd_write(name: str, offset: int, data: bytes) -> int:
    """Write to MTD device.

    Parameters
    ----------
    name : str
        Device name.
    offset : int
        Byte offset.
    data : bytes
        Data to write.

    Returns
    -------
    int
        Number of bytes written.
    """
    dev = _get_device(name)

    if not (dev.flags & MTD_WRITEABLE):
        raise IOError(f"MTD device '{name}' is not writeable")

    if offset + len(data) > dev.size:
        raise ValueError(
            f"Write range [{offset}, {offset + len(data)}) exceeds device size {dev.size}"
        )

    # Check bad blocks for NAND
    if dev.type in (MTD_NANDFLASH, MTD_MLCNANDFLASH, MTD_NANDSLC):
        if dev.erasesize > 0:
            blk_offset = offset - (offset % dev.erasesize)
            if blk_offset in dev._bad_blocks:
                raise IOError(f"Cannot write to bad block at offset 0x{blk_offset:x}")

    if dev._write is not None:
        return dev._write(dev, offset, data)

    dev._data[offset:offset + len(data)] = data
    return len(data)


def mtd_panic_write(name: str, offset: int, data: bytes) -> int:
    """Panic write (last resort).

    Bypasses write protections and bad block checks.
    Used in emergency/kernel-panic scenarios.
    """
    dev = _get_device(name)

    if offset + len(data) > dev.size:
        raise ValueError(
            f"Panic write range [{offset}, {offset + len(data)}) exceeds device size {dev.size}"
        )

    dev._data[offset:offset + len(data)] = data
    return len(data)


# ---------------------------------------------------------------------------
# Kernel API: OOB
# ---------------------------------------------------------------------------

def mtd_read_oob(name: str, offset: int, length: int) -> bytes:
    """Read OOB data from MTD device.

    Parameters
    ----------
    name : str
        Device name.
    offset : int
        Byte offset (typically aligned to erase block).
    length : int
        Number of OOB bytes to read.

    Returns
    -------
    bytes
        OOB data.
    """
    dev = _get_device(name)

    if dev.oobsize == 0:
        raise IOError(f"MTD device '{name}' has no OOB area")

    if dev._read_oob is not None:
        return dev._read_oob(dev, offset, length)

    oob_off = _oob_offset_for_block(dev, offset)
    # OOB is stored at the very end of the device data area
    oob_region_start = dev.size - (dev.size // dev.erasesize * dev.oobsize) if dev.erasesize else dev.size
    actual_off = oob_region_start + oob_off
    end = min(actual_off + length, dev.size)

    if actual_off >= dev.size:
        # Fallback: generate synthetic OOB
        return bytes([0xFF] * length)

    return bytes(dev._data[actual_off:end])


def mtd_write_oob(name: str, offset: int, data: bytes) -> int:
    """Write OOB data to MTD device.

    Parameters
    ----------
    name : str
        Device name.
    offset : int
        Byte offset (typically aligned to erase block).
    data : bytes
        OOB data to write.

    Returns
    -------
    int
        Number of OOB bytes written.
    """
    dev = _get_device(name)

    if dev.oobsize == 0:
        raise IOError(f"MTD device '{name}' has no OOB area")

    if not (dev.flags & MTD_WRITEABLE):
        raise IOError(f"MTD device '{name}' is not writeable")

    if dev._write_oob is not None:
        return dev._write_oob(dev, offset, data)

    oob_off = _oob_offset_for_block(dev, offset)
    oob_region_start = dev.size - (dev.size // dev.erasesize * dev.oobsize) if dev.erasesize else dev.size
    actual_off = oob_region_start + oob_off
    end = min(actual_off + len(data), dev.size)

    if actual_off >= dev.size:
        return 0

    dev._data[actual_off:end] = data[:end - actual_off]
    return end - actual_off


def mtd_oob_get_available(name: str) -> int:
    """Get available OOB size."""
    dev = _get_device(name)
    return dev.oobavail


# ---------------------------------------------------------------------------
# Kernel API: Bad block management
# ---------------------------------------------------------------------------

def mtd_block_isbad(name: str, offset: int) -> bool:
    """Check if block is bad.

    Parameters
    ----------
    name : str
        Device name.
    offset : int
        Block offset (typically aligned to erase block).

    Returns
    -------
    bool
        ``True`` if the block is marked bad.
    """
    dev = _get_device(name)

    if dev._block_isbad is not None:
        return dev._block_isbad(dev, offset)

    return offset in dev._bad_blocks


def mtd_block_markbad(name: str, offset: int) -> None:
    """Mark block as bad.

    Parameters
    ----------
    name : str
        Device name.
    offset : int
        Block offset (typically aligned to erase block).
    """
    dev = _get_device(name)

    if dev._block_markbad is not None:
        dev._block_markbad(dev, offset)
    else:
        dev._bad_blocks.add(offset)


def mtd_scan_bad_blocks(name: str) -> List[int]:
    """Scan for bad blocks.

    Returns list of bad block offsets.
    Only meaningful for NAND-type devices.
    """
    dev = _get_device(name)
    return sorted(dev._bad_blocks)


# ---------------------------------------------------------------------------
# Kernel API: Partition management
# ---------------------------------------------------------------------------

def mtd_add_partition(mtd_name: str, part_name: str, offset: int, size: int) -> MtdPart:
    """Add partition to MTD device.

    Parameters
    ----------
    mtd_name : str
        Parent MTD device name.
    part_name : str
        Partition name.
    offset : int
        Byte offset within parent device.
    size : int
        Partition size in bytes.

    Returns
    -------
    MtdPart
        The newly created partition.
    """
    dev = _get_device(mtd_name)

    if offset + size > dev.size:
        raise ValueError(
            f"Partition '{part_name}' [{offset}, {offset + size}) exceeds device size {dev.size}"
        )

    # Create partition table if needed
    if mtd_name not in _partitions:
        _partitions[mtd_name] = MtdPartition(mtd_name=mtd_name)

    pt = _partitions[mtd_name]

    # Check for overlapping partitions
    for p in pt.parts:
        existing_end = p.offset + p.size
        new_end = offset + size
        if p.offset < new_end and offset < existing_end:
            raise ValueError(
                f"Partition '{part_name}' overlaps with existing partition '{p.name}'"
            )

    part_idx = len(pt.parts)
    part = MtdPart(
        name=part_name,
        mtd_name=mtd_name,
        offset=offset,
        size=size,
        index=part_idx,
    )

    # Initialize partition data as a view into parent
    part._data = dev._data[offset:offset + size]
    pt.parts.append(part)
    dev.num_parts = len(pt.parts)

    return part


def mtd_del_partition(mtd_name: str, part_name: str) -> None:
    """Delete partition."""
    if mtd_name not in _partitions:
        raise KeyError(f"No partition table for MTD device '{mtd_name}'")

    pt = _partitions[mtd_name]
    for i, p in enumerate(pt.parts):
        if p.name == part_name:
            pt.parts.pop(i)
            # Reindex
            for j, pp in enumerate(pt.parts):
                pp.index = j
            dev = _devices.get(mtd_name)
            if dev is not None:
                dev.num_parts = len(pt.parts)
            return

    raise KeyError(f"Partition '{part_name}' not found on MTD device '{mtd_name}'")


def mtd_get_partition(mtd_name: str, part_name: str) -> MtdPart:
    """Get partition info."""
    if mtd_name not in _partitions:
        raise KeyError(f"No partition table for MTD device '{mtd_name}'")

    for p in _partitions[mtd_name].parts:
        if p.name == part_name:
            return p

    raise KeyError(f"Partition '{part_name}' not found on MTD device '{mtd_name}'")


def mtd_partition_table(mtd_name: str) -> MtdPartition:
    """Get partition table for MTD device."""
    _get_device(mtd_name)  # validate exists
    if mtd_name not in _partitions:
        return MtdPartition(mtd_name=mtd_name)
    return _partitions[mtd_name]


# ---------------------------------------------------------------------------
# Kernel API: Chip info
# ---------------------------------------------------------------------------

def mtd_get_erasesize(name: str) -> int:
    """Get erase block size."""
    return _get_device(name).erasesize


def mtd_get_writesize(name: str) -> int:
    """Get write page size."""
    return _get_device(name).writesize


def mtd_get_oobsize(name: str) -> int:
    """Get OOB size."""
    return _get_device(name).oobsize


def mtd_get_size(name: str) -> int:
    """Get total size."""
    return _get_device(name).size


# ---------------------------------------------------------------------------
# Kernel API: Info
# ---------------------------------------------------------------------------

def mtd_get_type_string(name: str) -> str:
    """Get type as string."""
    dev = _get_device(name)
    return _MTD_TYPE_NAMES.get(dev.type, f"UNKNOWN({dev.type})")


def mtd_is_writeable(name: str) -> bool:
    """Check if MTD is writeable."""
    return bool(_get_device(name).flags & MTD_WRITEABLE)


# ---------------------------------------------------------------------------
# Kernel API: Listing
# ---------------------------------------------------------------------------

def mtd_list_devices() -> List[str]:
    """List all MTD devices."""
    return list(_devices.keys())


def mtd_list_partitions(mtd_name: str) -> List[str]:
    """List partitions for MTD device."""
    if mtd_name not in _partitions:
        return []
    return [p.name for p in _partitions[mtd_name].parts]


# ---------------------------------------------------------------------------
# Built-in simulated MTD devices
# ---------------------------------------------------------------------------

class SimNorFlash:
    """Simulated NOR flash (Spansion/Intel style).

    Parameters
    ----------
    name : str
        Device name (default ``"nor0"``).
    size : int
        Total flash size (default 16 MiB).
    erase_size : int
        Erase block size (default 64 KiB).

    NOR flash characteristics:
    - Byte-addressable
    - Supports XIP (execute in place)
    - Erased state = 0xFF
    - No OOB area
    """

    def __init__(
        self,
        name: str = "nor0",
        size: int = 16 * 1024 * 1024,
        erase_size: int = 64 * 1024,
    ) -> None:
        self.name = name
        self.dev = mtd_device_register(
            name=name,
            size=size,
            mtd_type=MTD_NORFLASH,
            erasesize=erase_size,
            writesize=1,  # byte-addressable
            oobsize=0,
            flags=MTD_WRITEABLE | MTD_XIP | MTD_BIT_WRITEABLE,
        )


class SimNandFlash:
    """Simulated NAND flash (2KB pages, 128KB erase blocks).

    Parameters
    ----------
    name : str
        Device name (default ``"nand0"``).
    size : int
        Total flash size (default 256 MiB).
    page_size : int
        Write page size (default 2048 bytes).
    erase_size : int
        Erase block size (default 128 KiB).
    oob_size : int
        OOB area per erase block (default 64 bytes).

    NAND flash characteristics:
    - Page-based read/write
    - Block-based erase
    - Has OOB (out-of-band) area
    - Bad blocks possible (~2% simulated)
    """

    def __init__(
        self,
        name: str = "nand0",
        size: int = 256 * 1024 * 1024,
        page_size: int = 2048,
        erase_size: int = 128 * 1024,
        oob_size: int = 64,
    ) -> None:
        self.name = name
        self.dev = mtd_device_register(
            name=name,
            size=size,
            mtd_type=MTD_NANDFLASH,
            erasesize=erase_size,
            writesize=page_size,
            oobsize=oob_size,
            flags=MTD_WRITEABLE,
        )


class SimDataFlash:
    """Simulated DataFlash (AT45DBxxx).

    Parameters
    ----------
    name : str
        Device name (default ``"dataflash0"``).
    size : int
        Total flash size (default 8 MiB).
    page_size : int
        Page size (default 528 bytes, includes spare area).

    DataFlash characteristics:
    - Page-based read/write/program
    - Small page sizes (264/528 bytes)
    - Internal SRAM buffers for read/modify/write
    - Used for data logging, small storage
    """

    def __init__(
        self,
        name: str = "dataflash0",
        size: int = 8 * 1024 * 1024,
        page_size: int = 528,
    ) -> None:
        self.name = name
        erase_size = page_size * 8  # typical DataFlash block
        self.dev = mtd_device_register(
            name=name,
            size=size,
            mtd_type=MTD_DATAFLASH,
            erasesize=erase_size,
            writesize=page_size,
            oobsize=0,
            flags=MTD_WRITEABLE,
        )


# ---------------------------------------------------------------------------
# Pretty-printing helpers
# ---------------------------------------------------------------------------

def _format_size(size: int) -> str:
    """Format byte size into human-readable string."""
    if size == 0:
        return "0 B"
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}" if isinstance(size, float) and size != int(size) else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def _print_device_info(dev: MtdInfo) -> None:
    """Print formatted device information."""
    print(f"  Name:          {dev.name}")
    print(f"  Type:          {_MTD_TYPE_NAMES.get(dev.type, 'UNKNOWN')} ({dev.type})")
    print(f"  Flags:         0x{dev.flags:04x} [{_flags_to_str(dev.flags)}]")
    print(f"  Size:          {_format_size(dev.size)} ({dev.size} bytes)")
    print(f"  Erase size:    {_format_size(dev.erasesize)}")
    print(f"  Write size:    {_format_size(dev.writesize)}")
    print(f"  OOB size:      {dev.oobsize} bytes")
    print(f"  OOB available: {dev.oobavail} bytes")
    print(f"  Partitions:    {dev.num_parts}")
    print(f"  Index:         {dev.index}")


def _print_partition_info(part: MtdPart) -> None:
    """Print formatted partition information."""
    print(f"  [{part.index}] {part.name}")
    print(f"      Offset: 0x{part.offset:08x} ({_format_size(part.offset)})")
    print(f"      Size:   {_format_size(part.size)} ({part.size} bytes)")
    print(f"      End:    0x{part.offset + part.size:08x}")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    """Run comprehensive MTD subsystem demonstration."""
    print("=" * 72)
    print("  UmerOS MTD (Memory Technology Device) Framework Demo")
    print("=" * 72)

    # ------------------------------------------------------------------
    # 1. Device creation
    # ------------------------------------------------------------------
    print("\n--- 1. Creating Built-in MTD Devices ---\n")

    nor = SimNorFlash("nor0", size=16 * 1024 * 1024, erase_size=64 * 1024)
    nand = SimNandFlash("nand0", size=256 * 1024 * 1024, page_size=2048, erase_size=128 * 1024, oob_size=64)
    df = SimDataFlash("dataflash0", size=8 * 1024 * 1024, page_size=528)

    print("Created devices:")
    for name in mtd_list_devices():
        dev = mtd_get_device(name)
        print(f"  {name:12s}  {mtd_get_type_string(name):10s}  {_format_size(dev.size):>10s}")

    # ------------------------------------------------------------------
    # 2. Device info
    # ------------------------------------------------------------------
    print("\n--- 2. Device Information ---\n")

    for name in mtd_list_devices():
        dev = mtd_get_device(name)
        print(f"Device: {name}")
        _print_device_info(dev)
        print()

    # ------------------------------------------------------------------
    # 3. Write / Read operations
    # ------------------------------------------------------------------
    print("--- 3. Read / Write Operations ---\n")

    # NOR write
    test_data = b"UmerOS NOR flash test data - Hello from NOR!"
    mtd_write("nor0", 0x1000, test_data)
    read_back = mtd_read("nor0", 0x1000, len(test_data))
    print(f"  NOR:  wrote {len(test_data)} bytes @ 0x1000")
    print(f"  NOR:  read  {len(read_back)} bytes @ 0x1000")
    print(f"  NOR:  data  = {read_back[:40]}")
    print(f"  NOR:  match = {read_back == test_data}")

    # NAND write
    nand_data = b"UmerOS NAND flash test - page-based writes"
    mtd_write("nand0", 0x0000, nand_data)
    nand_read = mtd_read("nand0", 0x0000, len(nand_data))
    print(f"\n  NAND: wrote {len(nand_data)} bytes @ 0x0000")
    print(f"  NAND: read  {len(nand_read)} bytes @ 0x0000")
    print(f"  NAND: data  = {nand_read[:40]}")
    print(f"  NAND: match = {nand_read == nand_data}")

    # DataFlash write
    df_data = b"UmerOS DataFlash test - small pages"
    mtd_write("dataflash0", 0x0000, df_data)
    df_read = mtd_read("dataflash0", 0x0000, len(df_data))
    print(f"\n  DataFlash: wrote {len(df_data)} bytes @ 0x0000")
    print(f"  DataFlash: read  {len(df_read)} bytes @ 0x0000")
    print(f"  DataFlash: data  = {df_read[:40]}")
    print(f"  DataFlash: match = {df_read == df_data}")

    # ------------------------------------------------------------------
    # 4. Erase operations
    # ------------------------------------------------------------------
    print("\n--- 4. Erase Operations ---\n")

    # Write some data, then erase
    mtd_write("nor0", 0x0000, b"Data to be erased")
    before = mtd_read("nor0", 0x0000, 16)
    print(f"  Before erase: {before[:16]}")

    erase_result = mtd_erase("nor0", 0x0000, 64 * 1024)
    after = mtd_read("nor0", 0x0000, 16)
    print(f"  After erase:  {after[:16]}")
    print(f"  Erase result: addr=0x{erase_result.addr:x}, len={erase_result.len}")
    print(f"  Erased to 0xFF: {all(b == 0xFF for b in after)}")

    # NAND erase
    mtd_write("nand0", 0x0000, b"NAND erase test data")
    nand_before = mtd_read("nand0", 0x0000, 20)
    print(f"\n  NAND before erase: {nand_before[:20]}")

    nand_erase = mtd_erase("nand0", 0x0000, 128 * 1024)
    nand_after = mtd_read("nand0", 0x0000, 20)
    print(f"  NAND after erase:  {nand_after[:20]}")
    print(f"  NAND erase result: addr=0x{nand_erase.addr:x}, len={nand_erase.len}")

    # ------------------------------------------------------------------
    # 5. OOB operations
    # ------------------------------------------------------------------
    print("\n--- 5. OOB Operations ---\n")

    oob_data = b"OOB_META\x00CRC32_OK"
    mtd_write_oob("nand0", 0x0000, oob_data)
    oob_read = mtd_read_oob("nand0", 0x0000, len(oob_data))
    print(f"  NAND OOB write: {oob_data}")
    print(f"  NAND OOB read:  {oob_read}")
    print(f"  NAND OOB match: {oob_read == oob_data}")
    print(f"  NAND OOB avail: {mtd_oob_get_available('nand0')} bytes")

    # ------------------------------------------------------------------
    # 6. Bad block management
    # ------------------------------------------------------------------
    print("\n--- 6. Bad Block Management ---\n")

    # Manually mark a bad block
    mtd_block_markbad("nand0", 128 * 1024 * 3)  # block 3
    is_bad = mtd_block_isbad("nand0", 128 * 1024 * 3)
    print(f"  Block @ 0x{128 * 1024 * 3:x} is bad: {is_bad}")

    # Attempt erase on bad block
    try:
        mtd_erase("nand0", 128 * 1024 * 3, 128 * 1024)
        print("  Erase on bad block: succeeded (should not happen)")
    except IOError as e:
        print(f"  Erase on bad block: {e}")

    # Scan all bad blocks
    bad_blocks = mtd_scan_bad_blocks("nand0")
    total_blocks = 256 * 1024 * 1024 // (128 * 1024)
    print(f"\n  Total blocks: {total_blocks}")
    print(f"  Bad blocks:   {len(bad_blocks)}")
    if bad_blocks:
        print(f"  Bad offsets:  {[f'0x{b:x}' for b in bad_blocks[:5]]}{'...' if len(bad_blocks) > 5 else ''}")

    # ------------------------------------------------------------------
    # 7. Partition management
    # ------------------------------------------------------------------
    print("\n--- 7. Partition Management ---\n")

    mtd_add_partition("nand0", "bootloader", 0x0000000, 512 * 1024)
    mtd_add_partition("nand0", "kernel", 0x0080000, 8 * 1024 * 1024)
    mtd_add_partition("nand0", "rootfs", 0x0880000, 64 * 1024 * 1024)
    mtd_add_partition("nand0", "data", 0x4880000, 128 * 1024 * 1024)

    print("  NAND0 partition table:")
    pt = mtd_partition_table("nand0")
    for p in pt.parts:
        _print_partition_info(p)

    # Write to partition
    part_data = b"Bootloader v2.1 - UmerOS"
    mtd_write("nand0", 0x0000000, part_data)
    part_read = mtd_read("nand0", 0x0000000, len(part_data))
    print(f"\n  Written to bootloader partition: {part_data}")
    print(f"  Read back:                       {part_read}")

    # List partitions
    print(f"\n  Partitions on nand0: {mtd_list_partitions('nand0')}")

    # Delete a partition
    mtd_del_partition("nand0", "data")
    print(f"  After deleting 'data': {mtd_list_partitions('nand0')}")

    # ------------------------------------------------------------------
    # 8. Partition overlap detection
    # ------------------------------------------------------------------
    print("\n--- 8. Partition Overlap Detection ---\n")

    try:
        mtd_add_partition("nand0", "overlap_test", 0x0100000, 1 * 1024 * 1024)
        print("  Overlap test: created (should not happen)")
    except ValueError as e:
        print(f"  Overlap test: {e}")

    # ------------------------------------------------------------------
    # 9. Chip info queries
    # ------------------------------------------------------------------
    print("\n--- 9. Chip Info Queries ---\n")

    for name in mtd_list_devices():
        print(f"  {name}:")
        print(f"    Erase size: {_format_size(mtd_get_erasesize(name))}")
        print(f"    Write size: {_format_size(mtd_get_writesize(name))}")
        print(f"    OOB size:   {mtd_get_oobsize(name)} bytes")
        print(f"    Total size: {_format_size(mtd_get_size(name))}")
        print(f"    Writeable:  {mtd_is_writeable(name)}")
        print()

    # ------------------------------------------------------------------
    # 10. Panic write
    # ------------------------------------------------------------------
    print("--- 10. Panic Write ---\n")

    panic_data = b"PANIC: kernel oops at 0xDEADBEEF"
    written = mtd_panic_write("nor0", 0x100000, panic_data)
    read_back = mtd_read("nor0", 0x100000, len(panic_data))
    print(f"  Panic write: {written} bytes @ 0x100000")
    print(f"  Data:        {read_back}")

    # ------------------------------------------------------------------
    # 11. Custom register / unregister
    # ------------------------------------------------------------------
    print("\n--- 11. Custom Device Registration ---\n")

    mtd_device_register("ramdisk0", 4 * 1024 * 1024, MTD_RAM, erasesize=4096, writesize=1, oobsize=0)
    print(f"  Registered ramdisk0: type={mtd_get_type_string('ramdisk0')}, size={_format_size(mtd_get_size('ramdisk0'))}")

    mtd_device_unregister("ramdisk0")
    print(f"  Unregistered ramdisk0")
    print(f"  Remaining devices: {mtd_list_devices()}")

    # ------------------------------------------------------------------
    # 12. Error handling
    # ------------------------------------------------------------------
    print("\n--- 12. Error Handling ---\n")

    try:
        mtd_get_device("nonexistent")
    except KeyError as e:
        print(f"  Get nonexistent: {e}")

    try:
        mtd_device_register("nor0", 1024, MTD_NORFLASH)
    except ValueError as e:
        print(f"  Duplicate register: {e}")

    try:
        mtd_write("nor0", 0, b"test")
        mtd_device_unregister("nor0")
    except Exception:
        pass  # device may have been unregistered already

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("  MTD Framework Demo Complete")
    print("=" * 72)
    print(f"  Devices registered:  {len(mtd_list_devices())}")
    for name in mtd_list_devices():
        dev = mtd_get_device(name)
        bad = len(mtd_scan_bad_blocks(name))
        parts = len(mtd_list_partitions(name))
        print(f"    {name:12s}  {mtd_get_type_string(name):10s}  {_format_size(dev.size):>10s}  bad_blocks={bad}  partitions={parts}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo()
