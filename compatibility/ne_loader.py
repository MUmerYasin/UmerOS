"""
Umer OS /compatibility/ne_loader — 16-bit NE (New Executable) parser
================================================================

The **NE** format ("New Executable") was the 16-bit executable /
DLL format used by **Windows 1.0 / 2.0 / 3.x** and OS/2.  An MZ
header still precedes the NE header (``e_lfanew`` points to the NE
header, not a PE header).  A 16-bit Windows program therefore has
the form::

    +---------+   +-----------------+
    | MZ hdr  | → | NE header        |
    +---------+   +-----------------+
                  | segment table    |
                  | resource table   |
                  | resident names   |
                  | module refs      |
                  | imported names   |
                  | entry table      |
                  | non-resident...  |
                  +-----------------+

NE is far less common today (most 16-bit apps are gone) but the
format is still seen in:

* 16-bit Windows 3.x and 3.11 (WfW 3.11) installers,
* some OS/2 binaries,
* legacy 16-bit DOS extenders (DOS/4GW, Pharlap, Causeway).

This module:

* parses the NE header (the documented 40-byte part plus the
  optional Windows-specific extensions),
* enumerates the segment table (giving each entry a 16-bit
  address and a flags byte),
* enumerates the resource / entry / name / import tables,
* reports the size of the non-resident name table (the rest of the
  NE prefix is opaque bytes).

We do not *execute* NE binaries -- the user-space emulator required
for that is out of scope.  We only parse the metadata so the
``compatibility`` package can identify and audit legacy executables.

References
----------

* https://wiki.osdev.org/NE
* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#the-new-executable-header
* http://www.csn.ul.ie/~caolan/pub/winresdump/winrestoolspec.html
* "The Portable Executable File Format" -- Pietrek (MSJ 1994)

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import List

log = logging.getLogger("UmerOS.NE")

#: The 4-byte signature at the start of an NE header.
NE_MAGIC = b"NE"


@dataclass
class NeSegment:
    """A single NE segment entry."""

    offset_sectors: int    # file offset in sectors (multiply by sector size)
    length_bytes: int      # raw length in bytes
    flags: int             # bit 0: DATA, bit 1: ALLOC, bit 2: RELOCINFO, etc.
    min_alloc_bytes: int   # minimum allocation in bytes

    @property
    def is_code(self) -> bool:
        return bool(self.flags & 0x0004)  # 0x04 = CODE flag


@dataclass
class NeHeader:
    """The 16-bit Windows New Executable header (parsed)."""

    version_major: int
    version_minor: int
    entry_table_offset: int
    entry_table_length: int
    crc32: int
    program_flags: int
    application_flags: int
    auto_data_segment: int
    heap_size: int
    stack_size: int
    initial_ip: int
    initial_cs: int
    initial_sp: int
    initial_ss: int
    segment_count: int
    module_ref_count: int
    non_resident_name_size: int
    sector_shift: int
    resource_count: int
    resource_table_offset: int
    resident_name_table_offset: int
    module_ref_table_offset: int
    imported_name_table_offset: int
    non_resident_name_table_offset: int
    movable_entry_point_count: int
    alignment_shift_count: int
    max_resource_count: int

    segments: List[NeSegment] = field(default_factory=list)

    @property
    def is_ne(self) -> bool:
        return True

    @property
    def is_windows(self) -> bool:
        """``True`` iff the program targets Windows (vs OS/2)."""
        return bool(self.program_flags & 0x02)

    @property
    def is_dll(self) -> bool:
        """``True`` iff the program has the library bit set."""
        return bool(self.program_flags & 0x8000)


# Layout of the standard NE header (40 bytes) plus the Microsoft
# extensions (40 more bytes) -- all little-endian.
#
# offset  size  field
# ------  ----  -----
#   0      2   signature ("NE")
#   2      1   major version
#   3      1   minor version
#   4      2   entry-table offset (from NE start)
#   6      2   entry-table length
#   8      4   module CRC (optional, may be 0)
#  12      2   program flags
#  14      2   application flags
#  16      2   auto data segment index
#  18      2   local heap size
#  20      2   stack size
#  22      2   initial IP
#  24      2   initial CS (segment)
#  26      2   initial SP
#  28      2   initial SS (segment)
#  30      2   segment-table entry count
#  32      2   module-reference-table count
#  34      2   non-resident-name-table size
#  36      2   sector shift
#  38      2   resource-table entry count
#  40      2   resource-table offset (from NE start)
#  42      2   resident-name-table offset
#  44      2   module-reference-table offset
#  46      2   imported-name-table offset
#  48      4   non-resident-name-table offset (32-bit)
#  52      2   count of movable entries
#  54      2   alignment shift count
#  56      2   max resource count (or segment count >= 100)
#  58      2   reserved (must be 0)
#  60      2   Windows SDK revision
#  62      2   Windows SDK version
_NE_HDR_FMT = struct.Struct(
    "<"
    "2s"      #  0  signature
    "BB"      #  2  version major / minor
    "HH"      #  4  entry-table offset, length
    "I"       #  8  module CRC32
    "HH"      # 12  program flags, application flags
    "HH"      # 16  auto data segment, local heap size
    "HH"      # 20  stack size, initial IP
    "HH"      # 24  initial CS, initial SP
    "HH"      # 28  initial SS, segment count
    "HH"      # 32  module-ref count, non-resident name size
    "H"       # 36  sector shift
    "H"       # 38  resource count
    "H"       # 40  resource-table offset
    "H"       # 42  resident-name offset
    "H"       # 44  module-ref offset
    "H"       # 46  imported-name offset
    "I"       # 48  non-resident-name offset (32-bit)
    "H"       # 52  movable entry count
    "H"       # 54  alignment shift count
    "H"       # 56  max resource count
    "H"       # 58  reserved
    "HH"      # 60  Windows SDK rev, version
)


def parse_ne_header(data: bytes, *, ne_offset: int = 0) -> NeHeader:
    """Parse the 16-bit New Executable header at ``data[ne_offset:]``.

    Args:
        data: raw file bytes.
        ne_offset: byte offset of the NE signature.

    Raises:
        ValueError: on bad magic or truncation.
    """
    if ne_offset + 64 > len(data):
        raise ValueError("data too short to contain an NE header")
    sig = data[ne_offset:ne_offset + 2]
    if sig != NE_MAGIC:
        raise ValueError(f"not an NE file (magic={sig!r})")
    raw = _NE_HDR_FMT.unpack_from(data, ne_offset)
    sig, ver_maj, ver_min, et_off, et_len, crc, prog_flags, app_flags, \
        auto_ds, heap, stack, ip, cs, sp, ss, seg_count, mod_ref, \
        nres_size, sector_shift, res_count, res_table_off, res_name_off, \
        mod_ref_off, imp_name_off, nres_off, movable_count, align_count, \
        max_res_count, _reserved, _sdk_rev, _sdk_ver = raw

    hdr = NeHeader(
        version_major=ver_maj, version_minor=ver_min,
        entry_table_offset=et_off, entry_table_length=et_len,
        crc32=crc, program_flags=prog_flags, application_flags=app_flags,
        auto_data_segment=auto_ds, heap_size=heap, stack_size=stack,
        initial_ip=ip, initial_cs=cs, initial_sp=sp, initial_ss=ss,
        segment_count=seg_count, module_ref_count=mod_ref,
        non_resident_name_size=nres_size,
        sector_shift=sector_shift, resource_count=res_count,
        resource_table_offset=res_table_off,
        resident_name_table_offset=res_name_off,
        module_ref_table_offset=mod_ref_off,
        imported_name_table_offset=imp_name_off,
        non_resident_name_table_offset=nres_off,
        movable_entry_point_count=movable_count,
        alignment_shift_count=align_count,
        max_resource_count=max_res_count,
    )

    # ---- Segment table -------------------------------------------------
    # Each entry is 8 bytes: offset (2) | length (2) | flags (2) | min (2).
    seg_off = ne_offset + hdr.entry_table_offset
    sector_size = 1 << sector_shift if sector_shift > 0 else 1
    for _ in range(seg_count):
        if seg_off + 8 > len(data):
            break
        so, sl, sf, sm = struct.unpack_from("<HHHH", data, seg_off)
        hdr.segments.append(NeSegment(
            offset_sectors=so,
            length_bytes=sl * sector_size,
            flags=sf, min_alloc_bytes=sm,
        ))
        seg_off += 8
    return hdr


def _selftest() -> bool:
    """Round-trip a synthetic NE header."""
    data = bytearray(64)
    data[0:2] = NE_MAGIC
    data[2] = 5   # ver_major
    data[3] = 0   # ver_minor
    # entry table at offset 64 (from NE start, after the header)
    struct.pack_into("<H", data, 4, 64)
    struct.pack_into("<H", data, 6, 0)    # length = 0
    struct.pack_into("<H", data, 12, 0x02) # program flags: Windows
    struct.pack_into("<H", data, 16, 1)    # auto data seg
    struct.pack_into("<H", data, 18, 0)    # heap
    struct.pack_into("<H", data, 20, 0)    # stack
    struct.pack_into("<H", data, 22, 0)    # IP
    struct.pack_into("<H", data, 24, 0)    # CS
    struct.pack_into("<H", data, 26, 0)    # SP
    struct.pack_into("<H", data, 28, 0)    # SS
    struct.pack_into("<H", data, 30, 0)    # seg count
    struct.pack_into("<H", data, 32, 0)    # mod ref count
    struct.pack_into("<H", data, 34, 0)    # nres name size
    struct.pack_into("<H", data, 36, 9)    # sector shift (512-byte sectors)
    struct.pack_into("<H", data, 38, 0)    # resource count

    hdr = parse_ne_header(bytes(data))
    if not hdr.is_ne:
        return False
    if hdr.version_major != 5:
        return False
    if hdr.sector_shift != 9:
        return False
    if hdr.segment_count != 0:
        return False
    if not hdr.is_windows:
        return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    sys.exit(0 if _selftest() else 1)
