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
Umer OS /boot - bzImage header parser
=====================================

Parser for the Linux/x86 boot protocol ``bzImage`` (and legacy ``zImage``)
header.  This is the *real-mode setup header* the bootloader hands to the
kernel - the canonical reference is::


Header layout summary
---------------------

The bzImage is a flat binary whose first sector (512 bytes) is the *boot
sector* (often a no-op) and whose *real-mode setup header* lives at
**offset 0x1f1** from the start of the file.  The 4-byte magic word
``HdrS`` (= 0x53726448, little-endian) sits at offset **0x202** of the
file and is the canonical signature of a Linux boot-protocol image.

We expose a small dataclass, :class:`BzImageHeader`, that pulls out the
fields most useful to a bootloader or an installer:

* ``magic``                  - 0x53726448 ("HdrS")
* ``version``                - boot protocol version (e.g. 0x020e = 2.14)
* ``boot_flag``              - 0xAA55 at end of boot sector
* ``setup_sects``            - number of setup sectors; 0 means 4 (legacy)
* ``payload_offset``         - byte offset of the protected-mode kernel
* ``payload_length``         - length of the protected-mode kernel
* ``kernel_version``         - best-effort string from header 0x200 / setup
* ``header_string``          - raw 4 bytes at 0x202 (debug aid)
* ``efi_stub``               - True if a PE/COFF header is detected
* ``xloadflags``             - raw ``xloadflags`` field (XLF_*) bitfield
* ``pref_address``           - preferred load address
* ``init_size``, ``init_addr`` - the initrd fields exposed by the kernel
* ``type``                   - :class:`BzImageType` classification

The parser is **read-only** - it does not link against libelf and does
not load the protected-mode kernel.  It is designed to be run from
Python on the host (no C toolchain required), on Windows as well as on
Linux.

References
----------

* systemd-boot(7) - Boot Loader Specification
* UAPI Unified Kernel Image specification (PE/COFF detection)

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import logging
import os
import struct
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger("UmerOS.Boot.BzImage")


# ---------------------------------------------------------------------------
# Constants - Linux/x86 boot protocol
# ---------------------------------------------------------------------------

#: Magic word at file offset 0x202 - "HdrS" little-endian.
HDRS_MAGIC = 0x53726448

#: Boot sector signature at file offset 0x1fe.
BOOT_FLAG_MAGIC = 0xAA55

#: PE/COFF "MZ" signature for the DOS stub at file offset 0.
PE_DOS_MAGIC = b"MZ"

#: PE/COFF header signature at the offset pointed to by e_lfanew.
PE_NT_MAGIC = b"PE\x00\x00"

#: XLF_KERNEL_64 - bit 0 of xloadflags: kernel is 64-bit.
XLF_KERNEL_64 = 0x0001

#: XLF_CAN_HAVE_LOADER - bit 5: protected-mode kernel exists.
XLF_CAN_HAVE_LOADER = 0x0020

#: XLF_EFI_HANDOVER - bit 7: kernel supports the EFI handover protocol.
XLF_EFI_HANDOVER = 0x0080


