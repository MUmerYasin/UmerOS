"""tests — initrd/ license-header normalization (H7 canonical form).

The whole `initrd/` folder (17 modules) previously declared the non-canonical
line ``License: GPL-3.0 (GNU General Public License Version 3)``. H7's canonical
form is ``License: GPL-3.0 (GNU General Public License v3)``. This suite asserts
the folder is now 17/17 canonical and carries the full GPLv3 comment block.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INITRD = ROOT / "initrd"

CANONICAL = "License: GPL-3.0 (GNU General Public License v3)"
NON_CANONICAL = "License: GPL-3.0 (GNU General Public License Version 3)"

FILES = sorted(INITRD.glob("*.py"))


def test_folder_has_17_modules():
    assert len(FILES) == 17


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_canonical_license_line(path):
    assert CANONICAL in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_non_canonical_license_line(path):
    assert NON_CANONICAL not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_full_gplv3_comment_block(path):
    text = path.read_text(encoding="utf-8")
    assert "This program is free software" in text
    assert "GNU General Public License" in text
    assert "either version 3 of the License" in text
    # the canonical line sits in the module docstring, before any code
    assert text.index(CANONICAL) < text.index("from __future__")


def test_no_apache_stray_in_folder():
    """The standard's premise mentioned 'Apache strays'; none exist now."""
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        assert "Apache" not in text
        assert "Licence:" not in text  # British spelling must not reappear


def test_all_files_share_one_license_variant():
    variants = set()
    for path in FILES:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("License:"):
                variants.add(line.strip())
    assert variants == {CANONICAL}
