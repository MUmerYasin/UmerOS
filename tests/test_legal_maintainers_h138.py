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

"""H138 tests — maintainer key fingerprints are honest placeholders.

The standard flagged ``legal/maintainers.py``: the maintainer "cryptographic"
PQC/PGP fingerprints were hardcoded static literals (``DILITHIUM5:…``,
``4A9F …``) that were not derived from real keys, yet ``cli.py`` printed them as
real "PQC Key" / "PGP Key" (overstated-claim family).

No real key material exists in the repo, so H138 takes the standard's second
option: mark the values as ``PLACEHOLDER:``-prefixed placeholders, expose
``is_placeholder_fingerprint`` / ``key_fingerprints_are_placeholders``, and drop
the "verified / cryptographic" wording.
"""

import io
import contextlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAINT_SRC = ROOT / "legal" / "maintainers.py"

from legal.maintainers import (  # noqa: E402
    CORE_MAINTAINERS,
    MaintainerProfile,
    MaintainerRegistry,
    PLACEHOLDER_PREFIX,
    is_placeholder_fingerprint,
)


class TestPlaceholderMarking(unittest.TestCase):
    """Canonical fingerprints are explicitly marked as placeholders."""

    def test_canonical_fingerprints_are_prefixed(self):
        lead = MaintainerRegistry().get("MUmerYasin")
        self.assertIsNotNone(lead)
        self.assertTrue(lead.pqc_public_key_fingerprint.startswith(PLACEHOLDER_PREFIX))
        self.assertTrue(lead.pgp_fingerprint.startswith(PLACEHOLDER_PREFIX))

    def test_property_true_for_canonical(self):
        for m in CORE_MAINTAINERS:
            self.assertTrue(m.key_fingerprints_are_placeholders, m.name)

    def test_legacy_substring_preserved(self):
        lead = MaintainerRegistry().get("MUmerYasin")
        self.assertIn("DILITHIUM5", lead.pqc_public_key_fingerprint)

    def test_helper_semantics(self):
        self.assertTrue(is_placeholder_fingerprint(""))
        self.assertTrue(is_placeholder_fingerprint(PLACEHOLDER_PREFIX + "X"))
        self.assertFalse(is_placeholder_fingerprint("DILITHIUM5:deadbeef"))

    def test_real_looking_profile_is_not_a_placeholder(self):
        real = MaintainerProfile(name="R", handle="r", email="r@x", role="Dev",
                                 pqc_public_key_fingerprint="DILITHIUM5:deadbeef",
                                 pgp_fingerprint="ABCD 1234", bio="")
        self.assertFalse(real.key_fingerprints_are_placeholders)


class TestCliHonesty(unittest.TestCase):
    """The CLI surfaces the placeholder status, not a false 'key' claim."""

    def test_cli_marks_placeholders(self):
        from legal.cli import main as cli_main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli_main(["maintainers"])
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn(PLACEHOLDER_PREFIX, out)
        self.assertIn("placeholders", out)
        self.assertIn("not trust anchors", out)


class TestSourceInvariants(unittest.TestCase):
    """Pin code facts, never cosmetic tags."""

    def test_placeholder_prefix_defined(self):
        src = MAINT_SRC.read_text(encoding="utf-8")
        self.assertIn('PLACEHOLDER_PREFIX = "PLACEHOLDER:"', src)
        self.assertIn("def is_placeholder_fingerprint", src)

    def test_overstated_wording_removed(self):
        src = MAINT_SRC.read_text(encoding="utf-8")
        self.assertNotIn("cryptographic identities", src)
        self.assertNotIn("verified UmerOS subsystem maintainer", src)
        self.assertNotIn("trusted core subsystem maintainers", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
