#!/usr/bin/env python3
"""H40 — Add [TODAY] tier labels to all bin/*.py modules (§4.4)."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
TODAY_LABEL = "  [TODAY]"
DRY_RUN = "--dry-run" in sys.argv

stats = {"variant_a": 0, "variant_b": 0, "variant_c": 0, "skipped": 0, "errors": 0}


def classify(lines: list[str]) -> str:
    """Return 'A', 'B', or 'C' based on docstring pattern."""
    # Variant C: __init__.py — comment header, docstring on line ~26
    if lines[0].startswith("# UmerOS"):
        return "C"
    # Find first docstring start
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('"""'):
            # Single-line docstring: """..."""
            if stripped.count('"""') == 2 and len(stripped) > 6:
                return "B"
            # Multi-line docstring: """ on its own line
            return "A"
    return "A"  # fallback


def already_has_tod(label_line: str) -> bool:
    return "[TODAY]" in label_line or "[EXPERIMENTAL]" in label_line or "[FUTURE]" in label_line


def patch_variant_a(lines: list[str]) -> tuple[list[str], bool]:
    """Append [TODAY] after title on line 15 (0-indexed: 14)."""
    for i, line in enumerate(lines):
        if line.strip().startswith('"""') and i + 1 < len(lines):
            title_line_idx = i + 1
            title = lines[title_line_idx].rstrip()
            if already_has_tod(title):
                return lines, False  # already labeled
            new = lines[:]
            new[title_line_idx] = title + TODAY_LABEL + "\n"
            return new, True
    return lines, False


def patch_variant_b(lines: list[str]) -> tuple[list[str], bool]:
    """Single-line docstring: insert [TODAY] before closing triple-quote."""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('"""') and stripped.endswith('"""') and len(stripped) > 6:
            if already_has_tod(stripped):
                return lines, False
            new = lines[:]
            new_line = stripped[:-3] + TODAY_LABEL + '."""\n'
            new[i] = new_line
            return new, True
    return lines, False


def patch_variant_c(lines: list[str]) -> tuple[list[str], bool]:
    """__init__.py: add [TODAY] to docstring on line 26 (0-indexed: 25)."""
    for i, line in enumerate(lines):
        if line.strip().startswith("UmerOS /bin") and line.strip().endswith("binaries."):
            if already_has_tod(line):
                return lines, False
            new = lines[:]
            title = line.rstrip()
            new[i] = title + TODAY_LABEL + "\n"
            return new, True
    return lines, False


def process_file(filepath: Path) -> None:
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ERROR reading {filepath.name}: {e}")
        stats["errors"] += 1
        return

    lines = content.splitlines(keepends=True)
    variant = classify(lines)

    if variant == "C":
        new_lines, patched = patch_variant_c(lines)
        key = "variant_c"
    elif variant == "B":
        new_lines, patched = patch_variant_b(lines)
        key = "variant_b"
    else:
        new_lines, patched = patch_variant_a(lines)
        key = "variant_a"

    if not patched:
        print(f"  SKIP  {filepath.name} (already labeled)")
        stats["skipped"] += 1
        return

    stats[key] += 1
    if DRY_RUN:
        print(f"  PATCH {filepath.name} (variant {variant})")
    else:
        filepath.write_text("".join(new_lines), encoding="utf-8")
        print(f"  PATCHED {filepath.name} (variant {variant})")


def main() -> None:
    print(f"H40: Adding [TODAY] labels to {BIN_DIR}")
    if DRY_RUN:
        print("  *** DRY RUN — no files modified ***\n")

    py_files = sorted(BIN_DIR.glob("*.py"))
    print(f"Found {len(py_files)} .py files\n")

    for f in py_files:
        process_file(f)

    print(f"\nDone: {stats['variant_a']} A, {stats['variant_b']} B, "
          f"{stats['variant_c']} C, {stats['skipped']} skipped, "
          f"{stats['errors']} errors")


if __name__ == "__main__":
    main()
