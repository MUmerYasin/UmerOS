"""
Umer OS /compatibility/wine_shim — Pure-Python Windows launcher
=============================================================

The :class:`WineShim` is the high-level entry point that the rest
of the Umer OS uses to launch a Windows application.  It is a
**pure-Python** shim -- no external Wine / CrossOver / Proton
dependency -- and it is designed to:

* **parse** the PE binary to discover the IAT and other structures,
* **resolve** the IAT against the in-process host libraries,
* **load** the binary by mapping it into the Umer OS QFS
  (``/compat/c/...``),
* **invoke** a small "entry point" function on demand (no x86
  emulation, no actual execution of arbitrary x86 code).

The pure-Python design has two consequences:

* Code that depends on real x86 execution is *not* supported --
  callers should be aware of this and design their IAT usage to
  avoid it (e.g. by calling the host-side stub through a thin
  adapter).
* The shim is a great **static-analysis** tool: it tells you which
  imports a binary wants, which are unresolved, and which host
  stub will satisfy each one.

This module is the pure-Python counterpart of
:mod:`compatibility.container_engine.WineShim`, which delegates
to an external Wine binary.  Use this one when you want a
fully-portable, dependency-free analysis.

References
----------

* https://reactos.org/wiki/Development_Overview
* https://reactos.org/wiki/Building_ReactOS

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .pe_loader import PeFile
from .dll_loader import DllLoader, HOST_LIBRARIES, LoadedPe
from .win_path import DosPathMapper
from .winerror import format_win32_error
from .ntstatus import format_ntstatus

log = logging.getLogger("UmerOS.Compat.WineShim")


@dataclass
class LaunchResult:
    """The outcome of a :meth:`WineShim.launch` call."""

    binary_path: str
    pe: PeFile
    loaded: LoadedPe
    mapped_path: str              # the QFS path the binary is staged to
    issues: List[str] = field(default_factory=list)

    @property
    def is_loadable(self) -> bool:
        """``True`` iff every import is resolvable."""
        return not self.loaded.missing_imports()

    def render(self) -> str:
        lines = [
            f"WineShim: {self.binary_path}",
            f"  mapped:  {self.mapped_path}",
            f"  size:    {len(self.pe.raw)} bytes",
            f"  machine: {self.pe.machine_name}",
            f"  entry:   0x{self.pe.entry_point_rva:08X}",
            f"  image:   0x{self.pe.image_base:08X}",
            f"  imports: {len(self.loaded.imports)} DLL(s)",
        ]
        miss = self.loaded.missing_imports()
        if miss:
            lines.append(f"  MISSING: {len(miss)} unresolved import(s)")
            for d, n, o in miss[:20]:
                sym = n if n is not None else f"ord({o})"
                lines.append(f"    - {d}!{sym}")
        if self.issues:
            lines.append("  issues:")
            for it in self.issues:
                lines.append(f"    * {it}")
        return "\n".join(lines)


class WineShim:
    """High-level launcher for Windows binaries (pure-Python)."""

    def __init__(
        self,
        compat_root: Optional[str] = None,
        loader: Optional[DllLoader] = None,
    ) -> None:
        self.path_mapper = DosPathMapper(compat_root=compat_root)
        self.loader = loader or DllLoader()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def launch(self, binary_path: str) -> LaunchResult:
        """Open a PE binary, map it to the QFS, and analyse the IAT.

        Args:
            binary_path: Path to a .exe / .dll / .sys file.

        Returns:
            A :class:`LaunchResult` with the loaded image and any
            missing imports.
        """
        issues: List[str] = []
        try:
            pe = PeFile.from_file(binary_path)
        except (ValueError, FileNotFoundError) as exc:
            issues.append(f"parse error: {exc}")
            return LaunchResult(
                binary_path=binary_path, pe=PeFile.__new__(PeFile),
                loaded=LoadedPe(pe=PeFile.__new__(PeFile), imports=[],
                                exports_obj=None, relocations=None,
                                tls=None, resources=None),
                mapped_path="", issues=issues,
            )
        loaded = self.loader.resolve(pe)
        # Map the binary to the QFS compat tree.
        try:
            mapped = self.path_mapper.to_posix(binary_path)
        except Exception as exc:
            mapped = binary_path
            issues.append(f"path-mapping: {exc}")
        return LaunchResult(
            binary_path=binary_path, pe=pe, loaded=loaded,
            mapped_path=mapped, issues=issues,
        )

    def describe(self, binary_path: str) -> str:
        """Return a one-shot human-readable description of a binary."""
        result = self.launch(binary_path)
        return result.render()

    # ------------------------------------------------------------------
    # Static analysis helpers
    # ------------------------------------------------------------------

    def audit_directory(self, directory: str) -> Dict[str, LaunchResult]:
        """Audit every PE file in ``directory``.  Returns ``{path: result}``."""
        out: Dict[str, LaunchResult] = {}
        for name in sorted(os.listdir(directory)):
            full = os.path.join(directory, name)
            if not os.path.isfile(full):
                continue
            try:
                PeFile.from_file(full)
            except (ValueError, FileNotFoundError):
                continue
            out[full] = self.launch(full)
        return out


def _selftest() -> bool:
    shim = WineShim()
    # We don't have a real binary, so the test just sanity-checks
    # the audit helper on a temp directory containing no PEs.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        results = shim.audit_directory(tmp)
        if results != {}:
            return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
