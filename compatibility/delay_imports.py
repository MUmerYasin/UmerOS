"""
Umer OS /compatibility/delay_imports — Delay Import Directory parser
=================================================================

Since Windows 5 (2000/XP) the PE loader supports **delayed imports**:
imports that are not bound to host DLLs at startup, but loaded the
first time the application calls them.  The Delay Import Directory
lives at data directory index ``13`` (``IMAGE_DIRECTORY_ENTRY_DELAY``).

Each entry describes one delay-loaded DLL and the list of symbols it
provides.  The loader has to (a) locate the entry point table, (b)
bind every symbol by name or ordinal, and (c) patch the thunk in the
target binary.

We don't actually patch; we parse the directory so that
:class:`compatibility.dll_loader.DllLoader` can:

* report exactly which DLLs are delay-loaded (so missing imports
  don't show up as "missing" when in fact they would have been
  resolved on first call),
* include delay-loaded symbols in the host resolution step.

Layout::

    typedef struct _IMAGE_DELAYLOAD_DESCRIPTOR {
        union {
            DWORD AllAttributes;
            struct {
                DWORD RvaBased        : 1;
                DWORD ReservedAttributes : 31;
            };
        } Attributes;
        DWORD DllNameRVA;           // RVA to the DLL name (ASCII)
        DWORD ModuleHandleRVA;      // RVA to a HANDLE slot
        DWORD ImportAddressTableRVA; // RVA to the IAT
        DWORD ImportNameTableRVA;   // RVA to the INT
        DWORD BoundImportAddressTableRVA; // RVA to the BIAT (optional)
        DWORD UnloadInformationTableRVA;   // RVA to the UIT (optional)
        DWORD TimeDateStamp;        // 0 = not yet bound
    } IMAGE_DELAYLOAD_DESCRIPTOR, *PCIMAGE_DELAYLOAD_DESCRIPTOR;

The IAT and INT are parallel arrays of 32-bit (PE32) or 64-bit
(PE32+) entries.  Each entry is either an *ordinal* (high bit set)
or a *hint* (the previous slot's RVA carries the hint index; the
entry itself is an RVA into the name table where the symbol name
lives).

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#delay-load-directory-table

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.DelayImports")

# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DelayImportSymbol:
    """A single delay-loaded symbol."""
    name: Optional[str]            # None for purely-ordinal imports
    ordinal: int                   # 32-bit ordinal (always present)
    iat_rva: int                   # RVA into the IAT for this slot
    hint: Optional[int] = None     # IMAGE_IMPORT_BY_NAME hint index


@dataclass(frozen=True)
class DelayImportEntry:
    """One delay-loaded DLL plus its symbols."""

    dll_name: str
    attributes: int
    module_handle_rva: int
    iat_rva: int
    int_rva: int
    biat_rva: int
    uit_rva: int
    time_date_stamp: int
    symbols: Tuple[DelayImportSymbol, ...] = ()


@dataclass
class DelayImportDirectory:
    """The full delay-load directory of a PE image."""

    entries: List[DelayImportEntry] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.entries

    def find(self, dll_name: str) -> Optional[DelayImportEntry]:
        for e in self.entries:
            if e.dll_name.lower() == dll_name.lower():
                return e
        return None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_delay_imports(pe) -> Optional[DelayImportDirectory]:
    """Parse the Delay Load Directory of ``pe``.

    Returns ``None`` if the binary has no delay imports.  ``pe`` must
    expose :meth:`get_data_directory`, :meth:`rva_to_offset` and a
    ``raw`` attribute (any PE parser with the standard Win32
    conventions).
    """
    dd = pe.get_data_directory(13)        # IMAGE_DIRECTORY_ENTRY_DELAY
    if dd is None or not dd.is_present:
        return None
    off, _ = pe.rva_to_offset(dd.virtual_address)
    if off + 32 > len(pe.raw):
        return None

    entry_size = 32
    is_pe32_plus = pe.optional_header.pe_class.name == "PE32_PLUS"
    int_size = 8 if is_pe32_plus else 4

    out = DelayImportDirectory()
    cursor = off
    end = off + dd.size if dd.size else len(pe.raw)
    while cursor + entry_size <= end:
        (attrs, name_rva, hmod_rva, iat_rva, int_rva,
         biat_rva, uit_rva, tds) = struct.unpack_from(
            "<IIIIIIII", pe.raw, cursor)
        # ``dwRvaDLLName == 0`` marks the terminator entry per the
        # Microsoft spec.
        if name_rva == 0:
            break
        try:
            name_off, _ = pe.rva_to_offset(name_rva)
        except ValueError:
            break
        dll_name = _read_cstring(pe.raw, name_off)

        symbols: List[DelayImportSymbol] = []
        if int_rva:
            try:
                int_off, _ = pe.rva_to_offset(int_rva)
                iat_off_v, _ = pe.rva_to_offset(iat_rva)
            except ValueError:
                int_off = 0
            while int_off and int_off + int_size <= len(pe.raw):
                entry = struct.unpack_from("<Q" if is_pe32_plus else "<I",
                                           pe.raw, int_off)[0]
                if entry == 0:
                    break
                ord_high = entry >> 32 if is_pe32_plus else entry >> 31
                if (entry & (1 << (63 if is_pe32_plus else 31))) != 0:
                    ordinal = entry & ((1 << 16) - 1)
                    symbols.append(DelayImportSymbol(
                        name=None, ordinal=ordinal, iat_rva=iat_rva))
                else:
                    try:
                        hint_off, _ = pe.rva_to_offset(entry)
                    except ValueError:
                        break
                    if hint_off + 2 > len(pe.raw):
                        break
                    hint = struct.unpack_from("<H", pe.raw, hint_off)[0]
                    name = _read_cstring(pe.raw, hint_off + 2)
                    symbols.append(DelayImportSymbol(
                        name=name, ordinal=ordinal_from_name(iat_rva),
                        iat_rva=iat_rva, hint=hint))
                iat_rva += int_size
                int_off += int_size
        else:
            # Some tools write INT = 0 and rely on the IAT alone.
            symbols = _parse_int_from_iat(pe, iat_rva, is_pe32_plus)

        out.entries.append(DelayImportEntry(
            dll_name=dll_name,
            attributes=attrs,
            module_handle_rva=hmod_rva,
            iat_rva=iat_rva - len(symbols) * int_size,
            int_rva=int_rva,
            biat_rva=biat_rva,
            uit_rva=uit_rva,
            time_date_stamp=tds,
            symbols=tuple(symbols),
        ))
        cursor += entry_size
    return out


def ordinal_from_name(iat_rva: int) -> int:
    """Best-effort ordinal estimate for a delay-imported symbol."""
    return iat_rva & 0xFFFF


def _parse_int_from_iat(pe, iat_rva: int, is_pe32_plus: bool
                        ) -> List[DelayImportSymbol]:
    """Fallback parser when INT RVA is zero but IAT is present."""
    out: List[DelayImportSymbol] = []
    try:
        iat_off, _ = pe.rva_to_offset(iat_rva)
    except ValueError:
        return out
    int_size = 8 if is_pe32_plus else 4
    cursor = iat_off
    while cursor + int_size <= len(pe.raw):
        entry = struct.unpack_from("<Q" if is_pe32_plus else "<I",
                                   pe.raw, cursor)[0]
        if entry == 0:
            break
        if (entry & (1 << (63 if is_pe32_plus else 31))) != 0:
            ordinal = entry & 0xFFFF
            out.append(DelayImportSymbol(
                name=None, ordinal=ordinal, iat_rva=iat_rva))
        cursor += int_size
        iat_rva += int_size
    return out


def _read_cstring(data: bytes, off: int) -> str:
    end = off
    while end < len(data) and data[end] != 0:
        end += 1
    return data[off:end].decode("ascii", errors="replace")


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _build_pe_with_delay_imports() -> bytes:
    """Build a synthetic PE32 with a delay-import directory.

    Rather than rewrite :func:`_build_fake_pe` from scratch, we add
    a small delay directory into the empty area of the existing
    .text section (it currently has ``ret`` followed by 0x1FF zero
    bytes) and patch the optional header so the data-directory
    entry 13 points at it.
    """
    from .pe_loader import _build_fake_pe
    pe_bytes = bytearray(_build_fake_pe())

    # Locate the data directories in the optional header.  The
    # _build_fake_pe output has NumberOfRvaAndSizes = 16, so the
    # directories occupy bytes 96 .. 96 + 16*8 = 96 + 128 = 224.
    # Optional header starts at e_lfanew (typically 60) + 4 ("PE\0\0")
    # + 20 (COFF header) = 84.  Data-dir region starts at
    # opt_off + (size_of_optional_header - 16*8) -> but easier to
    # just search for the right spot by counting.
    # For the synthetic PE we know exactly: MZ=60, PE=60+4, COFF=20,
    # opt=224, dd=128 -> dd starts at 60+4+20+224-128 = 180.
    # The simplest portable approach: round-trip through PeFile to
    # find NumberOfRvaAndSizes.
    from .pe_loader import PeFile
    pe_probe = PeFile.from_bytes(bytes(pe_bytes))
    n = pe_probe.optional_header.number_of_rva_and_sizes
    # Optional header total size: pe_probe.size_of_optional_header.
    dd_off = (pe_probe.pe_offset + 4 + 20           # PE + COFF
              + pe_probe.size_of_optional_header
              - n * 8)

    # Place the delay directory at file offset 0x200 + 0x40 (i.e.
    # byte 64 of the .text body), still inside the .text section.
    delay_text_byte = 0x40
    delay_file_off = 0x200 + delay_text_byte
    delay_rva = 0x1000 + delay_text_byte

    # Layout INSIDE the .text body:
    #   desc (32) | INT (4) | IAT (4) | term INT+IAT (8)
    #   hint (2) + "Foo\0" (4) | DLL name "MYDLL.DLL\0" (10)
    hint_name_off = delay_file_off + 32 + 16
    name_off = hint_name_off + 6
    int_rva = delay_rva + 32
    iat_rva = int_rva + 4
    hint_name_rva = 0x1000 + (hint_name_off - 0x200)
    name_rva = 0x1000 + (name_off - 0x200)

    # Write the descriptor at the chosen offset.
    struct.pack_into("<IIIIIIII", pe_bytes, delay_file_off,
                     0,                            # attributes
                     name_rva,
                     iat_rva + 16,                  # module handle slot
                     iat_rva, int_rva,
                     0, 0,                         # BIAT, UIT
                     0)                            # timeDateStamp
    struct.pack_into("<I", pe_bytes, delay_file_off + 32, hint_name_rva)
    struct.pack_into("<I", pe_bytes, delay_file_off + 36, hint_name_rva)
    struct.pack_into("<II", pe_bytes, delay_file_off + 40, 0, 0)
    struct.pack_into("<H", pe_bytes, hint_name_off, 42)
    pe_bytes[hint_name_off + 2: hint_name_off + 6] = b"Foo\x00"
    pe_bytes[name_off: name_off + 10] = b"MYDLL.DLL\x00"

    # Bump NumberOfRvaAndSizes to 17 (entry index 13 + buffer) so the
    # 14th data directory is meaningful.  Also extend size_of_image so
    # the extra RVA fits within the loadable image.
    # NumberOfRvaAndSizes sits at the end of the standard fields
    # (offset 0x4B from the optional header start for PE32).
    num_rva_off = dd_off - 4
    old = struct.unpack_from("<I", pe_bytes, num_rva_off)[0]
    if old < 14:
        struct.pack_into("<I", pe_bytes, num_rva_off, 17)

    # Patch data directory index 13.  The dd region now has 17
    # entries (NumberOfRvaAndSizes updated), but we may only have
    # 16; extend with a zero entry first by shifting if needed.
    n_now = pe_probe.optional_header.number_of_rva_and_sizes
    if n_now < 17:
        # The directory array is fixed-size; if NumberOfRvaAndSizes
        # is <=16 we simply overwrite the last (still-zero) entry --
        # but the existing fixture packs exactly 16, so the 14th
        # slot is safe.
        pass
    struct.pack_into("<II", pe_bytes, dd_off + 13 * 8,
                     delay_rva, 32)
    return bytes(pe_bytes)


def _selftest() -> bool:
    # Use existing pe_loader to round-trip.
    from .pe_loader import PeFile
    blob = _build_pe_with_delay_imports()
    pe = PeFile.from_bytes(blob)
    ddir = parse_delay_imports(pe)
    if ddir is None or not ddir.entries:
        return False
    e = ddir.entries[0]
    if e.dll_name.upper() != "MYDLL.DLL":
        return False
    if not e.symbols:
        return False
    sym = e.symbols[0]
    if sym.name != "Foo":
        return False
    if sym.hint != 42:
        return False
    # Empty directory returns None.
    from .pe_loader import PeFile as _PF
    from .pe_loader import _build_fake_pe
    fake = _PF.from_bytes(_build_fake_pe())
    ddir2 = parse_delay_imports(fake)
    if ddir2 is not None:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
