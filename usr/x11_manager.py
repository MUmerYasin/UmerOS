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
UmerOS X11 Window System (/usr/X11R6)
======================================
X11/X.Org display server and window management.

Reference: Filesystem Hierarchy - /usr/X11R6
  /usr/X11R6 contains X Window System binaries, libraries,
  and data files for the X11R6 release. Modern systems often
  use /usr/lib/X11R6 or integrate X11 into standard paths.

UmerOS Virtualization:
  /usr/X11R6 serves as the display server management root,
  providing windowing, display protocols, and GUI application
  support for the UmerOS desktop environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ─── Constants ───────────────────────────────────────────────────────────────

X11_PATHS = {
    "bin": "/usr/X11R6/bin",
    "lib": "/usr/X11R6/lib",
    "include": "/usr/X11R6/include",
    "share": "/usr/X11R6/share",
    "man": "/usr/X11R6/man",
}

X11_PROTOCOLS = {
    "X11": {"version": "11", "release": "R6", "port": 6000},
    "XCB": {"version": "1.14", "description": "X C Binding"},
    "Xlib": {"version": "1.7", "description": "Xlib library"},
    "Xrender": {"version": "0.11", "description": "X Rendering Extension"},
    "Xdamage": {"version": "1.1", "description": "X Damage Extension"},
    "Xfixes": {"version": "6.0", "description": "X Fixes Extension"},
    "Xcomposite": {"version": "0.4", "description": "X Composite Extension"},
    "Xinerama": {"version": "1.1", "description": "Xinerama Extension"},
    "Xrandr": {"version": "1.5", "description": "X Resize and Rotate"},
    "Xcursor": {"version": "1.2", "description": "X Cursor Management"},
}

X11_EVENTS = [
    "KeyPress", "KeyRelease", "ButtonPress", "ButtonRelease",
    "MotionNotify", "EnterNotify", "LeaveNotify", "FocusIn",
    "FocusOut", "KeymapNotify", "Expose", "GraphicsExposure",
    "NoExposure", "VisibilityNotify", "CreateNotify", "DestroyNotify",
    "UnmapNotify", "MapNotify", "MapRequest", "ReparentNotify",
    "ConfigureNotify", "ConfigureRequest", "GravityNotify",
    "ResizeRequest", "CirculateNotify", "CirculateRequest",
    "PropertyNotify", "SelectionClear", "SelectionRequest",
    "SelectionNotify", "ColormapNotify", "ClientMessage",
    "MappingNotify",
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class X11Component(IntEnum):
    """X11 system components."""
    DISPLAY_SERVER = 1
    WINDOW_MANAGER = 2
    DISPLAY_MANAGER = 3
    FONT_SERVER = 4
    TOOLKIT = 5
    FONT = 6
    INPUT_METHOD = 7
    ACCESSIBILITY = 8
    SCREEN_SAVER = 9
    COMPOSITE_MANAGER = 10


class X11WindowState(IntEnum):
    """Window states."""
    NORMAL = 1
    MAXIMIZED = 2
    MINIMIZED = 3
    FULLSCREEN = 4
    ABOVE = 5
    BELOW = 6
    MODAL = 7
    SHADED = 8
    STICKY = 9
    UNDECORATED = 10


class X11WindowType(IntEnum):
    """Window types."""
    TOPLEVEL = 1
    DIALOG = 2
    MENU = 3
    UTILITY = 4
    DOCK = 5
    DESKTOP = 6
    SPLASH = 7
    TOOLBAR = 8
    POPUP_MENU = 9
    DROPDOWN_MENU = 10
    TOOLTIP = 11


class X11InputDevice(IntEnum):
    """Input device types."""
    KEYBOARD = 1
    MOUSE = 2
    TOUCHSCREEN = 3
    TABLET = 4
    TRACKPAD = 5
    JOYSTICK = 6
    OTHER = 7


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class X11Display:
    """Represents an X11 display."""
    name: str
    screen_count: int = 1
    depth: int = 24
    width: int = 1920
    height: int = 1080
    vendor: str = "UmerOS"
    renderer: str = "X.Org"
    version: str = "1.21"
    extensions: List[str] = field(default_factory=list)
    screens: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "screen_count": self.screen_count,
            "depth": self.depth,
            "width": self.width,
            "height": self.height,
            "vendor": self.vendor,
            "renderer": self.renderer,
            "version": self.version,
            "extensions": self.extensions,
            "screen_count": len(self.screens),
        }


