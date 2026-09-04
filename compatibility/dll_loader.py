"""
Umer OS /compatibility/dll_loader — Pure-Python PE / DLL loader
============================================================

The :class:`DllLoader` resolves the *IAT* of a parsed PE binary
against a pool of named *exports* (typically :data:`EXPORTS` from
:mod:`win_kernel32`, :mod:`win_user32`, ...).  It is **read-only**
and **non-executing** -- the goal is to give a static analysis /
audit / instrumentation pipeline everything it needs, and to give a
loader enough metadata to map IAT names to host-side stubs.

The loader is *not* a full PE loader; in particular it does *not*:

* perform relocations (the image is assumed to be loaded at its
  preferred ``ImageBase``),
* resolve delay-loaded imports,
* honour the Bound Import Directory (Windows 7+ ignores it),
* execute any code.

A caller that wants a deeper view of a binary should combine the
output of :class:`DllLoader` with the parsers in
:mod:`pe_resources`, :mod:`pe_tls`, :mod:`pe_relocations`, etc.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
* https://learn.microsoft.com/en-us/windows/win32/debug/import-table-image-only

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .pe_loader import PeFile
from .pe_imports import parse_imports
from .pe_exports import parse_exports
from .pe_relocations import parse_relocations
from .pe_tls import parse_tls_directory
from .pe_resources import parse_resources

log = logging.getLogger("UmerOS.Compat.DllLoader")


# ---------------------------------------------------------------------------
# A registry of named export tables -- one per "host-side DLL".
# ---------------------------------------------------------------------------

ExportTable = Dict[str, Callable]


# Built-in libraries: a single dict of name -> exports.  Real
# Windows has 50+ subsystem DLLs; we wire up the most common ones
# so that the loader can satisfy a typical IAT.
from .win_kernel32 import EXPORTS as _KERNEL32
from .win_user32 import EXPORTS as _USER32
from .win_gdi32 import EXPORTS as _GDI32
from .win_advapi32 import EXPORTS as _ADVAPI32
from .win_ntdll import EXPORTS as _NTDLL

HOST_LIBRARIES: Dict[str, ExportTable] = {
    "KERNEL32.DLL": _KERNEL32,
    "kernel32.dll": _KERNEL32,
    "USER32.DLL": _USER32,
    "user32.dll": _USER32,
    "GDI32.DLL": _GDI32,
    "gdi32.dll": _GDI32,
    "ADVAPI32.DLL": _ADVAPI32,
    "advapi32.dll": _ADVAPI32,
    "NTDLL.DLL": _NTDLL,
    "ntdll.dll": _NTDLL,
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ResolvedImport:
    """A single IAT entry resolved to a host-side stub."""

    dll: str
    name: Optional[str]            # None for ordinal-only imports
    ordinal: int
    target: Optional[Callable]    # the resolved stub (or None if missing)

    @property
    def is_resolved(self) -> bool:
        return self.target is not None


@dataclass
class LoadedPe:
    """A parsed + analysed PE binary."""

    pe: PeFile
    imports: list                          # from pe_imports
    exports_obj: object                     # from pe_exports (or None)
    relocations: object                     # from pe_relocations (or None)
    tls: object                             # from pe_tls (or None)
    resources: object                        # from pe_resources (or None)
    resolved_imports: List[ResolvedImport] = field(default_factory=list)

    def missing_imports(self) -> List[Tuple[str, Optional[str], int]]:
        """Return ``(dll, name, ordinal)`` for every unresolved IAT entry."""
        return [
            (r.dll, r.name, r.ordinal)
            for r in self.resolved_imports
            if not r.is_resolved
        ]

    def summary(self) -> str:
        lines = [
            f"PE: machine={self.pe.machine_name} "
            f"subsystem={self.pe.subsystem_name} "
            f"image_base=0x{self.pe.image_base:08X} "
            f"entry=0x{self.pe.entry_point_rva:08X}",
            f"  sections: {[s.name for s in self.pe.sections]}",
            f"  imports: {len(self.imports)} DLL(s), "
            f"{sum(len(d.symbols) for d in self.imports)} symbol(s)",
        ]
        miss = self.missing_imports()
        if miss:
            lines.append(f"  MISSING: {len(miss)} unresolved import(s)")
            for d, n, o in miss[:10]:
                sym = n if n is not None else f"ord({o})"
                lines.append(f"    {d}!{sym}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class DllLoader:
    """Static analyser + IAT resolver for a parsed PE binary."""

    def __init__(self, host_libraries: Optional[Dict[str, ExportTable]] = None) -> None:
        self.host_libraries: Dict[str, ExportTable] = (
            host_libraries if host_libraries is not None
            else dict(HOST_LIBRARIES)
        )

    def add_library(self, name: str, exports: ExportTable) -> None:
        self.host_libraries[name] = exports

    def resolve(self, pe: PeFile) -> LoadedPe:
        """Parse every directory of ``pe`` and resolve its IAT."""
        imports = parse_imports(pe)
        exports_obj = parse_exports(pe)
        reloc = parse_relocations(pe)
        tls = parse_tls_directory(pe)
        res = parse_resources(pe)

        resolved: List[ResolvedImport] = []
        for dll in imports:
            lib = self._lookup_dll(dll.name)
            for sym in dll.symbols:
                target = None
                if lib is not None:
                    if sym.is_ordinal_only:
                        # Try ordinal lookup.  We don't have an
                        # exact export-by-ordinal index here, so we
                        # look for any name with that ordinal hint.
                        for ename, eproc in lib.items():
                            if eproc.__doc__ and f"ordinal={sym.ordinal}" in eproc.__doc__:
                                target = eproc
                                break
                    else:
                        target = lib.get(sym.name)
                resolved.append(ResolvedImport(
                    dll=dll.name, name=sym.name, ordinal=sym.ordinal,
                    target=target,
                ))

        return LoadedPe(
            pe=pe, imports=imports, exports_obj=exports_obj,
            relocations=reloc, tls=tls, resources=res,
            resolved_imports=resolved,
        )

    def _lookup_dll(self, name: str) -> Optional[ExportTable]:
        # Case-insensitive lookup.
        upper = name.upper()
        for k, v in self.host_libraries.items():
            if k.upper() == upper:
                return v
        return None


def _selftest() -> bool:
    """Verify a minimal PE round-trip: load a synthetic binary, resolve."""
    from .pe_loader import _build_fake_pe
    pe = PeFile.from_bytes(_build_fake_pe())
    loader = DllLoader()
    loaded = loader.resolve(pe)
    if loaded.pe is not pe:
        return False
    if not isinstance(loaded.imports, list):
        return False
    if loaded.exports_obj is not None:
        # The fake PE has no export directory; we expect None.
        return False
    if loaded.resolved_imports != []:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
