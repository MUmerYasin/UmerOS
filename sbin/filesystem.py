"""
UmerOS /sbin Filesystem Commands
=================================
Filesystem manipulation command implementations.
fdisk, fsck, mkfs, swapon
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


# ─── Filesystem Commands ─────────────────────────────────────────────────────

class FdiskCommand(SbinCommand):
    """Partition table manipulator."""
    name = "fdisk"
    description = "Manipulate disk partition table"
    usage = "fdisk [-l] [-b S] [-C H] [-H M] [-u] device"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args or args[0] == "-l":
            print("Disk /dev/sda: 500 GiB, 536870912000 bytes, 1048576000 sectors")
            print("Device     Boot   Start        End   Sectors  Size Id Type")
            print("/dev/sda1  *       2048 1048575999 1048573952  500G  83 Linux")
            return 0
        print(f"fdisk: operating on '{args[0]}'", file=sys.stderr)
        return 0


class FsckCommand(SbinCommand):
    """Filesystem check and repair."""
    name = "fsck"
    description = "Check and repair a Linux filesystem"
    usage = "fsck [-aANrtVsTP] [-y] [-f] [-g] [-h] filesystem"

    def execute(self, args: Optional[List[str]] = None) -> int:
        target = args[0] if args else "/dev/sda1"
        print(f"fsck: checking {target}")
        print(f"fsck: clean, {0} files, {0} blocks")
        return 0


class MkfsCommand(SbinCommand):
    """Build a Linux filesystem."""
    name = "mkfs"
    description = "Build a Linux filesystem"
    usage = "mkfs [-t type] [-c] [-l opts] [-v] device [blocks]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        fs_type = "ext4"
        if len(args) >= 2 and args[0] == "-t":
            fs_type = args[1]
            args = args[2:]
        device = args[0] if args else "/dev/sda1"
        print(f"mkfs: creating {fs_type} filesystem on {device}")
        print("mke2fs 1.45.5 (07-Jan-2020)")
        return 0


class SwaponCommand(SbinCommand):
    """Enable swap devices and files."""
    name = "swapon"
    description = "Enable swap devices and files"
    usage = "swapon [-a] [-d] [-e] [-f] [-h] [-s] [-v] [-p priority] device"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args or args[0] == "-a":
            print("[*] swapon: enabling all swap devices")
            return 0
        print(f"swapon: enabling '{args[0]}'")
        return 0