@dataclass
class X11Window:
    """Represents an X11 window."""
    window_id: int
    title: str = ""
    window_type: X11WindowType = X11WindowType.TOPLEVEL
    state: X11WindowState = X11WindowState.NORMAL
    x: int = 0
    y: int = 0
    width: int = 800
    height: int = 600
    border_width: int = 1
    parent_id: int = 0
    class_name: str = ""
    instance_name: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "title": self.title,
            "type": self.window_type.name,
            "state": self.state.name,
            "geometry": {"x": self.x, "y": self.y, "width": self.width, "height": self.height},
            "border_width": self.border_width,
            "parent_id": self.parent_id,
            "class_name": self.class_name,
            "instance_name": self.instance_name,
        }


@dataclass
class X11Screen:
    """Represents a screen/monitor."""
    screen_id: int
    width: int = 1920
    height: int = 1080
    depth: int = 24
    root_window: int = 0
    name: str = ""
    manufacturer: str = ""
    model: str = ""
    refresh_rate: float = 60.0
    is_primary: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "screen_id": self.screen_id,
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "root_window": self.root_window,
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "refresh_rate": self.refresh_rate,
            "is_primary": self.is_primary,
        }


@dataclass
class X11Font:
    """Represents an X11 font."""
    name: str
    family: str = ""
    style: str = "Regular"
    size: int = 12
    path: str = ""
    encoding: str = "iso8859-1"
    charset: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "style": self.style,
            "size": self.size,
            "path": self.path,
            "encoding": self.encoding,
            "charset": self.charset,
        }


@dataclass
class X11Event:
    """Represents an X11 event."""
    event_type: str
    window_id: int = 0
    timestamp: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "window_id": self.window_id,
            "timestamp": self.timestamp,
            "data": self.data,
        }


@dataclass
class X11InputDevice:
    """Represents an input device."""
    device_id: int
    name: str
    device_type: X11InputDevice = X11InputDevice.MOUSE
    is_enabled: bool = True
    is_pointer: bool = True
    is_keyboard: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "type": self.device_type.name,
            "is_enabled": self.is_enabled,
            "is_pointer": self.is_pointer,
            "is_keyboard": self.is_keyboard,
        }


@dataclass
class X11WindowStateSnapshot:
    """Snapshot of all windows."""
    timestamp: float = 0.0
    windows: List[X11Window] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "window_count": len(self.windows),
            "windows": [w.to_dict() for w in self.windows],
        }


# ─── X11 Window System Manager ──────────────────────────────────────────────

