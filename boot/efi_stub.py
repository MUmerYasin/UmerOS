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
Umer OS /boot - EFI stub kernel detector
========================================

Detect whether a Linux kernel image is a **Unified Kernel Image (UKI)**
or simply a bzImage compiled with ``CONFIG_EFI_STUB=y`` (so the same
file can be booted from a UEFI firmware without a separate loader).

The two flavours of EFI-bootable Linux kernel are:

* **EFI stub bzImage** - the kernel image still looks like a bzImage
  (the boot-protocol setup header is intact) but it also starts with
  a PE/COFF header so UEFI firmware can ``LoadImage`` / ``StartImage``
  it directly.  The kernel is a single ELF that *also* carries an
  embedded DOS+PE stub.  This is enabled by ``CONFIG_EFI_STUB``.

* **Unified Kernel Image (UKI)** - a single PE/COFF executable that
  bundles the EFI stub, the kernel, an initrd, the kernel command line
  and a ``.osrel`` (os-release) text section.  UKIs are placed in
  ``/EFI/Linux/<name>.efi`` per the Boot Loader Specification
  and are required to be **cryptographically signed as a single unit**
  for Secure Boot to accept them.

This module is read-only: it does **not** parse PE/COFF fully
(no COFF/optional-header decoder is required - we only need a couple
of sections).  Instead it:

* checks the DOS+PE header,
* locates the section table,
* extracts the names of every section (``SECTION_ALIGN`` up to 96 bytes
  each, UTF-8, NUL-terminated),
* matches against the canonical UKI section set
  (``.text``, ``.data``, ``.sdmagic``, ``.osrel``, ``.cmdline``,
  ``.initrd``, ``.linux``, ``.ucode``, ``.splash``, ``.dtb``,
  ``.hwids``, ``.uname``, ``.profile``, ``.bootctl``, ``.confext``,
  ``.sysext``),
* returns a dataclass describing the image.


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
from typing import List, Optional

log = logging.getLogger("UmerOS.Boot.EfiStub")


# ---------------------------------------------------------------------------
# Canonical UKI section names
# ---------------------------------------------------------------------------

#: PE/COFF section names that identify a Unified Kernel Image.
UKI_SECTIONS = {
    ".linux",       # the kernel itself
    ".initrd",      # bundled initramfs
    ".cmdline",     # kernel command line (NUL-terminated)
    ".osrel",       # os-release text
    ".splash",      # BMP splash screen
    ".dtb",         # device tree
    ".ucode",       # microcode update blob
    ".sdmagic",     # 4-byte magic identifying a UKI
    ".uname",       # kernel version string
    ".hwids",       # hardware IDs
    ".profile",     # profile number
    ".bootctl",     # bootctl section
    ".confext",     # configuration extension DDI
    ".sysext",      # system extension DDI
    ".pcrsig",      # TPM PCR signature
    ".pcrpkey",     # TPM PCR public key
}

#: Section name that should be present in *any* Linux EFI binary.
COMMON_LINUX_EFI_SECTIONS = {".text", ".data", ".bss", ".rodata"}

#: ``.sdmagic`` payload - identifies a UKI per the UKI specification.
SDMAGIC = b"\x07\x00\x00\x00\x00\x00\x00\x00"


class EfiImageType(str, Enum):
    """How the EFI firmware will see this file."""

    UNKNOWN = "unknown"
    NOT_PE = "not_pe"
    EFI_STUB_BZIMAGE = "efi_stub_bzimage"  # CONFIG_EFI_STUB
    UKI = "uki"                            # Unified Kernel Image
    OTHER_PE = "other_pe"                  # some other PE/COFF binary


