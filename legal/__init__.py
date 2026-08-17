"""
UmerOS /legal — Legal, Disclaimer, Consent & Compliance Subsystem
================================================================

Implements legal liability disclaimers, user consent
verification gates, contributor attributions, donation
sponsorships, maintainer profiles,
open-source licensing compliance, and pre-execution safety checkpoints.

Modules:
--------
disclaimer   - DisclaimerNotice, DisclaimerRegistry, RiskLevel, UmerOS waivers
consent      - ConsentManager, ConsentRecord, ConsentGateError, 'I AGREE' validator
contributors - ContributorRegistry, ContributorRecord, DCO certification
donations    - DonationsManager, DonationRecord, DonationTier, funding channels
licenses     - LicenseManager, LicenseScanResult, multi-license auditor
maintainers  - MaintainerRegistry, MaintainerProfile, PQC & PGP signing keys
safety_check - SafetyChecker, SafetyCheckResult, pre-execution backup runner
manager      - LegalManager (master unified controller)
cli          - legal_ctl command-line controller

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import sys as _sys
from os import path as _p

_this_dir = _p.dirname(_p.abspath(__file__))
if _this_dir not in _sys.path:
    _sys.path.insert(0, _this_dir)

from disclaimer import (
    TLDP_DISCLAIMER_TEXT,
    UMEROS_MASTER_DISCLAIMER_TEXT,
    DisclaimerNotice,
    DisclaimerRegistry,
    RiskLevel,
)
from consent import (
    ConsentGateError,
    ConsentManager,
    ConsentRecord,
    get_machine_fingerprint,
)
from contributors import (
    CANONICAL_CONTRIBUTORS,
    ContributorRecord,
    ContributorRegistry,
    ContributorRole,
)
from donations import (
    DonationRecord,
    DonationsManager,
    DonationTier,
)
from licenses import (
    LicenseManager,
    LicenseScanResult,
)
from maintainers import (
    CORE_MAINTAINERS,
    MaintainerProfile,
    MaintainerRegistry,
)
from safety_check import (
    SafetyChecker,
    SafetyCheckResult,
)
from manager import (
    LegalManager,
    get_default_legal_manager,
)

__version__ = "1.0.0"

__all__ = [
    # Disclaimers
    "TLDP_DISCLAIMER_TEXT",
    "UMEROS_MASTER_DISCLAIMER_TEXT",
    "DisclaimerNotice",
    "DisclaimerRegistry",
    "RiskLevel",
    # Consent
    "ConsentRecord",
    "ConsentManager",
    "ConsentGateError",
    "get_machine_fingerprint",
    # Contributors
    "ContributorRole",
    "ContributorRecord",
    "ContributorRegistry",
    "CANONICAL_CONTRIBUTORS",
    # Donations
    "DonationTier",
    "DonationRecord",
    "DonationsManager",
    # Licenses
    "LicenseManager",
    "LicenseScanResult",
    # Maintainers
    "MaintainerProfile",
    "MaintainerRegistry",
    "CORE_MAINTAINERS",
    # Safety Check
    "SafetyChecker",
    "SafetyCheckResult",
    # Manager
    "LegalManager",
    "get_default_legal_manager",
]
