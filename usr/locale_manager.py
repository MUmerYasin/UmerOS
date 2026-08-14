"""
UmerOS Locale Manager (/usr/share/locale)
==========================================
Locale data and translations.

Reference: Filesystem Hierarchy - /usr/share/locale
  /usr/share/locale contains locale data files used by the GNU
  C Library and other programs for internationalization.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ─── Constants ───────────────────────────────────────────────────────────────

LOCALE_PATH = "/usr/share/locale"

LOCALE_CATEGORIES = {
    "LC_MESSAGES": "Message translations",
    "LC_TIME": "Time and date formats",
    "LC_NUMERIC": "Numeric formats",
    "LC_MONETARY": "Currency formats",
    "LC_COLLATE": "Collation rules",
    "LC_CTYPE": "Character classification",
    "LC_IDENTIFICATION": "Locale identification",
    "LC_MEASUREMENT": "Measurement units",
    "LC_PAPER": "Paper sizes",
    "LC_TELEPHONE": "Telephone formats",
    "LC_NAME": "Name formats",
    "LC_ADDRESS": "Address formats",
}

COMMON_LOCALES = [
    "en_US", "en_GB", "en_AU", "en_CA", "en_IN",
    "fr_FR", "fr_CA", "fr_BE", "fr_CH",
    "de_DE", "de_AT", "de_CH", "de_LU",
    "es_ES", "es_MX", "es_AR", "es_CL", "es_CO",
    "it_IT", "it_CH",
    "pt_BR", "pt_PT",
    "nl_NL", "nl_BE",
    "ru_RU", "uk_UA",
    "zh_CN", "zh_TW", "zh_HK",
    "ja_JP", "ko_KR",
    "ar_SA", "ar_EG", "ar_AE",
    "hi_IN", "bn_IN", "ta_IN", "te_IN",
    "th_TH", "vi_VN", "id_ID",
    "pl_PL", "cs_CZ", "sk_SK", "hu_HU",
    "sv_SE", "da_DK", "no_NO", "fi_FI",
    "el_GR", "tr_TR", "he_IL",
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class LocaleCategory(IntEnum):
    """Locale categories."""
    MESSAGES = 1
    TIME = 2
    NUMERIC = 3
    MONETARY = 4
    COLLATE = 5
    CTYPE = 6
    IDENTIFICATION = 7
    MEASUREMENT = 8
    PAPER = 9
    TELEPHONE = 10
    NAME = 11
    ADDRESS = 12


class LocaleStatus(IntEnum):
    """Locale availability status."""
    AVAILABLE = 1
    PARTIAL = 2
    MISSING = 3
    BROKEN = 4


class TranslationStatus(IntEnum):
    """Translation completeness status."""
    COMPLETE = 1
    PARTIAL = 2
    UNTRANSLATED = 3


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class LocaleEntry:
    """A single locale definition."""
    name: str
    path: str
    language: str = ""
    territory: str = ""
    codeset: str = "UTF-8"
    status: LocaleStatus = LocaleStatus.AVAILABLE
    categories: List[LocaleCategory] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "language": self.language,
            "territory": self.territory,
            "codeset": self.codeset,
            "status": self.status.name,
            "categories": [c.name for c in self.categories],
            "description": self.description,
        }


@dataclass
class Translation:
    """A translation entry for a specific key."""
    key: str
    msgid: str
    msgstr: str
    context: str = ""
    plural_forms: List[str] = field(default_factory=list)
    status: TranslationStatus = TranslationStatus.COMPLETE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "msgid": self.msgid,
            "msgstr": self.msgstr,
            "context": self.context,
            "plural_forms": self.plural_forms,
            "status": self.status.name,
        }


@dataclass
class GettextDomain:
    """A gettext translation domain."""
    name: str
    path: str
    locales: Dict[str, str] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "locales": self.locales,
            "description": self.description,
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_locale_manager: Optional["LocaleManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class LocaleManager:
    """Manages /usr/share/locale - locale data and translations."""

    def __init__(self) -> None:
        self._locales: Dict[str, LocaleEntry] = {}
        self._domains: Dict[str, GettextDomain] = {}
        self._translations: Dict[str, Dict[str, Translation]] = {}
        self._default_locale: str = "en_US.UTF-8"
        self._initialize_default_locales()

    def _initialize_default_locales(self) -> None:
        """Initialize with common locales."""
        for locale_name in COMMON_LOCALES:
            parts = locale_name.split("_")
            language = parts[0] if len(parts) > 0 else ""
            territory = parts[1] if len(parts) > 1 else ""
            entry = LocaleEntry(
                name=locale_name,
                path=f"/usr/share/locale/{locale_name}",
                language=language,
                territory=territory,
                categories=[LocaleCategory.MESSAGES, LocaleCategory.TIME,
                            LocaleCategory.NUMERIC, LocaleCategory.MONETARY],
            )
            self._locales[locale_name] = entry

    def get_locale(self, name: str) -> Optional[LocaleEntry]:
        """Get a locale by name."""
        return self._locales.get(name)

    def list_locales(self, language: Optional[str] = None) -> List[LocaleEntry]:
        """List all locales, optionally filtered by language."""
        locales = list(self._locales.values())
        if language is not None:
            locales = [l for l in locales if l.language == language]
        return sorted(locales, key=lambda l: l.name)

    def search_locales(self, query: str) -> List[LocaleEntry]:
        """Search locales by name or description."""
        query_lower = query.lower()
        results = []
        for locale in self._locales.values():
            if (query_lower in locale.name.lower() or
                query_lower in locale.description.lower()):
                results.append(locale)
        return results

    def set_default_locale(self, locale_name: str) -> bool:
        """Set the default system locale."""
        if locale_name in self._locales:
            self._default_locale = locale_name
            return True
        return False

    def get_default_locale(self) -> str:
        """Get the default system locale."""
        return self._default_locale

    def register_domain(self, domain: GettextDomain) -> None:
        """Register a gettext domain."""
        self._domains[domain.name] = domain

    def get_domain(self, name: str) -> Optional[GettextDomain]:
        """Get a domain by name."""
        return self._domains.get(name)

    def list_domains(self) -> List[GettextDomain]:
        """List all gettext domains."""
        return sorted(self._domains.values(), key=lambda d: d.name)

    def add_translation(self, locale: str, domain: str, translation: Translation) -> None:
        """Add a translation entry."""
        if locale not in self._translations:
            self._translations[locale] = {}
        key = f"{domain}:{translation.key}"
        self._translations[locale][key] = translation

    def get_translation(self, locale: str, domain: str, key: str) -> Optional[Translation]:
        """Get a translation."""
        if locale in self._translations:
            full_key = f"{domain}:{key}"
            return self._translations[locale].get(full_key)
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get locale statistics."""
        by_language: Dict[str, int] = {}
        for locale in self._locales.values():
            lang = locale.language or "unknown"
            by_language[lang] = by_language.get(lang, 0) + 1
        return {
            "total_locales": len(self._locales),
            "total_domains": len(self._domains),
            "total_translations": sum(len(t) for t in self._translations.values()),
            "by_language": by_language,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "locales": {k: v.to_dict() for k, v in self._locales.items()},
            "domains": {k: v.to_dict() for k, v in self._domains.items()},
            "default_locale": self._default_locale,
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_locale_manager() -> LocaleManager:
    """Get or create the global LocaleManager instance."""
    global _global_locale_manager
    if _global_locale_manager is None:
        _global_locale_manager = LocaleManager()
    return _global_locale_manager


def initialize() -> LocaleManager:
    """Initialize and return the global LocaleManager."""
    return get_global_locale_manager()


def refresh() -> LocaleManager:
    """Refresh the global LocaleManager."""
    global _global_locale_manager
    _global_locale_manager = LocaleManager()
    return _global_locale_manager
