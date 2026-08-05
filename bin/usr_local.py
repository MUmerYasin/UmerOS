"""
UmerOS /usr/local Hierarchy Commands
======================================
TLDP /usr/local: Locally installed software.

This includes:
  - Local binaries not part of the distribution
  - Local configuration files
  - Local libraries
  - Local share data
"""

from __future__ import annotations

from ..core.command import Command


# ─── Local Binaries ──────────────────────────────────────────────────────────


class LOCALBINCommand(Command):
    """Display /usr/local/bin contents."""

    name = "local-bin"
    description = "Display /usr/local/bin contents"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/bin:\n"
            "  Locally installed binaries\n"
            "  Not managed by the package manager\n"
            "  Highest priority in PATH\n"
        )


# ─── Local Configuration ────────────────────────────────────────────────────


class LOCALETCCommand(Command):
    """Display /usr/local/etc configuration."""

    name = "local-etc"
    description = "Display /usr/local/etc configuration files"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/etc:\n"
            "  Locally installed configuration files\n"
            "  Not managed by the package manager\n"
            "  Manually configured by administrator\n"
        )


# ─── Local Libraries ─────────────────────────────────────────────────────────


class LOCALLIBCommand(Command):
    """Display /usr/local/lib contents."""

    name = "local-lib"
    description = "Display /usr/local/lib contents"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/lib:\n"
            "  Locally installed libraries\n"
            "  Not managed by the package manager\n"
            "  Shared libraries for local programs\n"
        )


# ─── Local Share ──────────────────────────────────────────────────────────────


class LOCALSHARECommand(Command):
    """Display /usr/local/share contents."""

    name = "local-share"
    description = "Display /usr/local/share contents"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/share:\n"
            "  Architecture-independent local data\n"
            "  Man pages, docs, data files\n"
            "  Not managed by the package manager\n"
        )


# ─── Local Sbin ──────────────────────────────────────────────────────────────


class LOCALSBINCommand(Command):
    """Display /usr/local/sbin contents."""

    name = "local-sbin"
    description = "Display /usr/local/sbin contents"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/sbin:\n"
            "  Locally installed system administration binaries\n"
            "  Not managed by the package manager\n"
            "  For root/admin use only\n"
        )


# ─── Local Include ───────────────────────────────────────────────────────────


class LOCALINCLUDECommand(Command):
    """Display /usr/local/include contents."""

    name = "local-include"
    description = "Display /usr/local/include header files"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/include:\n"
            "  C/C++ header files for local software\n"
            "  Not managed by the package manager\n"
            "  Used during compilation of local software\n"
        )


# ─── Local Man Pages ─────────────────────────────────────────────────────────


class LOCALMANCommand(Command):
    """Display /usr/local/man contents."""

    name = "local-man"
    description = "Display /usr/local/man contents"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/man:\n"
            "  Man pages for locally installed software\n"
            "  Not managed by the package manager\n"
            "  Sections: man1, man3, man5, man7, man8\n"
        )


# ─── Local Documentation ─────────────────────────────────────────────────────


class LOCALDOCCommand(Command):
    """Display /usr/local/doc contents."""

    name = "local-doc"
    description = "Display /usr/local/doc contents"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/doc:\n"
            "  Documentation for locally installed software\n"
            "  README, CHANGELOG, LICENSE files\n"
            "  Not managed by the package manager\n"
        )


# ─── Local Source ─────────────────────────────────────────────────────────────


class LOCALSRCCommand(Command):
    """Display /usr/local/src contents."""

    name = "local-src"
    description = "Display /usr/local/src contents"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/src:\n"
            "  Source code for locally compiled software\n"
            "  Build directories\n"
            "  Not managed by the package manager\n"
        )