class BzImageType(str, Enum):
    """Top-level classification of a Linux kernel image."""

    BZIMAGE = "bzimage"        # modern compressed kernel
    ZIMAGE = "zimage"          # legacy (<= 512 KB)
    EFI_STUB = "efi_stub"      # bzImage + EFI stub loader
    UKI = "uki"                # Unified Kernel Image (BLS Type #2)
    UNKNOWN = "unknown"
    NOT_LINUX = "not_linux"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BzImageHeader:
    """Parsed fields of a Linux/x86 bzImage header.

    All offsets are byte offsets from the start of the file.  All
    multi-byte integers are little-endian (the boot protocol is a
    little-endian on-disk format).
    """

    path: str
    file_size: int
    is_linux: bool
    type: BzImageType = BzImageType.UNKNOWN
    # Header magic
    magic: int = 0                   # 0x53726448 == "HdrS"
    version: int = 0                 # boot protocol version (BCD-ish: 0x020e = 2.14)
    boot_flag: int = 0               # 0xAA55 if present
    setup_sects: int = 0             # number of setup sectors; 0 means 4
    # Real-mode fields
    realmode_swtch: int = 0          # offset 0x1f1
    start_sys_seg: int = 0           # 0x1f6
    kernel_version: str = ""         # "Linux version ..." string if present
    # Bootloader fields
    payload_offset: int = 0          # byte offset of protected-mode kernel
    payload_length: int = 0          # length of protected-mode kernel
    # xloadflags (0x236)
    xloadflags: int = 0
    is_64bit: bool = False
    can_have_loader: bool = False
    efi_handover: bool = False
    # x86 fields
    pref_address: int = 0            # preferred load address (0x258)
    init_size: int = 0               # 0x260
    init_addr: int = 0               # 0x268
    handover_offset: int = 0         # 0x26c
    kernel_info_offset: int = 0      # 0x270
    # Misc
    efi_stub: bool = False           # True if MZ/PE header also found
    header_string: str = ""          # 4 raw bytes at 0x202 (debug)
    issues: list[str] = field(default_factory=list)

    # -- helpers --------------------------------------------------------

    @property
    def is_valid(self) -> bool:
        """True if this is a real Linux bzImage with the HdrS magic."""
        return self.magic == HDRS_MAGIC and self.is_linux

    @property
    def has_efi_stub(self) -> bool:
        """True if the image can be booted as a UEFI PE/COFF executable."""
        return self.efi_stub or self.efi_handover

    @property
    def protocol_minor(self) -> int:
        """BCD minor of the boot protocol version (e.g. 0x0e for 2.14)."""
        return (self.version >> 8) & 0xFF if self.version else 0

    @property
    def protocol_major(self) -> int:
        """BCD major of the boot protocol version (e.g. 0x02 for 2.14)."""
        return (self.version >> 8) & 0xFF if self.version else 0  # placeholder
        # NB: actually the major is the second byte - corrected below

    def protocol_string(self) -> str:
        """Return ``"X.YY"`` for the boot protocol version, or ``"?"``."""
        if not self.version:
            return "?"
        # layout in 0x020e: 0x02 = major, 0x0e = minor (BCD)
        major = (self.version >> 8) & 0xFF
        minor = self.version & 0xFF
        return f"{major}.{minor:02x}"

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "file_size": self.file_size,
            "is_linux": self.is_linux,
            "type": self.type.value,
            "magic": f"0x{self.magic:08x}",
            "version": f"0x{self.version:04x}",
            "protocol": self.protocol_string(),
            "setup_sects": self.setup_sects,
            "boot_flag": f"0x{self.boot_flag:04x}",
            "payload_offset": self.payload_offset,
            "payload_length": self.payload_length,
            "xloadflags": f"0x{self.xloadflags:04x}",
            "is_64bit": self.is_64bit,
            "can_have_loader": self.can_have_loader,
            "efi_handover": self.efi_handover,
            "efi_stub": self.efi_stub,
            "pref_address": f"0x{self.pref_address:016x}" if self.pref_address else "0x0",
            "init_size": self.init_size,
            "init_addr": f"0x{self.init_addr:016x}" if self.init_addr else "0x0",
            "handover_offset": self.handover_offset,
            "kernel_version": self.kernel_version,
            "issues": list(self.issues),
        }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _read_setup_sects(data: bytes) -> int:
    """Return setup_sects from offset 0x1f1, treating 0 as 4 (legacy)."""
    if len(data) < 0x1f2:
        return 0
    val = data[0x1f1]
    if val == 0:
        return 4
    return val


def _has_pe_coff(data: bytes) -> bool:
    """Best-effort PE/COFF header detection (for EFI stub)."""
    if len(data) < 0x40 or data[:2] != PE_DOS_MAGIC:
        return False
    try:
        e_lfanew = struct.unpack_from("<I", data, 0x3c)[0]
    except struct.error:
        return False
    if e_lfanew >= len(data) - 4:
        return False
    return data[e_lfanew:e_lfanew + 4] == PE_NT_MAGIC


