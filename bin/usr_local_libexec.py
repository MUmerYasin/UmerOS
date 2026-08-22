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
UmerOS /usr/local/libexec Hierarchy Commands
=============================================
FHS 3.0 §4.2.6: Locally installed program binaries run by other programs.

Binaries in /usr/local/libexec are not part of the base system and
are not managed by the package manager. They are used internally by
locally installed software and should not be invoked directly by users.
"""

from __future__ import annotations

from core.command import Command


class LocalLibexecCommand(Command):
    """Display /usr/local/libexec contents."""

    name = "local-libexec"
    description = "Display /usr/local/libexec - locally installed internal binaries"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/libexec:\n"
            "  Internal binaries for locally installed software\n"
            "  Not invoked directly by users or shell\n"
            "  Examples: plugin helpers, mail agent internals\n"
            "  Architecture-specific subdirectories allowed\n"
            "  Not managed by the package manager\n"
        )


class LocalLibexecPluginCommand(Command):
    """Plugin helper binaries in /usr/local/libexec."""

    name = "local-libexec-plugin"
    description = "Plugin helper binaries in /usr/local/libexec"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/local/libexec/plugins/\n"
            "  Plugin helper binaries for locally installed software\n"
            "  Examples:\n"
            "    git-core/      - Git internal helpers (rebase, am, ...)\n"
            "    openssh/       - SSH internal helpers\n"
            "    python3/       - Python module helpers\n"
            "    firefox/       - Firefox internal components\n"
            "    gdb/           - GDB helper scripts\n"
            "  Only invoked by parent program, never directly\n"
        )


class LocalLibexecMailCommand(Command):
    """Mail subsystem internal binaries."""

    name = "local-libexec-mail"
    description = "Mail subsystem internal binaries in /usr/local/libexec"
    category = "system"
    privileges = ["root"]

    def execute(self, *args):
        return (
            "/usr/local/libexec/mail/\n"
            "  Mail subsystem internal binaries (if locally compiled)\n"
            "  Examples:\n"
            "    sendmail     - Local sendmail binary\n"
            "    mail.local   - Local delivery agent\n"
            "    postqueue    - Postfix queue management\n"
            "    newaliases   - Rebuild alias database\n"
            "  Only invoked by MTA, never directly\n"
        )


class LocalLibexecNetworkCommand(Command):
    """Network service internal helpers."""

    name = "local-libexec-network"
    description = "Network service internal helpers in /usr/local/libexec"
    category = "network"
    privileges = ["root"]

    def execute(self, *args):
        return (
            "/usr/local/libexec/network/\n"
            "  Network service internal helpers (locally compiled)\n"
            "  Examples:\n"
            "    pppoe-relay  - PPPoE relay helper\n"
            "    xl2tpd       - L2TP daemon helper\n"
            "    openvpn      - OpenVPN plugin helpers\n"
            "    wireguard    - WireGuard userspace tools\n"
            "  Only invoked by network daemons, never directly\n"
        )
