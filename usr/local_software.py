"""
UmerOS Local Software Manager
=============================
Locally installed software management under /usr/local.

The /usr/local hierarchy is reserved for local software installations
that are not managed by the system package manager. Per FHS:
  - /usr/local/bin  : Locally installed binaries
  - /usr/local/sbin : Locally installed system binaries
  - /usr/local/lib  : Local libraries
  - /usr/local/etc  : Local configuration files
  - /usr/local/share: Local architecture-independent data
  - /usr/local/include: Local C header files
  - /usr/local/src  : Local source code

This module manages discovery, installation tracking, and versioning
of locally installed software.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import (
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)


# ============================================================================
# Constants
# ============================================================================

LOCAL_BASE_PATH: str = "/usr/local"

LOCAL_SUBDIRS: Dict[str, str] = {
    "bin": "Local executables",
    "sbin": "Local system executables",
    "lib": "Local libraries (primary)",
    "lib64": "Local 64-bit libraries (lib<qual>)",
    "lib32": "Local 32-bit libraries (lib<qual>)",
    "libx32": "Local x32 libraries (lib<qual>)",
    "libexec": "Local helper executables",
    "etc": "Local configuration",
    "share": "Local shared data",
    "share/color": "Color definition files for applications",
    "include": "Local header files",
    "src": "Local source code",
    "man": "Local manual pages",
    "info": "Local info documents",
    "games": "Local games",
}

# FHS 3.0 lib<qual> — alternate format libraries
# On 64-bit systems: lib64 holds 64-bit .so files, lib holds 32-bit or compat
# On 32-bit systems: lib32 holds 32-bit, lib holds compat
# On x32 ABI systems: libx32 holds x32 ABI libraries
LIB_QUAL_DIRS = ["lib", "lib64", "lib32", "libx32"]

# FHS 3.0 Section 4.11.5 — color definitions
SHARE_COLOR_DIRS = ["color", "pixmaps"]


# ============================================================================
# Enums
# ============================================================================

class SoftwareStatus(IntEnum):
    """Installation status of a software package."""
    INSTALLED = 0
    PARTIALLY_INSTALLED = 1
    BROKEN = 2
    REQUIRES_UPDATE = 3
    DEPRECATED = 4


class BinaryType(IntEnum):
    """Types of installed binaries."""
    EXECUTABLE = 0
    SCRIPT = 1
    LIBRARY = 2
    MODULE = 3
    CONFIG = 4
    DATA = 5


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class InstalledBinary:
    """A single installed binary or script."""
    name: str = ""
    path: str = ""
    binary_type: BinaryType = BinaryType.EXECUTABLE
    size_bytes: int = 0
    permissions: int = 0o755
    installed_at: float = 0.0
    modified_at: float = 0.0
    symlink_target: Optional[str] = None
    checksum: str = ""

    def is_symlink(self) -> bool:
        """Check if this is a symlink."""
        return self.symlink_target is not None

    def is_executable(self) -> bool:
        """Check if this file is executable."""
        return bool(self.permissions & 0o111)


@dataclass
class InstalledLibrary:
    """A shared library installed locally."""
    name: str = ""
    path: str = ""
    version: str = ""
    major: int = 0
    minor: int = 0
    patch: int = 0
    size_bytes: int = 0
    installed_at: float = 0.0
    dependencies: List[str] = field(default_factory=list)

    def soname(self) -> str:
        """Get the shared object name."""
        return f"{self.name}.so.{self.major}"


@dataclass
class SoftwarePackage:
    """A locally installed software package."""
    name: str = ""
    version: str = ""
    description: str = ""
    install_prefix: str = ""
    status: SoftwareStatus = SoftwareStatus.INSTALLED
    binaries: List[InstalledBinary] = field(default_factory=list)
    libraries: List[InstalledLibrary] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    data_files: List[str] = field(default_factory=list)
    installed_at: float = 0.0
    updated_at: float = 0.0
    source_url: str = ""
    source_hash: str = ""
    size_bytes: int = 0

    def total_size(self) -> int:
        """Get total size including binaries and libraries."""
        total = sum(b.size_bytes for b in self.binaries)
        total += sum(lib.size_bytes for lib in self.libraries)
        total += self.size_bytes
        return total

    def get_binaries_by_type(self, btype: BinaryType) -> List[InstalledBinary]:
        """Get binaries filtered by type."""
        return [b for b in self.binaries if b.binary_type == btype]

    def get_executables(self) -> List[InstalledBinary]:
        """Get all executable files."""
        return [
            b for b in self.binaries
            if b.binary_type == BinaryType.EXECUTABLE and b.is_executable()
        ]

    def add_binary(self, binary: InstalledBinary) -> None:
        """Add a binary to this package."""
        self.binaries.append(binary)
        self.size_bytes += binary.size_bytes

    def remove_binary(self, name: str) -> bool:
        """Remove a binary by name."""
        for i, b in enumerate(self.binaries):
            if b.name == name:
                self.size_bytes -= b.size_bytes
                del self.binaries[i]
                return True
        return False


@dataclass
class SourceTree:
    """A source code tree in /usr/local/src."""
    name: str = ""
    path: str = ""
    build_system: str = ""
    version: str = ""
    is_built: bool = False
    build_path: Optional[str] = None
    files: List[str] = field(default_factory=list)

    def has_makefile(self) -> bool:
        """Check if source tree has a Makefile."""
        return "Makefile" in self.files or "makefile" in self.files

    def has_configure(self) -> bool:
        """Check if source tree has a configure script."""
        return "configure" in self.files

    def has_cmake(self) -> bool:
        """Check if source tree uses CMake."""
        return "CMakeLists.txt" in self.files


@dataclass
class InstallRecord:
    """Record of a software installation."""
    package_name: str = ""
    install_time: float = 0.0
    install_method: str = ""
    installed_files: List[str] = field(default_factory=list)
    removed_files: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class LibQualEntry:
    """Represents a /usr/local/lib<qual> directory.

    FHS 3.0 Section 4.9.2: /usr/local/lib<qual> provides alternate
    format libraries (e.g., lib64 for 64-bit, lib32 for 32-bit).
    """
    name: str
    path: Path
    exists: bool = False
    is_symlink: bool = False
    symlink_target: Optional[str] = None
    description: str = ""
    files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "exists": self.exists,
            "is_symlink": self.is_symlink,
            "symlink_target": self.symlink_target,
            "description": self.description,
            "files": self.files,
        }


@dataclass
class ShareColorEntry:
    """Represents a /usr/local/share/color directory.

    FHS 3.0 Section 4.11.5: Color definitions for application UI.
    Typically contains .clr files or subdirectories per app.
    """
    name: str
    path: Path
    exists: bool = False
    files: List[str] = field(default_factory=list)
    is_symlink: bool = False
    symlink_target: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "exists": self.exists,
            "files": self.files,
            "is_symlink": self.is_symlink,
            "symlink_target": self.symlink_target,
        }


# ============================================================================
# Local Software Manager
# ============================================================================

class LocalSoftwareManager:
    """
    Manages locally installed software under /usr/local.

    Tracks installed packages, binaries, libraries, and source trees
    without interference from the system package manager.
    """

    def __init__(self) -> None:
        self._base_path: str = LOCAL_BASE_PATH
        self._packages: Dict[str, SoftwarePackage] = {}
        self._binaries: Dict[str, InstalledBinary] = {}
        self._libraries: Dict[str, InstalledLibrary] = {}
        self._source_trees: Dict[str, SourceTree] = {}
        self._install_records: List[InstallRecord] = []
        self._path_bins: List[str] = []

    # -- Path Management --

    def get_base_path(self) -> str:
        """Get the base local path."""
        return self._base_path

    def get_subdirectories(self) -> Dict[str, str]:
        """Get all known subdirectories."""
        return dict(LOCAL_SUBDIRS)

    def get_path_directories(self) -> List[str]:
        """Get directories that should be in PATH."""
        path_dirs: List[str] = []
        for subdir in ["bin", "sbin"]:
            dirpath = os.path.join(self._base_path, subdir)
            if os.path.isdir(dirpath):
                path_dirs.append(dirpath)
        return path_dirs

    # -- Package Management --

    def register_package(self, package: SoftwarePackage) -> None:
        """Register a locally installed package."""
        self._packages[package.name] = package
        for binary in package.binaries:
            self._binaries[binary.name] = binary
        for library in package.libraries:
            self._libraries[library.name] = library

    def unregister_package(self, name: str) -> bool:
        """Unregister a package."""
        if name not in self._packages:
            return False
        package = self._packages[name]
        for binary in package.binaries:
            self._binaries.pop(binary.name, None)
        for library in package.libraries:
            self._libraries.pop(library.name, None)
        del self._packages[name]
        return True

    def get_package(self, name: str) -> Optional[SoftwarePackage]:
        """Get a package by name."""
        return self._packages.get(name)

    def list_packages(self) -> List[SoftwarePackage]:
        """List all registered packages."""
        return list(self._packages.values())

    def find_packages_by_status(
        self, status: SoftwareStatus
    ) -> List[SoftwarePackage]:
        """Find packages by status."""
        return [
            pkg for pkg in self._packages.values()
            if pkg.status == status
        ]

    # -- Binary Management --

    def scan_binaries(self) -> int:
        """Scan /usr/local/bin and /usr/local/sbin for binaries."""
        count = 0
        for subdir in ["bin", "sbin"]:
            dirpath = os.path.join(self._base_path, subdir)
            if not os.path.isdir(dirpath):
                continue
            for entry in os.scandir(dirpath):
                if entry.is_file():
                    binary = self._create_binary_entry(entry)
                    if binary:
                        self._binaries[binary.name] = binary
                        count += 1
                elif entry.is_symlink():
                    try:
                        target = os.readlink(entry.path)
                        binary = InstalledBinary(
                            name=entry.name,
                            path=entry.path,
                            symlink_target=target,
                            installed_at=entry.stat().st_ctime if entry.exists() else 0,
                        )
                        self._binaries[binary.name] = binary
                        count += 1
                    except OSError:
                        pass
        return count

    def _create_binary_entry(self, entry: os.DirEntry) -> Optional[InstalledBinary]:
        """Create an InstalledBinary from a directory entry."""
        try:
            stat = entry.stat()
            binary_type = BinaryType.EXECUTABLE
            if entry.name.endswith((".sh", ".bash", ".py", ".pl", ".rb")):
                binary_type = BinaryType.SCRIPT
            elif entry.name.endswith((".so", ".so.", ".a")):
                binary_type = BinaryType.LIBRARY
            elif entry.name.endswith((".conf", ".cfg", ".ini")):
                binary_type = BinaryType.CONFIG
            return InstalledBinary(
                name=entry.name,
                path=entry.path,
                binary_type=binary_type,
                size_bytes=stat.st_size,
                permissions=stat.st_mode & 0o7777,
                installed_at=stat.st_ctime,
                modified_at=stat.st_mtime,
            )
        except (OSError, ValueError):
            return None

    def get_binary(self, name: str) -> Optional[InstalledBinary]:
        """Get a binary by name."""
        return self._binaries.get(name)

    def find_binary_in_path(self, name: str) -> Optional[InstalledBinary]:
        """Find a binary by searching PATH directories."""
        for path_dir in self.get_path_directories():
            full_path = os.path.join(path_dir, name)
            if os.path.exists(full_path):
                return self.get_binary(name)
        return None

    def list_binaries(self) -> List[InstalledBinary]:
        """List all discovered binaries."""
        return list(self._binaries.values())

    # -- Library Management --

    def scan_libraries(self) -> int:
        """Scan /usr/local/lib for shared libraries."""
        count = 0
        lib_path = os.path.join(self._base_path, "lib")
        if not os.path.isdir(lib_path):
            return 0
        for entry in os.scandir(lib_path):
            if entry.is_file():
                name = entry.name
                if ".so" in name or name.endswith(".a"):
                    library = self._create_library_entry(entry)
                    if library:
                        self._libraries[library.name] = library
                        count += 1
        return count

    def _create_library_entry(self, entry: os.DirEntry) -> Optional[InstalledLibrary]:
        """Create an InstalledLibrary from a directory entry."""
        try:
            stat = entry.stat()
            name = entry.name.split(".")[0]
            version_parts = entry.name.replace(f"{name}.so.", "").split(".")
            major = int(version_parts[0]) if version_parts and version_parts[0].isdigit() else 0
            minor = int(version_parts[1]) if len(version_parts) > 1 and version_parts[1].isdigit() else 0
            patch = int(version_parts[2]) if len(version_parts) > 2 and version_parts[2].isdigit() else 0
            return InstalledLibrary(
                name=name,
                path=entry.path,
                version=f"{major}.{minor}.{patch}",
                major=major,
                minor=minor,
                patch=patch,
                size_bytes=stat.st_size,
                installed_at=stat.st_ctime,
            )
        except (OSError, ValueError):
            return None

    def get_library(self, name: str) -> Optional[InstalledLibrary]:
        """Get a library by name."""
        return self._libraries.get(name)

    def list_libraries(self) -> List[InstalledLibrary]:
        """List all discovered libraries."""
        return list(self._libraries.values())

    # -- Source Tree Management --

    def scan_source_trees(self) -> int:
        """Scan /usr/local/src for source trees."""
        count = 0
        src_path = os.path.join(self._base_path, "src")
        if not os.path.isdir(src_path):
            return 0
        for entry in os.scandir(src_path):
            if entry.is_dir():
                source = self._create_source_tree(entry)
                if source:
                    self._source_trees[source.name] = source
                    count += 1
        return count

    def _create_source_tree(self, entry: os.DirEntry) -> Optional[SourceTree]:
        """Create a SourceTree from a directory entry."""
        try:
            files: List[str] = []
            for sub in os.scandir(entry.path):
                files.append(sub.name)
            build_system = ""
            if "CMakeLists.txt" in files:
                build_system = "cmake"
            elif "Makefile" in files or "makefile" in files:
                build_system = "make"
            elif "configure" in files:
                build_system = "autotools"
            elif "meson.build" in files:
                build_system = "meson"
            elif "Cargo.toml" in files:
                build_system = "cargo"
            elif "setup.py" in files or "pyproject.toml" in files:
                build_system = "python"
            return SourceTree(
                name=entry.name,
                path=entry.path,
                build_system=build_system,
                files=files,
            )
        except (OSError, PermissionError):
            return None

    def get_source_tree(self, name: str) -> Optional[SourceTree]:
        """Get a source tree by name."""
        return self._source_trees.get(name)

    def list_source_trees(self) -> List[SourceTree]:
        """List all source trees."""
        return list(self._source_trees.values())

    # -- Install Records --

    def record_install(self, record: InstallRecord) -> None:
        """Record an installation."""
        self._install_records.append(record)

    def get_install_history(self) -> List[InstallRecord]:
        """Get installation history."""
        return list(self._install_records)

    # -- lib<qual> Management (FHS 3.0 Section 4.9.2) --

    def ensure_lib_qual_dirs(self) -> List[LibQualEntry]:
        """Create all lib<qual> directories if missing.

        FHS 3.0: /usr/local/lib<qual> provides alternate format libraries.
        On a 64-bit system, lib64 holds 64-bit libraries and lib holds
        compat/32-bit libraries. This ensures all qual variants exist.
        """
        entries: List[LibQualEntry] = []
        for qual in LIB_QUAL_DIRS:
            path = Path(self._base_path) / qual
            entry = LibQualEntry(
                name=qual,
                path=path,
                exists=path.exists(),
                description=LOCAL_SUBDIRS.get(qual, f"Local {qual} libraries"),
            )
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                entry.exists = True
            if path.is_symlink():
                entry.is_symlink = True
                entry.symlink_target = str(path.resolve())
            if path.exists():
                entry.files = sorted(f for f in os.listdir(str(path))
                                     if not f.startswith('.'))
            entries.append(entry)
        return entries

    def get_lib_qual_entries(self) -> List[LibQualEntry]:
        """List current lib<qual> directories and their contents."""
        entries: List[LibQualEntry] = []
        for qual in LIB_QUAL_DIRS:
            path = Path(self._base_path) / qual
            entry = LibQualEntry(
                name=qual,
                path=path,
                exists=path.exists(),
                is_symlink=path.is_symlink(),
                symlink_target=str(path.resolve()) if path.is_symlink() else None,
                description=LOCAL_SUBDIRS.get(qual, f"Local {qual} libraries"),
            )
            if path.exists():
                entry.files = sorted(f for f in os.listdir(str(path))
                                     if not f.startswith('.'))
            entries.append(entry)
        return entries

    def ensure_lib_qual_symlink(self, source: str = "lib",
                                target: str = "lib64") -> bool:
        """Create a symlink between lib<qual> directories.

        Useful when lib64 should point to lib or vice versa.
        """
        try:
            source_path = Path(self._base_path) / source
            target_path = Path(self._base_path) / target
            if source_path.exists() and not target_path.exists():
                os.symlink(str(source_path), str(target_path))
                return True
            return target_path.exists() or target_path.is_symlink()
        except Exception:
            return False

    # -- share/color Management (FHS 3.0 Section 4.11.5) --

    def ensure_share_color(self) -> ShareColorEntry:
        """Create /usr/local/share/color with standard structure.

        FHS 3.0: Color definition files for application UI theming.
        """
        color_path = Path(self._base_path) / "share" / "color"
        color_path.mkdir(parents=True, exist_ok=True)

        entry = ShareColorEntry(
            name="color",
            path=color_path,
            exists=True,
        )

        # Create standard color subdirectories
        for subdir in ["icc", "palette", "term"]:
            (color_path / subdir).mkdir(exist_ok=True)

        entry.files = sorted(f for f in os.listdir(str(color_path))
                             if not f.startswith('.'))
        return entry

    def get_share_color(self) -> ShareColorEntry:
        """Get current share/color directory info."""
        color_path = Path(self._base_path) / "share" / "color"
        entry = ShareColorEntry(
            name="color",
            path=color_path,
            exists=color_path.exists(),
            is_symlink=color_path.is_symlink(),
            symlink_target=str(color_path.resolve()) if color_path.is_symlink() else None,
        )
        if color_path.exists():
            entry.files = sorted(f for f in os.listdir(str(color_path))
                                 if not f.startswith('.'))
        return entry

    def add_color_file(self, name: str, content: str) -> bool:
        """Add a color definition file to /usr/local/share/color.

        Args:
            name: Filename (e.g., "app_theme.clr")
            content: Color definition content

        Returns:
            True if created successfully
        """
        try:
            color_path = Path(self._base_path) / "share" / "color"
            color_path.mkdir(parents=True, exist_ok=True)
            with open(color_path / name, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception:
            return False

    # -- Search --

    def search_packages(self, query: str) -> List[SoftwarePackage]:
        """Search packages by name or description."""
        query_lower = query.lower()
        results: List[SoftwarePackage] = []
        for pkg in self._packages.values():
            if query_lower in pkg.name.lower():
                results.append(pkg)
            elif query_lower in pkg.description.lower():
                results.append(pkg)
        return results

    # -- Utility --

    def total_size(self) -> int:
        """Get total size of all installed software."""
        return sum(pkg.total_size() for pkg in self._packages.values())

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about locally installed software."""
        return {
            "packages": len(self._packages),
            "binaries": len(self._binaries),
            "libraries": len(self._libraries),
            "source_trees": len(self._source_trees),
            "install_records": len(self._install_records),
            "total_size_bytes": self.total_size(),
        }

    def clear(self) -> None:
        """Clear all indexed data."""
        self._packages.clear()
        self._binaries.clear()
        self._libraries.clear()
        self._source_trees.clear()
        self._install_records.clear()


# ============================================================================
# Global Singleton
# ============================================================================

_global_local_software: Optional[LocalSoftwareManager] = None


def get_global_local_software() -> LocalSoftwareManager:
    """Get or create the global LocalSoftwareManager instance."""
    global _global_local_software
    if _global_local_software is None:
        _global_local_software = LocalSoftwareManager()
    return _global_local_software
