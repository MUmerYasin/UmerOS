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

"""H136 tests — the DCO status is an honest, fail-closed *declaration*.

The standard flagged ``legal/contributors.py``: ``verify_dco`` was decorative —
``dco_signed`` defaulted ``True`` and ``add_contributor`` never verified a real
DCO/CLA signature, so the "verification engine" just echoed a pre-set boolean
(overstated-claim family, cf. H51/H111/H132).

H136 renames the field to ``dco_flag`` and the query to ``has_dco_declaration``,
drops the "verification" wording, and makes the default **fail-closed** (a new
contributor is NOT assumed to have signed the DCO).  A legacy ``dco_signed``
property alias and a deprecated ``verify_dco`` alias preserve the API.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRIB_SRC = ROOT / "legal" / "contributors.py"

from legal.contributors import (  # noqa: E402
    CANONICAL_CONTRIBUTORS,
    ContributorRecord,
    ContributorRegistry,
    ContributorRole,
)

_FOUNDER = "Muhammad Umer Yasin (MUmerYasin)"
_TLDP = "The Linux Documentation Project (TLDP)"


class TestFailClosedDefault(unittest.TestCase):
    """A new contributor is NOT assumed to have accepted the DCO."""

    def test_record_default_is_false(self):
        rec = ContributorRecord(name="X", role=ContributorRole.COMMUNITY,
                                email_or_handle="", organization="I")
        self.assertFalse(rec.dco_flag)

    def test_add_contributor_default_is_false(self):
        reg = ContributorRegistry()
        rec = reg.add_contributor("Jane Doe", role="Tester")
        self.assertFalse(rec.dco_flag)
        self.assertFalse(reg.has_dco_declaration("Jane Doe"))

    def test_opt_in_declaration_is_honoured(self):
        reg = ContributorRegistry()
        reg.add_contributor("Bob", dco_flag=True)
        self.assertTrue(reg.has_dco_declaration("Bob"))

    def test_canonical_roster_declarations_preserved(self):
        reg = ContributorRegistry()
        self.assertTrue(reg.has_dco_declaration(_FOUNDER))
        self.assertTrue(reg.has_dco_declaration(_TLDP))
        # The canonical roster must set the flag explicitly, not rely on a default.
        for c in CANONICAL_CONTRIBUTORS:
            self.assertTrue(c.dco_flag, c.name)

    def test_unknown_contributor_is_false(self):
        self.assertFalse(ContributorRegistry().has_dco_declaration("nobody"))


class TestHonestNaming(unittest.TestCase):
    """The API reports a declaration, not a verification."""

    def test_query_method_reports_declaration(self):
        reg = ContributorRegistry()
        self.assertTrue(hasattr(reg, "has_dco_declaration"))
        self.assertFalse(reg.has_dco_declaration("Jane Doe"))

    def test_to_dict_uses_the_honest_field_name(self):
        rec = ContributorRecord(name="X", role=ContributorRole.COMMUNITY,
                                email_or_handle="", organization="I")
        d = rec.to_dict()
        self.assertIn("dco_flag", d)
        self.assertNotIn("dco_signed", d)

    def test_acknowledgements_no_longer_claim_certified(self):
        md = ContributorRegistry().generate_acknowledgements_md()
        self.assertIn("(DCO declared)", md)
        self.assertNotIn("(DCO Certified)", md)


class TestLegacyAliases(unittest.TestCase):
    """The old public surface still works but no longer over-claims."""

    def test_dco_signed_property_round_trips(self):
        rec = ContributorRecord(name="X", role=ContributorRole.COMMUNITY,
                                email_or_handle="", organization="I")
        self.assertFalse(rec.dco_signed)
        rec.dco_signed = True
        self.assertTrue(rec.dco_flag)
        self.assertTrue(rec.dco_signed)

    def test_verify_dco_alias_delegates(self):
        reg = ContributorRegistry()
        reg.add_contributor("Bob", dco_flag=True)
        self.assertTrue(reg.verify_dco("Bob"))
        self.assertFalse(reg.verify_dco("Jane Doe"))


class TestSourceInvariants(unittest.TestCase):
    """Pin code facts, never cosmetic tags."""

    def test_no_default_true(self):
        src = CONTRIB_SRC.read_text(encoding="utf-8")
        self.assertNotIn("dco_signed: bool = True", src)
        self.assertIn("dco_flag: bool = False", src)

    def test_overstated_wording_removed(self):
        src = CONTRIB_SRC.read_text(encoding="utf-8")
        self.assertNotIn("verification engine", src)
        self.assertNotIn("(DCO Certified)", src)

    def test_honest_query_present(self):
        src = CONTRIB_SRC.read_text(encoding="utf-8")
        self.assertIn("def has_dco_declaration", src)
        self.assertIn("dco_flag", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
