# UmerOS /proc — Virtual /proc filesystem (procfs)
# =================================================
# GPL-3.0 — see LICENSE and README for details.
#
# Provides a complete, Linux-compatible simulation of the ``/proc``
# pseudo-filesystem.  See ``proc/procfs.py`` for the actual file
# tree implementation.
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /proc — Virtual /proc filesystem (procfs).
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


# Relative imports only — the previous version used
# ``from proc.procfs import …`` which is brittle (it requires
# ``proc`` to be on ``sys.path`` as a top-level package and creates
# a name-shadowing problem when this package is itself imported as
# ``proc``).
for _mod, _names in (
    ("procfs", ("ProcFileSystem",)),
    ("kernel_adapter", ("KernelAdapter",)),
    ("process", ("ProcessInfo",)),
    ("sysctl", ("SysctlView",)),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the package is importable and the public surface exists."""
    import sys
    try:
        __import__(__name__)
    except Exception as exc:  # noqa: BLE001
        print(f"proc selftest FAIL: {exc}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
