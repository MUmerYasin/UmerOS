"""
UmerOS /sbin System Commands
=============================
System configuration command implementations.
sysctl, hwclock, ldconfig
"""

from __future__ import annotations
import os
import sys
from abc import abstractmethod
from typing import Any, Dict, List, Optional


class SbinCommand:
    """Base class for /sbin commands."""

    name: str = ""
    description: str = ""
    usage: str = ""

    @abstractmethod
    def execute(self, args: Optional[List[str]] = None) -> int:
        pass

    def help(self) -> str:
        return f"Usage: {self.usage}\n{self.description}"


# ─── System Commands ─────────────────────────────────────────────────────────

class SysctlCommand(SbinCommand):
    """Configure kernel parameters at runtime."""
    name = "sysctl"
    description = "Configure kernel parameters at runtime"
    usage = "sysctl [-n] [-e] [-w] [variable] [value]"

    DEFAULT_PARAMS: Dict[str, Any] = {
        "kernel.hostname": "umeros",
        "kernel.ostype": "Linux",
        "kernel.osrelease": "5.15.0-uming",
        "net.ipv4.ip_forward": 0,
        "vm.swappiness": 60,
        "fs.file-max": 2097152,
        "kernel.pid_max": 32768,
    }

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("sysctl: missing operand", file=sys.stderr)
            return 1

        param = args[0]

        if param in ("-h", "--help"):
            return 0

        if param in ("-a", "--all"):
            for key, value in sorted(self.DEFAULT_PARAMS.items()):
                print(f"{key} = {value}")
            return 0

        if param in ("-p", "--system"):
            # Load from /etc/sysctl.conf (simulate)
            print("sysctl: loading from /etc/sysctl.conf")
            for key, value in sorted(self.DEFAULT_PARAMS.items()):
                print(f"{key} = {value}")
            return 0

        if param in ("-w", "--write") and len(args) >= 3:
            key = args[1]
            value = args[2]
            print(f"[*] sysctl: setting '{key}' = '{value}'")
            return 0

        if param in ("-n", "--values"):
            if len(args) >= 2 and args[1] in self.DEFAULT_PARAMS:
                print(self.DEFAULT_PARAMS[args[1]])
                return 0
            print(f"sysctl: key not found '{args[1] if len(args) > 1 else ''}'", file=sys.stderr)
            return 1

        # Direct query: sysctl variable
        if param in self.DEFAULT_PARAMS:
            print(f"{param} = {self.DEFAULT_PARAMS[param]}")
            return 0

        print(f"sysctl: unknown key '{param}'", file=sys.stderr)
        return 1


class HwclockCommand(SbinCommand):
    """Query and set the hardware clock (RTC)."""
    name = "hwclock"
    description = "Query or set the hardware clock (RTC) and display the current time"
    usage = "hwclock [-r] [-w] [-s] [-u] [-l] [-f file] [-D] [--utc] [--localtime]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not args or args[0] == "-r":
            print(f"Hardware clock: {now}")
            print(f"System clock:   {now}")
            return 0
        if args[0] == "-w":
            print(f"[*] hwclock: writing system time to hardware clock ({now})")
            return 0
        if args[0] == "-s":
            print(f"[*] hwclock: setting system time from hardware clock")
            return 0
        if args[0] in ("-h", "--help"):
            print(self.help())
            return 0
        print(f"hwclock: operating on '{args[0]}'")
        return 0


