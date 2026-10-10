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
pytest suite for H70 — every `etc/` module must carry a mandatory tier label
(`[TODAY]` / `[EXPERIMENTAL]` / `[FUTURE]`, §4.4).
"""

import re
from pathlib import Path

import pytest

_ETC = Path(__file__).resolve().parent.parent / "etc"
_MODULES = sorted(_ETC.glob("*.py"))
_TIER = re.compile(r"\[(TODAY|EXPERIMENTAL|FUTURE)\]")


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_etc_module_has_tier_label(path):
    src = path.read_text(encoding="utf-8")
    assert _TIER.search(src), f"{path.name} lacks a [TODAY]/[EXPERIMENTAL]/[FUTURE] tier label"


@pytest.mark.parametrize("name", ["config_manager.py", "pam_config.py", "fstab_manager.py"])
def test_framework_managers_labelled_today(name):
    """The framework managers called out by H70 must be [TODAY]."""
    src = (_ETC / name).read_text(encoding="utf-8")
    assert "[TODAY]" in src
