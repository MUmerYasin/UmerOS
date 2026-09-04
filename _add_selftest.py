"""Add a standard ``_selftest()`` block to any UmerOS __init__.py that
doesn't already have one.

Usage:
    python _add_selftest.py path/to/__init__.py [more paths...]

The script:
  * Reads each target file.
  * If the file already contains ``def _selftest`` it skips it.
  * Otherwise it appends a uniform ``_selftest()`` + ``__main__`` block
    that imports the module and verifies every public name in
    ``__all__`` is present.

This is a one-shot refactor tool — it can be deleted once the
__init__.py files are updated.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TEMPLATE = '''


def _selftest() -> bool:
    """Verify every public name in ``__all__`` is importable from this package."""
    import importlib as _il
    import sys as _sys
    pkg = _il.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(
            f"{__name__} selftest FAIL: missing {missing}",
            file=_sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
'''


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python _add_selftest.py <file> [<file>...]", file=sys.stderr)
        return 2
    updated = 0
    skipped = 0
    for path_str in argv[1:]:
        p = Path(path_str)
        if not p.is_file():
            print(f"SKIP (not a file): {p}", file=sys.stderr)
            continue
        text = p.read_text(encoding="utf-8")
        if "def _selftest" in text:
            print(f"SKIP (already has _selftest): {p}")
            skipped += 1
            continue
        new_text = text.rstrip() + _TEMPLATE
        p.write_text(new_text, encoding="utf-8")
        print(f"OK  appended _selftest to: {p}")
        updated += 1
    print(f"Updated: {updated}, skipped: {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
