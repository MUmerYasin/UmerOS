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

"""H236 -- canonical GPLv3 header across ``scripts/``.

The row says ``scripts/`` is "2 tooling scripts (1,736 bytes)" and that "grep
found zero ``GPL``/``Apache``/``Copyright``/``Licence``/``License`` strings;
neither ``scripts/`` file carries any header".

Drift-recon (session 222): premise **stale in both halves** --

* the folder holds **five** scripts, not two.  ``check_layer_reachability.py``,
  ``check_readme_drift.py`` and ``mark_reference_packages.py`` were added after
  the survey and carry **no** licence at all;
* the two the row names, ``install_deps.py`` and ``test_endpoint.py``, **already
  had** the canonical 12-line GPLv3 comment block (so "zero GPL strings" is
  simply wrong), but neither had a module docstring, a §1 trailer, or
  ``from __future__ import annotations``.

Fix: the canonical block on all five, the ``Author:  Umer OS Project`` +
``License: GPL-3.0 (GNU General Public License v3)`` trailer on all five
docstrings (two of which had to be created), and ``from __future__`` as the
first post-docstring statement in the two that lacked it.

One deliberate deviation from the repo's usual ordering: 58 files put the GPL
block *above* the shebang (``packages/repository.py``, ``boot/demo_boot.py``,
…).  Both executable scripts here are mode 0755 and are meant to be run as
``./scripts/check_readme_drift.py``, and a shebang on line 2 is inert -- so for
those two the shebang stays on line 1 and the block starts on line 2.  The
declaration is still inside the 2 KB window ``legal/licenses.py`` scans, so the
fail-closed audit accepts them.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
if str(PROJ) not in sys.path:
    sys.path.insert(0, str(PROJ))

SCRIPTS = PROJ / "scripts"

CANON = "License: GPL-3.0 (GNU General Public License v3)"
AUTHOR = "Author:  Umer OS Project"

#: The five scripts audited in session 222.  A sixth file is a conscious act.
EXPECTED_MODULES = [
    "check_layer_reachability.py",
    "check_readme_drift.py",
    "install_deps.py",
    "mark_reference_packages.py",
    "test_endpoint.py",
]

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
    return sorted(p for p in SCRIPTS.glob("*.py") if "__pycache__" not in p.parts)


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(params=EXPECTED_MODULES)
def module(request) -> Path:
    return SCRIPTS / request.param


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

class TestHeaders:
    def test_module_set_is_pinned(self):
        found = [p.name for p in _modules()]
        assert found == EXPECTED_MODULES, (
            f"scripts/ module set changed (the H236 survey found 2, this pins 5): {found}"
        )

    def test_gpl_block_present(self, module):
        lines = _src(module).splitlines()
        if lines[:12] == GPL_BLOCK:
            return
        assert lines and lines[0].startswith("#!"), (
            f"{module.name} has neither a leading GPL block nor a shebang"
        )
        assert lines[1:13] == GPL_BLOCK, (
            f"{module.name}: GPL block is not at line 1 or line 2"
        )

    def test_executable_scripts_keep_the_shebang_first(self, module):
        """A shebang on line 2 does nothing, so 0755 scripts must lead with it.

        POSIX only: ``os.access(..., os.X_OK)`` answers "readable" on Windows,
        so every file looks executable there and the skip never fires.
        """
        if os.name == "nt":
            pytest.skip("POSIX permission bits only")
        if not os.access(module, os.X_OK):
            pytest.skip(f"{module.name} is not executable")
        assert _src(module).splitlines()[0].startswith("#!"), (
            f"{module.name} is executable but its shebang is not on line 1"
        )

    def test_canonical_license_line(self, module):
        assert CANON in _src(module), f"{module.name} must carry the canonical line"

    def test_no_spelled_out_version_3(self, module):
        assert "Version 3" not in _src(module)

    def test_no_british_spelling(self, module):
        assert "Licence:" not in _src(module)

    def test_author_trailer_two_spaces(self, module):
        """The trailer needs two spaces; ``#`` comments must not drift to one.

        A plain substring scan is wrong here: ``check_layer_reachability.py``
        and ``check_readme_drift.py`` describe the convention *in prose* inside
        their own docstrings (``Author: Umer OS Project  ·  License: GPL-3.0``
        -- a single space, deliberately, because it is a sentence fragment, not
        a trailer).  The trailer's exact form is already pinned structurally by
        ``test_trailer_is_last_two_docstring_lines``; what is left to police is
        the comment lines.
        """
        src = _src(module)
        assert AUTHOR in src, f"{module.name} must carry the two-space Author trailer"
        offenders = [
            f"{i}: {ln.strip()}"
            for i, ln in enumerate(src.splitlines(), 1)
            if ln.lstrip().startswith("#")
            and "Author: Umer OS Project" in ln
            and AUTHOR not in ln
        ]
        assert offenders == [], (
            f"{module.name} has a single-space Author line in a comment: {offenders}"
        )

    def test_exactly_one_license_declaration(self, module):
        hits = [
            f"{i}: {ln.strip()}"
            for i, ln in enumerate(_src(module).splitlines(), 1)
            if _LICENSE_LINE_RE.match(ln)
        ]
        assert len(hits) == 1, f"{module.name}: expected 1 License line, found {hits}"

    def test_compiles(self, module):
        ast.parse(_src(module))

    def test_line_endings_are_internally_consistent(self, module):
        """The folder is mixed CRLF/LF; a single file must not be."""
        raw = module.read_bytes()
        crlf = raw.count(b"\r\n")
        assert crlf == 0 or crlf == raw.count(b"\n"), (
            f"{module.name} mixes CRLF and LF line endings"
        )


# ---------------------------------------------------------------------------
# Section 1 per-file baseline
# ---------------------------------------------------------------------------

class TestSectionOneBaseline:
    def test_has_module_docstring(self, module):
        assert ast.get_docstring(ast.parse(_src(module))) is not None, (
            f"{module.name} has no module docstring"
        )

    def test_trailer_is_last_two_docstring_lines(self, module):
        doc = ast.get_docstring(ast.parse(_src(module)), clean=False)
        tail = [ln for ln in doc.strip().splitlines() if ln.strip()]
        assert tail[-2:] == [AUTHOR, CANON], (
            f"{module.name}: docstring must END with the Author/License trailer, "
            f"got {tail[-2:]!r}"
        )

    def test_trailer_is_inside_the_docstring(self, module):
        doc = ast.get_docstring(ast.parse(_src(module)), clean=False)
        assert CANON in doc, (
            f"{module.name}: the License line sits outside the module docstring"
        )

    def test_future_annotations_first_after_docstring(self, module):
        tree = ast.parse(_src(module))
        body = tree.body
        assert isinstance(body[0], ast.Expr) and isinstance(
            body[0].value, ast.Constant
        ), f"{module.name} must start with a module docstring"
        first = body[1]
        assert isinstance(first, ast.ImportFrom) and first.module == "__future__", (
            f"{module.name}: 'from __future__ import annotations' must be the "
            "first statement after the docstring"
        )
        assert [a.name for a in first.names] == ["annotations"]


# ---------------------------------------------------------------------------
# The repo's own fail-closed audit is the authority
# ---------------------------------------------------------------------------

class TestFailClosedAudit:
    def test_scan_directory_reports_full_compliance(self):
        from legal.licenses import LicenseManager

        result = LicenseManager.scan_directory(SCRIPTS)
        assert result.total_files_scanned == 5, (
            f"expected 5 files scanned, got {result.total_files_scanned}"
        )
        assert result.compliant_files == 5, (
            f"only {result.compliant_files}/5 scripts carry a GPL-3.0 declaration "
            "the fail-closed audit accepts"
        )

    def test_scripts_is_not_excluded_from_the_audit(self):
        from legal.licenses import LicenseManager

        assert LicenseManager.scan_directory(SCRIPTS).total_files_scanned > 0, (
            "scripts/ is being skipped by scan_directory"
        )


# ---------------------------------------------------------------------------
# Folder-wide sweep
# ---------------------------------------------------------------------------

class TestFolderSweep:
    def test_no_leftover_version_3(self):
        offenders = [
            p.name
            for p in SCRIPTS.rglob("*")
            if p.is_file()
            and p.suffix in (".py", ".md")
            and "__pycache__" not in p.parts
            and "Version 3" in _src(p)
        ]
        assert offenders == [], f"'Version 3' still present in {offenders}"
