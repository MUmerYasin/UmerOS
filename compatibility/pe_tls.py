"""
Umer OS /compatibility/pe_tls — Thread Local Storage (TLS) directory
=================================================================

The **TLS directory** of a PE binary lives in data-directory index
9.  It tells the loader how to set up per-thread storage and which
*TLS callbacks* to invoke at thread start / exit / DLL-attach /
DLL-detach.

Layout::

    typedef struct _IMAGE_TLS_DIRECTORY {
        ULONG StartAddressOfRawData;
        ULONG EndAddressOfRawData;
        ULONG AddressOfIndex;          // -> TLS index slot
        ULONG AddressOfCallBacks;      // -> PIMAGE_TLS_CALLBACK array
        ULONG SizeOfZeroFill;          // bytes to zero on init
        ULONG Characteristics;         // flags (see below)
    } IMAGE_TLS_DIRECTORY;            // 24 bytes (PE32) / 40 (PE32+)

``Characteristics`` flags include::

* ``IMAGE_TLS_BITMAP_DEFAULT``  (0x00000000) - aligned slot
* ``IMAGE_TLS_BITMAP_IMAGE``    (0x00000001)
* ``IMAGE_TLS_BITMAP_POINTER``  (0x00000002)
* ``IMAGE_TLS_BITMAP_DIRECT``   (0x00000004)
* ``IMAGE_TLS_VALID_64``        (0x00000040) - 64-bit addresses (PE32+)

A *callback* is a function pointer invoked for every thread that
enters or exits the DLL.  The address array is terminated by a NULL
pointer.

This module:

* parses the directory into a structured :class:`TlsDirectory`,
* enumerates the callback list.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#the-tls-directory

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional

from .pe_loader import PeFile, PeClass


class TlsBitmap:
    DEFAULT = 0x00
    IMAGE = 0x01
    POINTER = 0x02
    DIRECT = 0x04
    VALID_64 = 0x40


@dataclass
class TlsDirectory:
    """The IMAGE_TLS_DIRECTORY (32 or 64-bit) plus the callback list."""

    start_address_of_raw_data: int
    end_address_of_raw_data: int
    address_of_index: int
    address_of_callbacks: int
    size_of_zero_fill: int
    characteristics: int

    callbacks: List[int] = field(default_factory=list)

    @property
    def raw_data_size(self) -> int:
        return self.end_address_of_raw_data - self.start_address_of_raw_data

    @property
    def is_64bit(self) -> bool:
        return bool(self.characteristics & TlsBitmap.VALID_64)

    @property
    def is_pointer_based(self) -> bool:
        return bool(self.characteristics & TlsBitmap.POINTER)


def parse_tls_directory(pe: PeFile) -> Optional[TlsDirectory]:
    """Parse the TLS directory of ``pe``.

    Returns ``None`` if the TLS directory is absent.
    """
    dd = pe.get_data_directory(9)   # 9 = DataDirectoryId.TLS
    if dd is None or not dd.is_present:
        return None
    off, _ = pe.rva_to_offset(dd.virtual_address)
    if pe.optional_header.pe_class == PeClass.PE32:
        fmt = "<IIIIII"
    else:
        fmt = "<QQIIII"
    if off + struct.calcsize(fmt) > len(pe.raw):
        return None
    fields = struct.unpack_from(fmt, pe.raw, off)
    if pe.optional_header.pe_class == PeClass.PE32:
        start, end, index_addr, cbs_addr, zero_fill, chars = fields
    else:
        start, end, index_addr, cbs_addr, zero_fill, chars = fields

    # Walk the callback array.
    callbacks: List[int] = []
    if cbs_addr:
        try:
            cbs_off, _ = pe.rva_to_offset(cbs_addr)
        except ValueError:
            cbs_off = None
        if cbs_off is not None:
            word_size = 8 if pe.optional_header.pe_class == PeClass.PE32_PLUS else 4
            while cbs_off + word_size <= len(pe.raw):
                if word_size == 8:
                    val = struct.unpack_from("<Q", pe.raw, cbs_off)[0]
                else:
                    val = struct.unpack_from("<I", pe.raw, cbs_off)[0]
                if val == 0:
                    break
                callbacks.append(val)
                cbs_off += word_size

    return TlsDirectory(
        start_address_of_raw_data=start,
        end_address_of_raw_data=end,
        address_of_index=index_addr,
        address_of_callbacks=cbs_addr,
        size_of_zero_fill=zero_fill,
        characteristics=chars,
        callbacks=callbacks,
    )


def _selftest() -> bool:
    """Verify with a PE that has no TLS directory."""
    from .pe_loader import _build_fake_pe
    pe = PeFile.from_bytes(_build_fake_pe())
    if parse_tls_directory(pe) is not None:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
