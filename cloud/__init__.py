# UmerOS /cloud — Cloud orchestration and OTA updates
# ====================================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``cloud`` package hosts:
#   * ``cloud.ota_updater``  - signed over-the-air update manager
#   * any future cloud-only services (sync, telemetry backup, etc.)
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /cloud — Cloud orchestration and OTA updates.
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__: list[str] = []


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
    ("ota_updater", (
        "UpdateManager", "UpdateManifest", "UpdateChannel",
        "verify_and_apply",
    )),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the package is importable and exports the expected surface."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [name for name in __all__ if not hasattr(pkg, name)]
    if missing:
        print(
            f"cloud selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
