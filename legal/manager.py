"""
UmerOS /legal — Master Legal, Compliance & Safety Coordinator
============================================================

Central manager for disclaimers, user consent audit trails, open-source
licensing compliance, contributors, donations, and pre-execution safety checks.

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from consent import ConsentManager, ConsentRecord
from contributors import ContributorRegistry
from disclaimer import DisclaimerNotice, DisclaimerRegistry, RiskLevel
from donations import DonationsManager
from licenses import LicenseManager, LicenseScanResult
from maintainers import MaintainerRegistry
from safety_check import SafetyCheckResult, SafetyChecker

log = logging.getLogger("UmerOS.Legal.Manager")


class LegalManager:
    """Master coordinator for all legal, compliance, and safety systems."""

    def __init__(self, ledger_path: Optional[Path | str] = None) -> None:
        self.disclaimers = DisclaimerRegistry
        self.consent = ConsentManager(ledger_path=ledger_path)
        self.contributors = ContributorRegistry()
        self.donations = DonationsManager()
        self.licenses = LicenseManager()
        self.safety = SafetyChecker()
        self.maintainers = MaintainerRegistry()

    def audit_system_compliance(self, project_root: Path | str) -> Dict[str, Any]:
        """
        Runs comprehensive legal, license, and consent compliance audit across UmerOS.
        """
        lic_scan = self.licenses.scan_directory(project_root)
        consents = self.consent.list_consents()
        contribs = self.contributors.list_contributors()

        has_general_consent = self.consent.has_consented("general")

        return {
            "project_root": str(project_root),
            "has_general_consent": has_general_consent,
            "recorded_consents_count": len(consents),
            "total_contributors": len(contribs),
            "license_compliance": lic_scan.summary(),
            "is_fully_compliant": lic_scan.is_fully_compliant,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Returns statistics of legal records, contributors, and notices."""
        return {
            "disclaimer_notices": len(self.disclaimers.list_notices()),
            "recorded_consents": len(self.consent.list_consents()),
            "contributors_count": len(self.contributors.list_contributors()),
            "maintainers_count": len(self.maintainers.list_all()),
            "funding_channels": len(self.donations.get_funding_channels()),
        }


# ── Global Default Helper Functions ──────────────────────────────────────

_global_legal_mgr: Optional[LegalManager] = None


def get_default_legal_manager() -> LegalManager:
    global _global_legal_mgr
    if _global_legal_mgr is None:
        _global_legal_mgr = LegalManager()
    return _global_legal_mgr
