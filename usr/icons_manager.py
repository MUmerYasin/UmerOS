"""
UmerOS Icons Manager (/usr/share/icons)
========================================
System icons and icon themes.

Reference: Linux Filesystem Hierarchy - /usr/share/icons
  /usr/share/icons contains system icon themes and cursors.
  Icons are organized by theme, size, and category.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ─── Constants ───────────────────────────────────────────────────────────────

ICONS_PATH = "/usr/share/icons"

ICON_CATEGORIES = {
    "ACTIONS": "Action icons (edit, save, copy, etc.)",
    "APPLICATIONS": "Application icons",
    "CATEGORIES": "Category icons (utilities, settings, etc.)",
    "DEVICES": "Device icons (printer, disk, network, etc.)",
    "EMBLEMS": "Emblem icons (star, check, warning, etc.)",
    "EMOTES": "Emoticon icons",
    "MIMETYPES": "File type icons",
    "PLACES": "Location icons (home, folder, desktop, etc.)",
    "STATUS": "Status icons (info, error, warning, etc.)",
    "SCALABLE": "Scalable vector icons",
    "CURSORS": "Cursor themes",
}

ICON_SIZES = [16, 22, 24, 32, 48, 64, 96, 128, 256, 512]

ICON_FORMATS = ["svg", "png", "xpm", "bmp", "gif", "ico"]


# ─── Enums ───────────────────────────────────────────────────────────────────

class IconCategory(IntEnum):
    """Icon categories."""
    ACTIONS = 1
    APPLICATIONS = 2
    CATEGORIES = 3
    DEVICES = 4
    EMBLEMS = 5
    EMOTES = 6
    MIMETYPES = 7
    PLACES = 8
    STATUS = 9
    SCALABLE = 10
    CURSORS = 11
    UNKNOWN = 99


class IconFormat(IntEnum):
    """Icon file formats."""
    SVG = 1
    PNG = 2
    XPM = 3
    BMP = 4
    GIF = 5
    ICO = 6


class IconThemeStatus(IntEnum):
    """Icon theme status."""
    ACTIVE = 1
    INACTIVE = 2
    BROKEN = 3


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class IconFile:
    """Represents an icon file."""
    name: str
    path: str
    size: int
    category: IconCategory = IconCategory.UNKNOWN
    format: IconFormat = IconFormat.PNG
    description: str = ""
    scalable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "category": self.category.name,
            "format": self.format.name,
            "description": self.description,
            "scalable": self.scalable,
        }


@dataclass
class IconTheme:
    """An icon theme with metadata."""
    name: str
    description: str = ""
    inherits: str = ""
    status: IconThemeStatus = IconThemeStatus.ACTIVE
    directories: List[str] = field(default_factory=list)
    icons: Dict[str, List[IconFile]] = field(default_factory=dict)
    preview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inherits": self.inherits,
            "status": self.status.name,
            "directories": self.directories,
            "icons_count": {k: len(v) for k, v in self.icons.items()},
        }


@dataclass
class CursorTheme:
    """A cursor theme."""
    name: str
    path: str
    description: str = ""
    inherits: str = ""
    cursors: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "inherits": self.inherits,
            "cursors": self.cursors,
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_icons_manager: Optional["IconsManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class IconsManager:
    """Manages /usr/share/icons - system icons."""

    def __init__(self) -> None:
        self._themes: Dict[str, IconTheme] = {}
        self._cursor_themes: Dict[str, CursorTheme] = {}
        self._active_theme: str = "Adwaita"
        self._initialize_default_themes()

    def _initialize_default_themes(self) -> None:
        """Initialize with common icon themes."""
        default_themes = [
            ("Adwaita", "GNOME default icon theme", "gnome"),
            ("hicolor", "Fallback icon theme", ""),
            ("breeze", "KDE Plasma icon theme", "breeze-dark"),
            ("breeze-dark", "KDE Plasma dark icon theme", ""),
            ("Papirus", "Popular multi-icon theme", "Papirus-Dark"),
            ("Papirus-Dark", "Papirus dark variant", ""),
            ("Papirus-Light", "Papirus light variant", ""),
            ("Numix", "Numix icon theme", "Numix-Circle"),
            ("Numix-Circle", "Numix circle icons", ""),
            ("Moka", "Moka icon theme", ""),
            ("elementary", "elementary OS icon theme", ""),
            ("La Capitaine", "macOS-inspired icon theme", "Adwaita"),
        ]
        for name, desc, inherits in default_themes:
            theme = IconTheme(name=name, description=desc, inherits=inherits)
            for cat in ["actions", "apps", "categories", "devices",
                        "emblems", "emotes", "mimetypes", "places", "status"]:
                theme.directories.append(f"{name}/{cat}")
            self._themes[name] = theme

        # Default cursors
        self._cursor_themes["Adwaita"] = CursorTheme(
            name="Adwaita",
            path="/usr/share/icons/Adwaita/cursors",
            description="GNOME default cursor theme",
        )
        self._cursor_themes["breeze"] = CursorTheme(
            name="breeze",
            path="/usr/share/icons/breeze/cursors",
            description="KDE Plasma cursor theme",
        )

    def get_theme(self, name: str) -> Optional[IconTheme]:
        """Get a theme by name."""
        return self._themes.get(name)

    def list_themes(self) -> List[IconTheme]:
        """List all icon themes."""
        return sorted(self._themes.values(), key=lambda t: t.name)

    def set_active_theme(self, name: str) -> bool:
        """Set the active icon theme."""
        if name in self._themes:
            self._active_theme = name
            self._themes[name].status = IconThemeStatus.ACTIVE
            return True
        return False

    def get_active_theme(self) -> Optional[IconTheme]:
        """Get the currently active theme."""
        return self._themes.get(self._active_theme)

    def search_icons(self, query: str, theme: Optional[str] = None) -> List[IconFile]:
        """Search icons by name."""
        results = []
        search_themes = [self._themes[theme]] if theme and theme in self._themes else self._themes.values()
        for t in search_themes:
            for cat, icons in t.icons.items():
                for icon in icons:
                    if query.lower() in icon.name.lower():
                        results.append(icon)
        return results

    def get_cursor_theme(self, name: str) -> Optional[CursorTheme]:
        """Get a cursor theme by name."""
        return self._cursor_themes.get(name)

    def list_cursor_themes(self) -> List[CursorTheme]:
        """List all cursor themes."""
        return sorted(self._cursor_themes.values(), key=lambda t: t.name)

    def get_statistics(self) -> Dict[str, Any]:
        """Get icons statistics."""
        total_icons = 0
        for theme in self._themes.values():
            for icons in theme.icons.values():
                total_icons += len(icons)
        return {
            "total_themes": len(self._themes),
            "total_cursor_themes": len(self._cursor_themes),
            "total_icons": total_icons,
            "active_theme": self._active_theme,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "themes": {k: v.to_dict() for k, v in self._themes.items()},
            "cursor_themes": {k: v.to_dict() for k, v in self._cursor_themes.items()},
            "active_theme": self._active_theme,
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_icons_manager() -> IconsManager:
    """Get or create the global IconsManager instance."""
    global _global_icons_manager
    if _global_icons_manager is None:
        _global_icons_manager = IconsManager()
    return _global_icons_manager


def initialize() -> IconsManager:
    """Initialize and return the global IconsManager."""
    return get_global_icons_manager()


def refresh() -> IconsManager:
    """Refresh the global IconsManager."""
    global _global_icons_manager
    _global_icons_manager = IconsManager()
    return _global_icons_manager
