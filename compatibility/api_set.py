"""
Umer OS /compatibility/api_set — API Set Schema parser
======================================================

Windows 7+ replaced the flat ``kernel32.dll`` / ``user32.dll`` set
with a *namespace* of virtual modules whose names begin with
``api-ms-win-*`` (``api-ms-win-core-io-l1-1-0.dll``,
``api-ms-win-crt-runtime-l1-1-0.dll``, ...).  The mapping from each
virtual name to one or more *host* DLLs lives in the
``.apiset`` section of a single system image
(``apisetschema.dll``) and is consulted by the loader every time
the IAT references one of these names.

This module is a pure-Python implementation of the schema reader.
It supports the v2 layout that ships with every Windows release
since Windows 7 and the v6 layout that some embedded SKUs use.

Layout (v2)::

    typedef struct _API_SET_NAMESPACE {
        ULONG Version;        // 2
        ULONG Size;
        ULONG Flags;          // 0
        ULONG Count;
        ULONG EntryOffset;
        ULONG HashOffset;
        ULONG HashFactor;
    } API_SET_NAMESPACE;

    typedef struct _API_SET_HASH_ENTRY {
        ULONG Hash;
        ULONG Index;
    } API_SET_HASH_ENTRY;

    typedef struct _API_SET_NAMESPACE_ENTRY {
        ULONG Flags;
        ULONG NameOffset;
        ULONG NameLength;
        ULONG HashedLength;
        ULONG ValueOffset;
        ULONG ValueCount;
    } API_SET_NAMESPACE_ENTRY;

    typedef struct _API_SET_VALUE_ENTRY {
        ULONG Flags;
        ULONG NameOffset;
        ULONG NameLength;
        ULONG ValueOffset;
        ULONG ValueLength;
    } API_SET_VALUE_ENTRY;

Strings are stored as UTF-16LE *and* include a trailing ``-l<n>-<m>``
suffix (the API set contract version); the resolver strips this
suffix before matching.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/apiindex/api-set-loader-operation
* https://ntcore.com/files/ApiSetSchema.pdf

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.ApiSet")


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApiSetValue:
    """One host DLL entry inside a namespace entry."""
    dll_name: str                  # e.g. "kernel32.dll"
    flags: int = 0


@dataclass(frozen=True)
class ApiSetEntry:
    """One virtual API set contract and its host DLLs.

    ``name`` is stored *without* the ``.dll`` suffix; ``contract_name``
    is the verbatim contract string the loader sees in the IAT.
    """
    name: str                       # "api-ms-win-core-io-l1-1-0"
    contract_name: str              # "api-ms-win-core-io-l1-1-0.dll"
    values: Tuple[ApiSetValue, ...]
    flags: int = 0


@dataclass
class ApiSetNamespace:
    """The whole schema -- a mapping from contract name to host DLL(s)."""

    version: int
    flags: int
    entries: Dict[str, ApiSetEntry] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def resolve(self, contract: str) -> Optional[ApiSetEntry]:
        """Resolve an IAT contract name (case-insensitive, optional ``.dll``)."""
        if not contract:
            return None
        upper = contract.upper()
        # Try with .dll first, then bare name.
        if upper in self.entries:
            return self.entries[upper]
        bare = upper[:-4] if upper.endswith(".DLL") else upper
        if bare and (bare + ".DLL") in self.entries:
            return self.entries[bare + ".DLL"]
        # Last-ditch: any entry whose name == bare.
        for k, v in self.entries.items():
            if k[:-4] == bare:
                return v
        return None

    def all_contracts(self) -> List[str]:
        return sorted(self.entries.keys())

    def host_dlls(self, contract: str) -> List[str]:
        entry = self.resolve(contract)
        if entry is None:
            return []
        return [v.dll_name for v in entry.values]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _u16_at(buf: bytes, off: int) -> str:
    """Decode a UTF-16LE string starting at ``off`` up to a NUL terminator."""
    end = off
    while end + 1 < len(buf):
        if buf[end] == 0 and buf[end + 1] == 0:
            break
        end += 2
    return buf[off:end].decode("utf-16-le", errors="replace")


def parse_apiset(blob: bytes) -> Optional[ApiSetNamespace]:
    """Parse an API Set Schema blob (the contents of ``.apiset``).

    Returns ``None`` if the blob is too small to hold the header.
    """
    if len(blob) < 28:
        return None
    (version, size, flags, count,
     entry_off, hash_off, _hash_factor) = struct.unpack_from(
        "<7I", blob, 0)
    if version not in (2, 3, 4, 6):
        log.debug("unknown API set version %d", version)
        return None
    if size > len(blob) or count > (len(blob) // 24):
        log.debug("implausible API set header (size=%d count=%d)", size, count)
        return None

    # The hash table is consulted by the Windows loader for O(1)
    # lookups; for an offline analyser the sequential scan is fine.
    # Walk EntryOffset..EntryOffset + 24*Count (each namespace entry
    # is 6 ULONGs = 24 bytes; values are 5 ULONGs = 20 bytes each).
    entries: Dict[str, ApiSetEntry] = {}
    base = entry_off
    for i in range(count):
        off = base + i * 24
        if off + 24 > len(blob):
            break
        (ent_flags, name_off, name_len, _hash_len,
         val_off, val_count) = struct.unpack_from("<6I", blob, off)
        name = _u16_at(blob, name_off)
        # Some schemas include a leading ``.dll`` in the contract name;
        # strip it so callers can pass either form.
        if name.lower().endswith(".dll"):
            bare = name[:-4]
        else:
            bare = name
        # Values follow the entry table (one struct per value, 20 bytes).
        values: List[ApiSetValue] = []
        for j in range(val_count):
            v_off = val_off + j * 20
            if v_off + 20 > len(blob):
                break
            (v_flags, v_name_off, v_name_len, _v_val_off, _v_val_len
             ) = struct.unpack_from("<5I", blob, v_off)
            v_name = _u16_at(blob, v_name_off)
            # Host DLL names sometimes arrive with a leading
            # ``\x00\x00`` (Windows quirk); strip trailing whitespace.
            v_name = v_name.strip()
            values.append(ApiSetValue(dll_name=v_name, flags=v_flags))

        entry = ApiSetEntry(
            name=bare,
            contract_name=(bare + ".dll").upper(),
            values=tuple(values),
            flags=ent_flags,
        )
        entries[entry.contract_name] = entry

    return ApiSetNamespace(version=version, flags=flags, entries=entries)


# ---------------------------------------------------------------------------
# Built-in fallback schema
# ---------------------------------------------------------------------------
#
# When the host does not ship an ``apisetschema.dll`` (e.g. when we
# run on a non-Windows box), the loader needs *something* to keep
# modern binaries from looking entirely unresolved.  The fallback
# below is a hand-curated subset of the contracts that ship with
# every Windows 10+ install.  It is **not** exhaustive -- production
# should always prefer the live schema when available.

_FALLBACK_VALUES: Dict[str, Tuple[str, ...]] = {
    "api-ms-win-core-console-l1-1-0":         ("kernel32.dll",),
    "api-ms-win-core-console-l2-1-0":         ("kernel32.dll",),
    "api-ms-win-core-datetime-l1-1-0":        ("kernel32.dll",),
    "api-ms-win-core-debug-l1-1-0":           ("kernel32.dll",),
    "api-ms-win-core-errorhandling-l1-1-0":   ("kernel32.dll",),
    "api-ms-win-core-fibers-l1-1-0":          ("kernel32.dll",),
    "api-ms-win-core-file-l1-1-0":            ("kernel32.dll",),
    "api-ms-win-core-handle-l1-1-0":          ("kernel32.dll",),
    "api-ms-win-core-heap-l1-1-0":            ("kernel32.dll",),
    "api-ms-win-core-interlocked-l1-1-0":     ("kernel32.dll",),
    "api-ms-win-core-io-l1-1-0":              ("kernel32.dll",),
    "api-ms-win-core-libraryloader-l1-1-0":   ("kernel32.dll",),
    "api-ms-win-core-localization-l1-1-0":    ("kernel32.dll",),
    "api-ms-win-core-memory-l1-1-0":          ("kernel32.dll",),
    "api-ms-win-core-namedpipe-l1-1-0":       ("kernel32.dll",),
    "api-ms-win-core-processenvironment-l1-1-0": ("kernel32.dll",),
    "api-ms-win-core-processthreads-l1-1-0":  ("kernel32.dll",),
    "api-ms-win-core-profile-l1-1-0":         ("kernel32.dll",),
    "api-ms-win-core-rtlsupport-l1-1-0":      ("kernel32.dll",),
    "api-ms-win-core-string-l1-1-0":         ("kernel32.dll",),
    "api-ms-win-core-synch-l1-1-0":           ("kernel32.dll",),
    "api-ms-win-core-sysinfo-l1-1-0":         ("kernel32.dll",),
    "api-ms-win-core-threadpool-l1-1-0":      ("kernel32.dll",),
    "api-ms-win-core-timezone-l1-1-0":        ("kernel32.dll",),
    "api-ms-win-core-ums-l1-1-0":             ("kernel32.dll",),
    "api-ms-win-core-wow64-l1-1-0":           ("kernel32.dll",),
    "api-ms-win-core-xstate-l1-1-0":          ("kernel32.dll",),
    "api-ms-win-core-realtime-l1-1-0":        ("kernel32.dll",),
    "api-ms-win-core-winrt-l1-1-0":           ("kernel32.dll",),

    "api-ms-win-crt-conio-l1-1-0":            ("ucrtbase.dll",),
    "api-ms-win-crt-convert-l1-1-0":          ("ucrtbase.dll",),
    "api-ms-win-crt-environment-l1-1-0":      ("ucrtbase.dll",),
    "api-ms-win-crt-filesystem-l1-1-0":       ("ucrtbase.dll",),
    "api-ms-win-crt-heap-l1-1-0":             ("ucrtbase.dll",),
    "api-ms-win-crt-locale-l1-1-0":           ("ucrtbase.dll",),
    "api-ms-win-crt-math-l1-1-0":             ("ucrtbase.dll",),
    "api-ms-win-crt-multibyte-l1-1-0":        ("ucrtbase.dll",),
    "api-ms-win-crt-private-l1-1-0":          ("ucrtbase.dll",),
    "api-ms-win-crt-process-l1-1-0":          ("ucrtbase.dll",),
    "api-ms-win-crt-runtime-l1-1-0":          ("ucrtbase.dll",),
    "api-ms-win-crt-stdio-l1-1-0":            ("ucrtbase.dll",),
    "api-ms-win-crt-string-l1-1-0":           ("ucrtbase.dll",),
    "api-ms-win-crt-time-l1-1-0":             ("ucrtbase.dll",),
    "api-ms-win-crt-utility-l1-1-0":          ("ucrtbase.dll",),

    "api-ms-win-eventing-classicprovider-l1-1-0": ("advapi32.dll",),
    "api-ms-win-eventing-consumer-l1-1-0":    ("advapi32.dll",),
    "api-ms-win-eventing-controller-l1-1-0":  ("advapi32.dll",),
    "api-ms-win-eventing-legacy-l1-1-0":     ("advapi32.dll",),
    "api-ms-win-eventing-provider-l1-1-0":    ("advapi32.dll",),

    "api-ms-win-security-base-l1-1-0":        ("advapi32.dll",),
    "api-ms-win-security-cryptoapi-l1-1-0":  ("advapi32.dll",),
    "api-ms-win-security-credentials-l1-1-0": ("advapi32.dll",),
    "api-ms-win-security-lsalookup-l1-1-0":   ("advapi32.dll",),
    "api-ms-win-security-sddl-l1-1-0":       ("advapi32.dll",),

    "api-ms-win-service-core-l1-1-0":         ("sechost.dll", "advapi32.dll"),
    "api-ms-win-service-management-l1-1-0":   ("sechost.dll", "advapi32.dll"),
    "api-ms-win-service-winsvc-l1-1-0":       ("sechost.dll", "advapi32.dll"),

    "api-ms-win-power-base-l1-1-0":           ("powrprof.dll",),
    "api-ms-win-power-setting-l1-1-0":        ("powrprof.dll",),
}


def fallback_namespace() -> ApiSetNamespace:
    """Return the small, hard-coded schema we ship as a fallback."""
    entries: Dict[str, ApiSetEntry] = {}
    for name, hosts in _FALLBACK_VALUES.items():
        entry = ApiSetEntry(
            name=name,
            contract_name=(name + ".dll").upper(),
            values=tuple(ApiSetValue(dll_name=h, flags=0) for h in hosts),
        )
        entries[entry.contract_name] = entry
    return ApiSetNamespace(version=2, flags=0, entries=entries)


def is_api_set_name(name: str) -> bool:
    """Return ``True`` if ``name`` looks like an API Set contract."""
    if not name:
        return False
    upper = name.upper()
    return upper.startswith(("API-MS-WIN-", "API-MS-WIN-CORE-",
                             "API-MS-WIN-CRT-"))


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    # Fallback schema is populated.
    ns = fallback_namespace()
    if not ns.entries:
        return False
    e = ns.resolve("api-ms-win-core-io-l1-1-0.dll")
    if e is None or e.values[0].dll_name.lower() != "kernel32.dll":
        return False
    e = ns.resolve("api-ms-win-crt-runtime-l1-1-0")
    if e is None or e.values[0].dll_name.lower() != "ucrtbase.dll":
        return False
    if not is_api_set_name("api-ms-win-core-foo-l1-1-0"):
        return False
    if is_api_set_name("KERNEL32.DLL"):
        return False
    # Round-trip parse a synthetic schema blob.
    blob = _build_synthetic_schema()
    parsed = parse_apiset(blob)
    if parsed is None or parsed.version != 2:
        return False
    e = parsed.resolve("api-ms-win-test-set-l1-1-0.dll")
    if e is None or e.values[0].dll_name != "ucrtbase.dll":
        return False
    return True


def _build_synthetic_schema() -> bytes:
    """Build a minimal v2 schema blob in-memory so ``parse_apiset`` has
    something to chew on during the selftest."""
    strings = [
        "api-ms-win-test-set-l1-1-0",
        "ucrtbase.dll",
    ]
    blobs = [s.encode("utf-16-le") + b"\x00\x00" for s in strings]

    # Lay out: [header 28][entry 24][value 20][string data...]
    entry_off = 28
    value_off = entry_off + 24
    name_string_off = value_off + 20
    host_string_off = name_string_off + len(blobs[0])
    total_size = host_string_off + len(blobs[1])

    entry = struct.pack(
        "<6I",
        0,                          # Flags
        name_string_off,            # NameOffset
        len(strings[0]) * 2,        # NameLength (UTF-16LE bytes, no NUL)
        len(strings[0]) * 2,        # HashedLength
        value_off,                  # ValueOffset
        1,                          # ValueCount
    )
    value = struct.pack(
        "<5I",
        0,                          # Flags
        host_string_off,            # NameOffset
        len(strings[1]) * 2,        # NameLength
        host_string_off,            # ValueOffset
        len(strings[1]) * 2,        # ValueLength
    )
    blob = struct.pack(
        "<7I",
        2,                          # Version
        total_size,                 # Size (full blob length)
        0,                          # Flags
        1,                          # Count
        entry_off,
        entry_off + 32,             # HashOffset (dummy)
        1,                          # HashFactor (dummy)
    )
    blob += entry + value + b"".join(blobs)
    assert len(blob) == total_size, f"size mismatch: {len(blob)} vs {total_size}"
    return blob


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
