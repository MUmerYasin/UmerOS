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
UmerOS /lib<qual> — Multi-arch Alternate Library Manager
=========================================================
Implements the FHS-mandated handling of alternate-format library
directories.  Per the FHS, one or more variants of ``/lib`` may exist
on systems supporting more than one binary format:

    /lib     — native format
    /lib32   — 32-bit libraries
    /lib64   — 64-bit libraries
    /libx32  — x32 ABI (64-bit program with 32-bit pointers)
    /libsf   — soft-float variant (rare, ARM)

When present, the content rules mirror ``/lib`` *except* that
``/lib<qual>/cpp`` is *not* required.

In modern Debian/Ubuntu-derived distros, ``/lib`` itself is a symlink to
``/usr/lib`` and the alternates are flat ``/lib32``, ``/lib64`` etc.  In
RHEL, ``/lib64`` is a real directory beside ``/lib``.

This module owns the policy that decides where a binary of a given
triplet should look for its shared libraries.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import logging
import os
import platform
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

log = logging.getLogger("UmerOS.Lib.Multiarch")


class LibQualifier(str, Enum):
    """The recognised FHS /lib<qual> suffixes."""
    NATIVE = ""        # i.e. /lib itself
    LIB32  = "32"
    LIB64  = "64"
    LIBX32 = "x32"
    LIBSF  = "sf"


@dataclass
class LibVariant:
    """One /lib<qual> directory."""
    qualifier: LibQualifier
    path: str                        # e.g. /lib32, /lib64, /lib
    description: str
    bits: int
    is_default: bool = False
    libraries: List[str] = field(default_factory=list)
    is_symlink: bool = False
    symlink_target: Optional[str] = None
    is_required: bool = True
    requires_cpp_symlink: bool = True    # /lib<qual>/cpp rule


_STOCK_VARIANTS: List[LibVariant] = [
    LibVariant(
        LibQualifier.NATIVE, "/lib", "Native-format libraries",
        bits=64, is_default=True, is_required=True, requires_cpp_symlink=True,
    ),
    LibVariant(
        LibQualifier.LIB32, "/lib32", "32-bit libraries",
        bits=32, is_required=False, requires_cpp_symlink=False,
    ),
    LibVariant(
        LibQualifier.LIB64, "/lib64", "64-bit libraries",
        bits=64, is_required=False, requires_cpp_symlink=False,
    ),
    LibVariant(
        LibQualifier.LIBX32, "/libx32", "x32 ABI libraries",
        bits=64, is_required=False, requires_cpp_symlink=False,
    ),
    LibVariant(
        LibQualifier.LIBSF, "/libsf", "Soft-float libraries",
        bits=32, is_required=False, requires_cpp_symlink=False,
    ),
]


class MultiarchManager:
    """
    Manages the ``/lib<qual>`` family of alternate-format directories
    and the policy that picks which one a binary should search.
    """

    def __init__(self, root: str = "/") -> None:
        self.root = Path(root)
        self._variants: Dict[str, LibVariant] = {
            v.qualifier.value: v for v in _STOCK_VARIANTS
        }

    # ── listing ──────────────────────────────────────────────────

    def list_variants(self) -> List[LibVariant]:
        return list(self._variants.values())

    def get_variant(self, qualifier: str) -> Optional[LibVariant]:
        if qualifier == "" or qualifier == "native":
            return self._variants[""]
        return self._variants.get(qualifier)

    def default_variant(self) -> LibVariant:
        for v in self._variants.values():
            if v.is_default:
                return v
        return self._variants[""]

    # ── resolution policy ────────────────────────────────────────

    def candidate_search_dirs(self, binary_bits: int) -> List[str]:
        """
        Return the candidate /lib<qual> directories for a binary of the
        given word size, in the order they should be searched.

        Example: a 32-bit binary on a 64-bit system gets
        ``[/lib32, /lib, /lib64]`` (32-bit preferred, then fallback to
        native, then 64-bit just in case).
        """
        native = self.default_variant()
        if binary_bits == 32:
            order = ["32", "", "64", "x32", "sf"]
        else:
            order = ["64", "", "x32", "32", "sf"]
        return [
            self._variants[q].path for q in order if q in self._variants
        ]

    def resolve_libraries(
        self,
        soname: str,
        binary_bits: int,
    ) -> List[Optional[str]]:
        """
        Look for ``soname`` in each candidate /lib<qual> in turn.
        Returns the path list with None for misses.
        """
        out: List[Optional[str]] = []
        for d in self.candidate_search_dirs(binary_bits):
            found = self._find_soname_in_dir(d, soname)
            out.append(found)
        return out

    @staticmethod
    def _find_soname_in_dir(directory: str, soname: str) -> Optional[str]:
        """Search ``directory`` for a file matching ``soname``."""
        p = Path(directory)
        if not p.exists():
            return None
        target = p / soname
        if target.exists():
            return str(target)
        for hit in p.glob(f"**/{soname}*"):
            return str(hit)
        for hit in p.glob("**/*.so*"):
            if soname in hit.name:
                return str(hit)
        return None

    # ── on-disk materialisation ──────────────────────────────────

    def make_lib_symlink_to_64(self) -> Path:
        """
        Realise the modern Debian/Ubuntu convention:
        ``/lib`` -> ``/usr/lib`` (a symlink).

        Returns the path that was used as the symlink.
        """
        # We model the intent: in our manager, /lib becomes a symlink to /lib64
        # when the user runs a 64-bit-only system.  We don't actually call
        # os.symlink unless the user opts in via ensure_symlink().
        lib_path = self.root / "lib"
        lib64 = self.root / "lib64"
        variant = self._variants[""]
        variant.is_symlink = True
        variant.symlink_target = str(lib64)
        return lib_path

    def ensure_symlink(self, qualifier: str) -> Path:
        """
        Make ``/lib`` a symlink to ``/lib<qual>`` (or the reverse).

        Returns the path of the symlink.
        """
        if qualifier in ("", "native"):
            raise ValueError("Pass a non-native qualifier (e.g. '64' or '32')")
        lib_path = self.root / "lib"
        target = self.root / f"lib{qualifier}"
        if lib_path.exists() and not lib_path.is_symlink():
            raise FileExistsError(
                f"{lib_path} exists and is not a symlink; refusing to overwrite"
            )
        if lib_path.is_symlink():
            lib_path.unlink()
        try:
            lib_path.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as e:
            log.warning("Could not create symlink %s → %s: %s",
                        lib_path, target, e)
        # Update the in-memory model
        self._variants[""].is_symlink = True
        self._variants[""].symlink_target = str(target)
        return lib_path

    # ── registration ─────────────────────────────────────────────

    def register_variant(self, variant: LibVariant) -> None:
        self._variants[variant.qualifier.value] = variant

    # ── summary ──────────────────────────────────────────────────

    def get_summary(self) -> Dict:
        return {
            "variants": [
                {
                    "qualifier": v.qualifier.value or "native",
                    "path": v.path,
                    "bits": v.bits,
                    "is_default": v.is_default,
                    "is_required": v.is_required,
                    "requires_cpp_symlink": v.requires_cpp_symlink,
                    "is_symlink": v.is_symlink,
                    "symlink_target": v.symlink_target,
                    "library_count": len(v.libraries),
                }
                for v in self._variants.values()
            ],
            "total_variants": len(self._variants),
        }


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = MultiarchManager(root=tmpdir)
        variants = mgr.list_variants()
        assert isinstance(variants, list), "variants should be a list"
        summary = mgr.get_summary()
        assert "total_variants" in summary, "summary should have total_variants"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