@dataclass
class EfiImage:
    """Summary of a Linux EFI binary (stub or UKI)."""

    path: str
    file_size: int
    type: EfiImageType = EfiImageType.UNKNOWN
    machine: int = 0
    subsystem: int = 0
    entry_point: int = 0
    image_base: int = 0
    sections: List[str] = field(default_factory=list)
    uki_sections: List[str] = field(default_factory=list)
    has_sdmagic: bool = False
    has_osrel: bool = False
    has_cmdline: bool = False
    has_initrd: bool = False
    has_linux: bool = False
    has_splash: bool = False
    has_ucode: bool = False
    has_dtb: bool = False
    boot_loader_spec_type: int = 0   # 1 for Type #1, 2 for UKI
    issues: List[str] = field(default_factory=list)

    @property
    def is_uki(self) -> bool:
        return self.type == EfiImageType.UKI

    @property
    def is_efi_stub(self) -> bool:
        return self.type in (EfiImageType.UKI, EfiImageType.EFI_STUB_BZIMAGE)

    @property
    def is_secure_boot_signable(self) -> bool:
        """True if the image is a single PE/COFF unit (UKI or pure stub)."""
        return self.is_efi_stub

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "file_size": self.file_size,
            "type": self.type.value,
            "machine": f"0x{self.machine:04x}",
            "subsystem": f"0x{self.subsystem:04x}",
            "entry_point": f"0x{self.entry_point:016x}" if self.entry_point else "0x0",
            "image_base": f"0x{self.image_base:016x}" if self.image_base else "0x0",
            "sections": list(self.sections),
            "uki_sections": list(self.uki_sections),
            "has_sdmagic": self.has_sdmagic,
            "has_osrel": self.has_osrel,
            "has_cmdline": self.has_cmdline,
            "has_initrd": self.has_initrd,
            "has_linux": self.has_linux,
            "has_splash": self.has_splash,
            "has_ucode": self.has_ucode,
            "has_dtb": self.has_dtb,
            "boot_loader_spec_type": self.boot_loader_spec_type,
            "issues": list(self.issues),
        }


# ---------------------------------------------------------------------------
# PE/COFF field sizes
# ---------------------------------------------------------------------------

# IMAGE_FILE_MACHINE_AMD64 = 0x8664
MACHINE_AMD64 = 0x8664
# IMAGE_FILE_MACHINE_I386 = 0x14c
MACHINE_I386  = 0x014C
# IMAGE_FILE_MACHINE_AARCH64 = 0xaa64
MACHINE_AARCH64 = 0xAA64
# IMAGE_SUBSYSTEM_EFI_APPLICATION = 10
EFI_SUBSYSTEM_APPLICATION = 10
# IMAGE_SUBSYSTEM_EFI_BOOT_SERVICE_DRIVER = 11
EFI_SUBSYSTEM_BOOT_DRIVER = 11


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _read_cstr(data: bytes, offset: int, max_len: int = 256) -> str:
    end = offset + max_len
    nul = data.find(b"\x00", offset, end)
    if 0 <= nul <= end:
        chunk = data[offset:nul]
    else:
        chunk = data[offset:end]
    try:
        return chunk.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_sections(data: bytes,
                      section_table_offset: int,
                      num_sections: int,
                      size_of_optional_header: int) -> List[str]:
    """Return the list of section names in a PE/COFF image."""
    names: List[str] = []
    # Each section header is 40 bytes.
    entry_size = 40
    # Section table sits right after the optional header.
    pos = section_table_offset
    if num_sections <= 0 or num_sections > 96:
        return names
    for _ in range(num_sections):
        if pos + entry_size > len(data):
            break
        # Name is 8 bytes, NUL-padded (UTF-8).
        name_bytes = data[pos:pos + 8]
        try:
            name = name_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        except Exception:
            name = ""
        if name:
            names.append(name)
        pos += entry_size
    return names


