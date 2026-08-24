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
Comprehensive Test Suite for UmerOS /legal Subsystem
====================================================

Verifies disclaimers, user consent gate, contributors, donations,
license compliance, maintainers, and safety checks.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add project root and legal folder to sys.path
_leg_dir = Path(__file__).resolve().parent
_root_dir = _leg_dir.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))
if str(_leg_dir) not in sys.path:
    sys.path.insert(0, str(_leg_dir))


def test_imports() -> bool:
    print("=" * 60)
    print("Test 1: Module Imports")
    print("=" * 60)
    try:
        import legal
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
        print("[OK] All /legal modules and classes imported successfully.")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return False


def test_disclaimers() -> bool:
    print("\n" + "=" * 60)
    print("Test 2: Disclaimer Registry & Liability Notices")
    print("=" * 60)
    from legal.disclaimer import DisclaimerRegistry, RiskLevel

    notices = DisclaimerRegistry.list_notices()
    assert "general" in notices
    assert "tldp" in notices
    assert "installer" in notices
    assert "kernel_hal" in notices

    gen = DisclaimerRegistry.get_notice("general")
    assert "LEGAL LIABILITY WAIVER" in gen.full_text
    assert gen.backup_recommended

    hal = DisclaimerRegistry.get_notice("kernel_hal")
    assert hal.risk_level == RiskLevel.CRITICAL

    print(f"[OK] Disclaimer registry ({len(notices)} notices) verified.")
    return True


def test_consent_gate() -> bool:
    print("\n" + "=" * 60)
    print("Test 3: Consent Gate & Cryptographic Ledger")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = (Path(tmpdir) / "consent_ledger.json").resolve()
        from legal.consent import ConsentManager

        mgr = ConsentManager(ledger_path=ledger_path)

        assert not mgr.has_consented("installer")

        # Rejection on invalid response
        try:
            mgr.grant_consent("installer", user_response="maybe")
            assert False, "Should reject consent without 'I AGREE'"
        except ValueError:
            pass

        # Grant consent
        rec = mgr.grant_consent("installer", user_response="I AGREE")
        assert rec.status == "GRANTED"
        assert len(rec.consent_token) == 64
        assert mgr.has_consented("installer")

        # Persistence check
        assert ledger_path.exists()
        mgr2 = ConsentManager(ledger_path=ledger_path)
        assert mgr2.has_consented("installer")

        # Revocation
        assert mgr2.revoke_consent("installer")
        assert not mgr2.has_consented("installer")

        print("[OK] Consent gate ('I AGREE'), ledger persistence, and revocation verified.")
        return True


def test_contributors() -> bool:
    print("\n" + "=" * 60)
    print("Test 4: Contributors Roster & DCO Certification")
    print("=" * 60)
    from legal.contributors import ContributorRegistry

    reg = ContributorRegistry()
    roster = reg.list_contributors()
    assert len(roster) >= 3

    assert reg.verify_dco("Muhammad Umer Yasin (MUmerYasin)")
    assert reg.verify_dco("The Linux Documentation Project (TLDP)")

    # Add community contributor
    reg.add_contributor("Jane Doe", role="Tester", contributions=["Quantum unit tests"])
    assert reg.get_contributor("Jane Doe") is not None

    md = reg.generate_acknowledgements_md()
    assert "# UmerOS Project Contributors" in md

    print(f"[OK] Contributors roster ({len(roster)} entries) and DCO checks verified.")
    return True


def test_donations() -> bool:
    print("\n" + "=" * 60)
    print("Test 5: Donations & Sustainability Engine")
    print("=" * 60)
    from legal.donations import DonationsManager, DonationTier

    mgr = DonationsManager()
    channels = mgr.get_funding_channels()
    assert "github_sponsors" in channels

    # Add donation
    d1 = mgr.add_donation("Open Tech Foundation", 15000, public_note="For quantum research")
    assert d1.tier == DonationTier.PLATINUM

    d2 = mgr.add_donation("Community Member", 50, public_note="Keep it up!")
    assert d2.tier == DonationTier.COMMUNITY

    assert len(mgr.list_donations()) == 2
    md = mgr.generate_sponsors_md()
    assert "Open Tech Foundation" in md

    print("[OK] Donations tiers, funding channels, and sponsor wall verified.")
    return True


def test_licenses_and_maintainers() -> bool:
    print("\n" + "=" * 60)
    print("Test 6: License Manager & Maintainer Profiles")
    print("=" * 60)
    from legal.licenses import LicenseManager
    from legal.maintainers import MaintainerRegistry

    # License text
    gpl = LicenseManager.get_license_text("GPL-3.0")
    assert "GNU General Public License" in gpl

    # Maintainers
    m_reg = MaintainerRegistry()
    maintainers = m_reg.list_all()
    assert len(maintainers) >= 1

    lead = m_reg.get("MUmerYasin")
    assert lead is not None
    assert "DILITHIUM5" in lead.pqc_public_key_fingerprint

    print("[OK] License manager and maintainer PQC profiles verified.")
    return True


def test_safety_check() -> bool:
    print("\n" + "=" * 60)
    print("Test 7: Pre-Execution Safety & Checkpoint Backup")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir) / "critical_data"
        target_dir.mkdir()
        (target_dir / "config.sys").write_text("critical boot config", encoding="utf-8")

        from legal.safety_check import SafetyChecker
        from legal.disclaimer import RiskLevel

        res = SafetyChecker.verify_safety(
            operation_name="flash_firmware",
            risk_level=RiskLevel.HIGH,
            target_path=target_dir,
            create_backup=True,
        )
        assert res.is_safe
        assert res.backup_path is not None
        assert Path(res.backup_path).exists()
        assert (Path(res.backup_path) / "config.sys").exists()

        print("[OK] Pre-execution safety check and snapshot backup verified.")
        return True


def test_legal_manager_and_cli() -> bool:
    print("\n" + "=" * 60)
    print("Test 8: LegalManager & CLI Execution (legal_ctl)")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = Path(tmpdir) / "ledger.json"
        from legal.manager import LegalManager
        from legal.cli import main as cli_main

        mgr = LegalManager(ledger_path=ledger)
        s = mgr.get_summary()
        assert s["disclaimer_notices"] >= 4

        # CLI tests
        assert cli_main(["summary"]) == 0
        assert cli_main(["disclaimer", "general"]) == 0
        assert cli_main(["contributors"]) == 0
        assert cli_main(["donations"]) == 0
        assert cli_main(["maintainers"]) == 0
        assert cli_main(["consent", "general", "--user", "test_user"]) == 0
        assert cli_main(["verify", "general"]) == 0

        print("[OK] LegalManager master coordinator and CLI commands executed successfully.")
        return True


def run_all_tests() -> bool:
    tests = [
        test_imports,
        test_disclaimers,
        test_consent_gate,
        test_contributors,
        test_donations,
        test_licenses_and_maintainers,
        test_safety_check,
        test_legal_manager_and_cli,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            if t():
                passed += 1
            else:
                failed += 1
        except Exception as ex:
            print(f"[FAIL] Exception in {t.__name__}: {ex}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} PASSED, {failed} FAILED (Total: {len(tests)})")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
