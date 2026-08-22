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
UmerOS /usr/libexec Hierarchy Commands
========================================
FHS 3.0 §4.2.6: Binaries run by other programs.

This directory contains program binaries that are not meant to be
executed directly by the shell or users. These binaries are used
internally by programs and are not typically invoked directly.
"""

from __future__ import annotations

from core.command import Command


# ─── Libexec Binaries ────────────────────────────────────────────────────────


class LIBEXECCommand(Command):
    """Display /usr/libexec contents."""

    name = "libexec"
    description = "Display /usr/libexec - binaries run by other programs"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/libexec:\n"
            "  Binaries executed internally by other programs\n"
            "  Not invoked directly by users or shell\n"
            "  Examples: pppd plugins, mail agent internals\n"
            "  Architecture-specific subdirectories allowed\n"
        )


class PPPODCommand(Command):
    """PPPoE daemon helper."""

    name = "pppoe-discovery"
    description = "PPPoE discovery daemon helper"
    category = "network"
    privileges = ["user"]

    def execute(self, *args):
        return "pppoe-discovery: PPPoE discovery helper (simulated)\n"


class SENDMAILCommand(Command):
    """Sendmail binary (internal)."""

    name = "sendmail.libexec"
    description = "Sendmail - internal mail transfer agent binary"
    category = "system"
    privileges = ["root"]

    def execute(self, *args):
        return "sendmail: Mail transfer agent (internal binary, simulated)\n"


class LPDCCommand(Command):
    """LPRng printer spooler helper."""

    name = "lpd.conf"
    description = "LPRng printer spooler configuration helper"
    category = "system"
    privileges = ["root"]

    def execute(self, *args):
        return "lpd.conf: Printer spooler helper (simulated)\n"


class MINIUPNPCCommand(Command):
    """miniupnpd UPnP helper."""

    name = "miniupnpd"
    description = "miniupnpd - UPnP/NAT-PMP port mapping daemon helper"
    category = "network"
    privileges = ["root"]

    def execute(self, *args):
        return "miniupnpd: UPnP port mapping helper (simulated)\n"
