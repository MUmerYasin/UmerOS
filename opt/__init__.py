# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
# [REFERENCE-ONLY] Not reachable from main.py — see docs/reference_corpus.md

"""
UmerOS /opt — Add-on software package management.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

__version__ = "1.0.0"
__author__ = "UmerOS"
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
    ("manager", ("OptManager", "PackageOptManager")),
    ("package", ("OptPackage",)),
    ("config", ("OptConfig", "OptIntegration")),
    ("env", ("OptEnvManager",)),
    ("fhs", ("OptFHSValidator",)),
    ("hierarchy", ("OptHierarchy",)),
    ("var", ("VarOptManager",)),
    ("integration", ("OptEnvironment", "OptPathManager", "OptServiceManager")),
):
    _try_import(_mod, _names)


# Modules whose own _selftest() the package selftest runs (H192).
_SELFTEST_MODULES = (
    "env", "fhs", "hierarchy", "var", "config",
    "integration", "manager", "package",
)


def _selftest() -> bool:
    """Verify the public surface is importable and every child passes."""
    import importlib
    import sys

    # Executed as a file (`python opt/__init__.py`) __name__ is __main__ and
    # the repo root is not on sys.path - make the package importable and
    # address the children by absolute name either way.
    if __name__ == "__main__":
        _root = str(Path(__file__).resolve().parent.parent)
        if _root not in sys.path:
            sys.path.insert(0, _root)
        package = "opt"
    else:
        package = __name__

    pkg = importlib.import_module(package)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"opt selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    # Run each child's own _selftest so one command checks the subsystem
    # instead of only the import surface.
    failures = []
    for mod_name in _SELFTEST_MODULES:
        try:
            module = importlib.import_module(f"{package}.{mod_name}")
        except ImportError as exc:
            failures.append(f"{mod_name}: {exc}")
            continue
        child = getattr(module, "_selftest", None)
        if child is not None and child() is not True:
            failures.append(mod_name)
    if failures:
        print(f"opt selftest FAIL: {failures}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
