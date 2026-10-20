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

"""H176 tests — ``mnt/`` license headers use the H7 canonical GPL-3.0 form.

The standard flagged ``mnt/`` as having license strays (🟡 H176): "``mount_ops.py``
/``fstab.py``/``mount_point.py``/``user_mount.py``/``audit.py``/``validation.py``
say ``Licence: GPL-3.0 (GNU General Public License Version 3)`` (British
spelling + space, so a naive ``Apache-2.0`` grep misses them); ``__init__.py``
has no header."

Drift-recon corrected the premise. Two parts of it were stale:

* **No British spelling existed in ``mnt/``** — all six used the American
  ``License:``. The one genuine British ``Licence:`` stray in the tree is
  ``legal/licenses.py`` (its own header), which lives in the already-closed
  ``legal/`` folder and is therefore out of scope for this item.
* **Nothing was invisible to the scanner** — ``legal/licenses.py``'s
  fail-closed audit accepts ``"License: GPL-3.0"`` as a *substring*, so the
  verbose ``... (GNU General Public License Version 3)`` form was already
  recognised, and ``__init__.py`` was accepted via the canonical GPL
  comment block. ``scan_directory("mnt")`` reported 7/7 compliant before
  any change.

What *was* genuinely wrong is real nonetheless, and is what these tests
pin: the six modules used the **verbose** ``Version 3`` spelling where the
whole rest of the repository baseline (``media/`` included) uses the
canonical short form ``License: GPL-3.0 (GNU General Public License v3)``,
and ``mnt/__init__.py`` was the only package ``__init__`` without the
``Author:``/``License:`` trailer its siblings carry.

This is the ``mnt/`` analogue of the already-completed ``media/`` fix (H160).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MNT = ROOT / "mnt"

#: H7 canonical short form used repo-wide.
CANONICAL = "License: GPL-3.0 (GNU General Public License v3)"
#: The verbose form the six modules used to carry.
VERBOSE = "License: GPL-3.0 (GNU General Public License Version 3)"

ALL_SEVEN = (
    "__init__.py",
    "audit.py",
    "fstab.py",
    "mount_ops.py",
    "mount_point.py",
    "user_mount.py",
    "validation.py",
)

#: The six that carried the verbose line (``__init__`` had no line at all).
SIX_VERBOSE = (
    "audit.py",
    "fstab.py",
    "mount_ops.py",
    "mount_point.py",
    "user_mount.py",
    "validation.py",
)

#: The fail-closed declarations the real scanner accepts (legal/licenses.py).
SCANNER_MARKERS = (
    "GNU General Public License as published by\n# the Free Software Foundation, either version 3",
    "License: GPL-3.0",
    "SPDX-License-Identifier: GPL-3.0",
    "SPDX-License-Identifier: GPL-3.0-or-later",
)


class TestMntLicenseHeaders(unittest.TestCase):
    """Every ``mnt/`` module carries the H7 canonical short form."""

    def test_mnt_has_the_expected_modules(self):
        names = {p.name for p in MNT.glob("*.py")}
        for want in ALL_SEVEN:
            self.assertIn(want, names, f"{want} missing from mnt/")

    def test_every_module_carries_the_canonical_line(self):
        for name in ALL_SEVEN:
            with self.subTest(module=name):
                text = (MNT / name).read_text(encoding="utf-8")
                self.assertIn(
                    CANONICAL,
                    text,
                    f"{name} does not carry the canonical H7 line",
                )

    def test_no_verbose_license_line(self):
        for name in ALL_SEVEN:
            with self.subTest(module=name):
                text = (MNT / name).read_text(encoding="utf-8")
                self.assertNotIn(
                    VERBOSE,
                    text,
                    f"{name} still carries the verbose 'Version 3' form",
                )

    def test_no_british_license_declaration(self):
        """No ``Licence:`` anywhere in ``mnt/`` (the standard's wording)."""
        for name in ALL_SEVEN:
            text = (MNT / name).read_text(encoding="utf-8")
            self.assertNotIn(
                "Licence:", text, f"{name} uses the British spelling"
            )

    def test_init_has_author_trailer(self):
        """``__init__`` must match its siblings (e.g. ``media/__init__.py``)."""
        text = (MNT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("Author:  Umer OS Project", text)

    def test_init_carries_the_canonical_line(self):
        text = (MNT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn(CANONICAL, text)

    def test_six_former_verbose_files_are_now_canonical(self):
        for name in SIX_VERBOSE:
            with self.subTest(module=name):
                text = (MNT / name).read_text(encoding="utf-8")
                self.assertIn(CANONICAL, text)
                self.assertNotIn(VERBOSE, text)

    # -- the real scanner must still accept every file ----------------------

    def test_fail_closed_scanner_accepts_every_module(self):
        """`legal/licenses.py`'s audit must keep reporting 7/7 compliant."""
        from legal.licenses import LicenseManager

        result = LicenseManager.scan_directory(MNT)
        self.assertEqual(
            result.missing_license_files,
            [],
            "the real scanner no longer recognises a mnt/ module",
        )
        self.assertTrue(result.is_fully_compliant)

    def test_scanner_sees_the_canonical_line(self):
        """Sanity: the canonical form contains a marker the scanner accepts."""
        self.assertTrue(
            any(marker in CANONICAL for marker in SCANNER_MARKERS),
            "canonical line must be scanner-recognisable",
        )


if __name__ == "__main__":
    unittest.main()
