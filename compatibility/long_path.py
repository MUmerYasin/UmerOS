r"""
Umer OS /compatibility/long_path — Win32 extended-length path handling
====================================================================

The Win32 file API supports two **extended-length** path prefixes:

* ``\\?\D:\path\to\file`` — disabled path parsing (no normalization,
  no ``..`` resolution, no current-directory relativity, length up
  to 32 767 chars).
* ``\\.\D:\path\to\file`` — same as above but reserved for device
  namespace; the path refers to a *device* (e.g. ``\\.\C:``) when
  the prefix is the only thing preceding the colon.

UNC extended-length paths look like ``\\?\UNC\server\share\path``.

This module parses such paths into a structured :class:`LongPath`
dataclass and offers round-trip helpers (``to_string`` and
``to_native``) that the rest of the compatibility layer can use to
either *preserve* the extended-length semantics or strip the prefix
when handing the path to the POSIX host.

The implementation is intentionally host-agnostic: we never assume
the path is valid; malformed input is returned as
:class:`LongPath.raw_path = <input>` with the ``prefix`` field set
to :data:`PREFIX_NONE`.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file#maxpath
* https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Tuple


class LongPathPrefix(IntEnum):
    NONE = 0
    WIN32_EXTENDED = 1     # \\?\ ...
    WIN32_DEVICE = 2       # \\.\ ...
    WIN32_UNC = 3          # \\?\UNC\ ...
    WIN32_DEVICE_UNC = 4   # \\.\UNC\ ...

    def __str__(self) -> str:
        return {
            LongPathPrefix.NONE: "",
            LongPathPrefix.WIN32_EXTENDED: "\\\\?\\",
            LongPathPrefix.WIN32_DEVICE: "\\\\.\\",
            LongPathPrefix.WIN32_UNC: "\\\\?\\UNC\\",
            LongPathPrefix.WIN32_DEVICE_UNC: "\\\\.\\UNC\\",
        }[self]


@dataclass(frozen=True)
class LongPath:
    """A parsed Win32 path with optional extended-length prefix."""

    prefix: LongPathPrefix
    drive: Optional[str] = None        # 'C' / 'c' for drive-relative
    is_unc: bool = False
    server: Optional[str] = None
    share: Optional[str] = None
    path_parts: Tuple[str, ...] = field(default_factory=tuple)
    raw_path: str = ""

    # ------------------------------------------------------------------
    # Pretty-printer
    # ------------------------------------------------------------------

    def to_string(self) -> str:
        if self.prefix in (LongPathPrefix.WIN32_EXTENDED,
                           LongPathPrefix.WIN32_DEVICE):
            prefix = str(self.prefix)
            if self.is_unc:
                return prefix + "UNC\\" + "\\".join(
                    [self.server or "", self.share or "", *self.path_parts]
                ).rstrip("\\")
            if self.drive:
                return prefix + self.drive.upper() + ":\\" + \
                    "\\".join(self.path_parts)
            return prefix + "\\".join(self.path_parts)
        if self.prefix in (LongPathPrefix.WIN32_UNC,
                           LongPathPrefix.WIN32_DEVICE_UNC):
            prefix = str(self.prefix)
            return prefix + "\\".join(
                [self.server or "", self.share or "", *self.path_parts]
            ).rstrip("\\")
        return self.raw_path

    def to_native(self) -> str:
        """Drop the prefix and return the path the POSIX host understands."""
        if self.prefix == LongPathPrefix.NONE:
            return self.raw_path
        if self.is_unc:
            return "\\\\" + (self.server or "") + "\\" + \
                (self.share or "") + "\\" + "\\".join(self.path_parts)
        if self.drive:
            return self.drive.upper() + ":\\" + "\\".join(self.path_parts)
        return "\\".join(self.path_parts)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_EXT_PREFIXES = ("\\\\?\\", "\\\\.\\")
_DRIVE_LETTER_RE = re.compile(r"^([A-Za-z]):")


def parse_long_path(s: str) -> LongPath:
    """Parse ``s`` into a :class:`LongPath`.

    The parser is deliberately lenient: anything that does not look
    like an extended-length path is returned as ``prefix=NONE`` with
    ``raw_path=s`` and the drive / UNC fields populated when
    recognisable.
    """
    if not s:
        return LongPath(prefix=LongPathPrefix.NONE, raw_path=s)

    raw = s
    # Normalise the *prefix detection only* — everything below is
    # treated case-insensitively.
    upper = s.replace("/", "\\")
    prefix = LongPathPrefix.NONE
    rest = upper

    # NB: literal Windows prefixes use 4 backslashes in Python source
    # (two for the raw backslash, two for the escape); e.g. ``"\\\\?\\"``
    # represents the actual 4-character prefix ``\\?\``.
    for pfx, kind in (("\\\\?\\UNC\\", LongPathPrefix.WIN32_UNC),
                      ("\\\\.\\UNC\\", LongPathPrefix.WIN32_DEVICE_UNC),
                      ("\\\\?\\", LongPathPrefix.WIN32_EXTENDED),
                      ("\\\\.\\", LongPathPrefix.WIN32_DEVICE)):
        if upper.startswith(pfx):
            prefix = kind
            rest = upper[len(pfx):]
            break

    if prefix in (LongPathPrefix.WIN32_UNC,
                  LongPathPrefix.WIN32_DEVICE_UNC):
        # \\?\UNC\server\share\path
        parts = [p for p in rest.split("\\") if p]
        if len(parts) >= 2:
            return LongPath(
                prefix=prefix,
                is_unc=True,
                server=parts[0],
                share=parts[1],
                path_parts=tuple(parts[2:]),
                raw_path=raw,
            )
        # Malformed UNC extended path.
        return LongPath(prefix=prefix, raw_path=raw)

    # Drive path: ?\C:\foo\bar
    m = _DRIVE_LETTER_RE.match(rest)
    if m:
        drive = m.group(1)
        after = rest[m.end():].lstrip("\\")
        parts = tuple(p for p in after.split("\\") if p)
        return LongPath(
            prefix=prefix,
            drive=drive,
            path_parts=parts,
            raw_path=raw,
        )

    # Non-drive extended path: \\?\foo\bar
    parts = tuple(p for p in rest.split("\\") if p)
    return LongPath(
        prefix=prefix,
        path_parts=parts,
        raw_path=raw,
    )


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def make_extended(drive: str, parts: Tuple[str, ...]) -> str:
    """Return an extended-length path for a drive + relative components."""
    return str(LongPathPrefix.WIN32_EXTENDED) + drive.upper() + ":\\" + \
        "\\".join(parts)


def make_extended_unc(server: str, share: str,
                      parts: Tuple[str, ...]) -> str:
    """Return an extended-length UNC path."""
    return str(LongPathPrefix.WIN32_UNC) + "\\".join(
        [server, share] + list(parts)
    ).rstrip("\\")


# ---------------------------------------------------------------------------
# POSIX integration helpers
# ---------------------------------------------------------------------------

MAX_WIN32_PATH = 260
MAX_WIN32_LONG_PATH = 32_767


def is_too_long_for_win32(s: str) -> bool:
    """Return ``True`` if ``s`` exceeds the legacy Win32 path limit."""
    return len(s) >= MAX_WIN32_PATH


def needs_extended_prefix(s: str) -> bool:
    """Return ``True`` if ``s`` must be wrapped in ``\\?\`` to round-trip
    through the Win32 API without truncation."""
    return is_too_long_for_win32(s)


def wrap_if_needed(s: str, *, drive: Optional[str] = None,
                   is_unc: bool = False) -> str:
    """Return ``s`` unchanged if it fits in 260 chars, else wrap it.

    ``drive`` and ``is_unc`` are required when wrapping; otherwise
    the function falls back to ``\\?\`` + the literal path.
    """
    if not needs_extended_prefix(s):
        return s
    if is_unc and drive is None:
        return make_extended_unc("", "", tuple(s.split("\\")))
    if drive:
        parts = tuple(p for p in s.replace("/", "\\").split("\\") if p)
        # Strip a redundant leading "X:" so we don't double the drive.
        if parts and parts[0].rstrip(":").upper() == drive.upper():
            parts = parts[1:]
        return make_extended(drive, parts)
    return str(LongPathPrefix.WIN32_EXTENDED) + s


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    p = parse_long_path(r"\\?\C:\Windows\System32\kernel32.dll")
    if p.prefix != LongPathPrefix.WIN32_EXTENDED or p.drive != "C":
        return False
    if p.path_parts != ("Windows", "System32", "kernel32.dll"):
        return False
    if p.to_string() != r"\\?\C:\Windows\System32\kernel32.dll":
        return False
    if p.to_native() != r"C:\Windows\System32\kernel32.dll":
        return False

    p = parse_long_path(r"\\?\UNC\server\share\dir\file.txt")
    if p.prefix != LongPathPrefix.WIN32_UNC:
        return False
    if not p.is_unc or p.server != "server" or p.share != "share":
        return False
    if p.path_parts != ("dir", "file.txt"):
        return False
    if p.to_string() != r"\\?\UNC\server\share\dir\file.txt":
        return False
    if p.to_native() != r"\\server\share\dir\file.txt":
        return False

    # Device prefix.
    p = parse_long_path(r"\\.\COM1")
    if p.prefix != LongPathPrefix.WIN32_DEVICE:
        return False
    # No drive / UNC fields, raw preserved.
    if p.to_native() != r"COM1":
        return False

    # Mixed separators.
    p = parse_long_path(r"\\?\C:/Windows/System32")
    if p.prefix != LongPathPrefix.WIN32_EXTENDED or p.drive != "C":
        return False
    if p.path_parts != ("Windows", "System32"):
        return False

    # No prefix -- raw passthrough.
    p = parse_long_path(r"C:\Windows")
    if p.prefix != LongPathPrefix.NONE:
        return False
    if p.drive != "C":
        return False

    # Empty input.
    p = parse_long_path("")
    if p.prefix != LongPathPrefix.NONE:
        return False

    # wrap_if_needed.
    short = r"C:\Windows"
    if wrap_if_needed(short, drive="C") != short:
        return False
    long = "C:\\" + "\\".join(["a" * 50] * 10)        # > 260 chars
    wrapped = wrap_if_needed(long, drive="C")
    if not wrapped.startswith("\\\\?\\C:\\"):
        return False
    # Wrapped extended paths can be > 260 chars -- that's the point.
    if len(wrapped) <= MAX_WIN32_PATH:
        return False

    # make_extended / make_extended_unc round-trip via parse.
    s = make_extended("d", ("foo", "bar"))
    p = parse_long_path(s)
    if p.drive != "D" or p.path_parts != ("foo", "bar"):
        return False
    s = make_extended_unc("srv", "sh", ("x", "y"))
    p = parse_long_path(s)
    if not p.is_unc or p.server != "srv" or p.share != "sh":
        return False
    if p.path_parts != ("x", "y"):
        return False

    # is_too_long_for_win32.
    if is_too_long_for_win32("x" * (MAX_WIN32_PATH - 1)):
        return False
    if not is_too_long_for_win32("x" * MAX_WIN32_PATH):
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
