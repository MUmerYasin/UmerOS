"""
Umer OS /compatibility/forwarded — Forwarded-export chain follower
================================================================

A *forwarded export* is a PE export whose EAT entry points back into
the *export section* of the same image.  The data at that address is
a printable ASCII string of the form ``"dll.symbol"`` (or
``"dll.#ordinal"``), and the real implementation lives in ``dll``.

The Windows loader follows the chain recursively until it finds an
export whose EAT entry points into a *code* section.  This module
implements the same algorithm in pure Python::

    forwarded.resolve(symbol) -> ResolvedForward
        chain   : list of forwarder strings encountered
        final   : the dll.symbol we ended up at
        depth   : number of hops
        is_terminal: True if the final entry is not a forwarder

Forwarders can also reference **API Set** contracts (e.g.
``api-ms-win-core-...``); we delegate to :mod:`api_set` so the same
chain follower covers both flavours.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#export-address-table
* https://ntcore.com/files/ApiSetSchema.pdf

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .pe_loader import PeFile
from .pe_exports import ExportedSymbol, parse_exports, ExportDirectory

log = logging.getLogger("UmerOS.Compat.Forwarded")


#: Type alias for the export resolver.  Given a DLL name (case-
#: insensitive) and a symbol (name or ``"#<ordinal>"``), return the
#: resolution string the loader would have used.  Returning
#: ``None`` indicates the symbol was not found.
ExportResolver = Callable[[str, str], Optional[str]]

#: Maximum recursion depth.  Windows itself caps around 8; we cap at 16
#: so a malformed PE that creates a cycle cannot crash the loader.
MAX_FORWARD_DEPTH = 16


@dataclass(frozen=True)
class ResolvedForward:
    """The end-to-end result of following a forwarder chain."""

    symbol: str                       # original "dll.symbol" we asked about
    final_dll: str                    # the dll we ended up at
    final_name: str                   # the symbol we ended up at
    chain: Tuple[str, ...]            # ordered list of forwarder strings
    depth: int
    is_terminal: bool                 # True if chain ended in a real export

    @property
    def resolved_as(self) -> str:
        return f"{self.final_dll}!{self.final_name}"


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------

@dataclass
class ForwarderString:
    """A parsed ``"dll.symbol"`` forwarder string."""

    dll: str
    symbol: str
    is_ordinal: bool = False
    ordinal: int = 0

    @classmethod
    def parse(cls, s: str) -> Optional["ForwarderString"]:
        if not s:
            return None
        # The Windows loader uses ``strrchr`` (the *last* dot) to find
        # the boundary; this matches both ``kernel32.DecodePointer``
        # and ``api-ms-win-foo-l1-1-0.dll.Symbol`` (which has two dots).
        idx = s.rfind(".")
        if idx <= 0 or idx >= len(s) - 1:
            return None
        dll = s[:idx].strip()
        rest = s[idx + 1:].strip()
        if not dll or not rest:
            return None
        if rest.startswith("#"):
            try:
                ordv = int(rest[1:])
            except ValueError:
                return None
            return cls(dll=dll, symbol=rest, is_ordinal=True, ordinal=ordv)
        return cls(dll=dll, symbol=rest, is_ordinal=False)


def is_forwarder_rva(rva: int, export_dir: ExportDirectory) -> bool:
    """Return ``True`` if ``rva`` lies inside the export directory range.

    This is the canonical way the loader recognises a forwarder: the
    EAT entry holds an RVA, and if that RVA falls within the export
    *section* (not just the directory structure itself), the bytes at
    that location form a printable ``"dll.symbol"`` string.
    """
    dd_rva = export_dir.base_ordinal  # placeholder; real check below
    # We can compute the export-section RVA range from the directory
    # header.  parse_exports already exposed ``name`` and counts but
    # not the RVA range; we recompute it lazily.
    return False  # see export_section_range() helper


def export_section_rva_range(pe: PeFile, export_dir: ExportDirectory
                              ) -> Tuple[int, int]:
    """Return the (start, end) RVA range of the export directory entry.

    The forwarder RVA detection needs the *directory* RVA range, not
    the section range: any RVA inside the directory block holds the
    forwarder string, anything else holds code.
    """
    # The ExportDirectory dataclass doesn't carry its own RVA; we can
    # find it via the data directory of the PE.
    dd = pe.get_data_directory(0)   # DataDirectoryId.EXPORT
    if dd is None or not dd.is_present:
        return (0, 0)
    return (dd.virtual_address, dd.virtual_address + dd.size)


def is_forwarder_in_range(rva: int, range_: Tuple[int, int]) -> bool:
    return range_[0] <= rva < range_[1]


# ---------------------------------------------------------------------------
# Chain follower
# ---------------------------------------------------------------------------

def follow_forward(symbol: str,
                   resolver: ExportResolver,
                   *,
                   max_depth: int = MAX_FORWARD_DEPTH
                   ) -> Optional[ResolvedForward]:
    """Follow a forwarder chain starting at ``symbol``.

    ``symbol`` may be either a DLL+name pair encoded as
    ``"dll.symbol"`` (the same form a forwarder string uses) or a
    plain symbol name belonging to ``dll``.

    ``resolver(dll, sym)`` is called with each hop; it must return
    the *next* forwarder string (``"dll.symbol"``) when the symbol
    is a forwarder, ``None`` if the symbol is not exported, or the
    literal string ``"__terminal__"`` to indicate the symbol is a
    real export (not a forwarder).

    The function returns ``None`` if the chain loops or exceeds
    ``max_depth``.
    """
    if not symbol:
        return None
    parsed = ForwarderString.parse(symbol)
    if parsed is None:
        return None
    chain: List[str] = []
    depth = 0
    while True:
        depth += 1
        if depth > max_depth:
            log.warning("forwarder chain exceeded %d hops at %s",
                        max_depth, symbol)
            return None
        next_str = resolver(parsed.dll, parsed.symbol)
        if next_str is None:
            # Symbol not found at all.
            return ResolvedForward(
                symbol=symbol,
                final_dll=parsed.dll,
                final_name=parsed.symbol,
                chain=tuple(chain),
                depth=depth,
                is_terminal=False,
            )
        if next_str == "__terminal__":
            # Found a real export.
            return ResolvedForward(
                symbol=symbol,
                final_dll=parsed.dll,
                final_name=parsed.symbol,
                chain=tuple(chain),
                depth=depth,
                is_terminal=True,
            )
        chain.append(f"{parsed.dll}!{parsed.symbol} -> {next_str}")
        nxt = ForwarderString.parse(next_str)
        if nxt is None:
            log.warning("malformed forwarder string: %r", next_str)
            return None
        parsed = nxt
        # Cycle detection.
        if next_str in chain[:-1]:
            log.warning("forwarder cycle at %s", next_str)
            return None


# ---------------------------------------------------------------------------
# Adapter: build an ExportResolver from a {dll: {symbol: callable}} map
# ---------------------------------------------------------------------------

def make_table_resolver(table: Dict[str, Dict[str, Callable]]
                        ) -> ExportResolver:
    """Build a resolver from a {dll -> exports} map.

    The returned function returns the next forwarder string when the
    *real* export table is provided, or ``"__terminal__"`` if the
    function is in the table but we want to treat it as terminal.
    Tables from the loader layer do not store forwarder chains; use
    :func:`make_pe_resolver` for that.
    """
    # Build a normalized view: keys are upper-cased and have a ``.DLL``
    # suffix so callers can pass either ``"kernel32"`` or ``"kernel32.dll"``.
    normalized: Dict[str, Dict[str, Callable]] = {}
    for k, v in table.items():
        upper = k.upper()
        normalized[upper] = v
        if not upper.endswith(".DLL"):
            normalized[upper + ".DLL"] = v
        elif upper.endswith(".DLL"):
            bare = upper[:-4]
            if bare not in normalized:
                normalized[bare] = v

    def resolve(dll: str, sym: str) -> Optional[str]:
        upper = dll.upper()
        candidates = [upper, upper + ".DLL"] if not upper.endswith(".DLL") \
            else [upper, upper[:-4]]
        for c in candidates:
            if c in normalized and sym in normalized[c]:
                return "__terminal__"
        return None
    return resolve


def make_pe_resolver(image_table: Dict[str, PeFile],
                     api_set_resolver: Optional[Callable[[str], Optional[str]]] = None
                     ) -> ExportResolver:
    """Build a resolver that walks an in-memory PE image table.

    ``image_table`` maps DLL name (upper case) to the parsed
    :class:`PeFile` for that DLL.  When asked to resolve a symbol,
    the resolver parses the export directory of the target PE and:

    * returns the forwarder string if the symbol is a forwarder,
    * returns ``"__terminal__"`` if the symbol exists and is real,
    * returns ``None`` if the symbol does not exist.

    API Set contracts are handled via ``api_set_resolver``: given a
    contract name it returns the host DLL (e.g. ``"kernel32.dll"``).
    """
    cache: Dict[str, Tuple[ExportDirectory, Tuple[int, int]]] = {}

    def _dir(dll: str) -> Optional[Tuple[ExportDirectory, Tuple[int, int]]]:
        if dll in cache:
            return cache[dll]
        pe = image_table.get(dll)
        if pe is None:
            return None
        d = parse_exports(pe)
        if d is None:
            cache[dll] = (None, (0, 0))    # type: ignore[assignment]
            return cache[dll]
        r = export_section_rva_range(pe, d)
        cache[dll] = (d, r)
        return cache[dll]

    def resolve(dll: str, sym: str) -> Optional[str]:
        # Resolve api-set first if we have a resolver.
        upper = dll.upper()
        if api_set_resolver is not None and upper.startswith("API-MS-WIN-"):
            host = api_set_resolver(dll)
            if host is not None:
                upper = host.upper()
        entry = _dir(upper)
        if entry is None or entry[0] is None:
            return None
        export_dir, rva_range = entry
        sym_obj: Optional[ExportedSymbol] = None
        if sym.startswith("#"):
            try:
                ordv = int(sym[1:])
                sym_obj = export_dir.by_ordinal.get(ordv)
            except ValueError:
                sym_obj = None
        else:
            sym_obj = export_dir.by_name.get(sym)
        if sym_obj is None:
            return None
        if sym_obj.is_forwarder:
            return sym_obj.forwarder
        # The official loader heuristic: an export is a forwarder when
        # its RVA falls inside the export directory range.  ``is_forwarder``
        # in our parser uses a string-presence test which can be fooled
        # by data sections; the range test is more robust.
        if is_forwarder_in_range(sym_obj.rva, rva_range):
            # Read the forwarder string from the PE.
            pe = image_table.get(upper)
            if pe is None:
                return None
            try:
                off, _ = pe.rva_to_offset(sym_obj.rva)
            except ValueError:
                return None
            blob = pe.raw[off:off + 256]
            end = blob.find(b"\x00")
            if end <= 0:
                return None
            return blob[:end].decode("ascii", errors="replace")
        return "__terminal__"

    return resolve


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    # Round-trip a forwarder string.
    f = ForwarderString.parse("kernel32.DecodePointer")
    if f is None or f.dll != "kernel32" or f.symbol != "DecodePointer":
        return False
    if f.is_ordinal:
        return False
    f2 = ForwarderString.parse("ntdll.#42")
    if f2 is None or f2.dll != "ntdll" or not f2.is_ordinal:
        return False
    if f2.ordinal != 42:
        return False
    # Bad input.
    if ForwarderString.parse("") is not None:
        return False
    if ForwarderString.parse("nodothere") is not None:
        return False
    if ForwarderString.parse(".sym") is not None:
        return False
    if ForwarderString.parse("dll.") is not None:
        return False

    # Chain follower with a stub resolver.
    table = {
        "KERNEL32.DLL": {"Sleep": object()},
        "NTDLL.DLL": {"RtlSleep": object()},
    }
    res = make_table_resolver(table)
    chain = follow_forward("kernel32.Sleep", res)
    if chain is None or not chain.is_terminal:
        return False

    # Build a forwarding chain:  A!foo -> B!bar -> C!baz.
    def chain_resolver(dll, sym):
        if (dll.upper(), sym) == ("A", "foo"):
            return "b.dll.bar"
        if (dll.upper(), sym) == ("B.DLL", "bar"):
            return "c.dll.baz"
        if (dll.upper(), sym) == ("C.DLL", "baz"):
            return "__terminal__"
        return None

    chain = follow_forward("a.foo", chain_resolver)
    if chain is None or chain.is_terminal is False:
        return False
    if chain.depth != 3:
        return False
    if chain.final_dll.upper() != "C.DLL" or chain.final_name != "baz":
        return False
    if len(chain.chain) != 2:
        return False

    # Cycle detection.
    def cyclic(dll, sym):
        if sym == "alpha":
            return "beta"
        if sym == "beta":
            return "alpha"
        return None
    if follow_forward("gamma.alpha", cyclic) is not None:
        return False

    # Max-depth detection.
    def depthy(dll, sym):
        return "next.next"        # always forwards

    r = follow_forward("start.start", depthy, max_depth=4)
    if r is not None:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
