"""
UmerOS /usr/share/locale Hierarchy Commands
=============================================
FHS 3.0 §4.11.8: Locale information.

This directory contains locale data files. Each subdirectory
represents a locale, containing LC_* category data.
"""

from __future__ import annotations

from core.command import Command


# ─── Locale Data ─────────────────────────────────────────────────────────────


class LOCALEDIRCommand(Command):
    """Display /usr/share/locale contents."""

    name = "locale-dir"
    description = "Display /usr/share/locale - locale data"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/locale:\n"
            "  Per-locale data directories\n"
            "  Format: /usr/share/locale/<lang>/\n"
            "  Contains: LC_MESSAGES, LC_COLLATE, LC_TIME, etc.\n"
            "  Message catalogs: .mo files (compiled gettext)\n"
        )


class LOCALELISTCommand(Command):
    """List installed locales."""

    name = "locale-list"
    description = "List installed locales"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "Installed locales:\n"
            "  en_US.UTF-8  - English (United States)\n"
            "  en_GB.UTF-8  - English (United Kingdom)\n"
            "  fr_FR.UTF-8  - French (France)\n"
            "  de_DE.UTF-8  - German (Germany)\n"
            "  es_ES.UTF-8  - Spanish (Spain)\n"
            "  ar_SA.UTF-8  - Arabic (Saudi Arabia)\n"
            "  ja_JP.UTF-8  - Japanese (Japan)\n"
            "  zh_CN.UTF-8  - Chinese (Simplified)\n"
        )


class GETTEXTCommand(Command):
    """GNU gettext internationalization."""

    name = "gettext"
    description = "GNU gettext - translate messages"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: gettext <domain> <message>\n"
        return f"gettext: Translating message from /usr/share/locale (simulated)\n"


class MSGFMTCommand(Command):
    """Compile message catalogs."""

    name = "msgfmt"
    description = "Compile .po message catalog to .mo binary"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: msgfmt <input.po> -o <output.mo>\n"
        return f"msgfmt: Compiling message catalog (simulated)\n"


class MSGUNFMTCommand(Command):
    """Uncompile message catalogs."""

    name = "msgunfmt"
    description = "Uncompile .mo message catalog to .po"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: msgunfmt <input.mo>\n"
        return f"msgunfmt: Decompiling message catalog (simulated)\n"
