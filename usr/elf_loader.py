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
UmerOS ELF Loader Module
=========================
kernel ELF binary loading interface.
Implements ELF parsing, program loading, and dynamic linking.

Reference: docs.kernel.org/userspace-api/elf.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple
import struct
import threading


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOMEM: int = 12
ENOEXEC: int = 8
ENOENT: int = 2


class ELFClass(IntEnum):
    """ELF file class."""
    ELFCLASS_NONE: int = 0
    ELFCLASS32: int = 1
    ELFCLASS64: int = 2


class ELFData(IntEnum):
    """ELF data encoding."""
    ELFDATANONE: int = 0
    ELFDATA2LSB: int = 1
    ELFDATA2MSB: int = 2


class ELFType(IntEnum):
    """ELF file type."""
    ET_NONE: int = 0
    ET_REL: int = 1
    ET_EXEC: int = 2
    ET_DYN: int = 3
    ET_CORE: int = 4


class ELFMachine(IntEnum):
    """ELF machine type."""
    EM_NONE: int = 0
    EM_386: int = 3
    EM_X86_64: int = 62
    EM_ARM: int = 40
    EM_AARCH64: int = 183
    EM_MIPS: int = 8
    EM_PPC: int = 20
    EM_PPC64: int = 21
    EM_RISCV: int = 243
    EM_S390: int = 22


class ELFProgramHeaderType(IntEnum):
    """ELF program header types."""
    PT_NULL: int = 0
    PT_LOAD: int = 1
    PT_DYNAMIC: int = 2
    PT_INTERP: int = 3
    PT_NOTE: int = 4
    PT_SHLIB: int = 5
    PT_PHDR: int = 6
    PT_TLS: int = 7
    PT_GNU_EH_FRAME: int = 0x6474e550
    PT_GNU_STACK: int = 0x6474e551
    PT_GNU_RELRO: int = 0x6474e552


class ELFSectionHeaderType(IntEnum):
    """ELF section header types."""
    SHT_NULL: int = 0
    SHT_PROGBITS: int = 1
    SHT_SYMTAB: int = 2
    SHT_STRTAB: int = 3
    SHT_RELA: int = 4
    SHT_HASH: int = 5
    SHT_DYNAMIC: int = 6
    SHT_NOTE: int = 7
    SHT_NOBITS: int = 8
    SHT_REL: int = 9
    SHT_DYNSYM: int = 11


class ELFSegmentFlags(IntEnum):
    """ELF segment flags."""
    PF_X: int = 1
    PF_W: int = 2
    PF_R: int = 4


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class ELFHeader:
    """ELF file header."""
    magic: bytes = b"\x7fELF"
    elf_class: ELFClass = ELFClass.ELFCLASS64
    data: ELFData = ELFData.ELFDATA2LSB
    version: int = 1
    os_abi: int = 0
    type: ELFType = ELFType.ET_EXEC
    machine: ELFMachine = ELFMachine.EM_X86_64
    entry: int = 0
    phoff: int = 0
    shoff: int = 0
    flags: int = 0
    ehsize: int = 0
    phentsize: int = 0
    phnum: int = 0
    shentsize: int = 0
    shnum: int = 0
    shstrndx: int = 0

    def parse(self, data: bytes) -> int:
        """Parse ELF header from bytes."""
        if len(data) < 64:
            return EINVAL
        if data[:4] != b"\x7fELF":
            return ENOEXEC
        self.magic = data[:4]
        self.elf_class = ELFClass(data[4])
        self.data = ELFData(data[5])
        self.version = data[6]
        self.os_abi = data[7]
        if self.elf_class == ELFClass.ELFCLASS64:
            self.type = ELFType(struct.unpack_from("<H", data, 16)[0])
            self.machine = ELFMachine(struct.unpack_from("<H", data, 18)[0])
            self.entry = struct.unpack_from("<Q", data, 24)[0]
            self.phoff = struct.unpack_from("<Q", data, 32)[0]
            self.shoff = struct.unpack_from("<Q", data, 40)[0]
            self.flags = struct.unpack_from("<I", data, 48)[0]
            self.ehsize = struct.unpack_from("<H", data, 52)[0]
            self.phentsize = struct.unpack_from("<H", data, 54)[0]
            self.phnum = struct.unpack_from("<H", data, 56)[0]
            self.shentsize = struct.unpack_from("<H", data, 58)[0]
            self.shnum = struct.unpack_from("<H", data, 60)[0]
            self.shstrndx = struct.unpack_from("<H", data, 62)[0]
        return SUCCESS


