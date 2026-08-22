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
XDG Session Manager - /usr/share/xsessions and /usr/share/wayland-sessions

Manages desktop session entries:
- X11 desktop sessions (.desktop files)
- Wayland desktop sessions (.desktop files)
- Session metadata (name, command, desktop names)
- Session icons
"""
from __future__ import annotations
from enum import IntEnum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Any
import uuid
import configparser


class SessionType(IntEnum):
    """Session type"""
    X11 = 0
    WAYLAND = 1
    MIR = 2


@dataclass
class DesktopSession:
    """A desktop session entry"""
    session_id: str
    name: str
    session_type: SessionType
    exec_command: str
    desktop_names: List[str] = field(default_factory=list)
    comment: str = ""
    try_exec: str = ""
    icon: str = ""
    file_path: str = ""
    is_default: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "session_type": self.session_type,
            "exec_command": self.exec_command,
            "desktop_names": self.desktop_names,
            "comment": self.comment,
            "try_exec": self.try_exec,
            "icon": self.icon,
            "file_path": self.file_path,
            "is_default": self.is_default,
        }


XSESSIONS_PATH = "/usr/share/xsessions"
WAYLAND_SESSIONS_PATH = "/usr/share/wayland-sessions"


class XDGSessionManager:
    """Manages desktop session entries"""

    def __init__(self):
        self._x11_sessions: Dict[str, DesktopSession] = {}
        self._wayland_sessions: Dict[str, DesktopSession] = {}
        self._x11_path = Path(XSESSIONS_PATH)
        self._wayland_path = Path(WAYLAND_SESSIONS_PATH)
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize the manager"""
        if self._initialized:
            return True
        self._x11_path.mkdir(parents=True, exist_ok=True)
        self._wayland_path.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        return True

    def refresh(self) -> bool:
        """Refresh from filesystem"""
        self._x11_sessions.clear()
        self._wayland_sessions.clear()

        self._scan_sessions(self._x11_path, SessionType.X11, self._x11_sessions)
        self._scan_sessions(self._wayland_path, SessionType.WAYLAND, self._wayland_sessions)

        return True

    def _scan_sessions(self, path: Path, session_type: SessionType, store: Dict[str, DesktopSession]):
        """Scan a directory for .desktop session files"""
        if not path.exists():
            return

        for desktop_file in path.glob("*.desktop"):
            session = self._parse_desktop_file(desktop_file, session_type)
            if session:
                store[session.session_id] = session

    def _parse_desktop_file(self, path: Path, session_type: SessionType) -> Optional[DesktopSession]:
        """Parse a .desktop file for session info"""
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(str(path))

            if "Desktop Entry" not in config:
                return None

            section = config["Desktop Entry"]
            exec_cmd = section.get("Exec", "")
            name = section.get("Name", path.stem)

            if not exec_cmd:
                return None

            desktop_names_str = section.get("DesktopNames", "")
            desktop_names = [n.strip() for n in desktop_names_str.split(";") if n.strip()]

            return DesktopSession(
                session_id=str(uuid.uuid4()),
                name=name,
                session_type=session_type,
                exec_command=exec_cmd,
                desktop_names=desktop_names,
                comment=section.get("Comment", ""),
                try_exec=section.get("TryExec", ""),
                icon=section.get("Icon", ""),
                file_path=str(path),
            )
        except Exception:
            return None

    def list_x11_sessions(self) -> List[Dict[str, Any]]:
        """List X11 sessions"""
        return [s.to_dict() for s in self._x11_sessions.values()]

    def list_wayland_sessions(self) -> List[Dict[str, Any]]:
        """List Wayland sessions"""
        return [s.to_dict() for s in self._wayland_sessions.values()]

    def list_all_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions"""
        all_sessions = list(self._x11_sessions.values()) + list(self._wayland_sessions.values())
        return [s.to_dict() for s in all_sessions]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID"""
        for store in [self._x11_sessions, self._wayland_sessions]:
            session = store.get(session_id)
            if session:
                return session.to_dict()
        return None

    def get_x11_path(self) -> Path:
        return self._x11_path

    def get_wayland_path(self) -> Path:
        return self._wayland_path

    def get_stats(self) -> Dict[str, int]:
        return {
            "x11_sessions": len(self._x11_sessions),
            "wayland_sessions": len(self._wayland_sessions),
            "total_sessions": len(self._x11_sessions) + len(self._wayland_sessions),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x11_path": str(self._x11_path),
            "wayland_path": str(self._wayland_path),
            "stats": self.get_stats(),
        }


_manager: Optional[XDGSessionManager] = None


def get_global_xdg_session_manager() -> XDGSessionManager:
    global _manager
    if _manager is None:
        _manager = XDGSessionManager()
    return _manager


def initialize() -> bool:
    return get_global_xdg_session_manager().initialize()


def refresh() -> bool:
    return get_global_xdg_session_manager().refresh()
