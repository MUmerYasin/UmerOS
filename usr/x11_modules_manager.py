"""
UmerOS X11 Modules Manager (/usr/X11R6/lib/modules)
====================================================
XFree86/X11 system modules - video, DRI, GLX, input drivers.

Reference: Linux Filesystem Hierarchy - /usr/X11R6/lib/modules
  /usr/X11R6/lib/modules contains the modules that X loads upon startup.
  Without these modules video4linux, DRI and GLX extensions and drivers
  for certain input devices would cease to function.

  Typical module types:
  - Video drivers (nvidia, ati, intel, nouveau)
  - Input drivers (evdev, synaptics, wacom)
  - Extension modules (GLX, DRI, Composite)
  - Font modules (freetype, type1)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional


# ─── Constants ───────────────────────────────────────────────────────────────

X11_MODULES_PATH = "/usr/X11R6/lib/modules"

MODULE_CATEGORIES = {
    "VIDEO": "Video/display drivers",
    "INPUT": "Input device drivers",
    "EXTENSION": "X11 extension modules",
    "FONT": "Font rendering modules",
    "RENDER": "Render acceleration modules",
    "MISC": "Miscellaneous modules",
}

DEFAULT_VIDEO_DRIVERS = [
    ("nvidia", "NVIDIA proprietary driver", True),
    ("nouveau", "NVIDIA open-source driver", True),
    ("ati", "ATI/AMD Radeon driver", True),
    ("intel", "Intel integrated graphics", True),
    ("modesetting", "Kernel modesetting driver", True),
    ("vesa", "Generic VESA driver", False),
    ("fbdev", "Framebuffer device driver", False),
]

DEFAULT_INPUT_DRIVERS = [
    ("evdev", "Generic event-driven input", True),
    ("synaptics", "Synaptics touchpad driver", True),
    ("libinput", "Generic input library", True),
    ("wacom", "Wacom tablet driver", True),
    ("mouse", "Generic mouse driver", False),
    ("keyboard", "Generic keyboard driver", False),
]

DEFAULT_EXTENSION_MODULES = [
    ("glx", "OpenGL Extension to X", True),
    ("dri", "Direct Rendering Infrastructure", True),
    ("composite", "Compositing manager extension", True),
    ("randr", "Resize and Rotate extension", True),
    ("xinerama", "Xinerama extension", False),
    ("record", "Record extension", False),
    ("xfixes", "X Fixes extension", True),
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class ModuleCategory(IntEnum):
    """Module categories."""
    VIDEO = 1
    INPUT = 2
    EXTENSION = 3
    FONT = 4
    RENDER = 5
    MISC = 6


class ModuleStatus(IntEnum):
    """Module status."""
    ACTIVE = 1
    INACTIVE = 2
    DISABLED = 3
    MISSING = 4
    BROKEN = 5


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class XModule:
    """An X11 module definition."""
    name: str
    path: str
    category: ModuleCategory = ModuleCategory.MISC
    description: str = ""
    filename: str = ""
    version: str = ""
    status: ModuleStatus = ModuleStatus.ACTIVE
    required: bool = False
    dependencies: List[str] = field(default_factory=list)
    size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "path": self.path,
            "category": self.category.name, "description": self.description,
            "filename": self.filename, "version": self.version,
            "status": self.status.name, "required": self.required,
            "dependencies": self.dependencies, "size_bytes": self.size_bytes,
        }


@dataclass
class XModuleGroup:
    """A group of related X11 modules."""
    name: str
    description: str = ""
    modules: List[XModule] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "description": self.description,
            "modules_count": len(self.modules),
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_x11_modules_manager: Optional["X11ModulesManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class X11ModulesManager:
    """Manages /usr/X11R6/lib/modules - X11 system modules."""

    def __init__(self) -> None:
        self._modules: Dict[str, XModule] = {}
        self._groups: Dict[str, XModuleGroup] = {}
        self._initialize_default_modules()

    def _initialize_default_modules(self) -> None:
        """Initialize with common X11 modules."""
        for name, desc, required in DEFAULT_VIDEO_DRIVERS:
            self._modules[name] = XModule(
                name=name, path=f"{X11_MODULES_PATH}/drivers/{name}.so",
                category=ModuleCategory.VIDEO, description=desc,
                filename=f"{name}.so", required=required,
            )

        for name, desc, required in DEFAULT_INPUT_DRIVERS:
            self._modules[name] = XModule(
                name=name, path=f"{X11_MODULES_PATH}/input/{name}.so",
                category=ModuleCategory.INPUT, description=desc,
                filename=f"{name}.so", required=required,
            )

        for name, desc, required in DEFAULT_EXTENSION_MODULES:
            self._modules[name] = XModule(
                name=name, path=f"{X11_MODULES_PATH}/extensions/{name}.so",
                category=ModuleCategory.EXTENSION, description=desc,
                filename=f"{name}.so", required=required,
            )

    def get_module(self, name: str) -> Optional[XModule]:
        return self._modules.get(name)

    def list_modules(self, category: Optional[ModuleCategory] = None) -> List[XModule]:
        modules = list(self._modules.values())
        if category is not None:
            modules = [m for m in modules if m.category == category]
        return sorted(modules, key=lambda m: m.name)

    def get_required_modules(self) -> List[XModule]:
        return [m for m in self._modules.values() if m.required]

    def get_active_modules(self) -> List[XModule]:
        return [m for m in self._modules.values() if m.status == ModuleStatus.ACTIVE]

    def search_modules(self, query: str) -> List[XModule]:
        query_lower = query.lower()
        return [m for m in self._modules.values()
                if query_lower in m.name.lower() or query_lower in m.description.lower()]

    def register_module(self, module: XModule) -> None:
        self._modules[module.name] = module

    def disable_module(self, name: str) -> bool:
        module = self._modules.get(name)
        if module:
            module.status = ModuleStatus.DISABLED
            return True
        return False

    def enable_module(self, name: str) -> bool:
        module = self._modules.get(name)
        if module:
            module.status = ModuleStatus.ACTIVE
            return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        by_cat: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for m in self._modules.values():
            c = m.category.name
            s = m.status.name
            by_cat[c] = by_cat.get(c, 0) + 1
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "total_modules": len(self._modules),
            "by_category": by_cat, "by_status": by_status,
            "required_count": len(self.get_required_modules()),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modules": {k: v.to_dict() for k, v in self._modules.items()},
            "groups": {k: v.to_dict() for k, v in self._groups.items()},
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_x11_modules_manager() -> X11ModulesManager:
    global _global_x11_modules_manager
    if _global_x11_modules_manager is None:
        _global_x11_modules_manager = X11ModulesManager()
    return _global_x11_modules_manager


def initialize() -> X11ModulesManager:
    return get_global_x11_modules_manager()


def refresh() -> X11ModulesManager:
    global _global_x11_modules_manager
    _global_x11_modules_manager = X11ModulesManager()
    return _global_x11_modules_manager
