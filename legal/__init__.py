# UmerOS /legal — Legal, Disclaimer, Consent & Compliance Subsystem
# =================================================================
# GPL-3.0 — see LICENSE and README for details.
#
# Implements legal liability disclaimers, user consent verification
# gates, contributor attributions, donation sponsorships, maintainer
# profiles, open-source licensing compliance, and pre-execution
# safety checkpoints.
#
# Modules:
# --------
# disclaimer   - DisclaimerNotice, DisclaimerRegistry, RiskLevel, UmerOS waivers
# consent      - ConsentManager, ConsentRecord, ConsentGateError, 'I AGREE' validator
# contributors - ContributorRegistry, ContributorRecord, DCO certification
# donations    - DonationsManager, DonationRecord, DonationTier, funding channels
# licenses     - LicenseManager, LicenseScanResult, multi-license auditor
# maintainers  - MaintainerRegistry, MaintainerProfile, PQC & PGP signing keys
# safety_check - SafetyChecker, SafetyCheckResult, pre-execution backup runner
# manager      - LegalManager (master unified controller)
# cli          - legal_ctl command-line controller
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /legal — Legal, Disclaimer, Consent & Compliance Subsystem.
"""

from __future__ import annotations

__version__ = "1.1.0"
__all__: list[str] = []

# All imports are best-effort with try/except so a partially-built
# checkout can still be imported.  The previous sys.path self-injection
# was removed (root cause: it shadowed the top-level ``manager`` module
# once this package was imported, breaking unrelated tests).

try:
    from .disclaimer import (
        TLDP_DISCLAIMER_TEXT,
        UMEROS_MASTER_DISCLAIMER_TEXT,
        DisclaimerNotice,
        DisclaimerRegistry,
        RiskLevel,
    )
    __all__ += [
        "TLDP_DISCLAIMER_TEXT",
        "UMEROS_MASTER_DISCLAIMER_TEXT",
        "DisclaimerNotice",
        "DisclaimerRegistry",
        "RiskLevel",
    ]
except ImportError:
    pass

try:
    from .consent import (
        ConsentGateError,
        ConsentManager,
        ConsentRecord,
        get_machine_fingerprint,
    )
    __all__ += [
        "ConsentGateError",
        "ConsentManager",
        "ConsentRecord",
        "get_machine_fingerprint",
    ]
except ImportError:
    pass

try:
    from .contributors import (
        CANONICAL_CONTRIBUTORS,
        ContributorRecord,
        ContributorRegistry,
        ContributorRole,
    )
    __all__ += [
        "CANONICAL_CONTRIBUTORS",
        "ContributorRecord",
        "ContributorRegistry",
        "ContributorRole",
    ]
except ImportError:
    pass

try:
    from .donations import (
        DonationRecord,
        DonationsManager,
        DonationTier,
    )
    __all__ += [
        "DonationRecord",
        "DonationsManager",
        "DonationTier",
    ]
except ImportError:
    pass

try:
    from .licenses import (
        LicenseManager,
        LicenseScanResult,
    )
    __all__ += [
        "LicenseManager",
        "LicenseScanResult",
    ]
except ImportError:
    pass

try:
    from .maintainers import (
        CORE_MAINTAINERS,
        MaintainerProfile,
        MaintainerRegistry,
    )
    __all__ += [
        "CORE_MAINTAINERS",
        "MaintainerProfile",
        "MaintainerRegistry",
    ]
except ImportError:
    pass

try:
    from .safety_check import (
        SafetyChecker,
        SafetyCheckResult,
    )
    __all__ += [
        "SafetyChecker",
        "SafetyCheckResult",
    ]
except ImportError:
    pass

try:
    from .manager import (
        LegalManager,
        get_default_legal_manager,
    )
    __all__ += [
        "LegalManager",
        "get_default_legal_manager",
    ]
except ImportError:
    pass


def _selftest() -> bool:
    """Verify every name in ``__all__`` is importable from this package."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [name for name in __all__ if not hasattr(pkg, name)]
    if missing:
        print(
            f"legal selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