def parse_efi_image(path: str | os.PathLike,
                    data: Optional[bytes] = None) -> EfiImage:
    """Parse a PE/COFF EFI image and classify it as UKI / EFI stub / other."""
    p = Path(path)
    if data is None:
        try:
            with open(p, "rb") as f:
                data = f.read()
        except OSError as exc:
            return EfiImage(path=str(p), file_size=0,
                            issues=[f"cannot read file: {exc}"])
    file_size = len(data)
    img = EfiImage(path=str(p), file_size=file_size)

    if len(data) < 0x40 or data[:2] != b"MZ":
        img.type = EfiImageType.NOT_PE
        return img

    # e_lfanew -> PE signature
    try:
        e_lfanew = struct.unpack_from("<I", data, 0x3c)[0]
    except struct.error as exc:
        img.issues.append(f"bad e_lfanew: {exc}")
        return img

    if e_lfanew + 24 > len(data):
        img.type = EfiImageType.NOT_PE
        img.issues.append("file truncated before PE header")
        return img

    if data[e_lfanew:e_lfanew + 4] != b"PE\x00\x00":
        img.type = EfiImageType.NOT_PE
        img.issues.append("missing PE\\0\\0\\0 signature")
        return img

    # COFF header is 20 bytes at e_lfanew+4
    coff = e_lfanew + 4
    try:
        (machine, num_sections, _timestamp, _sym_table,
         _num_symbols, size_of_optional_header, characteristics) = (
            struct.unpack_from("<HHIIIHH", data, coff)
        )
    except struct.error as exc:
        img.issues.append(f"bad COFF header: {exc}")
        return img

    img.machine = machine
    img.entry_point = 0
    img.image_base = 0
    img.subsystem = 0

    # Optional header starts at coff+20
    opt = coff + 20
    if size_of_optional_header >= 112 and opt + 112 <= len(data):
        # PE32 magic = 0x10b, PE32+ magic = 0x20b
        magic = struct.unpack_from("<H", data, opt)[0]
        if magic == 0x20b and opt + 112 <= len(data):
            # PE32+ (used for 64-bit EFI binaries)
            img.subsystem = struct.unpack_from("<H", data, opt + 68)[0]
            img.image_base = struct.unpack_from("<Q", data, opt + 24)[0]
            img.entry_point = struct.unpack_from("<I", data, opt + 16)[0]
        elif magic == 0x10b and opt + 112 <= len(data):
            # PE32 (32-bit)
            img.subsystem = struct.unpack_from("<H", data, opt + 68)[0]
            img.entry_point = struct.unpack_from("<I", data, opt + 16)[0]
        # else: unknown optional-header format - leave fields zero.

    # Section table is right after the optional header.
    section_table_offset = opt + size_of_optional_header
    img.sections = _extract_sections(
        data, section_table_offset, num_sections, size_of_optional_header
    )
    img.uki_sections = [s for s in img.sections if s in UKI_SECTIONS]

    # Classification
    has_uki = bool(img.uki_sections)
    has_linux_section = ".linux" in img.sections
    has_initrd = ".initrd" in img.sections
    has_osrel = ".osrel" in img.sections
    has_cmdline = ".cmdline" in img.sections
    img.has_sdmagic = ".sdmagic" in img.sections
    img.has_osrel = has_osrel
    img.has_cmdline = has_cmdline
    img.has_initrd = has_initrd
    img.has_linux = has_linux_section
    img.has_splash = ".splash" in img.sections
    img.has_ucode = ".ucode" in img.sections
    img.has_dtb = ".dtb" in img.sections

    if has_linux_section and (has_initrd or has_osrel or img.has_sdmagic):
        img.type = EfiImageType.UKI
        img.boot_loader_spec_type = 2
    elif has_linux_section:
        # Linux kernel compiled with CONFIG_EFI_STUB (without UKI bundling).
        img.type = EfiImageType.EFI_STUB_BZIMAGE
    else:
        img.type = EfiImageType.OTHER_PE

    return img


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class EfiStubInspector:
    """Inspect Linux EFI binaries under a directory."""

    def __init__(self, boot_dir: str | os.PathLike) -> None:
        self.boot_dir = Path(boot_dir)

    def inspect(self, name: str) -> Optional[EfiImage]:
        p = self.boot_dir / name
        if not p.is_file():
            return None
        return parse_efi_image(p)

    def find_ukis(self) -> List[EfiImage]:
        """Return all ``/EFI/Linux/*.efi`` candidates under ``boot_dir``."""
        results: List[EfiImage] = []
        # Direct EFI/Linux directory?
        linux_dir = self.boot_dir / "EFI" / "Linux"
        if linux_dir.is_dir():
            for p in sorted(linux_dir.glob("*.efi")):
                img = parse_efi_image(p)
                if img.is_efi_stub:
                    results.append(img)
        # Also scan the top-level for .efi files (BLS Type #1 ``uki`` key).
        for p in sorted(self.boot_dir.glob("*.efi")):
            img = parse_efi_image(p)
            if img.is_efi_stub and img not in results:
                results.append(img)
        return results

    def find_efi_stubs(self) -> List[EfiImage]:
        """Return all EFI-stub bzImages under ``boot_dir`` (vmlinuz-*)."""
        results: List[EfiImage] = []
        for p in sorted(self.boot_dir.glob("vmlinuz-*")):
            img = parse_efi_image(p)
            if img.is_efi_stub:
                results.append(img)
        return results


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _build_fake_pe(sections: List[str],
                   subsystem: int = EFI_SUBSYSTEM_APPLICATION,
                   machine: int = MACHINE_AMD64,
                   is_pe32_plus: bool = True) -> bytes:
    """Build a synthetic PE/COFF binary with the given section names.

    The image is good enough for header parsing; the section bodies are
    all zero.  We populate ``.sdmagic`` with the canonical payload so
    that ``has_sdmagic`` comes out True.
    """
    size_of_optional_header = 112  # PE32 / PE32+ minimal
    e_lfanew = 0x80
    buf = bytearray(0x200 + size_of_optional_header + 40 * max(len(sections), 1))
    buf[0:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3c, e_lfanew)
    buf[e_lfanew:e_lfanew + 4] = b"PE\x00\x00"
    coff = e_lfanew + 4
    # COFF header
    struct.pack_into("<HHIIIHH", buf, coff,
                     machine, len(sections), 0, 0, 0, size_of_optional_header, 0)
    opt = coff + 20
    magic = 0x20b if is_pe32_plus else 0x10b
    struct.pack_into("<H", buf, opt, magic)
    if is_pe32_plus:
        # PE32+: entry point, image base, subsystem
        struct.pack_into("<I", buf, opt + 16, 0x1000)         # AddressOfEntryPoint
        struct.pack_into("<Q", buf, opt + 24, 0x400000)       # ImageBase
        struct.pack_into("<H", buf, opt + 68, subsystem)      # Subsystem
    else:
        struct.pack_into("<I", buf, opt + 16, 0x1000)
        struct.pack_into("<I", buf, opt + 28, 0x400000)
        struct.pack_into("<H", buf, opt + 68, subsystem)
    # Section table
    sec_offset = opt + size_of_optional_header
    for i, name in enumerate(sections):
        n = name.encode("utf-8")[:8].ljust(8, b"\x00")
        buf[sec_offset + i * 40:sec_offset + i * 40 + 8] = n
        if name == ".sdmagic":
            # Plant SDMAGIC payload at the start of the section body.
            # Section header is 40 bytes; the body comes right after.
            body_offset = sec_offset + (i + 1) * 40
            if body_offset + 8 <= len(buf):
                buf[body_offset:body_offset + 8] = SDMAGIC
    return bytes(buf)


