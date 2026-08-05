"""
UmerOS Fonts Manager (/usr/share/fonts)
========================================
System fonts and font configuration.

Reference: Linux Filesystem Hierarchy - /usr/share/fonts
  /usr/share/fonts contains system-wide font files and font
  configuration. Fonts are organized by type and purpose.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ─── Constants ───────────────────────────────────────────────────────────────

FONTS_PATH = "/usr/share/fonts"

FONT_CATEGORIES = {
    "TRUETYPE": "TrueType fonts (.ttf)",
    "OPENTYPE": "OpenType fonts (.otf)",
    "TYPE1": "PostScript Type 1 fonts (.pfa, .pfb)",
    "CID": "CID-keyed fonts",
    "BDF": "Bitmap Distribution Format fonts",
    "PCF": "Portable Compiled Format fonts",
    "TTC": "TrueType Collection fonts",
    "WOFF": "Web Open Font Format",
    "WOFF2": "Web Open Font Format 2",
}

FONT_PURPOSES = {
    "SERIF": "Serif fonts for body text",
    "SANS-SERIF": "Sans-serif fonts for UI",
    "MONOSPACE": "Monospace fonts for code",
    "CURSIVE": "Cursive/script fonts",
    "FANTASY": "Decorative fonts",
    "EMOJI": "Emoji fonts",
    "MONO": "Monospace alias",
}

FONT_LANGUAGES = [
    "latin", "latin-ext", "cyrillic", "cyrillic-ext",
    "greek", "greek-ext", "vietnamese", "arabic",
    "hebrew", "thai", "chinese-simplified", "chinese-traditional",
    "japanese", "korean", "devanagari", "bengali",
    "tamil", "telugu", "kannada", "malayalam",
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class FontType(IntEnum):
    """Font file types."""
    TRUETYPE = 1
    OPENTYPE = 2
    TYPE1 = 3
    CID = 4
    BDF = 5
    PCF = 6
    TTC = 7
    WOFF = 8
    WOFF2 = 9
    UNKNOWN = 99


class FontPurpose(IntEnum):
    """Font purposes."""
    SERIF = 1
    SANS_SERIF = 2
    MONOSPACE = 3
    CURSIVE = 4
    FANTASY = 5
    EMOJI = 6


class FontStatus(IntEnum):
    """Font availability status."""
    ACTIVE = 1
    DISABLED = 2
    BROKEN = 3
    MISSING = 4


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class FontFile:
    """Represents a font file."""
    name: str
    path: str
    font_type: FontType = FontType.TRUETYPE
    purpose: FontPurpose = FontPurpose.SANS_SERIF
    family: str = ""
    style: str = "Regular"
    weight: int = 400
    width: str = "normal"
    slant: str = "roman"
    size: int = 0
    languages: List[str] = field(default_factory=list)
    description: str = ""
    version: str = ""
    designer: str = ""
    status: FontStatus = FontStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "font_type": self.font_type.name,
            "purpose": self.purpose.name,
            "family": self.family,
            "style": self.style,
            "weight": self.weight,
            "width": self.width,
            "slant": self.slant,
            "size": self.size,
            "languages": self.languages,
            "description": self.description,
            "version": self.version,
            "designer": self.designer,
            "status": self.status.name,
        }


@dataclass
class FontFamily:
    """A collection of related fonts."""
    name: str
    description: str = ""
    fonts: List[FontFile] = field(default_factory=list)
    purposes: List[FontPurpose] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "fonts_count": len(self.fonts),
            "purposes": [p.name for p in self.purposes],
            "languages": self.languages,
        }


@dataclass
class FontConfig:
    """Font configuration entry."""
    family: str
    purpose: FontPurpose = FontPurpose.SANS_SERIF
    fallbacks: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    antialias: bool = True
    hinting: bool = True
    autohint: bool = False
    hintstyle: str = "hintslight"
    antialias_rgba: bool = True
    lcdfilter: str = "lcddefault"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family": self.family,
            "purpose": self.purpose.name,
            "fallbacks": self.fallbacks,
            "aliases": self.aliases,
            "antialias": self.antialias,
            "hinting": self.hinting,
            "autohint": self.autohint,
            "hintstyle": self.hintstyle,
            "lcdfilter": self.lcdfilter,
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_fonts_manager: Optional["FontsManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class FontsManager:
    """Manages /usr/share/fonts - system fonts."""

    def __init__(self) -> None:
        self._fonts: Dict[str, FontFile] = {}
        self._families: Dict[str, FontFamily] = {}
        self._config: Dict[str, FontConfig] = {}
        self._initialize_default_fonts()
        self._initialize_default_config()

    def _initialize_default_fonts(self) -> None:
        """Initialize with common system fonts."""
        default_families = [
            ("DejaVu Sans", "Sans-serif", FontPurpose.SANS_SERIF),
            ("DejaVu Sans Mono", "Monospace", FontPurpose.MONOSPACE),
            ("DejaVu Serif", "Serif", FontPurpose.SERIF),
            ("Liberation Sans", "Sans-serif", FontPurpose.SANS_SERIF),
            ("Liberation Mono", "Monospace", FontPurpose.MONOSPACE),
            ("Liberation Serif", "Serif", FontPurpose.SERIF),
            ("Noto Sans", "Sans-serif", FontPurpose.SANS_SERIF),
            ("Noto Serif", "Serif", FontPurpose.SERIF),
            ("Noto Sans Mono", "Monospace", FontPurpose.MONOSPACE),
            ("Ubuntu", "Sans-serif", FontPurpose.SANS_SERIF),
            ("Ubuntu Mono", "Monospace", FontPurpose.MONOSPACE),
            ("Fira Code", "Monospace", FontPurpose.MONOSPACE),
            ("Source Code Pro", "Monospace", FontPurpose.MONOSPACE),
            ("Cantarell", "Sans-serif", FontPurpose.SANS_SERIF),
            ("Roboto", "Sans-serif", FontPurpose.SANS_SERIF),
            ("Open Sans", "Sans-serif", FontPurpose.SANS_SERIF),
        ]
        for family, desc, purpose in default_families:
            font = FontFile(
                name=family,
                path=f"/usr/share/fonts/{family.lower().replace(' ', '-')}",
                family=family,
                purpose=purpose,
                description=desc,
            )
            self._fonts[family] = font
            self._families[family] = FontFamily(
                name=family, description=desc, fonts=[font], purposes=[purpose]
            )

    def _initialize_default_config(self) -> None:
        """Initialize default font configuration."""
        self._config["sans-serif"] = FontConfig(
            family="sans-serif",
            purpose=FontPurpose.SANS_SERIF,
            fallbacks=["Noto Sans", "DejaVu Sans", "Liberation Sans"],
        )
        self._config["serif"] = FontConfig(
            family="serif",
            purpose=FontPurpose.SERIF,
            fallbacks=["Noto Serif", "DejaVu Serif", "Liberation Serif"],
        )
        self._config["monospace"] = FontConfig(
            family="monospace",
            purpose=FontPurpose.MONOSPACE,
            fallbacks=["Noto Sans Mono", "DejaVu Sans Mono", "Liberation Mono"],
        )
        self._config["cursive"] = FontConfig(
            family="cursive",
            purpose=FontPurpose.CURSIVE,
            fallbacks=["URW Chancery L"],
        )
        self._config["fantasy"] = FontConfig(
            family="fantasy",
            purpose=FontPurpose.FANTASY,
            fallbacks=["URW Gothic L"],
        )

    def get_font(self, name: str) -> Optional[FontFile]:
        """Get a font by name."""
        return self._fonts.get(name)

    def list_fonts(self, purpose: Optional[FontPurpose] = None) -> List[FontFile]:
        """List all fonts, optionally filtered by purpose."""
        fonts = list(self._fonts.values())
        if purpose is not None:
            fonts = [f for f in fonts if f.purpose == purpose]
        return sorted(fonts, key=lambda f: f.name)

    def search_fonts(self, query: str) -> List[FontFile]:
        """Search fonts by name, family, or description."""
        query_lower = query.lower()
        results = []
        for font in self._fonts.values():
            if (query_lower in font.name.lower() or
                query_lower in font.family.lower() or
                query_lower in font.description.lower()):
                results.append(font)
        return results

    def get_family(self, name: str) -> Optional[FontFamily]:
        """Get a font family by name."""
        return self._families.get(name)

    def list_families(self) -> List[FontFamily]:
        """List all font families."""
        return sorted(self._families.values(), key=lambda f: f.name)

    def get_config(self, family: str) -> Optional[FontConfig]:
        """Get font configuration for a family."""
        return self._config.get(family)

    def set_config(self, config: FontConfig) -> None:
        """Set font configuration."""
        self._config[config.family] = config

    def list_config(self) -> List[FontConfig]:
        """List all font configurations."""
        return sorted(self._config.values(), key=lambda c: c.family)

    def get_statistics(self) -> Dict[str, Any]:
        """Get fonts statistics."""
        by_purpose: Dict[str, int] = {}
        for font in self._fonts.values():
            purpose = font.purpose.name
            by_purpose[purpose] = by_purpose.get(purpose, 0) + 1
        return {
            "total_fonts": len(self._fonts),
            "total_families": len(self._families),
            "by_purpose": by_purpose,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "fonts": {k: v.to_dict() for k, v in self._fonts.items()},
            "families": {k: v.to_dict() for k, v in self._families.items()},
            "config": {k: v.to_dict() for k, v in self._config.items()},
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_fonts_manager() -> FontsManager:
    """Get or create the global FontsManager instance."""
    global _global_fonts_manager
    if _global_fonts_manager is None:
        _global_fonts_manager = FontsManager()
    return _global_fonts_manager


def initialize() -> FontsManager:
    """Initialize and return the global FontsManager."""
    return get_global_fonts_manager()


def refresh() -> FontsManager:
    """Refresh the global FontsManager."""
    global _global_fonts_manager
    _global_fonts_manager = FontsManager()
    return _global_fonts_manager
