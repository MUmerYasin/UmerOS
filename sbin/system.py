"""
UmerOS /sbin System Commands
=============================
System configuration command implementations.
sysctl
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
            # Show all parameters
            for key, value in sorted(self.DEFAULT_PARAMS.items()):
                print(f"{key} = {value}")
            return 0

        param = args[0]
        if param in ("-a", "--all"):
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