class LdconfigCommand(SbinCommand):
    """Configure dynamic linker runtime bindings."""
    name = "ldconfig"
    description = "Configure dynamic linker runtime bindings"
    usage = "ldconfig [-nNvXV] [-f conf] [-C cache] [-r root] directory..."

    DEFAULT_LIBS: Dict[str, str] = {
        "/usr/lib": "libc.so.6, libm.so.6, libpthread.so.0",
        "/lib": "ld-linux.so.2, libc.so.6",
        "/usr/local/lib": "libfoo.so.1",
    }

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            # Show current cache
            print("ldconfig: current cache contents:")
            for path, libs in self.DEFAULT_LIBS.items():
                print(f"  {path}: {libs}")
            return 0
        if args[0] in ("-v", "--verbose"):
            print("ldconfig: updating library cache...")
            for path, libs in self.DEFAULT_LIBS.items():
                print(f"  {path}: {libs}")
            print("ldconfig: cache updated")
            return 0
        if args[0] in ("-n", "--precache"):
            print("[*] ldconfig: processing only named directories")
            return 0
        if args[0] in ("-N", "--not-changed"):
            print("[*] ldconfig: not changing cache")
            return 0
        if args[0] in ("-p", "--print-cache"):
            print("ldconfig: current cache:")
            for path, libs in self.DEFAULT_LIBS.items():
                print(f"  {path}: {libs}")
            return 0
        if args[0] in ("-X", "--no-links"):
            print("[*] ldconfig: skipping symlink creation")
            return 0
        if args[0] in ("-V", "--version"):
            print("ldconfig (UmerOS) 1.0.0")
            return 0
        if args[0] in ("-f", "--file") and len(args) > 1:
            print(f"[*] ldconfig: using config file '{args[1]}'")
            return 0
        if args[0] in ("-C", "--cache") and len(args) > 1:
            print(f"[*] ldconfig: using cache file '{args[1]}'")
            return 0
        if args[0] in ("-r", "--root") and len(args) > 1:
            print(f"[*] ldconfig: using root directory '{args[1]}'")
            return 0
        # Process directories
        for d in args:
            if not d.startswith("-"):
                print(f"[*] ldconfig: processing directory '{d}'")
        return 0


def _selftest() -> bool:
    """Run self-tests for /sbin system commands."""
    tests_passed = 0
    tests_failed = 0

    def check(condition: bool, msg: str):
        nonlocal tests_passed, tests_failed
        if condition:
            tests_passed += 1
        else:
            tests_failed += 1
            print(f"  FAIL: {msg}")

    cmd = SysctlCommand()
    check(cmd.name == "sysctl", "sysctl name")
    check(cmd.execute() == 1, "sysctl no args -> 1")
    check(cmd.execute(["-a"]) == 0, "sysctl -a -> 0")
    check(cmd.execute(["-h"]) == 0, "sysctl -h -> 0")
    check(cmd.execute(["-p"]) == 0, "sysctl -p -> 0")
    check(cmd.execute(["-w", "kernel.hostname", "test"]) == 0, "sysctl -w key val -> 0")
    check(cmd.execute(["-n", "kernel.hostname"]) == 0, "sysctl -n key -> 0")
    check(cmd.execute(["kernel.hostname"]) == 0, "sysctl kernel.hostname -> 0")
    check(cmd.execute(["unknown.key"]) == 1, "sysctl unknown -> 1")

    cmd = HwclockCommand()
    check(cmd.name == "hwclock", "hwclock name")
    check(cmd.execute() == 0, "hwclock no args -> 0")
    check(cmd.execute(["-r"]) == 0, "hwclock -r -> 0")
    check(cmd.execute(["-w"]) == 0, "hwclock -w -> 0")
    check(cmd.execute(["-s"]) == 0, "hwclock -s -> 0")
    check(cmd.execute(["-h"]) == 0, "hwclock -h -> 0")

    cmd = LdconfigCommand()
    check(cmd.name == "ldconfig", "ldconfig name")
    check(cmd.execute() == 0, "ldconfig no args -> 0")
    check(cmd.execute(["-v"]) == 0, "ldconfig -v -> 0")
    check(cmd.execute(["-p"]) == 0, "ldconfig -p -> 0")
    check(cmd.execute(["-V"]) == 0, "ldconfig -V -> 0")
    check(cmd.execute(["-f", "/etc/ld.so.conf"]) == 0, "ldconfig -f -> 0")

    print(f"sbin/system.py: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0
