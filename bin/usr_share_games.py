"""
UmerOS /usr/share/games Hierarchy Commands
============================================
FHS 3.0 §4.11.6: Static game data files.

This directory contains static, read-only game data. Game binaries
go in /usr/games or /usr/bin; only architecture-independent data
belongs here.
"""

from __future__ import annotations

from ..core.command import Command


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
