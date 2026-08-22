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
UmerOS /usr/share/games Hierarchy Commands
============================================
FHS 3.0 §4.11.6: Static game data files.

This directory contains static, read-only game data. Game binaries
go in /usr/games or /usr/bin; only architecture-independent data
belongs here.
"""

from __future__ import annotations

from core.command import Command


# ─── Game Data ───────────────────────────────────────────────────────────────


class GAMEDATADIRCommand(Command):
    """Display /usr/share/games contents."""

    name = "game-data"
    description = "Display /usr/share/games - static game data"
    category = "games"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/games:\n"
            "  Architecture-independent game data\n"
            "  Read-only static data files\n"
            "  Examples: maps, levels, sounds, textures\n"
            "  NOT game binaries (those go in /usr/games)\n"
        )


class NETHACKCommand(Command):
    """Nethack game data."""

    name = "nethack-data"
    description = "NetHack game data files"
    category = "games"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "NetHack data:\n"
            "  /usr/share/games/nethack/\n"
            "    dat/      - Level data, des files\n"
            "    lib/      - Configuration, logos\n"
            "    save/     - Save game directory\n"
            "    info/     - Documentation\n"
        )


class MAHJOCommand(Command):
    """Mahjongg game data."""

    name = "mahjongg-data"
    description = "Mahjongg game tile data"
    category = "games"
    privileges = ["user"]

    def execute(self, *args):
        return "mahjongg-data: Tile images for Mahjongg (simulated)\n"
