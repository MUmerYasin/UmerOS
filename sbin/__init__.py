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

# UmerOS /sbin — System binaries
# ===============================
# GPL-3.0 — see LICENSE and README for details.
#
# /sbin implementation: system administration,
# maintenance, boot, hardware config, and filesystem management
# programs.
# [REFERENCE-ONLY] Not reachable from main.py — see docs/reference_corpus.md

"""
UmerOS /sbin — System binaries.

Every command in this package is a **simulation**: it prints what it would
have done and returns an exit status, without issuing the syscall.
Output lines are prefixed ``[simulated]``, each audit record carries
``simulated=True``, and ``SbinManager.is_simulated(name)`` answers it
programmatically.  ``mktemp`` is the sole exception -- it really creates a
temp file.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Sbin")


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


# Relative imports only — the previous sys.path
# self-injection was removed because it shadowed the same-named
# top-level packages (e.g. ``boot``).
for _mod, _names in (
    ("boot", (
        "HaltCommand", "InitCommand", "PoweroffCommand", "RebootCommand",
        "ShutdownCommand", "GettyCommand", "FastbootCommand",
        "FasthaltCommand", "UpdateCommand",
    )),
    ("filesystem", (
        "FdiskCommand", "FsckCommand", "MkfsCommand",
        "SwaponCommand", "SwapoffCommand", "MkswapCommand", "ChrootCommand",
    )),
    ("modules", (
        "InsmodCommand", "LsmodCommand", "ModprobeCommand",
        "RmmodCommand", "DepmodCommand",
    )),
    ("network", ("IfconfigCommand", "IpCommand", "RouteCommand")),
    ("system", ("SysctlCommand", "HwclockCommand", "LdconfigCommand")),
    ("mount", (
        "MountCommand", "UmountCommand", "MknodCommand",
        "LosetupCommand", "PivotRootCommand",
    )),
    ("maintenance", (
        "Tune2fsCommand", "E2fsckCommand", "Mke2fsCommand",
        "CtrlaltdelCommand", "KbdrateCommand", "LoadkeysCommand",
        "DumpCommand", "RestoreCommand", "SlnCommand",
        "MktempCommand", "SetfdprmCommand", "RdevCommand",
    )),
    ("sbin_manager", (
        "SbinManager", "FHS_REQUIRED_SBIN", "FHS_OPTIONAL_SBIN",
        "ALL_SBIN_ENTRIES", "SBIN_COMMAND_REGISTRY",
    )),
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
            f"sbin selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
