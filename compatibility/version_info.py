"""
Umer OS /compatibility/version_info — VS_VERSIONINFO resource parser
====================================================================

Pure-Python implementation of the Win32 *version resource* surface::

    GetFileVersionInfoA / GetFileVersionInfoW   (load the blob)
    GetFileVersionInfoSizeA / GetFileVersionInfoSizeW
    VerQueryValueA / VerQueryValueW             (pull out a sub-block)

We do not implement the Win32 functions literally; instead we return
the parsed tree so callers can do::

    info = parse_version_info(blob_from_pe)
    print(info.file_version, info.product_version, info.company_name)

Layout (Microsoft spec)::

    VS_VERSIONINFO (root)
      ├─ VS_FIXEDFILEINFO        (binary; 52 bytes)
      └─ StringFileInfo
          ├─ StringTable (one per language/codepage)
          │   ├─ CompanyName
          │   ├─ FileDescription
          │   ├─ FileVersion
          │   ├─ InternalName
          │   ├─ LegalCopyright
          │   ├─ OriginalFilename
          │   ├─ ProductName
          │   └─ ProductVersion
      └─ VarFileInfo
          └─ Translation (array of LANGID/CODEPAGE pairs)

The resource is a tree of ``VERSIONNODE`` structures stored
back-to-back; each node is::

    WORD cbNode      (size of this node + children)
    WORD cbData      (size of value; 0 if binary node has no value)
    WCHAR szKey[]   (utf-16le, null-terminated)
    WORD Padding1[] (align Value to 32-bit boundary)
    BYTE Value[cbData]
    WORD Padding2[] (align Children to 32-bit boundary)
    BYTE Children[]

References
----------

* https://learn.microsoft.com/en-us/windows/win32/menurc/vs-versioninfo
* https://learn.microsoft.com/en-us/windows/win32/menurc/stringfileinfo

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.VersionInfo")

# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VsFixedFileInfo:
    """The binary header of ``VS_VERSIONINFO`` (always 52 bytes)."""

    signature: int
    struct_version: int
    file_version_ms: int
    file_version_ls: int
    product_version_ms: int
    product_version_ls: int
    file_flags_mask: int
    file_flags: int
    file_os: int
    file_type: int
    file_subtype: int
    file_date_ms: int
    file_date_ls: int

    @property
    def file_version(self) -> str:
        return _quad_to_str(self.file_version_ms, self.file_version_ls)

    @property
    def product_version(self) -> str:
        return _quad_to_str(self.product_version_ms, self.product_version_ls)


@dataclass(frozen=True)
class VersionStringTable:
    """One ``StringTable`` (keyed by language/codepage hex string)."""
    lang_cp: str                    # e.g. "040904b0"
    entries: Dict[str, str] = field(default_factory=dict)


@dataclass
class VersionInfo:
    """The whole parsed ``VS_VERSIONINFO`` block."""

    fixed: Optional[VsFixedFileInfo] = None
    string_tables: List[VersionStringTable] = field(default_factory=list)
    translation: List[Tuple[int, int]] = field(default_factory=list)
    raw_key: str = ""

    @property
    def file_version(self) -> str:
        if self.fixed:
            return self.fixed.file_version
        # Fall back to the first StringTable's FileVersion, if any.
        for st in self.string_tables:
            if st.entries.get("FileVersion"):
                return st.entries["FileVersion"]
        return ""

    @property
    def product_version(self) -> str:
        if self.fixed:
            return self.fixed.product_version
        for st in self.string_tables:
            if st.entries.get("ProductVersion"):
                return st.entries["ProductVersion"]
        return ""

    def find_string(self, name: str) -> Optional[str]:
        """Return ``name`` from the first StringTable that defines it."""
        for st in self.string_tables:
            v = st.entries.get(name)
            if v:
                return v
        return None

    # Convenience accessors.
    def company_name(self) -> str:        return self.find_string("CompanyName") or ""
    def file_description(self) -> str:    return self.find_string("FileDescription") or ""
    def original_filename(self) -> str:   return self.find_string("OriginalFilename") or ""
    def product_name(self) -> str:        return self.find_string("ProductName") or ""
    def legal_copyright(self) -> str:     return self.find_string("LegalCopyright") or ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _quad_to_str(ms: int, ls: int) -> str:
    """Combine the 16-bit halves of a 64-bit version into a dotted string."""
    hi = (ms >> 16) & 0xFFFF
    lo = ms & 0xFFFF
    hi2 = (ls >> 16) & 0xFFFF
    lo2 = ls & 0xFFFF
    return f"{hi}.{lo}.{hi2}.{lo2}"


def _dword_align(offset: int) -> int:
    """Round ``offset`` up to the nearest 32-bit boundary."""
    return (offset + 3) & ~3


def _wchar_at(buf: bytes, off: int) -> Tuple[str, int]:
    """Decode a NUL-terminated UTF-16LE string; return ``(text, next_off)``."""
    end = off
    while end + 1 < len(buf):
        if buf[end] == 0 and buf[end + 1] == 0:
            break
        end += 2
    text = buf[off:end].decode("utf-16-le", errors="replace")
    return text, end + 2          # +2 to skip NUL


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

@dataclass
class _Node:
    """Tree node used while parsing."""
    key: str
    value: bytes
    children: List["_Node"] = field(default_factory=list)


def _parse_node(buf: bytes, base: int, end: int, level: int = 0
                ) -> Optional[_Node]:
    """Parse one node (and any children) starting at ``base``.

    Returns ``None`` when there is not enough space for a header.
    """
    if base + 6 > end:
        return None
    cb_node, cb_data, _w_type = struct.unpack_from("<HHH", buf, base)
    if cb_node < 6 or base + cb_node > end + 4:
        return None
    key, after_key = _wchar_at(buf, base + 6)
    after_key = _dword_align(after_key)
    # Value.
    value = b""
    if cb_data:
        value = bytes(buf[after_key:after_key + cb_data])
    after_value = _dword_align(after_key + cb_data)
    # Children follow immediately.
    node = _Node(key=key, value=value)
    cursor = after_value
    while cursor < base + cb_node:
        # Save the cb_node of the next child *before* recursing so we
        # can advance to the sibling with the *real* encoded size,
        # which is more robust than recomputing ``_node_size``.
        if cursor + 2 > end:
            break
        child_cb_node = struct.unpack_from("<H", buf, cursor)[0]
        if child_cb_node < 6:
            break
        child = _parse_node(buf, cursor, base + cb_node, level + 1)
        if child is None:
            break
        node.children.append(child)
        cursor += child_cb_node
    return node


def _aligned_after_value(buf: bytes, node: _Node) -> int:
    """Helper used during tests."""
    # Compute the offset right after the Value field (with alignment).
    # Not used in hot paths -- kept for documentation.
    return 0


def parse_version_info(blob: bytes) -> Optional[VersionInfo]:
    """Parse a raw ``VS_VERSIONINFO`` blob.

    Returns ``None`` if the blob is too small or malformed.
    """
    if len(blob) < 6 + 32:    # header + at least the szKey
        return None
    cb_node, cb_data, w_type = struct.unpack_from("<HHH", blob, 0)
    if cb_node < 6 or cb_node > len(blob) + 4:
        return None
    if w_type not in (0, 1):
        return None
    key, after_key = _wchar_at(blob, 6)
    if key != "VS_VERSION_INFO":
        return None
    after_key = _dword_align(after_key)

    fixed: Optional[VsFixedFileInfo] = None
    value = b""
    if cb_data and len(blob) >= after_key + cb_data:
        value = bytes(blob[after_key:after_key + cb_data])
    after_value = _dword_align(after_key + cb_data)

    # Parse the FixedFileInfo (52 bytes when present).
    if len(value) >= 52:
        signature = int.from_bytes(value[:4], "little")
        if signature == 0xFEEF04BD:
            (signature, struct_version, file_ms, file_ls, prod_ms, prod_ls,
             flags_mask, flags, file_os, file_type, file_subtype,
             date_ms, date_ls) = struct.unpack_from("<13I", value, 0)
            fixed = VsFixedFileInfo(
                signature=signature, struct_version=struct_version,
                file_version_ms=file_ms, file_version_ls=file_ls,
                product_version_ms=prod_ms, product_version_ls=prod_ls,
                file_flags_mask=flags_mask, file_flags=flags,
                file_os=file_os, file_type=file_type,
                file_subtype=file_subtype,
                file_date_ms=date_ms, file_date_ls=date_ls,
            )

    # Walk the children for StringFileInfo / VarFileInfo.
    cursor = after_value
    out = VersionInfo(raw_key=key, fixed=fixed)
    while cursor < len(blob):
        child = _parse_node(blob, cursor, len(blob))
        if child is None:
            break
        _harvest(child, out)
        cursor += _advance_past(blob, cursor, len(blob))
    return out


def _harvest(node: _Node, out: VersionInfo) -> None:
    """Walk a parsed tree and populate ``out``."""
    if node.key == "StringFileInfo":
        for st_node in node.children:
            if st_node.key:
                st = VersionStringTable(lang_cp=st_node.key)
                for entry in st_node.children:
                    if entry.key and entry.value:
                        # value is UTF-16LE NUL-terminated.
                        text = entry.value.decode("utf-16-le",
                                                   errors="replace")
                        text = text.rstrip("\x00").rstrip("\x00")
                        st.entries[entry.key] = text
                out.string_tables.append(st)
    elif node.key == "VarFileInfo":
        for var in node.children:
            if var.key == "Translation" and len(var.value) >= 4:
                # Each entry is a 32-bit LANGID/CODEPAGE pair.
                for i in range(0, len(var.value) - 3, 4):
                    lang, cp = struct.unpack_from("<HH", var.value, i)
                    out.translation.append((lang, cp))


def _advance_past(buf: bytes, start: int, end: int) -> int:
    """Return how many bytes a node at ``start`` consumes."""
    if start + 6 > end:
        return end - start
    cb_node = struct.unpack_from("<H", buf, start)[0]
    if cb_node < 6:
        return 6
    return cb_node


# ---------------------------------------------------------------------------
# Win32-shaped facade
# ---------------------------------------------------------------------------

def GetFileVersionInfoSize(blob: bytes) -> int:
    return len(blob)


def VerQueryValue(blob: bytes, sub_block: str
                  ) -> Optional[Tuple[str, object]]:
    """Return ``(key_kind, value)`` for common ``\\\\<sub-block>`` queries.

    The Win32 function returns a void pointer; the caller uses the
    key to interpret it.  We mirror that by returning a kind tag
    plus a Python value.
    """
    parsed = parse_version_info(blob)
    if parsed is None:
        return None
    if sub_block == "\\":
        return ("root", parsed)
    if sub_block == "\\StringFileInfo":
        return ("StringFileInfo",
                [st.entries for st in parsed.string_tables])
    if sub_block == "\\VarFileInfo":
        return ("VarFileInfo", parsed.translation)
    if sub_block == "\\StringFileInfo\\040904b0":
        for st in parsed.string_tables:
            if st.lang_cp == "040904b0":
                return ("StringFileInfo", st.entries)
    if sub_block.startswith("\\StringFileInfo\\"):
        cp = sub_block[len("\\StringFileInfo\\"):]
        for st in parsed.string_tables:
            if st.lang_cp.lower() == cp.lower():
                return ("StringFileInfo", st.entries)
        return None
    return None


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

_FIXTURE = (
    # cbNode (filled in at end) -- placeholder; will compute.
    # We craft the actual bytes in _selftest below to keep alignment right.
    b""
)


def _build_fixture() -> bytes:
    """Build a hand-crafted VS_VERSIONINFO blob for testing.

    The layout follows the Microsoft spec::

        VS_VERSIONINFO (root, wType=0, Value=VS_FIXEDFILEINFO)
        ├─ StringFileInfo (wType=1)
        │   └─ StringTable "040904b0" (wType=1)
        │       ├─ CompanyName "Umer OS Project" (wType=1)
        │       ├─ FileDescription "selftest pe"
        │       ├─ FileVersion "1.2.3.4"
        │       ├─ InternalName "umeros_test"
        │       ├─ LegalCopyright "(c) 2026"
        │       ├─ OriginalFilename "test.dll"
        │       ├─ ProductName "UmerOS selftest"
        │       └─ ProductVersion "1.2.3.0"
        └─ VarFileInfo (wType=1)
            └─ Translation (wType=0) = {0x0409, 0x04b0}
    """
    def wstr(s: str) -> bytes:
        return s.encode("utf-16-le") + b"\x00\x00"

    def w32_boundary(n: int) -> int:
        return (n + 3) & ~3

    def leaf(k: str, v: str) -> bytes:
        """A text leaf (szKey, utf-16le string value)."""
        kdata = wstr(k)
        vdata = wstr(v)
        # Header: cbNode placeholder (2), cbData (2), wType (2)
        # Body: szKey + align + Value + align
        body = struct.pack("<HHH", 0, len(vdata), 1)
        body += kdata
        # align before Value
        body += b"\x00" * (w32_boundary(len(body)) - len(body))
        body += vdata
        body += b"\x00" * (w32_boundary(len(body)) - len(body))
        # Patch cbNode (size of full node)
        body = struct.pack("<H", len(body)) + body[2:]
        return body

    def container(k: str, children: bytes) -> bytes:
        """A text container (szKey, no value, wType=1)."""
        kdata = wstr(k)
        body = struct.pack("<HHH", 0, 0, 1)
        body += kdata
        body += b"\x00" * (w32_boundary(len(body)) - len(body))
        body += children
        body = struct.pack("<H", len(body)) + body[2:]
        return body

    def binary_leaf(k: str, value: bytes) -> bytes:
        """A binary leaf (szKey, value=bytes, wType=0)."""
        kdata = wstr(k)
        body = struct.pack("<HHH", 0, len(value), 0)
        body += kdata
        body += b"\x00" * (w32_boundary(len(body)) - len(body))
        body += value
        body += b"\x00" * (w32_boundary(len(body)) - len(body))
        body = struct.pack("<H", len(body)) + body[2:]
        return body

    pairs = [
        ("CompanyName", "Umer OS Project"),
        ("FileDescription", "selftest pe"),
        ("FileVersion", "1.2.3.4"),
        ("InternalName", "umeros_test"),
        ("LegalCopyright", "(c) 2026"),
        ("OriginalFilename", "test.dll"),
        ("ProductName", "UmerOS selftest"),
        ("ProductVersion", "1.2.3.0"),
    ]
    string_entries = b"".join(leaf(k, v) for k, v in pairs)
    table = container("040904b0", string_entries)
    sfi = container("StringFileInfo", table)
    trans = struct.pack("<HH", 0x0409, 0x04b0)
    var_entry = binary_leaf("Translation", trans)
    vfi = container("VarFileInfo", var_entry)

    ffi = struct.pack(
        "<13I",
        0xFEEF04BD,
        0x00010000,
        (1 << 16) | 2,
        (3 << 16) | 4,
        (5 << 16) | 6,
        (7 << 16) | 8,
        0x3F, 0x00, 0x40004, 0x02, 0, 0, 0,
    )

    # Root: wType=0 (binary), Value=ffi, Children=(sfi, vfi).
    body = struct.pack("<HHH", 0, len(ffi), 0)
    body += wstr("VS_VERSION_INFO")
    body += b"\x00" * (w32_boundary(len(body)) - len(body))
    body += ffi
    body += b"\x00" * (w32_boundary(len(body)) - len(body))
    body += sfi + vfi
    body = struct.pack("<H", len(body)) + body[2:]
    return body


def _selftest() -> bool:
    blob = _build_fixture()
    if len(blob) < 100:
        return False
    info = parse_version_info(blob)
    if info is None:
        return False
    if info.fixed is None:
        return False
    if info.fixed.file_version != "1.2.3.4":
        return False
    if info.fixed.product_version != "5.6.7.8":
        return False
    if info.company_name() != "Umer OS Project":
        return False
    if info.file_description() != "selftest pe":
        return False
    if info.product_name() != "UmerOS selftest":
        return False
    if info.original_filename() != "test.dll":
        return False
    if not info.string_tables:
        return False
    if info.string_tables[0].lang_cp != "040904b0":
        return False
    if info.string_tables[0].entries.get("FileVersion") != "1.2.3.4":
        return False
    if (0x0409, 0x04b0) not in info.translation:
        return False

    # VerQueryValue-style lookup.
    q = VerQueryValue(blob, "\\StringFileInfo\\040904b0")
    if q is None or q[0] != "StringFileInfo":
        return False
    entries = q[1]
    if not isinstance(entries, dict):
        return False
    if entries.get("FileVersion") != "1.2.3.4":
        return False

    # Malformed blob returns None.
    if parse_version_info(b"\x00\x00") is not None:
        return False
    if parse_version_info(b"") is not None:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
