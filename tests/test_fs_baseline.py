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
pytest suite for — `fs/` license headers + per-file baseline.

H81: `fs/qfs.py` declared the verbose `GPL-3.0 (GNU General Public License
Version 3)` (H7 violation), `fs/__init__.py` had no full GPLv3 header,
`fs/vfs.py` lacked `from __future__ import annotations`, and `vfs.py` used
`print(...)` instead of stdlib `logging`. The fix normalizes the license line,
adds the full header to `__init__.py`, adds the future import, swaps `print` for
`logging.getLogger("UmerOS.VFS")`, and completes the §4.4 tier labels.
"""

import ast
import os
import re
import sys
from pathlib import Path

import pytest

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

_FS = Path(_PROJ) / "fs"
_MODULES = sorted(_FS.glob("*.py"))

CANON = "License: GPL-3.0 (GNU General Public License v3)"
_HEADER_MARKER = "This program is free software: you can redistribute it"
_LICENSE_RE = re.compile(r"^[ \t]*#?[ \t]*Licen[cs]e:")
_TIER_RE = re.compile(r"\[(TODAY|EXPERIMENTAL|FUTURE)")


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_fs_module_has_gplv3_header(path):
    assert _HEADER_MARKER in path.read_text(encoding="utf-8"), f"{path.name} lacks the GPLv3 header"


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_fs_module_has_future_annotations(path):
    assert "from __future__ import annotations" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_fs_module_has_docstring(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert ast.get_docstring(tree), f"{path.name} lacks a module docstring"


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_fs_module_has_tier_label(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    title = ast.get_docstring(tree).splitlines()[0]
    assert _TIER_RE.search(title), f"{path.name} title lacks a tier label: {title!r}"


def test_no_verbose_or_british_license_lines():
    offenders = [
        p.name
        for p in _MODULES
        if "GNU General Public License Version 3" in p.read_text(encoding="utf-8")
        or "Licence:" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"non-canonical license lines in: {offenders}"


def test_declared_license_lines_are_canonical():
    bad = []
    for p in _MODULES:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if _LICENSE_RE.match(line):
                norm = re.sub(r"^[ \t]*#?[ \t]*", "", line).strip()
                if norm != CANON:
                    bad.append(f"{p.name}:{i}: {line.strip()!r}")
    assert bad == [], f"non-canonical license declarations: {bad}"


def test_vfs_uses_logging_not_print():
    src = (_FS / "vfs.py").read_text(encoding="utf-8")
    assert "print(" not in src
    assert "import logging" in src
    assert 'logging.getLogger("UmerOS.VFS")' in src


def test_fs_package_imports():
    import importlib

    mod = importlib.import_module("fs")
    assert "VirtualFileSystem" in mod.__all__
