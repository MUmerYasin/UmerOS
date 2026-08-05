"""
NLS Manager — Native Language Support Message Catalogs (/usr/share/nls)

FHS 3.0 Section 4.11.3: Message catalogs for Native Language Support.

Manages:
- Message catalog directories per locale
- Locale-specific message files
- Message catalog lookup
- NLS database management
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class NLSFormat(Enum):
    """NLS message catalog formats."""
    GNU_MO = "mo"
    GNU_PO = "po"
    XPG = "xpg"
    CAT = "cat"
    CUSTOM = "custom"


class NLSStatus(IntEnum):
    """Status of NLS entries."""
    MISSING = 0
    PRESENT = 1
    COMPILED = 2
    CORRUPTED = 3


@dataclass
class NLSEntry:
    """Represents an NLS message catalog."""
    name: str
    path: Path
    locale: str = ""
    format: NLSFormat = NLSFormat.CUSTOM
    status: NLSStatus = NLSStatus.MISSING
    file_size: int = 0
    is_directory: bool = False
    message_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "locale": self.locale,
            "format": self.format.value,
            "status": self.status.value,
            "file_size": self.file_size,
            "is_directory": self.is_directory,
            "message_count": self.message_count
        }


class NLSManager:
    """Manages /usr/share/nls message catalogs per FHS 3.0."""

    BASE_DIR = Path("/usr/share/nls")

    # Common NLS locales
    COMMON_LOCALES = {
        "en_US", "en_GB", "fr_FR", "fr_CA", "de_DE", "de_AT",
        "es_ES", "es_MX", "it_IT", "pt_BR", "pt_PT", "nl_NL",
        "ru_RU", "ja_JP", "ko_KR", "zh_CN", "zh_TW", "ar_SA",
        "hi_IN", "tr_TR", "pl_PL", "sv_SE", "da_DK", "no_NO",
        "fi_FI", "cs_CZ", "ro_RO", "hu_HU", "el_GR", "he_IL",
        "th_TH", "vi_VN", "id_ID", "ms_MY",
    }

    def __init__(self):
        self._entries: Dict[str, NLSEntry] = {}
        self._locales: Dict[str, List[str]] = {}
        self._refresh()

    def _refresh(self):
        """Refresh NLS cache."""
        self._entries.clear()
        self._locales.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        for locale_dir in sorted(self.BASE_DIR.iterdir()):
            if locale_dir.is_dir():
                locale = locale_dir.name
                self._locales[locale] = []
                self._scan_locale_directory(locale_dir, locale)

    def _scan_locale_directory(self, locale_dir: Path, locale: str):
        """Scan a locale directory for NLS entries."""
        for entry_path in sorted(locale_dir.iterdir()):
            if entry_path.is_file() or entry_path.is_symlink():
                entry = self._create_entry(entry_path, locale)
                self._entries[entry.name] = entry
                self._locales[locale].append(entry.name)

    def _create_entry(self, path: Path, locale: str) -> NLSEntry:
        """Create an NLSEntry for a path."""
        name = path.name
        fmt = self._detect_format(path)

        status = NLSStatus.MISSING
        file_size = 0
        message_count = 0

        if path.is_symlink():
            status = NLSStatus.PRESENT
        elif path.exists():
            file_size = path.stat().st_size
            if file_size > 0:
                try:
                    with open(path, 'rb') as f:
                        magic = f.read(4)
                    if magic == b'\x95\x04\x12\xde':
                        status = NLSStatus.COMPILED
                        message_count = self._count_messages_mo(path)
                    else:
                        status = NLSStatus.PRESENT
                except Exception:
                    status = NLSStatus.CORRUPTED

        return NLSEntry(
            name=name,
            path=path,
            locale=locale,
            format=fmt,
            status=status,
            file_size=file_size,
            is_directory=path.is_dir(),
            message_count=message_count
        )

    def _detect_format(self, path: Path) -> NLSFormat:
        """Detect NLS format."""
        suffix = path.suffix.lower()
        if suffix == '.mo':
            return NLSFormat.GNU_MO
        if suffix == '.po':
            return NLSFormat.GNU_PO
        if suffix == '.cat':
            return NLSFormat.CAT
        return NLSFormat.CUSTOM

    def _count_messages_mo(self, path: Path) -> int:
        """Count messages in a .mo file."""
        try:
            with open(path, 'rb') as f:
                magic = f.read(4)
                if magic != b'\x95\x04\x12\xde':
                    return 0
                f.seek(8)
                nstrings = int.from_bytes(f.read(4), 'little')
                return nstrings
        except Exception:
            return 0

    def list_entries(self) -> List[NLSEntry]:
        """List all NLS entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[NLSEntry]:
        """Get a specific NLS entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if an NLS entry exists."""
        return name in self._entries

    def get_locales(self) -> List[str]:
        """Get all locales."""
        return sorted(self._locales.keys())

    def get_entries_for_locale(self, locale: str) -> List[NLSEntry]:
        """Get all entries for a specific locale."""
        names = self._locales.get(locale, [])
        return [self._entries[n] for n in names if n in self._entries]

    def add_locale(self, locale: str) -> bool:
        """Add a new locale directory."""
        try:
            locale_dir = self.BASE_DIR / locale
            locale_dir.mkdir(parents=True, exist_ok=True)
            self._refresh()
            return True
        except Exception:
            return False

    def add_entry(self, locale: str, name: str) -> bool:
        """Add a new NLS entry."""
        try:
            locale_dir = self.BASE_DIR / locale
            locale_dir.mkdir(parents=True, exist_ok=True)
            entry_path = locale_dir / name
            entry_path.touch()
            self._refresh()
            return True
        except Exception:
            return False

    def remove_entry(self, name: str) -> bool:
        """Remove an NLS entry."""
        try:
            entry = self.get_entry(name)
            if entry and entry.path.exists():
                entry.path.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get NLS manager status."""
        present = sum(1 for e in self._entries.values()
                      if e.status == NLSStatus.PRESENT)
        compiled = sum(1 for e in self._entries.values()
                       if e.status == NLSStatus.COMPILED)
        total_messages = sum(e.message_count for e in self._entries.values())
        total_size = sum(e.file_size for e in self._entries.values())

        return {
            "base_dir": str(self.BASE_DIR),
            "exists": self.BASE_DIR.exists(),
            "total_entries": len(self._entries),
            "total_locales": len(self._locales),
            "present": present,
            "compiled": compiled,
            "total_messages": total_messages,
            "total_size": total_size,
            "locales": self.get_locales()
        }


# Singleton instance
nls_manager = NLSManager()
