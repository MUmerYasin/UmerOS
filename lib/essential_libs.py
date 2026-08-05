"""
UmerOS Essential Shared Library Stubs
======================================
Provides stub representations for essential shared libraries required by FHS 3.0.

According to TLDP/FHS:
  /lib must contain:
    - libc.so.*  — The C library (most important shared library)
    - ld*        — The dynamic linker/loader

Additional may-exist libraries:
    - libm.so.*        — Math library
    - libpthread.so.*  — POSIX threads library
    - libdl.so.*       — Dynamic loading library
    - librt.so.*       — Realtime extensions library

These stubs simulate the presence of these libraries for the UmerOS
virtual filesystem without requiring actual binary files.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SharedLibrary:
    """Represents an essential shared library stub."""
    name: str
    path: str
    version: str
    description: str
    size_bytes: int
    symlink_target: Optional[str] = None


# ─── Essential Library Definitions ──────────────────────────────────────────

ESSENTIAL_LIBRARIES: List[SharedLibrary] = [
    # The C Library — most important shared library
    SharedLibrary(
        name="libc.so.6",
        path="/lib/libc.so.6",
        version="2.31",
        description="GNU C Library (glibc) — provides fundamental C library functions",
        size_bytes=2_032_920,
        symlink_target="libc-2.31.so",
    ),
    SharedLibrary(
        name="libc-2.31.so",
        path="/lib/libc-2.31.so",
        version="2.31",
        description="GNU C Library (glibc) — main library file",
        size_bytes=2_032_920,
    ),

    # The dynamic linker/loader
    SharedLibrary(
        name="ld-linux.so.2",
        path="/lib/ld-linux.so.2",
        version="2.31",
        description="The Linux dynamic linker/loader for x86 (32-bit)",
        size_bytes=186_896,
        symlink_target="ld-2.31.so",
    ),
    SharedLibrary(
        name="ld-linux-x86-64.so.2",
        path="/lib/ld-linux-x86-64.so.2",
        version="2.31",
        description="The Linux dynamic linker/loader for x86-64 (64-bit)",
        size_bytes=202_952,
        symlink_target="ld-2.31.so",
    ),
    SharedLibrary(
        name="ld-2.31.so",
        path="/lib/ld-2.31.so",
        version="2.31",
        description="The Linux dynamic linker/loader (main file)",
        size_bytes=202_952,
    ),

    # Math library
    SharedLibrary(
        name="libm.so.6",
        path="/lib/libm.so.6",
        version="2.31",
        description="GNU C Library — math library functions",
        size_bytes=1_381_528,
        symlink_target="libm-2.31.so",
    ),
    SharedLibrary(
        name="libm-2.31.so",
        path="/lib/libm-2.31.so",
        version="2.31",
        description="GNU C Library — math library (main file)",
        size_bytes=1_381_528,
    ),

    # POSIX threads library
    SharedLibrary(
        name="libpthread.so.0",
        path="/lib/libpthread.so.0",
        version="2.31",
        description="POSIX threads library",
        size_bytes=158_216,
        symlink_target="libpthread-2.31.so",
    ),
    SharedLibrary(
        name="libpthread-2.31.so",
        path="/lib/libpthread-2.31.so",
        version="2.31",
        description="POSIX threads library (main file)",
        size_bytes=158_216,
    ),

    # Dynamic loading library
    SharedLibrary(
        name="libdl.so.2",
        path="/lib/libdl.so.2",
        version="2.31",
        description="Dynamic linking interface library",
        size_bytes=18_672,
        symlink_target="libdl-2.31.so",
    ),
    SharedLibrary(
        name="libdl-2.31.so",
        path="/lib/libdl-2.31.so",
        version="2.31",
        description="Dynamic linking interface library (main file)",
        size_bytes=18_672,
    ),

    # Realtime extensions library
    SharedLibrary(
        name="librt.so.1",
        path="/lib/librt.so.1",
        version="2.31",
        description="Realtime extensions library",
        size_bytes=35_304,
        symlink_target="librt-2.31.so",
    ),
    SharedLibrary(
        name="librt-2.31.so",
        path="/lib/librt-2.31.so",
        version="2.31",
        description="Realtime extensions library (main file)",
        size_bytes=35_304,
    ),

    # NSS (Name Service Switch) library
    SharedLibrary(
        name="libnss_files.so.2",
        path="/lib/libnss_files.so.2",
        version="2.31",
        description="NSS module for file-based name service lookups",
        size_bytes=56_264,
        symlink_target="libnss_files-2.31.so",
    ),
    SharedLibrary(
        name="libnss_files-2.31.so",
        path="/lib/libnss_files-2.31.so",
        version="2.31",
        description="NSS module for file-based name service lookups (main file)",
        size_bytes=56_264,
    ),

    # Resolv library
    SharedLibrary(
        name="libresolv.so.2",
        path="/lib/libresolv.so.2",
        version="2.31",
        description="DNS resolver library",
        size_bytes=67_928,
        symlink_target="libresolv-2.31.so",
    ),
    SharedLibrary(
        name="libresolv-2.31.so",
        path="/lib/libresolv-2.31.so",
        version="2.31",
        description="DNS resolver library (main file)",
        size_bytes=67_928,
    ),
]


class EssentialLibraryManager:
    """
    Manages essential shared library stubs in /lib.

    Provides a registry of the core libraries required by FHS 3.0
    without requiring actual binary files to exist on disk.
    """

    def __init__(self) -> None:
        self._libraries: Dict[str, SharedLibrary] = {}
        for lib in ESSENTIAL_LIBRARIES:
            self._libraries[lib.name] = lib

    def list_libraries(self) -> List[SharedLibrary]:
        """List all essential libraries."""
        return list(self._libraries.values())

    def find_library(self, name: str) -> Optional[SharedLibrary]:
        """Find a library by name."""
        return self._libraries.get(name)

    def find_by_pattern(self, pattern: str) -> List[SharedLibrary]:
        """Find libraries matching a pattern (e.g., 'libc' or 'ld')."""
        results = []
        for lib in self._libraries.values():
            if pattern in lib.name:
                results.append(lib)
        return results

    def get_symlink_pairs(self) -> List[tuple[str, str]]:
        """Get all (symlink_name, target) pairs."""
        pairs = []
        for lib in self._libraries.values():
            if lib.symlink_target:
                pairs.append((lib.name, lib.symlink_target))
        return pairs

    def get_required_libs(self) -> List[SharedLibrary]:
        """Get only the FHS-required libraries (libc and ld)."""
        return [
            lib for lib in self._libraries.values()
            if lib.name.startswith("libc.so") or lib.name.startswith("ld-")
        ]

    def get_total_size(self) -> int:
        """Get total size of all unique library files."""
        seen = set()
        total = 0
        for lib in self._libraries.values():
            if lib.path not in seen:
                seen.add(lib.path)
                total += lib.size_bytes
        return total

    def get_summary(self) -> Dict[str, int]:
        """Get summary of essential libraries."""
        return {
            "total_entries": len(self._libraries),
            "unique_files": len({lib.path for lib in self._libraries.values()}),
            "symlinks": len([lib for lib in self._libraries.values() if lib.symlink_target]),
            "total_size_bytes": self.get_total_size(),
        }
