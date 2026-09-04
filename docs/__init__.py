# UmerOS /docs — In-repo developer documentation toolkit
# ======================================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``docs`` package hosts the developer documentation generator
# and any helpers used to keep Markdown / man-page / Sphinx output
# consistent across the project.
#
# Modules (planned / optional):
# -----------------------------
# api_index   - Auto-generate the public API index from each package's
#               ``__init__.py`` ``__all__`` list.
# man_pages   - Helpers to render man-page skeletons from docstrings.
# screenshots - Hooks to refresh the UI screenshots in /docs/img.
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /docs — In-repo developer documentation toolkit.
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
    ("api_index", ("build_api_index", "iter_package_apis")),
    ("man_pages", ("ManPage", "render_man_page")),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """The docs package is a leaf — a successful import is enough."""
    import sys
    try:
        __import__(__name__)
    except Exception as exc:  # noqa: BLE001
        print(f"docs selftest FAIL: cannot import {__name__}: {exc}",
              file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
