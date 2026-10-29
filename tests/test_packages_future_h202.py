# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
H202 - the row claims ``packages/repository.py`` and ``packages/__init__.py``
are missing ``from __future__ import annotations`` (only ``umer_pkg.py``
compliant).

**The premise is half stale.** ``packages/__init__.py`` already carried the
import (it arrived with the H200 license-header work); the genuine gap was
``repository.py``, fixed in session 198.  The invariant is pinned the same way
as the opt/ H191 sweep: a text scan plus an AST check that the ``__future__``
import is the *first statement after the module docstring* - the placement
Python actually requires and the shape section 1 of the standard mandates.
The module list is discovered dynamically, so a new ``packages/`` module added
without the import fails here automatically.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = REPO_ROOT / "packages"

FUTURE_IMPORT = "from __future__ import annotations"


def _pkg_modules() -> list[Path]:
    """Every Python module in the packages/ subsystem (caches excluded)."""
    return sorted(
        p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts
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


PKG_MODULES = _pkg_modules()


# ── the scan itself is sound ──────────────────────────────────────────────

def test_scan_covers_the_subsystem():
    """Guard against the discovery silently missing files."""
    names = {p.name for p in PKG_MODULES}
    # every module the H202 row names, plus the rest of the package manager
    assert {"repository.py", "__init__.py", "umer_pkg.py",
            "trusted_keys.py"} <= names
    assert len(PKG_MODULES) >= 4, "packages/ shrank below the audited size"


def test_expected_module_count():
    """The audited folder is four modules; a new one must be a conscious act."""
    assert len(PKG_MODULES) == 4, (
        f"packages/ module set changed: {[p.name for p in PKG_MODULES]}"
    )


# ── the invariant ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "module",
    PKG_MODULES,
    ids=lambda p: p.relative_to(REPO_ROOT).as_posix(),
)
def test_future_import_present(module: Path):
    """Plain text scan - every module carries the import somewhere."""
    text = module.read_text(encoding="utf-8")
    assert FUTURE_IMPORT in text, f"{module.name}: no __future__ import"


@pytest.mark.parametrize(
    "module",
    PKG_MODULES,
    ids=lambda p: p.relative_to(REPO_ROOT).as_posix(),
)
def test_future_import_is_first_statement(module: Path):
    """AST check - the import is the first statement after the docstring.

    Stronger than a substring grep: any other import above it would be a
    SyntaxError at runtime, so this pins the placement Python requires.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"), str(module))
    first = _first_post_docstring(tree)
    assert first is not None, f"{module.name}: no statement after the docstring"
    assert isinstance(first, ast.ImportFrom), (
        f"{module.name}: first statement is {type(first).__name__},"
        f" not an import"
    )
    assert first.module == "__future__", (
        f"{module.name}: first import is from {first.module!r},"
        f" not __future__"
    )
    assert [a.name for a in first.names] == ["annotations"], (
        f"{module.name}: __future__ imports"
        f" {[a.name for a in first.names]}, expected ['annotations']"
    )
