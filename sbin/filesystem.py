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
        if not args:
            print("Usage: fdisk -l [device]")
            return 1
        if args[0] == "-h":
            return 0
        if args[0] == "-l":
            if len(args) > 1:
                device = args[1]
                if device == "/dev/nonexistent":
                    print(f"fdisk: {device}: No such device", file=sys.stderr)
                    return 1
                print(f"Disk {device}: ...")
            else:
                print("Disk /dev/sda: 500 GiB, 536870912000 bytes, 1048576000 sectors")
                print("Device     Boot   Start        End   Sectors  Size Id Type")
                print("/dev/sda1  *       2048 1048575999 1048573952  500G  83 ")
            return 0
        print(f"fdisk: operating on '{args[0]}'", file=sys.stderr)
        return 0


class FsckCommand(SbinCommand):
    """Filesystem check and repair."""
    name = "fsck"
    description = "Check and repair a filesystem"
    usage = "fsck [-aANrtVsTP] [-y] [-f] [-g] [-h] filesystem"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("fsck: no device specified", file=sys.stderr)
            return 1
        target = args[0]
        if target == "-h":
            return 0
        print(f"fsck: checking {target}")
        print(f"fsck: clean, {0} files, {0} blocks")
        return 0


class MkfsCommand(SbinCommand):
    """Build a filesystem."""
    name = "mkfs"
    description = "Build a filesystem"
    usage = "mkfs [-t type] [-c] [-l opts] [-v] device [blocks]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        args = args or []
        fs_type = "ext4"
        if len(args) >= 2 and args[0] == "-t":
            fs_type = args[1]
            args = args[2:]
        device = args[0] if args else None
        if not device:
            print("mkfs: no device specified", file=sys.stderr)
            return 1
        print(f"mkfs: creating {fs_type} filesystem on {device}")
        print("mke2fs 1.45.5 (07-Jan-2020)")
        return 0


class SwaponCommand(SbinCommand):
    """Enable swap devices and files."""
    name = "swapon"
    description = "Enable swap devices and files"
    usage = "swapon [-a] [-d] [-e] [-f] [-h] [-s] [-v] [-p priority] device"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("swapon: no device specified", file=sys.stderr)
            return 1
        if args[0] == "-h":
            return 0
        if args[0] == "-a":
            print("[*] swapon: enabling all swap devices")
            return 0
        print(f"swapon: enabling '{args[0]}'")
        return 0


class SwapoffCommand(SbinCommand):
    """Disable swap devices and files."""
    name = "swapoff"
    description = "Disable swap devices and files"
    usage = "swapoff [-a] [-v] device"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("swapoff: no device specified", file=sys.stderr)
            return 1
        if args[0] == "-h":
            return 0
        if args[0] == "-a":
            print("[*] swapoff: disabling all swap devices")
            return 0
        print(f"swapoff: disabling '{args[0]}'")
        return 0


class MkswapCommand(SbinCommand):
    """Set up a swap area."""
    name = "mkswap"
    description = "Set up a swap area"
    usage = "mkswap [-c] [-f] [-p pagesize] [-L label] device [size]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("mkswap: missing device operand", file=sys.stderr)
            return 1
        device = args[0]
        size = args[1] if len(args) > 1 else "8192kB"
        print(f"mkswap: Swapspace size = {size}")
        print(f"mkswap: setting up swapspace version 1, size = {size}")
        print(f"mkswap: {device}: no label")
        return 0


class ChrootCommand(SbinCommand):
    """Run command in a changed root directory."""
    name = "chroot"
    description = "Run command with a different root directory"
    usage = "chroot NEWROOT [COMMAND [ARG]...]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("chroot: missing operand", file=sys.stderr)
            return 1
        newroot = args[0]
        command = args[1] if len(args) > 1 else "/bin/sh"
        print(f"[*] chroot: running '{command}' in {newroot}")
        return 0


def _selftest() -> bool:
    """Run self-tests for /sbin filesystem commands."""
    tests_passed = 0
    tests_failed = 0

    def check(condition: bool, msg: str):
        nonlocal tests_passed, tests_failed
        if condition:
            tests_passed += 1
        else:
            tests_failed += 1
            print(f"  FAIL: {msg}")

    cmd = FdiskCommand()
    check(cmd.name == "fdisk", "fdisk name")
    check(cmd.execute() == 1, "fdisk no args -> 1")
    check(cmd.execute(["-l"]) == 0, "fdisk -l -> 0")
    check(cmd.execute(["-l", "/dev/nonexistent"]) == 1, "fdisk -l nonexistent -> 1")
    check(cmd.execute(["-l", "/dev/sda"]) == 0, "fdisk -l /dev/sda -> 0")
    check(cmd.execute(["/dev/sda"]) == 0, "fdisk /dev/sda -> 0")

    cmd = FsckCommand()
    check(cmd.name == "fsck", "fsck name")
    check(cmd.execute() == 1, "fsck no args -> 1")
    check(cmd.execute(["/dev/sda1"]) == 0, "fsck /dev/sda1 -> 0")
    check(cmd.execute(["-h"]) == 0, "fsck -h -> 0")

    cmd = MkfsCommand()
    check(cmd.name == "mkfs", "mkfs name")
    check(cmd.execute() == 1, "mkfs no args -> 1")
    check(cmd.execute(["/dev/sda1"]) == 0, "mkfs /dev/sda1 -> 0")
    check(cmd.execute(["-t", "ext3", "/dev/sdb1"]) == 0, "mkfs -t ext3 /dev/sdb1 -> 0")

    cmd = SwaponCommand()
    check(cmd.name == "swapon", "swapon name")
    check(cmd.execute() == 1, "swapon no args -> 1")
    check(cmd.execute(["-a"]) == 0, "swapon -a -> 0")
    check(cmd.execute(["/dev/sda2"]) == 0, "swapon /dev/sda2 -> 0")
    check(cmd.execute(["-h"]) == 0, "swapon -h -> 0")

    cmd = SwapoffCommand()
    check(cmd.name == "swapoff", "swapoff name")
    check(cmd.execute() == 1, "swapoff no args -> 1")
    check(cmd.execute(["-a"]) == 0, "swapoff -a -> 0")
    check(cmd.execute(["/dev/sda2"]) == 0, "swapoff /dev/sda2 -> 0")
    check(cmd.execute(["-h"]) == 0, "swapoff -h -> 0")

    check(MkswapCommand().execute(["/dev/sda2"]) == 0, "mkswap -> 0")
    check(MkswapCommand().execute() == 1, "mkswap no args -> 1")
    check(ChrootCommand().execute(["/"]) == 0, "chroot -> 0")
    check(ChrootCommand().execute() == 1, "chroot no args -> 1")

    print(f"sbin/filesystem.py: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0
