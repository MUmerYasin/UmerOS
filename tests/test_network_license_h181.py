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

"""H181 tests — ``network/`` carries the H7 canonical license trailer.

The standard flagged ``network/`` (💭 H181): "no license headers in any of the
6 files ... and ``__init__.py`` lacks ``from __future__ import annotations``."

Drift-recon corrected the premise, as it did for ``mnt/`` (H176):

* **The "no license headers at all" clause is stale.** All six modules already
  carry the canonical GPLv3 comment block, which is *declaration form #1* of
  ``legal/licenses.py``'s fail-closed audit. ``scan_directory("network")``
  already reported 6/6 compliant before any change — so nothing here was
  invisible to the scanner either.
* **What genuinely was missing** is the per-file baseline trailer every other
  package carries: the H7 canonical short line
  ``License: GPL-3.0 (GNU General Public License v3)`` (not the verbose
  ``... Version 3`` spelling) plus ``Author:  Umer OS Project``, sitting at
  the end of the module docstring.
* **``__init__.py`` genuinely lacked ``from __future__ import annotations``**
  — it was the only module in the tree's package without it (0 occurrences,
  while all five sibling modules had it).

These tests pin the *code facts*: docstring contents, the position of the
first statement, and the real scanner's verdict.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NETWORK = ROOT / "network"

#: H7 canonical short form used repo-wide (American "License", "v3").
CANONICAL = "License: GPL-3.0 (GNU General Public License v3)"
#: The verbose form no module may use.
VERBOSE = "License: GPL-3.0 (GNU General Public License Version 3)"
#: Canonical author trailer (note: two spaces after the colon).
AUTHOR = "Author:  Umer OS Project"

#: All six modules of the package.
ALL_SIX = (
    "__init__.py",
    "dns_resolver.py",
    "http_client.py",
    "network_stack.py",
    "tcp_server.py",
    "vpn_tunnel.py",
)

#: The fail-closed declarations the real scanner accepts (legal/licenses.py).
SCANNER_MARKERS = (
    "GNU General Public License as published by\n# the Free Software Foundation, either version 3",
    "License: GPL-3.0",
    "SPDX-License-Identifier: GPL-3.0",
    "SPDX-License-Identifier: GPL-3.0-or-later",
)

#: First line of the canonical GPLv3 comment block.
GPL_FIRST_LINE = "# This program is free software: you can redistribute it and/or modify"


def _read(name: str) -> str:
    """Read without newline translation (network/ is CRLF on disk)."""
    with open(NETWORK / name, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _docstring_end(name: str) -> int:
    """Line number the module docstring ends on (1-based)."""
    tree = ast.parse(_read(name))
    node = tree.body[0]
    assert isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    assert isinstance(node.value.value, str)
    return node.end_lineno


class TestNetworkLicenseTrailers(unittest.TestCase):
    """Every ``network/`` module carries the H7 canonical trailer."""

    def test_network_has_the_expected_modules(self):
        names = {p.name for p in NETWORK.glob("*.py")}
        for want in ALL_SIX:
            self.assertIn(want, names, f"{want} missing from network/")

    def test_every_module_carries_the_canonical_line(self):
        for name in ALL_SIX:
            with self.subTest(module=name):
                self.assertIn(
                    CANONICAL,
                    _read(name),
                    f"{name} does not carry the canonical H7 line",
                )

    def test_every_module_carries_the_author_trailer(self):
        for name in ALL_SIX:
            with self.subTest(module=name):
                self.assertIn(
                    AUTHOR,
                    _read(name),
                    f"{name} lacks the 'Author:  Umer OS Project' trailer",
                )

    def test_no_verbose_license_line(self):
        """The verbose ``Version 3`` spelling must not appear anywhere."""
        for name in ALL_SIX:
            with self.subTest(module=name):
                self.assertNotIn(
                    VERBOSE,
                    _read(name),
                    f"{name} still carries the verbose 'Version 3' form",
                )

    def test_no_british_license_declaration(self):
        """American ``License:`` only — no British ``Licence:``."""
        for name in ALL_SIX:
            with self.subTest(module=name):
                self.assertNotIn(
                    "Licence:",
                    _read(name),
                    f"{name} uses the British spelling",
                )

    def test_trailer_sits_at_the_end_of_the_module_docstring(self):
        """Placement is the invariant, not mere presence of the string."""
        for name in ALL_SIX:
            with self.subTest(module=name):
                tree = ast.parse(_read(name))
                doc = tree.body[0].value.value
                self.assertTrue(
                    doc.rstrip("\r\n").endswith(CANONICAL),
                    f"{name}: license line is not the last thing in the docstring",
                )
                self.assertIn(AUTHOR, doc, f"{name}: trailer not inside docstring")


class TestNetworkGplBlock(unittest.TestCase):
    """Pin the fact that *contradicts* the standard's stale clause."""

    def test_gpl_block_is_the_first_thing_in_every_module(self):
        """The stale clause said 'no license headers at all' — false."""
        for name in ALL_SIX:
            with self.subTest(module=name):
                self.assertTrue(
                    _read(name).startswith(GPL_FIRST_LINE),
                    f"{name} does not open with the canonical GPL comment block",
                )

    def test_gpl_block_declares_version_3(self):
        for name in ALL_SIX:
            with self.subTest(module=name):
                head = _read(name)[:2048]
                self.assertIn(
                    "Free Software Foundation, either version 3",
                    head,
                    f"{name}: no GPLv3 declaration in the first 2KB",
                )


