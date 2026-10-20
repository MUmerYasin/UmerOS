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

"""H149 tests — ``lib/`` license headers use the H7 canonical GPL-3.0 form.

The standard flagged ``lib/`` as the "largest Apache-2.0 cluster" (🟡 H149).
Drift-recon showed that premise is **stale** — every ``lib/`` module already
carries the canonical GPL-3.0 header block; the only real inconsistency was the
verbose ``License: GPL-3.0 (GNU General Public License Version 3)`` line (and the
same string in ``lib/README.md``), which H7 (session 39) normalized to the short
form ``License: GPL-3.0 (GNU General Public License v3)``.

These tests pin that every ``lib/`` module (and its README) uses the canonical
short form and carries no British ``Licence`` license declaration.  The
``Licence:`` field inside ``lib/firmware.py``'s WHENCE manifest is *firmware
metadata* (upstream WHENCE format), not a license declaration, and must be kept.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LIB = ROOT / "lib"

CANONICAL = "License: GPL-3.0 (GNU General Public License v3)"
NON_CANONICAL = "License: GPL-3.0 (GNU General Public License Version 3)"


def _lib_py_files() -> list[Path]:
    return sorted(p for p in LIB.rglob("*.py") if p.is_file())


def _lib_license_files() -> list[Path]:
    """Every file that must carry the canonical license line."""
    files = _lib_py_files()
    readme = LIB / "README.md"
    if readme.is_file():
        files.append(readme)
    return files


class TestCanonicalLicenseLine(unittest.TestCase):
    """Every lib/ module + README uses the H7 short form, not the verbose one."""

    def test_no_verbose_license_line_anywhere_in_lib(self):
        offenders = [
            str(p.relative_to(ROOT))
            for p in _lib_license_files()
            if NON_CANONICAL in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [], f"verbose 'Version 3' license line in: {offenders}")

    def test_every_module_carries_the_canonical_line(self):
        missing = [
            str(p.relative_to(ROOT))
            for p in _lib_license_files()
            if CANONICAL not in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(missing, [], f"missing canonical license line in: {missing}")

    def test_lib_has_modules(self):
        # Guard against a silently-empty glob making the checks vacuous.
        self.assertGreaterEqual(len(_lib_py_files()), 20)


class TestNoBritishLicenceDeclaration(unittest.TestCase):
    """No British ``Licence`` *license declaration* may reappear (H7)."""

    def test_no_british_license_declaration(self):
        offenders = [
            str(p.relative_to(ROOT))
            for p in _lib_py_files()
            if "Licence: GPL" in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [], f"British 'Licence: GPL' declaration in: {offenders}")


class TestFirmwareWhencePreserved(unittest.TestCase):
    """The WHENCE ``Licence:`` field is firmware metadata, not a license header."""

    def test_whence_licence_field_still_emitted(self):
        src = (LIB / "firmware.py").read_text(encoding="utf-8")
        # Upstream WHENCE format field must remain (do NOT "fix" this to License:).
        self.assertIn('lines.append(f"Licence: {blob.license.value}")', src)
        # ...while the module's own license line is canonical.
        self.assertIn(CANONICAL, src)
        self.assertNotIn(NON_CANONICAL, src)


class TestReadmeLine(unittest.TestCase):
    def test_readme_uses_canonical_line(self):
        readme = (LIB / "README.md").read_text(encoding="utf-8")
        self.assertIn(CANONICAL, readme)
        self.assertNotIn(NON_CANONICAL, readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
