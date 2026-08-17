"""
UmerOS /bin -- Essential Command Binaries
==========================================
Contains all essential command binaries.

Modules:
    essential_commands - cat, cp, mv, rm, ls, mkdir, rmdir, ln, dd, more
    permissions        - chmod, chown, chgrp
    system_info        - uname, dmesg, hostname, df, echo, date, pwd
    process            - ps, kill, mount, umount, stty, sync
    user_commands      - su, login
    boolean_ops        - true, false, test, [, yes, printenv, env
    shell              - sh, sed, tar, gzip, gunzip, zcat, netstat, ping, cpio
    device             - mknod
    archive            - tar (legacy)
    network_cmds       - ifconfig, ip, route, arp
    csh                - csh (C Shell)
    ed                 - ed (line editor)
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional

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
    """Run self-tests for all /bin modules."""
    tests_passed = 0
    tests_failed = 0

    def check(condition: bool, msg: str) -> None:
        nonlocal tests_passed, tests_failed
        if condition:
            tests_passed += 1
        else:
            tests_failed += 1
            print(f"FAIL: {msg}")

    # Test that all modules can be imported
    for mod_name in _BIN_MODULES:
        try:
            mod = importlib.import_module(mod_name)
            check(True, f"import {mod_name}")
            if hasattr(mod, "_selftest"):
                result = mod._selftest()
                check(result, f"_selftest in {mod_name}")
        except Exception as e:
            check(False, f"import {mod_name}: {e}")

    print(f"  {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


if __name__ == "__main__":
    _selftest()
