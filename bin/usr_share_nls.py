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
UmerOS /usr/share/nls Hierarchy Commands
==========================================
FHS 3.0 §4.11.9: Native Language Support (NLS).

This directory contains Native Language Support (NLS) catalogs
used by older libc5 systems. Modern systems use /usr/share/locale.
"""

from __future__ import annotations

from core.command import Command


# ─── NLS Catalogs ────────────────────────────────────────────────────────────


class NLSCommand(Command):
    """Display /usr/share/nls contents."""

    name = "nls-dir"
    description = "Display /usr/share/nls - Native Language Support"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/nls:\n"
            "  Native Language Support catalogs\n"
            "  Legacy format from libc5 era\n"
            "  Modern systems use /usr/share/locale\n"
            "  Format: .cat files\n"
            "  Used by: catopen/catgets/catclose API\n"
        )


class NLSLISTCommand(Command):
    """List installed NLS catalogs."""

    name = "nls-list"
    description = "List installed NLS catalogs"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "NLS catalogs:\n"
            "  en.cat    - English\n"
            "  fr.cat    - French\n"
            "  de.cat    - German\n"
            "  es.cat    - Spanish\n"
            "  ja.cat    - Japanese\n"
            "  (legacy format - prefer /usr/share/locale)\n"
        )
