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
pytest suite for  — `feedback/` must import cleanly and be honest.
claimed `import feedback` raised ``ModuleNotFoundError`` because
``__init__.py`` imported five non-existent submodules (collector / tracker /
channels / gfdl / manager) via a ``sys.path`` hack. That code premise is now
resolved (relative + guarded imports; the ``sys.path`` hack is gone), and the
header/docstring were made honest about the package being a stub: only
``feedback.models`` exists; the other advertised submodules are marked
``[PLANNED - not implemented]``.
"""

import importlib
import os
import sys
from pathlib import Path

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

_FEEDBACK = Path(_PROJ) / "feedback"
_INIT_SRC = (_FEEDBACK / "__init__.py").read_text(encoding="utf-8")

# submodules advertised in the header that do NOT exist on disk
_MISSING = ("collector", "tracker", "channels", "gfdl", "manager", "cli")


def test_package_imports_cleanly():
    mod = importlib.import_module("feedback")
    assert mod is not None


def test_all_exports_are_real():
    mod = importlib.import_module("feedback")
    assert mod.__all__ == [
        "FeedbackEntry",
        "FeedbackKind",
        "FeedbackStatus",
        "FeedbackPriority",
    ]
    for name in mod.__all__:
        assert hasattr(mod, name), f"{name} listed in __all__ but not present"


def test_selftest_passes():
    mod = importlib.import_module("feedback")
    assert mod._selftest() is True


def test_no_sys_path_hack():
    assert "sys.path.insert" not in _INIT_SRC
    assert "sys.path.append" not in _INIT_SRC


def test_uses_relative_imports():
    assert "from .models import" in _INIT_SRC


def test_advertised_modules_are_actually_absent():
    # the honesty fix is only correct while these really do not exist
    for name in _MISSING:
        assert not (_FEEDBACK / f"{name}.py").exists(), f"{name}.py unexpectedly exists"


def test_header_marks_missing_modules_as_planned():
    for name in _MISSING:
        line = next((l for l in _INIT_SRC.splitlines() if l.startswith(f"# {name}")), None)
        assert line is not None, f"no header line for {name}"
        assert "PLANNED" in line, f"{name} header not marked PLANNED: {line!r}"


def test_docstring_declares_stub():
    assert "[STUB]" in _INIT_SRC
    assert "models" in _INIT_SRC
