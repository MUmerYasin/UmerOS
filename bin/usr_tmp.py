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
UmerOS /usr/tmp - User Space Temporary Files
=============================================
TLDP /usr: User space temporary files. Not found on modern distributions.
Was created as a consequence of UNIX heritage.
"""

from __future__ import annotations

from core.command import Command


class UsrTmpCommand(Command):
    """User space temporary directory."""

    name = "usr-tmp"
    description = "/usr/tmp - user space temporary files (legacy)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/tmp/ - User space temporary files\n"
            "  Legacy location, rarely used on modern systems.\n"
            "  Modern equivalent: /var/tmp/ or /tmp/\n"
            "  Original from UNIX heritage.\n"
        )


class UsrTmpLinkCommand(Command):
    """usr/tmp symlink management."""

    name = "usr-tmp-link"
    description = "Manage /usr/tmp symlinks"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/tmp -> /var/tmp (symlink)\n"
            "  On modern systems, /usr/tmp is typically a symlink\n"
            "  to /var/tmp for backward compatibility.\n"
        )
