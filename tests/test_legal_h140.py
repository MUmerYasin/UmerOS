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

"""H140 tests — pin the DCO assertions and the CI coverage of in-package suites.

The standard flagged ``legal/test_legal.py:120-121``: Test 4 was said to assert
``verify_dco("Antigravity AI / DeepMind Team")`` is True although that name is not
in the roster — so the test failed as written, and "no CI step exists to catch it".

Drift-recon: the broken assertion is **already gone** (the live test asserts the
real roster names).  The remaining, actionable part of the remedy — *run the
suite in CI* — was real: CI only collected ``tests/``, so the in-package
``test_*.py`` suites (incl. ``legal/test_legal.py``) were never executed.  H140
adds them to CI and fixes the one Windows-portability assertion in
``srv/test_srv.py`` that would otherwise make CI red.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEGAL_TEST = ROOT / "legal" / "test_legal.py"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
SRV_TEST = ROOT / "srv" / "test_srv.py"

from legal.contributors import ContributorRegistry  # noqa: E402


class TestDcoAssertionsUseRealNames(unittest.TestCase):
    """Test 4 must only assert names that are actually in the roster."""

    def test_no_antigravity_assertion(self):
        src = LEGAL_TEST.read_text(encoding="utf-8")
        self.assertNotIn("Antigravity", src)
        self.assertNotIn("DeepMind Team", src)

    def test_every_asserted_name_is_in_the_roster(self):
        src = LEGAL_TEST.read_text(encoding="utf-8")
        asserted = set(re.findall(r'(?:has_dco_declaration|verify_dco)\("([^"]+)"\)', src))
        added = set(re.findall(r'add_contributor\("([^"]+)"', src))
        self.assertTrue(asserted, "no DCO assertions found — parser drifted?")
        reg = ContributorRegistry()
        for name in sorted(asserted - added):
            self.assertIsNotNone(reg.get_contributor(name),
                                 f"{name!r} is asserted but is not in the roster")


class TestCiCollectsInPackageSuites(unittest.TestCase):
    """CI must execute the in-package test_*.py modules (H140 remedy clause)."""

    def test_ci_targets_include_in_package_dirs(self):
        yml = CI_YML.read_text(encoding="utf-8")
        m = re.search(r"python -m pytest ([^\n]*)", yml)
        self.assertIsNotNone(m, "no pytest invocation found in ci.yml")
        targets = m.group(1)
        for d in ("tests/", "legal/", "opt/", "sources/", "srv/", "tmp/"):
            self.assertIn(d, targets, f"CI does not collect {d}")

    def test_in_package_modules_exist(self):
        for rel in ("legal/test_legal.py", "opt/test_opt.py",
                    "sources/test_sources.py", "srv/test_srv.py", "tmp/test_tmp.py"):
            self.assertTrue((ROOT / rel).exists(), rel)


class TestSrvPathAssertionIsPortable(unittest.TestCase):
    """The srv persistence test compares resolved paths (Windows 8.3 short names)."""

    def test_srv_test_uses_resolved_comparison(self):
        src = SRV_TEST.read_text(encoding="utf-8")
        self.assertIn("Path(rec.base_path).resolve()", src)
        self.assertNotIn('assert rec.base_path == str(srv_root / "test_api")', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
