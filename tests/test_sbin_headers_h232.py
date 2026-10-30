"""pin the canonical GPL-3.0 header across ``sbin/``.

The row claims a grep "across all 9 files found ZERO ``GPL``/``Apache``/
``Copyright`` strings ... this package silently ships no license at all".

Drift-recon (session 218): premise **stale for 8 of 9 modules, true for one**.
Every module except ``sbin/__init__.py`` already opened with the canonical
12-line GPLv3 comment block -- the exact block that ``legal/licenses.py``'s
fail-closed audit accepts as declaration form #1.  Running that audit against
the folder proved it: ``scan_directory("sbin")`` reported **9 scanned / 8
compliant** before any change.  The single genuine headerless module was
``sbin/__init__.py``, which carried only a prose banner
(``# GPL-3.0 -- see LICENSE and README for details.``) -- the same shape
``packages/__init__.py`` had at H200, and the shape the scanner rejects.

The real repo-wide gap was the **§1 per-file baseline trailer**: none of the
nine module docstrings ended with ``Author:  Umer OS Project`` (two spaces) +
``License: GPL-3.0 (GNU General Public License v3)``.  That is what this file
pins, alongside the header, so the folder cannot silently drift back.

Prints are deliberately **not** asserted here: ``sbin/`` is a CLI command
package whose whole job is emitting command output, and the "commands
masquerade as functional" concern is 💭 **H235**'s remit, not H232's.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import sys

PROJ = Path(__file__).resolve().parent.parent
if str(PROJ) not in sys.path:
    sys.path.insert(0, str(PROJ))

SBIN = PROJ / "sbin"

CANON = "License: GPL-3.0 (GNU General Public License v3)"
AUTHOR = "Author:  Umer OS Project"

#: The nine modules audited in session 218.  A tenth file is a conscious act.
EXPECTED_MODULES = [
    "__init__.py",
    "boot.py",
    "filesystem.py",
    "maintenance.py",
    "modules.py",
    "mount.py",
    "network.py",
    "sbin_manager.py",
    "system.py",
]

#: The canonical 12-line GPLv3 comment block, byte for byte.
GPL_BLOCK = [
    "# This program is free software: you can redistribute it and/or modify",
    "# it under the terms of the GNU General Public License as published by",
    "# the Free Software Foundation, either version 3 of the License, or",
    "# (at your option) any later version.",
    "#",
    "# This program is distributed in the hope that it will be useful,",
    "# but WITHOUT ANY WARRANTY; without even the implied warranty of",
    "# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the",
    "# GNU General Public License for more details.",
    "#",
    "# You should have received a copy of the GNU General Public License",
    "# along with this program.  If not, see <https://www.gnu.org/licenses/>.",
]

_LICENSE_LINE_RE = re.compile(r"^[ \t]*#?[ \t]*Licen[cs]e:")


def _modules() -> list[Path]:
    return sorted(p for p in SBIN.glob("*.py") if "__pycache__" not in p.parts)


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(params=EXPECTED_MODULES)
def module(request) -> Path:
    return SBIN / request.param


# ---------------------------------------------------------------------------
# The nine modules -- header
# ---------------------------------------------------------------------------

class TestModuleHeaders:
    def test_module_set_is_pinned(self):
        found = [p.name for p in _modules()]
        assert found == EXPECTED_MODULES, f"sbin/ module set changed: {found}"

    def test_opens_with_canonical_gpl_block(self, module):
        """The block must be the *first* thing in the file, not appended later."""
        lines = _src(module).splitlines()
        assert lines[:12] == GPL_BLOCK, (
            f"{module.name} does not open with the canonical 12-line GPLv3 block"
        )

    def test_canonical_license_line(self, module):
        assert CANON in _src(module), f"{module.name} must carry the canonical line"

    def test_no_spelled_out_version_3(self, module):
        assert "Version 3" not in _src(module), (
            f"{module.name} still spells out 'Version 3'"
        )

    def test_no_british_spelling(self, module):
        assert "Licence:" not in _src(module), (
            f"{module.name} has the British 'Licence:' spelling"
        )

    def test_author_trailer_two_spaces(self, module):
        assert AUTHOR in _src(module), (
            f"{module.name} must carry 'Author:  Umer OS Project' (two spaces)"
        )
        assert "Author: Umer OS Project" not in _src(module).replace(AUTHOR, ""), (
            f"{module.name} has a single-space Author line somewhere"
        )

    def test_exactly_one_license_declaration(self, module):
        """A second stray header is precisely the H7 defect being fixed."""
        hits = [
            f"{i}: {ln.strip()}"
            for i, ln in enumerate(_src(module).splitlines(), 1)
            if _LICENSE_LINE_RE.match(ln)
        ]
        assert len(hits) == 1, f"{module.name}: expected 1 License line, found {hits}"

    def test_license_line_is_byte_identical(self, module):
        for line in _src(module).splitlines():
            if _LICENSE_LINE_RE.match(line):
                assert line == CANON, f"{module.name}: unexpected line {line!r}"

    def test_compiles(self, module):
        ast.parse(_src(module))

    def test_crlf_preserved(self, module):
        raw = module.read_bytes()
        assert raw.count(b"\r\n") == raw.count(b"\n"), (
            f"{module.name}: mixed line endings introduced"
        )


# ---------------------------------------------------------------------------
# The trailer lives at the *end* of the module docstring (AST-verified)
# ---------------------------------------------------------------------------

class TestDocstringTrailer:
    def test_trailer_is_last_two_lines_of_docstring(self, module):
        doc = ast.get_docstring(ast.parse(_src(module)), clean=False)
        assert doc is not None, f"{module.name} has no module docstring"
        tail = [ln for ln in doc.strip().splitlines() if ln.strip()]
        assert tail[-2:] == [AUTHOR, CANON], (
            f"{module.name}: docstring must END with the Author/License trailer, "
            f"got {tail[-2:]!r}"
        )

    def test_trailer_is_inside_the_docstring_not_a_stray_comment(self, module):
        """The License line must be part of the string, not a `#` comment."""
        doc = ast.get_docstring(ast.parse(_src(module)), clean=False)
        assert CANON in doc, (
            f"{module.name}: License line sits outside the module docstring"
        )


# ---------------------------------------------------------------------------
# Section 1 per-file baseline
# ---------------------------------------------------------------------------

class TestSectionOneBaseline:
    def test_has_module_docstring(self, module):
        assert ast.get_docstring(ast.parse(_src(module))) is not None

    def test_future_annotations_first_after_docstring(self, module):
        tree = ast.parse(_src(module))
        body = tree.body
        assert isinstance(body[0], ast.Expr) and isinstance(
            body[0].value, ast.Constant
        ), f"{module.name} must start with a module docstring"
        assert len(body) > 1, f"{module.name} has no statements after the docstring"
        first = body[1]
        assert isinstance(first, ast.ImportFrom) and first.module == "__future__", (
            f"{module.name}: 'from __future__ import annotations' must be the "
            "first statement after the docstring"
        )
        assert [a.name for a in first.names] == ["annotations"]


# ---------------------------------------------------------------------------
# The decisive behavioural test: the repo's own fail-closed audit
# ---------------------------------------------------------------------------

class TestFailClosedAudit:
    def test_scan_directory_reports_full_compliance(self):
        """`legal/licenses.py` is the authority; it must now say 9/9."""
        from legal.licenses import LicenseManager

        result = LicenseManager.scan_directory(SBIN)
        assert result.total_files_scanned == 9, (
            f"expected 9 files scanned, got {result.total_files_scanned}"
        )
        assert result.compliant_files == 9, (
            f"only {result.compliant_files}/9 sbin modules carry a GPL-3.0 "
            "declaration the fail-closed audit accepts"
        )

    def test_sbin_is_not_excluded_from_the_audit(self):
        """`packages/` is skipped by the scanner; `sbin/` must not be.

        If someone adds `sbin` to the skip list this test fails, forcing the
        coverage change to be a conscious act (the H200 precedent).
        """
        from legal.licenses import LicenseManager

        result = LicenseManager.scan_directory(SBIN)
        assert result.total_files_scanned > 0, (
            "sbin/ is being skipped by scan_directory -- the audit no longer "
            "covers this folder"
        )


# ---------------------------------------------------------------------------
# Folder-wide sweep
# ---------------------------------------------------------------------------

class TestFolderSweep:
    def test_no_leftover_version_3_anywhere_under_sbin(self):
        offenders = [
            p.name
            for p in SBIN.rglob("*")
            if p.is_file()
            and p.suffix in (".py", ".md")
            and "__pycache__" not in p.parts
            and "Version 3" in _src(p)
        ]
        assert not offenders, f"'Version 3' still present in {offenders}"

    def test_package_still_imports(self):
        import importlib

        mod = importlib.import_module("sbin")
        assert hasattr(mod, "__all__")
