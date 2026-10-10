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
pytest suite for H69 — `drivers/` baseline compliance:
`from __future__ import annotations`, a module docstring, and stdlib `logging`
(never `loguru`).
"""

import ast
from pathlib import Path

import pytest

_DRIVERS = Path(__file__).resolve().parent.parent / "drivers"
_MODULES = sorted(_DRIVERS.glob("*.py"))


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_driver_module_has_future_annotations(path):
    src = path.read_text(encoding="utf-8")
    assert "from __future__ import annotations" in src, f"{path.name} lacks future annotations"


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_driver_module_has_docstring(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert ast.get_docstring(tree), f"{path.name} lacks a module docstring"


def test_no_driver_module_uses_loguru():
    offenders = [p.name for p in _MODULES if "loguru" in p.read_text(encoding="utf-8")]
    assert offenders == [], f"loguru still used in: {offenders}"


def test_driver_service_uses_stdlib_logging():
    src = (_DRIVERS / "driver_service.py").read_text(encoding="utf-8")
    assert "import logging" in src
    assert "logging.getLogger(" in src
    assert "from loguru import" not in src
