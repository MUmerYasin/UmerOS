# UmerOS /sdk — SDK for third-party UmerOS apps
# =============================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``sdk`` package contains the public surface a third-party
# developer uses to build a UmerOS-native app:
#
#   * ``app_template`` - ``UmerApp`` base class (lifecycle hooks).
#   * ``build_tool``   - ``BuildTool`` (packaging, signing).
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /sdk — SDK for third-party UmerOS apps.
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.SDK")


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


for _mod, _names in (
    ("app_template", ("UmerApp",)),
    ("build_tool", ("BuildTool",)),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the public surface is importable."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"sdk selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
