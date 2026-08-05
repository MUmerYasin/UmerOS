"""
UmerOS /usr/man - Manual Pages Hierarchy
=========================================
TLDP /usr/man: Manual pages organized in 8 sections.
Now located at /usr/share/man, symlinked from /usr/man.
"""

from __future__ import annotations

from ..core.command import Command


class ManCmdCommand(Command):
    """Display manual page for a command."""

    name = "man-cmd"
    description = "Display manual page for a command"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: man [section] command\n"
        cmd = args[-1]
        return (
            f"Manual page for {cmd}:\n"
            f"NAME\n    {cmd} - {cmd} command\n"
            f"SYNOPSIS\n    {cmd} [options] [arguments]\n"
            f"DESCRIPTION\n    Execute {cmd} command in UmerOS.\n"
            f"SEE ALSO\n    info, help\n"
        )


class ManDirCommand(Command):
    """Manual page directory listing."""

    name = "man-dir"
    description = "List /usr/share/man directory structure"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/man/ - Manual pages by section:\n"
            "  man1/ - User programs (ls, cat, echo, ...)\n"
            "  man2/ - System calls (open, read, write, ...)\n"
            "  man3/ - Library functions (printf, malloc, ...)\n"
            "  man4/ - Special files (sd, tty, ...)\n"
            "  man5/ - File formats (/etc/passwd, ...)\n"
            "  man6/ - Games (fortune, cowsay, ...)\n"
            "  man7/ - Miscellaneous (signal, regex, ...)\n"
            "  man8/ - System admin (mount, fsck, ...)\n"
        )


class ManPathCommand(Command):
    """Show manual page search path."""

    name = "manpath"
    description = "Show manual page search path"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "MANPATH=/usr/local/man:/usr/share/man:/usr/man\n"
            "Sections searched in order: 1 8 3 2 4 5 6 7 9 0 l n\n"
        )


class UsrAproposCommand(Command):
    """Search manual pages by keyword."""

    name = "usr-apropos"
    description = "Search manual page names and descriptions"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: apropos keyword\n"
        keyword = args[0]
        return (
            f"apropos: no manual entries for '{keyword}'\n"
            f"Try 'man -k {keyword}' or 'apropos {keyword}'.\n"
        )


class UsrWhatisCommand(Command):
    """Display manual page description."""

    name = "usr-whatis"
    description = "Display manual page description for a command"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: whatis command\n"
        return f"{args[0]} - {args[0]} command in UmerOS\n"
