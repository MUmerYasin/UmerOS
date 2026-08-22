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
UmerOS Shared Data Manager
==========================
Architecture-independent shared data management under /usr/share.

The /usr/share hierarchy provides read-only, architecture-independent
shared data including:
  - man/     : Manual pages
  - doc/     : Documentation
  - info/    : GNU Info system documents
  - locale/  : Locale-specific data
  - zoneinfo/: Timezone data
  - dict/    : Word lists
  - games/   : Game data files
  - misc/    : Miscellaneous shared data
  - colors/  : Color definition files
  - icons/   : Icon themes
  - pixmaps/ : Pixmap images

This module manages discovery, indexing, and access control for
shared data resources across the system.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import (
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
)


# ============================================================================
# Constants
# ============================================================================

SHARE_BASE_PATH: str = "/usr/share"

SHARE_SUBDIRS: Dict[str, str] = {
    "man": "Manual pages",
    "doc": "Documentation",
    "info": "GNU Info documents",
    "locale": "Locale data",
    "zoneinfo": "Timezone data",
    "dict": "Word lists",
    "games": "Game data",
    "misc": "Miscellaneous data",
    "colors": "Color definitions",
    "icons": "Icon themes",
    "pixmaps": "Pixmap images",
    "applications": "Desktop entries",
    "desktop-directories": "Desktop directory entries",
    "mime": "MIME type data",
    "themes": "GUI themes",
    "fonts": "Font files",
    "wallpapers": "Wallpapers",
    "sounds": "Sound files",
}

LOCALE_DIRS: List[str] = [
    "en_US", "en_GB", "fr_FR", "de_DE", "es_ES",
    "pt_BR", "ja_JP", "zh_CN", "ko_KR", "ar_SA",
    "hi_IN", "ru_RU", "it_IT", "nl_NL", "pl_PL",
]


# ============================================================================
# Enums
# ============================================================================

class ShareCategory(IntEnum):
    """Categories of shared data."""
    MANUAL_PAGES = 0
    DOCUMENTATION = 1
    INFO_DOCUMENTS = 2
    LOCALE_DATA = 3
    TIMEZONE_DATA = 4
    DICTIONARY = 5
    GAMES = 6
    MISCELLANEOUS = 7
    COLORS = 8
    ICONS = 9
    PIXMAPS = 10
    DESKTOP_ENTRIES = 11
    MIME_DATA = 12
    THEMES = 13
    FONTS = 14
    WALLPAPERS = 15
    SOUNDS = 16
    CUSTOM = 17


class AccessMode(IntEnum):
    """Access modes for shared resources."""
    READ_ONLY = 0
    READ_WRITE = 1
    EXECUTABLE = 2


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class ShareResource:
    """A single shared data resource."""
    name: str = ""
    path: str = ""
    category: ShareCategory = ShareCategory.MISCELLANEOUS
    size_bytes: int = 0
    is_directory: bool = False
    children: List[ShareResource] = field(default_factory=list)
    mime_type: str = ""
    permissions: AccessMode = AccessMode.READ_ONLY
    created_at: float = 0.0
    modified_at: float = 0.0

    def get_extension(self) -> str:
        """Get file extension."""
        _, ext = os.path.splitext(self.name)
        return ext

    def is_compressed(self) -> bool:
        """Check if resource is compressed."""
        compressed_exts = {".gz", ".bz2", ".xz", ".zst", ".tar", ".zip"}
        return self.get_extension() in compressed_exts

    def total_size(self) -> int:
        """Get total size including children."""
        total = self.size_bytes
        for child in self.children:
            total += child.total_size()
        return total


@dataclass
class LocaleEntry:
    """A locale-specific data entry."""
    locale: str = ""
    language: str = ""
    territory: str = ""
    codeset: str = "UTF-8"
    path: str = ""
    translations: Dict[str, str] = field(default_factory=dict)

    def display_name(self) -> str:
        """Get human-readable locale name."""
        lang = self.language.upper()
        terr = self.territory.upper()
        return f"{lang}_{terr}.{self.codeset}"


