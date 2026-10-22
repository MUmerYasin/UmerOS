"""
H191 - the row claims `opt/` is missing ``from __future__ import annotations``
in 10 modules (``config``, ``manager``, ``package``, ``integration``,
``installers/*``, ``test_opt.py``), with only ``env``/``fhs``/``hierarchy``/
``var`` compliant.

**The premise is fully stale.** Session 187 (H183) added the import to the nine
modules that genuinely lacked it, so all 15 ``opt/`` modules now carry it.
Verified two ways before closing the row:

* a plain text scan (15/15 files contain the import), and
* an AST check that the ``__future__`` import is the *first statement after the
  module docstring* in every file - the placement Python actually requires, and
  the shape section 1 of the standard mandates (``from __future__ import
  annotations`` at top). A stray ``import os`` above it would be a SyntaxError,
  so this is stronger than a substring grep.

These tests pin the invariant instead of re-fixing it: the module list is
discovered dynamically, so a *new* ``opt/`` module added without the import
fails here automatically rather than waiting for the next sweep.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
OPT_ROOT = REPO_ROOT / "opt"


def _opt_modules() -> list[Path]:
    """Every Python module in the opt/ subsystem (caches excluded)."""
    return sorted(
        p for p in OPT_ROOT.rglob("*.py") if "__pycache__" not in p.parts
    )


def _first_post_docstring(tree: ast.Module):
    """The first real statement, skipping the module docstring."""
    body = tree.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return body[0] if body else None


OPT_MODULES = _opt_modules()


# ── the scan itself is sound ──────────────────────────────────────────────

def test_scan_covers_the_subsystem():
    """Guard against the discovery silently missing files."""
    names = {p.name for p in OPT_MODULES}
    # every module the H191 row names, plus the package __init__
    assert {"config.py", "manager.py", "package.py", "integration.py",
            "env.py", "fhs.py", "hierarchy.py", "var.py", "test_opt.py",
            "__init__.py"} <= names
    installers = [p for p in OPT_MODULES if p.parent.name == "installers"]
    assert len(installers) >= 5, "installers/ modules not discovered"
    assert len(OPT_MODULES) >= 15, "opt/ shrank below the audited size"


# ── the invariant ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "module",
    OPT_MODULES,
    ids=lambda p: p.relative_to(REPO_ROOT).as_posix(),
)
def test_future_annotations_is_the_first_statement(module: Path):
    """`from __future__ import annotations` must head the module (post-docstring)."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    first = _first_post_docstring(tree)
    assert isinstance(first, ast.ImportFrom), (
        f"{module.name}: first statement after the docstring is "
        f"{type(first).__name__}, expected the __future__ import"
    )
    assert first.module == "__future__", (
        f"{module.name}: expected `from __future__ import ...`, got {first.module}"
    )
    assert "annotations" in [alias.name for alias in first.names], (
        f"{module.name}: __future__ import lacks `annotations`"
    )


@pytest.mark.parametrize(
    "module",
    OPT_MODULES,
    ids=lambda p: p.relative_to(REPO_ROOT).as_posix(),
)
def test_future_annotations_precedes_every_other_import(module: Path):
    """No import may sit above the __future__ import (Python enforces this too)."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    body = tree.body
    start = 1 if _is_docstring(body) else 0
    for node in body[start:]:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            break
        assert not isinstance(node, (ast.Import, ast.ImportFrom)), (
            f"{module.name}: {ast.dump(node)[:60]} precedes the __future__ import"
        )


def _is_docstring(body) -> bool:
    return bool(
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )
