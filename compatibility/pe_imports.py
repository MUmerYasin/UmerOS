"""
Umer OS /compatibility/pe_imports — Import Directory parser
=========================================================

The **Import Address Table** (IAT) of a PE binary is built from the
*Import Directory* located in the data directory at index 1.  The
directory is a sequence of ``IMAGE_IMPORT_DESCRIPTOR`` entries, one
per imported DLL; the array is terminated by a zero-filled entry::

    typedef struct _IMAGE_IMPORT_DESCRIPTOR {
        union {
            DWORD Characteristics;            // 0 if not ordinal
            DWORD OriginalFirstThunk;         // RVA -> INT (Import Name Table)
        } DUMMYUNIONNAME;
        DWORD TimeDateStamp;                   // 0 if not bound,
                                               // -1 if bound + real
                                               // timestamp
        DWORD ForwarderChain;                 // -1 if no forwarder
        DWORD Name;                            // RVA -> DLL name (ASCII)
        DWORD FirstThunk;                      // RVA -> IAT (will be
                                               // rewritten at load time)
    } IMAGE_IMPORT_DESCRIPTOR;
    // 20 bytes per entry.

For each entry, the loader:

* resolves the DLL by name (case-insensitive on Windows),
* walks the *Import Name Table* (a parallel array of 32-bit
  integers pointing at ``IMAGE_IMPORT_BY_NAME`` records or ordinals),
* writes the resolved function address into the *Import Address
  Table* (the slot pointed at by ``FirstThunk``).

This module parses the directory and yields structured
:class:`ImportedDll` records with the resolved-by-name function
list.  It does *not* perform relocation (that's :mod:`pe_relocations`).

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#import-directory-table
* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#import-name-table
* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#import-lookup-table

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional

from .pe_loader import PeFile


# Size of IMAGE_IMPORT_DESCRIPTOR.
_IMPORT_DESC_SIZE = 20

#: ``ORIGINAL_FIRST_THUNK`` / ``FIRST_THUNK`` value indicating
#: the entry is a *by-ordinal* import (high bit set).
IMPORT_ORDINAL_FLAG = 0x80000000
#: Mask to extract the 16-bit ordinal value.
IMPORT_ORDINAL_MASK = 0x0000FFFF


@dataclass
class ImportedSymbol:
    """One imported function (or ordinal) from a single DLL."""

    name: Optional[str]            # human-readable name (or None for ordinal)
    ordinal: int                  # 16-bit ordinal (always present)
    hint: int                     # export-table hint (0 if absent)
    is_ordinal_only: bool         # True if no name was emitted

    def __str__(self) -> str:
        if self.is_ordinal_only:
            return f"ord({self.ordinal})"
        return f"{self.name} (ord {self.ordinal})"


@dataclass
class ImportedDll:
    """A single DLL entry in the Import Directory Table."""

    name: str
    original_first_thunk: int      # RVA
    time_date_stamp: int
    forwarder_chain: int
    first_thunk: int               # RVA
    symbols: List[ImportedSymbol] = field(default_factory=list)

    @property
    def symbol_count(self) -> int:
        return len(self.symbols)


def parse_imports(pe: PeFile) -> List[ImportedDll]:
    """Parse the Import Directory Table of ``pe``.

    Args:
        pe: a parsed :class:`PeFile`.

    Returns:
        A list of :class:`ImportedDll` records (one per imported DLL).
        Returns an empty list if the import directory is absent.
    """
    dd = pe.get_data_directory(1)   # 1 = DataDirectoryId.IMPORT
    if dd is None or not dd.is_present:
        return []

    dlls: List[ImportedDll] = []
    # Each directory entry is 20 bytes; the table is zero-terminated.
    off = pe.rva_to_offset(dd.virtual_address)[0]
    for _ in range(dd.size // _IMPORT_DESC_SIZE + 1):
        if off + _IMPORT_DESC_SIZE > len(pe.raw):
            break
        raw = pe.raw[off:off + _IMPORT_DESC_SIZE]
        (oft_or_char, tds, fwd, name_rva, first_thunk) = struct.unpack_from(
            "<IIIII", raw, 0,
        )
        if oft_or_char == 0 and name_rva == 0 and first_thunk == 0:
            break    # terminator
        # DLL name
        try:
            name_off, avail = pe.rva_to_offset(name_rva)
            name = _read_cstring(pe.raw, name_off, avail)
        except ValueError:
            name = "<unresolvable>"

        # Import Name Table (the *original* one, if present; else
        # the IAT itself acts as the lookup table after loader fixup).
        int_rva = oft_or_char or first_thunk
        symbols: List[ImportedSymbol] = []
        if int_rva:
            try:
                int_off, avail = pe.rva_to_offset(int_rva)
                cursor = int_off
                while True:
                    if cursor + 4 > int_off + avail:
                        break
                    entry = struct.unpack_from("<I", pe.raw, cursor)[0]
                    if entry == 0:
                        break
                    cursor += 4
                    if entry & IMPORT_ORDINAL_FLAG:
                        ordinal = entry & IMPORT_ORDINAL_MASK
                        symbols.append(ImportedSymbol(
                            name=None, ordinal=ordinal,
                            hint=0, is_ordinal_only=True,
                        ))
                    else:
                        # By-name: 2-byte hint + ASCII name.
                        try:
                            ent_off, ent_avail = pe.rva_to_offset(entry)
                        except ValueError:
                            continue
                        if ent_off + 2 > len(pe.raw):
                            continue
                        hint = struct.unpack_from("<H", pe.raw, ent_off)[0]
                        sym_name = _read_cstring(
                            pe.raw, ent_off + 2,
                            len(pe.raw) - ent_off - 2,
                        )
                        symbols.append(ImportedSymbol(
                            name=sym_name, ordinal=hint,
                            hint=hint, is_ordinal_only=False,
                        ))
            except ValueError:
                pass

        dlls.append(ImportedDll(
            name=name,
            original_first_thunk=oft_or_char,
            time_date_stamp=tds,
            forwarder_chain=fwd,
            first_thunk=first_thunk,
            symbols=symbols,
        ))
        off += _IMPORT_DESC_SIZE
    return dlls


def _read_cstring(data: bytes, off: int, max_len: int) -> str:
    """Read a NUL-terminated ASCII string at ``off`` (bounded by max_len)."""
    end = off
    limit = min(off + max_len, len(data))
    while end < limit and data[end] != 0:
        end += 1
    return data[off:end].decode("ascii", errors="replace")


def _selftest() -> bool:
    """Verify the import parser: a PE with no import directory
    should return an empty list."""
    from .pe_loader import _build_fake_pe
    pe = PeFile.from_bytes(_build_fake_pe())
    if parse_imports(pe) != []:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
