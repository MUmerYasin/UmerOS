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
UmerOS /usr/share/color Hierarchy Commands
============================================
FHS 3.0 §4.11.3: Color management information.

This directory contains color profile and device information
for color management systems like Oy-Color Management.
"""

from __future__ import annotations

from core.command import Command


# ─── Color Profiles ──────────────────────────────────────────────────────────


class COLORPROFILESCommand(Command):
    """Display ICC color profiles."""

    name = "color-profiles"
    description = "Display ICC color profiles"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/color/icc:\n"
            "  ICC (International Color Consortium) color profiles\n"
            "  Device profiles for monitors, printers, cameras\n"
            "  Format: .icc, .icm\n"
            "  Managed by oyranos-color or colord\n"
        )


class COLORMANAGERCommand(Command):
    """Color management system status."""

    name = "colormgr"
    description = "Color management system status"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "Color Management:\n"
            "  Profile dir: /usr/share/color/icc/\n"
            "  Device data: /var/lib/color/\n"
            "  System: oyranos-color / colord\n"
            "  Profiles loaded: 3 (simulated)\n"
        )


class OYRANOSCommand(Command):
    """Oyranos color management system."""

    name = "oyranos-monitor"
    description = "Oyranos color management - monitor profile"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return "oyranos-monitor: Color profile for monitor (simulated)\n"
