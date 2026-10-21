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

"""tests — ``opt/`` uses the H7 canonical GPL-3.0 header form.

The standard flagged ``opt/`` (🟡 H183): "``env``/``fhs``/``hierarchy``/``var``
say ``Licence: GPL-3.0 (GNU General Public License Version 3)`` (British
spelling, like mnt H176); ``config``/``manager``/``package``/``integration``/
``installers/*``/``test_opt`` have NO header at all."

Drift-recon corrected the premise on three of its four clauses:

* **No British spelling anywhere.** Zero ``Licence:`` occurrences, exactly as
  in ``mnt/`` (H176).
* **Nothing was headerless.** Every one of the 15 modules already carried the
  canonical GPLv3 comment block — declaration form #1 of
  ``legal/licenses.py``'s fail-closed audit. The clause's author had mistaken
  the *missing ``Author:``/``License:`` trailer* for a missing header.
* **``var`` was mis-listed.** It already used the short ``License: GPL-3.0``;
  its "Version 3" hit was an explanatory comment about the repo being GPL-3.0.

What was genuinely wrong, and what these tests pin:

* ``opt/env.py``, ``opt/fhs.py`` and ``opt/hierarchy.py`` did use the verbose
  ``... (GNU General Public License Version 3)`` spelling where the repo
  baseline uses the canonical short form ``... v3``.
* ``opt/config.py``, ``opt/package.py`` and ``opt/var.py`` used the bare
  ``License: GPL-3.0`` grant line, and ``config``/``package`` had no
  ``Author:`` line at all.
* ``opt/__init__.py`` and ``opt/installers/__init__.py`` — **missed by the
  row** — used a *prose* header ("GPL-3.0 — see LICENSE and README"), which
  the fail-closed scanner does **not** accept: ``scan_directory("opt")``
  reported 13/15 compliant before any change. These two were real failures.
* Nine modules lacked ``from __future__ import annotations``.

This is the ``opt/`` analogue of the completed ``mnt/`` (H176) and
``network/`` (H181) fixes.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OPT = ROOT / "opt"

#: H7 canonical short form used repo-wide.
CANONICAL = "License: GPL-3.0 (GNU General Public License v3)"
#: The long spelling the three modules used to carry.
VERBOSE = "License: GPL-3.0 (GNU General Public License Version 3)"
#: Canonical author trailer (note: two spaces after the colon).
AUTHOR = "Author:  Umer OS Project"
#: First line of the canonical GPLv3 comment block.
GPL_FIRST_LINE = "# This program is free software: you can redistribute it and/or modify"

#: All 15 Python modules under ``opt/``.
ALL_FILES = tuple(
    str(p.relative_to(OPT)).replace("\\", "/")
    for p in sorted(OPT.rglob("*.py"))
)

#: The three modules that carried the verbose spelling.
VERBOSE_FILES = ("env.py", "fhs.py", "hierarchy.py")

#: The three modules whose grant line was the bare ``License: GPL-3.0``.
BARE_FILES = ("config.py", "package.py", "var.py")

#: The two package ``__init__`` files that used a prose header.
PROSE_INITS = ("__init__.py", "installers/__init__.py")

#: The fail-closed declarations the real scanner accepts (legal/licenses.py).
SCANNER_MARKERS = (
    "GNU General Public License as published by\n# the Free Software Foundation, either version 3",
    "License: GPL-3.0",
    "SPDX-License-Identifier: GPL-3.0",
    "SPDX-License-Identifier: GPL-3.0-or-later",
)


def _read(rel: str) -> str:
    """Read without newline translation (``opt/`` is CRLF on disk)."""
    with open(OPT / rel, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


class TestOptLicenseHeaders(unittest.TestCase):
    """Every ``opt/`` module carries the H7 canonical short form."""

    def test_opt_has_the_expected_modules(self):
        self.assertEqual(len(ALL_FILES), 15, f"expected 15 modules, got {ALL_FILES}")
        for want in ("__init__.py", "config.py", "manager.py", "installers/web_server.py"):
            self.assertIn(want, ALL_FILES)

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
                self.assertNotIn(VERBOSE, _read(rel), f"{rel} still uses 'Version 3'")
                self.assertNotIn(
                    "General Public License Version 3)",
                    _read(rel),
                    f"{rel} still mentions the verbose spelling",
                )

    def test_no_british_license_declaration(self):
        """American ``License:`` only — the row's premise clause."""
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                self.assertNotIn("Licence:", _read(rel), f"{rel} uses the British spelling")

    def test_former_verbose_files_are_now_canonical(self):
        for rel in VERBOSE_FILES:
            with self.subTest(module=rel):
                text = _read(rel)
                self.assertIn(CANONICAL, text)
                self.assertNotIn(VERBOSE, text)

    def test_former_bare_files_are_now_canonical(self):
        """The bare grant line was expanded to the canonical short form."""
        for rel in BARE_FILES:
            with self.subTest(module=rel):
                text = _read(rel)
                self.assertIn(CANONICAL, text)
                self.assertNotIn("\nLicense: GPL-3.0\n", text, f"{rel} still bare")

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