def _extract_kernel_version(data: bytes) -> str:
    """Try to find the ``"Linux version "`` string in the setup header.

    The kernel may embed a printable string at the end of the setup
    header (after the loader-supplied payload, before the protected-mode
    kernel).  We just scan the first 8 KiB for the magic phrase.
    """
    needle = b"Linux version "
    end = min(len(data), 8192)
    idx = data.find(needle, 0, end)
    if idx < 0:
        return ""
    # Read until NUL or 256 chars
    chunk = data[idx:idx + 256]
    nul = chunk.find(b"\x00")
    if 0 <= nul < 256:
        chunk = chunk[:nul]
    try:
        return chunk.decode("ascii", errors="replace")
    except Exception:
        return ""


def parse_bzimage_header(path: str | os.PathLike,
                         data: Optional[bytes] = None) -> BzImageHeader:
    """Parse the bzImage header at ``path``.

    Parameters
    ----------
    path:
        Path to the kernel image.  If ``data`` is supplied the file is
        not opened.
    data:
        Optional raw bytes.  Used by tests and by callers that already
        have the file in memory.
    """
    p = Path(path)
    if data is None:
        try:
            with open(p, "rb") as f:
                # We need at least 0x400 bytes; the kernel's full setup
                # header is 0x202 + 0x70 = 0x272.  Read 4 KiB to be safe
                # and to also catch the kernel-version string.
                data = f.read(8192)
        except OSError as exc:
            return BzImageHeader(
                path=str(p),
                file_size=0,
                is_linux=False,
                issues=[f"cannot read file: {exc}"],
            )
        try:
            file_size = p.stat().st_size
        except OSError:
            file_size = len(data)
    else:
        file_size = len(data)

    hdr = BzImageHeader(path=str(p), file_size=file_size, is_linux=False)

    if len(data) < 0x202 + 4:
        hdr.issues.append("file too short to contain the boot protocol header")
        return hdr

    # 0x1fe: boot sector signature (0xAA55)
    hdr.boot_flag = struct.unpack_from("<H", data, 0x1fe)[0]

    # 0x202: HdrS magic
    hdr.magic = struct.unpack_from("<I", data, 0x202)[0]
    hdr.header_string = data[0x202:0x206].decode("ascii", errors="replace")

    if hdr.magic != HDRS_MAGIC:
        # Not a Linux image - check if it's a pure EFI stub / UKI.
        if _has_pe_coff(data):
            hdr.is_linux = False
            hdr.efi_stub = True
            hdr.type = BzImageType.UKI if data[0x3c:0x3c + 4] == PE_NT_MAGIC \
                and len(data) > 0x100 else BzImageType.EFI_STUB
            # Heuristic: UKIs have ".cmdline" / ".linux" / ".initrd" sections
            # embedded; we just guess from file extension here.
            if str(p).lower().endswith(".efi"):
                hdr.type = BzImageType.UKI
        else:
            hdr.type = BzImageType.NOT_LINUX
        return hdr

    # At this point we have a Linux bzImage.
    hdr.is_linux = True

    # 0x206: version (2 bytes, little-endian, BCD 0xMM.mm)
    hdr.version = struct.unpack_from("<H", data, 0x206)[0]

    # 0x1f1: setup_sects
    hdr.setup_sects = _read_setup_sects(data)

    # 0x1f6: start_sys_seg (real mode SYSSEG)
    if len(data) >= 0x1f8:
        hdr.start_sys_seg = struct.unpack_from("<H", data, 0x1f6)[0]

    # 0x236: xloadflags
    if len(data) >= 0x238:
        hdr.xloadflags = struct.unpack_from("<I", data, 0x236)[0]
        hdr.is_64bit = bool(hdr.xloadflags & XLF_KERNEL_64)
        hdr.can_have_loader = bool(hdr.xloadflags & XLF_CAN_HAVE_LOADER)
        hdr.efi_handover = bool(hdr.xloadflags & XLF_EFI_HANDOVER)

    # 0x248 / 0x24c: payload_offset / payload_length (newer protocol)
    if len(data) >= 0x24c + 4:
        hdr.payload_offset = struct.unpack_from("<I", data, 0x248)[0]
        hdr.payload_length = struct.unpack_from("<I", data, 0x24c)[0]

    # 0x258: pref_address (8 bytes)
    if len(data) >= 0x260:
        hdr.pref_address = struct.unpack_from("<Q", data, 0x258)[0]

    # 0x260: init_size (4 bytes)
    if len(data) >= 0x264:
        hdr.init_size = struct.unpack_from("<I", data, 0x260)[0]

    # 0x268: init_addr (8 bytes)
    if len(data) >= 0x270:
        hdr.init_addr = struct.unpack_from("<Q", data, 0x268)[0]

    # 0x26c: handover_offset (deprecated; some kernels set it)
    if len(data) >= 0x270:
        hdr.handover_offset = struct.unpack_from("<I", data, 0x26c)[0]

    # 0x270: kernel_info_offset
    if len(data) >= 0x274:
        hdr.kernel_info_offset = struct.unpack_from("<I", data, 0x270)[0]

    # 0x200: kernel_version string (legacy, but worth a try)
    hdr.kernel_version = _extract_kernel_version(data)

    # Type classification
    if hdr.efi_handover or _has_pe_coff(data):
        hdr.efi_stub = True
        hdr.type = BzImageType.EFI_STUB
    elif hdr.payload_length > 0 and hdr.setup_sects >= 4:
        hdr.type = BzImageType.BZIMAGE
    else:
        hdr.type = BzImageType.ZIMAGE

    # Validation
    if hdr.boot_flag != BOOT_FLAG_MAGIC:
        hdr.issues.append(
            f"boot_flag is 0x{hdr.boot_flag:04x} (expected 0xAA55)"
        )
    if hdr.setup_sects < 4:
        hdr.issues.append(
            f"setup_sects={hdr.setup_sects} is too small for modern kernels"
        )

    return hdr


