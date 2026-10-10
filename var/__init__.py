# UmerOS /var — Log management, spool dirs, variable state
# =========================================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``/var`` filesystem: log directories, mailboxes, caches,
# spool, transient and per-application variable state.  The package
# also re-exports the ``safe_child`` / ``safe_join`` /
# ``PathTraversalError`` helpers (a thin shim over the canonical
# ``core.path_guard``) so they can be used as a drop-in for any
# ``/var`` write that needs path-traversal protection.
# [REFERENCE-ONLY] Not reachable from main.py — see docs/reference_corpus.md

"""
UmerOS /var — Log management, mail, cache, spool dirs, variable state.
"""

from __future__ import annotations

import logging
import os
import sys

__version__ = "1.1.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Var")

# Real package name, robust even when this file is executed
# directly (``python var/__init__.py`` runs it as ``__main__``,
# which would otherwise break ``__import__(f"{__name__}.…")``).
_PKG = os.path.basename(os.path.dirname(os.path.abspath(__file__)))

# Ensure the project root is importable even when this file is
# executed directly (``python var/__init__.py`` puts the var
# directory itself on sys.path, not its parent).
_proj_root = os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)


def _try_import(module_name: str, names: tuple[str, ...]) -> None:
    """Import optional helpers and add the names to ``__all__``."""
    global __all__
    try:
        mod = __import__(f"{_PKG}.{module_name}", fromlist=names)
    except ImportError as exc:
        # [FIX] A missing submodule must not fail silently: it would
        # leave the package without a whole manager (e.g. no
        # LogManager) while every ``from var import ...`` still works.
        log.warning("var.%s could not be imported (%s); skipping.",
                    module_name, exc)
        return
    for n in names:
        if hasattr(mod, n):
            globals()[n] = getattr(mod, n)
            __all__ = list(__all__) + [n]


for _mod, _names in (
    ("log_manager", ("LogManager",)),
    ("spool_manager", ("SpoolManager",)),
    ("directory_manager", ("VarDirectoryManager",)),
    ("mail_manager", ("MailManager",)),
    ("cache_manager", ("CacheManager",)),
    ("_path_guard", ("safe_child", "safe_join", "PathTraversalError")),
):
    _try_import(_mod, _names)

# /var/lib state information is implemented in the ``lib`` package
# (lib/var_lib.py); re-export it so ``var`` exposes the complete
# FHS /var surface: log, mail, cache, spool, lib, local, lock,
# opt, run, tmp.
try:
    from lib.var_lib import (  # noqa: E402
        AlternativesManager,
        StateKind,
        VarLibEntry,
        VarLibManager,
    )
    __all__ += ["AlternativesManager", "StateKind", "VarLibEntry",
                "VarLibManager"]
except Exception as exc:  # pragma: no cover - optional integration
    log.warning("lib.var_lib could not be imported (%s); "
                "/var/lib support skipped.", exc)


def _selftest() -> bool:
    """Verify the public surface is importable."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"var selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