class TestOptGplBlock(unittest.TestCase):
    """Pin the fact that contradicts the row's "no header at all" clause."""

    def test_gpl_block_is_the_first_thing_in_every_module(self):
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                self.assertTrue(
                    _read(rel).startswith(GPL_FIRST_LINE),
                    f"{rel} does not open with the canonical GPL comment block",
                )

    def test_prose_inits_now_carry_the_block(self):
        """The two files the row missed: they used a prose header.

        ``scan_directory("opt")`` reported them MISSING before the fix, so
        this is the one clause of the row that was understated, not overstated.
        """
        for rel in PROSE_INITS:
            with self.subTest(module=rel):
                text = _read(rel)
                self.assertTrue(
                    text.startswith(GPL_FIRST_LINE),
                    f"{rel} still opens with a prose header",
                )
                self.assertIn("# GPL-3.0 — see LICENSE and README", text)
                # the original prose comment must survive *below* the block
                self.assertGreater(text.index("# GPL-3.0 — see LICENSE"), 0)


class TestOptFutureAnnotations(unittest.TestCase):
    """``from __future__ import annotations`` is the first post-docstring stmt."""

    def test_every_module_declares_future_annotations(self):
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                self.assertIn(
                    "from __future__ import annotations",
                    _read(rel),
                    f"{rel} lacks the __future__ import",
                )

    def test_future_import_is_the_first_statement_after_the_docstring(self):
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                tree = ast.parse(_read(rel))
                self.assertGreaterEqual(len(tree.body), 2, f"{rel}: too few statements")
                stmt = tree.body[1]
                self.assertIsInstance(
                    stmt, ast.ImportFrom, f"{rel}: {type(stmt).__name__} after docstring"
                )
                self.assertEqual(stmt.module, "__future__", f"{rel}: not __future__")
                self.assertEqual(
                    stmt.names[0].name, "annotations", f"{rel}: wrong future name"
                )


class TestOptScanner(unittest.TestCase):
    """The real fail-closed audit must keep accepting all fifteen modules."""

    def test_fail_closed_scanner_accepts_every_module(self):
        from legal.licenses import LicenseManager

        result = LicenseManager.scan_directory(OPT)
        self.assertEqual(result.missing_license_files, [], "a module is no longer recognised")
        self.assertTrue(result.is_fully_compliant)
        self.assertEqual(result.total_files_scanned, 15)

    def test_scanner_markers_cover_the_canonical_line(self):
        """Sanity: the canonical line contains a marker the scanner accepts."""
        self.assertTrue(
            any(marker in CANONICAL for marker in SCANNER_MARKERS),
            "canonical line must be scanner-recognisable",
        )

    def test_line_endings_stay_crlf(self):
        """No lone LFs: the package is CRLF on disk and must stay so."""
        for rel in ALL_FILES:
            with self.subTest(module=rel):
                text = _read(rel)
                self.assertEqual(text.count("\n"), text.count("\r\n"), f"{rel}: mixed endings")


if __name__ == "__main__":
    unittest.main()