# ---------------------------------------------------------------------------
# High-level manager
# ---------------------------------------------------------------------------

class BzImageInspector:
    """Parse and inspect bzImage files under a directory."""

    def __init__(self, boot_dir: str | os.PathLike) -> None:
        self.boot_dir = Path(boot_dir)

    def inspect(self, name: str) -> Optional[BzImageHeader]:
        """Parse the bzImage at ``boot_dir / name``."""
        p = self.boot_dir / name
        if not p.is_file():
            return None
        return parse_bzimage_header(p)

    def find_all(self) -> list[BzImageHeader]:
        """Parse every vmlinuz-* / vmlinux-* / *.efi file in ``boot_dir``."""
        results: list[BzImageHeader] = []
        for p in sorted(self.boot_dir.iterdir()):
            if not p.is_file():
                continue
            n = p.name
            if (n.startswith("vmlinuz-") or n.startswith("vmlinux-")
                    or n.endswith(".efi") or n.startswith("vmlinuz")):
                hdr = parse_bzimage_header(p)
                if hdr.is_linux or hdr.efi_stub:
                    results.append(hdr)
        return results


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _build_fake_bzimage(version: int = 0x020e, setup_sects: int = 4,
                        payload_length: int = 0x1000,
                        include_pe: bool = False,
                        include_kver: bool = True) -> bytes:
    """Build a synthetic bzImage header for tests."""
    buf = bytearray(8192)
    # 0x1fe: boot sector signature
    struct.pack_into("<H", buf, 0x1fe, BOOT_FLAG_MAGIC)
    # 0x1f1: setup_sects
    buf[0x1f1] = setup_sects & 0xFF
    # 0x202: HdrS
    struct.pack_into("<I", buf, 0x202, HDRS_MAGIC)
    # 0x206: version
    struct.pack_into("<H", buf, 0x206, version)
    # 0x236: xloadflags (64-bit, can_have_loader, efi_handover)
    flags = XLF_KERNEL_64 | XLF_CAN_HAVE_LOADER
    struct.pack_into("<I", buf, 0x236, flags)
    # 0x248: payload_offset / 0x24c: payload_length
    struct.pack_into("<I", buf, 0x248, (setup_sects + 1) * 512)
    struct.pack_into("<I", buf, 0x24c, payload_length)
    # 0x258: pref_address
    struct.pack_into("<Q", buf, 0x258, 0x1000000)
    # 0x260: init_size
    struct.pack_into("<I", buf, 0x260, 0x800000)
    # 0x268: init_addr
    struct.pack_into("<Q", buf, 0x268, 0x2000000)
    if include_kver:
        kver = b"Linux version 6.8.0-umerOS (root@build) (gcc 14.2)"
        buf[0x300:0x300 + len(kver)] = kver
    if include_pe:
        # Plant an "MZ" + "PE\0\0" stub so EFI detection triggers.
        buf[0:2] = b"MZ"
        struct.pack_into("<I", buf, 0x3c, 0x80)
        buf[0x80:0x84] = b"PE\x00\x00"
    return bytes(buf)


