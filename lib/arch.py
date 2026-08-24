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
UmerOS /lib/<machine-architecture> — Architecture-Specific Library Manager
===========================================================================
Implements the FHS subdirectory ``/lib/<machine-architecture>`` which
holds architecture-dependent libraries.  Modern distros use
multi-arch paths such as::

    /lib/i386-linux-gnu/
    /lib/x86_64-linux-gnu/
    /lib/aarch64-linux-gnu/
    /lib/arm-linux-gnueabihf/
    /lib/powerpc64le-linux-gnu/
    /lib/riscv64-linux-gnu/
    /lib/loongarch64-linux-gnu/
    /lib/s390x-linux-gnu/
    /lib/mips64el-linux-gnuabi64/

Per FHS, only architecture-DEPENDENT libraries belong here;
architecture-independent libraries stay directly in /lib (or /usr/lib).

The host's machine architecture is available via the standard triplet
``$(uname -m)``-``$(gcc -dumpmachine)``.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import logging
import platform
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

log = logging.getLogger("UmerOS.Lib.Arch")


# ─────────────────────────────────────────────────────────────────────────────
#  Known multi-arch triplets
# ─────────────────────────────────────────────────────────────────────────────

# The ``linux-gnu`` ABI suffix is the common case.  For each base architecture
# we record:  - the canonical triplet
#              - the legacy 32/64-bit names
#              - the uname -m name
#              - a few user-friendly aliases
ARCHITECTURES: Dict[str, Dict[str, str]] = {
    "x86_64": {
        "triplet":   "x86_64-linux-gnu",
        "legacy":    ["x86_64", "x86-64", "amd64"],
        "uname_m":   "x86_64",
        "bits":      "64",
        "endian":    "little",
        "description": "Intel/AMD 64-bit",
    },
    "i386": {
        "triplet":   "i386-linux-gnu",
        "legacy":    ["i386", "i486", "i686"],
        "uname_m":   "i686",
        "bits":      "32",
        "endian":    "little",
        "description": "Intel 32-bit",
    },
    "aarch64": {
        "triplet":   "aarch64-linux-gnu",
        "legacy":    ["aarch64", "arm64"],
        "uname_m":   "aarch64",
        "bits":      "64",
        "endian":    "little",
        "description": "ARM 64-bit (AArch64)",
    },
    "arm": {
        "triplet":   "arm-linux-gnueabihf",
        "legacy":    ["arm", "armhf", "armv7l", "armv7hl"],
        "uname_m":   "armv7l",
        "bits":      "32",
        "endian":    "little",
        "description": "ARM 32-bit hard-float",
    },
    "armel": {
        "triplet":   "arm-linux-gnueabi",
        "legacy":    ["armel"],
        "uname_m":   "armv4tl",
        "bits":      "32",
        "endian":    "little",
        "description": "ARM 32-bit soft-float",
    },
    "powerpc": {
        "triplet":   "powerpc-linux-gnu",
        "legacy":    ["powerpc", "ppc"],
        "uname_m":   "ppc",
        "bits":      "32",
        "endian":    "big",
        "description": "PowerPC 32-bit big-endian",
    },
    "powerpc64": {
        "triplet":   "powerpc64-linux-gnu",
        "legacy":    ["powerpc64", "ppc64"],
        "uname_m":   "ppc64",
        "bits":      "64",
        "endian":    "big",
        "description": "PowerPC 64-bit big-endian",
    },
    "powerpc64le": {
        "triplet":   "powerpc64le-linux-gnu",
        "legacy":    ["powerpc64le", "ppc64le"],
        "uname_m":   "ppc64le",
        "bits":      "64",
        "endian":    "little",
        "description": "PowerPC 64-bit little-endian",
    },
    "s390x": {
        "triplet":   "s390x-linux-gnu",
        "legacy":    ["s390x"],
        "uname_m":   "s390x",
        "bits":      "64",
        "endian":    "big",
        "description": "IBM Z (s390x)",
    },
    "riscv64": {
        "triplet":   "riscv64-linux-gnu",
        "legacy":    ["riscv64"],
        "uname_m":   "riscv64",
        "bits":      "64",
        "endian":    "little",
        "description": "RISC-V 64-bit",
    },
    "riscv32": {
        "triplet":   "riscv32-linux-gnu",
        "legacy":    ["riscv32"],
        "uname_m":   "riscv32",
        "bits":      "32",
        "endian":    "little",
        "description": "RISC-V 32-bit",
    },
    "mips": {
        "triplet":   "mips-linux-gnu",
        "legacy":    ["mips"],
        "uname_m":   "mips",
        "bits":      "32",
        "endian":    "big",
        "description": "MIPS 32-bit big-endian",
    },
    "mipsel": {
        "triplet":   "mipsel-linux-gnu",
        "legacy":    ["mipsel"],
        "uname_m":   "mipsel",
        "bits":      "32",
        "endian":    "little",
        "description": "MIPS 32-bit little-endian",
    },
    "mips64": {
        "triplet":   "mips64-linux-gnuabi64",
        "legacy":    ["mips64"],
        "uname_m":   "mips64",
        "bits":      "64",
        "endian":    "big",
        "description": "MIPS 64-bit big-endian",
    },
    "mips64el": {
        "triplet":   "mips64el-linux-gnuabi64",
        "legacy":    ["mips64el"],
        "uname_m":   "mips64el",
        "bits":      "64",
        "endian":    "little",
        "description": "MIPS 64-bit little-endian",
    },
    "loongarch64": {
        "triplet":   "loongarch64-linux-gnu",
        "legacy":    ["loongarch64", "loong64"],
        "uname_m":   "loongarch64",
        "bits":      "64",
        "endian":    "little",
        "description": "LoongArch 64-bit",
    },
    "sparc": {
        "triplet":   "sparc-linux-gnu",
        "legacy":    ["sparc"],
        "uname_m":   "sparc",
        "bits":      "32",
        "endian":    "big",
        "description": "SPARC 32-bit",
    },
    "sparc64": {
        "triplet":   "sparc64-linux-gnu",
        "legacy":    ["sparc64"],
        "uname_m":   "sparc64",
        "bits":      "64",
        "endian":    "big",
        "description": "SPARC 64-bit",
    },
    "alpha": {
        "triplet":   "alpha-linux-gnu",
        "legacy":    ["alpha"],
        "uname_m":   "alpha",
        "bits":      "64",
        "endian":    "little",
        "description": "DEC Alpha",
    },
    "hppa": {
        "triplet":   "hppa-linux-gnu",
        "legacy":    ["hppa", "parisc"],
        "uname_m":   "parisc",
        "bits":      "32",
        "endian":    "big",
        "description": "HP PA-RISC",
    },
    "ia64": {
        "triplet":   "ia64-linux-gnu",
        "legacy":    ["ia64", "itanium"],
        "uname_m":   "ia64",
        "bits":      "64",
        "endian":    "little",
        "description": "Intel Itanium (IA-64)",
    },
    "sh4": {
        "triplet":   "sh4-linux-gnu",
        "legacy":    ["sh4", "sh"],
        "uname_m":   "sh4",
        "bits":      "32",
        "endian":    "little",
        "description": "SuperH 32-bit",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ArchDir:
    """An /lib/<triplet> directory and its library set."""
    triplet: str
    path: str
    base_arch: str
    description: str
    bits: int
    endian: str
    libraries: List[str] = field(default_factory=list)
    is_native: bool = False
    is_system: bool = True

    def has_library(self, name: str) -> bool:
        return any(name in lib for lib in self.libraries)


# ─────────────────────────────────────────────────────────────────────────────
#  Manager
# ─────────────────────────────────────────────────────────────────────────────

class ArchLibraryManager:
    """
    Manages ``/lib/<machine-architecture>`` directories and the libraries
    each one contains.
    """

    def __init__(self, lib_path: str = "/lib") -> None:
        self.lib_path = Path(lib_path)
        self._arches: Dict[str, ArchDir] = {}
        for arch_key, info in ARCHITECTURES.items():
            triplet = info["triplet"]
            self._arches[triplet] = ArchDir(
                triplet=triplet,
                path=f"/lib/{triplet}",
                base_arch=arch_key,
                description=info["description"],
                bits=int(info["bits"]),
                endian=info["endian"],
                libraries=[],
            )
        # Mark the native arch
        native_triplet = self.detect_native()
        if native_triplet in self._arches:
            self._arches[native_triplet].is_native = True

    # ── detection ────────────────────────────────────────────────

    @staticmethod
    def detect_native() -> str:
        """
        Return the multi-arch triplet for the *current* machine.
        Defaults to ``x86_64-linux-gnu`` if the host platform is not in
        our recognised list.
        """
        machine = platform.machine().lower()
        for arch_key, info in ARCHITECTURES.items():
            if info["uname_m"].lower() == machine or machine in info["legacy"]:
                return info["triplet"]
        return "x86_64-linux-gnu"

    @staticmethod
    def uname() -> Dict[str, str]:
        """Mimic ``uname -a`` output for UmerOS."""
        return {
            "sysname":  platform.system() or "UmerOS",
            "nodename": platform.node() or "UmerOS",
            "release":  platform.release() or "6.6.0-UmerOS",
            "version":  platform.version() or "UmerOS #1 SMP",
            "machine":  platform.machine() or "x86_64",
            "triplet":  ArchLibraryManager.detect_native(),
        }

    # ── queries ───────────────────────────────────────────────────

    def list_architectures(self) -> List[ArchDir]:
        return list(self._arches.values())

    def list_triplets(self) -> List[str]:
        return list(self._arches.keys())

    def get_architecture(self, triplet: str) -> Optional[ArchDir]:
        return self._arches.get(triplet)

    def native_architecture(self) -> ArchDir:
        for arch in self._arches.values():
            if arch.is_native:
                return arch
        return self._arches[self.detect_native()]

    def is_compatible(self, triplet: str) -> bool:
        """Can a binary built for ``triplet`` run on the native arch?"""
        if triplet not in self._arches:
            return False
        a = self._arches[triplet]
        b = self.native_architecture()
        # Same arch + same endianness = compatible
        if a.base_arch == b.base_arch:
            return True
        # AArch64 can run AArch32
        if b.base_arch == "aarch64" and a.base_arch in ("arm", "armel"):
            return True
        # x86_64 can run i386
        if b.base_arch == "x86_64" and a.base_arch == "i386":
            return True
        return False

    # ── library management ───────────────────────────────────────

    def add_library(self, triplet: str, library_path: str) -> bool:
        arch = self._arches.get(triplet)
        if arch is None:
            return False
        arch.libraries.append(library_path)
        return True

    def get_libraries(self, triplet: str) -> List[str]:
        arch = self._arches.get(triplet)
        return list(arch.libraries) if arch else []

    def find_library(self, name: str) -> Dict[str, List[str]]:
        """Return ``{triplet: [paths]}`` for every triplet that has ``name``."""
        out: Dict[str, List[str]] = {}
        for arch in self._arches.values():
            matches = [l for l in arch.libraries if name in l]
            if matches:
                out[arch.triplet] = matches
        return out

    def register_triplet(
        self,
        triplet: str,
        base_arch: str,
        *,
        bits: int = 64,
        endian: str = "little",
        description: str = "",
    ) -> ArchDir:
        """Add a new architecture that wasn't in the default table."""
        if triplet in self._arches:
            return self._arches[triplet]
        arch = ArchDir(
            triplet=triplet,
            path=f"/lib/{triplet}",
            base_arch=base_arch,
            description=description or f"Custom arch {base_arch}",
            bits=bits,
            endian=endian,
            is_system=False,
        )
        self._arches[triplet] = arch
        return arch

    # ── summary ──────────────────────────────────────────────────

    def get_summary(self) -> Dict:
        arches = list(self._arches.values())
        return {
            "native_triplet": self.detect_native(),
            "total_architectures": len(arches),
            "system_architectures": sum(1 for a in arches if a.is_system),
            "libraries_total": sum(len(a.libraries) for a in arches),
            "by_endian": {
                "little": sum(1 for a in arches if a.endian == "little"),
                "big":    sum(1 for a in arches if a.endian == "big"),
            },
            "by_bits": {
                "32": sum(1 for a in arches if a.bits == 32),
                "64": sum(1 for a in arches if a.bits == 64),
            },
        }


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ArchLibraryManager(lib_path=tmpdir)
        summary = mgr.get_summary()
        assert "total_architectures" in summary, "summary should have total_architectures"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
