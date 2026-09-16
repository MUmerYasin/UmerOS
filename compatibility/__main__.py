"""
Umer OS /compatibility/__main__ — CLI dispatcher
================================================

Runs the most useful operations from the command line::

    python -m compatibility selftest
    python -m compatibility info
    python -m compatibility audit <path/to/something.exe>
    python -m compatibility run  <path/to/something.exe>

Sub-commands
------------

``selftest``
    Run every ``_selftest()`` exposed by sub-modules.  Exit code 0 on
    success, 1 on failure.

``info``
    Print the package version, the number of modules, and the size
    of the public API surface.

``audit <path>``
    Read ``path`` as a PE/NE/MZ file and print a summary: format,
    machine, entry point, imports, missing imports.  This is the
    pure-Python equivalent of ``wine ldd`` / ``objdump -p``.

``run <path>``
    Launch the file using :class:`wine_shim.WineShim`.  Only the
    *audit* step is actually executed; the loader cannot run native
    x86 code on a non-x86 host.  Exit code 0 when the audit succeeds,
    1 otherwise.

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import info as _info, selftest as _selftest
from .wine_shim import WineShim


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m compatibility",
        description="UmerOS Windows compatibility layer — CLI",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selftest", help="run every module's _selftest()")
    sub.add_parser("info", help="print package metadata")

    audit = sub.add_parser("audit",
                           help="audit a PE/NE/MZ file (no execution)")
    audit.add_argument("path", help="path to a Windows executable")

    run = sub.add_parser("run",
                         help="launch a Windows executable via wine_shim")
    run.add_argument("path", help="path to a Windows executable")
    run.add_argument("--dry-run", action="store_true",
                     help="audit only; do not invoke the loader")

    return p


def _audit(path: str) -> int:
    if not os.path.isfile(path):
        print(f"audit: file not found: {path}", file=sys.stderr)
        return 1
    shim = WineShim()
    result = shim.launch(path)
    summary = {
        "path": path,
        "machine": hex(result.pe.machine),
        "entry_rva": hex(result.pe.entry_point_rva),
        "subsystem": result.pe.subsystem_name,
        "image_base": hex(result.pe.image_base),
        "n_imports": len(result.loaded.imports),
        "n_resolved": len(result.loaded.resolved_imports),
        "missing": [f"{m.dll_name}!{m.symbol}"
                    for m in result.loaded.missing_imports()],
        "is_loadable": result.is_loadable,
    }
    print(json.dumps(summary, indent=2))
    return 0 if result.is_loadable else 1


def _run(path: str, dry_run: bool) -> int:
    if dry_run:
        return _audit(path)
    shim = WineShim()
    r = shim.launch(path)
    if not r.is_loadable:
        print("run: image is not loadable on this host", file=sys.stderr)
        return 1
    print(f"run: audited {path} successfully", file=sys.stderr)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "selftest":
        return 0 if _selftest() else 1
    if args.cmd == "info":
        print(json.dumps(_info(), indent=2))
        return 0
    if args.cmd == "audit":
        return _audit(args.path)
    if args.cmd == "run":
        return _run(args.path, args.dry_run)
    return 2    # unreachable


if __name__ == "__main__":
    sys.exit(main())
