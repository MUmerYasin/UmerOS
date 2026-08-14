"""
UmerOS Library Manager (/usr/lib)
=================================
Shared/static library management.

Reference: Filesystem Hierarchy - /usr/lib
  /usr/lib contains program libraries - collections of frequently used
  program routines. Libraries are essential for program execution and
  development.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ─── Constants ───────────────────────────────────────────────────────────────

LIB_PATHS = [
    "/usr/lib",
    "/usr/lib64",
    "/usr/lib/x86_64-gnu",
    "/usr/lib/i386-gnu",
    "/usr/lib/aarch64-gnu",
    "/usr/lib/arm-gnueabihf",
    "/usr/local/lib",
    "/usr/local/lib64",
]

LD_CONFIG_PATH = "/etc/ld.so.conf"
LD_CACHE_PATH = "/etc/ld.so.cache"
LD_LIBRARY_ENV = "LD_LIBRARY_PATH"

LIB_EXTENSIONS = {
    ".so": "Shared Object",
    ".so.0": "Shared Object (versioned)",
    ".a": "Static Archive",
    ".la": "Libtool Archive",
    ".o": "Object File",
    ".pic.o": "PIC Object File",
}

PKG_CONFIG_DIR = "/usr/lib/pkgconfig"
PKG_CONFIG_PATH = "/usr/share/pkgconfig"


# ─── Enums ───────────────────────────────────────────────────────────────────

class LibraryType(IntEnum):
    """Library file types."""
    SHARED = 1
    STATIC = 2
    LIBTOOL = 3
    OBJECT = 4
    UNKNOWN = 5


class LibraryArch(IntEnum):
    """Library architecture targets."""
    X86_64 = 1
    I386 = 2
    AARCH64 = 3
    ARM = 4
    RISCV = 5
    MIPS = 6
    PPC64 = 7
    S390X = 8
    UNKNOWN = 9


class LibraryStatus(IntEnum):
    """Library installation status."""
    INSTALLED = 1
    UPDATED = 2
    DEPRECATED = 3
    BROKEN = 4
    MISSING = 5


class SymbolBinding(IntEnum):
    """ELF symbol binding types."""
    LOCAL = 0
    GLOBAL = 1
    WEAK = 2
    GNU_UNIQUE = 10


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class LibrarySymbol:
    """Represents an exported symbol from a library."""
    name: str
    version: str = ""
    binding: SymbolBinding = SymbolBinding.GLOBAL
    size: int = 0
    section: str = ""
    is_defined: bool = True
    is_function: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "binding": self.binding.name,
            "size": self.size,
            "section": self.section,
            "is_defined": self.is_defined,
            "is_function": self.is_function,
        }


@dataclass
class LibraryDependency:
    """Represents a library dependency."""
    name: str
    version: str = ""
    needed: bool = True
    soname: str = ""
    path: str = ""
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "needed": self.needed,
            "soname": self.soname,
            "path": self.path,
            "resolved": self.resolved,
        }


@dataclass
class LibraryMetadata:
    """Complete metadata for a library file."""
    path: str
    name: str
    lib_type: LibraryType = LibraryType.UNKNOWN
    arch: LibraryArch = LibraryArch.UNKNOWN
    status: LibraryStatus = LibraryStatus.INSTALLED
    size: int = 0
    soname: str = ""
    version: str = ""
    description: str = ""
    symbols: List[LibrarySymbol] = field(default_factory=list)
    dependencies: List[LibraryDependency] = field(default_factory=list)
    rpath: str = ""
    runpath: str = ""
    build_id: str = ""
    md5: str = ""
    sha256: str = ""
    installed_by: str = ""
    install_date: str = ""
    tags: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "lib_type": self.lib_type.name,
            "arch": self.arch.name,
            "status": self.status.name,
            "size": self.size,
            "soname": self.soname,
            "version": self.version,
            "description": self.description,
            "symbol_count": len(self.symbols),
            "dependency_count": len(self.dependencies),
            "dependencies": [d.to_dict() for d in self.dependencies],
            "rpath": self.rpath,
            "runpath": self.runpath,
            "build_id": self.build_id,
            "installed_by": self.installed_by,
            "tags": sorted(self.tags),
        }


@dataclass
class LibraryIndex:
    """Searchable index entry for a library."""
    name: str
    path: str
    lib_type: LibraryType
    arch: LibraryArch
    version: str
    provides: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "lib_type": self.lib_type.name,
            "arch": self.arch.name,
            "version": self.version,
            "provides": self.provides,
            "requires": self.requires,
        }


@dataclass
class LdConfigEntry:
    """An entry from ld.so.conf."""
    path: str
    is_native: bool = True
    is_include: bool = False
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "is_native": self.is_native,
            "is_include": self.is_include,
            "priority": self.priority,
        }


@dataclass
class PkgConfigEntry:
    """A pkg-config package entry."""
    name: str
    version: str
    description: str = ""
    cflags: str = ""
    libs: str = ""
    requires: List[str] = field(default_factory=list)
    path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "cflags": self.cflags,
            "libs": self.libs,
            "requires": self.requires,
            "path": self.path,
        }


# ─── Library Manager ────────────────────────────────────────────────────────

class LibraryManager:
    """
    Manages /usr/lib - program libraries, shared objects,
    static archives, and library resolution.

    Responsibilities:
        - Discover and catalog libraries in /usr/lib paths
        - Parse library metadata (ELF headers, soname, version)
        - Manage library dependencies and resolution
        - Maintain library index for search
        - Parse ld.so.conf and ld.so.cache
        - Handle pkg-config integration
        - Provide library installation/removal
        - Track library versions and ABI compatibility
    """

    def __init__(self) -> None:
        self._libraries: Dict[str, LibraryMetadata] = {}
        self._index: Dict[str, List[LibraryIndex]] = {}
        self._soname_index: Dict[str, List[str]] = {}
        self._ld_config: List[LdConfigEntry] = []
        self._pkg_config: Dict[str, PkgConfigEntry] = {}
        self._search_paths: List[str] = list(LIB_PATHS)
        self._cache: Dict[str, Any] = {}
        self._initialized = False
        self._scan_lock = False

    def initialize(self) -> None:
        """Initialize the library manager and scan paths."""
        if self._initialized:
            return
        self._scan_all_paths()
        self._load_ld_config()
        self._load_pkg_config()
        self._initialized = True

    def _scan_all_paths(self) -> None:
        """Scan all configured library paths."""
        if self._scan_lock:
            return
        self._scan_lock = True
        try:
            for path in self._search_paths:
                self._scan_directory(path)
        finally:
            self._scan_lock = False

    def _scan_directory(self, directory: str) -> None:
        """Scan a directory for library files."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return

        for entry in dir_path.rglob("*"):
            if entry.is_file() and self._is_library_file(entry.name):
                meta = self._parse_library(entry)
                if meta:
                    self._libraries[str(entry)] = meta
                    self._add_to_index(meta)

    def _is_library_file(self, filename: str) -> bool:
        """Check if filename is a known library type."""
        for ext in LIB_EXTENSIONS:
            if filename.endswith(ext):
                return True
        if filename.startswith("lib") and "." in filename:
            return True
        return False

    def _parse_library(self, path: Path) -> Optional[LibraryMetadata]:
        """Parse a library file and extract metadata."""
        try:
            stat = path.stat()
            lib_type = self._detect_type(path.name)
            arch = self._detect_arch(path.parent)
            name = self._extract_lib_name(path.name)
            version = self._extract_version(path.name)
            soname = self._extract_soname(path.name)

            return LibraryMetadata(
                path=str(path),
                name=name,
                lib_type=lib_type,
                arch=arch,
                status=LibraryStatus.INSTALLED,
                size=stat.st_size,
                soname=soname,
                version=version,
            )
        except (OSError, ValueError):
            return None

    def _detect_type(self, filename: str) -> LibraryType:
        """Detect library type from filename."""
        if ".so" in filename:
            return LibraryType.SHARED
        if filename.endswith(".a"):
            return LibraryType.STATIC
        if filename.endswith(".la"):
            return LibraryType.LIBTOOL
        if filename.endswith(".o"):
            return LibraryType.OBJECT
        return LibraryType.UNKNOWN

    def _detect_arch(self, parent: Path) -> LibraryArch:
        """Detect architecture from directory path."""
        path_str = str(parent).lower()
        if "x86_64" in path_str or "amd64" in path_str:
            return LibraryArch.X86_64
        if "i386" in path_str or "i686" in path_str or "i586" in path_str:
            return LibraryArch.I386
        if "aarch64" in path_str or "arm64" in path_str:
            return LibraryArch.AARCH64
        if "arm" in path_str:
            return LibraryArch.ARM
        if "riscv" in path_str:
            return LibraryArch.RISCV
        if "mips" in path_str:
            return LibraryArch.MIPS
        if "ppc64" in path_str:
            return LibraryArch.PPC64
        if "s390x" in path_str:
            return LibraryArch.S390X
        return LibraryArch.X86_64

    def _extract_lib_name(self, filename: str) -> str:
        """Extract library name from filename."""
        name = filename
        if name.startswith("lib"):
            name = name[3:]
        for ext in [".so", ".a", ".la", ".o"]:
            if ext in name:
                name = name[:name.index(ext)]
                break
        parts = name.split(".")
        if parts and parts[0].isdigit():
            name = ".".join(parts[:0]) if len(parts) > 1 else ""
        return f"lib{filename[:filename.index('.')]}" if "." in filename else filename

    def _extract_version(self, filename: str) -> str:
        """Extract version from filename."""
        parts = filename.split(".")
        if "so" in parts:
            so_idx = parts.index("so")
            if so_idx + 1 < len(parts) and parts[so_idx + 1].isdigit():
                return parts[so_idx + 1]
        return ""

    def _extract_soname(self, filename: str) -> str:
        """Extract SONAME from filename."""
        if ".so" in filename:
            idx = filename.index(".so")
            return filename[:idx + 3]
        return filename

    def _add_to_index(self, meta: LibraryMetadata) -> None:
        """Add library to search index."""
        name = meta.name
        if name not in self._index:
            self._index[name] = []
        self._index[name].append(LibraryIndex(
            name=name,
            path=meta.path,
            lib_type=meta.lib_type,
            arch=meta.arch,
            version=meta.version,
        ))

        if meta.soname:
            if meta.soname not in self._soname_index:
                self._soname_index[meta.soname] = []
            self._soname_index[meta.soname].append(meta.path)

    def _load_ld_config(self) -> None:
        """Load ld.so.conf configuration."""
        config_path = Path(LD_CONFIG_PATH)
        if not config_path.exists():
            return
        try:
            lines = config_path.read_text().splitlines()
            for i, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("include"):
                    include_path = line.split(None, 1)[1] if len(line.split()) > 1 else ""
                    self._ld_config.append(LdConfigEntry(
                        path=include_path,
                        is_include=True,
                        priority=i,
                    ))
                else:
                    self._ld_config.append(LdConfigEntry(
                        path=line,
                        is_native=True,
                        priority=i,
                    ))
        except OSError:
            pass

    def _load_pkg_config(self) -> None:
        """Load pkg-config .pc files."""
        for pkg_dir in [PKG_CONFIG_DIR, PKG_CONFIG_PATH]:
            dir_path = Path(pkg_dir)
            if not dir_path.exists():
                continue
            for pc_file in dir_path.glob("*.pc"):
                entry = self._parse_pc_file(pc_file)
                if entry:
                    self._pkg_config[entry.name] = entry

    def _parse_pc_file(self, path: Path) -> Optional[PkgConfigEntry]:
        """Parse a .pc pkg-config file."""
        try:
            lines = path.read_text().splitlines()
            name = ""
            version = ""
            description = ""
            cflags = ""
            libs = ""
            requires: List[str] = []
            for line in lines:
                if line.startswith("Name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
                elif line.startswith("Description:"):
                    description = line.split(":", 1)[1].strip()
                elif line.startswith("Cflags:"):
                    cflags = line.split(":", 1)[1].strip()
                elif line.startswith("Libs:"):
                    libs = line.split(":", 1)[1].strip()
                elif line.startswith("Requires:"):
                    req_str = line.split(":", 1)[1].strip()
                    requires = [r.strip() for r in req_str.split() if r.strip()]
            if name:
                return PkgConfigEntry(
                    name=name,
                    version=version,
                    description=description,
                    cflags=cflags,
                    libs=libs,
                    requires=requires,
                    path=str(path),
                )
        except OSError:
            pass
        return None

    # ─── Public API ──────────────────────────────────────────────────────

    def get_library(self, path: str) -> Optional[LibraryMetadata]:
        """Get metadata for a specific library."""
        return self._libraries.get(path)

    def find_libraries(self, name: str) -> List[LibraryMetadata]:
        """Find libraries by name."""
        results = []
        for meta in self._libraries.values():
            if meta.name == name or name in meta.name:
                results.append(meta)
        return results

    def find_by_soname(self, soname: str) -> List[LibraryMetadata]:
        """Find libraries by SONAME."""
        results = []
        for meta in self._libraries.values():
            if meta.soname == soname:
                results.append(meta)
        return results

    def get_dependencies(self, path: str) -> List[LibraryDependency]:
        """Get dependencies for a library."""
        meta = self._libraries.get(path)
        return meta.dependencies if meta else []

    def get_dependents(self, path: str) -> List[str]:
        """Find libraries that depend on the given library."""
        target_name = Path(path).name
        dependents = []
        for lib_path, meta in self._libraries.items():
            for dep in meta.dependencies:
                if dep.name == target_name or target_name in dep.name:
                    dependents.append(lib_path)
                    break
        return dependents

    def search(self, query: str) -> List[LibraryIndex]:
        """Search library index."""
        results = []
        query_lower = query.lower()
        for name, entries in self._index.items():
            if query_lower in name.lower():
                results.extend(entries)
        return results

    def get_ld_config(self) -> List[LdConfigEntry]:
        """Get ld.so.conf entries."""
        return list(self._ld_config)

    def get_pkg_config(self, package: str) -> Optional[PkgConfigEntry]:
        """Get pkg-config info for a package."""
        return self._pkg_config.get(package)

    def search_pkg_config(self, query: str) -> List[PkgConfigEntry]:
        """Search pkg-config packages."""
        results = []
        query_lower = query.lower()
        for name, entry in self._pkg_config.items():
            if query_lower in name.lower() or query_lower in entry.description.lower():
                results.append(entry)
        return results

    def list_libraries(self) -> List[LibraryMetadata]:
        """List all discovered libraries."""
        return list(self._libraries.values())

    def list_by_type(self, lib_type: LibraryType) -> List[LibraryMetadata]:
        """List libraries of a specific type."""
        return [m for m in self._libraries.values() if m.lib_type == lib_type]

    def list_by_arch(self, arch: LibraryArch) -> List[LibraryMetadata]:
        """List libraries for a specific architecture."""
        return [m for m in self._libraries.values() if m.arch == arch]

    def get_statistics(self) -> Dict[str, Any]:
        """Get library statistics."""
        total = len(self._libraries)
        by_type = {}
        for lib_type in LibraryType:
            count = len([m for m in self._libraries.values() if m.lib_type == lib_type])
            if count > 0:
                by_type[lib_type.name] = count
        by_arch = {}
        for arch in LibraryArch:
            count = len([m for m in self._libraries.values() if m.arch == arch])
            if count > 0:
                by_arch[arch.name] = count
        total_size = sum(m.size for m in self._libraries.values())
        return {
            "total_libraries": total,
            "by_type": by_type,
            "by_arch": by_arch,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "pkg_config_packages": len(self._pkg_config),
            "ld_config_entries": len(self._ld_config),
            "search_paths": len(self._search_paths),
        }

    def add_search_path(self, path: str) -> bool:
        """Add a library search path."""
        if path not in self._search_paths:
            self._search_paths.append(path)
            return True
        return False

    def remove_search_path(self, path: str) -> bool:
        """Remove a library search path."""
        if path in self._search_paths:
            self._search_paths.remove(path)
            return True
        return False

    def refresh(self) -> None:
        """Refresh library cache."""
        self._libraries.clear()
        self._index.clear()
        self._soname_index.clear()
        self._initialized = False
        self.initialize()


# ─── Global Singleton ────────────────────────────────────────────────────────

_global_lib_manager: Optional[LibraryManager] = None


def get_global_lib_manager() -> LibraryManager:
    """Get or create the global library manager."""
    global _global_lib_manager
    if _global_lib_manager is None:
        _global_lib_manager = LibraryManager()
        _global_lib_manager.initialize()
    return _global_lib_manager
