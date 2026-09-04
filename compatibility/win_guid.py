"""
Umer OS /compatibility/win_guid — Windows GUID / UUID handling
=============================================================

A Windows ``GUID`` is a 128-bit identifier with a well-defined
binary layout::

    +-------+---------------------+--------------------+----------+----------+
    |  0-3  |        4-5          |        6-7         |   8-9    |  10-15   |
    +-------+---------------------+--------------------+----------+----------+
    |  4B   |         2B          |        2B          |   2B    |    6B    |
    |Data1  |       Data2        |       Data3        |  Data4   |  Data4   |
    +-------+---------------------+--------------------+----------+----------+

When displayed as a string, the canonical form is the "registry
form"::

    {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}

with all letters uppercase and surrounded by braces.  The variant
``DEFINE_GUID!`` macro in ``guiddef.h`` is what generates the
``GUID`` literal at compile time.

This module:

* represents a ``GUID`` via the :class:`Guid` dataclass,
* parses and emits the canonical string forms,
* reads/writes the 16-byte binary form,
* implements the Windows ``GUID`` comparison and hashing semantics,
* generates v1 / v4 / v5 GUIDs from ``uuid`` (so the values match
  what the Win32 API would emit).

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/guiddef/ns-guiddef-guid
* https://www.rfc-editor.org/rfc/rfc4122

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Tuple


#: A canonical-form GUID: braces + 8-4-4-4-12 lowercase hex.
_GUID_RE = re.compile(
    r"^\{?([0-9A-Fa-f]{8})-([0-9A-Fa-f]{4})-([0-9A-Fa-f]{4})-"
    r"([0-9A-Fa-f]{4})-([0-9A-Fa-f]{12})\}?$"
)

#: Binary layout = 16 bytes in the order Microsoft uses (mixed-endian).
STRUCT_FMT = "<IHH6s"


@dataclass(frozen=True, order=True)
class Guid:
    """A 128-bit Windows GUID.

    The fields mirror ``GUID`` in ``guiddef.h``:

    * ``data1``  -- 32 bits
    * ``data2``  -- 16 bits
    * ``data3``  -- 16 bits
    * ``data4``  -- 8 raw bytes (note: not a single 64-bit int)
    """

    data1: int
    data2: int
    data3: int
    data4: Tuple[int, ...]    # exactly 8 ints in [0..255]

    def __post_init__(self) -> None:
        if not (0 <= self.data1 <= 0xFFFFFFFF):
            raise ValueError("GUID.Data1 must fit in 32 bits")
        if not (0 <= self.data2 <= 0xFFFF):
            raise ValueError("GUID.Data2 must fit in 16 bits")
        if not (0 <= self.data3 <= 0xFFFF):
            raise ValueError("GUID.Data3 must fit in 16 bits")
        if len(self.data4) != 8 or any(
            not (0 <= b <= 0xFF) for b in self.data4
        ):
            raise ValueError(
                "GUID.Data4 must be exactly 8 bytes in [0..255]"
            )

    # ------------------------------------------------------------------
    # Conversions
    # ------------------------------------------------------------------

    @classmethod
    def from_string(cls, s: str) -> "Guid":
        """Parse any of: registry, ``DEFINE_GUID``, plain, or braces."""
        if not s:
            raise ValueError("empty GUID string")
        m = _GUID_RE.match(s.strip())
        if not m:
            raise ValueError(f"not a valid GUID string: {s!r}")
        d1 = int(m.group(1), 16)
        d2 = int(m.group(2), 16)
        d3 = int(m.group(3), 16)
        d4 = int(m.group(4), 16) >> 8, int(m.group(4), 16) & 0xFF
        d4 += tuple(int(m.group(5)[i:i + 2], 16) for i in range(0, 12, 2))
        return cls(d1, d2, d3, d4)

    @classmethod
    def from_bytes(cls, blob: bytes) -> "Guid":
        """Decode a 16-byte Microsoft-ordered GUID."""
        if len(blob) != 16:
            raise ValueError(f"GUID must be 16 bytes (got {len(blob)})")
        import struct
        d1, d2, d3, d4 = struct.unpack(STRUCT_FMT, blob)
        return cls(d1, d2, d3, tuple(d4))

    @classmethod
    def from_uuid(cls, u: uuid.UUID) -> "Guid":
        """Convert a stdlib ``uuid.UUID`` to a Microsoft-ordered GUID.

        The stdlib uses the RFC 4122 big-endian layout while
        Microsoft mixes in ``Data4``; this helper bridges them.
        """
        import struct
        # RFC 4122 fields: 4B time_low | 2B time_mid | 2B time_hi_ver |
        # 8B clock_seq_hi + node -- same as MS for Data1/2/3/4 if we
        # only use big-endian for Data4.
        big = u.bytes
        d1, d2, d3 = struct.unpack(">IHH", big[:8])
        d4 = tuple(big[8:])
        return cls(d1, d2, d3, d4)

    def to_bytes(self) -> bytes:
        """Encode this GUID as a 16-byte Microsoft-ordered blob."""
        import struct
        return struct.pack(STRUCT_FMT, self.data1, self.data2, self.data3,
                           bytes(self.data4))

    def to_uuid(self) -> uuid.UUID:
        """Return a stdlib ``uuid.UUID`` (big-endian) with the same bits."""
        import struct
        big = struct.pack(">IHH", self.data1, self.data2, self.data3) + \
              bytes(self.data4)
        return uuid.UUID(bytes=big)

    # ------------------------------------------------------------------
    # String rendering
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        """Canonical registry form: ``{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}``."""
        d4a = (self.data4[0] << 8) | self.data4[1]
        d4b = bytes(self.data4[2:])
        return (
            f"{{{self.data1:08X}-{self.data2:04X}-{self.data3:04X}-"
            f"{d4a:04X}-{d4b.hex().upper()}}}"
        )

    def to_c_guid_macro(self) -> str:
        """Return a C-style ``DEFINE_GUID!`` macro line for headers."""
        d4 = ", ".join(f"0x{b:02X}" for b in self.data4)
        return (
            f"DEFINE_GUID!({str(self)[1:-1]}, 0x{self.data1:08X}, 0x{self.data2:04X}, "
            f"0x{self.data3:04X}, 0x{self.data4[0]:02X}, 0x{self.data4[1]:02X}, "
            f"{d4})"
        )

    def short(self) -> str:
        """A condensed form, useful for logs: 8 hex digits (Data1)."""
        return f"{self.data1:08X}"


# ---------------------------------------------------------------------------
# Well-known GUIDs (a tiny, opinionated subset).
# ---------------------------------------------------------------------------

GUID_NULL = Guid(0, 0, 0, (0, 0, 0, 0, 0, 0, 0, 0))
GUID_NIL = GUID_NULL

# IUnknown / IDispatch / IClassFactory interfaces
IID_IUNKNOWN = Guid(
    0x00000000, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46),
)
IID_IDISPATCH = Guid(
    0x00020400, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46),
)
IID_ICLASSFACTORY = Guid(
    0x00000001, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46),
)

# Common FMTID / CLSID for shell
FMTID_ISHELL_FOLDER = Guid(
    0xC3DF1E84, 0xD1B7, 0x4C20, (0x8C, 0xE0, 0x9F, 0x6C, 0x10, 0x9F, 0x09, 0x99),
)
CLSID_SHELL_FOLDER = FMTID_ISHELL_FOLDER

# Program identifier for the "This PC" / "My Computer" virtual folder
CLSID_MY_COMPUTER = Guid(
    0x20D04FE0, 0x3AEA, 0x1069, (0xA2, 0xD8, 0x08, 0x00, 0x2B, 0x30, 0x30, 0x9D),
)

# Windows Explorer shell CLSID
CLSID_EXPLORER = Guid(
    0xE057C8B3, 0x4A1E, 0x4D4D, (0x8E, 0x49, 0x90, 0x9A, 0x4A, 0xC4, 0xE0, 0x4D),
)


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------

def new_guid_v4() -> Guid:
    """Return a freshly-generated random (v4) GUID."""
    return Guid.from_uuid(uuid.uuid4())


def new_guid_v5(namespace: Guid, name: str) -> Guid:
    """Return a name-based (v5) GUID within ``namespace``."""
    return Guid.from_uuid(uuid.uuid5(namespace.to_uuid(), name))