@dataclass
class TimeZoneEntry:
    """A timezone data entry."""
    name: str = ""
    path: str = ""
    region: str = ""
    utc_offset: str = ""
    dst_offset: str = ""
    abbreviation: str = ""

    def full_name(self) -> str:
        """Get full timezone name with region."""
        return f"{self.region}/{self.name}" if self.region else self.name


@dataclass
class DesktopEntry:
    """A freedesktop.org desktop entry."""
    name: str = ""
    path: str = ""
    exec_command: str = ""
    icon: str = ""
    categories: List[str] = field(default_factory=list)
    comment: str = ""
    terminal: bool = False
    startup_notify: bool = False

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "Name": self.name,
            "Exec": self.exec_command,
            "Icon": self.icon,
            "Categories": ";".join(self.categories),
            "Comment": self.comment,
            "Terminal": "true" if self.terminal else "false",
        }


@dataclass
class ColorDefinition:
    """A named color definition."""
    name: str = ""
    hex_value: str = ""
    red: int = 0
    green: int = 0
    blue: int = 0
    alpha: int = 255

    def to_hex(self) -> str:
        """Get hex color string."""
        if self.hex_value:
            return self.hex_value
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"

    def to_rgba(self) -> Tuple[int, int, int, int]:
        """Get RGBA tuple."""
        return (self.red, self.green, self.blue, self.alpha)


@dataclass
class ShareIndex:
    """Index entry for shared data."""
    name: str = ""
    category: ShareCategory = ShareCategory.MISCELLANEOUS
    path: str = ""
    size_bytes: int = 0
    file_count: int = 0


# ============================================================================
# Share Data Manager
# ============================================================================

