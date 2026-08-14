"""
UmerOS GCC Support Manager (/usr/lib/gcc)
==========================================
GCC (GNU Compiler Collection) support files and libraries.

  Filesystem Hierarchy - /usr/lib/gcc
  /usr/lib/gcc contains GCC support files including compiler
  libraries, specifications, and executables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Constants ───────────────────────────────────────────────────────────────

GCC_PATH = "/usr/lib/gcc"

GCC_CATEGORIES = {
    "LIBRARY": "Compiler support libraries",
    "SPEC": "Compiler specifications",
    "INCLUDE": "Compiler include files",
    "BINARY": "Compiler executables",
    "OTHER": "Other GCC support files",
}

SUPPORTED_LANGUAGES = [
    "c", "c++", "fortran", "objc", "obj-c++",
    "ada", "go", "d", "lto", "jit",
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class GccLibType(IntEnum):
    """GCC library types."""
    STATIC = 1
    SHARED = 2
    OBJECT = 3


class GccStatus(IntEnum):
    """GCC component status."""
    ACTIVE = 1
    DEPRECATED = 2
    MISSING = 3


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class GccLibrary:
    """A GCC support library."""
    name: str
    path: str
    lib_type: GccLibType = GccLibType.STATIC
    language: str = ""
    size: int = 0
    version: str = ""
    description: str = ""
    status: GccStatus = GccStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "lib_type": self.lib_type.name,
            "language": self.language,
            "size": self.size,
            "version": self.version,
            "description": self.description,
            "status": self.status.name,
        }


@dataclass
class GccSpec:
    """A GCC specification file."""
    name: str
    path: str
    language: str = ""
    description: str = ""
    status: GccStatus = GccStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "language": self.language,
            "description": self.description,
            "status": self.status.name,
        }


@dataclass
class GccInstallation:
    """A GCC installation directory."""
    name: str
    path: str
    version: str = ""
    target: str = ""
    languages: List[str] = field(default_factory=list)
    libraries: List[GccLibrary] = field(default_factory=list)
    specs: List[GccSpec] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "version": self.version,
            "target": self.target,
            "languages": self.languages,
            "libraries_count": len(self.libraries),
            "specs_count": len(self.specs),
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_gcc_manager: Optional["GccManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class GccManager:
    """Manages /usr/lib/gcc - GCC support files."""

    def __init__(self) -> None:
        self._installations: Dict[str, GccInstallation] = {}
        self._libraries: Dict[str, GccLibrary] = {}
        self._specs: Dict[str, GccSpec] = {}
        self._initialize_default_installations()

    def _initialize_default_installations(self) -> None:
        """Initialize with common GCC installations."""
        default_installations = [
            ("gcc-13", "/usr/lib/gcc/x86_64-linux-gnu/13", "13.3.0", "x86_64-linux-gnu",
             ["c", "c++", "fortran", "objc"]),
            ("gcc-12", "/usr/lib/gcc/x86_64-linux-gnu/12", "12.4.0", "x86_64-linux-gnu",
             ["c", "c++", "fortran", "objc"]),
            ("gcc-11", "/usr/lib/gcc/x86_64-linux-gnu/11", "11.5.0", "x86_64-linux-gnu",
             ["c", "c++", "fortran", "objc"]),
        ]
        for name, path, version, target, langs in default_installations:
            installation = GccInstallation(
                name=name, path=path, version=version,
                target=target, languages=langs,
            )
            self._installations[name] = installation
            # Add default libraries
            for lang in ["c", "c++"]:
                lib_name = f"lib{lang}.a"
                lib = GccLibrary(
                    name=lib_name,
                    path=f"{path}/{lib_name}",
                    language=lang,
                    description=f"GCC {lang} support library",
                )
                self._libraries[f"{name}:{lib_name}"] = lib
                installation.libraries.append(lib)

    def get_installation(self, name: str) -> Optional[GccInstallation]:
        """Get a GCC installation by name."""
        return self._installations.get(name)

    def list_installations(self) -> List[GccInstallation]:
        """List all GCC installations."""
        return sorted(self._installations.values(), key=lambda i: i.name)

    def get_library(self, key: str) -> Optional[GccLibrary]:
        """Get a library by key (installation:library)."""
        return self._libraries.get(key)

    def list_libraries(self, language: Optional[str] = None) -> List[GccLibrary]:
        """List all libraries, optionally filtered by language."""
        libs = list(self._libraries.values())
        if language is not None:
            libs = [l for l in libs if l.language == language]
        return sorted(libs, key=lambda l: l.name)

    def get_spec(self, name: str) -> Optional[GccSpec]:
        """Get a spec by name."""
        return self._specs.get(name)

    def list_specs(self) -> List[GccSpec]:
        """List all specs."""
        return sorted(self._specs.values(), key=lambda s: s.name)

    def register_installation(self, installation: GccInstallation) -> None:
        """Register a GCC installation."""
        self._installations[installation.name] = installation

    def get_statistics(self) -> Dict[str, Any]:
        """Get GCC statistics."""
        by_language: Dict[str, int] = {}
        for lib in self._libraries.values():
            lang = lib.language or "unknown"
            by_language[lang] = by_language.get(lang, 0) + 1
        return {
            "total_installations": len(self._installations),
            "total_libraries": len(self._libraries),
            "total_specs": len(self._specs),
            "by_language": by_language,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "installations": {k: v.to_dict() for k, v in self._installations.items()},
            "libraries": {k: v.to_dict() for k, v in self._libraries.items()},
            "specs": {k: v.to_dict() for k, v in self._specs.items()},
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_gcc_manager() -> GccManager:
    """Get or create the global GccManager instance."""
    global _global_gcc_manager
    if _global_gcc_manager is None:
        _global_gcc_manager = GccManager()
    return _global_gcc_manager


def initialize() -> GccManager:
    """Initialize and return the global GccManager."""
    return get_global_gcc_manager()


def refresh() -> GccManager:
    """Refresh the global GccManager."""
    global _global_gcc_manager
    _global_gcc_manager = GccManager()
    return _global_gcc_manager