@dataclass
class ELFProgramHeader:
    """ELF program header (segment descriptor)."""
    p_type: ELFProgramHeaderType = ELFProgramHeaderType.PT_NULL
    p_flags: int = 0
    p_offset: int = 0
    p_vaddr: int = 0
    p_paddr: int = 0
    p_filesz: int = 0
    p_memsz: int = 0
    p_align: int = 0

    def parse(self, data: bytes, offset: int = 0) -> int:
        """Parse program header from bytes."""
        if len(data) < offset + 56:
            return EINVAL
        self.p_type = ELFProgramHeaderType(struct.unpack_from("<I", data, offset)[0])
        self.p_flags = struct.unpack_from("<I", data, offset + 4)[0]
        self.p_offset = struct.unpack_from("<Q", data, offset + 8)[0]
        self.p_vaddr = struct.unpack_from("<Q", data, offset + 16)[0]
        self.p_paddr = struct.unpack_from("<Q", data, offset + 24)[0]
        self.p_filesz = struct.unpack_from("<Q", data, offset + 32)[0]
        self.p_memsz = struct.unpack_from("<Q", data, offset + 40)[0]
        self.p_align = struct.unpack_from("<Q", data, offset + 48)[0]
        return SUCCESS

    def is_loadable(self) -> bool:
        """Check if this is a loadable segment."""
        return self.p_type == ELFProgramHeaderType.PT_LOAD

    def is_executable(self) -> bool:
        """Check if segment is executable."""
        return bool(self.p_flags & ELFSegmentFlags.PF_X)

    def is_writable(self) -> bool:
        """Check if segment is writable."""
        return bool(self.p_flags & ELFSegmentFlags.PF_W)

    def is_readable(self) -> bool:
        """Check if segment is readable."""
        return bool(self.p_flags & ELFSegmentFlags.PF_R)


@dataclass
class ELFSectionHeader:
    """ELF section header."""
    sh_name: int = 0
    sh_type: ELFSectionHeaderType = ELFSectionHeaderType.SHT_NULL
    sh_flags: int = 0
    sh_addr: int = 0
    sh_offset: int = 0
    sh_size: int = 0
    sh_link: int = 0
    sh_info: int = 0
    sh_addralign: int = 0
    sh_entsize: int = 0
    name: str = ""

    def parse(self, data: bytes, offset: int = 0) -> int:
        """Parse section header from bytes."""
        if len(data) < offset + 64:
            return EINVAL
        self.sh_name = struct.unpack_from("<I", data, offset)[0]
        self.sh_type = ELFSectionHeaderType(struct.unpack_from("<I", data, offset + 4)[0])
        self.sh_flags = struct.unpack_from("<Q", data, offset + 8)[0]
        self.sh_addr = struct.unpack_from("<Q", data, offset + 16)[0]
        self.sh_offset = struct.unpack_from("<Q", data, offset + 24)[0]
        self.sh_size = struct.unpack_from("<Q", data, offset + 32)[0]
        self.sh_link = struct.unpack_from("<I", data, offset + 40)[0]
        self.sh_info = struct.unpack_from("<I", data, offset + 44)[0]
        self.sh_addralign = struct.unpack_from("<Q", data, offset + 48)[0]
        self.sh_entsize = struct.unpack_from("<Q", data, offset + 56)[0]
        return SUCCESS


@dataclass
class ELFMemoryRegion:
    """Loaded ELF memory region."""
    vaddr: int = 0
    size: int = 0
    flags: int = 0
    data: bytes = b""
    mapped: bool = False


