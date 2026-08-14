"""
UmerOS /usr/doc - Documentation Hierarchy
==========================================
TLDP /usr: The central documentation directory.
Now located at /usr/share/doc, symlinked from /usr/doc.
"""

from __future__ import annotations

from core.command import Command


class DocCommand(Command):
    """Browse package documentation."""

    name = "doc"
    description = "Browse /usr/share/doc package documentation"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/doc/ -> /usr/share/doc/\n"
            "  Package-specific documentation directories.\n"
            "  Each package installs docs under its name directory.\n"
            "  Typically contains README, changelogs, examples.\n"
        )


class PkgDocCommand(Command):
    """List documentation for installed packages."""

    name = "pkg-doc"
    description = "List documentation files for installed packages"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/doc/ contents:\n"
            "  bash/          - Bash documentation\n"
            "  coreutils/     - GNU Coreutils documentation\n"
            "  glibc/         - GNU C Library documentation\n"
            "  doc/           - kernel documentation\n"
            "  openssh/       - OpenSSH documentation\n"
            "  python3/       - Python 3 documentation\n"
        )


class UsrInfoCommand(Command):
    """GNU Info documentation reader (symlinked from /usr/info)."""

    name = "usr-info"
    description = "GNU Info documentation reader"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return (
                "Usage: info [menu-item]\n"
                "Read Info documentation pages.\n"
                "Info pages are now in /usr/share/info/\n"
            )
        return f"info: {args[0]}: Info page not found\n"


class InfoDirCommand(Command):
    """Info directory file."""

    name = "infodir"
    description = "Info directory listing"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/info/ - GNU Info documentation pages\n"
            "  dir       - Top-level directory\n"
            "  bash.info  - Bash manual\n"
            "  coreutils.info - Coreutils manual\n"
            "  gcc.info  - GCC manual\n"
        )
