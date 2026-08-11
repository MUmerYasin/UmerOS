"""
UmerOS /lib Shared Library Management
=======================================
Manages shared libraries in /lib.

FHS 3.0:
  /lib          — Essential shared libraries
  /lib/modules  — Loadable kernel modules

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import fnmatch
import logging
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Lib.LibraryManager")


@dataclass
class LibraryInfo:
    """Represents a shared library."""
    name: str
    path: str
    version: str = ""
    size: int = 0
    md5: str = ""
    symlink_to: Optional[str] = None
    is_symlink: bool = False


class LibraryManager:
    """
    Manages shared libraries in /lib.

    Handles library lookup, version management, and symlink maintenance.
    """

    def __init__(self, lib_path: str = "/lib"):
        self.lib_path = Path(lib_path)

    def list_libraries(self, recursive: bool = False) -> List[LibraryInfo]:
        """List all shared libraries in /lib."""
        libraries = []
        pattern = "**/*" if recursive else "*"
        for item in self.lib_path.glob(pattern):
            if item.is_file():
                lib = LibraryInfo(
                    name=item.name,
                    path=str(item),
                    size=item.stat().st_size,
                    md5=self._compute_md5(item),
                    is_symlink=item.is_symlink(),
                    symlink_to=str(item.readlink()) if item.is_symlink() else None,
                )
                libraries.append(lib)
        return libraries

    def find_library(self, name: str) -> Optional[LibraryInfo]:
        """Find a library by name."""
        for lib in self.list_libraries(recursive=True):
            if lib.name == name or lib.name.startswith(name + "."):
                return lib
        return None

    def find_library_by_pattern(self, pattern: str) -> List[LibraryInfo]:
        """Find libraries matching a pattern (e.g., 'lib*.so')."""
        results = []
        for lib in self.list_libraries(recursive=True):
            if fnmatch.fnmatchcase(lib.name, pattern):
                results.append(lib)
        return results

    def get_library_version(self, name: str) -> str:
        """Extract version from library filename (e.g., libfoo.so.1.2.3 → 1.2.3)."""
        lib = self.find_library(name)
        if lib and lib.name:
            parts = lib.name.split(".")
            if len(parts) >= 2:
                # Find version-like part
                for part in parts:
                    if any(c.isdigit() for c in part):
                        return part
        return ""

    def create_symlink(self, target: str, link_name: str) -> bool:
        """Create a symlink for a library."""
        target_path = self.lib_path / target
        link_path = self.lib_path / link_name
        try:
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            link_path.symlink_to(target)
            log.info("Created symlink: %s -> %s", link_name, target)
            return True
        except Exception as e:
            log.error("Failed to create symlink: %s", e)
            return False

    def remove_library(self, name: str) -> bool:
        """Remove a library file."""
        lib = self.find_library(name)
        if lib is None:
            return False
        try:
            path = Path(lib.path)
            path.unlink()
            log.info("Removed library: %s", name)
            return True
        except Exception as e:
            log.error("Failed to remove library: %s", e)
            return False

    def get_total_size(self) -> int:
        """Get total size of all libraries in /lib."""
        total = 0
        for lib in self.list_libraries(recursive=True):
            total += lib.size
        return total

    def _compute_md5(self, path: Path) -> str:
        """Compute MD5 hash of a file."""
        try:
            h = hashlib.md5()
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def get_summary(self) -> Dict:
        """Get summary of /lib contents."""
        libs = self.list_libraries()
        return {
            "total_libraries": len(libs),
            "total_size_bytes": self.get_total_size(),
            "symlinks": sum(1 for lib in libs if lib.is_symlink),
            "regular_files": sum(1 for lib in libs if not lib.is_symlink),
        }
