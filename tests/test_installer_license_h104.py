"""tests — installer/ license-header normalization (H7 canonical form).

Live scope (drift-recon'd; the standard's premise was partly stale):
  installer/installer.py - full GPLv3 block, non-canonical license line -> fixed
  installer/__init__.py  - only a short header -> full GPLv3 block added
  installer/install.py   - does NOT exist 
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INST = ROOT / "installer"

CANONICAL = "License: GPL-3.0 (GNU General Public License v3)"
NON_CANONICAL = "License: GPL-3.0 (GNU General Public License Version 3)"

PY_FILES = sorted(INST.glob("*.py"))


def test_installer_folder_has_expected_modules():
    names = {p.name for p in PY_FILES}
    assert names == {"__init__.py", "installer.py"}


def test_install_py_does_not_exist():
    """The standard cites install.py, but it was removed (H98/H106)."""
    assert not (INST / "install.py").exists()


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: p.name)
def test_full_gplv3_comment_block(path):
    text = path.read_text(encoding="utf-8")
    assert "This program is free software" in text
    assert "either version 3 of the License" in text
    assert "GNU General Public License for more details" in text
    assert "https://www.gnu.org/licenses/" in text


def test_installer_py_canonical_line():
    text = (INST / "installer.py").read_text(encoding="utf-8")
    assert CANONICAL in text
    assert NON_CANONICAL not in text


def test_init_py_carries_canonical_note():
    """__init__.py is a package header; it must carry the GPLv3 block."""
    text = (INST / "__init__.py").read_text(encoding="utf-8")
    assert "This program is free software" in text
    assert "GPL-3.0" in text  # the descriptive note is retained


def test_no_non_canonical_or_british_spelling_anywhere():
    for path in PY_FILES:
        text = path.read_text(encoding="utf-8")
        assert NON_CANONICAL not in text
        assert "Licence:" not in text


def test_init_py_descriptive_comment_preserved():
    """The fix must ADD the block, not delete the existing descriptive header."""
    text = (INST / "__init__.py").read_text(encoding="utf-8")
    assert "UmerOS /installer" in text
    assert "[REFERENCE-ONLY]" in text


def test_modules_import_cleanly():
    import importlib
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    pkg = importlib.import_module("installer")
    assert pkg is not None
    mod = importlib.import_module("installer.installer")
    assert hasattr(mod, "UmerInstaller")
