"""
Umer OS /compatibility/win_strings — UNICODE_STRING and friends
=============================================================

Windows uses UTF-16LE strings almost everywhere in its internal
APIs (kernel-mode and user-mode native APIs).  Two of the most
common wire formats are:

* ``UNICODE_STRING`` (16-bit, length in bytes, optional null
  terminator).  Used in ``ntdll`` and the kernel.  Layout::

      typedef struct _UNICODE_STRING {
          USHORT Length;         // length in bytes (excluding the null)
          USHORT MaximumLength;   // buffer size in bytes (incl. null)
          PWSTR  Buffer;         // pointer to UTF-16LE chars
      } UNICODE_STRING;

* ``LSA_UNICODE_STRING`` (32-bit length, otherwise identical).  Used
  by ``Secur32.dll`` / ``LSA``.

This module provides:

* a pure-Python :class:`UnicodeString` dataclass that wraps a UTF-16LE
  string and exposes ``.length_bytes`` / ``.max_bytes`` / ``.text`` /
  a ``to_bytes()`` serialiser and ``from_bytes()`` parser;
* a separate :class:`LsaUnicodeString` (32-bit lengths);
* a tiny ``wide_str()`` / ``from_wide()`` helper for the common
  round-trip case where no explicit length prefix is needed.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/ntdef/ns-ntdef-_unicode_string
* https://learn.microsoft.com/en-us/windows/win32/api/lsalookup/ns-lsalookup-lsa_unicode_string

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


def wide_str(s: str) -> bytes:
    """Encode ``s`` as a *null-terminated* UTF-16LE string."""
    return (s + "\0").encode("utf-16-le")


def from_wide(blob: bytes) -> str:
    """Decode a *null-terminated* UTF-16LE string."""
    end = blob.find(b"\x00\x00")
    if end < 0:
        end = len(blob)
    return blob[:end].decode("utf-16-le", errors="replace")


@dataclass
class UnicodeString:
    """A 16-bit Windows ``UNICODE_STRING``.

    * ``text``         - the actual UTF-16-decoded text.
    * ``max_chars``    - size of the backing buffer in characters
                         (not bytes).  Includes the optional NUL.
    """

    text: str
    max_chars: Optional[int] = None

    def __post_init__(self) -> None:
        if "\0" in self.text:
            raise ValueError(
                "UnicodeString must not contain an embedded NUL; "
                "the null terminator is implicit."
            )
        if self.max_chars is None:
            # Default to text + 1 NUL.
            self.max_chars = len(self.text) + 1
        if self.max_chars < len(self.text) + 1:
            raise ValueError(
                "max_chars must be at least len(text) + 1 (null terminator)"
            )

    @property
    def length_bytes(self) -> int:
        """``Length`` field: bytes used by ``text`` (no NUL)."""
        return len(self.text) * 2

    @property
    def max_bytes(self) -> int:
        """``MaximumLength`` field: total buffer size in bytes (incl. NUL)."""
        return self.max_chars * 2

    def to_bytes(self) -> bytes:
        """Serialise as the on-wire ``UNICODE_STRING`` payload.

        The format is::

            USHORT Length;
            USHORT MaximumLength;
            WCHAR  Buffer[MaxChars];

        Returned buffer is ``Length + 2`` bytes (text + NUL).
        """
        payload = (self.text + "\0").encode("utf-16-le")
        return payload

    @classmethod
    def from_bytes(cls, blob: bytes, *, has_max: bool = True) -> "UnicodeString":
        """Parse a serialised UNICODE_STRING (caller supplies the length
        prefix if present).

        Args:
            blob:  raw UTF-16LE bytes (no NUL required but accepted).
            has_max: ignored; the caller is expected to strip the
                     length prefix before calling this.
        """
        del has_max
        text = from_wide(blob)
        return cls(text=text, max_chars=(len(blob) // 2))


@dataclass
class LsaUnicodeString:
    """A 32-bit ``LSA_UNICODE_STRING`` (32-bit ``Length`` / ``MaximumLength``)."""

    text: str
    max_chars: Optional[int] = None

    def __post_init__(self) -> None:
        if "\0" in self.text:
            raise ValueError(
                "LsaUnicodeString must not contain an embedded NUL"
            )
        if self.max_chars is None:
            self.max_chars = len(self.text) + 1
        if self.max_chars < len(self.text) + 1:
            raise ValueError("max_chars too small")

    @property
    def length_bytes(self) -> int:
        return len(self.text) * 2

    @property
    def max_bytes(self) -> int:
        return self.max_chars * 2

    def to_bytes(self) -> bytes:
        return (self.text + "\0").encode("utf-16-le")

    @classmethod
    def from_bytes(cls, blob: bytes) -> "LsaUnicodeString":
        return cls(text=from_wide(blob),
                   max_chars=(len(blob) // 2))


# ---------------------------------------------------------------------------
# ANSI / wide string conversion helpers
# ---------------------------------------------------------------------------

def ansi_to_wide(s: str, *, codepage: str = "cp1252") -> bytes:
    """Convert an ANSI string (Windows code page 1252 by default) to UTF-16LE.

    Used when parsing Win32 ANSI APIs (rare in modern code, but still
    used by the registry / GDI / etc.).
    """
    return s.encode(codepage)


def wide_to_ansi(blob: bytes, *, codepage: str = "cp1252") -> str:
    """Decode a UTF-16LE string to ANSI (Windows code page 1252)."""
    return from_wide(blob).encode(codepage).decode(codepage)


__all__ = [
    "UnicodeString",
    "LsaUnicodeString",
    "wide_str",
    "from_wide",
    "ansi_to_wide",
    "wide_to_ansi",
]
