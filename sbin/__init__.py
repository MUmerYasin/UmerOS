# UmerOS /sbin — System binaries
# ===============================
# GPL-3.0 — see LICENSE and README for details.
#
# /sbin implementation: system administration,
# maintenance, boot, hardware config, and filesystem management
# programs.
"""
UmerOS /sbin — System binaries.
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


# [FIX H261] Relative imports only — the previous sys.path
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
