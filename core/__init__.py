# UmerOS /core — Core microkernel primitives
# ===========================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``core`` package hosts the small handful of foundational
# building blocks used by the rest of the system: a base ``Command``
# class for the FHS `/bin` / `/sbin` programs, a ``Permission`` /
# ``Capability``-style guard, a JSON-config loader, and a small
# ``errno`` mapping.
#
# Modules (planned / optional):
# -----------------------------
# command     - Base class for FHS commands (`execute(args=None) -> int`).
# permission  - POSIX-style permission helpers.
# json_config - JSON-on-disk config loader.
# errno_map   - errno <-> string mapping for shell commands.
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /core — Core microkernel primitives.
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__: list[str] = []

# Best-effort re-exports.  Each module is optional so partial checkouts
# can still be imported.
_IMPORT_MAP = (
    ("command", ("Command", "BaseCommand")),
    ("permission", ("Permission", "check_permission")),
    ("json_config", ("JsonConfig", "load_config", "save_config")),
    ("errno_map", ("ERRNO_MAP", "errno_to_name", "name_to_errno")),
)


def _try_import(module_name: str, names: tuple[str, ...]) -> None:
    """Import ``module_name`` and add the requested names to __all__."""
    global __all__
    try:
        mod = __import__(f"{__name__}.{module_name}", fromlist=names)
    except ImportError:
        return
    for n in names:
        if hasattr(mod, n):
            globals()[n] = getattr(mod, n)
            __all__ = list(__all__) + [n]


for _mod, _names in _IMPORT_MAP:
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the package is importable.  Returns True on success."""
    import sys

    try:
        importlib_import = __import__("importlib").import_module
    except ImportError:  # pragma: no cover
        return True
    try:
        importlib_import(__name__)
    except Exception as exc:  # noqa: BLE001
        print(f"core selftest FAIL: cannot import {__name__}: {exc}",
              file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