class ShareDataManager:
    """
    Manages architecture-independent shared data under /usr/share.

    Handles discovery, indexing, and access of shared resources
    including locales, timezones, desktop entries, and general data files.
    """

    def __init__(self) -> None:
        self._base_path: str = SHARE_BASE_PATH
        self._resources: Dict[str, ShareResource] = {}
        self._locales: Dict[str, LocaleEntry] = {}
        self._timezones: Dict[str, TimeZoneEntry] = {}
        self._desktop_entries: Dict[str, DesktopEntry] = {}
        self._colors: Dict[str, ColorDefinition] = {}
        self._category_index: Dict[ShareCategory, List[str]] = {}
        self._custom_dirs: List[str] = []

    # -- Path Management --

    def get_base_path(self) -> str:
        """Get the base share path."""
        return self._base_path

    def add_custom_dir(self, path: str) -> None:
        """Add a custom shared data directory."""
        if path not in self._custom_dirs:
            self._custom_dirs.append(path)

    def get_subdirectories(self) -> Dict[str, str]:
        """Get all known subdirectories."""
        return dict(SHARE_SUBDIRS)

    # -- Resource Management --

    def scan_resources(self) -> int:
        """Scan the share directory and index resources."""
        count = 0
        for subdir in SHARE_SUBDIRS:
            dirpath = os.path.join(self._base_path, subdir)
            if os.path.isdir(dirpath):
                count += self._scan_directory(dirpath, subdir)
        return count

    def _scan_directory(self, dirpath: str, category_name: str) -> int:
        """Recursively scan a directory and index resources."""
        count = 0
        category = self._category_from_name(category_name)
        try:
            for entry in os.scandir(dirpath):
                resource = ShareResource(
                    name=entry.name,
                    path=entry.path,
                    category=category,
                    is_directory=entry.is_dir(),
                )
                try:
                    stat = entry.stat()
                    resource.size_bytes = stat.st_size
                    resource.created_at = stat.st_ctime
                    resource.modified_at = stat.st_mtime
                except OSError:
                    pass
                self._resources[entry.path] = resource
                key = f"{category_name}:{entry.name}"
                self._category_index.setdefault(category, []).append(key)
                count += 1
                if entry.is_dir():
                    count += self._scan_directory(entry.path, category_name)
        except (OSError, PermissionError):
            pass
        return count

    def _category_from_name(self, name: str) -> ShareCategory:
        """Convert directory name to ShareCategory."""
        mapping: Dict[str, ShareCategory] = {
            "man": ShareCategory.MANUAL_PAGES,
            "doc": ShareCategory.DOCUMENTATION,
            "info": ShareCategory.INFO_DOCUMENTS,
            "locale": ShareCategory.LOCALE_DATA,
            "zoneinfo": ShareCategory.TIMEZONE_DATA,
            "dict": ShareCategory.DICTIONARY,
            "games": ShareCategory.GAMES,
            "misc": ShareCategory.MISCELLANEOUS,
            "colors": ShareCategory.COLORS,
            "icons": ShareCategory.ICONS,
            "pixmaps": ShareCategory.PIXMAPS,
            "applications": ShareCategory.DESKTOP_ENTRIES,
            "mime": ShareCategory.MIME_DATA,
            "themes": ShareCategory.THEMES,
            "fonts": ShareCategory.FONTS,
        }
        return mapping.get(name, ShareCategory.CUSTOM)

    def get_resource(self, path: str) -> Optional[ShareResource]:
        """Get a resource by path."""
        return self._resources.get(path)

    def list_resources(self, category: Optional[ShareCategory] = None) -> List[ShareResource]:
        """List all resources, optionally filtered by category."""
        if category is None:
            return list(self._resources.values())
        return [
            r for r in self._resources.values()
            if r.category == category
        ]

    # -- Locale Management --

    def scan_locales(self) -> int:
        """Scan and index locale data."""
        count = 0
        locale_path = os.path.join(self._base_path, "locale")
        if not os.path.isdir(locale_path):
            return 0
        for entry in os.scandir(locale_path):
            if entry.is_dir() and "_" in entry.name:
                parts = entry.name.split(".")
                locale_code = parts[0]
                codeset = parts[1] if len(parts) > 1 else "UTF-8"
                lang_territory = locale_code.split("_", 1)
                locale = LocaleEntry(
                    locale=entry.name,
                    language=lang_territory[0] if lang_territory else "",
                    territory=lang_territory[1] if len(lang_territory) > 1 else "",
                    codeset=codeset,
                    path=entry.path,
                )
                self._locales[entry.name] = locale
                count += 1
        return count

    def get_locale(self, locale_name: str) -> Optional[LocaleEntry]:
        """Get a locale entry by name."""
        return self._locales.get(locale_name)

    def list_locales(self) -> List[LocaleEntry]:
        """List all indexed locales."""
        return list(self._locales.values())

    def find_locales_by_language(self, language: str) -> List[LocaleEntry]:
        """Find locales by language code."""
        lang_lower = language.lower()
        return [
            loc for loc in self._locales.values()
            if loc.language.lower() == lang_lower
        ]

    # -- Timezone Management --

    def scan_timezones(self) -> int:
        """Scan and index timezone data."""
        count = 0
        tz_path = os.path.join(self._base_path, "zoneinfo")
        if not os.path.isdir(tz_path):
            return 0
        for entry in os.scandir(tz_path):
            if entry.is_dir():
                region = entry.name
                for tz_entry in os.scandir(entry.path):
                    if tz_entry.is_file():
                        tz = TimeZoneEntry(
                            name=tz_entry.name,
                            path=tz_entry.path,
                            region=region,
                        )
                        key = f"{region}/{tz_entry.name}"
                        self._timezones[key] = tz
                        count += 1
        return count

    def get_timezone(self, name: str) -> Optional[TimeZoneEntry]:
        """Get a timezone entry by name."""
        return self._timezones.get(name)

    def list_timezones(self, region: Optional[str] = None) -> List[TimeZoneEntry]:
        """List timezones, optionally filtered by region."""
        if region is None:
            return list(self._timezones.values())
        return [
            tz for tz in self._timezones.values()
            if tz.region == region
        ]

    def get_timezone_regions(self) -> List[str]:
        """Get all timezone regions."""
        return sorted(set(
            tz.region for tz in self._timezones.values()
        ))

    # -- Desktop Entries --

    def parse_desktop_entry(self, filepath: str) -> Optional[DesktopEntry]:
        """Parse a .desktop file."""
        try:
            entry = DesktopEntry(path=filepath)
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                in_desktop_entry = False
                for line in f:
                    line = line.strip()
                    if line == "[Desktop Entry]":
                        in_desktop_entry = True
                        continue
                    if line.startswith("[") and line.endswith("]"):
                        in_desktop_entry = False
                        continue
                    if not in_desktop_entry or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if key == "Name":
                        entry.name = value
                    elif key == "Exec":
                        entry.exec_command = value
                    elif key == "Icon":
                        entry.icon = value
                    elif key == "Categories":
                        entry.categories = [
                            c.strip() for c in value.split(";") if c.strip()
                        ]
                    elif key == "Comment":
                        entry.comment = value
                    elif key == "Terminal":
                        entry.terminal = value.lower() == "true"
                    elif key == "StartupNotify":
                        entry.startup_notify = value.lower() == "true"
            return entry
        except (OSError, IOError):
            return None

    def scan_desktop_entries(self) -> int:
        """Scan and index .desktop files."""
        count = 0
        apps_path = os.path.join(self._base_path, "applications")
        if not os.path.isdir(apps_path):
            return 0
        for entry in os.scandir(apps_path):
            if entry.is_file() and entry.name.endswith(".desktop"):
                de = self.parse_desktop_entry(entry.path)
                if de:
                    self._desktop_entries[entry.name] = de
                    count += 1
        return count

    def get_desktop_entry(self, name: str) -> Optional[DesktopEntry]:
        """Get a desktop entry by name."""
        return self._desktop_entries.get(name)

    def find_desktop_entries_by_category(
        self, category: str
    ) -> List[DesktopEntry]:
        """Find desktop entries by category."""
        cat_lower = category.lower()
        return [
            de for de in self._desktop_entries.values()
            if cat_lower in [c.lower() for c in de.categories]
        ]

    def list_desktop_entries(self) -> List[DesktopEntry]:
        """List all indexed desktop entries."""
        return list(self._desktop_entries.values())

    # -- Color Definitions --

    def load_color_scheme(self, filepath: str) -> int:
        """Load color definitions from a file."""
        count = 0
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        color = ColorDefinition(
                            name=parts[0],
                            hex_value=parts[1] if parts[1].startswith("#") else f"#{parts[1]}",
                        )
                        self._colors[color.name] = color
                        count += 1
        except (OSError, IOError):
            pass
        return count

    def get_color(self, name: str) -> Optional[ColorDefinition]:
        """Get a color by name."""
        return self._colors.get(name)

    def list_colors(self) -> List[ColorDefinition]:
        """List all loaded colors."""
        return list(self._colors.values())

    # -- Utility --

    def total_size(self) -> int:
        """Get total size of all indexed resources."""
        return sum(r.size_bytes for r in self._resources.values())

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about shared data."""
        stats: Dict[str, int] = {
            "total_resources": len(self._resources),
            "locales": len(self._locales),
            "timezones": len(self._timezones),
            "desktop_entries": len(self._desktop_entries),
            "colors": len(self._colors),
            "total_size_bytes": self.total_size(),
        }
        for cat in ShareCategory:
            stats[f"category_{cat.name}"] = len(
                self._category_index.get(cat, [])
            )
        return stats

    def clear(self) -> None:
        """Clear all indexed data."""
        self._resources.clear()
        self._locales.clear()
        self._timezones.clear()
        self._desktop_entries.clear()
        self._colors.clear()
        self._category_index.clear()


# ============================================================================
# Global Singleton
# ============================================================================

_global_share: Optional[ShareDataManager] = None


def get_global_share() -> ShareDataManager:
    """Get or create the global ShareDataManager instance."""
    global _global_share
    if _global_share is None:
        _global_share = ShareDataManager()
    return _global_share