class TestNetworkFutureAnnotations(unittest.TestCase):
    """``from __future__ import annotations`` is the first post-docstring stmt."""

    def test_every_module_declares_future_annotations(self):
        for name in ALL_SIX:
            with self.subTest(module=name):
                self.assertIn(
                    "from __future__ import annotations",
                    _read(name),
                    f"{name} lacks the __future__ import",
                )

    def test_future_import_is_the_first_statement_after_the_docstring(self):
        """Position matters: it must precede every other statement."""
        for name in ALL_SIX:
            with self.subTest(module=name):
                tree = ast.parse(_read(name))
                self.assertGreaterEqual(len(tree.body), 2, f"{name}: too few statements")
                stmt = tree.body[1]
                self.assertIsInstance(
                    stmt,
                    ast.ImportFrom,
                    f"{name}: statement after docstring is {type(stmt).__name__}",
                )
                self.assertEqual(stmt.module, "__future__", f"{name}: not __future__")
                self.assertEqual(
                    stmt.names[0].name, "annotations", f"{name}: wrong future name"
                )

    def test_init_docstring_is_multi_line_now(self):
        """``__init__`` used to be a single-line docstring."""
        tree = ast.parse(_read("__init__.py"))
        doc = tree.body[0]
        self.assertGreater(
            doc.end_lineno,
            doc.lineno,
            "__init__.py docstring is still a single line",
        )
        self.assertIn(AUTHOR, doc.value.value)
        self.assertTrue(doc.value.value.rstrip("\r\n").endswith(CANONICAL))


class TestNetworkScanner(unittest.TestCase):
    """The real fail-closed audit must keep accepting all six modules."""

    def test_fail_closed_scanner_accepts_every_module(self):
        from legal.licenses import LicenseManager

        result = LicenseManager.scan_directory(NETWORK)
        self.assertEqual(
            result.missing_license_files,
            [],
            "the real scanner no longer recognises a network/ module",
        )
        self.assertTrue(result.is_fully_compliant)
        # 6 original modules + network/softbus/ (__init__, discovery, session),
        # added externally after H181 closed this folder; the three new modules
        # carry the canonical GPL comment block (declaration form #1), so the
        # scanner accepts them - only the count moved.  They are LF, not CRLF,
        # and carry no Author/License trailer, so ALL_SIX above still pins the
        # original six for the trailer/CRLF invariants.
        self.assertEqual(result.total_files_scanned, 9)

    def test_scanner_markers_cover_the_canonical_line(self):
        """Sanity: the canonical line contains a marker the scanner accepts."""
        self.assertTrue(
            any(marker in CANONICAL for marker in SCANNER_MARKERS),
            "canonical line must be scanner-recognisable",
        )

    def test_line_endings_stay_crlf(self):
        """No lone LFs: the package is CRLF on disk and must stay so."""
        for name in ALL_SIX:
            with self.subTest(module=name):
                text = _read(name)
                self.assertEqual(
                    text.count("\n"),
                    text.count("\r\n"),
                    f"{name} has mixed line endings",
                )


if __name__ == "__main__":
    unittest.main()