class X11Manager:
    """
    Manages /usr/X11R6 - X11 Window System.

    Responsibilities:
        - Track display server configuration
        - Manage virtual windows and screens
        - Handle window state transitions
        - Provide font and input device management
        - Simulate X11 protocol events
        - Track display properties and extensions
        - Support multiple screen configurations
        - Manage window stacking and focus
    """

    def __init__(self) -> None:
        self._displays: Dict[str, X11Display] = {}
        self._windows: Dict[int, X11Window] = {}
        self._screens: Dict[int, X11Screen] = {}
        self._fonts: Dict[str, X11Font] = {}
        self._input_devices: Dict[int, X11InputDevice] = {}
        self._events: List[X11Event] = []
        self._next_window_id = 1
        self._next_device_id = 1
        self._initialized = False

    def initialize(self) -> None:
        """Initialize X11 manager."""
        if self._initialized:
            return
        self._setup_default_display()
        self._setup_default_screens()
        self._setup_default_fonts()
        self._setup_default_devices()
        self._initialized = True

    def _setup_default_display(self) -> None:
        """Set up default display configuration."""
        self._displays[":0"] = X11Display(
            name=":0",
            screen_count=1,
            depth=24,
            width=1920,
            height=1080,
            extensions=list(X11_PROTOCOLS.keys()),
        )

    def _setup_default_screens(self) -> None:
        """Set up default screens."""
        self._screens[0] = X11Screen(
            screen_id=0,
            width=1920,
            height=1080,
            depth=24,
            root_window=0,
            name="Primary",
            manufacturer="UmerOS",
            model="Default",
            is_primary=True,
        )

    def _setup_default_fonts(self) -> None:
        """Set up default fonts."""
        default_fonts = [
            ("monospace", "Monospace", "Regular", 12),
            ("serif", "Serif", "Regular", 12),
            ("sans-serif", "Sans-Serif", "Regular", 12),
            ("cursor", "Cursor", "Regular", 12),
        ]
        for name, family, style, size in default_fonts:
            self._fonts[name] = X11Font(
                name=name, family=family, style=style, size=size
            )

    def _setup_default_devices(self) -> None:
        """Set up default input devices."""
        self._input_devices[1] = X11InputDevice(
            device_id=1, name="keyboard", device_type=X11InputDevice.KEYBOARD,
            is_pointer=False, is_keyboard=True,
        )
        self._input_devices[2] = X11InputDevice(
            device_id=2, name="mouse", device_type=X11InputDevice.MOUSE,
            is_pointer=True, is_keyboard=False,
        )

    # ─── Display Management ──────────────────────────────────────────────

    def get_display(self, name: str = ":0") -> Optional[X11Display]:
        """Get display configuration."""
        return self._displays.get(name)

    def list_displays(self) -> List[X11Display]:
        """List all displays."""
        return list(self._displays.values())

    def update_display(self, name: str, **kwargs: Any) -> bool:
        """Update display properties."""
        display = self._displays.get(name)
        if not display:
            return False
        for key, value in kwargs.items():
            if hasattr(display, key):
                setattr(display, key, value)
        return True

    # ─── Screen Management ───────────────────────────────────────────────

    def get_screen(self, screen_id: int) -> Optional[X11Screen]:
        """Get screen by ID."""
        return self._screens.get(screen_id)

    def list_screens(self) -> List[X11Screen]:
        """List all screens."""
        return list(self._screens.values())

    def add_screen(self, screen: X11Screen) -> bool:
        """Add a new screen."""
        if screen.screen_id in self._screens:
            return False
        self._screens[screen.screen_id] = screen
        return True

    def remove_screen(self, screen_id: int) -> bool:
        """Remove a screen."""
        if screen_id not in self._screens:
            return False
        del self._screens[screen_id]
        return True

    def get_total_resolution(self) -> Dict[str, int]:
        """Get total resolution across all screens."""
        total_width = sum(s.width for s in self._screens.values())
        max_height = max((s.height for s in self._screens.values()), default=0)
        return {"width": total_width, "height": max_height}

    # ─── Window Management ───────────────────────────────────────────────

    def create_window(
        self,
        title: str = "",
        window_type: X11WindowType = X11WindowType.TOPLEVEL,
        x: int = 0, y: int = 0,
        width: int = 800, height: int = 600,
        class_name: str = "",
    ) -> X11Window:
        """Create a new window."""
        window_id = self._next_window_id
        self._next_window_id += 1

        window = X11Window(
            window_id=window_id,
            title=title,
            window_type=window_type,
            x=x, y=y, width=width, height=height,
            class_name=class_name,
        )
        self._windows[window_id] = window
        self._emit_event("CreateNotify", window_id)
        return window

    def destroy_window(self, window_id: int) -> bool:
        """Destroy a window."""
        if window_id not in self._windows:
            return False
        del self._windows[window_id]
        self._emit_event("DestroyNotify", window_id)
        return True

    def get_window(self, window_id: int) -> Optional[X11Window]:
        """Get window by ID."""
        return self._windows.get(window_id)

    def list_windows(self) -> List[X11Window]:
        """List all windows."""
        return list(self._windows.values())

    def find_windows(self, title: str) -> List[X11Window]:
        """Find windows by title (partial match)."""
        title_lower = title.lower()
        return [w for w in self._windows.values() if title_lower in w.title.lower()]

    def set_window_title(self, window_id: int, title: str) -> bool:
        """Set window title."""
        window = self._windows.get(window_id)
        if not window:
            return False
        window.title = title
        return True

    def set_window_state(self, window_id: int, state: X11WindowState) -> bool:
        """Set window state."""
        window = self._windows.get(window_id)
        if not window:
            return False
        window.state = state
        return True

    def move_window(self, window_id: int, x: int, y: int) -> bool:
        """Move a window."""
        window = self._windows.get(window_id)
        if not window:
            return False
        window.x = x
        window.y = y
        self._emit_event("ConfigureNotify", window_id)
        return True

    def resize_window(self, window_id: int, width: int, height: int) -> bool:
        """Resize a window."""
        window = self._windows.get(window_id)
        if not window:
            return False
        window.width = width
        window.height = height
        self._emit_event("ConfigureNotify", window_id)
        return True

    def maximize_window(self, window_id: int) -> bool:
        """Maximize a window."""
        return self.set_window_state(window_id, X11WindowState.MAXIMIZED)

    def minimize_window(self, window_id: int) -> bool:
        """Minimize a window."""
        return self.set_window_state(window_id, X11WindowState.MINIMIZED)

    def restore_window(self, window_id: int) -> bool:
        """Restore a window to normal state."""
        return self.set_window_state(window_id, X11WindowState.NORMAL)

    def fullscreen_window(self, window_id: int) -> bool:
        """Make a window fullscreen."""
        return self.set_window_state(window_id, X11WindowState.FULLSCREEN)

    def stack_above(self, window_id: int) -> bool:
        """Raise window above others."""
        return self.set_window_state(window_id, X11WindowState.ABOVE)

    def stack_below(self, window_id: int) -> bool:
        """Lower window below others."""
        return self.set_window_state(window_id, X11WindowState.BELOW)

    def get_window_stack(self) -> List[X11Window]:
        """Get windows in stacking order (top first)."""
        above = [w for w in self._windows.values() if w.state == X11WindowState.ABOVE]
        normal = [w for w in self._windows.values() if w.state == X11WindowState.NORMAL]
        below = [w for w in self._windows.values() if w.state == X11WindowState.BELOW]
        return above + normal + below

    # ─── Font Management ─────────────────────────────────────────────────

    def get_font(self, name: str) -> Optional[X11Font]:
        """Get font by name."""
        return self._fonts.get(name)

    def list_fonts(self) -> List[X11Font]:
        """List all fonts."""
        return list(self._fonts.values())

    def add_font(self, font: X11Font) -> bool:
        """Add a font."""
        if font.name in self._fonts:
            return False
        self._fonts[font.name] = font
        return True

    def find_fonts(self, family: str) -> List[X11Font]:
        """Find fonts by family."""
        family_lower = family.lower()
        return [f for f in self._fonts.values() if family_lower in f.family.lower()]

    # ─── Input Device Management ─────────────────────────────────────────

    def get_input_device(self, device_id: int) -> Optional[X11InputDevice]:
        """Get input device by ID."""
        return self._input_devices.get(device_id)

    def list_input_devices(self) -> List[X11InputDevice]:
        """List all input devices."""
        return list(self._input_devices.values())

    def add_input_device(self, device: X11InputDevice) -> bool:
        """Add an input device."""
        device.device_id = self._next_device_id
        self._next_device_id += 1
        self._input_devices[device.device_id] = device
        return True

    def enable_device(self, device_id: int) -> bool:
        """Enable an input device."""
        device = self._input_devices.get(device_id)
        if not device:
            return False
        device.is_enabled = True
        return True

    def disable_device(self, device_id: int) -> bool:
        """Disable an input device."""
        device = self._input_devices.get(device_id)
        if not device:
            return False
        device.is_enabled = False
        return True

    # ─── Event Management ────────────────────────────────────────────────

    def _emit_event(self, event_type: str, window_id: int = 0, data: Optional[Dict] = None) -> None:
        """Emit an X11 event."""
        import time
        event = X11Event(
            event_type=event_type,
            window_id=window_id,
            timestamp=time.time(),
            data=data or {},
        )
        self._events.append(event)

    def get_events(self, limit: int = 100) -> List[X11Event]:
        """Get recent events."""
        return self._events[-limit:]

    def clear_events(self) -> None:
        """Clear event queue."""
        self._events.clear()

    # ─── Statistics ──────────────────────────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        """Get X11 system statistics."""
        return {
            "displays": len(self._displays),
            "screens": len(self._screens),
            "windows": len(self._windows),
            "fonts": len(self._fonts),
            "input_devices": len(self._input_devices),
            "events": len(self._events),
            "protocols": list(X11_PROTOCOLS.keys()),
        }

    def refresh(self) -> None:
        """Reset X11 manager."""
        self._displays.clear()
        self._windows.clear()
        self._screens.clear()
        self._fonts.clear()
        self._input_devices.clear()
        self._events.clear()
        self._next_window_id = 1
        self._next_device_id = 1
        self._initialized = False
        self.initialize()


# ─── Global Singleton ────────────────────────────────────────────────────────

_global_x11_manager: Optional[X11Manager] = None


def get_global_x11_manager() -> X11Manager:
    """Get or create the global X11 manager."""
    global _global_x11_manager
    if _global_x11_manager is None:
        _global_x11_manager = X11Manager()
        _global_x11_manager.initialize()
    return _global_x11_manager
