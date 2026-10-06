#!/usr/bin/env python3
"""
H14-extension — reachability classifier for the UmerOS tree.

Why this exists
---------------
UmerOS contains two very different kinds of Python:

* **Live runtime** — reachable from ``main.py`` by static import.  This is the
  code a booted UmerOS actually executes (kernel, boot, quantum, security,
  network, ...).
* **Reference corpus** — the FHS userland emulation under ``bin/``, ``sbin/``,
  ``usr/``, ``etc/``, ``dev/``, ``lib/``, ``proc/``, ``var/``, ``srv/``, ``opt/``,
  ``media/``, ``mnt/``, ``root/``, ``home/``, ``tmp/``, ``legal/``, ``sources/``,
  ``backup/`` and friends.  It is a large, largely template-generated body of
  code that is exercised only by its own unit tests; nothing imports it from the
  boot path, so it is documentation and design material rather than a running
  component.

Before this check the two were indistinguishable in the tree: both carried
``[TODAY]`` tier labels, so a reader could reasonably conclude that ``bin/`` was
hooked into the shell.  It is not.

What it does
------------
Parses the static import graph starting at ``main.py`` using ``ast`` (nothing is
imported or executed) and reports which first-party top-level packages are
reachable.  The result is compared against the classification declared in
``docs/reference_corpus.md`` (mirrored in ``LIVE``/``REFERENCE`` below); a
mismatch exits 1 so the documentation cannot silently drift out of date.

Usage::

    python scripts/check_layer_reachability.py            # report + verify
    python scripts/check_layer_reachability.py --list     # machine-readable sets

Author: Umer OS Project  ·  License: GPL-3.0
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Dict, Iterable, Set

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "main.py"

# Directories that are not part of the importable tree.
SKIP_DIRS = {
    ".git", ".github", ".venv", "venv", "node_modules", "__pycache__",
    "build", "dist", ".pytest_cache", ".workbuddy-ai", ".agents", ".claude",
    ".qodo", ".vscode", ".zcode", "Old Linux Code", "liboqs", "Skills",
    "MainTask", "HostFiles", "umer_fs", "UmerOS", "docs", "sources_of_truth",
}

# ── Declared classification (mirrors docs/reference_corpus.md) ──────────────
# Packages the boot path actually reaches.
LIVE: Set[str] = {
    "boot", "core", "kernel", "lib",
}
# Packages that build/runtime tooling reaches, but the boot path does not.
TOOLING: Set[str] = {
    "packages", "scripts", "setup.py",
}
# FHS userland emulation + research corpora: no importer on the boot path.
REFERENCE: Set[str] = {
    "ai", "backup", "bin", "cloud", "compatibility", "dev", "drivers", "etc",
    "feedback", "fs", "home", "initrd", "installer", "legal",
    "media", "mnt", "network", "opt", "proc", "quantum", "root", "sbin",
    "sdk", "security", "sources", "srv", "tmp", "ui", "usr", "var",
    "virt",
}
# Reference material that is a plain script directory, not an importable package.
REFERENCE_SCRIPT_DIRS: Set[str] = {"examples", "tools"}

# Marker every reference package's __init__.py must carry, so a reader opening
# any corpus package sees the classification immediately.  Applied by
# scripts/mark_reference_packages.py.
REFERENCE_MARKER = "# [REFERENCE-ONLY] Not reachable from main.py"


def _first_party_packages() -> Set[str]:
    """Top-level importable names living in the repository root."""
    names: Set[str] = set()
    for child in ROOT.iterdir():
        if child.name in SKIP_DIRS or child.name.startswith("."):
            continue
        if child.is_dir() and (child / "__init__.py").exists():
            names.add(child.name)
        elif child.is_file() and child.suffix == ".py":
            names.add(child.stem)
    return names


def _module_file(module: str) -> Path | None:
    """Resolve a dotted module name to a file in the repo, or None."""
    rel = Path(*module.split("."))
    candidate = ROOT / rel.with_suffix(".py")
    if candidate.is_file():
        return candidate
    package = ROOT / rel / "__init__.py"
    if package.is_file():
        return package
    return None


def _imports_in(path: Path) -> Iterable[str]:
    """Yield absolute module names imported by ``path`` (static analysis)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import — resolve against the package
                continue
            if node.module:
                yield node.module


def reachable_modules(entry: Path = ENTRY) -> Set[str]:
    """Transitive closure of first-party modules reachable from ``entry``."""
    first_party = _first_party_packages()
    seen: Set[str] = set()
    queue = [entry]
    visited_files: Set[Path] = set()

    while queue:
        current = queue.pop()
        if current in visited_files or not current.is_file():
            continue
        visited_files.add(current)

        for raw in _imports_in(current):
            parts = raw.split(".")
            top = parts[0]
            if top not in first_party:
                continue
            # Record every prefix so both ``kernel`` and ``kernel.scheduler``
            # are attributed to the top-level package.
            for depth in range(1, len(parts) + 1):
                seen.add(".".join(parts[:depth]))
            resolved = _module_file(raw)
            if resolved is not None:
                queue.append(resolved)
            else:
                # Module object does not resolve (e.g. a package __init__ that
                # only re-exports) — still walk the package __init__ if present.
                pkg_init = _module_file(top)
                if pkg_init is not None:
                    queue.append(pkg_init)
    return seen


def reachable_packages() -> Set[str]:
    return {m.split(".")[0] for m in reachable_modules()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--list", action="store_true",
                        help="print the computed sets and exit")
    args = parser.parse_args()

    if not ENTRY.is_file():
        print(f"ERROR: entry point not found: {ENTRY}", file=sys.stderr)
        return 2

    computed = reachable_packages()
    declared_reference = set(REFERENCE)

    if args.list:
        print("reachable:", " ".join(sorted(computed)))
        print("reference:", " ".join(sorted(declared_reference)))
        return 0

    print("UmerOS reachability report")
    print("=" * 60)
    print(f"entry point            : {ENTRY.relative_to(ROOT)}")
    print(f"reachable packages     : {len(computed)}")
    print(f"  {' '.join(sorted(computed))}")
    unreachable = sorted(declared_reference)
    print(f"reference-corpus pkgs  : {len(unreachable)}")
    print(f"  {' '.join(unreachable)}")

    problems = []
    for pkg in sorted(computed & declared_reference):
        problems.append(
            f"'{pkg}' is declared REFERENCE (non-executable) but is reachable "
            f"from main.py — move it to LIVE and update docs/reference_corpus.md"
        )
    first_party = _first_party_packages()
    for pkg in sorted(declared_reference - first_party):
        problems.append(
            f"'{pkg}' is declared REFERENCE but is not an importable package"
        )
    for pkg in sorted(REFERENCE_SCRIPT_DIRS):
        if not (ROOT / pkg).is_dir():
            problems.append(
                f"'{pkg}' is declared a reference script directory but does not exist"
            )
        if pkg in first_party:
            problems.append(
                f"'{pkg}' became an importable package — move it into REFERENCE"
            )

    # Every reference package must advertise the classification in its
    # __init__.py so the tree cannot silently mislead a reader.
    for pkg in sorted(declared_reference):
        init = ROOT / pkg / "__init__.py"
        if not init.is_file():
            continue
        if REFERENCE_MARKER not in init.read_text(encoding="utf-8", errors="replace"):
            problems.append(
                f"'{pkg}/__init__.py' is missing the '{REFERENCE_MARKER}' marker — "
                f"run scripts/mark_reference_packages.py"
            )

    if problems:
        print("\nreachability drift detected:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("\nOK: no package declared non-executable is reachable from main.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
