#!/usr/bin/env python3
"""
H14 — README doc-drift check (CI gate).

The README documents an *aspirational* architecture: some code examples
`import` modules that are not (yet) present in the tree, and the Project
Structure tree lists planned modules.  This check guards against the worst
regression class — code examples that import a **phantom module** (a file that
does not exist in the repo) — so the README can never again silently claim a
runnable import for a non-existent module.

What it does
------------
* Parses fenced ```python blocks in README.md.
* Extracts `import <mod>` / `from <mod> import ...` statements.
* For each referenced module whose top-level package IS a repo directory,
  verifies the file `<repo>/<mod>.py` (or `<mod>/__init__.py`) exists.
* Modules in PLANNED_MODULES are allowed (documented as 🚧 planned in README).
* Stdlib / third-party modules (top-level not a repo dir) are skipped.

Exit code 1 if any non-allowed, non-external module path is missing.

Author: Umer OS Project  ·  License: GPL-3.0
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

# Modules the README explicitly documents as PLANNED / not-yet-present
# (see the "📌 Documentation status" note and the 🚧 tree markers).
PLANNED_MODULES = {
    "kernel.ipc",
    "security.crypto",
    "fs.quantum_fs",
    "ui.shell",
}

# Directories that are NOT source trees — skip any top-level package absent here.
SKIP_TOPLEVEL_DIRS = {
    ".git", ".github", "node_modules", "__pycache__",
    ".workbuddy-ai", "Old Linux Code", "build", "dist",
    ".venv", "venv", "Lib", "Scripts",
}

_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_.]+))"
)


def _repo_top_dirs() -> set[str]:
    return {
        p.name for p in ROOT.iterdir()
        if p.is_dir() and p.name not in SKIP_TOPLEVEL_DIRS
    }


def _module_resolves(mod: str) -> bool:
    rel = Path(*mod.split("."))
    return (ROOT / rel.with_suffix(".py")).exists() or (ROOT / rel / "__init__.py").exists()


def main() -> int:
    if not README.exists():
        print(f"ERROR: {README} not found", file=sys.stderr)
        return 2

    text = README.read_text(encoding="utf-8")
    top_dirs = _repo_top_dirs()

    missing: list[str] = []
    in_python = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            fence = stripped[3:].strip()
            in_python = fence in ("python", "py")
            continue
        if not in_python:
            continue
        m = _IMPORT_RE.match(line)
        if not m:
            continue
        mod = m.group(1) or m.group(2)
        top = mod.split(".")[0]
        if top not in top_dirs:
            continue  # external / stdlib — not our tree
        if mod in PLANNED_MODULES:
            continue  # documented as planned/aspirational
        if not _module_resolves(mod):
            missing.append(mod)

    if missing:
        print("README doc-drift: code examples import modules absent from the tree:")
        for mod in sorted(set(missing)):
            print(f"  - {mod}  (expected {ROOT / Path(*mod.split('.'))})")
        print("\nIf the module is planned/aspirational, add it to PLANNED_MODULES in")
        print("scripts/check_readme_drift.py and mark it 🚧 in the README tree.")
        return 1

    print("README doc-drift check: OK (no phantom module imports in examples).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
