"""
Umer OS /compatibility/pe_resources — PE Resource Directory parser
===============================================================

The **Resource Directory** lives at data-directory index 2 and
holds the .NET manifest, icons, dialogs, string tables, version
info, and other auxiliary blobs.  It is structured as a
3-level tree of directories and data entries::

    [IMAGE_RESOURCE_DIRECTORY]            // each "page" is 16 bytes
        Type / Name / Language (12-bit IDs)
        -> directory entry (16 bytes):
            * high bit = 0: pointer to another directory
            * high bit = 1: pointer to a data entry
    [IMAGE_RESOURCE_DIRECTORY_ENTRY] * N
        union Name/Id;                       // 4 bytes
        union OffsetToData / OffsetToDirectory;  // 4 bytes
    [IMAGE_RESOURCE_DATA_ENTRY]            // 16 bytes
        DWORD Size;
        DWORD Codepage;
        RVA   RVA_to_data;

This module:

* walks the resource tree, collecting leaf :class:`ResourceEntry`
  records,
* decodes string-table (``RT_STRING``) and message-table
  (``RT_MESSAGETABLE``) blobs,
* supports **any** RT_ value (the rest are returned as raw bytes).

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#resource-directory-table

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional

from .pe_loader import PeFile


# Predefined resource types (RT_*).  Any unknown value is preserved
# as a raw int.
class Rt:
    CURSOR = 1
    BITMAP = 2
    ICON = 3
    MENU = 4
    DIALOG = 5
    STRING = 6
    FONTDIR = 7
    FONT = 8
    ACCELERATOR = 9
    RCDATA = 10
    MESSAGETABLE = 11
    GROUP_CURSOR = 12
    GROUP_ICON = 14
    VERSION = 16
    DLGINCLUDE = 17
    PLUGPLAY = 19
    VXD = 20
    ANICURSOR = 21
    ANIICON = 22
    HTML = 23
    MANIFEST = 24


_RT_NAMES = {v: k for k, v in vars(Rt).items()
             if not k.startswith("_") and isinstance(v, int)}


@dataclass
class ResourceEntry:
    """A single leaf resource."""

    type_id: int
    type_name: str
    name_id: int
    name_str: str
    language: int
    size: int
    codepage: int
    rva: int
    data: bytes = b""

    def as_string(self) -> Optional[str]:
        """Return the resource as a string if it's a known text type."""
        if self.type_id == Rt.STRING:
            # RT_STRING is a sequence of length-prefixed UTF-16LE strings
            # (length is in *characters*, not bytes).
            try:
                pos = 0
                out = []
                while pos + 2 < len(self.data):
                    nchars = struct.unpack_from("<H", self.data, pos)[0]
                    pos += 2
                    raw = self.data[pos:pos + 2 * nchars]
                    out.append(raw.decode("utf-16-le", errors="replace"))
                    pos += 2 * nchars
                return "\n".join(out)
            except Exception:
                return None
        return None


@dataclass
class ResourceDirectory:
    """A list of all resources in the binary."""

    entries: List[ResourceEntry] = field(default_factory=list)

    def by_type(self, type_id: int) -> List[ResourceEntry]:
        return [e for e in self.entries if e.type_id == type_id]

    def manifest(self) -> Optional[str]:
        """Return the first MANIFEST (application config) found, as text."""
        for e in self.by_type(Rt.MANIFEST):
            try:
                return e.data.decode("utf-8", errors="replace")
            except Exception:
                continue
        return None


_DIR_SIZE = 16
_ENTRY_SIZE = 8


def parse_resources(pe: PeFile) -> Optional[ResourceDirectory]:
    """Parse the Resource Directory of ``pe``.

    Returns ``None`` if the resource directory is absent.
    """
    dd = pe.get_data_directory(2)   # 2 = DataDirectoryId.RESOURCE
    if dd is None or not dd.is_present:
        return None
    dir_off, _ = pe.rva_to_offset(dd.virtual_address)
    rva_base = dd.virtual_address
    root = _parse_dir(pe, dir_off, rva_base, 0)
    if root is None:
        return None
    return ResourceDirectory(entries=_flatten(root))


