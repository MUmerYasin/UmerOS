"""
UmerOS Color Definitions Manager (/usr/share/colors)
=====================================================
System color definition files and palettes.

  Filesystem Hierarchy - /usr/share/colors
  /usr/share/colors contains color definition files used by desktop
  environments and applications for consistent color schemes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ─── Constants ───────────────────────────────────────────────────────────────

COLORS_PATH = "/usr/share/colors"

COLOR_NAMES = [
    "aliceblue", "antiquewhite", "aqua", "aquamarine", "azure",
    "beige", "bisque", "black", "blanchedalmond", "blue",
    "blueviolet", "brown", "burlywood", "cadetblue", "chartreuse",
    "chocolate", "coral", "cornflowerblue", "cornsilk", "crimson",
    "cyan", "darkblue", "darkcyan", "darkgoldenrod", "darkgray",
    "darkgreen", "darkgrey", "darkkhaki", "darkmagenta", "darkolivegreen",
    "darkorange", "darkorchid", "darkred", "darksalmon", "darkseagreen",
    "darkslateblue", "darkslategray", "darkslategrey", "darkturquoise", "darkviolet",
    "deeppink", "deepskyblue", "dimgray", "dimgrey", "dodgerblue",
    "firebrick", "floralwhite", "forestgreen", "fuchsia", "gainsboro",
    "ghostwhite", "gold", "goldenrod", "gray", "green",
    "greenyellow", "grey", "honeydew", "hotpink", "indianred",
    "indigo", "ivory", "khaki", "lavender", "lavenderblush",
    "lawngreen", "lemonchiffon", "lightblue", "lightcoral", "lightcyan",
    "lightgoldenrodyellow", "lightgray", "lightgreen", "lightgrey", "lightpink",
    "lightsalmon", "lightseagreen", "lightskyblue", "lightslategray", "lightslategrey",
    "lightsteelblue", "lightyellow", "lime", "limegreen", "linen",
    "magenta", "maroon", "mediumaquamarine", "mediumblue", "mediumorchid",
    "mediumpurple", "mediumseagreen", "mediumslateblue", "mediumspringgreen", "mediumturquoise",
    "mediumvioletred", "midnightblue", "mintcream", "mistyrose", "moccasin",
    "navajowhite", "navy", "oldlace", "olive", "olivedrab",
    "orange", "orangered", "orchid", "palegoldenrod", "palegreen",
    "paleturquoise", "palevioletred", "papayawhip", "peachpuff", "peru",
    "pink", "plum", "powderblue", "purple", "rebeccapurple",
    "red", "rosybrown", "royalblue", "saddlebrown", "salmon",
    "sandybrown", "seagreen", "seashell", "sienna", "silver",
    "skyblue", "slateblue", "slategray", "slategrey", "snow",
    "springgreen", "steelblue", "tan", "teal", "thistle",
    "tomato", "turquoise", "violet", "wheat", "white",
    "whitesmoke", "yellow", "yellowgreen",
]

# Named color palettes
COLOR_PALETTES = {
    "gnome": {
        "blue": "#3584e4",
        "green": "#33d17a",
        "red": "#e01b24",
        "yellow": "#f6d32d",
        "orange": "#ff7800",
        "purple": "#9141ac",
    },
    "kde": {
        "blue": "#2196f3",
        "green": "#4caf50",
        "red": "#f44336",
        "yellow": "#ffeb3b",
        "orange": "#ff9800",
        "purple": "#9c27b0",
    },
    "xfce": {
        "blue": "#3498db",
        "green": "#2ecc71",
        "red": "#e74c3c",
        "yellow": "#f1c40f",
        "orange": "#e67e22",
        "purple": "#9b59b6",
    },
}


# ─── Enums ───────────────────────────────────────────────────────────────────

class ColorFormat(IntEnum):
    """Color code formats."""
    HEX = 1
    RGB = 2
    RGBA = 3
    HSL = 4
    HSV = 5
    CMYK = 6
    NAMED = 7


class ColorProfile(IntEnum):
    """Color profile types."""
    SRGB = 1
    ADOBERGB = 2
    PROPHOTORGB = 3
    CUSTOM = 4


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class ColorValue:
    """Represents a color value in various formats."""
    name: str = ""
    hex_value: str = "#000000"
    rgb: Tuple[int, int, int] = (0, 0, 0)
    rgba: Tuple[int, int, int, int] = (0, 0, 0, 255)
    alpha: float = 1.0
    format: ColorFormat = ColorFormat.HEX

    def to_hex(self) -> str:
        """Get hex representation."""
        if self.hex_value:
            return self.hex_value
        r, g, b = self.rgb[:3]
        return f"#{r:02x}{g:02x}{b:02x}"

    def to_rgb(self) -> Tuple[int, int, int]:
        """Get RGB tuple."""
        if self.rgb != (0, 0, 0):
            return self.rgb
        if self.hex_value and self.hex_value.startswith("#"):
            h = self.hex_value.lstrip("#")
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        return (0, 0, 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "hex": self.to_hex(),
            "rgb": list(self.to_rgb()),
            "rgba": list(self.rgba),
            "alpha": self.alpha,
            "format": self.format.name,
        }


@dataclass
class ColorPalette:
    """A named collection of colors."""
    name: str
    description: str = ""
    colors: Dict[str, ColorValue] = field(default_factory=dict)
    profile: ColorProfile = ColorProfile.SRGB

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "colors": {k: v.to_dict() for k, v in self.colors.items()},
            "profile": self.profile.name,
        }


@dataclass
class ColorTheme:
    """A complete color theme for an application or desktop."""
    name: str
    description: str = ""
    palettes: List[str] = field(default_factory=list)
    foreground: ColorValue = field(default_factory=ColorValue)
    background: ColorValue = field(default_factory=ColorValue)
    accent: ColorValue = field(default_factory=ColorValue)
    error: ColorValue = field(default_factory=ColorValue)
    warning: ColorValue = field(default_factory=ColorValue)
    success: ColorValue = field(default_factory=ColorValue)
    info: ColorValue = field(default_factory=ColorValue)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "palettes": self.palettes,
            "foreground": self.foreground.to_dict(),
            "background": self.background.to_dict(),
            "accent": self.accent.to_dict(),
            "error": self.error.to_dict(),
            "warning": self.warning.to_dict(),
            "success": self.success.to_dict(),
            "info": self.info.to_dict(),
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_colors_manager: Optional["ColorsManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class ColorsManager:
    """Manages /usr/share/colors - color definitions."""

    def __init__(self) -> None:
        self._colors: Dict[str, ColorValue] = {}
        self._palettes: Dict[str, ColorPalette] = {}
        self._themes: Dict[str, ColorTheme] = {}
        self._initialize_default_colors()
        self._initialize_default_palettes()
        self._initialize_default_themes()

    def _initialize_default_colors(self) -> None:
        """Initialize with common color names."""
        for name in COLOR_NAMES:
            self._colors[name] = ColorValue(name=name, hex_value=f"#{name}")

    def _initialize_default_palettes(self) -> None:
        """Initialize default palettes."""
        for palette_name, colors in COLOR_PALETTES.items():
            palette = ColorPalette(name=palette_name)
            for color_name, hex_val in colors.items():
                palette.colors[color_name] = ColorValue(name=color_name, hex_value=hex_val)
            self._palettes[palette_name] = palette

    def _initialize_default_themes(self) -> None:
        """Initialize default themes."""
        self._themes["light"] = ColorTheme(
            name="light",
            description="Light color theme",
            foreground=ColorValue(name="foreground", hex_value="#000000"),
            background=ColorValue(name="background", hex_value="#ffffff"),
            accent=ColorValue(name="accent", hex_value="#3584e4"),
            error=ColorValue(name="error", hex_value="#e01b24"),
            warning=ColorValue(name="warning", hex_value="#f6d32d"),
            success=ColorValue(name="success", hex_value="#33d17a"),
            info=ColorValue(name="info", hex_value="#2196f3"),
        )
        self._themes["dark"] = ColorTheme(
            name="dark",
            description="Dark color theme",
            foreground=ColorValue(name="foreground", hex_value="#ffffff"),
            background=ColorValue(name="background", hex_value="#1e1e1e"),
            accent=ColorValue(name="accent", hex_value="#7aa2f7"),
            error=ColorValue(name="error", hex_value="#f44336"),
            warning=ColorValue(name="warning", hex_value="#ffeb3b"),
            success=ColorValue(name="success", hex_value="#4caf50"),
            info=ColorValue(name="info", hex_value="#2196f3"),
        )

    def get_color(self, name: str) -> Optional[ColorValue]:
        """Get a color by name."""
        return self._colors.get(name)

    def register_color(self, color: ColorValue) -> None:
        """Register a new color."""
        self._colors[color.name] = color

    def search_colors(self, query: str) -> List[ColorValue]:
        """Search colors by name."""
        query_lower = query.lower()
        return [c for c in self._colors.values() if query_lower in c.name.lower()]

    def get_palette(self, name: str) -> Optional[ColorPalette]:
        """Get a palette by name."""
        return self._palettes.get(name)

    def list_palettes(self) -> List[ColorPalette]:
        """List all palettes."""
        return sorted(self._palettes.values(), key=lambda p: p.name)

    def register_palette(self, palette: ColorPalette) -> None:
        """Register a new palette."""
        self._palettes[palette.name] = palette

    def get_theme(self, name: str) -> Optional[ColorTheme]:
        """Get a theme by name."""
        return self._themes.get(name)

    def list_themes(self) -> List[ColorTheme]:
        """List all themes."""
        return sorted(self._themes.values(), key=lambda t: t.name)

    def register_theme(self, theme: ColorTheme) -> None:
        """Register a new theme."""
        self._themes[theme.name] = theme

    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB."""
        h = hex_color.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """Convert RGB to hex color."""
        return f"#{r:02x}{g:02x}{b:02x}"

    def get_complementary(self, color: ColorValue) -> ColorValue:
        """Get complementary color."""
        r, g, b = color.to_rgb()
        comp_hex = self.rgb_to_hex(255 - r, 255 - g, 255 - b)
        return ColorValue(name=f"{color.name}-complementary", hex_value=comp_hex)

    def get_statistics(self) -> Dict[str, Any]:
        """Get colors statistics."""
        return {
            "total_colors": len(self._colors),
            "total_palettes": len(self._palettes),
            "total_themes": len(self._themes),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "colors": {k: v.to_dict() for k, v in self._colors.items()},
            "palettes": {k: v.to_dict() for k, v in self._palettes.items()},
            "themes": {k: v.to_dict() for k, v in self._themes.items()},
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_colors_manager() -> ColorsManager:
    """Get or create the global ColorsManager instance."""
    global _global_colors_manager
    if _global_colors_manager is None:
        _global_colors_manager = ColorsManager()
    return _global_colors_manager


def initialize() -> ColorsManager:
    """Initialize and return the global ColorsManager."""
    return get_global_colors_manager()


def refresh() -> ColorsManager:
    """Refresh the global ColorsManager."""
    global _global_colors_manager
    _global_colors_manager = ColorsManager()
    return _global_colors_manager
