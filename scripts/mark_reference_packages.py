"""One-off migration: mark reference-corpus packages with [REFERENCE-ONLY].

Idempotent and assert-first: re-running is a no-op, and every edited file is
re-compiled before the script reports success.
"""
from __future__ import annotations

import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_layer_reachability import REFERENCE  # noqa: E402

MARKER = "# [REFERENCE-ONLY] Not reachable from main.py — see docs/reference_corpus.md"


def insert_marker(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if any(MARKER in ln for ln in lines):
        return False

    # Insert after the leading run of comments/blank lines (license header,
    # shebang, coding declaration) and before the first statement (docstring).
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].lstrip()
        if stripped.startswith("#") or not stripped.strip():
            idx += 1
        else:
            break

    lines.insert(idx, MARKER + "\n")
    if idx < len(lines) - 1 and lines[idx + 1].strip() and not lines[idx + 1].startswith("\n"):
        lines.insert(idx + 1, "\n")

    path.write_text("".join(lines), encoding="utf-8")
    return True


def main() -> int:
    changed, skipped, missing = [], [], []
    for pkg in sorted(REFERENCE):
        init = ROOT / pkg / "__init__.py"
        if not init.is_file():
            missing.append(pkg)
            continue
        if insert_marker(init):
            changed.append(pkg)
        else:
            skipped.append(pkg)

    for pkg in changed:
        target = ROOT / pkg / "__init__.py"
        try:
            py_compile.compile(str(target), doraise=True)
        except py_compile.PyCompileError as exc:
            print(f"COMPILE FAILED after edit: {target}\n{exc}", file=sys.stderr)
            return 1
        if MARKER not in target.read_text(encoding="utf-8"):
            print(f"marker missing after edit: {target}", file=sys.stderr)
            return 1

    print(f"marked    ({len(changed)}): {' '.join(changed) or '-'}")
    print(f"already   ({len(skipped)}): {' '.join(skipped) or '-'}")
    print(f"no __init__({len(missing)}): {' '.join(missing) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
