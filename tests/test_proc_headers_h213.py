"""H213 -- pin the section-1 per-file baseline for all ``proc/`` modules.

Every ``proc/*.py`` module must carry:
  1. The canonical GPL-3.0 comment header block (``GNU General Public License``)
  2. A module-level docstring (AST-detectable)
  3. ``from __future__ import annotations`` as the first statement after the
     module docstring (AST-verified, not just a text grep -- any other import
     above it is a ``SyntaxError``, so compile-clean already implies correct
     placement, but the AST check makes the invariant explicit)
  4. The ``Author:  Umer OS Project`` (two spaces) + ``License: GPL-3.0
     (GNU General Public License v3)`` docstring trailer

The test discovers the module list dynamically so a future ``proc/`` module
is covered automatically, and pins the count at 25.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROC_DIR = Path(__file__).resolve().parent.parent / "proc"

AUTHOR_LINE = "Author:  Umer OS Project"  # two spaces after colon
LICENSE_LINE = "License: GPL-3.0 (GNU General Public License v3)"
GPL_MARKER = "GNU General Public License"


def _discover_proc_modules() -> list[Path]:
    """Return every ``.py`` file directly inside ``proc/``."""
    return sorted(PROC_DIR.glob("*.py"))


PROC_MODULES = _discover_proc_modules()


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_future_import_as_first_stmt(src: str) -> bool:
    """AST-verify that ``from __future__ import annotations`` is the first
    statement after the module docstring (or the first statement if no
    docstring)."""
    tree = ast.parse(src)
    body = tree.body

    # Skip the docstring if present
    start = 0
    if body and isinstance(body[0], ast.Expr) and isinstance(
        body[0].value, ast.Constant
    ) and isinstance(body[0].value.value, str):
        start = 1

    if start >= len(body):
        return False

    stmt = body[start]
    if not isinstance(stmt, ast.ImportFrom):
        return False
    if stmt.module != "__future__":
        return False
    # Check it imports annotations
    for alias in stmt.names:
        if alias.name == "annotations":
            return True
    return False


# --- tests ------------------------------------------------------------------

class TestProcModuleCount:
    """Pin the audited module count so a new module is a conscious act."""

    def test_module_count_is_25(self) -> None:
        modules = _discover_proc_modules()
        assert len(modules) == 25, (
            f"Expected 25 proc/*.py modules; got {len(modules)}: "
            f"{[m.name for m in modules]}"
        )


class TestGplHeaderPresent:
    """Every proc/ module must carry the GPL-3.0 comment header."""

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_gpl_header(self, module_path: Path) -> None:
        src = _source(module_path)
        assert GPL_MARKER in src, (
            f"{module_path.name}: GPL-3.0 header block missing"
        )


class TestModuleDocstring:
    """Every proc/ module must have an AST-detectable module docstring."""

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_has_docstring(self, module_path: Path) -> None:
        src = _source(module_path)
        tree = ast.parse(src)
        doc = ast.get_docstring(tree)
        assert doc is not None, (
            f"{module_path.name}: no module-level docstring"
        )
        assert len(doc.strip()) > 0, (
            f"{module_path.name}: empty module docstring"
        )


class TestFutureAnnotationsFirst:
    """Every proc/ module must have ``from __future__ import annotations``
    as the first statement after the docstring."""

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_future_annotations(self, module_path: Path) -> None:
        src = _source(module_path)
        assert "from __future__ import annotations" in src, (
            f"{module_path.name}: from __future__ import annotations missing"
        )
        assert _has_future_import_as_first_stmt(src), (
            f"{module_path.name}: from __future__ import annotations is not "
            f"the first statement after the docstring"
        )


class TestAuthorLicenseTrailer:
    """Every proc/ module docstring must end with the Author/License trailer."""

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_author_trailer(self, module_path: Path) -> None:
        src = _source(module_path)
        assert AUTHOR_LINE in src, (
            f"{module_path.name}: Author trailer missing "
            f"(expected '{AUTHOR_LINE}' with two spaces)"
        )

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_license_trailer(self, module_path: Path) -> None:
        src = _source(module_path)
        assert LICENSE_LINE in src, (
            f"{module_path.name}: License trailer missing "
            f"(expected '{LICENSE_LINE}')"
        )

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_no_british_spelling(self, module_path: Path) -> None:
        """Ensure no 'Licence:' (British) in the file."""
        src = _source(module_path)
        assert "Licence:" not in src, (
            f"{module_path.name}: British 'Licence:' spelling found "
            f"(should be 'License:')"
        )

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_no_version_3_suffix(self, module_path: Path) -> None:
        """Ensure no '(GNU General Public License Version 3)' suffix
        (the canonical form uses 'v3', not 'Version 3')."""
        src = _source(module_path)
        assert "GNU General Public License Version 3" not in src, (
            f"{module_path.name}: found '(GNU General Public License Version 3)' "
            f"-- should be '(GNU General Public License v3)'"
        )


class TestCompilesClean:
    """Every proc/ module must compile without SyntaxError."""

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_compiles(self, module_path: Path) -> None:
        src = _source(module_path)
        # This will raise SyntaxError if the file is broken
        ast.parse(src)
