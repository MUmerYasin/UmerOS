# UmerOS /packages — Umer package manager (.umerpkg)
# ===================================================
# GPL-3.0 — see LICENSE and README for details.
#
# The package manager entry point for UmerOS.  Implements the
# ``.umerpkg`` artifact format (signing, install, uninstall,
# upgrade, dependency resolution, repository sync).
#
# Modules (planned / optional):
# -----------------------------
# umer_pkg    - UmerPackageManager — main CLI / library entry point.
# repository  - PackageRepository, PackageInfo — local + remote repos.
# format      - .umerpkg binary format reader/writer.
# crypto      - Signed-payload verification (Dilithium / Ed25519).
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /packages — Umer package manager (.umerpkg).
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


# Note: previous version used ``from .umer_pkg import ...`` but the
# module is named ``umer_pkg.py``; relative imports are fine, but we
# keep a tolerant form here so a partial checkout still loads.
for _mod, _names in (
    ("umer_pkg", ("UmerPackageManager", "install", "uninstall", "upgrade")),
    ("repository", ("PackageRepository", "PackageInfo")),
    ("format", ("UmerPkg", "read_umerpkg", "write_umerpkg")),
    ("crypto", ("verify_signature", "sign_payload")),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the package is importable."""
    import sys
    try:
        __import__(__name__)
    except Exception as exc:  # noqa: BLE001
        print(f"packages selftest FAIL: {exc}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
