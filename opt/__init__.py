# UmerOS /opt — Add-on software package management
# =================================================
# GPL-3.0 — see LICENSE and README for details.
#
# /opt: each package is installed in ``/opt/<package>`` (or
# ``/opt/<provider>/<package>``).  Host-specific config files live
# in ``/etc/opt``; variable data lives in ``/var/opt``.
#
# Modules
# -------
# manager     - OptManager (the main entry point).
# package     - OptPackage (one installed package).
# config      - OptConfig (host-specific configuration).
"""
UmerOS /opt — Add-on software package management.
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__author__ = "UmerOS Development Team"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Opt")


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
    ("manager", ("OptManager",)),
    ("package", ("OptPackage",)),
    ("config", ("OptConfig",)),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the public surface is importable."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"opt selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
