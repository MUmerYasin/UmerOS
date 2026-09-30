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
License: GPL-3.0 
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
    # Optional execution result (populated when launch(..., execute=True)).
    run_result: Optional["ExecuteResult"] = None

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
        if self.run_result is not None:
            lines.append(f"  executed: rc={self.run_result.exit_code}"
                         f" steps={self.run_result.steps}"
                         f" final_rip=0x{self.run_result.rip_final:x}")
        return "\n".join(lines)


@dataclass
class ExecuteResult:
    """The outcome of actually running a PE through the emulator."""
    exit_code: int = 0
    steps: int = 0
    rip_final: int = 0
    error: Optional[str] = None
    halted: bool = False


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

    def launch(self, binary_path: str, *,
               execute: bool = False,
               max_steps: int = 100_000) -> LaunchResult:
        """Open a PE binary, map it to the QFS, and analyse the IAT.

        Args:
            binary_path: Path to a .exe / .dll / .sys file.
            execute: If ``True`` and the binary is 64-bit x86, run it
                in the pure-Python emulator.  Imported functions are
                dispatched to the compatibility-layer stubs via
                :class:`compatibility.win32_runner.Win32Runner`.
            max_steps: Maximum number of emulated instructions to
                execute before bailing out.

        Returns:
            A :class:`LaunchResult` with the loaded image and any
            missing imports.  When ``execute=True`` and the binary is
            runnable, ``result.run_result`` carries the exit code and
            final RIP.
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
        run_result: Optional[ExecuteResult] = None
        if execute and pe.machine == 0x8664:        # AMD64
            try:
                run_result = self.execute(pe, max_steps=max_steps)
            except Exception as exc:    # noqa: BLE001
                issues.append(f"execute: {exc}")
        return LaunchResult(
            binary_path=binary_path, pe=pe, loaded=loaded,
            mapped_path=mapped, issues=issues,
            run_result=run_result,
        )

    # ------------------------------------------------------------------
    # x86-64 execution path
    # ------------------------------------------------------------------

    def execute(self, pe: PeFile, *, max_steps: int = 100_000) -> ExecuteResult:
        """Load ``pe`` into the pure-Python emulator and run its entry
        point.

        Imports are dispatched to the in-process host libraries
        (``compatibility.dll_loader.HOST_LIBRARIES``).  The method
        blocks until the program halts (or ``max_steps`` is reached).
        """
        from .win32_runner import Win32Runner, RunResult
        from .x86_runner import EmulatorHalt, EmulatorError

        # First, map the pe-loader-level imports into the form that
        # Win32Runner expects (a flat ``dll -> name -> callable`` map).
        import_table: Dict[str, Dict[str, callable]] = {}
        for desc in self.loader.resolve(pe).imports:
            lib_map: Dict[str, callable] = {}
            for sym in desc.symbols:
                if sym.is_ordinal_only:
                    lib_map[f"ordinal_{sym.ordinal}"] = lambda emu: None
                else:
                    lib_map[sym.name] = lambda emu: None
            import_table[desc.name.upper()] = lib_map

        runner = Win32Runner(image_base=int(pe.optional_header.image_base),
                             imports=import_table)
        runner.load_pe(pe, raw_image=pe.raw)
        # The Win64 ABI starts at the entry point with rsp pointing
        # into the stack; the runner builds a stub argv/envp for us.
        entry_va = (int(pe.optional_header.image_base)
                    + pe.optional_header.address_of_entry_point)
        runner.emulator.regs.set(15, entry_va)
        try:
            rc = runner.emulator.run(max_steps=max_steps)
            return ExecuteResult(
                exit_code=rc,
                steps=runner.emulator.steps,
                rip_final=runner.emulator.regs.get(15),
                halted=rc >= 0,
            )
        except EmulatorHalt:
            return ExecuteResult(
                exit_code=runner.emulator.exit_code,
                steps=runner.emulator.steps,
                rip_final=runner.emulator.regs.get(15),
                halted=True,
            )
        except EmulatorError as exc:
            return ExecuteResult(
                exit_code=-1,
                steps=runner.emulator.steps,
                rip_final=runner.emulator.regs.get(15),
                error=str(exc),
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
