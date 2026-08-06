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


# ─── Local Share - Color Management (FHS 3.0 §4.11.3) ─────────────────────


class LOCALSHARECOLORCommand(Command):
    """Display /usr/local/share/color profiles."""

    name = "local-share-color"
    description = "Display /usr/local/share/color profile directory"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/share/color/\n"
            "  FHS 3.0 §4.11.3: Required if /usr/share/color exists\n"
            "  colord/     - Color profiles (local installs)\n"
            "  icc/        - ICC color profiles\n"
            "  Used by: colord, sane, printing systems\n"
            "  Not managed by the package manager\n"
        )


# ─── Local Share - SGML (FHS 3.0 §4.11.11) ──────────────────────────────────


class LOCALSHARESGMLCommand(Command):
    """Display /usr/local/share/sgml contents."""

    name = "local-share-sgml"
    description = "Display /usr/local/share/sgml contents"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/share/sgml/\n"
            "  FHS 3.0 §4.11.11: Local SGML data files\n"
            "  docbook/    - Local DocBook DTDs and stylesheets\n"
            "  dsssl/      - Local DSSSL stylesheets\n"
            "  catalog     - Local SGML catalog file\n"
            "  Not managed by the package manager\n"
        )


# ─── Local Share - XML (FHS 3.0 §4.11.12) ───────────────────────────────────


class LOCALSHAREXMLCommand(Command):
    """Display /usr/local/share/xml contents."""

    name = "local-share-xml"
    description = "Display /usr/local/share/xml contents"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/share/xml/\n"
            "  FHS 3.0 §4.11.12: Local XML data files\n"
            "  docbook/    - Local DocBook XML catalogs and DTDs\n"
            "  entity/     - Local XML entity definitions\n"
            "  catalog     - Local XML catalog file\n"
            "  Not managed by the package manager\n"
        )


# ─── Local Share - Templates (FHS 3.0 §4.11.13) ─────────────────────────────


class LOCALSHARETEMPLATESCommand(Command):
    """Display /usr/local/share/templates contents."""

    name = "local-share-templates"
    description = "Display /usr/local/share/templates contents"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/share/templates/\n"
            "  FHS 3.0 §4.11.13: Local default configuration templates\n"
            "  Contains template files for local applications\n"
            "  Used as starting points for new configurations\n"
            "  Not managed by the package manager\n"
        )
