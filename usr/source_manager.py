"""
UmerOS Source Code Manager (/usr/src)
======================================
Kernel and package source code management.

Reference: Filesystem Hierarchy - /usr/src
  /usr/src holds source code for the kernel, package build
  trees (RPM, DEB), and development headers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ─── Constants ───────────────────────────────────────────────────────────────

SRC_PATHS = [
    "/usr/src",
    "/usr/src/",
    "/usr/src/headers",
    "/usr/src/modules",
    "/usr/src/RPM",
    "/usr/src/deb",
]

KERNEL_FILES = [
    "Makefile",
    "Kconfig",
    "README",
    "COPYING",
    "CREDITS",
    "MAINTAINERS",
    "REPORTING-BUGS",
    "Rules.make",
    ".config",
    ".depend",
    ".hdepend",
]

RPM_SUBDIRS = [
    "BUILD",
    "RPMS",
    "SOURCES",
    "SPECS",
    "SRPMS",
]

DEB_SUBDIRS = [
    "deb",
    "debian",
    "build-area",
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class SourceType(IntEnum):
    """Types of source trees."""
    KERNEL = 1
    MODULE = 2
    RPM_PACKAGE = 3
    DEB_PACKAGE = 4
    CUSTOM = 5
    HEADER = 6


class BuildSystem(IntEnum):
    """Build system types."""
    MAKE = 1
    CMAKE = 2
    AUTOCONF = 3
    MESON = 4
    CARGO = 5
    GO = 6
    NPM = 7
    PIP = 8
    RUST = 9
    UNKNOWN = 10


class KernelConfig(IntEnum):
    """Kernel configuration states."""
    NOT_CONFIGURED = 1
    CONFIGURED = 2
    COMPILED = 3
    INSTALLED = 4


class PackageFormat(IntEnum):
    """Package source formats."""
    RPM = 1
    DEB = 2
    PKGBUILD = 3
    EBUILD = 4
    SPEC = 5
    UNKNOWN = 6


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class KernelVersion:
    """Kernel version information."""
    major: int = 0
    minor: int = 0
    patch: int = 0
    sublevel: int = 0
    extra: str = ""
    full: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "sublevel": self.sublevel,
            "extra": self.extra,
            "full": self.full,
        }


@dataclass
class SourceTree:
    """Represents a source code tree."""
    path: str
    name: str
    source_type: SourceType = SourceType.CUSTOM
    build_system: BuildSystem = BuildSystem.UNKNOWN
    version: str = ""
    description: str = ""
    files: List[str] = field(default_factory=list)
    subdirs: List[str] = field(default_factory=list)
    config_state: KernelConfig = KernelConfig.NOT_CONFIGURED
    package_format: PackageFormat = PackageFormat.UNKNOWN
    maintainer: str = ""
    license: str = ""
    build_deps: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    size_bytes: int = 0
    last_modified: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "source_type": self.source_type.name,
            "build_system": self.build_system.name,
            "version": self.version,
            "description": self.description,
            "file_count": len(self.files),
            "subdir_count": len(self.subdirs),
            "config_state": self.config_state.name,
            "package_format": self.package_format.name,
            "maintainer": self.maintainer,
            "license": self.license,
            "build_deps": self.build_deps,
            "tags": sorted(self.tags),
            "size_bytes": self.size_bytes,
        }


@dataclass
class KernelSource:
    """Kernel source tree metadata."""
    path: str
    version: KernelVersion = field(default_factory=KernelVersion)
    config: KernelConfig = KernelConfig.NOT_CONFIGURED
    config_path: str = ""
    has_modules: bool = False
    module_count: int = 0
    has_headers: bool = False
    architecture: str = ""
    defconfig: str = ""
    config_options: Dict[str, str] = field(default_factory=dict)
    maintainers: List[str] = field(default_factory=list)
    credits_file: str = ""
    readme: str = ""
    license: str = "GPL-2.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "version": self.version.to_dict(),
            "config": self.config.name,
            "config_path": self.config_path,
            "has_modules": self.has_modules,
            "module_count": self.module_count,
            "has_headers": self.has_headers,
            "architecture": self.architecture,
            "defconfig": self.defconfig,
            "maintainers": self.maintainers,
            "license": self.license,
        }


@dataclass
class PackageSource:
    """A package source tree (RPM, DEB, etc.)."""
    path: str
    name: str
    version: str = ""
    release: str = ""
    package_format: PackageFormat = PackageFormat.UNKNOWN
    spec_file: str = ""
    source_tarball: str = ""
    patches: List[str] = field(default_factory=list)
    build_script: str = ""
    dependencies: List[str] = field(default_factory=list)
    description: str = ""
    architecture: str = ""
    changelog: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "version": self.version,
            "release": self.release,
            "package_format": self.package_format.name,
            "spec_file": self.spec_file,
            "source_tarball": self.source_tarball,
            "patch_count": len(self.patches),
            "build_script": self.build_script,
            "dependencies": self.dependencies,
            "description": self.description,
            "architecture": self.architecture,
            "changelog_entries": len(self.changelog),
        }


@dataclass
class BuildTree:
    """RPM/DEB build tree structure."""
    base_path: str
    package_format: PackageFormat = PackageFormat.RPM
    subdirs: Dict[str, str] = field(default_factory=dict)
    build_count: int = 0
    rpms: List[str] = field(default_factory=list)
    srpms: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    specs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_path": self.base_path,
            "package_format": self.package_format.name,
            "subdirs": self.subdirs,
            "build_count": self.build_count,
            "rpm_count": len(self.rpms),
            "srpm_count": len(self.srpms),
            "source_count": len(self.sources),
            "spec_count": len(self.specs),
        }


# ─── Source Manager ─────────────────────────────────────────────────────────

class SourceManager:
    """
    Manages /usr/src - source code trees, kernel sources,
    and package build trees.

    Responsibilities:
        - Discover and catalog source trees in /usr/src
        - Parse kernel source metadata (version, config, Makefile)
        - Manage RPM/DEB build tree structures
        - Track kernel configuration state
        - Handle header file packages
        - Provide source search and browsing
        - Track build dependencies
    """

    def __init__(self) -> None:
        self._sources: Dict[str, SourceTree] = {}
        self._kernel: Optional[KernelSource] = None
        self._packages: Dict[str, PackageSource] = {}
        self._build_trees: Dict[str, BuildTree] = {}
        self._search_paths: List[str] = list(SRC_PATHS)
        self._initialized = False

    def initialize(self) -> None:
        """Initialize source manager and scan paths."""
        if self._initialized:
            return
        self._scan_all_paths()
        self._initialized = True

    def _scan_all_paths(self) -> None:
        """Scan all configured source paths."""
        for path in self._search_paths:
            self._scan_directory(path)

    def _scan_directory(self, directory: str) -> None:
        """Scan a directory for source trees."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return

        for entry in dir_path.iterdir():
            if entry.is_dir():
                self._analyze_source_tree(entry)

    def _analyze_source_tree(self, path: Path) -> None:
        """Analyze a directory to determine source tree type."""
        files = [f.name for f in path.iterdir() if f.is_file()]
        subdirs = [d.name for d in path.iterdir() if d.is_dir()]

        source_type = self._detect_source_type(path, files, subdirs)
        build_system = self._detect_build_system(files, subdirs)

        tree = SourceTree(
            path=str(path),
            name=path.name,
            source_type=source_type,
            build_system=build_system,
            files=files,
            subdirs=subdirs,
        )

        if source_type == SourceType.KERNEL:
            self._parse_kernel_source(path, tree)
        elif source_type in (SourceType.RPM_PACKAGE, SourceType.DEB_PACKAGE):
            self._parse_package_source(path, tree)

        self._sources[str(path)] = tree

    def _detect_source_type(self, path: Path, files: List[str], subdirs: List[str]) -> SourceType:
        """Detect the type of source tree."""
        name = path.name.lower()

        if name.startswith("linux") and "Makefile" in files:
            return SourceType.KERNEL
        if "Kconfig" in files and "Makefile" in files:
            return SourceType.KERNEL
        if "RPM" in path.parent.name or any(d in subdirs for d in RPM_SUBDIRS):
            return SourceType.RPM_PACKAGE
        if "deb" in path.parent.name.lower() or any(d in subdirs for d in DEB_SUBDIRS):
            return SourceType.DEB_PACKAGE
        if "include" in subdirs or "headers" in subdirs:
            return SourceType.HEADER
        if any(f in files for f in ["Makefile", "CMakeLists.txt", "configure.ac", "meson.build"]):
            return SourceType.CUSTOM
        if any(f.startswith("module") for f in subdirs):
            return SourceType.MODULE
        return SourceType.CUSTOM

    def _detect_build_system(self, files: List[str], subdirs: List[str]) -> BuildSystem:
        """Detect build system from files."""
        if "Makefile" in files or "makefile" in files:
            return BuildSystem.MAKE
        if "CMakeLists.txt" in files:
            return BuildSystem.CMAKE
        if "configure.ac" in files or "configure" in files:
            return BuildSystem.AUTOCONF
        if "meson.build" in files:
            return BuildSystem.MESON
        if "Cargo.toml" in files:
            return BuildSystem.CARGO
        if "go.mod" in files:
            return BuildSystem.GO
        if "package.json" in files:
            return BuildSystem.NPM
        if "setup.py" in files or "pyproject.toml" in files:
            return BuildSystem.PIP
        if "Cargo.lock" in files:
            return BuildSystem.RUST
        return BuildSystem.UNKNOWN

    def _parse_kernel_source(self, path: Path, tree: SourceTree) -> None:
        """Parse kernel source metadata."""
        version = KernelVersion()
        config_state = KernelConfig.NOT_CONFIGURED
        config_path = ""

        makefile = path / "Makefile"
        if makefile.exists():
            try:
                lines = makefile.read_text(errors="replace").splitlines()[:10]
                for line in lines:
                    if line.startswith("VERSION"):
                        version.major = self._extract_num(line)
                    elif line.startswith("PATCHLEVEL"):
                        version.minor = self._extract_num(line)
                    elif line.startswith("SUBLEVEL"):
                        version.patch = self._extract_num(line)
                    elif line.startswith("EXTRAVERSION"):
                        version.extra = line.split("=", 1)[1].strip().strip('"')
                version.full = f"{version.major}.{version.minor}.{version.patch}"
                if version.extra:
                    version.full += f"-{version.extra}"
                tree.version = version.full
            except OSError:
                pass

        config_file = path / ".config"
        if config_file.exists():
            config_state = KernelConfig.CONFIGURED
            config_path = str(config_file)

        kernel = KernelSource(
            path=str(path),
            version=version,
            config=config_state,
            config_path=config_path,
        )
        self._kernel = kernel

    def _extract_num(self, line: str) -> int:
        """Extract numeric value from Makefile variable line."""
        try:
            return int(line.split("=", 1)[1].strip())
        except (ValueError, IndexError):
            return 0

    def _parse_package_source(self, path: Path, tree: SourceTree) -> None:
        """Parse package source tree."""
        name = path.name
        pkg_format = PackageFormat.UNKNOWN
        if "RPM" in path.parent.name or path.parent.name == "RPM":
            pkg_format = PackageFormat.RPM
        elif "deb" in path.parent.name.lower():
            pkg_format = PackageFormat.DEB

        pkg = PackageSource(
            path=str(path),
            name=name,
            package_format=pkg_format,
        )
        self._packages[str(path)] = pkg

    def _detect_build_tree(self, path: Path) -> Optional[BuildTree]:
        """Detect and parse a build tree structure."""
        if not path.exists():
            return None

        subdirs = {d.name: str(path / d) for d in path.iterdir() if d.is_dir()}
        tree = BuildTree(
            base_path=str(path),
            subdirs=subdirs,
        )

        rpm_dir = path / "RPMS"
        if rpm_dir.exists():
            tree.package_format = PackageFormat.RPM
            tree.rpms = [str(f) for f in rpm_dir.rglob("*.rpm")]

        srpms_dir = path / "SRPMS"
        if srpms_dir.exists():
            tree.srpms = [str(f) for f in srpms_dir.glob("*.src.rpm")]

        sources_dir = path / "SOURCES"
        if sources_dir.exists():
            tree.sources = [str(f) for f in sources_dir.iterdir() if f.is_file()]

        specs_dir = path / "SPECS"
        if specs_dir.exists():
            tree.specs = [str(f) for f in specs_dir.glob("*.spec")]

        tree.build_count = len(tree.rpms) + len(tree.srpms)
        return tree

    # ─── Public API ──────────────────────────────────────────────────────

    def get_source(self, path: str) -> Optional[SourceTree]:
        """Get source tree metadata."""
        return self._sources.get(path)

    def find_sources(self, query: str) -> List[SourceTree]:
        """Find source trees by name."""
        results = []
        query_lower = query.lower()
        for tree in self._sources.values():
            if query_lower in tree.name.lower() or query_lower in tree.path.lower():
                results.append(tree)
        return results

    def list_sources(self) -> List[SourceTree]:
        """List all discovered source trees."""
        return list(self._sources.values())

    def list_by_type(self, source_type: SourceType) -> List[SourceTree]:
        """List source trees of a specific type."""
        return [t for t in self._sources.values() if t.source_type == source_type]

    def list_by_build_system(self, build_system: BuildSystem) -> List[SourceTree]:
        """List source trees using a specific build system."""
        return [t for t in self._sources.values() if t.build_system == build_system]

    def get_kernel(self) -> Optional[KernelSource]:
        """Get kernel source metadata."""
        return self._kernel

    def get_kernel_version(self) -> Optional[str]:
        """Get kernel version string."""
        if self._kernel:
            return self._kernel.version.full
        return None

    def get_packages(self) -> List[PackageSource]:
        """Get all package sources."""
        return list(self._packages.values())

    def get_build_tree(self, path: str) -> Optional[BuildTree]:
        """Get or create build tree metadata."""
        if path in self._build_trees:
            return self._build_trees[path]
        tree = self._detect_build_tree(Path(path))
        if tree:
            self._build_trees[path] = tree
        return tree

    def get_statistics(self) -> Dict[str, Any]:
        """Get source statistics."""
        total = len(self._sources)
        by_type = {}
        for st in SourceType:
            count = len([t for t in self._sources.values() if t.source_type == st])
            if count > 0:
                by_type[st.name] = count
        by_build = {}
        for bs in BuildSystem:
            count = len([t for t in self._sources.values() if t.build_system == bs])
            if count > 0:
                by_build[bs.name] = count
        return {
            "total_sources": total,
            "by_type": by_type,
            "by_build_system": by_build,
            "kernel_found": self._kernel is not None,
            "package_count": len(self._packages),
            "build_tree_count": len(self._build_trees),
            "search_paths": len(self._search_paths),
        }

    def add_search_path(self, path: str) -> bool:
        """Add a source search path."""
        if path not in self._search_paths:
            self._search_paths.append(path)
            return True
        return False

    def refresh(self) -> None:
        """Refresh source cache."""
        self._sources.clear()
        self._kernel = None
        self._packages.clear()
        self._build_trees.clear()
        self._initialized = False
        self.initialize()


# ─── Global Singleton ────────────────────────────────────────────────────────

_global_source_manager: Optional[SourceManager] = None


def get_global_source_manager() -> SourceManager:
    """Get or create the global source manager."""
    global _global_source_manager
    if _global_source_manager is None:
        _global_source_manager = SourceManager()
        _global_source_manager.initialize()
    return _global_source_manager
