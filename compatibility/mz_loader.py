"""
Umer OS /compatibility/mz_loader — DOS MZ / EXE parser
======================================================

The oldest Windows executable format, the **MZ** header (named for
the ``MZ`` magic bytes that Mark Zbikowski's linker put at offset
0), was inherited from MS-DOS.  Every modern Windows PE binary
*still* starts with an MZ header that contains a small DOS stub
program -- when you run a PE binary on DOS, the stub runs and prints
"This program cannot be run in DOS mode".

This module:

* parses the MZ header (also called the **IMAGE_DOS_HEADER** in
  Microsoft's terms);
* supports the *real* MZ-only DOS executables (Windows 3.0's
  ``KRNL386.EXE`` and friends, 16-bit Windows 1/2/3);
* exposes the offset of the **PE header** (or the NE / LE / LX
  header, for the older 16-bit / VXD formats) so the higher-level
  PE / NE loaders can take over;
* handles the *stub program* bytes (raw MZ payload after the
  header) opaquely -- we don't disassemble the stub, we just expose
  the raw bytes.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#the-dos-header-still-required
* https://wiki.osdev.org/MZ
* https://en.wikipedia.org/wiki/DOS_EXE

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("UmerOS.MZ")


#: Offset of the ``e_lfanew`` field -- the file offset of the
#: next-header pointer (PE / NE / LE / LX).
LFANEW_OFFSET = 0x3C

#: Magic value at offset 0.
MZ_MAGIC = b"MZ"

#: A few of the well-known next-header sigs we recognise.
PE_SIG = b"PE\0\0"
NE_SIG = b"NE"
LE_SIG = b"LE"
LX_SIG = b"LX"


@dataclass
class MzHeader:
    """The IMAGE_DOS_HEADER (subset) plus a few convenience helpers.

    The full ``IMAGE_DOS_HEADER`` is 64 bytes; we expose only the
    fields a loader or auditor needs.
    """

    e_magic: bytes
    e_cblp: int            # bytes on last page
    e_cp: int              # pages in file
    e_crlc: int            # relocations
    e_cparhdr: int         # header size in paragraphs (16-byte units)
    e_minalloc: int        # min extra paragraphs
    e_maxalloc: int        # max extra paragraphs
    e_ss: int              # initial SS
    e_sp: int              # initial SP
    e_csum: int            # checksum
    e_ip: int              # initial IP
    e_cs: int              # initial CS
    e_lfarlc: int          # relocations file offset
    e_ovno: int            # overlay number
    e_oemid: int           # OEM id
    e_oeminfo: int         # OEM info
    e_lfanew: int           # next-header offset (PE / NE / LE / LX)

    # -- raw bytes -------------------------------------------------------
    raw: bytes = b""

    # -- extras ----------------------------------------------------------
    relocations: list = field(default_factory=list)
    next_signature: bytes = b""
    next_header: Optional[bytes] = None
    next_header_offset: int = 0

    @property
    def is_mz(self) -> bool:
        return self.e_magic == MZ_MAGIC

    @property
    def next_type(self) -> str:
        """Return one of ``"PE"`` / ``"NE"`` / ``"LE"`` / ``"LX"`` / ``"MZ"``."""
        if self.next_signature == PE_SIG:
            return "PE"
        if self.next_signature == NE_SIG:
            return "NE"
        if self.next_signature == LE_SIG:
            return "LE"
        if self.next_signature == LX_SIG:
            return "LX"
        return "MZ"


_FMT = ("<28x"     # e_magic .. e_oeminfo are 28 bytes at offset 0
       "H")        # e_lfanew at offset 0x3C


def parse_mz_header(data: bytes, *, base: int = 0) -> MzHeader:
    """Parse the IMAGE_DOS_HEADER at ``data[base:]``.

    Args:
        data: raw file bytes.
        base: byte offset where the header starts (default 0).

    Returns:
        A populated :class:`MzHeader`.

    Raises:
        ValueError: on truncation or bad magic.
    """
    if base + LFANEW_OFFSET + 2 > len(data):
        raise ValueError(
            f"data is too short to contain an MZ header "
            f"({len(data) - base} bytes at offset {base})"
        )
    e_magic = data[base:base + 2]
    if e_magic != MZ_MAGIC:
        raise ValueError(f"not an MZ file: magic={e_magic!r}")
    # Parse the historical MZ layout.  The 30 bytes of e_cblp..e_oeminfo
    # are 15 little-endian 16-bit fields, but we just need the scalars
    # at the well-known offsets, so read them individually.
    def u16(off: int) -> int:
        return struct.unpack_from("<H", data, base + off)[0]
    def u32(off: int) -> int:
        return struct.unpack_from("<I", data, base + off)[0]

    e_cblp      = u16(2)
    e_cp        = u16(4)
    e_crlc      = u16(6)
    e_cparhdr   = u16(8)
    e_minalloc  = u16(10)
    e_maxalloc  = u16(12)
    e_ss        = u16(14)
    e_sp        = u16(16)
    e_csum      = u16(18)
    e_ip        = u16(20)
    e_cs        = u16(22)
    e_lfarlc    = u16(24)
    e_ovno      = u16(26)
    e_oemid     = u16(28)
    e_oeminfo   = u16(30)
    e_lfanew    = u32(0x3C)
    hdr = MzHeader(
        e_magic=e_magic,
        e_cblp=struct.unpack_from("<H", data, base + 2)[0],
        e_cp=struct.unpack_from("<H", data, base + 4)[0],
        e_crlc=struct.unpack_from("<H", data, base + 6)[0],
        e_cparhdr=struct.unpack_from("<H", data, base + 8)[0],
        e_minalloc=struct.unpack_from("<H", data, base + 10)[0],
        e_maxalloc=struct.unpack_from("<H", data, base + 12)[0],
        e_ss=struct.unpack_from("<H", data, base + 14)[0],
        e_sp=struct.unpack_from("<H", data, base + 16)[0],
        e_csum=struct.unpack_from("<H", data, base + 18)[0],
        e_ip=struct.unpack_from("<H", data, base + 20)[0],
        e_cs=struct.unpack_from("<H", data, base + 22)[0],
        e_lfarlc=struct.unpack_from("<H", data, base + 24)[0],
        e_ovno=struct.unpack_from("<H", data, base + 26)[0],
        e_oemid=struct.unpack_from("<H", data, base + 28)[0],
        e_oeminfo=struct.unpack_from("<H", data, base + 30)[0],
        e_lfanew=e_lfanew,
        raw=data,
    )

    # --- relocations ----------------------------------------------------
    reloc_offs = base + hdr.e_lfarlc
    n = hdr.e_crlc
    if reloc_offs + 4 * n <= len(data):
        relocs = []
        for i in range(n):
            off, seg = struct.unpack_from("<HH", data, reloc_offs + i * 4)
            relocs.append((seg, off))
        hdr.relocations = relocs

    # --- next-header (PE / NE / LE / LX) -------------------------------
    if base + hdr.e_lfanew + 4 <= len(data):
        off = base + hdr.e_lfanew
        hdr.next_header_offset = off
        sig = data[off:off + 4]
        hdr.next_signature = sig
        # Pull up to 256 bytes so callers can do their own parsing.
        hdr.next_header = data[off:off + 256]
    return hdr


def _selftest() -> bool:
    """Round-trip a synthetic MZ header."""
    # 1. Minimal header: 64 bytes of zero except e_magic='MZ' and
    #    e_lfanew=0x40 (just past the header).
    data = bytearray(b"MZ" + b"\x00" * 58)
    data[0x3C:0x40] = (0x40).to_bytes(4, "little")
    # Add a fake PE signature at offset 0x40.
    data += b"PE\x00\x00\x00\x00"
    hdr = parse_mz_header(bytes(data))
    if not hdr.is_mz:
        return False
    if hdr.e_lfanew != 0x40:
        return False
    if hdr.next_type != "PE":
        return False
    if hdr.next_header != b"PE\x00\x00\x00\x00":
        return False
    # 2. Truncated data should raise.
    try:
        parse_mz_header(b"MZ" + b"\x00" * 8)
    except ValueError:
        pass
    else:
        return False
    # 3. Bad magic should raise.
    try:
        parse_mz_header(b"XX" + b"\x00" * 64)
    except ValueError:
        pass
    else:
        return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    sys.exit(0 if _selftest() else 1)
