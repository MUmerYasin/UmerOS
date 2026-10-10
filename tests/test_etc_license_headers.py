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
pytest suite for H71 — `etc/` license-header compliance.

Every `etc/` module must carry the canonical full GPLv3 comment header, and
any declared license docstring line must use the canonical H7 string
``License: GPL-3.0 (GNU General Public License v3)`` — never the British
``Licence`` spelling nor the verbose ``... Version 3`` form.
"""

import ast
import re
from pathlib import Path

import pytest

_ETC = Path(__file__).resolve().parent.parent / "etc"
_MODULES = sorted(_ETC.glob("*.py"))

CANON = "License: GPL-3.0 (GNU General Public License v3)"
_HEADER_MARKER = "This program is free software: you can redistribute it"
_LICENSE_RE = re.compile(r"^[ \t]*Licen[cs]e:")


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_etc_module_has_gplv3_header(path):
    src = path.read_text(encoding="utf-8")
    assert _HEADER_MARKER in src, f"{path.name} lacks the full GPLv3 comment header"


def test_no_british_or_verbose_license_lines():
    offenders = [
        p.name
        for p in _MODULES
        if "Licence:" in p.read_text(encoding="utf-8")
        or "GNU General Public License Version 3" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"non-canonical license lines in: {offenders}"


def test_declared_license_lines_are_canonical():
    bad = []
    for p in _MODULES:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if _LICENSE_RE.match(line) and line.strip() != CANON:
                bad.append(f"{p.name}:{i}: {line.strip()!r}")
    assert bad == [], f"non-canonical license declarations: {bad}"


@pytest.mark.parametrize("name", ["__init__.py", "login_config.py"])
def test_header_insertion_kept_module_docstring(name):
    tree = ast.parse((_ETC / name).read_text(encoding="utf-8"))
    assert ast.get_docstring(tree), f"{name} lost its module docstring"


def test_init_retains_reference_only_note():
    src = (_ETC / "__init__.py").read_text(encoding="utf-8")
    assert "[REFERENCE-ONLY]" in src
