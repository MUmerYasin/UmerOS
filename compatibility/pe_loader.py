"""
Umer OS /compatibility/pe_loader — PE32 / PE32+ parser
======================================================

The **Portable Executable** (PE) format is the on-disk layout for
modern Windows executables (.exe), DLLs (.dll), device drivers
(.sys), screen-savers (.scr), control-panel applets (.cpl), and
several other binary types.

Layout overview::

    +---------------------+
    | DOS MZ header       |   (can be skipped; only e_lfanew used)
    +---------------------+
    | DOS stub program    |   (variable, ends at e_lfanew)
    +---------------------+
    | PE signature        |   4 bytes: "PE\0\0"
    +---------------------+
    | COFF file header    |   IMAGE_FILE_HEADER (20 bytes)
    +---------------------+
    | Optional header      |   IMAGE_OPTIONAL_HEADER (PE32=224, PE32+=240)
    |   - Standard fields  |
    |   - Windows-specific |
    |   - Data dirs (16)   |
    +---------------------+
    | Section headers     |   IMAGE_SECTION_HEADER x N (40 bytes each)
    +---------------------+
    | Section data        |   (per section table, raw bytes)
    +---------------------+

This module:

* validates the PE signature,
* parses the COFF file header,
* parses the *standard* (PE32/PE32+) and *Windows-specific*
  optional-header fields,
* enumerates the **section table** with virtual-size / virtual-address
  / raw-size / raw-offset + characteristics,
* exposes the 16 **data directories** as named offsets (so other
  modules — :mod:`pe_imports`, :mod:`pe_exports`, :mod:`pe_resources`,
  :mod:`pe_tls`, :mod:`pe_relocations` — can locate them),
* provides a minimal **loader** (read-only; no execution) that
  resolves a VirtualAddress to ``(section, offset, length)`` so
  callers can pull bytes out of the right section.

The class :class:`PeFile` is the entry point.  Use
:meth:`PeFile.from_file` or :meth:`PeFile.from_bytes`.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
* "An In-Depth Look into the Win32 Portable Executable File Format"
  (MSDN Magazine, Feb 2002)
* https://wiki.osdev.org/PE

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.PE")

#: 4-byte PE signature at the start of the COFF header.
PE_SIG = b"PE\x00\x00"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class MachineType(IntEnum):
    """COFF MachineType (``.Machine`` field)."""

    UNKNOWN = 0x0000
    I386 = 0x014C
    AMD64 = 0x8664
    ARM = 0x01C0
    ARM64 = 0xAA64
    IA64 = 0x0200


class PeClass(IntEnum):
    """PE32 (32-bit) vs PE32+ (64-bit)."""

    PE32 = 32
    PE32_PLUS = 64


class Subsystem(IntEnum):
    """PE Optional Header ``Subsystem`` field."""

    UNKNOWN = 0
    NATIVE = 1
    WINDOWS_GUI = 2
    WINDOWS_CUI = 3
    OS2_CUI = 5
    POSIX_CUI = 7
    NATIVE_WIN = 8
    WINDOWS_CE_GUI = 9
    EFI_APPLICATION = 10
    EFI_BOOT_SERVICE_DRIVER = 11
    EFI_RUNTIME_DRIVER = 12
    EFI_ROM = 13
    XBOX = 14
    WINDOWS_BOOT_APPLICATION = 16


class DllCharacteristics(IntEnum):
    """``IMAGE_OPTIONAL_HEADER.DllCharacteristics`` flags."""

    DYNAMIC_BASE = 0x0040
    FORCE_INTEGRITY = 0x0080
    NX_COMPAT = 0x0100
    NO_ISOLATION = 0x0200
    NO_SEH = 0x0400
    NO_BIND = 0x0800
    APPCONTAINER = 0x1000
    WDM_DRIVER = 0x2000
    GUARD_CF = 0x4000
    TERMINAL_SERVER_AWARE = 0x8000


class DataDirectoryId(IntEnum):
    """Indexes into the ``IMAGE_OPTIONAL_HEADER.DataDirectory`` array."""

    EXPORT = 0
    IMPORT = 1
    RESOURCE = 2
    EXCEPTION = 3
    SECURITY = 4
    BASERELOC = 5
    DEBUG = 6
    ARCHITECTURE = 7
    GLOBALPTR = 8
    TLS = 9
    LOAD_CONFIG = 10
    BOUND_IMPORT = 11
    IAT = 12
    DELAY_IMPORT = 13
    COM_DESCRIPTOR = 14
    RESERVED = 15


#: Pretty names for the data-directory entries.
DATA_DIRECTORY_NAMES: Dict[int, str] = {
    DataDirectoryId.EXPORT:        "Export",
    DataDirectoryId.IMPORT:        "Import",
    DataDirectoryId.RESOURCE:      "Resource",
    DataDirectoryId.EXCEPTION:     "Exception",
    DataDirectoryId.SECURITY:      "Security",
    DataDirectoryId.BASERELOC:     "BaseRelocation",
    DataDirectoryId.DEBUG:         "Debug",
    DataDirectoryId.ARCHITECTURE:  "Architecture",
    DataDirectoryId.GLOBALPTR:     "GlobalPointer",
    DataDirectoryId.TLS:           "TLS",
    DataDirectoryId.LOAD_CONFIG:   "LoadConfig",
    DataDirectoryId.BOUND_IMPORT:  "BoundImport",
    DataDirectoryId.IAT:           "IAT",
    DataDirectoryId.DELAY_IMPORT:  "DelayImport",
    DataDirectoryId.COM_DESCRIPTOR: "ComDescriptor",
    DataDirectoryId.RESERVED:      "Reserved",
}


#: Section characteristic flags.
class SectionFlags(IntEnum):
    """Subset of ``IMAGE_SECTION_HEADER.Characteristics``."""

    CNT_CODE = 0x00000020
    CNT_INITIALIZED_DATA = 0x00000040
    CNT_UNINITIALIZED_DATA = 0x00000080
    MEM_EXECUTE = 0x20000000
    MEM_READ = 0x40000000
    MEM_WRITE = 0x80000000


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PeSection:
    """A single ``IMAGE_SECTION_HEADER``."""

    name: str
    virtual_size: int
    virtual_address: int
    raw_size: int
    raw_offset: int
    characteristics: int

    @property
    def is_code(self) -> bool:
        return bool(self.characteristics & SectionFlags.CNT_CODE)

    @property
    def is_data(self) -> bool:
        return bool(self.characteristics & SectionFlags.CNT_INITIALIZED_DATA)

    @property
    def is_readable(self) -> bool:
        return bool(self.characteristics & SectionFlags.MEM_READ)

    @property
    def is_writable(self) -> bool:
        return bool(self.characteristics & SectionFlags.MEM_WRITE)

    @property
    def is_executable(self) -> bool:
        return bool(self.characteristics & SectionFlags.MEM_EXECUTE)


@dataclass
class DataDirectory:
    """A single entry in the PE data directory."""

    index: int
    name: str
    virtual_address: int
    size: int

    @property
    def is_present(self) -> bool:
        return self.virtual_address != 0 and self.size != 0


@dataclass
class PeOptionalHeader:
    """The IMAGE_OPTIONAL_HEADER (standard + Windows-specific)."""

    magic: int
    pe_class: PeClass
    major_linker_version: int
    minor_linker_version: int
    size_of_code: int
    size_of_initialized_data: int
    size_of_uninitialized_data: int
    address_of_entry_point: int
    base_of_code: int
    base_of_data: int
    # PE32+ only
    image_base: int
    # PE32 only
    image_base_32: int
    image_base_64: int
    section_alignment: int
    file_alignment: int
    major_os_version: int
    minor_os_version: int
    major_image_version: int
    minor_image_version: int
    major_subsystem_version: int
    minor_subsystem_version: int
    win32_version_value: int
    size_of_image: int
    size_of_headers: int
    check_sum: int
    subsystem: int
    dll_characteristics: int
    size_of_stack_reserve: int
    size_of_stack_commit: int
    size_of_heap_reserve: int
    size_of_heap_commit: int
    loader_flags: int
    number_of_rva_and_sizes: int
    data_directories: List[DataDirectory] = field(default_factory=list)


@dataclass
class PeFile:
    """A complete parsed PE file."""

    # ----- raw + offsets -------------------------------------------------
    raw: bytes
    pe_offset: int                # offset of the PE signature

    # ----- COFF file header ---------------------------------------------
    machine: int
    number_of_sections: int
    time_date_stamp: int
    pointer_to_symbol_table: int
    number_of_symbols: int
    size_of_optional_header: int
    characteristics: int

    # ----- Optional header ---------------------------------------------
    optional_header: PeOptionalHeader

    # ----- Sections -----------------------------------------------------
    sections: List[PeSection] = field(default_factory=list)

    # ----- Convenience --------------------------------------------------
    @property
    def machine_name(self) -> str:
        try:
            return MachineType(self.machine).name
        except ValueError:
            return f"UNKNOWN(0x{self.machine:04X})"

    @property
    def subsystem_name(self) -> str:
        try:
            return Subsystem(self.optional_header.subsystem).name
        except ValueError:
            return f"UNKNOWN(0x{self.optional_header.subsystem:02X})"

    @property
    def entry_point_rva(self) -> int:
        return self.optional_header.address_of_entry_point

    @property
    def image_base(self) -> int:
        return (self.optional_header.image_base_64
                if self.optional_header.pe_class == PeClass.PE32_PLUS
                else self.optional_header.image_base_32)

    def get_data_directory(self, index: int) -> Optional[DataDirectory]:
        """Return the data directory at ``index`` (or ``None``)."""
        for d in self.optional_header.data_directories:
            if d.index == index:
                return d
        return None

    # ------------------------------------------------------------------
    # Address translation (read-only)
    # ------------------------------------------------------------------

    def rva_to_offset(self, rva: int) -> Tuple[int, int]:
        """Translate a Relative Virtual Address to a file offset.

        Returns:
            ``(offset, length)`` -- the file offset of ``rva`` and
            the number of bytes available.  Raises
            :class:`ValueError` if ``rva`` does not fall inside any
            section.
        """
        for s in self.sections:
            if s.virtual_address <= rva < s.virtual_address + max(
                s.virtual_size, s.raw_size
            ):
                delta = rva - s.virtual_address
                return s.raw_offset + delta, s.raw_size - delta
        raise ValueError(f"RVA 0x{rva:08X} not in any section")

    def get_data(self, rva: int, length: int) -> bytes:
        """Return ``length`` bytes from the given RVA."""
        off, avail = self.rva_to_offset(rva)
        if length > avail:
            raise ValueError(
                f"requested {length} bytes from RVA 0x{rva:08X} "
                f"but only {avail} are available"
            )
        return self.raw[off:off + length]

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str) -> "PeFile":
        with open(path, "rb") as f:
            return cls.from_bytes(f.read())

    @classmethod
    def from_bytes(cls, data: bytes, *, pe_offset: Optional[int] = None) -> "PeFile":
        """Parse a PE file from raw bytes.

        Args:
            data: file contents.
            pe_offset: explicit PE offset (default: read from
                ``e_lfanew`` in the embedded MZ header).
        """
        if pe_offset is None:
            # Delegate the MZ parsing to the sibling module so the
            # formats stay in sync.
            from compatibility.mz_loader import parse_mz_header
            mz = parse_mz_header(data)
            pe_offset = mz.e_lfanew
        if pe_offset is None or pe_offset < 0:
            raise ValueError("invalid PE offset")
        if pe_offset + 24 > len(data):
            raise ValueError("data too short to contain a PE header")
        if data[pe_offset:pe_offset + 4] != PE_SIG:
            raise ValueError(
                f"PE signature missing at offset 0x{pe_offset:X}"
            )
        return cls._from_known_offset(data, pe_offset)

    @classmethod
    def _from_known_offset(cls, data: bytes, pe_offset: int) -> "PeFile":
        # COFF file header (20 bytes)
        coff = struct.unpack_from(
            "<HHIIIHH", data, pe_offset + 4
        )
        (machine, n_sections, time_stamp, sym_table, n_syms,
         size_opt, characteristics) = coff
        # Optional header follows immediately.
        opt_off = pe_offset + 24
        if opt_off + 2 > len(data):
            raise ValueError("truncated optional header (no magic)")
        opt_magic = struct.unpack_from("<H", data, opt_off)[0]
        if opt_magic == 0x10B:
            pe_class = PeClass.PE32
            opt_struct = _OPT_PE32
        elif opt_magic == 0x20B:
            pe_class = PeClass.PE32_PLUS
            opt_struct = _OPT_PE32_PLUS
        else:
            raise ValueError(
                f"unknown optional-header magic 0x{opt_magic:04X}"
            )
        # The size_of_optional_header field is the authoritative length;
        # the standard 96-byte struct is then followed by 16 x 8-byte
        # data directories.  We read both regions and combine them.
        opt_size_declared = size_opt
        if opt_off + opt_size_declared > len(data):
            raise ValueError("truncated optional header")
        opt_raw = opt_struct.unpack_from(data, opt_off)

        # Build the optional-header dataclass, separating the
        # standard / Windows / data-directory fields.
        opt = _build_optional_header(pe_class, opt_raw, opt_struct, data, opt_off)

        # Section headers (right after the declared optional header).
        sec_off = opt_off + opt_size_declared
        sections: List[PeSection] = []
        for _ in range(n_sections):
            if sec_off + 40 > len(data):
                break
            (
                name_bytes, v_size, v_addr, raw_size, raw_ptr,
                _relocs, _lines, _nrelocs, _nlines, chars,
            ) = struct.unpack_from(
                "<8sIIIIIIHHI", data, sec_off
            )
            name = name_bytes.rstrip(b"\x00").decode("ascii", errors="replace")
            sections.append(PeSection(
                name=name, virtual_size=v_size, virtual_address=v_addr,
                raw_size=raw_size, raw_offset=raw_ptr,
                characteristics=chars,
            ))
            sec_off += 40

        return cls(
            raw=data, pe_offset=pe_offset,
            machine=machine, number_of_sections=n_sections,
            time_date_stamp=time_stamp,
            pointer_to_symbol_table=sym_table,
            number_of_symbols=n_syms,
            size_of_optional_header=size_opt,
            characteristics=characteristics,
            optional_header=opt, sections=sections,
        )


# ---------------------------------------------------------------------------
# Optional-header layouts
# ---------------------------------------------------------------------------

#: Standard (common) fields of the IMAGE_OPTIONAL_HEADER.  These appear
#: before the Windows-specific fields in both PE32 and PE32+.
_OPT_COMMON = struct.Struct("<" "HBBIIIIIH")  # see _build_optional_header

_OPT_PE32 = struct.Struct(
    "<"
    "H"   #  0  magic
    "BB"  #  2  major / minor linker version
    "I"   #  4  size_of_code
    "I"   #  8  size_of_initialized_data
    "I"   # 12  size_of_uninitialized_data
    "I"   # 16  address_of_entry_point
    "I"   # 20  base_of_code
    "I"   # 24  base_of_data
    "I"   # 28  image_base (32-bit)
    "I"   # 32  section_alignment
    "I"   # 36  file_alignment
    "HH"  # 40  major / minor OS version
    "HH"  # 44  major / minor image version
    "HH"  # 48  major / minor subsystem version
    "I"   # 52  win32_version_value
    "I"   # 56  size_of_image
    "I"   # 60  size_of_headers
    "I"   # 64  check_sum
    "H"   # 68  subsystem
    "H"   # 70  dll_characteristics
    "I"   # 72  size_of_stack_reserve
    "I"   # 76  size_of_stack_commit
    "I"   # 80  size_of_heap_reserve
    "I"   # 84  size_of_heap_commit
    "I"   # 88  loader_flags
    "I"   # 92  number_of_rva_and_sizes
    # 96..(96 + 8*16) -- data directories
)

_OPT_PE32_PLUS = struct.Struct(
    "<"
    "H"   #  0  magic
    "BB"  #  2  major / minor linker version
    "I"   #  4  size_of_code
    "I"   #  8  size_of_initialized_data
    "I"   # 12  size_of_uninitialized_data
    "I"   # 16  address_of_entry_point
    "I"   # 20  base_of_code
    "Q"   # 24  image_base (64-bit)
    "I"   # 32  section_alignment
    "I"   # 36  file_alignment
    "HH"  # 40  major / minor OS version
    "HH"  # 44  major / minor image version
    "HH"  # 48  major / minor subsystem version
    "I"   # 52  win32_version_value
    "I"   # 56  size_of_image
    "I"   # 60  size_of_headers
    "I"   # 64  check_sum
    "H"   # 68  subsystem
    "H"   # 70  dll_characteristics
    "Q"   # 72  size_of_stack_reserve
    "Q"   # 80  size_of_stack_commit
    "Q"   # 88  size_of_heap_reserve
    "Q"   # 96  size_of_heap_commit
    "I"   # 104 loader_flags
    "I"   # 108 number_of_rva_and_sizes
    # 112..(112 + 8*16) -- data directories
)


def _build_optional_header(
    pe_class: PeClass,
    raw: Tuple,
    opt_struct: struct.Struct,
    data: bytes,
    opt_off: int,
) -> PeOptionalHeader:
    """Turn the unpacked optional-header tuple into a dataclass."""
    # Field ordering matches _OPT_PE32 / _OPT_PE32_PLUS.
    if pe_class == PeClass.PE32:
        (magic, lmaj, lmin, sz_code, sz_idata, sz_udata, eop, base_code,
         base_data, image_base, sec_align, file_align, mo, mio, mi, mii,
         mss, msss, winver, sz_img, sz_hdr, csum, subsys, dllc, ssr, ssc,
         shr, shc, lflags, n_rva) = raw
        ib32, ib64 = image_base, 0
    else:
        (magic, lmaj, lmin, sz_code, sz_idata, sz_udata, eop, base_code,
         image_base, sec_align, file_align, mo, mio, mi, mii, mss, msss,
         winver, sz_img, sz_hdr, csum, subsys, dllc, ssr, ssc, shr, shc,
         lflags, n_rva) = raw
        ib32, ib64 = 0, image_base

    # Data directories (16 entries, each 8 bytes = VA + Size).
    # They sit at the *end* of the optional header.  In the parsed
    # struct we did not include them, so we read them directly.
    dd_off = opt_off + opt_struct.size
    dds: List[DataDirectory] = []
    for i in range(min(n_rva, 16)):
        if dd_off + 8 > len(data):
            break
        va, sz = struct.unpack_from("<II", data, dd_off)
        dds.append(DataDirectory(
            index=i,
            name=DATA_DIRECTORY_NAMES.get(i, f"Directory{i}"),
            virtual_address=va, size=sz,
        ))
        dd_off += 8

    return PeOptionalHeader(
        magic=magic, pe_class=pe_class,
        major_linker_version=lmaj, minor_linker_version=lmin,
        size_of_code=sz_code,
        size_of_initialized_data=sz_idata,
        size_of_uninitialized_data=sz_udata,
        address_of_entry_point=eop,
        base_of_code=base_code,
        base_of_data=base_data if pe_class == PeClass.PE32 else 0,
        image_base=image_base,
        image_base_32=ib32, image_base_64=ib64,
        section_alignment=sec_align, file_alignment=file_align,
        major_os_version=mo, minor_os_version=mio,
        major_image_version=mi, minor_image_version=mii,
        major_subsystem_version=mss, minor_subsystem_version=msss,
        win32_version_value=winver,
        size_of_image=sz_img, size_of_headers=sz_hdr, check_sum=csum,
        subsystem=subsys, dll_characteristics=dllc,
        size_of_stack_reserve=ssr, size_of_stack_commit=ssc,
        size_of_heap_reserve=shr, size_of_heap_commit=shc,
        loader_flags=lflags, number_of_rva_and_sizes=n_rva,
        data_directories=dds,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _build_fake_pe() -> bytes:
    """Build a minimal but well-formed PE32 binary in memory."""
    out = bytearray()
    # --- MZ header ---
    out += b"MZ"
    out += b"\x00" * 58
    pe_off = len(out)
    out += struct.pack("<I", pe_off + 4)   # e_lfanew
    # --- PE header ---
    out += b"PE\x00\x00"
    # COFF file header
    out += struct.pack(
        "<HHIIIHH",
        0x014C,    # machine = i386
        2,         # number of sections
        0,         # time-date stamp
        0, 0,      # symbol table
        224,       # size_of_optional_header (PE32)
        0x0102,    # characteristics: EXECUTABLE_IMAGE | 32BIT_MACHINE
    )
    # Optional header
    opt_start = len(out)
    # 30 fields before the data directories.  See _OPT_PE32 for the
    # full byte-by-byte layout.
    out += struct.pack(
        "<HBBIIIIIIIIIHHHHHHIIIIHHIIIIII",
        0x10B,     # magic = PE32
        14, 0,     # linker version
        0x200,     # size_of_code
        0x100,     # size_of_initialized_data
        0,         # size_of_uninitialized_data
        0x1000,    # address_of_entry_point
        0x1000,    # base_of_code
        0x2000,    # base_of_data
        0x400000,  # image_base (32-bit)
        0x1000,    # section_alignment
        0x200,     # file_alignment
        6, 0,      # OS version
        0, 0,      # image version
        6, 0,      # subsystem version
        0,         # win32 version
        0x3000,    # size_of_image
        0x200,     # size_of_headers
        0,         # check_sum
        3,         # subsystem = WINDOWS_CUI
        0x0140,    # dll characteristics: DYNAMIC_BASE | NX_COMPAT
        0x100000, 0x1000,    # stack reserve / commit
        0x100000, 0x1000,    # heap  reserve / commit
        0,         # loader flags
        16,        # number_of_rva_and_sizes
    )
    # 16 data directories (all zero for the bare selftest PE).
    for _ in range(16):
        out += struct.pack("<II", 0, 0)
    assert len(out) - opt_start == 224
    # Section header #1
    out += b".text\x00\x00\x00"
    out += struct.pack(
        "<IIIIIIHHI",
        0x100, 0x1000, 0x200, 0x200, 0, 0, 0, 0,
        0x60000020,  # characteristics: CODE | EXECUTE | READ
    )
    # Section header #2
    out += b".data\x00\x00\x00"
    out += struct.pack(
        "<IIIIIIHHI",
        0x100, 0x2000, 0x100, 0x400, 0, 0, 0, 0,
        0xC0000040,  # INITIALIZED_DATA | READ | WRITE
    )
    # Pad to 0x200 (file_alignment)
    while len(out) % 0x200 != 0:
        out += b"\x00"
    # .text body (entry stub: just `ret`)
    out += b"\xC3" + b"\x00" * 0x1FF
    # .data body
    out += b"D" * 0x100
    return bytes(out)


def _selftest() -> bool:
    import sys
    data = _build_fake_pe()
    pe = PeFile.from_bytes(data)
    if pe.machine != 0x014C:
        print(f"FAIL machine={hex(pe.machine)}", file=sys.stderr)
        return False
    if pe.optional_header.pe_class != PeClass.PE32:
        print(f"FAIL pe_class={pe.optional_header.pe_class}", file=sys.stderr)
        return False
    if pe.number_of_sections != 2:
        print(f"FAIL number_of_sections={pe.number_of_sections}", file=sys.stderr)
        return False
    if pe.entry_point_rva != 0x1000:
        print(f"FAIL entry_rva={hex(pe.entry_point_rva)}", file=sys.stderr)
        return False
    if pe.image_base != 0x400000:
        print(f"FAIL image_base={hex(pe.image_base)}", file=sys.stderr)
        return False
    if pe.subsystem_name != "WINDOWS_CUI":
        print(f"FAIL subsystem={pe.subsystem_name}", file=sys.stderr)
        return False
    if pe.optional_header.dll_characteristics & 0x100 == 0:    # NX_COMPAT
        print(f"FAIL dll_chars={hex(pe.optional_header.dll_characteristics)}", file=sys.stderr)
        return False
    # Check that the data-directory entries were parsed.
    if len(pe.optional_header.data_directories) != 16:
        print(f"FAIL data_dirs={len(pe.optional_header.data_directories)}", file=sys.stderr)
        return False
    # The fake PE has no exports / imports etc., so all dirs are
    # absent.  We just check the count and skip the "first is
    # present" check.
    # Section table.
    names = [s.name for s in pe.sections]
    if ".text" not in names or ".data" not in names:
        print(f"FAIL section_names={names}", file=sys.stderr)
        return False
    text = pe.sections[0]
    if not text.is_code or not text.is_executable:
        print(f"FAIL text.is_code={text.is_code} text.is_executable={text.is_executable}", file=sys.stderr)
        return False
    data_sec = pe.sections[1]
    if not data_sec.is_data or not data_sec.is_writable:
        print(f"FAIL data.is_data={data_sec.is_data} data.is_writable={data_sec.is_writable}", file=sys.stderr)
        return False
    # RVA -> offset
    off, length = pe.rva_to_offset(0x1000)
    if off != 0x200:    # 0x200 == file_alignment == where .text starts
        return False
    payload = pe.get_data(0x1000, 1)
    if payload != b"\xC3":
        return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    sys.exit(0 if _selftest() else 1)
