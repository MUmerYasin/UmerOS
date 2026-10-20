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

"""H160 tests — ``media/`` license headers use the H7 canonical GPL-3.0 form.

The standard flagged ``media/`` as having a license inconsistency (🟡 H160):
"5 modules carry the verbose ``Licence: GPL-3.0 (GNU General Public License
Version 3)`` and 7 files have no header at all".

Drift-recon corrected the counts: **23** ``media/**.py`` modules carried the
verbose ``License: GPL-3.0 (GNU General Public License Version 3)`` line (no
British ``Licence`` spelling existed), and **7** top-level modules had the GPL
comment block but **no docstring license line** — none were truly headerless.

These tests pin that every ``media/`` module uses the canonical short form
``License: GPL-3.0 (GNU General Public License v3)`` and carries no verbose
``Version 3`` line or British ``Licence`` declaration.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MEDIA = ROOT / "media"

CANONICAL = "License: GPL-3.0 (GNU General Public License v3)"
NON_CANONICAL = "License: GPL-3.0 (GNU General Public License Version 3)"

# The 7 modules that previously had the GPL comment block but no license line.
SEVEN = [
    "__init__.py", "auto_mount.py", "filesystem.py", "fstab.py",
    "mount_ops.py", "permissions.py", "udisks2.py",
]


def _media_py_files() -> list:
    return sorted(p for p in MEDIA.rglob("*.py") if p.is_file())


class TestCanonicalLicenseLine(unittest.TestCase):
    """Every media/ module uses the H7 short form, not the verbose one."""

    def test_no_verbose_license_line(self):
        offenders = [
            str(p.relative_to(ROOT))
            for p in _media_py_files()
            if NON_CANONICAL in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [], f"verbose 'Version 3' line in: {offenders}")

    def test_every_module_carries_the_canonical_line(self):
        missing = [
            str(p.relative_to(ROOT))
            for p in _media_py_files()
            if CANONICAL not in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(missing, [], f"missing canonical license line in: {missing}")

    def test_media_has_modules(self):
        # Guard against a silently-empty glob making the checks vacuous.
        self.assertGreaterEqual(len(_media_py_files()), 20)


class TestNoBritishLicenceDeclaration(unittest.TestCase):
    """No British ``Licence`` *license declaration* may appear (H7)."""

    def test_no_british_license_declaration(self):
        offenders = [
            str(p.relative_to(ROOT))
            for p in _media_py_files()
            if "Licence: GPL" in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [], f"British 'Licence: GPL' declaration in: {offenders}")


class TestPreviouslyHeaderlessModules(unittest.TestCase):
    """The 7 modules that lacked a docstring license line now carry the trailer."""

    def test_seven_now_have_the_trailer(self):
        for name in SEVEN:
            p = MEDIA / name
            text = p.read_text(encoding="utf-8")
            self.assertIn("Author:  Umer OS Project", text, name)
            self.assertIn(CANONICAL, text, name)

    def test_all_seven_exist(self):
        for name in SEVEN:
            self.assertTrue((MEDIA / name).is_file(), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
