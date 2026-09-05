# UmerOS — H8 lint gate
# AST-based check that all ``except Exception: pass`` catches inside
# ``bin/*.py`` are inside a ``_selftest()`` function.  Operational
# code must use narrower exception types (see H8 remediation).
#
# Run with:  python -m pytest tests/test_h8_lint.py -v

from __future__ import annotations

import ast
import pathlib
import sys
import textwrap
from typing import List

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "bin"

# ── helpers ──────────────────────────────────────────────────────────────────

def _inside_selftest(node: ast.AST, parent_stack: list[ast.AST]) -> bool:
    """Return True when *node* is nested inside a ``_selftest`` function."""
    for ancestor in parent_stack:
        if isinstance(ancestor, ast.FunctionDef) and ancestor.name == "_selftest":
            return True
    return False


def _find_bare_exception_pass(filepath: pathlib.Path) -> List[dict]:
    """Parse *filepath* and return every ``except Exception: pass`` outside ``_selftest``."""
    source = filepath.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(filepath))

    results: list[dict] = []
    parent_stack: list[ast.AST] = []

    def _visit(node: ast.AST, stack: list[ast.AST]) -> None:
        new_stack = stack + [node]
        if isinstance(node, ast.ExceptHandler):
            # Check: bare ``except Exception: pass``
            is_exception = (
                node.type is not None
                and isinstance(node.type, ast.Name)
                and node.type.id == "Exception"
            )
            is_bare_pass = (
                len(node.body) == 1
                and isinstance(node.body[0], ast.Pass)
            )
            if is_exception and is_bare_pass and not _inside_selftest(node, new_stack):
                results.append(
                    {
                        "file": str(filepath),
                        "line": node.lineno,
                        "col": node.col_offset,
                    }
                )
        for child in ast.iter_child_nodes(node):
            _visit(child, new_stack)

    _visit(tree, [])
    return results


# ── test ─────────────────────────────────────────────────────────────────────

def test_h8_bare_except_outside_selftest():
    """All ``except Exception: pass`` outside ``_selftest`` must be narrowed."""
    violations: list[dict] = []
    for py_file in sorted(BIN_DIR.glob("*.py")):
        violations.extend(_find_bare_exception_pass(py_file))

    if violations:
        lines = ["H8 lint violations — bare ``except Exception: pass`` outside _selftest():\n"]
        for v in violations:
            rel = v["file"].replace(str(BIN_DIR.parent) + "\\", "").replace("\\", "/")
            lines.append(f"  {rel}:{v['line']}:{v['col']}")
        lines.append(
            "\nFix: narrow the exception type (e.g. ``except (OSError, ValueError): pass``)"
            " and add a ``# [FIX H8]`` comment."
        )
        pytest.fail("\n".join(lines))
