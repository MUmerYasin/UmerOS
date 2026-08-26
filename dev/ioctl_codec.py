# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
UmerOS /dev ioctl codec — exact include/uapi/asm-generic/ioctl.h layout.

32-bit command word:
    dir  (2 bits)  << 30   00 none | 01 userland-writes | 10 userland-reads
    size(14 bits)  << 16   sizeof(data_type), max 16383 (8191 practical)
    type(8 bits)   <<  8   driver magic letter/number
    nr  (8 bits)   <<  0   command serial number

Builders mirror _IO/_IOR/_IOW/_IOWR; decode() reverses any raw value.
"""

from __future__ import annotations

from typing import Any, Dict


class IoctlCodec:

    NR_BITS = 8
    TYPE_BITS = 8
    SIZE_BITS = 14
    DIR_BITS = 2

    NR_SHIFT = 0
    TYPE_SHIFT = NR_SHIFT + NR_BITS          # 8
    SIZE_SHIFT = TYPE_SHIFT + TYPE_BITS      # 16
    DIR_SHIFT = SIZE_SHIFT + SIZE_BITS       # 30

    DIR_NONE = 0
    DIR_WRITE = 1   # userland -> kernel
    DIR_READ = 2    # kernel -> userland
    MAX_SIZE = (1 << SIZE_BITS) - 1

    KNOWN_MAGIC = {
        0x54: "'T' tty",
        0x73: "'s' serial",
        0x92: "MON_IOC usbmon",
        0xB7: "'W' watchdog",
        0x03: "HDIO",
        0x12: "SCSI_IOCTL",
        0x94: "btrfs",
        0xAE: "VFIO",
        0x3D: "'=' loop",
        0x46: "'F' fbdev",
        0x56: "'V' video4linux",
        0x4C: "'L' dm",
    }

    @classmethod
    def _ioc(cls, direction: int, itype: int, nr: int, size: int) -> int:
        checks = (("dir", direction, 0x3), ("type", itype, 0xFF),
                  ("nr", nr, 0xFF), ("size", size, cls.MAX_SIZE))
        for name, val, mask in checks:
            if not 0 <= val <= mask:
                raise ValueError(f"ioctl {name}={val} out of range")
        return (((direction & 0x3) << cls.DIR_SHIFT)
                | ((itype & 0xFF) << cls.TYPE_SHIFT)
                | ((nr & 0xFF) << cls.NR_SHIFT)
                | ((size & cls.MAX_SIZE) << cls.SIZE_SHIFT))

    @classmethod
    def io(cls, itype: int, nr: int) -> int:
        return cls._ioc(cls.DIR_NONE, itype, nr, 0)

    @classmethod
    def ior(cls, itype: int, nr: int, size: int) -> int:
        return cls._ioc(cls.DIR_READ, itype, nr, size)

    @classmethod
    def iow(cls, itype: int, nr: int, size: int) -> int:
        return cls._ioc(cls.DIR_WRITE, itype, nr, size)

    @classmethod
    def iowr(cls, itype: int, nr: int, size: int) -> int:
        return cls._ioc(cls.DIR_READ | cls.DIR_WRITE, itype, nr, size)

    @classmethod
    def decode(cls, cmd: int) -> Dict[str, Any]:
        direction = (cmd >> cls.DIR_SHIFT) & 0x3
        size = (cmd >> cls.SIZE_SHIFT) & cls.MAX_SIZE
        itype = (cmd >> cls.TYPE_SHIFT) & 0xFF
        nr = (cmd >> cls.NR_SHIFT) & 0xFF
        dir_name = {cls.DIR_NONE: "_IO", cls.DIR_WRITE: "_IOW",
                    cls.DIR_READ: "_IOR",
                    cls.DIR_READ | cls.DIR_WRITE: "_IOWR"}[direction]
        type_char = chr(itype) if 32 <= itype < 127 else str(itype)
        return {
            "raw": cmd,
            "raw_hex": f"0x{cmd:08x}",
            "direction": dir_name,
            "direction_bits": direction,
            "size": size,
            "type": itype,
            "type_char": type_char,
            "nr": nr,
            "macro": f"{dir_name}({type_char}, {nr}, {size})",
            "magic_note": cls.KNOWN_MAGIC.get(itype, "unknown magic"),
            "valid_size": size <= 8191,
        }
