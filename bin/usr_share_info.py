"""
UmerOS /usr/share/info Hierarchy Commands
==========================================
FHS 3.0 §4.11.7: GNU Info system documentation.

This directory contains Info pages, the GNU documentation system.
Info pages are typically generated from Texinfo source.
"""

from __future__ import annotations

from core.command import Command


# ─── Info System ─────────────────────────────────────────────────────────────


class INFODIRCommand(Command):
    """Display /usr/share/info contents."""

    name = "info-dir"
    description = "Display /usr/share/info - GNU Info documentation"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/info:\n"
            "  GNU Info documentation pages\n"
            "  Format: <package>.info\n"
            "  Index: dir (top-level directory)\n"
            "  Read by: info, pinfo, Emacs\n"
            "  Generated from Texinfo source\n"
        )


class INFODIR2Command(Command):
    """Display Info directory listing."""

    name = "info-pages"
    description = "List installed Info pages"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "Installed Info pages:\n"
            "  autoconf.info    - GNU Autoconf\n"
            "  automake.info    - GNU Automake\n"
            "  bash.info        - Bash Reference Manual\n"
            "  coreutils.info   - GNU Core Utilities\n"
            "  gcc.info         - GCC Documentation\n"
            "  glibc.info       - GNU C Library\n"
            "  make.info        - GNU Make\n"
            "  texinfo.info     - Texinfo\n"
        )


class MAKEINFOCommand(Command):
    """Generate Info files from Texinfo."""

    name = "makeinfo"
    description = "Convert Texinfo to Info format"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: makeinfo <file.texi>\n"
        return f"makeinfo: Converting {args[0]} to Info format (simulated)\n"
