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
UmerOS /bin/bash - The Bourne Again Shell
==========================================
TLDP /bin: bash is the most important shell in /bin.
If /bin/sh is not a true Bourne shell, it must be a hard or symbolic
link to the real shell command (bash).

Bash provides:
  - Command line editing
  - History
  - Tab completion
  - Job control
  - Programmable completion
  - Aliases and functions
  - Arithmetic expansion
  - Brace expansion
  - Extended pattern matching
"""

from __future__ import annotations

from core.command import Command


class BashCommand(Command):
    """Bourne Again Shell - the primary interactive shell."""

    name = "bash"
    description = "Bourne Again Shell - primary interactive shell"
    category = "shell"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] == "--version":
            return (
                "UmerOS bash, version 5.2.15(1)-release\n"
                "Copyright (C) 2022 Free Software Foundation, Inc.\n"
                "License GPLv3+: GNU GPL version 3 or later\n"
            )
        if args and args[0] == "--help":
            return (
                "Usage: bash [options] [file]\n"
                "  --version    Display version information\n"
                "  --help       Display this help\n"
                "  -c string    Read commands from string\n"
                "  -i           Interactive shell\n"
                "  -l           Login shell\n"
                "  -r           Restricted shell\n"
                "  -s           Read commands from stdin\n"
                "  -x           Print commands before execution\n"
            )
        return "bash: interactive shell not available in UmerOS (simulated)\n"


class ZshCommand(Command):
    """Z Shell - extended Bourne shell with improvements."""

    name = "zsh"
    description = "Z Shell - extended Bourne shell with improvements"
    category = "shell"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] == "--version":
            return "zsh 5.9 (x86_64-pc-gnu)\n"
        return "zsh: interactive shell not available in UmerOS (simulated)\n"


class KshCommand(Command):
    """Korn Shell - POSIX-compliant shell."""

    name = "ksh"
    description = "Korn Shell - POSIX-compliant shell"
    category = "shell"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] == "--version":
            return "ksh 93u+ 2012-08-01\n"
        return "ksh: interactive shell not available in UmerOS (simulated)\n"


class TcshCommand(Command):
    """TENEX C Shell - enhanced C shell with completion."""

    name = "tcsh"
    description = "TENEX C Shell - enhanced C shell with completion"
    category = "shell"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] == "--version":
            return "tcsh 6.24.01 (Astron) 2022-07-01\n"
        return "tcsh: interactive shell not available in UmerOS (simulated)\n"


class DashCommand(Command):
    """Debian Almquist Shell - lightweight POSIX shell."""

    name = "dash"
    description = "Debian Almquist Shell - lightweight POSIX shell"
    category = "shell"
    privileges = ["user"]

    def execute(self, *args):
        return "dash: POSIX shell not available in UmerOS (simulated)\n"


class FishCommand(Command):
    """Friendly Interactive Shell - user-friendly shell."""

    name = "fish"
    description = "Friendly Interactive Shell - user-friendly shell"
    category = "shell"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] == "--version":
            return "fish, version 3.6.0\n"
        return "fish: interactive shell not available in UmerOS (simulated)\n"


class MkshCommand(Command):
    """MirBSD Korn Shell - lightweight shell."""

    name = "mksh"
    description = "MirBSD Korn Shell - lightweight shell"
    category = "shell"
    privileges = ["user"]

    def execute(self, *args):
        return "mksh: shell not available in UmerOS (simulated)\n"


class BusyboxCommand(Command):
    """BusyBox - multi-call binary for embedded systems."""

    name = "busybox"
    description = "BusyBox - multi-call binary for embedded systems"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        if not args or args[0] in ("--help", "--usage"):
            return (
                "BusyBox v1.36.0 (2023-01-01 00:00:00 UTC) multi-call binary.\n"
                "Usage: busybox [function] [arguments]...\n"
                "   or: busybox --list\n"
                "   or: busybox --install [-a]\n"
            )
        if args[0] == "--list":
            return "Built-in commands: sh, ls, cat, echo, mkdir, rm, cp, mv, ...\n"
        func = args[0]
        return f"busybox: {func}: applet not found (simulated)\n"
