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
UmerOS /usr/share/ppd Hierarchy Commands
==========================================
FHS 3.0 §4.11.10: Printer definitions (optional).

This directory contains PostScript Printer Description (PPD)
files used by printing systems to configure printers.
"""

from __future__ import annotations

from core.command import Command


# ─── PPD Printer Definitions ─────────────────────────────────────────────────


class PPDDIRCommand(Command):
    """Display /usr/share/ppd contents."""

    name = "ppd-dir"
    description = "Display /usr/share/ppd - printer definitions"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/ppd:\n"
            "  PostScript Printer Description (PPD) files\n"
            "  Used by CUPS and other print systems\n"
            "  Format: <manufacturer>/<model>.ppd\n"
            "  Defines printer capabilities and options\n"
        )


class LPADMINCommand(Command):
    """Printer administration."""

    name = "lpadmin"
    description = "CUPS printer administration"
    category = "system"
    privileges = ["root"]

    def execute(self, *args):
        if not args:
            return "Usage: lpadmin [options]\n"
        return f"lpadmin: Configuring printer with PPD (simulated)\n"


class LPINFOCommand(Command):
    """List available printers and PPDs."""

    name = "lpinfo"
    description = "List available printers and PPD drivers"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "Available PPDs:\n"
            "  generic/PPD\n"
            "  HP/HP_LaserJet.ppd\n"
            "  EPSON/Epson_L360.ppd\n"
            "  Canon/Canon_LBP2900.ppd\n"
        )


class FOOMATICCommand(Command):
    """Foomatic printer database."""

    name = "foomatic"
    description = "Foomatic - printer configuration database"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "Foomatic printer database:\n"
            "  Drivers: /usr/share/ppd/foomatic/\n"
            "  Supported printers: 4000+\n"
            "  Driver: hpijs, PostScript, PCL\n"
        )
