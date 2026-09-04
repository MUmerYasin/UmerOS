# UmerOS /bin — Essential command binaries
# =========================================
# GPL-3.0 — see LICENSE and README for details.
#
# /bin implementation.  Each command module lives in
# this package and follows the
# ``execute(args=None) -> int`` + ``self.name/description/usage`` +
# ``_selftest()`` contract.
#
# Modules
# -------
# essential_commands - cat, cp, mv, rm, ls, mkdir, rmdir, ln, dd, more
# permissions        - chmod, chown, chgrp
# system_info        - uname, dmesg, hostname, df, echo, date, pwd
# process            - ps, kill, mount, umount, stty, sync
# user_commands      - su, login
# boolean_ops        - true, false, test, [, yes, printenv, env
# shell              - sh, sed, tar, gzip, gunzip, zcat, netstat, ping, cpio
# device             - mknod
# archive            - tar (legacy)
# network_cmds       - ifconfig, ip, route, arp
# csh                - csh (C Shell)
# ed                 - ed (line editor)
# bin_manager        - command registry, FHS audit
"""
UmerOS /bin — Essential command binaries.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, List, Optional

__version__ = "1.0.0"
__author__ = "UmerOS Development Team"

log = logging.getLogger("UmerOS.Bin")

# All command modules available in /bin
_BIN_MODULES: List[str] = [
    "essential_commands",
    "permissions",
    "system_info",
    "process",
    "user_commands",
    "boolean_ops",
    "shell",
    "device",
    "archive",
    "network_cmds",
    "csh",
    "ed",
    "usr_commands",
    "usr_cmds",
    "bin_manager",
]


def _selftest() -> bool:
    """Run self-tests for all /bin modules.

    Imports every module in ``_BIN_MODULES`` and, when present, calls
    its ``_selftest()`` function.  Returns True only when all modules
    import and all sub-tests pass.

    On non-POSIX platforms (notably Windows) some modules that depend
    on ``pwd`` / ``termios`` / ``grp`` are skipped rather than treated
    as failures — the modules are POSIX-only by design.
    """
    import os
    import sys

    is_posix = (os.name == "posix")

    tests_passed = 0
    tests_failed = 0

    def check(condition: bool, msg: str) -> None:
        nonlocal tests_passed, tests_failed
        if condition:
            tests_passed += 1
        else:
            tests_failed += 1
            print(f"FAIL: {msg}")

    # Modules that depend on POSIX-only stdlib (pwd, grp, termios, spwd)
    # and therefore cannot be imported on Windows.
    POSIX_ONLY = {
        "process",        # uses termios
        "user_commands",  # uses pwd / grp / spwd
    }

    for mod_name in _BIN_MODULES:
        if mod_name in POSIX_ONLY and not is_posix:
            check(True, f"skip {mod_name} (POSIX-only on this platform)")
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{mod_name}")
            check(True, f"import {__name__}.{mod_name}")
            if hasattr(mod, "_selftest"):
                result = mod._selftest()
                check(bool(result), f"_selftest in {mod_name}")
        except Exception as e:  # noqa: BLE001
            check(False, f"import {__name__}.{mod_name}: {e}")

    print(f"  {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
