"""
Umer OS /compatibility/shell_links — Shell Link (.lnk) parser
============================================================

Pure-Python implementation of the Win32 *Shell Link* parser used
to read ``.lnk`` files (the Windows shortcut format).

A ``.lnk`` file is a structured binary blob with::

    SHELL_LINK_HEADER          (76 bytes; always present)
    [LINK_TARGET_IDLIST]       (optional; HasLinkTargetIDList flag)
    [LINK_INFO]                (optional; HasLinkInfo flag)
    [STRING_DATA]*             (one per set flag: name, relative-path,
                                working-dir, args, icon-location)
    [EXTRA_DATA]*              (extra blocks: Tracker, Vista+ IDs,
                                PropertyStore, ...)

The header is fixed-width.  Each subsequent structure has a flag in
``LinkFlags`` that signals whether it is present.

We intentionally implement the parser only; installers commonly
*create* ``.lnk`` files (IShellLinkW::SetPath) but we accept any
"shape" and produce a structured :class:`ShellLink` view.

References
----------

* https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.ShellLinks")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHELL_LINK_HEADER_SIZE = 0x0000004C
SHELL_LINK_CLSID       = (0x00021401, 0x0000, 0x0000,
                          0xC0, 0x00, 0x00, 0x00, 0x00,
                          0x00, 0x00, 0x00, 0x46)

# LinkFlags bits.
HAS_LINK_TARGET_IDLIST    = 0x00000001
HAS_LINK_INFO             = 0x00000002
HAS_NAME                  = 0x00000004
HAS_RELATIVE_PATH         = 0x00000008
HAS_WORKING_DIR           = 0x00000010
HAS_ARGUMENTS             = 0x00000020
HAS_ICON_LOCATION         = 0x00000040
IS_UNICODE                = 0x00000080
FORCE_NO_LINKINFO         = 0x00000100
HAS_EXP_STRING            = 0x00000200
IS_INDOOR_TARGET          = 0x00000400
PREFER_ENVIRONMENT_PATH   = 0x00000800
RUN_WITH_SHIM_LAYER       = 0x00001000
FORCE_DONT_LINKINFO       = 0x00002000
HAS_DARWIN_ID             = 0x00004000
RUN_AS_USER               = 0x00008000
HAS_EXP_ICON              = 0x00010000
NO_PIDL_ALIAS             = 0x00020000
HAS_UNICODE_NAME          = 0x00040000
FORCE_NO_LINKTRACK        = 0x00080000
ENABLE_TARGET_METADATA    = 0x00100000
DONT_RESOLVE_LINK         = 0x00400000
HAS_METADATA              = 0x00800000

# FileAttributes bits (subset).
FILE_ATTRIBUTE_READONLY   = 0x00000001
FILE_ATTRIBUTE_HIDDEN     = 0x00000002
FILE_ATTRIBUTE_SYSTEM     = 0x00000004
FILE_ATTRIBUTE_DIRECTORY  = 0x00000010
FILE_ATTRIBUTE_ARCHIVE    = 0x00000020
FILE_ATTRIBUTE_NORMAL     = 0x00000080


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass
class ShellLinkHeader:
    """The fixed-width 76-byte header."""

    header_size: int = SHELL_LINK_HEADER_SIZE
    link_clsid: tuple = field(default_factory=lambda: SHELL_LINK_CLSID)
    link_flags: int = 0
    file_attributes: int = 0
    creation_time: int = 0     # FILETIME, 0 if absent
    access_time: int = 0
    write_time: int = 0
    file_size: int = 0
    icon_index: int = 0
    show_command: int = 0      # SW_SHOWNORMAL etc.
    hot_key: int = 0
    reserved: int = 0


@dataclass
class LinkInfo:
    """Local-volume link information (volume id + local path)."""

    volume_id: bytes = b""           # 4 bytes drive serial + 4 path prefix
    local_base_path: str = ""
    network_share_name: str = ""
    common_path_suffix: str = ""

    @property
    def drive_letter(self) -> str:
        if len(self.volume_id) >= 4:
            return ""
        return ""

    def full_local_path(self) -> str:
        if self.network_share_name:
            return f"\\\\{self.network_share_name}\\{self.common_path_suffix}"
        return self.local_base_path + self.common_path_suffix


@dataclass
class StringData:
    name: str = ""
    relative_path: str = ""
    working_dir: str = ""
    command_line_args: str = ""
    icon_location: str = ""


@dataclass
class ExtraData:
    """Variable-length extra block(s).

    We surface the parsed tracker block (Vista+) and the property
    store version.
    """

    tracker: bytes = b""
    property_store_version: int = 0


@dataclass
class ShellLink:
    """Top-level parsed shortcut."""

    header: ShellLinkHeader = field(default_factory=ShellLinkHeader)
    link_info: Optional[LinkInfo] = None
    link_target_idlist_size: int = 0
    strings: StringData = field(default_factory=StringData)
    extra: ExtraData = field(default_factory=ExtraData)
    raw: bytes = b""

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def target_path(self) -> str:
        if self.link_info is None:
            return ""
        return self.link_info.full_local_path()

    @property
    def is_unicode(self) -> bool:
        return bool(self.header.link_flags & IS_UNICODE)

    @property
    def file_size_bytes(self) -> int:
        return self.header.file_size

    def attribute_names(self) -> List[str]:
        names = []
        if self.header.file_attributes & FILE_ATTRIBUTE_READONLY:
            names.append("READONLY")
        if self.header.file_attributes & FILE_ATTRIBUTE_HIDDEN:
            names.append("HIDDEN")
        if self.header.file_attributes & FILE_ATTRIBUTE_SYSTEM:
            names.append("SYSTEM")
        if self.header.file_attributes & FILE_ATTRIBUTE_DIRECTORY:
            names.append("DIRECTORY")
        if self.header.file_attributes & FILE_ATTRIBUTE_ARCHIVE:
            names.append("ARCHIVE")
        return names


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _read_cstring(buf: bytes, off: int) -> Tuple[str, int]:
    end = off
    while end < len(buf) and buf[end] != 0:
        end += 1
    return buf[off:end].decode("ascii", errors="replace"), end + 1


def _read_wstring(buf: bytes, off: int, char_count: int) -> Tuple[str, int]:
    """Decode a UTF-16LE string of ``char_count`` characters."""
    raw = buf[off:off + char_count * 2]
    text = raw.decode("utf-16-le", errors="replace")
    return text, off + char_count * 2


def parse_shell_link(blob: bytes) -> Optional[ShellLink]:
    """Parse a ``.lnk`` blob into a :class:`ShellLink`.

    Returns ``None`` if the header signature is missing.
    """
    if len(blob) < SHELL_LINK_HEADER_SIZE:
        return None
    (header_size, _cls1, _cls2, _cls3, _cls4,
     _cls5, _cls6, _cls7, _cls8, _cls9, _cls10,
     _cls11, _cls12,
     link_flags, file_attrs, ctime, atime, wtime,
     file_size, icon_index, show_command,
     hot_key, _reserved) = struct.unpack_from(
        "<IIHHHHHHHHHHHHIIQQIIQ", blob, 0)
    # Validate.
    if header_size != SHELL_LINK_HEADER_SIZE:
        return None
    clsid = (_cls1, _cls2, _cls3, _cls4, _cls5, _cls6, _cls7, _cls8,
             _cls9, _cls10, _cls11, _cls12)
    if clsid != SHELL_LINK_CLSID:
        return None
    out = ShellLink(
        raw=bytes(blob),
        header=ShellLinkHeader(
            header_size=header_size,
            link_clsid=clsid,
            link_flags=link_flags,
            file_attributes=file_attrs,
            creation_time=ctime,
            access_time=atime,
            write_time=wtime,
            file_size=file_size,
            icon_index=icon_index,
            show_command=show_command,
            hot_key=hot_key,
            reserved=_reserved,
        ),
    )

    cursor = SHELL_LINK_HEADER_SIZE

    # LinkTargetIDList
    if link_flags & HAS_LINK_TARGET_IDLIST:
        if cursor + 2 > len(blob):
            return out
        size = struct.unpack_from("<H", blob, cursor)[0]
        out.link_target_idlist_size = size
        cursor += 2 + size
    # LinkInfo
    if link_flags & HAS_LINK_INFO:
        out.link_info, consumed = _parse_link_info(blob, cursor)
        cursor += consumed
    # String data.
    out.strings = _parse_string_data(blob, cursor, link_flags)
    return out


def _parse_link_info(buf: bytes, off: int) -> Tuple[Optional[LinkInfo], int]:
    if off + 28 > len(buf):
        return None, 0
    (size, hdr_size, flags, vol_id_off, local_base_off,
     common_path_off) = struct.unpack_from("<IIIII", buf, off)
    info = LinkInfo()
    cursor = off + hdr_size
    # Volume ID block (size + data).
    if vol_id_off:
        vol_abs = off + vol_id_off
        if vol_abs + 4 <= len(buf):
            info.volume_id = bytes(buf[vol_abs:vol_abs + 4])
        # Drive letter offset 4 bytes into the block.
        if vol_abs + 8 <= len(buf):
            drive_letter, _ = _read_cstring(buf, vol_abs + 4)
            info.volume_id = info.volume_id + bytes([ord(drive_letter) or 0])
    if local_base_off:
        abs_off = off + local_base_off
        if abs_off < len(buf):
            s, _ = _read_cstring(buf, abs_off)
            info.local_base_path = s
    if common_path_off:
        abs_off = off + common_path_off
        if abs_off < len(buf):
            s, _ = _read_cstring(buf, abs_off)
            info.common_path_suffix = s
    return info, size


def _parse_string_data(buf: bytes, off: int, flags: int) -> StringData:
    out = StringData()
    is_unicode = bool(flags & IS_UNICODE)
    if flags & HAS_NAME:
        out.name, off = _read_one_string(buf, off, is_unicode)
    if flags & HAS_RELATIVE_PATH:
        out.relative_path, off = _read_one_string(buf, off, is_unicode)
    if flags & HAS_WORKING_DIR:
        out.working_dir, off = _read_one_string(buf, off, is_unicode)
    if flags & HAS_ARGUMENTS:
        out.command_line_args, off = _read_one_string(buf, off, is_unicode)
    if flags & HAS_ICON_LOCATION:
        out.icon_location, off = _read_one_string(buf, off, is_unicode)
    return out


def _read_one_string(buf: bytes, off: int, unicode: bool
                     ) -> Tuple[str, int]:
    if off + 2 > len(buf):
        return "", off
    chars = struct.unpack_from("<H", buf, off)[0]
    off += 2
    if unicode:
        return _read_wstring(buf, off, chars)
    end = off + chars
    text = buf[off:end].decode("ascii", errors="replace")
    return text, end


# ---------------------------------------------------------------------------
# Builder (used by tests + IShellLink emulation)
# ---------------------------------------------------------------------------

def build_shell_link(target: str,
                     *,
                     working_dir: str = "",
                     arguments: str = "",
                     icon_path: str = "",
                     description: str = "",
                     file_attributes: int = FILE_ATTRIBUTE_ARCHIVE,
                     file_size: int = 0) -> bytes:
    """Build a minimal valid ``.lnk`` blob for the given target path.

    Used by tests and as the seed for the IShellLink façade in
    :mod:`win_shell`.  The header flags declare ``IsUnicode`` plus
    whatever string fields are non-empty.
    """
    flags = IS_UNICODE | HAS_LINK_INFO
    if working_dir:
        flags |= HAS_WORKING_DIR
    if arguments:
        flags |= HAS_ARGUMENTS
    if icon_path:
        flags |= HAS_ICON_LOCATION
    if description:
        flags |= HAS_NAME

    out = bytearray(SHELL_LINK_HEADER_SIZE)
    # Header.
    struct.pack_into("<I", out, 0, SHELL_LINK_HEADER_SIZE)
    out[4:20] = b"\x01\x14\x02\x00" + b"\x00" * 10 + b"\x46"
    struct.pack_into("<I", out, 24, flags)
    struct.pack_into("<I", out, 28, file_attributes)
    struct.pack_into("<Q", out, 32, 0)        # creation time
    struct.pack_into("<Q", out, 40, 0)        # access time
    struct.pack_into("<Q", out, 48, 0)        # write time
    struct.pack_into("<I", out, 56, file_size)
    struct.pack_into("<I", out, 60, 0)        # icon index
    struct.pack_into("<H", out, 64, 1)        # show command (SW_SHOWNORMAL)
    struct.pack_into("<H", out, 66, 0)        # hot key

    # LinkInfo: minimal volume-id + local base path.
    link_info_off = len(out)
    # Reserve 28 bytes for the LinkInfo header.
    out += b"\x00" * 28
    link_info_size = 28
    # Local base path.
    base_off = link_info_size
    local = target.encode("utf-16-le" if target else "ascii") + b"\x00\x00"
    if target and not target.startswith("\\\\"):
        # ASCII for the LinkInfo volume-id block.
        local = target.encode("ascii", errors="replace") + b"\x00"
    out += local
    link_info_size += len(local)
    # Volume-id block (4 bytes drive serial + 1 byte drive letter + NUL).
    vol_off = link_info_size
    out += struct.pack("<I", 0)            # drive serial
    out += bytes([0]) + b"\x00"           # drive letter, NUL
    link_info_size += 6
    # Back-fill LinkInfo header.
    struct.pack_into("<I", out, link_info_off, link_info_size)
    struct.pack_into("<I", out, link_info_off + 4, 28)
    struct.pack_into("<I", out, link_info_off + 8, 0)
    struct.pack_into("<I", out, link_info_off + 12, vol_off)
    struct.pack_into("<I", out, link_info_off + 16, base_off)
    struct.pack_into("<I", out, link_info_off + 20, base_off)

    # String data (Unicode, length-prefixed).
    def add_unicode_string(s: str) -> None:
        nonlocal out
        encoded = s.encode("utf-16-le")
        out += struct.pack("<H", len(s)) + encoded
    if description:
        add_unicode_string(description)
    if working_dir:
        add_unicode_string(working_dir)
    if arguments:
        add_unicode_string(arguments)
    if icon_path:
        add_unicode_string(icon_path)

    return bytes(out)


# ---------------------------------------------------------------------------
# Win32 facade (the IShellLinkW / IPersistFile pair)
# ---------------------------------------------------------------------------

def IShellLinkW_SetPath(link: ShellLink, path: str) -> None:
    """Apply :func:`IShellLinkW::SetPath` semantics to a parsed link."""
    if link.link_info is None:
        link.link_info = LinkInfo()
    link.link_info.common_path_suffix = path
    link.link_info.network_share_name = ""
    link.link_info.local_base_path = ""


def IShellLinkW_GetPath(link: ShellLink) -> str:
    return link.target_path


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    blob = build_shell_link(
        "C:\\Windows\\notepad.exe",
        working_dir="C:\\Windows",
        arguments=r"test.txt",
        description="Open test.txt",
    )
    link = parse_shell_link(blob)
    if link is None:
        return False
    if link.target_path != "C:\\Windows\\notepad.exe":
        return False
    if link.strings.working_dir != "C:\\Windows":
        return False
    if link.strings.command_line_args != r"test.txt":
        return False
    if link.strings.name != "Open test.txt":
        return False
    if "ARCHIVE" not in link.attribute_names():
        return False
    # Truncated blob returns None.
    if parse_shell_link(b"") is not None:
        return False
    if parse_shell_link(b"MZ" + b"\x00" * 100) is not None:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
