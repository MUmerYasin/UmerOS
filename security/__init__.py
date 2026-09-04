# UmerOS /security — Zero-trust, crypto, and AV subsystems
# ==========================================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``security`` package is the **root of the zero-trust boundary**:
#
#   * ``sandbox``       - SecuritySandbox, process-isolation primitives.
#   * ``crypto_engine`` - CryptoEngine (signed payloads, Kyber, Dilithium).
#   * ``antivirus``     - AntivirusEngine (signature + heuristic).
#
# Subpackage:
#   * ``security.antivirus``  - signature DB, scanner, real-time monitor,
#                              quarantine, heuristics.
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /security — Zero-trust, crypto, and AV subsystems.
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Security")


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
    ("sandbox", ("SecuritySandbox",)),
    ("crypto_engine", ("CryptoEngine",)),
    ("antivirus", ("AntivirusEngine",)),
    ("capability", ("Capability",)),
    ("tls_utils", ("TLSContext",)),
    ("hmac_utils", ("hmac_sign", "hmac_verify")),
    ("audit", ("SecurityAudit",)),
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
            f"security selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
