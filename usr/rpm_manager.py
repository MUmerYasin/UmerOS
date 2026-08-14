"""
UmerOS RPM Manager (/usr/src/RPM)
=================================
RPM build structure for creating packages from source.

Reference: Filesystem Hierarchy - /usr/src/RPM
  /usr/src/RPM provides a substructure for building RPMs from SRPMs.
  Organisation of this branch is fairly logical with packages being
  organised according to a package's architecture.

  Directory structure:
  /usr/src/RPM/
  ├── BUILD        - Temporary store for RPM binary files being built
  ├── RPMS/        - Architecture-dependent RPM binary files
  │   ├── athlon/
  │   ├── i386/
  │   ├── i486/
  │   ├── i586/
  │   ├── i686/
  │   ├── x86_64/
  │   └── noarch/
  ├── SOURCES      - Source TAR files, patches, icon files
  ├── SPECS        - RPM SPEC files (build instructions)
  └── SRPMS        - Source RPM files resulting from builds
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional


# ─── Constants ───────────────────────────────────────────────────────────────

RPM_BASE_PATH = "/usr/src/RPM"

RPM_DIRECTORIES = {
    "BUILD": "/usr/src/RPM/BUILD",
    "RPMS": "/usr/src/RPM/RPMS",
    "SOURCES": "/usr/src/RPM/SOURCES",
    "SPECS": "/usr/src/RPM/SPECS",
    "SRPMS": "/usr/src/RPM/SRPMS",
}

SUPPORTED_ARCHITECTURES = [
    "noarch", "i386", "i486", "i586", "i686", "x86_64",
    "athlon", "amd64", "arm64", "ppc64le", "s390x", "aarch64",
]

DEFAULT_SPEC_DIRECTIVES = [
    "Name", "Version", "Release", "License", "Summary",
    "Group", "Source", "Patch", "BuildRoot", "Requires",
    "BuildRequires", "Provides", "Conflicts", "Obsoletes",
    "%description", "%prep", "%build", "%install", "%files",
    "%changelog", "%clean", "%pre", "%post", "%preun", "%postun",
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class RPMPackageStatus(IntEnum):
    """RPM package build status."""
    PENDING = 1
    BUILDING = 2
    COMPLETED = 3
    FAILED = 4
    INSTALLED = 5


class RPMSpecDirective(IntEnum):
    """RPM SPEC file directives."""
    NAME = 1
    VERSION = 2
    RELEASE = 3
    LICENSE = 4
    SUMMARY = 5
    GROUP = 6
    SOURCE = 7
    PATCH = 8
    BUILDROOT = 9
    REQUIRES = 10
    BUILD_REQUIRES = 11
    PROVIDES = 12
    CONFLICTS = 13
    OBSOLETES = 14


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class RPMSpec:
    """An RPM SPEC file definition."""
    name: str
    path: str
    version: str = ""
    release: str = ""
    license: str = ""
    summary: str = ""
    group: str = ""
    source_url: str = ""
    patches: List[str] = field(default_factory=list)
    build_root: str = ""
    requires: List[str] = field(default_factory=list)
    build_requires: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    obsoletes: List[str] = field(default_factory=list)
    description: str = ""
    prep_script: str = ""
    build_script: str = ""
    install_script: str = ""
    files_section: str = ""
    changelog: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "path": self.path,
            "version": self.version, "release": self.release,
            "license": self.license, "summary": self.summary,
            "group": self.group, "source_url": self.source_url,
            "patches": self.patches, "build_root": self.build_root,
            "requires": self.requires, "build_requires": self.build_requires,
            "provides": self.provides, "conflicts": self.conflicts,
            "obsoletes": self.obsoletes, "description": self.description,
        }


@dataclass
class RPMPackage:
    """An RPM package definition."""
    name: str
    version: str = ""
    release: str = ""
    architecture: str = "noarch"
    filename: str = ""
    path: str = ""
    status: RPMPackageStatus = RPMPackageStatus.PENDING
    size_bytes: int = 0
    build_time: str = ""
    spec: Optional[RPMSpec] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "version": self.version,
            "release": self.release, "architecture": self.architecture,
            "filename": self.filename, "path": self.path,
            "status": self.status.name, "size_bytes": self.size_bytes,
            "build_time": self.build_time,
        }


@dataclass
class RPMSource:
    """An RPM source file."""
    name: str
    path: str
    filename: str = ""
    size_bytes: int = 0
    md5: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "path": self.path,
            "filename": self.filename, "size_bytes": self.size_bytes,
            "md5": self.md5,
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_rpm_manager: Optional["RPMManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class RPMManager:
    """Manages /usr/src/RPM - RPM build structure."""

    def __init__(self) -> None:
        self._specs: Dict[str, RPMSpec] = {}
        self._packages: Dict[str, RPMPackage] = {}
        self._sources: Dict[str, RPMSource] = {}
        self._build_dirs: Dict[str, str] = dict(RPM_DIRECTORIES)

    def get_spec(self, name: str) -> Optional[RPMSpec]:
        return self._specs.get(name)

    def list_specs(self) -> List[RPMSpec]:
        return sorted(self._specs.values(), key=lambda s: s.name)

    def register_spec(self, spec: RPMSpec) -> None:
        self._specs[spec.name] = spec

    def get_package(self, name: str) -> Optional[RPMPackage]:
        return self._packages.get(name)

    def list_packages(self, arch: Optional[str] = None) -> List[RPMPackage]:
        packages = list(self._packages.values())
        if arch is not None:
            packages = [p for p in packages if p.architecture == arch]
        return sorted(packages, key=lambda p: p.name)

    def register_package(self, package: RPMPackage) -> None:
        self._packages[package.name] = package

    def get_source(self, name: str) -> Optional[RPMSource]:
        return self._sources.get(name)

    def list_sources(self) -> List[RPMSource]:
        return sorted(self._sources.values(), key=lambda s: s.name)

    def register_source(self, source: RPMSource) -> None:
        self._sources[source.name] = source

    def get_build_dir(self, name: str) -> Optional[str]:
        return self._build_dirs.get(name)

    def list_architectures(self) -> List[str]:
        archs = set()
        for p in self._packages.values():
            archs.add(p.architecture)
        return sorted(archs)

    def get_statistics(self) -> Dict[str, Any]:
        by_arch: Dict[str, int] = {}
        for p in self._packages.values():
            a = p.architecture
            by_arch[a] = by_arch.get(a, 0) + 1
        return {
            "total_specs": len(self._specs),
            "total_packages": len(self._packages),
            "total_sources": len(self._sources),
            "by_architecture": by_arch,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "specs": {k: v.to_dict() for k, v in self._specs.items()},
            "packages": {k: v.to_dict() for k, v in self._packages.items()},
            "sources": {k: v.to_dict() for k, v in self._sources.items()},
            "build_dirs": self._build_dirs,
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_rpm_manager() -> RPMManager:
    global _global_rpm_manager
    if _global_rpm_manager is None:
        _global_rpm_manager = RPMManager()
    return _global_rpm_manager


def initialize() -> RPMManager:
    return get_global_rpm_manager()


def refresh() -> RPMManager:
    global _global_rpm_manager
    _global_rpm_manager = RPMManager()
    return _global_rpm_manager
