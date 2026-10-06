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

"""Layer classification regression tests (docs/reference_corpus.md).

Only ``boot``, ``core``, ``kernel`` and ``lib/lostfound`` are reachable from
``main.py``.  The other 31 importable packages are *reference corpus*: kept,
tested and useful, but not executed by a booted UmerOS.  These tests stop the
classification from silently drifting — either by a corpus package quietly
becoming reachable, or by the marker disappearing from a package's
``__init__.py`` so a reader is misled again.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_layer_reachability as clr  # noqa: E402


def test_reachable_packages_are_exactly_the_declared_live_set():
    assert clr.reachable_packages() == clr.LIVE


def test_no_reference_package_is_reachable_from_main():
    overlap = clr.reachable_packages() & clr.REFERENCE
    assert not overlap, (
        f"{sorted(overlap)} are declared non-executable but are reachable from "
        f"main.py — update LIVE/REFERENCE and docs/reference_corpus.md"
    )


def test_live_and_reference_are_disjoint():
    assert not (clr.LIVE & clr.REFERENCE)


def test_every_declared_reference_package_exists():
    missing = [p for p in sorted(clr.REFERENCE) if not (_ROOT / p).is_dir()]
    assert missing == []


def test_every_reference_package_advertises_the_marker():
    missing = []
    for pkg in sorted(clr.REFERENCE):
        init = _ROOT / pkg / "__init__.py"
        if not init.is_file():
            continue
        if clr.REFERENCE_MARKER not in init.read_text(encoding="utf-8",
                                                      errors="replace"):
            missing.append(pkg)
    assert missing == [], (
        f"{missing} are missing the '{clr.REFERENCE_MARKER}' marker — run "
        f"scripts/mark_reference_packages.py"
    )


def test_marker_does_not_break_module_docstrings():
    """A comment before the docstring must not stop it being the docstring."""
    import importlib

    for pkg in ("ai", "quantum", "drivers"):
        module = importlib.import_module(pkg)
        assert module.__doc__, f"{pkg} lost its module docstring"


def test_checker_script_exits_zero():
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "check_layer_reachability.py")],
        capture_output=True, text=True, cwd=str(_ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_reference_corpus_doc_exists_and_is_linked_from_readme():
    doc = _ROOT / "docs" / "reference_corpus.md"
    assert doc.is_file(), "docs/reference_corpus.md is the authoritative record"
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/reference_corpus.md" in readme
