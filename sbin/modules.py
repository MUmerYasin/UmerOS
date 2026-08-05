"""
UmerOS /sbin Module Commands
==============================
Kernel module management command implementations.
insmod, lsmod, modprobe, rmmod
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


# ─── Module Commands ─────────────────────────────────────────────────────────

class InsmodCommand(SbinCommand):
    """Insert a module into the Linux kernel."""
    name = "insmod"
    description = "Insert a module into the Linux kernel"
    usage = "insmod [filename] [module-parameters]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("insmod: missing module filename", file=sys.stderr)
            return 1
        module = args[0]
        print(f"[*] insmod: inserting module '{module}'")
        return 0


class LsmodCommand(SbinCommand):
    """List currently loaded kernel modules."""
    name = "lsmod"
    description = "Show the status of modules in the Linux kernel"
    usage = "lsmod"

    def execute(self, args: Optional[List[str]] = None) -> int:
        print("Module                  Size  Used by")
        print("vfio_pci               81920  0")
        print("irqbypass              16384  1 vfio_pci")
        print("kvm_intel             401408  0")
        print("kvm                   983040  1 kvm_intel")
        print("pcspkr                 16384  0")
        print("i2c_piix4             28672  0")
        print("joydev                 24576  0")
        print("input_leds             16384  0")
        print("serio_raw              20480  0")
        print("ext4                  917504  1")
        print("mbcache                16384  1 ext4")
        print("jbd2                  106496  1 ext4")
        return 0


class ModprobeCommand(SbinCommand):
    """Add or remove modules from the Linux kernel."""
    name = "modprobe"
    description = "Intelligently add or remove modules from the Linux kernel"
    usage = "modprobe [-k] [-r] [-v] module-name"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("modprobe: missing module name", file=sys.stderr)
            return 1

        module = args[0]
        remove = "-r" in args

        if remove:
            print(f"[*] modprobe: removing module '{module}'")
        else:
            print(f"[*] modprobe: loading module '{module}'")
        return 0


class RmmodCommand(SbinCommand):
    """Remove a module from the Linux kernel."""
    name = "rmmod"
    description = "Remove a module from the Linux kernel"
    usage = "rmmod [-f] [-w] [-s] module-name"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("rmmod: missing module name", file=sys.stderr)
            return 1
        module = args[0]
        print(f"[*] rmmod: removing module '{module}'")
        return 0
