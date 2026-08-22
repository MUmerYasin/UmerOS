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
UmerOS X11 Fonts Manager (/usr/X11R6/lib/X11/fonts)
====================================================
XFree86/X11 system fonts used by the X Font Server (xfs).

  Filesystem Hierarchy - /usr/X11R6/lib/X11/fonts
  /usr/X11R6/lib/X11/fonts contains XFree86 system fonts.
  Fonts that are utilised by 'xfs' (the X Font Server) and programs
  of that ilk.

  Font types:
  - Type1 (.pfa/.pfb) - PostScript Type 1 fonts
  - TrueType (.ttf) - TrueType fonts
  - OpenType (.otf) - OpenType fonts
  - Bitmap (.bdf/.pcf) - Bitmap font formats
  - CID - CID-keyed fonts for CJK
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional


# ─── Constants ───────────────────────────────────────────────────────────────

X11_FONTS_PATH = "/usr/X11R6/lib/X11/fonts"

FONT_CATEGORIES = {
    "TYPE1": "PostScript Type 1 fonts (.pfa/.pfb)",
    "TRUETYPE": "TrueType fonts (.ttf)",
    "OPENTYPE": "OpenType fonts (.otf)",
    "BITMAP": "Bitmap fonts (.bdf/.pcf)",
    "CID": "CID-keyed fonts for CJK",
    "MISC": "Miscellaneous font formats",
}

DEFAULT_FONTS = [
    ("cursor", "Cursor font", "BITMAP", True),
    ("misc", "Miscellaneous fonts", "BITMAP", False),
    ("75dpi", "75 DPI fonts", "BITMAP", False),
    ("100dpi", "100 DPI fonts", "BITMAP", False),
    ("encum", "Encoding fonts", "TYPE1", False),
    ("util", "Utility fonts", "TYPE1", False),
    ("TTF", "TrueType font collection", "TRUETYPE", False),
    ("OTF", "OpenType font collection", "OPENTYPE", False),
]

FONT_ENCODINGS = [
    "iso8859-1", "iso8859-2", "iso8859-3", "iso8859-4", "iso8859-5",
    "iso8859-6", "iso8859-7", "iso8859-8", "iso8859-9", "iso8859-10",
    "iso8859-11", "iso8859-13", "iso8859-14", "iso8859-15", "iso8859-16",
    "koi8-r", "koi8-u", "koi8-f", "big5", "gb2312", "gbk", "shift_jis",
    "euc-jp", "euc-kr", "utf-8",
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class FontType(IntEnum):
    """Font types."""
    TYPE1 = 1
    TRUETYPE = 2
    OPENTYPE = 3
    BITMAP = 4
    CID = 5
    MISC = 6


class FontStatus(IntEnum):
    """Font status."""
    ACTIVE = 1
    INACTIVE = 2
    DISABLED = 3
    MISSING = 4


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class XFont:
    """An X11 font definition."""
    name: str
    path: str
    font_type: FontType = FontType.MISC
    description: str = ""
    family: str = ""
    style: str = ""
    weight: str = "regular"
    size: int = 0
    encoding: str = "iso8859-1"
    status: FontStatus = FontStatus.ACTIVE
    scalable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "path": self.path,
            "font_type": self.font_type.name, "description": self.description,
            "family": self.family, "style": self.style, "weight": self.weight,
            "size": self.size, "encoding": self.encoding,
            "status": self.status.name, "scalable": self.scalable,
        }


@dataclass
class FontDir:
    """A font directory."""
    name: str
    path: str
    description: str = ""
    fonts: List[XFont] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "path": self.path,
            "description": self.description, "fonts_count": len(self.fonts),
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_x11_fonts_manager: Optional["X11FontsManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class X11FontsManager:
    """Manages /usr/X11R6/lib/X11/fonts - X11 system fonts."""

    def __init__(self) -> None:
        self._fonts: Dict[str, XFont] = {}
        self._dirs: Dict[str, FontDir] = {}
        self._initialize_default_fonts()

    def _initialize_default_fonts(self) -> None:
        for name, desc, ftype, scalable in DEFAULT_FONTS:
            font = XFont(
                name=name, path=f"{X11_FONTS_PATH}/{name}",
                font_type=FontType[ftype], description=desc, scalable=scalable,
            )
            self._fonts[name] = font

    def get_font(self, name: str) -> Optional[XFont]:
        return self._fonts.get(name)

    def list_fonts(self, font_type: Optional[FontType] = None) -> List[XFont]:
        fonts = list(self._fonts.values())
        if font_type is not None:
            fonts = [f for f in fonts if f.font_type == font_type]
        return sorted(fonts, key=lambda f: f.name)

    def get_scalable_fonts(self) -> List[XFont]:
        return [f for f in self._fonts.values() if f.scalable]

    def search_fonts(self, query: str) -> List[XFont]:
        query_lower = query.lower()
        return [f for f in self._fonts.values()
                if query_lower in f.name.lower() or query_lower in f.description.lower()]

    def register_font(self, font: XFont) -> None:
        self._fonts[font.name] = font

    def get_statistics(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        for f in self._fonts.values():
            t = f.font_type.name
            by_type[t] = by_type.get(t, 0) + 1
        return {"total_fonts": len(self._fonts), "by_type": by_type}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fonts": {k: v.to_dict() for k, v in self._fonts.items()},
            "dirs": {k: v.to_dict() for k, v in self._dirs.items()},
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_x11_fonts_manager() -> X11FontsManager:
    global _global_x11_fonts_manager
    if _global_x11_fonts_manager is None:
        _global_x11_fonts_manager = X11FontsManager()
    return _global_x11_fonts_manager


def initialize() -> X11FontsManager:
    return get_global_x11_fonts_manager()


def refresh() -> X11FontsManager:
    global _global_x11_fonts_manager
    _global_x11_fonts_manager = X11FontsManager()
    return _global_x11_fonts_manager
