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
pytest suite for — `feedback/` tier labels.

Neither `feedback/` module carried a `[TODAY]/[EXPERIMENTAL]/[FUTURE]` label.
The fix appends the tier label to the module-docstring title line:
`__init__.py` (a stub) is `[EXPERIMENTAL]`; `models.py` is `[TODAY]`.
"""

import ast
import os
import sys
from pathlib import Path

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

_FEEDBACK = Path(_PROJ) / "feedback"
_MODULES = sorted(_FEEDBACK.glob("*.py"))

_TIERS = ("[TODAY]", "[EXPERIMENTAL]", "[FUTURE]")
_EXPECTED = {
    "__init__.py": "[EXPERIMENTAL]",
    "models.py": "[TODAY]",
}


def _title_line(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    doc = ast.get_docstring(tree)
    assert doc, f"{path.name} has no module docstring"
    return doc.splitlines()[0]


def test_every_feedback_module_has_a_tier_label():
    for p in _MODULES:
        title = _title_line(p)
        assert title.rstrip().endswith(_TIERS), f"{p.name} title lacks a tier label: {title!r}"


def test_expected_tier_labels():
    for name, tier in _EXPECTED.items():
        title = _title_line(_FEEDBACK / name)
        assert title.rstrip().endswith(tier), f"{name} expected {tier}, got {title!r}"


def test_label_is_on_the_title_line_not_buried():
    # the label must be the final token of the FIRST docstring line
    for p in _MODULES:
        assert _title_line(p).count("[") >= 1
