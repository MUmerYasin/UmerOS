"""
H200 - ``packages/`` H7 license strays.  The row says ``umer_pkg.py``'s
docstring declares ``Licence: GPL-3.0 (GNU General Public License Version 3)``
(British spelling + verbose parenthetical) and that ``repository.py`` and
``__init__.py`` carry no license header at all.

Drift-recon corrected the premise on two of its three clauses, exactly as in
``mnt/`` (H176) and ``opt/`` (H183):

* **``umer_pkg.py`` was already half-normalized** - an external pass had
  replaced the British/verbose spelling with the short ``License: GPL-3.0``
  grant line (a comment in the file records it), but the module carried **no
  GPLv3 comment block** at all, so declaration form #1 of
  ``legal/licenses.py``'s fail-closed audit was still missing.
* **``repository.py`` was genuinely headerless** - the premise held (it also
  still starts with a bare shebang).
* **``__init__.py`` had a *prose* header** - "GPL-3.0 - see LICENSE and
  README", the same shape ``opt/__init__.py`` carried before H183 and which
  the fail-closed scanner does not accept - plus the verbose
  ``Version 3`` spelling and a single-space ``Author: UmerOS Project``.
* **The row missed ``trusted_keys.py``** - same class of defect (short-form
  trailer, no GPLv3 comment block); fixed too, per the H183 precedent of
  fixing the files the row missed.

Note that ``legal/licenses.py::scan_directory`` skips ``packages/``
altogether, so the repo-wide fail-closed audit never covered this folder -
these tests are the enforcement mechanism, the ``packages/`` analogue of
``tests/test_opt_license_h183.py``.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PKG = ROOT / "packages"

#: H7 canonical short form used repo-wide.
CANONICAL = "License: GPL-3.0 (GNU General Public License v3)"
#: The long spelling the row (correctly, for __init__.py) flagged.
VERBOSE = "License: GPL-3.0 (GNU General Public License Version 3)"
#: Canonical author trailer (note: two spaces after the colon).
AUTHOR = "Author:  Umer OS Project"
#: First line of the canonical GPLv3 comment block.
GPL_FIRST_LINE = "# This program is free software: you can redistribute it and/or modify"

#: All Python modules under ``packages/`` (caches excluded).
ALL_FILES = tuple(
    str(p.relative_to(PKG)).replace("\\", "/")
    for p in sorted(PKG.rglob("*.py"))
    if "__pycache__" not in p.parts
)


def _read(rel: str) -> str:
    """Read without newline translation (``umer_pkg.py`` is CRLF on disk)."""
    with open(PKG / rel, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


class TestPackagesLicenseHeaders(unittest.TestCase):
    """Every ``packages/`` module carries the H7 canonical form."""

    def test_packages_has_the_expected_modules(self):
        self.assertEqual(
            len(ALL_FILES), 4,
            f"expected 4 modules, got {ALL_FILES}",
        )
        for want in (
            "__init__.py",
            "umer_pkg.py",
            "repository.py",
            "trusted_keys.py",
        ):
            self.assertIn(want, ALL_FILES)

    def test_gpl_block_is_the_first_thing_in_every_module(self):
        """Declaration form #1 of the fail-closed audit, everywhere."""
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                self.assertTrue(
                    _read(rel).startswith(GPL_FIRST_LINE),
                    f"{rel} does not open with the canonical GPL comment block",
                )

    def test_every_module_carries_the_canonical_line(self):
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                self.assertIn(
                    CANONICAL,
                    _read(rel),
                    f"{rel} does not carry the canonical H7 line",
                )

    def test_every_module_carries_the_author_trailer(self):
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                self.assertIn(AUTHOR, _read(rel), f"{rel} lacks the Author: trailer")

    def test_no_verbose_license_line(self):
        """The verbose ``Version 3`` spelling must not appear anywhere."""
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                text = _read(rel)
                self.assertNotIn(VERBOSE, text, f"{rel} still uses 'Version 3'")
                self.assertNotIn(
                    "General Public License Version 3)",
                    text,
                    f"{rel} still mentions the verbose spelling",
                )

    def test_no_british_license_declaration(self):
        """American ``License:`` only - the row's premise clause."""
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                self.assertNotIn("Licence:", _read(rel), f"{rel} uses the British spelling")

    def test_trailer_sits_at_the_end_of_the_module_docstring(self):
        """Placement is the invariant, not mere presence of the string."""
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                tree = ast.parse(_read(rel))
                doc = tree.body[0].value.value
                self.assertTrue(
                    doc.rstrip("\r\n").endswith(CANONICAL),
                    f"{rel}: license line is not the last thing in the docstring",
                )
                self.assertIn(AUTHOR, doc, f"{rel}: trailer not inside the docstring")

    def test_no_mixed_line_endings(self):
        """Each file is internally consistent (the folder is mixed CRLF/LF)."""
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                text = _read(rel)
                crlf = text.count("\r\n")
                total = text.count("\n")
                # all-CRLF (every \n is part of a \r\n) or all-LF (no \r\n)
                self.assertTrue(
                    crlf == total or crlf == 0,
                    f"{rel}: mixed line endings",
                )


class TestScannerCoverageDrift(unittest.TestCase):
    """Why a dedicated test exists: the repo-wide audit skips ``packages/``."""

    def test_general_scanner_skips_packages(self):
        """``legal/licenses.py`` never scans ``packages/`` - pin that fact.

        If a future change removes ``packages`` from the scanner's skip set,
        this test fails on purpose: the coverage decision must be conscious,
        and the H7 canonical form pinned above is what the scanner accepts.
        """
        from legal.licenses import LicenseManager

        result = LicenseManager.scan_directory(PKG)
        self.assertEqual(result.total_files_scanned, 0)
        self.assertEqual(result.missing_license_files, [])

    def test_scanner_markers_cover_the_canonical_line(self):
        """Sanity: the canonical line contains a marker the scanner accepts."""
        self.assertTrue(
            any(
                marker in CANONICAL
                for marker in (
                    "GNU General Public License as published by\n# the Free Software Foundation, either version 3",
                    "License: GPL-3.0",
                    "SPDX-License-Identifier: GPL-3.0",
                    "SPDX-License-Identifier: GPL-3.0-or-later",
                )
            ),
            "canonical line must be scanner-recognisable",
        )


if __name__ == "__main__":
    unittest.main()