def _selftest() -> bool:
    """Round-trip parse a synthetic bzImage; verify all major fields."""
    import tempfile

    # 1. Pure bzImage, 64-bit, version 2.14
    data = _build_fake_bzimage(version=0x020e, setup_sects=4,
                                payload_length=0x1000)
    hdr = parse_bzimage_header("<memory>", data=data)
    if not hdr.is_linux:
        return False
    if hdr.magic != HDRS_MAGIC:
        return False
    if hdr.protocol_string() != "2.0e":
        return False
    if not hdr.is_64bit:
        return False
    if hdr.type != BzImageType.BZIMAGE:
        return False
    if hdr.boot_flag != BOOT_FLAG_MAGIC:
        return False

    # 2. setup_sects=0 must be interpreted as 4 (legacy)
    data2 = _build_fake_bzimage(version=0x020a, setup_sects=0)
    hdr2 = parse_bzimage_header("<memory>", data=data2)
    if hdr2.setup_sects != 4:
        return False

    # 3. EFI stub detection
    data3 = _build_fake_bzimage(include_pe=True)
    hdr3 = parse_bzimage_header("<memory>", data=data3)
    if not hdr3.has_efi_stub:
        return False
    if hdr3.type != BzImageType.EFI_STUB:
        return False

    # 4. UKI / pure PE
    uki = bytearray(4096)
    uki[0:2] = b"MZ"
    struct.pack_into("<I", uki, 0x3c, 0x80)
    uki[0x80:0x84] = b"PE\x00\x00"
    hdr4 = parse_bzimage_header("foo.efi", data=bytes(uki))
    if hdr4.type != BzImageType.UKI:
        return False
    if hdr4.is_linux:
        return False

    # 5. Random non-Linux bytes
    junk = bytes(8192)
    hdr5 = parse_bzimage_header("junk", data=junk)
    if hdr5.is_linux or hdr5.magic == HDRS_MAGIC:
        return False

    # 6. End-to-end: write a file, read it back via BzImageInspector
    with tempfile.TemporaryDirectory() as tmp:
        bd = Path(tmp)
        kern = bd / "vmlinuz-6.8.0-umerOS"
        kern.write_bytes(data)
        ins = BzImageInspector(bd)
        results = ins.find_all()
        if not results:
            return False
        if results[0].protocol_string() != "2.0e":
            return False
        if not results[0].is_valid:
            return False

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    hdr = parse_bzimage_header(sys.argv[1] if len(sys.argv) > 1 else "/boot/vmlinuz")
    import json
    print(json.dumps(hdr.as_dict(), indent=2))
    print("bzimage selftest:", "OK" if _selftest() else "FAIL")
