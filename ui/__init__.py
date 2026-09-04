# UmerOS /ui — Legacy user interface (Tkinter / Kivy / CLI)
# ============================================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``ui`` package hosts the **legacy** user interfaces that
# pre-date the Flutter (Dart) desktop shell in ``ui/flutter_ui``.
# New UI work should go there; this package is kept only for
# backwards compatibility with existing scripts and tests.
#
# Modules
# -------
# fluidic_ui - FluidicShell (CLI shell).
# theme      - Theme dataclass.
"""
UmerOS /ui — Legacy user interface (Tkinter / Kivy / CLI).
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.UI")


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
    ("fluidic_ui", ("FluidicShell",)),
    ("theme", ("Theme",)),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the public surface is importable."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"ui selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
