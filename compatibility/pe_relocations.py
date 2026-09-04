"""
Umer OS /compatibility/pe_relocations — Base Relocation Table
===========================================================

When a PE image is *not* loaded at its preferred ``ImageBase`` the
loader must patch every absolute pointer in the image.  The list
of pointers to patch lives in the **Base Relocation Table** at
data-directory index 5.

The table is a sequence of **blocks**; each block covers a 4-KiB
region of the image and is described by a header followed by a
list of 16-bit entries::

    typedef struct _IMAGE_BASE_RELOCATION {
        DWORD VirtualAddress;     // RVA of the page this block covers
        DWORD SizeOfBlock;        // total block size (incl. this hdr)
        WORD  TypeOffset[];       // (high 4 bits) type, (low 12 bits)
                                  // offset within the page
    } IMAGE_BASE_RELOCATION;
    // Each header is 8 bytes; each entry is 2 bytes.

Common relocation types::

    IMAGE_REL_BASED_ABSOLUTE         0  (a no-op padding entry)
    IMAGE_REL_BASED_HIGHLOW         3  (32-bit absolute)
    IMAGE_REL_BASED_DIR64           10 (64-bit absolute)
    IMAGE_REL_BASED_HIGH            1
    IMAGE_REL_BASED_LOW             2
    IMAGE_REL_BASED_HIGHADJ         4

This module parses the table and yields structured records.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#the-reloc-section-image-only

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List

from .pe_loader import PeFile


#: Relocation types (subset).
class RelocType:
    ABSOLUTE = 0
    HIGH = 1
    LOW = 2
    HIGHLOW = 3
    HIGHADJ = 4
    DIR64 = 10
    # MIPS, IA64, ARM variants omitted (not needed for the Win32 ABI).


@dataclass
class RelocEntry:
    """A single (page-offset, type) entry."""

    rva: int           # the absolute RVA to patch
    type: int          # one of :class:`RelocType`


@dataclass
class RelocBlock:
    """A single Base Relocation block (one 4-KiB page)."""

    page_rva: int
    entries: List[RelocEntry] = field(default_factory=list)


@dataclass
class RelocationTable:
    blocks: List[RelocBlock] = field(default_factory=list)

    @property
    def entry_count(self) -> int:
        return sum(len(b.entries) for b in self.blocks)


def parse_relocations(pe: PeFile) -> RelocationTable:
    """Parse the Base Relocation Table of ``pe``.

    Returns an empty :class:`RelocationTable` if the table is absent.
    """
    dd = pe.get_data_directory(5)   # 5 = DataDirectoryId.BASERELOC
    if dd is None or not dd.is_present:
        return RelocationTable()

    table = RelocationTable()
    off, _ = pe.rva_to_offset(dd.virtual_address)
    end = off + dd.size
    while off + 8 <= end and off + 8 <= len(pe.raw):
        page_rva, size = struct.unpack_from("<II", pe.raw, off)
        if size < 8:
            break
        n_entries = (size - 8) // 2
        block = RelocBlock(page_rva=page_rva)
        for j in range(n_entries):
            type_off = struct.unpack_from(
                "<H", pe.raw, off + 8 + j * 2,
            )[0]
            rtype = (type_off >> 12) & 0xF
            raddr = type_off & 0xFFF
            if rtype != RelocType.ABSOLUTE:
                block.entries.append(RelocEntry(
                    rva=page_rva + raddr, type=rtype,
                ))
        table.blocks.append(block)
        off += size
    return table


def _selftest() -> bool:
    """Verify with a PE that has no relocations."""
    from .pe_loader import _build_fake_pe
    pe = PeFile.from_bytes(_build_fake_pe())
    table = parse_relocations(pe)
    return table.entry_count == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
