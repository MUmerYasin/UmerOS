# UmerOS /feedback — Community Feedback, Bug Reports & GNU FDL Subsystem
# =======================================================================
# GPL-3.0 — see LICENSE and README for details.
#
# Implements the community feedback framework, bug/correction/suggestion
# pipeline, and GNU Free Documentation License (GFDL) engine.
#
# Modules (only `models` exists today; the rest are planned stubs):
# ---------
# models        - FeedbackEntry, FeedbackKind, FeedbackStatus, FeedbackPriority  [IMPLEMENTED]
# collector     - FeedbackCollector: submit, validate & persist reports          [PLANNED - not implemented]
# tracker       - FeedbackTracker: triage, assign, resolve & audit lifecycle     [PLANNED - not implemented]
# channels      - Channel definitions (email, GitHub, mailing-list, IRC/Matrix)  [PLANNED - not implemented]
# gfdl          - GFDLLicense: GNU Free Documentation License 1.3 compliance     [PLANNED - not implemented]
# manager       - FeedbackManager: master coordinator                            [PLANNED - not implemented]
# cli           - feedback_ctl command-line controller                           [PLANNED - not implemented]
#
# Author: Muhammad Umer Yasin / UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
# [REFERENCE-ONLY] Not reachable from main.py — see docs/reference_corpus.md

"""
UmerOS /feedback — Community Feedback, Bug Reports & GNU FDL Subsystem.

[STUB] Only the data models (``feedback.models``) are implemented. The
collector / tracker / channels / gfdl / manager / cli submodules listed above do
**not** exist yet; their imports below are guarded (``try/except ImportError``)
so ``import feedback`` succeeds and exports only the symbols that are actually
present (the ``models`` names).
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__: list[str] = []

# Use relative imports — the previous sys.path self-injection was removed
# (H76 root cause: it shadowed same-named top-level packages and broke
# the test suite once this package was imported).

try:
    from .models import (
        FeedbackEntry,
        FeedbackKind,
        FeedbackStatus,
        FeedbackPriority,
    )
    __all__ += [
        "FeedbackEntry",
        "FeedbackKind",
        "FeedbackStatus",
        "FeedbackPriority",
    ]
except ImportError:
    pass

try:
    from .collector import FeedbackCollector
    __all__ += ["FeedbackCollector"]
except ImportError:
    pass

try:
    from .tracker import FeedbackTracker
    __all__ += ["FeedbackTracker"]
except ImportError:
    pass

try:
    from .channels import FeedbackChannel, UMEROS_FEEDBACK_CHANNELS
    __all__ += ["FeedbackChannel", "UMEROS_FEEDBACK_CHANNELS"]
except ImportError:
    pass

try:
    from .gfdl import GFDLLicense, GFDL_SECTIONS
    __all__ += ["GFDLLicense", "GFDL_SECTIONS"]
except ImportError:
    pass

try:
    from .manager import FeedbackManager, get_default_feedback_manager
    __all__ += ["FeedbackManager", "get_default_feedback_manager"]
except ImportError:
    pass


def _selftest() -> bool:
    """Verify that the public surface of this package is importable.

    Returns True if every name in ``__all__`` is also importable, False
    if any are missing (the test runner can then flag the package as
    partially broken).
    """
    import importlib

    pkg = importlib.import_module(__name__)
    missing = [name for name in __all__ if not hasattr(pkg, name)]
    if missing:
        import sys
        print(
            f"feedback selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
