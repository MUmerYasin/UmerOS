"""
UmerOS /usr/share/doc Hierarchy Commands
==========================================
FHS 3.0 §4.11.5: Documentation files.

Software documentation should be placed in /usr/share/doc/<pkg>
where <pkg> is the package name. This directory contains README,
CHANGES, LICENSE, and other documentation files.
"""

from __future__ import annotations

from core.command import Command


# ─── Documentation ───────────────────────────────────────────────────────────


class DOCDIRCommand(Command):
    """Display /usr/share/doc contents."""

    name = "doc-dir"
    description = "Display /usr/share/doc documentation directory"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/doc:\n"
            "  Per-package documentation\n"
            "  Format: /usr/share/doc/<package-name>/\n"
            "  Files: README, CHANGELOG, LICENSE, AUTHORS\n"
            "  Not mandatory - packages may omit docs\n"
            "  No binary files, only text and images\n"
        )


class LSCOMMAND(Command):
    """List installed package documentation."""

    name = "doc-list"
    description = "List installed package documentation"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "Package documentation:\n"
            "  coreutils/README\n"
            "  bash/README, CHANGES\n"
            "  gcc/README, COPYING, CHANGELOG\n"
            "  glibc/README, INSTALL, COPYING.LIB\n"
            "  openssl/README, CHANGES, LICENSE\n"
        )


class PKGDOCCOMMAND(Command):
    """Display documentation for a package."""

    name = "pkg-doc"
    description = "Display documentation for an installed package"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: pkg-doc <package>\n"
        return (
            f"/usr/share/doc/{args[0]}:\n"
            f"  README    - Package description\n"
            f"  CHANGELOG - Version history\n"
            f"  LICENSE   - Software license\n"
            f"  AUTHORS   - Contributors\n"
        )


class PKGCHANGESCommand(Command):
    """Display changelog for a package."""

    name = "pkg-changes"
    description = "Display changelog for an installed package"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: pkg-changes <package>\n"
        return (
            f"/usr/share/doc/{args[0]}/CHANGELOG:\n"
            f"  Version 1.0 - Initial release\n"
            f"  Version 1.1 - Bug fixes\n"
            f"  Version 1.2 - New features\n"
        )
