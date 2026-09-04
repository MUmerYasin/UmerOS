"""
Umer OS /compatibility/pe_exports — Export Directory parser
=========================================================

The **Export Directory** of a PE binary (usually a DLL) lives in
the data directory at index 0.  It tells the loader *which* symbols
the DLL exposes and *how* to find them.

Layout of the directory::

    typedef struct _IMAGE_EXPORT_DIRECTORY {
        DWORD Characteristics;        // reserved, 0
        DWORD TimeDateStamp;            // 0
        WORD  MajorVersion;             // 0
        WORD  MinorVersion;             // 0
        DWORD Name;                      // RVA -> DLL name (ASCII)
        DWORD Base;                      // starting ordinal
        DWORD NumberOfFunctions;        // total exported entries
        DWORD NumberOfNames;             // named exports (subset)
        DWORD AddressOfFunctions;       // RVA -> DWORD[NumberOfFunctions] (EAT)
        DWORD AddressOfNames;            // RVA -> DWORD[NumberOfNames]  (ENT)
        DWORD AddressOfNameOrdinals;    // RVA -> WORD[NumberOfNames]  (EOT)
    } IMAGE_EXPORT_DIRECTORY;            // 40 bytes

* EAT = Export Address Table  (RVAs into the image)
* ENT = Export Name Table     (RVAs into name strings)
* EOT = Export Ordinal Table  (parallel to ENT, gives the EAT index
  for each name)

A *forwarder* is an export whose address lives in a different DLL;
the corresponding EAT entry holds an RVA into the *forwarder string*
(e.g. ``"NTDLL.RtlAllocateHeap"``).

This module parses the directory and yields structured
:class:`ExportedSymbol` records.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#export-directory-table

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .pe_loader import PeFile


@dataclass
class ExportedSymbol:
    """A single exported symbol (or forwarder)."""

    name: Optional[str]            # None for purely-ordinal exports
    ordinal: int                  # 16-bit ordinal (always present)
    rva: int                      # the address RVA, or the forwarder RVA
    is_forwarder: bool            # True if ``rva`` points to a string
    forwarder: Optional[str]      # populated when ``is_forwarder`` is True

    def __str__(self) -> str:
        head = self.name or f"ord({self.ordinal})"
        if self.is_forwarder:
            return f"{head} -> {self.forwarder}"
        return f"{head} @ 0x{self.rva:08X}"


@dataclass
class ExportDirectory:
    """The IMAGE_EXPORT_DIRECTORY header plus its parsed tables."""

    name: str
    time_date_stamp: int
    base_ordinal: int
    number_of_functions: int
    number_of_names: int
    symbols: List[ExportedSymbol] = field(default_factory=list)
    by_name: Dict[str, ExportedSymbol] = field(default_factory=dict)
    by_ordinal: Dict[int, ExportedSymbol] = field(default_factory=dict)


_FORWARDER_STRING_RVA_MIN = 0
_FORWARDER_STRING_RVA_MAX = 0x7FFFFFFF


def parse_exports(pe: PeFile) -> Optional[ExportDirectory]:
    """Parse the Export Directory of ``pe``.

    Returns:
        A populated :class:`ExportDirectory`, or ``None`` if the
        binary exports no symbols.
    """
    dd = pe.get_data_directory(0)   # 0 = DataDirectoryId.EXPORT
    if dd is None or not dd.is_present:
        return None

    off, _ = pe.rva_to_offset(dd.virtual_address)
    if off + 40 > len(pe.raw):
        return None
    (chars, tds, _maj, _min, name_rva, base, n_funcs, n_names,
     eat_rva, ent_rva, eot_rva) = struct.unpack_from("<IIHHIIIIII", pe.raw, off)
    if n_funcs == 0 and n_names == 0:
        return None

    # DLL name
    name_off, _ = pe.rva_to_offset(name_rva)
    dll_name = _read_cstring(pe.raw, name_off)

    # EAT
    eat_off, _ = pe.rva_to_offset(eat_rva)
    eat = struct.unpack_from(f"<{n_funcs}I", pe.raw, eat_off)
    # ENT (parallel array)
    ent_off, _ = pe.rva_to_offset(ent_rva)
    ent = struct.unpack_from(f"<{n_names}I", pe.raw, ent_off)
    # EOT (parallel to ENT, WORD-sized)
    eot_off, _ = pe.rva_to_offset(eot_rva)
    eot = struct.unpack_from(f"<{n_names}H", pe.raw, eot_off)

    # Forwarder strings live in the *export directory's* RVA range,
    # so we recognise a forwarder by checking that the EAT entry is a
    # printable ASCII string starting with a Windows DLL name.
    def maybe_forwarder(rva: int) -> Optional[str]:
        try:
            soff, _ = pe.rva_to_offset(rva)
        except ValueError:
            return None
        if soff + 64 > len(pe.raw):
            return None
        blob = pe.raw[soff:soff + 64]
        end = blob.find(b"\x00")
        if end <= 0 or end > 64:
            return None
        s = blob[:end].decode("ascii", errors="replace")
        if not s or "." not in s or " " in s:
            return None
        return s

    syms: List[ExportedSymbol] = []
    by_name: Dict[str, ExportedSymbol] = {}
    by_ord: Dict[int, ExportedSymbol] = {}

    # EAT-only entries first (no name): ordinals [base..base+n_funcs).
    for i in range(n_funcs):
        ordinal = base + i
        rva = eat[i]
        is_fwd = maybe_forwarder(rva) is not None
        sym = ExportedSymbol(
            name=None, ordinal=ordinal, rva=rva,
            is_forwarder=is_fwd,
            forwarder=maybe_forwarder(rva) if is_fwd else None,
        )
        by_ord[ordinal] = sym
        syms.append(sym)

    # Named entries (EOT gives the EAT index for each name).
    for i, (name_rva, eat_idx) in enumerate(zip(ent, eot)):
        if eat_idx >= n_funcs:
            continue    # corrupt -- skip
        noff, _ = pe.rva_to_offset(name_rva)
        sname = _read_cstring(pe.raw, noff)
        ordinal = base + eat_idx
        existing = by_ord.get(ordinal)
        if existing is None:
            continue
        existing.name = sname
        existing.is_ordinal_only = False
        by_name[sname] = existing
        # Also re-key by_name in case multiple names map to one
        # ordinal (rare, but legal).
        syms.append(ExportedSymbol(
            name=sname, ordinal=ordinal, rva=existing.rva,
            is_forwarder=existing.is_forwarder,
            forwarder=existing.forwarder,
        ))

    return ExportDirectory(
        name=dll_name,
        time_date_stamp=tds,
        base_ordinal=base,
        number_of_functions=n_funcs,
        number_of_names=n_names,
        symbols=syms,
        by_name=by_name,
        by_ordinal=by_ord,
    )


def _read_cstring(data: bytes, off: int) -> str:
    end = off
    while end < len(data) and data[end] != 0:
        end += 1
    return data[off:end].decode("ascii", errors="replace")


def _selftest() -> bool:
    """Verify the export parser with a PE that has no exports."""
    from .pe_loader import _build_fake_pe
    pe = PeFile.from_bytes(_build_fake_pe())
    if parse_exports(pe) is None:
        return True
    return False


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
