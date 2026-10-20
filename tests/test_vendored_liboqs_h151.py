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

"""H151 tests — the vendored ``liboqs/`` submodule is declared and pinned.

The standard flagged ``liboqs/`` as an **unpinned** vendored OQS C library with
no ``.gitmodules`` (so it could silently drift) and an MIT license said to
conflict with the adopted H7 -> GPL-3.0 canonical.

Drift-recon refined that premise:

* The root index *did* carry a gitlink (mode ``160000``) pinned to commit
  ``5a1a854b0dc9f2141bdc771c555ee60c37950183`` (tag ``0.16.0``), but there was
  **no ``.gitmodules``** file declaring it -> an *undeclared* submodule that a
  fresh clone could not fetch.  That is the real gap, now fixed by
  ``.gitmodules``.
* MIT is a permissive, **GPL-3.0-compatible** license, so there is no license
  conflict: the vendored library keeps its own MIT terms and is intentionally
  excluded from the GPL-3.0 header audit in ``legal/licenses.py``.

These tests pin the declaration, the recorded provenance, and the license
compatibility rationale.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GITMODULES = ROOT / ".gitmodules"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
LIBOQS = ROOT / "liboqs"
LIBOQS_LICENSE = LIBOQS / "LICENSE.txt"
LICENSE_AUDITOR = ROOT / "legal" / "licenses.py"

PIN_COMMIT = "5a1a854b0dc9f2141bdc771c555ee60c37950183"
PIN_TAG = "0.16.0"
OQS_URL = "https://github.com/open-quantum-safe/liboqs"


def _git(*args: str) -> str:
    """Run a git command in ROOT; raises on failure."""
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


class TestGitmodulesDeclaration(unittest.TestCase):
    """``.gitmodules`` declares the ``liboqs`` submodule with the OQS upstream."""

    def test_gitmodules_exists(self):
        self.assertTrue(GITMODULES.is_file(), ".gitmodules is missing at repo root")

    def test_declares_liboqs_submodule(self):
        text = GITMODULES.read_text(encoding="utf-8")
        self.assertIn('[submodule "liboqs"]', text)
        self.assertIn("path = liboqs", text)

    def test_declares_oqs_upstream(self):
        text = GITMODULES.read_text(encoding="utf-8")
        self.assertIn(f"url = {OQS_URL}.git", text)

    def test_records_the_pinned_commit(self):
        # The pin must be discoverable from the declaration (not just the index).
        self.assertIn(PIN_COMMIT, GITMODULES.read_text(encoding="utf-8"))


class TestThirdPartyNotice(unittest.TestCase):
    """``THIRD_PARTY_NOTICES.md`` records provenance + license compatibility."""

    def test_notice_exists(self):
        self.assertTrue(NOTICES.is_file(), "THIRD_PARTY_NOTICES.md is missing")

    def test_records_provenance(self):
        text = NOTICES.read_text(encoding="utf-8")
        self.assertIn(OQS_URL, text)
        self.assertIn(PIN_COMMIT, text)
        self.assertIn(PIN_TAG, text)

    def test_records_mit_and_compatibility(self):
        text = NOTICES.read_text(encoding="utf-8")
        self.assertIn("MIT", text)
        self.assertIn("GPL-3.0-compatible", text)

    def test_does_not_claim_relicensing(self):
        # The vendored library keeps its MIT license; the notice must say so.
        text = NOTICES.read_text(encoding="utf-8")
        self.assertIn("**not** rewritten to GPL-3.0", text)


class TestVendoredLicense(unittest.TestCase):
    """The vendored library keeps its own MIT license (not relicensed)."""

    def test_liboqs_license_is_mit(self):
        self.assertTrue(LIBOQS_LICENSE.is_file(), "liboqs/LICENSE.txt is missing")
        self.assertIn("MIT license", LIBOQS_LICENSE.read_text(encoding="utf-8"))


class TestLicenseAuditExcludesThirdParty(unittest.TestCase):
    """The GPL-3.0 header audit deliberately skips the vendored library."""

    def test_licenses_py_skips_liboqs(self):
        src = LICENSE_AUDITOR.read_text(encoding="utf-8")
        self.assertIn('"liboqs"', src)
        self.assertIn('"node_modules"', src)  # the third-party skip set


@unittest.skipUnless(shutil.which("git"), "git not available")
class TestGitIndexPin(unittest.TestCase):
    """The committed gitlink matches the declared pin (best-effort, needs git)."""

    def test_gitlink_is_pinned_commit(self):
        try:
            out = _git("ls-tree", "HEAD", "liboqs")
        except subprocess.CalledProcessError as exc:  # pragma: no cover - env dependent
            self.skipTest(f"git ls-tree unavailable: {exc}")
        self.assertIn("160000", out)
        self.assertIn(PIN_COMMIT, out)

    def test_nested_remote_matches_declared_url(self):
        nested = LIBOQS / ".git"
        if not nested.exists():
            self.skipTest("liboqs/ is not checked out")
        try:
            url = _git("-C", "liboqs", "remote", "get-url", "origin").strip()
        except subprocess.CalledProcessError as exc:  # pragma: no cover - env dependent
            self.skipTest(f"nested remote unavailable: {exc}")
        self.assertTrue(url.rstrip("/").endswith("open-quantum-safe/liboqs.git") or url.rstrip("/").endswith("open-quantum-safe/liboqs"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
