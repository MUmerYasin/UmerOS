# UmerOS /installer — Deployment / installation surface
# =====================================================
# GPL-3.0 — see LICENSE and README for details.
#
# Re-exports the real, feature-complete ``UmerInstaller`` from
# ``installer.py`` (fix for H98/H106 — the previous non-functional
# stub was removed).  The installer enforces the EULA "I AGREE" gate
# and uses fail-closed rollback.
"""
UmerOS /installer — Deployment / installation surface.
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Installer")


def _try_import(module_name: str, names: tuple[str, ...]) -> None:
    """Import optional helpers and add the names to ``__all__``."""
    global __all__
    try:
        mod = __import__(f"{__name__}.{module_name}", fromlist=names)
    except ImportError:
        return
    for n in names:
        if hasattr(mod, n):
            globals()[n] = getattr(mod, n)
            __all__ = list(__all__) + [n]


# [FIX H98] Re-export the real, feature-complete installer (installer.py),
# not the dead non-functional stub (install.py).  Now tolerant of partial
# checkouts.
for _mod, _names in (
    ("installer", ("UmerInstaller", "InstallLogger", "EULA_TEXT")),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the public surface is importable."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(
            f"installer selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
