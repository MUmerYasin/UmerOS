"""
ELF Binary Format Parser for UmerOS /lib
=========================================
Parses ELF (Executable and Linkable Format) shared libraries (.so files)
to extract metadata: SONAME, NEEDED libraries, exported/imported symbols,
architecture, type, and entry point.

Covers the real ELF parsing that the existing metadata-only managers lack —
the actual binary format knowledge needed to resolve .so dependencies,
audit libraries, and build ld.so.cache entries.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum, auto
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# ELF constants
# ---------------------------------------------------------------------------

ELF_MAGIC = b"\x7fELF"


class ElfClass(IntEnum):
    """ELF file class (bit width)."""
    ELFCLASS32 = 1
    ELFCLASS64 = 2


class ElfData(IntEnum):
    """Data encoding."""
    ELFDATA2LSB = 1  # Little-endian
    ELFDATA2MSB = 2  # Big-endian


class ElfType(IntEnum):
    """ELF object type."""
    ET_NONE = 0
    ET_REL = 1   # Relocatable
    ET_EXEC = 2   # Executable
    ET_DYN = 3    # Shared object / PIE executable
    ET_CORE = 4   # Core dump


class ElfMachine(IntEnum):
    """Target architecture."""
    EM_NONE = 0
    EM_386 = 3
    EM_ARM = 40
    EM_X86_64 = 62
    EM_AARCH64 = 183
    EM_RISCV = 243


class DynamicTag(IntEnum):
    """Dynamic section tags we care about."""
    DT_NULL = 0
    DT_NEEDED = 1
    DT_SONAME = 14
    DT_RPATH = 15
    DT_RUNPATH = 29
    DT_SYMBOL = 6
    DT_STRTAB = 5
    DT_STRSZ = 10
    DT_SYMTAB = 11
    DT_HASH = 4
    DT_GNU_HASH = 0x6ffffef5


class ShtType(IntEnum):
    """Section header types."""
    SHT_NULL = 0
    SHT_PROGBITS = 1
    SHT_SYMTAB = 2
    SHT_STRTAB = 3
    SHT_RELA = 4
    SHT_HASH = 5
    SHT_DYNAMIC = 6
    SHT_NOTE = 7
    SHT_NOBITS = 8
    SHT_REL = 9
    SHT_DYNSYM = 11


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ElfHeader:
    """Parsed ELF header."""
    e_ident: bytes
    e_class: ElfClass
    e_data: ElfData
    e_version: int
    e_type: ElfType
    e_machine: ElfMachine
    e_entry: int
    e_phoff: int
    e_shoff: int
    e_flags: int
    e_ehsize: int
    e_phentsize: int
    e_phnum: int
    e_shentsize: int
    e_shnum: int
    e_shstrndx: int


@dataclass
class SectionHeader:
    """Parsed section header entry."""
    sh_name: int
    sh_type: ShtType
    sh_flags: int
    sh_addr: int
    sh_offset: int
    sh_size: int
    sh_link: int
    sh_info: int
    sh_addralign: int
    sh_entsize: int
    name: str = ""


@dataclass
class SymbolEntry:
    """A single symbol from .dynsym or .symtab."""
    st_name: str
    st_value: int
    st_size: int
    st_info: int
    st_shndx: int
    binding: int = 0
    symbol_type: int = 0


@dataclass
class DynamicEntry:
    """A single entry from the .dynamic section."""
    d_tag: DynamicTag
    d_value: int


@dataclass
class ElfBinary:
    """Complete parsed representation of an ELF shared library."""
    path: str
    header: ElfHeader
    sections: list[SectionHeader]
    dynamic: list[DynamicEntry]
    symbols: list[SymbolEntry]
    needed: list[str]
    soname: str
    rpath: str
    runpath: str
    rpaths: list[str]
    runpaths: list[str]
    is_shared: bool
    is_pie: bool
    string_table: str

    @property
    def bit_width(self) -> int:
        return 64 if self.header.e_class == ElfClass.ELFCLASS64 else 32

    @property
    def endianness(self) -> str:
        return "little" if self.header.e_data == ElfData.ELFDATA2LSB else "big"

    @property
    def machine_name(self) -> str:
        names = {
            ElfMachine.EM_NONE: "none",
            ElfMachine.EM_386: "i386",
            ElfMachine.EM_ARM: "arm",
            ElfMachine.EM_X86_64: "x86_64",
            ElfMachine.EM_AARCH64: "aarch64",
            ElfMachine.EM_RISCV: "riscv",
        }
        return names.get(self.header.e_machine, f"unknown({self.header.e_machine})")

    @property
    def exported_symbols(self) -> list[SymbolEntry]:
        return [s for s in self.symbols if s.st_value != 0 and s.binding != 0]  # STB_LOCAL=0

    @property
    def imported_symbols(self) -> list[SymbolEntry]:
        return [s for s in self.symbols if s.st_value == 0 and s.st_name]

    @property
    def gnu_version(self) -> Optional[str]:
        return None


@dataclass
class ElfParseError(Exception):
    """Raised when an ELF file cannot be parsed."""
    path: str
    reason: str

    def __str__(self) -> str:
        return f"ElfParseError({self.path}): {self.reason}"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ElfParser:
    """
    Parses ELF shared libraries (.so) and executables.

    Reads the real ELF header, section headers, dynamic section,
    and symbol tables to extract SONAME, NEEDED, RPATH/RUNPATH,
    exported/imported symbols, and architecture metadata.

    Usage::

        parser = ElfParser()
        binary = parser.parse("/lib/x86_64-linux-gnu/libc.so.6")
        print(binary.soname, binary.needed, binary.machine_name)
    """

    def __init__(self) -> None:
        self._cache: dict[str, ElfBinary] = {}

    def parse(self, path: str | Path) -> ElfBinary:
        """Parse an ELF binary and return structured metadata."""
        path = str(Path(path).resolve())
        if path in self._cache:
            return self._cache[path]

        try:
            with open(path, "rb") as f:
                data = f.read()
        except (OSError, PermissionError) as exc:
            raise ElfParseError(path=path, reason=str(exc))

        if len(data) < 16:
            raise ElfParseError(path=path, reason="File too small for ELF header")

        if data[:4] != ELF_MAGIC:
            raise ElfParseError(path=path, reason=f"Bad magic: {data[:4]!r}")

        # --- ELF ident ---
        e_class = ElfClass(data[4])
        e_data = ElfData(data[5])
        e_version = data[6]

        if e_class not in (ElfClass.ELFCLASS32, ElfClass.ELFCLASS64):
            raise ElfParseError(path=path, reason=f"Unsupported class {e_class}")

        is64 = e_class == ElfClass.ELFCLASS64
        endian = "<" if e_data == ElfData.ELFDATA2LSB else ">"

        # --- Parse header ---
        if is64:
            hdr_fmt = endian + "HHIQQQIHHHHHH"
            hdr_size = 64
        else:
            hdr_fmt = endian + "HHIIIIIHHHHHH"
            hdr_size = 52

        if len(data) < hdr_size:
            raise ElfParseError(path=path, reason="Truncated ELF header")

        fields = struct.unpack_from(hdr_fmt, data, 16)

        if is64:
            (e_type, e_machine, e_version, e_entry, e_phoff, e_shoff,
             e_flags, e_ehsize, e_phentsize, e_phnum, e_shentsize,
             e_shnum, e_shstrndx) = fields
        else:
            (e_type, e_machine, e_version, e_entry, e_phoff, e_shoff,
             e_flags, e_ehsize, e_phentsize, e_phnum, e_shentsize,
             e_shnum, e_shstrndx) = fields

        header = ElfHeader(
            e_ident=data[:16],
            e_class=e_class,
            e_data=e_data,
            e_version=e_version,
            e_type=ElfType(e_type),
            e_machine=ElfMachine(e_machine) if e_machine <= 243 else ElfMachine.EM_NONE,
            e_entry=e_entry,
            e_phoff=e_phoff,
            e_shoff=e_shoff,
            e_flags=e_flags,
            e_ehsize=e_ehsize,
            e_phentsize=e_phentsize,
            e_phnum=e_phnum,
            e_shentsize=e_shentsize,
            e_shnum=e_shnum,
            e_shstrndx=e_shstrndx,
        )

        # --- Section headers ---
        sections = self._parse_sections(data, header, endian, is64)

        # --- Find string table ---
        string_table = ""
        if e_shstrndx < len(sections):
            strtab_sec = sections[e_shstrndx]
            raw = data[strtab_sec.sh_offset:strtab_sec.sh_offset + strtab_sec.sh_size]
            string_table = raw.decode("latin-1", errors="replace")

        for sec in sections:
            if sec.sh_name < len(string_table):
                end = string_table.find("\x00", sec.sh_name)
                sec.name = string_table[sec.sh_name:end if end != -1 else len(string_table)]

        # --- Dynamic section ---
        dynamic = self._parse_dynamic(data, sections, endian, is64)

        # --- Symbol table (dynsym + symtab) ---
        symbols = self._parse_symbols(data, sections, string_table, endian, is64)

        # --- Extract key values ---
        strtab_data = self._find_section_data(data, sections, ".dynstr", ".strtab")
        needed = []
        soname = ""
        rpath = ""
        runpath = ""
        rpaths: list[str] = []
        runpaths: list[str] = []

        for entry in dynamic:
            tag = entry.d_tag
            if tag == DynamicTag.DT_NEEDED:
                needed.append(self._read_string(strtab_data, entry.d_value))
            elif tag == DynamicTag.DT_SONAME:
                soname = self._read_string(strtab_data, entry.d_value)
            elif tag == DynamicTag.DT_RPATH:
                rp = self._read_string(strtab_data, entry.d_value)
                rpath = rp
                rpaths.extend(rp.split(":") if rp else [])
            elif tag == DynamicTag.DT_RUNPATH:
                rp = self._read_string(strtab_data, entry.d_value)
                runpath = rp
                runpaths.extend(rp.split(":") if rp else [])

        binary = ElfBinary(
            path=path,
            header=header,
            sections=sections,
            dynamic=dynamic,
            symbols=symbols,
            needed=needed,
            soname=soname,
            rpath=rpath,
            runpath=runpath,
            rpaths=rpaths,
            runpaths=runpaths,
            is_shared=header.e_type == ElfType.ET_DYN,
            is_pie=header.e_type == ElfType.ET_DYN,
            string_table=string_table,
        )
        self._cache[path] = binary
        return binary

    def _parse_sections(
        self, data: bytes, header: ElfHeader, endian: str, is64: bool
    ) -> list[SectionHeader]:
        sections: list[SectionHeader] = []
        for i in range(header.e_shnum):
            off = header.e_shoff + i * header.e_shentsize
            if off + header.e_shentsize > len(data):
                break
            if is64:
                fmt = endian + "IIQQQQIIQQ"
            else:
                fmt = endian + "IIIIIIIIII"
            fields = struct.unpack_from(fmt, data, off)
            sh = SectionHeader(
                sh_name=fields[0], sh_type=ShtType(fields[1]),
                sh_flags=fields[2], sh_addr=fields[3], sh_offset=fields[4],
                sh_size=fields[5], sh_link=fields[6], sh_info=fields[7],
                sh_addralign=fields[8], sh_entsize=fields[9],
            )
            sections.append(sh)
        return sections

    def _parse_dynamic(
        self, data: bytes, sections: list[SectionHeader], endian: str, is64: bool
    ) -> list[DynamicEntry]:
        dyn_sec = next((s for s in sections if s.sh_type == ShtType.SHT_DYNAMIC), None)
        if dyn_sec is None:
            return []

        entries: list[DynamicEntry] = []
        count = dyn_sec.sh_size // dyn_sec.sh_entsize
        for i in range(int(count)):
            off = dyn_sec.sh_offset + i * dyn_sec.sh_entsize
            if off + dyn_sec.sh_entsize > len(data):
                break
            if is64:
                tag, val = struct.unpack_from(endian + "QQ", data, off)
            else:
                tag, val = struct.unpack_from(endian + "II", data, off)
            try:
                d_tag = DynamicTag(tag)
            except ValueError:
                d_tag = tag  # type: ignore[assignment]
            entries.append(DynamicEntry(d_tag=d_tag, d_value=val))
            if tag == DynamicTag.DT_NULL:
                break
        return entries

    def _parse_symbols(
        self, data: bytes, sections: list[SectionHeader], string_table: str,
        endian: str, is64: bool,
    ) -> list[SymbolEntry]:
        symbols: list[SymbolEntry] = []
        for sec in sections:
            if sec.sh_type not in (ShtType.SHT_DYNSYM, ShtType.SHT_SYMTAB):
                continue
            if sec.sh_entsize == 0:
                continue

            # Find the associated string table
            if sec.sh_link < len(sections):
                link_sec = sections[sec.sh_link]
                st_data = data[link_sec.sh_offset:link_sec.sh_offset + link_sec.sh_size]
            else:
                st_data = string_table.encode("latin-1")

            count = sec.sh_size // sec.sh_entsize
            for i in range(int(count)):
                off = sec.sh_offset + i * sec.sh_entsize
                if off + sec.sh_entsize > len(data):
                    break
                if is64:
                    fmt = endian + "IBBHQQ"
                else:
                    fmt = endian + "IIBBHH"
                fields = struct.unpack_from(fmt, data, off)
                st_name_idx = fields[0]
                st_info = fields[2] if not is64 else fields[2]
                st_shndx = fields[4] if not is64 else fields[4]

                if is64:
                    st_value = fields[1]
                    st_size = fields[5]
                else:
                    st_value = fields[1]
                    st_size = fields[3]

                # Read name from string table
                name = ""
                if isinstance(st_data, bytes):
                    if st_name_idx < len(st_data):
                        end = st_data.find(b"\x00", st_name_idx)
                        name = st_data[st_name_idx:end if end != -1 else len(st_data)].decode("latin-1", errors="replace")
                elif isinstance(st_data, str):
                    if st_name_idx < len(st_data):
                        end = st_data.find("\x00", st_name_idx)
                        name = st_data[st_name_idx:end if end != -1 else len(st_data)]

                binding = st_info >> 4
                sym_type = st_info & 0xf

                symbols.append(SymbolEntry(
                    st_name=name,
                    st_value=st_value,
                    st_size=st_size,
                    st_info=st_info,
                    st_shndx=st_shndx,
                    binding=binding,
                    symbol_type=sym_type,
                ))
        return symbols

    def _find_section_data(
        self, data: bytes, sections: list[SectionHeader], *names: str
    ) -> str:
        for name in names:
            sec = next((s for s in sections if s.name == name), None)
            if sec is not None:
                raw = data[sec.sh_offset:sec.sh_offset + sec.sh_size]
                return raw.decode("latin-1", errors="replace")
        return ""

    @staticmethod
    def _read_string(table: str, offset: int) -> str:
        if offset >= len(table):
            return ""
        end = table.find("\x00", offset)
        return table[offset:end if end != -1 else len(table)]

    def quick_inspect(self, path: str | Path) -> dict[str, object]:
        """Parse and return a summary dict suitable for ld.so.cache entries."""
        binary = self.parse(path)
        return {
            "path": binary.path,
            "soname": binary.soname,
            "needed": binary.needed,
            "machine": binary.machine_name,
            "bit_width": binary.bit_width,
            "endianness": binary.endianness,
            "type": binary.header.e_type.name,
            "rpath": binary.rpath,
            "runpath": binary.runpath,
            "exported_count": len(binary.exported_symbols),
            "imported_count": len(binary.imported_symbols),
        }

    def clear_cache(self) -> None:
        self._cache.clear()


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def read_soname(path: str | Path) -> str:
    """Read SONAME from an ELF shared library. Returns '' on failure."""
    try:
        return ElfParser().parse(path).soname
    except ElfParseError:
        return ""


def read_needed(path: str | Path) -> list[str]:
    """Read NEEDED list from an ELF binary. Returns [] on failure."""
    try:
        return ElfParser().parse(path).needed
    except ElfParseError:
        return []


def is_elf(path: str | Path) -> bool:
    """Check if a file starts with the ELF magic bytes."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == ELF_MAGIC
    except (OSError, PermissionError):
        return False


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Build a minimal valid ELF in memory and round-trip it through
    :class:`ElfParser`.  We don't try to be exhaustive here - just
    enough to confirm the parser is wired correctly.
    """
    import io
    import struct
    import tempfile

    # A 64-bit, little-endian, ET_EXEC ELF with no program / section
    # headers.  Just enough bytes for the parser to recognise the
    # file as ELF and report the basics.
    e_ident = (
        b"\x7fELF"            # magic
        b"\x02"               # 64-bit
        b"\x01"               # little-endian
        b"\x01"               # ELF version
        b"\x00" * 9           # padding
    )
    # sizeof(Elf64_Ehdr) = 64 bytes.
    header = struct.pack(
        "<16sHHIQQQIHHHHHH",
        e_ident,
        2,            # e_type = ET_EXEC
        0x3E,         # e_machine = EM_X86_64
        1,            # e_version
        0,            # e_entry
        0,            # e_phoff
        0,            # e_shoff
        0,            # e_flags
        64,           # e_ehsize
        0,            # e_phentsize
        0,            # e_phnum
        0,            # e_shentsize
        0,            # e_shnum
        0,            # e_shstrndx
    )
    blob = header
    parser = ElfParser()
    try:
        info = parser.parse(io.BytesIO(blob))
    except Exception:  # noqa: BLE001
        return False
    if info is None:
        return False
    if info.header.e_machine != ElfMachine.EM_X86_64:
        return False
    if info.header.e_type != ElfType.ET_EXEC:
        return False
    # Round-trip through the file API as well.
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "tiny.elf"
        p.write_bytes(blob)
        if not is_elf(p):
            return False
        if is_elf(Path(tmp) / "does-not-exist"):
            return False
    return True


if __name__ == "__main__":
    print("elf_parser selftest:", "OK" if _selftest() else "FAIL")
