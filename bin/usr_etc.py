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
UmerOS /usr/etc - System Configuration Hierarchy
=================================================
TLDP /usr: Another directory for configuration files. Virtually unused now.
"""

from __future__ import annotations

from core.command import Command


class UsrEtcCommand(Command):
    """System-wide configuration (usr/etc)."""

    name = "usr-etc"
    description = "/usr/etc - system-wide configuration (rarely used)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/etc/ - System-wide configuration\n"
            "  Theoretically for configuration files shared across hosts.\n"
            "  Virtually unused on modern systems.\n"
            "  Preferred location: /etc/ for host-specific config,\n"
            "  /usr/share/etc/ for shareable config.\n"
        )


class UsrEtcDefaultCommand(Command):
    """Default values for programs."""

    name = "usr-etc-default"
    description = "/usr/etc/default - default program values"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/etc/default/ - Default configuration values\n"
            "  Used to store default settings for programs.\n"
            "  Similar to /etc/default/ but for read-only /usr.\n"
        )


class UsrEtcProfileCommand(Command):
    """System-wide profile scripts."""

    name = "usr-etc-profile"
    description = "/usr/etc/profile - system-wide shell profile"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/etc/profile.d/ - System-wide shell initialization\n"
            "  Scripts executed by login shells.\n"
            "  Similar to /etc/profile.d/ but for /usr.\n"
        )