def _selftest() -> bool:
    import tempfile

    # 1. UKI with all canonical sections
    sections = [".text", ".data", ".rodata",
                ".sdmagic", ".osrel", ".cmdline", ".linux", ".initrd",
                ".ucode", ".splash", ".dtb"]
    img = parse_efi_image("uki.efi", data=_build_fake_pe(sections))
    if img.type != EfiImageType.UKI:
        return False
    if not img.has_sdmagic or not img.has_linux or not img.has_initrd:
        return False
    if img.boot_loader_spec_type != 2:
        return False
    if not img.is_secure_boot_signable:
        return False

    # 2. Bare EFI stub (no .linux section but EFI subsystem set)
    img2 = parse_efi_image("stub.efi",
                            data=_build_fake_pe([".text", ".data", ".rodata"]))
    if img2.type != EfiImageType.OTHER_PE:
        return False

    # 3. Not a PE at all
    img3 = parse_efi_image("blob", data=b"\x00\x00\x00\x00not-a-pe")
    if img3.type != EfiImageType.NOT_PE:
        return False

    # 4. End-to-end with EfiStubInspector
    with tempfile.TemporaryDirectory() as tmp:
        bd = Path(tmp)
        # /EFI/Linux/uki-foo.efi
        lin = bd / "EFI" / "Linux"
        lin.mkdir(parents=True)
        (lin / "uki-foo.efi").write_bytes(_build_fake_pe(sections))
        ins = EfiStubInspector(bd)
        ukis = ins.find_ukis()
        if len(ukis) != 1:
            return False
        if not ukis[0].is_uki:
            return False

    return True


if __name__ == "__main__":
    import json
    import sys
    logging.basicConfig(level=logging.INFO)
    target = sys.argv[1] if len(sys.argv) > 1 else "/boot/vmlinuz"
    img = parse_efi_image(target)
    print(json.dumps(img.as_dict(), indent=2))
    print("efi_stub selftest:", "OK" if _selftest() else "FAIL")