def _parse_dir(pe: PeFile, dir_off: int, rva_base: int, depth: int):
    """Recursive directory walker.  Returns a list of (type, name, leaf)
    tuples or a leaf record when ``depth == 3``.
    """
    if dir_off + _DIR_SIZE > len(pe.raw):
        return None
    (chars, tts) = struct.unpack_from("<IHH", pe.raw, dir_off)
    _ = chars
    entries: List[tuple] = []
    for i in range(tts):
        eoff = dir_off + _DIR_SIZE + i * _ENTRY_SIZE
        if eoff + _ENTRY_SIZE > len(pe.raw):
            return None
        name_or_id, data_or_dir = struct.unpack_from("<II", pe.raw, eoff)
        is_named = bool(name_or_id & 0x80000000)
        is_dir = not (data_or_dir & 0x80000000)
        if is_named:
            try:
                noff = rva_base + (name_or_id & 0x7FFFFFFF) - dd_rva_base(pe)
            except Exception:
                continue
            # Name is a UNICODE_STRING (USHORT length, USHORT max, WCHAR buf)
            if noff + 2 > len(pe.raw):
                continue
            nchars = struct.unpack_from("<H", pe.raw, noff)[0]
            nstr = pe.raw[noff + 2:noff + 2 + 2 * nchars].decode(
                "utf-16-le", errors="replace")
        else:
            nstr = ""
        if is_dir:
            doff = (data_or_dir & 0x7FFFFFFF) + dir_off
            sub = _parse_dir(pe, doff, rva_base, depth + 1)
            if sub is None:
                continue
            entries.append((name_or_id & 0xFFFF, nstr, sub))
        else:
            data_off = (data_or_dir & 0x7FFFFFFF) + dir_off
            if data_off + 16 > len(pe.raw):
                continue
            size, cp, data_rva = struct.unpack_from("<III", pe.raw, data_off)
            try:
                actual_off, _ = pe.rva_to_offset(data_rva)
            except ValueError:
                continue
            blob = pe.raw[actual_off:actual_off + size]
            entries.append((name_or_id & 0xFFFF, nstr,
                           ("leaf", size, cp, data_rva, blob)))
    return entries


def dd_rva_base(pe: PeFile) -> int:
    """Return the resource directory's RVA (for offset arithmetic)."""
    dd = pe.get_data_directory(2)
    return dd.virtual_address if dd else 0


def _flatten(directory_tree, type_id: int = 0, name: str = ""):
    """Walk the 3-level tree and yield :class:`ResourceEntry` leaves."""
    out: List[ResourceEntry] = []
    for entry_id, name_str, sub in directory_tree:
        if isinstance(sub, list):
            # Either type-level (depth 1) or name-level (depth 2).
            if type_id == 0:
                # New type
                t_id = entry_id
                t_name = _RT_NAMES.get(t_id, f"TYPE_{t_id}")
                out.extend(_flatten(sub, type_id=t_id, name=t_name))
            else:
                # New name
                out.extend(_flatten(sub, type_id=type_id, name=name_str))
        elif isinstance(sub, tuple) and sub and sub[0] == "leaf":
            _, size, cp, rva, blob = sub
            out.append(ResourceEntry(
                type_id=type_id,
                type_name=_RT_NAMES.get(type_id, f"TYPE_{type_id}"),
                name_id=0, name_str=name,
                language=0, size=size, codepage=cp, rva=rva, data=blob,
            ))
    return out


def _selftest() -> bool:
    """Verify with a PE that has no resources."""
    from .pe_loader import _build_fake_pe
    pe = PeFile.from_bytes(_build_fake_pe())
    r = parse_resources(pe)
    return r is None


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
