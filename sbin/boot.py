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
UmerOS /sbin Boot Commands
==========================
Boot and shutdown command implementations.
halt, init, poweroff, reboot, shutdown, getty
"""

from __future__ import annotations
import os
import sys
from abc import abstractmethod
from typing import Any, Dict, List, Optional


# ─── Base Class ─────────────────────────────────────────────────────────────

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


# ─── Boot Commands ───────────────────────────────────────────────────────────

class HaltCommand(SbinCommand):
    """Halt the system immediately."""
    name = "halt"
    description = "Halt the system immediately"
    usage = "halt [-n] [-w] [-d] [-f] [-p]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        print("[*] halt: System halted", file=sys.stderr)
        return 0


class InitCommand(SbinCommand):
    """Process control initialization."""
    name = "init"
    description = "Process control initialization (PID 1)"
    usage = "init [0-6]"

    LEVELS = {
        0: "halt",
        1: "single-user",
        2: "multi-user (no networking)",
        3: "multi-user (with networking)",
        4: "unused/user-definable",
        5: "X11 (multi-user graphical)",
        6: "reboot",
    }

    def execute(self, args: Optional[List[str]] = None) -> int:
        level = 3
        if args:
            arg = args[0]
            if arg == "-q":
                return 0
            if arg == "s":
                level = 1
            else:
                try:
                    level = int(arg)
                except ValueError:
                    print(f"init: invalid runlevel '{arg}'", file=sys.stderr)
                    return 1
        if level not in self.LEVELS:
            print(f"init: unknown runlevel {level}", file=sys.stderr)
            return 1
        print(f"[*] init: switching to runlevel {level} ({self.LEVELS[level]})", file=sys.stderr)
        return 0


def _selftest() -> bool:
    """Run self-tests for /sbin boot commands."""
    tests_passed = 0
    tests_failed = 0

    def check(condition: bool, msg: str):
        nonlocal tests_passed, tests_failed
        if condition:
            tests_passed += 1
        else:
            tests_failed += 1
            print(f"  FAIL: {msg}")

    cmd = HaltCommand()
    check(cmd.name == "halt", "halt name")
    check(cmd.execute() == 0, "halt no args -> 0")
    check(cmd.execute(["-w"]) == 0, "halt -w -> 0")
    check(cmd.execute(["-f"]) == 0, "halt -f -> 0")
    check(cmd.execute(["-p"]) == 0, "halt -p -> 0")

    cmd = InitCommand()
    check(cmd.name == "init", "init name")
    check(cmd.execute() == 0, "init no args -> 0")
    check(cmd.execute(["3"]) == 0, "init 3 -> 0")
    check(cmd.execute(["5"]) == 0, "init 5 -> 0")
    check(cmd.execute(["s"]) == 0, "init s -> 0")
    check(cmd.execute(["-q"]) == 0, "init -q -> 0")
    check(cmd.execute(["99"]) == 1, "init 99 -> 1")
    check(cmd.execute(["unknown"]) == 1, "init unknown -> 1")

    check(PoweroffCommand().execute() == 0, "poweroff -> 0")
    check(RebootCommand().execute() == 0, "reboot -> 0")
    check(ShutdownCommand().execute() == 1, "shutdown no args -> 1")
    check(ShutdownCommand().execute(["now"]) == 0, "shutdown now -> 0")
    check(GettyCommand().execute() == 0, "getty -> 0")
    check(FastbootCommand().execute() == 0, "fastboot -> 0")
    check(FasthaltCommand().execute() == 0, "fasthalt -> 0")
    check(UpdateCommand().execute() == 0, "update -> 0")

    print(f"sbin/boot.py: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


class PoweroffCommand(SbinCommand):
    """Power off the system."""
    name = "poweroff"
    description = "Power off the system"
    usage = "poweroff [-n] [-w] [-d] [-f]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        print("[*] poweroff: System powered off", file=sys.stderr)
        return 0


class RebootCommand(SbinCommand):
    """Reboot the system."""
    name = "reboot"
    description = "Reboot the system"
    usage = "reboot [-n] [-w] [-d] [-f]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        print("[*] reboot: System rebooting", file=sys.stderr)
        return 0


class ShutdownCommand(SbinCommand):
    """Shut down or reboot the system."""
    name = "shutdown"
    description = "Shut down or reboot the system"
    usage = "shutdown [-h] [-r] [-c] [-k] [-n] time [message]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("shutdown: missing time operand", file=sys.stderr)
            return 1
        time = args[0]
        msg = " ".join(args[1:]) if len(args) > 1 else "System going down"
        print(f"[*] shutdown: scheduled for {time} -- {msg}", file=sys.stderr)
        return 0


class GettyCommand(SbinCommand):
    """Virtual terminal manager."""
    name = "getty"
    description = "Virtual terminal manager (line-by-line login prompt)"
    usage = "getty [-HHhLlNff] [-w] [-i] [-l] [-t] line [baud_rate]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        print("[*] getty: waiting for login...", file=sys.stderr)
        return 0


class LiloCommand(SbinCommand):
    """ loader installer."""
    name = "lilo"
    description = "Install the  loader (LILO) boot manager"
    usage = "lilo [-A|-E|-I|-J|-R|-W] [-b device] [-c config] [-d delay] [-D label] [-f file] [-i boot] [-I label] [-l] [-m map] [-P fix] [-q] [-r root] [-s file] [-S file] [-t] [-v]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        print("LILO version 24.2")
        print("LILO: installing boot loader on /dev/sda")
        print("[*] lilo: boot loader installed")
        return 0


class FastbootCommand(SbinCommand):
    """Reboot without checking filesystems."""
    name = "fastboot"
    description = "Reboot the system without checking filesystems"
    usage = "fastboot [-n] [-w] [-d] [-f]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        print("[*] fastboot: rebooting without filesystem check", file=sys.stderr)
        return 0


class FasthaltCommand(SbinCommand):
    """Halt without checking filesystems."""
    name = "fasthalt"
    description = "Halt the system without checking filesystems"
    usage = "fasthalt [-n] [-w] [-d] [-f]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        print("[*] fasthalt: halting without filesystem check", file=sys.stderr)
        return 0


class UpdateCommand(SbinCommand):
    """Update boot block files."""
    name = "update"
    description = "Periodically update /etc/utmp and /var/log/wtmp"
    usage = "update [-s seconds] [-f frequency] [-b burst] [-i interval] [-w]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        print("[*] update: starting periodic updates")
        return 0
