"""
UmerOS i18n Manager (/usr/share/i18n)
======================================
Internationalization data and locale definitions.

Reference: Filesystem Hierarchy - /usr/share/i18n
  /usr/share/i18n contains locale definition files and
  character set definitions used by the C library.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ─── Constants ───────────────────────────────────────────────────────────────

I18N_PATH = "/usr/share/i18n"

CHARMAPS_PATH = "/usr/share/i18n/charmaps"
LOCALEDATA_PATH = "/usr/share/i18n/locales"
TRANSLATIONS_PATH = "/usr/share/i18n/translations"

CHARMAPS = [
    "UTF-8", "ISO-8859-1", "ISO-8859-2", "ISO-8859-3", "ISO-8859-4",
    "ISO-8859-5", "ISO-8859-6", "ISO-8859-7", "ISO-8859-8", "ISO-8859-9",
    "ISO-8859-10", "ISO-8859-11", "ISO-8859-13", "ISO-8859-14", "ISO-8859-15",
    "ISO-8859-16", "KOI8-R", "KOI8-U", "KOI8-T", "CP1250", "CP1251",
    "CP1252", "CP1253", "CP1254", "CP1255", "CP1256", "CP1257", "CP1258",
    "GB2312", "GBK", "GB18030", "BIG5", "EUC-JP", "EUC-KR", "SHIFT_JIS",
    "ISO-2022-JP", "ISO-2022-KR", "ISO-2022-CN", "TIS-620", "VISCII",
    "ARMSCII-8", "GEORGIAN-PS", "PT154", "RK1048", "MULELAO-1",
    "TCVN-5712", "GEORGIAN", "TCVN", "VPS",
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class CharsetType(IntEnum):
    """Character set types."""
    SINGLE_BYTE = 1
    MULTI_BYTE = 2
    DOUBLE_BYTE = 3
    VARIABLE = 4


class I18nStatus(IntEnum):
    """i18n data status."""
    ACTIVE = 1
    DEPRECATED = 2
    REMOVED = 3
    BROKEN = 4


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class CharmapEntry:
    """A character map entry."""
    name: str
    path: str
    charset_type: CharsetType = CharsetType.SINGLE_BYTE
    encoding: str = ""
    description: str = ""
    languages: List[str] = field(default_factory=list)
    status: I18nStatus = I18nStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "charset_type": self.charset_type.name,
            "encoding": self.encoding,
            "description": self.description,
            "languages": self.languages,
            "status": self.status.name,
        }


@dataclass
class LocaleDefinition:
    """A locale definition file."""
    name: str
    path: str
    language: str = ""
    territory: str = ""
    codeset: str = "UTF-8"
    description: str = ""
    categories: List[str] = field(default_factory=list)
    status: I18nStatus = I18nStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "language": self.language,
            "territory": self.territory,
            "codeset": self.codeset,
            "description": self.description,
            "categories": self.categories,
            "status": self.status.name,
        }


@dataclass
class TranslationEntry:
    """A translation entry."""
    name: str
    path: str
    language: str = ""
    description: str = ""
    status: I18nStatus = I18nStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "language": self.language,
            "description": self.description,
            "status": self.status.name,
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_i18n_manager: Optional["I18nManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class I18nManager:
    """Manages /usr/share/i18n - internationalization data."""

    def __init__(self) -> None:
        self._charmaps: Dict[str, CharmapEntry] = {}
        self._locales: Dict[str, LocaleDefinition] = {}
        self._translations: Dict[str, TranslationEntry] = {}
        self._default_charmap: str = "UTF-8"
        self._initialize_default_charmaps()

    def _initialize_default_charmaps(self) -> None:
        """Initialize with common charmaps."""
        for name in CHARMAPS:
            charset_type = CharsetType.SINGLE_BYTE
            if name.startswith("UTF"):
                charset_type = CharsetType.VARIABLE
            elif name.startswith("GB") or name.startswith("BIG5"):
                charset_type = CharsetType.DOUBLE_BYTE
            elif name.startswith("EUC") or name.startswith("SHIFT"):
                charset_type = CharsetType.MULTI_BYTE
            entry = CharmapEntry(
                name=name,
                path=f"/usr/share/i18n/charmaps/{name}",
                charset_type=charset_type,
                description=f"Character set: {name}",
            )
            self._charmaps[name] = entry

    def get_charmap(self, name: str) -> Optional[CharmapEntry]:
        """Get a charmap by name."""
        return self._charmaps.get(name)

    def list_charmaps(self, charset_type: Optional[CharsetType] = None) -> List[CharmapEntry]:
        """List all charmaps, optionally filtered by type."""
        charmaps = list(self._charmaps.values())
        if charset_type is not None:
            charmaps = [c for c in charmaps if c.charset_type == charset_type]
        return sorted(charmaps, key=lambda c: c.name)

    def search_charmaps(self, query: str) -> List[CharmapEntry]:
        """Search charmaps by name."""
        query_lower = query.lower()
        return [c for c in self._charmaps.values() if query_lower in c.name.lower()]

    def get_locale(self, name: str) -> Optional[LocaleDefinition]:
        """Get a locale definition by name."""
        return self._locales.get(name)

    def list_locales(self, language: Optional[str] = None) -> List[LocaleDefinition]:
        """List all locale definitions."""
        locales = list(self._locales.values())
        if language is not None:
            locales = [l for l in locales if l.language == language]
        return sorted(locales, key=lambda l: l.name)

    def register_locale(self, locale: LocaleDefinition) -> None:
        """Register a locale definition."""
        self._locales[locale.name] = locale

    def get_translation(self, name: str) -> Optional[TranslationEntry]:
        """Get a translation by name."""
        return self._translations.get(name)

    def list_translations(self) -> List[TranslationEntry]:
        """List all translations."""
        return sorted(self._translations.values(), key=lambda t: t.name)

    def register_translation(self, translation: TranslationEntry) -> None:
        """Register a translation."""
        self._translations[translation.name] = translation

    def set_default_charmap(self, name: str) -> bool:
        """Set the default charmap."""
        if name in self._charmaps:
            self._default_charmap = name
            return True
        return False

    def get_default_charmap(self) -> str:
        """Get the default charmap."""
        return self._default_charmap

    def get_statistics(self) -> Dict[str, Any]:
        """Get i18n statistics."""
        by_type: Dict[str, int] = {}
        for cm in self._charmaps.values():
            t = cm.charset_type.name
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total_charmaps": len(self._charmaps),
            "total_locales": len(self._locales),
            "total_translations": len(self._translations),
            "by_type": by_type,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "charmaps": {k: v.to_dict() for k, v in self._charmaps.items()},
            "locales": {k: v.to_dict() for k, v in self._locales.items()},
            "translations": {k: v.to_dict() for k, v in self._translations.items()},
            "default_charmap": self._default_charmap,
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_i18n_manager() -> I18nManager:
    """Get or create the global I18nManager instance."""
    global _global_i18n_manager
    if _global_i18n_manager is None:
        _global_i18n_manager = I18nManager()
    return _global_i18n_manager


def initialize() -> I18nManager:
    """Initialize and return the global I18nManager."""
    return get_global_i18n_manager()


def refresh() -> I18nManager:
    """Refresh the global I18nManager."""
    global _global_i18n_manager
    _global_i18n_manager = I18nManager()
    return _global_i18n_manager
