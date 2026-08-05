"""
UmerOS 64-bit Libraries Manager (/usr/lib64)
=============================================
64-bit shared libraries and symlinks.

Reference: Linux Filesystem Hierarchy - /usr/lib64
  /usr/lib64 contains 64-bit shared libraries and symlinks.
  On 64-bit systems, this directory is often a symlink to /usr/lib.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Constants ───────────────────────────────────────────────────────────────

LIB64_PATH = "/usr/lib64"

LIB64_CATEGORIES = {
    "SHARED": "Shared libraries (.so)",
    "STATIC": "Static libraries (.a)",
    "DEVEL": "Development libraries",
    "LOCALE": "Locale-specific libraries",
    "PYTHON": "Python module libraries",
    "PYTHON3": "Python 3 module libraries",
}


# ─── Enums ───────────────────────────────────────────────────────────────────

class Lib64Type(IntEnum):
    """64-bit library types."""
    SHARED = 1
    STATIC = 2
    OBJECT = 3
    LINK = 4
    UNKNOWN = 99


class Lib64Status(IntEnum):
    """Library status."""
    ACTIVE = 1
    DEPRECATED = 2
    MISSING = 3
    BROKEN = 4


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class Lib64Entry:
    """Represents a 64-bit library entry."""
    name: str
    path: str
    lib_type: Lib64Type = Lib64Type.SHARED
    version: str = ""
    size: int = 0
    target: str = ""
    description: str = ""
    status: Lib64Status = Lib64Status.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "lib_type": self.lib_type.name,
            "version": self.version,
            "size": self.size,
            "target": self.target,
            "description": self.description,
            "status": self.status.name,
        }


@dataclass
class Lib64Directory:
    """A subdirectory in /usr/lib64."""
    name: str
    path: str
    description: str = ""
    entries: List[Lib64Entry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "entries_count": len(self.entries),
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_lib64_manager: Optional["Lib64Manager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class Lib64Manager:
    """Manages /usr/lib64 - 64-bit shared libraries."""

    def __init__(self) -> None:
        self._entries: Dict[str, Lib64Entry] = {}
        self._directories: Dict[str, Lib64Directory] = {}
        self._symlink_to_lib: bool = False
        self._initialize_default_entries()

    def _initialize_default_entries(self) -> None:
        """Initialize with common 64-bit libraries."""
        default_entries = [
            ("libc.so.6", "/usr/lib64/libc.so.6", Lib64Type.SHARED, "2.35", "C library"),
            ("libm.so.6", "/usr/lib64/libm.so.6", Lib64Type.SHARED, "2.35", "Math library"),
            ("libpthread.so.0", "/usr/lib64/libpthread.so.0", Lib64Type.SHARED, "2.35", "POSIX threads"),
            ("libdl.so.2", "/usr/lib64/libdl.so.2", Lib64Type.SHARED, "2.35", "Dynamic linker"),
            ("libstdc++.so.6", "/usr/lib64/libstdc++.so.6", Lib64Type.SHARED, "13.2.0", "C++ standard library"),
            ("libgcc_s.so.1", "/usr/lib64/libgcc_s.so.1", Lib64Type.SHARED, "13.2.0", "GCC support library"),
            ("libssl.so.3", "/usr/lib64/libssl.so.3", Lib64Type.SHARED, "3.0.12", "OpenSSL SSL library"),
            ("libcrypto.so.3", "/usr/lib64/libcrypto.so.3", Lib64Type.SHARED, "3.0.12", "OpenSSL crypto library"),
            ("libz.so.1", "/usr/lib64/libz.so.1", Lib64Type.SHARED, "1.2.13", "zlib compression"),
            ("libxml2.so.2", "/usr/lib64/libxml2.so.2", Lib64Type.SHARED, "2.9.14", "XML parser library"),
            ("libglib-2.0.so.0", "/usr/lib64/libglib-2.0.so.0", Lib64Type.SHARED, "2.78.3", "GLib library"),
            ("libgobject-2.0.so.0", "/usr/lib64/libgobject-2.0.so.0", Lib64Type.SHARED, "2.78.3", "GLib object system"),
            ("libgio-2.0.so.0", "/usr/lib64/libgio-2.0.so.0", Lib64Type.SHARED, "2.78.3", "GLib I/O library"),
            ("libpango-1.0.so.0", "/usr/lib64/libpango-1.0.so.0", Lib64Type.SHARED, "1.51.2", "Pango text layout"),
            ("libcairo.so.2", "/usr/lib64/libcairo.so.2", Lib64Type.SHARED, "1.18.0", "Cairo graphics"),
            ("libgdk_pixbuf-2.0.so.0", "/usr/lib64/libgdk_pixbuf-2.0.so.0", Lib64Type.SHARED, "2.42.10", "GDK Pixbuf"),
            ("libgtk-3.so.0", "/usr/lib64/libgtk-3.so.0", Lib64Type.SHARED, "3.24.38", "GTK 3 toolkit"),
            ("libX11.so.6", "/usr/lib64/libX11.so.6", Lib64Type.SHARED, "1.8.7", "X11 client library"),
            ("libXext.so.6", "/usr/lib64/libXext.so.6", Lib64Type.SHARED, "1.3.5", "X11 extensions"),
            ("libXrender.so.1", "/usr/lib64/libXrender.so.1", Lib64Type.SHARED, "0.9.11", "X11 Render"),
            ("libGL.so.1", "/usr/lib64/libGL.so.1", Lib64Type.SHARED, "23.1.9", "OpenGL library"),
            ("libEGL.so.1", "/usr/lib64/libEGL.so.1", Lib64Type.SHARED, "1.5.5", "EGL library"),
            ("libwayland-client.so.0", "/usr/lib64/libwayland-client.so.0", Lib64Type.SHARED, "1.22.0", "Wayland client"),
            ("libffi.so.8", "/usr/lib64/libffi.so.8", Lib64Type.SHARED, "3.4.4", "Foreign function interface"),
            ("libsqlite3.so.0", "/usr/lib64/libsqlite3.so.0", Lib64Type.SHARED, "3.44.0", "SQLite database"),
            ("libuuid.so.1", "/usr/lib64/libuuid.so.1", Lib64Type.SHARED, "2.39.2", "UUID library"),
            ("libbz2.so.1.0", "/usr/lib64/libbz2.so.1.0", Lib64Type.SHARED, "1.0.8", "bzip2 compression"),
            ("liblzma.so.5", "/usr/lib64/liblzma.so.5", Lib64Type.SHARED, "5.4.4", "XZ compression"),
            ("libncursesw.so.6", "/usr/lib64/libncursesw.so.6", Lib64Type.SHARED, "6.4.20230520", "ncurses library"),
            ("libreadline.so.8", "/usr/lib64/libreadline.so.8", Lib64Type.SHARED, "8.2", "GNU Readline"),
        ]
        for name, path, lib_type, version, desc in default_entries:
            entry = Lib64Entry(
                name=name, path=path, lib_type=lib_type,
                version=version, description=desc,
            )
            self._entries[name] = entry

    def get_entry(self, name: str) -> Optional[Lib64Entry]:
        """Get a library entry by name."""
        return self._entries.get(name)

    def list_entries(self, lib_type: Optional[Lib64Type] = None) -> List[Lib64Entry]:
        """List all entries, optionally filtered by type."""
        entries = list(self._entries.values())
        if lib_type is not None:
            entries = [e for e in entries if e.lib_type == lib_type]
        return sorted(entries, key=lambda e: e.name)

    def search_entries(self, query: str) -> List[Lib64Entry]:
        """Search entries by name or description."""
        query_lower = query.lower()
        results = []
        for entry in self._entries.values():
            if (query_lower in entry.name.lower() or
                query_lower in entry.description.lower()):
                results.append(entry)
        return results

    def register_entry(self, entry: Lib64Entry) -> None:
        """Register a new library entry."""
        self._entries[entry.name] = entry

    def get_directory(self, name: str) -> Optional[Lib64Directory]:
        """Get a directory by name."""
        return self._directories.get(name)

    def list_directories(self) -> List[Lib64Directory]:
        """List all directories."""
        return sorted(self._directories.values(), key=lambda d: d.name)

    def set_symlink_to_lib(self, is_symlink: bool) -> None:
        """Set whether /usr/lib64 is a symlink to /usr/lib."""
        self._symlink_to_lib = is_symlink

    def get_statistics(self) -> Dict[str, Any]:
        """Get lib64 statistics."""
        by_type: Dict[str, int] = {}
        for entry in self._entries.values():
            t = entry.lib_type.name
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total_entries": len(self._entries),
            "total_directories": len(self._directories),
            "symlink_to_lib": self._symlink_to_lib,
            "by_type": by_type,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "entries": {k: v.to_dict() for k, v in self._entries.items()},
            "directories": {k: v.to_dict() for k, v in self._directories.items()},
            "symlink_to_lib": self._symlink_to_lib,
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_lib64_manager() -> Lib64Manager:
    """Get or create the global Lib64Manager instance."""
    global _global_lib64_manager
    if _global_lib64_manager is None:
        _global_lib64_manager = Lib64Manager()
    return _global_lib64_manager


def initialize() -> Lib64Manager:
    """Initialize and return the global Lib64Manager."""
    return get_global_lib64_manager()


def refresh() -> Lib64Manager:
    """Refresh the global Lib64Manager."""
    global _global_lib64_manager
    _global_lib64_manager = Lib64Manager()
    return _global_lib64_manager
