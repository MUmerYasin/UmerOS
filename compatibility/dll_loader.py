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
License: GPL-3.0 
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
from .api_set import ApiSetNamespace, fallback_namespace, is_api_set_name
from .forwarded import (ForwarderString, follow_forward,
                        make_pe_resolver, make_table_resolver)
from .dll_search import (DllSearchPath, find_dll, SearchLocation,
                         LOAD_LIBRARY_SEARCH_DEFAULT_DIRS)

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


#: Cache populated by :meth:`DllLoader.resolve_advanced` when a
#: ``search_path`` is supplied.  Maps ``id(pe)`` to a ``{dll_name:
#: (location, abs_path)}`` dict so callers can re-use the search
#: results without re-walking the filesystem.
_SEARCH_HITS: Dict[int, Dict[str, "tuple"]] = {}


def get_search_hits(loaded: "LoadedPe") -> Dict[str, "tuple"]:
    """Return the disk-search hits accumulated for ``loaded.pe``."""
    return dict(_SEARCH_HITS.get(id(loaded.pe), {}))


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
    #: Forwarder chain (populated when the import resolved through a chain).
    forward_chain: Tuple[str, ...] = ()
    #: API Set host DLL that ultimately satisfied the import (if any).
    api_set_host: Optional[str] = None

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
        return self.resolve_advanced(pe, api_set=None, search_path=None,
                                     image_table=None)

    def resolve_advanced(self, pe: PeFile,
                         *,
                         api_set: Optional[ApiSetNamespace] = None,
                         search_path: Optional[DllSearchPath] = None,
                         image_table: Optional[Dict[str, PeFile]] = None,
                         ) -> LoadedPe:
        """Like :meth:`resolve` but uses API Set + forwarded + search
        order when supplied.

        * ``api_set`` -- an :class:`~compatibility.api_set.ApiSetNamespace`
          that maps contract names (``api-ms-win-...``) to host DLLs.
          When absent, the small built-in :func:`fallback_namespace` is
          used.
        * ``search_path`` -- a :class:`~compatibility.dll_search.DllSearchPath`
          describing where the loader should look for DLL files.
        * ``image_table`` -- a mapping from DLL name (case-insensitive)
          to a parsed :class:`PeFile`, used to follow forwarder chains
          that re-enter another DLL.
        """
        if api_set is None:
            api_set = fallback_namespace()
        imports = parse_imports(pe)
        exports_obj = parse_exports(pe)
        reloc = parse_relocations(pe)
        tls = parse_tls_directory(pe)
        res = parse_resources(pe)

        # Build a resolver that consults API Set first, then walks
        # forwarder chains across image_table / host_libraries.
        host_libraries = self.host_libraries

        def api_set_resolve(name: str) -> Optional[str]:
            entry = api_set.resolve(name)
            if entry is None or not entry.values:
                return None
            return entry.values[0].dll_name

        resolver = make_pe_resolver(
            image_table or {},
            api_set_resolver=api_set_resolve,
        )

        resolved: List[ResolvedImport] = []
        for dll in imports:
            api_set_host: Optional[str] = None
            effective_dll = dll.name
            if is_api_set_name(dll.name):
                host = api_set_resolve(dll.name)
                if host is not None:
                    api_set_host = host
                    effective_dll = host

            lib = self._lookup_dll(effective_dll)
            for sym in dll.symbols:
                target = None
                chain: Tuple[str, ...] = ()
                if lib is not None:
                    if sym.is_ordinal_only:
                        for ename, eproc in lib.items():
                            if eproc.__doc__ and f"ordinal={sym.ordinal}" in eproc.__doc__:
                                target = eproc
                                break
                    else:
                        target = lib.get(sym.name)
                        # If still unresolved, try following the
                        # forwarder chain via image_table.
                        if target is None and image_table is not None:
                            fw = follow_forward(
                                f"{effective_dll}.{sym.name}",
                                resolver,
                            )
                            if fw is not None and fw.is_terminal:
                                chain = fw.chain
                                target = self._lookup_dll_export(
                                    fw.final_dll, fw.final_name)
                resolved.append(ResolvedImport(
                    dll=dll.name, name=sym.name, ordinal=sym.ordinal,
                    target=target,
                    forward_chain=chain,
                    api_set_host=api_set_host,
                ))
                # Side effect: if a search_path was given and we did
                # not find the DLL in host_libraries, record the disk
                # location for the caller (used by the audit CLI).
                if (search_path is not None and lib is None
                        and not is_api_set_name(dll.name)):
                    hit = find_dll(dll.name, search_path)
                    if hit is not None:
                        _SEARCH_HITS.setdefault(id(pe), {})[dll.name] = hit

        loaded = LoadedPe(
            pe=pe, imports=imports, exports_obj=exports_obj,
            relocations=reloc, tls=tls, resources=res,
            resolved_imports=resolved,
        )
        return loaded

    def _lookup_dll_export(self, dll: str, name: str) -> Optional[Callable]:
        """Resolve an export name across the registered host libraries."""
        lib = self._lookup_dll(dll)
        if lib is None:
            return None
        return lib.get(name)

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
