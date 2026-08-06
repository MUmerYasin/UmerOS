"""
UmerOS /usr/share/dict Hierarchy Commands
==========================================
FHS 3.0 §4.11.4: Word lists.

This directory contains the list of words available on the system.
Used by spell-checkers and word games.
"""

from __future__ import annotations

from core.command import Command


# ─── Word Lists ──────────────────────────────────────────────────────────────


class DICTCommand(Command):
    """Look up word in word list."""

    name = "look"
    description = "Look up word in word list (dictionary)"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: look <string>\n"
        word = args[0].upper()
        return f"look: {word} found in /usr/share/dict/words (simulated)\n"


class DICLSCommand(Command):
    """List available dictionaries."""

    name = "dict-ls"
    description = "List available dictionaries in /usr/share/dict"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/dict:\n"
            "  words    - Common English words (72,000+)\n"
            "  american-english - American English word list\n"
            "  british-english  - British English word list\n"
            "  propernames      - Proper names\n"
            "  web2             - Webster's Second International\n"
        )


class ISpellCommand(Command):
    """Spell checker using dictionary."""

    name = "ispell"
    description = "Interactive spell checker"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: ispell <file>\n"
        return f"ispell: Checking {args[0]} against /usr/share/dict/words (simulated)\n"


class ASpellCommand(Command):
    """GNU spell checker."""

    name = "aspell"
    description = "GNU Aspell spell checker"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: aspell <command> [options]\n"
        return f"aspell: Spell checking with /usr/share/dict/words (simulated)\n"


class HUNSPELLCommand(Command):
    """Hunspell spell checker."""

    name = "hunspell"
    description = "Hunspell spell checker and morphological analyzer"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: hunspell [options] [file]\n"
        return f"hunspell: Spell checking with dictionary (simulated)\n"