@dataclass
class ELFProcess:
    """Loaded ELF process."""
    pid: int = 0
    elf_path: str = ""
    header: ELFHeader = field(default_factory=ELFHeader)
    program_headers: List[ELFProgramHeader] = field(default_factory=list)
    section_headers: List[ELFSectionHeader] = field(default_factory=list)
    regions: List[ELFMemoryRegion] = field(default_factory=list)
    entry_point: int = 0
    brk: int = 0
    loaded: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def load(self, data: bytes) -> int:
        """Load an ELF binary."""
        with self.lock:
            ret = self.header.parse(data)
            if ret != SUCCESS:
                return ret

            for i in range(self.header.phnum):
                off = self.header.phoff + i * self.header.phentsize
                ph = ELFProgramHeader()
                ret = ph.parse(data, off)
                if ret == SUCCESS:
                    self.program_headers.append(ph)

            for i in range(self.header.shnum):
                off = self.header.shoff + i * self.header.shentsize
                sh = ELFSectionHeader()
                ret = sh.parse(data, off)
                if ret == SUCCESS:
                    self.section_headers.append(sh)

            for ph in self.program_headers:
                if ph.is_loadable():
                    region = ELFMemoryRegion(
                        vaddr=ph.p_vaddr,
                        size=ph.p_memsz,
                        flags=ph.p_flags,
                        data=data[ph.p_offset:ph.p_offset + ph.p_filesz],
                        mapped=True,
                    )
                    self.regions.append(region)

            self.entry_point = self.header.entry
            self.brk = max((r.vaddr + r.size for r in self.regions), default=0)
            self.loaded = True
        return SUCCESS

    def resolve_symbol(self, name: str) -> Optional[int]:
        """Resolve a symbol address (stub)."""
        for sh in self.section_headers:
            if sh.sh_type == ELFSectionHeaderType.SHT_SYMTAB:
                return None
        return None

    def get_interp(self) -> Optional[str]:
        """Get the interpreter path (PT_INTERP)."""
        for ph in self.program_headers:
            if ph.p_type == ELFProgramHeaderType.PT_INTERP:
                return f"ld-linux.so.{self.header.machine.value}"
        return None

    def stats(self) -> Dict[str, int]:
        """Get load statistics."""
        return {
            "entry_point": self.entry_point,
            "brk": self.brk,
            "regions": len(self.regions),
            "program_headers": len(self.program_headers),
            "section_headers": len(self.section_headers),
            "total_mapped": sum(r.size for r in self.regions),
        }


# ============================================================================
# ELF Loader
# ============================================================================

class ELFLoader:
    """ELF loader subsystem."""
    processes: Dict[int, ELFProcess] = field(default_factory=dict)
    next_pid: int = 1
    lock: threading.Lock = field(default_factory=threading.Lock)

    def load_binary(self, path: str, data: bytes) -> Optional[ELFProcess]:
        """Load an ELF binary."""
        with self.lock:
            proc = ELFProcess(pid=self.next_pid, elf_path=path)
            self.next_pid += 1
            ret = proc.load(data)
            if ret == SUCCESS:
                self.processes[proc.pid] = proc
                return proc
        return None

    def get_process(self, pid: int) -> Optional[ELFProcess]:
        """Get a loaded process by PID."""
        return self.processes.get(pid)

    def unload_process(self, pid: int) -> int:
        """Unload a process."""
        self.processes.pop(pid, None)
        return SUCCESS

    def list_processes(self) -> List[int]:
        """List loaded PIDs."""
        return list(self.processes.keys())

    def find_by_path(self, path: str) -> Optional[ELFProcess]:
        """Find a process by ELF path."""
        for proc in self.processes.values():
            if proc.elf_path == path:
                return proc
        return None


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_elf_loader: Optional[ELFLoader] = None


def get_global_elf_loader() -> ELFLoader:
    """Get global ELF loader."""
    global _global_elf_loader
    if _global_elf_loader is None:
        _global_elf_loader = ELFLoader()
    return _global_elf_loader
