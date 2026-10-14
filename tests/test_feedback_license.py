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
pytest suite for H77 — `feedback/` license headers.

both `feedback/__init__.py` and `feedback/models.py` used the verbose
``License: GPL-3.0 (GNU General Public License Version 3)`` (H7 says the
canonical form is ``License: GPL-3.0 (GNU General Public License v3)``), and the
package docstring left the GNU FDL reference unreconciled (GFDL is a
*documentation* license, not a code license).
"""

import os
import re
import sys
from pathlib import Path

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

_FEEDBACK = Path(_PROJ) / "feedback"
_MODULES = sorted(_FEEDBACK.glob("*.py"))

CANON = "License: GPL-3.0 (GNU General Public License v3)"
_HEADER_MARKER = "This program is free software: you can redistribute it"
_LICENSE_RE = re.compile(r"^[ \t]*#?[ \t]*Licen[cs]e:")


def test_every_feedback_module_has_gplv3_header():
    for p in _MODULES:
        src = p.read_text(encoding="utf-8")
        assert _HEADER_MARKER in src, f"{p.name} lacks the full GPLv3 comment header"


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


def test_both_files_declare_canonical_license():
    assert (_FEEDBACK / "__init__.py").read_text(encoding="utf-8").count(CANON) == 1
    assert (_FEEDBACK / "models.py").read_text(encoding="utf-8").count(CANON) == 1


def test_gfdl_reference_reconciled():
    src = (_FEEDBACK / "__init__.py").read_text(encoding="utf-8")
    # NB: the cosmetic tag can be stripped by external
    # tooling, so assert on the substantive note instead.
    # the note must make explicit that GFDL governs docs output, not code
    assert "documentation output" in src
    assert "not relicense any code" in src
