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

"""
pytest test suite for UmerOS /legal subsystem.
"""

import sys
import tempfile
from pathlib import Path
import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from legal import (
    DisclaimerRegistry,
    RiskLevel,
    ConsentManager,
    ConsentRecord,
    ContributorRegistry,
    DonationsManager,
    LicenseManager,
    MaintainerRegistry,
    SafetyChecker,
    LegalManager,
)


def test_disclaimers():
    notices = DisclaimerRegistry.list_notices()
    assert "general" in notices
    assert "tldp" in notices
    assert "installer" in notices


def test_consent():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = Path(tmpdir) / "consent.json"
        mgr = ConsentManager(ledger_path=ledger)
        assert not mgr.has_consented("general")
        mgr.grant_consent("general", "I AGREE")
        assert mgr.has_consented("general")


def test_contributors():
    reg = ContributorRegistry()
    assert len(reg.list_all()) if hasattr(reg, "list_all") else len(reg.list_contributors()) >= 2


def test_donations():
    mgr = DonationsManager()
    d = mgr.add_donation("Anonymous", 100)
    assert d.amount_usd == 100


def test_safety_check():
    res = SafetyChecker.verify_safety("test_op", RiskLevel.SAFE)
    assert res.is_safe


def test_legal_manager():
    mgr = LegalManager()
    summary = mgr.get_summary()
    assert summary["disclaimer_notices"] >= 4
