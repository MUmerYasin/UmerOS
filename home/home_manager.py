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
UmerOS /home Directory Manager
Core management of user home directories per FHS.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import stat
import shutil
import json


@dataclass
class HomeEntry:
    """Represents a user home directory."""
    username: str
    path: Path
    uid: int = 1000
    gid: int = 1000
    shell: str = "/bin/bash"
    created: bool = False
    size_bytes: int = 0
    dotfiles: List[str] = field(default_factory=list)


class HomeManager:
    """Manages /home directory structure per FHS."""

    DEFAULT_XDG_DIRS = [
        "Desktop", "Documents", "Downloads", "Music", "Pictures",
        "Public", "Templates", "Videos",
    ]

    DEFAULT_DOTFILES = [
        ".bashrc", ".bash_profile", ".profile", ".bash_logout",
        ".xsession", ".Xresources", ".xinitrc",
        ".config", ".local", ".cache",
    ]

    def __init__(self, home_path: str = "/home"):
        self.home_path = Path(home_path)
        self.users: Dict[str, HomeEntry] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        """Scan /home for existing user directories."""
        if not self.home_path.exists():
            self.home_path.mkdir(parents=True, exist_ok=True)
        for entry in self.home_path.iterdir():
            if entry.is_dir() and not entry.name.startswith('.'):
                self.users[entry.name] = HomeEntry(
                    username=entry.name,
                    path=entry,
                )

    def create_home(self, username: str, uid: int = 1000, gid: int = 1000,
                    shell: str = "/bin/bash", skel_path: str = "/etc/skel") -> HomeEntry:
        """Create a new user home directory with FHS structure."""
        user_home = self.home_path / username
        user_home.mkdir(parents=True, exist_ok=True)

        entry = HomeEntry(
            username=username,
            path=user_home,
            uid=uid,
            gid=gid,
            shell=shell,
            created=True,
        )

        # Create XDG directories
        for dirname in self.DEFAULT_XDG_DIRS:
            (user_home / dirname).mkdir(exist_ok=True)

        # Copy skel dotfiles
        skel = Path(skel_path)
        if skel.exists():
            for item in skel.iterdir():
                if item.name.startswith('.'):
                    dest = user_home / item.name
                    if item.is_dir():
                        shutil.copytree(str(item), str(dest), dirs_exist_ok=True)
                    else:
                        shutil.copy2(str(item), str(dest))

        # Set ownership (in real OS this would use os.chown)
        self._set_permissions(user_home, uid, gid)

        self.users[username] = entry
        return entry

    def remove_home(self, username: str, backup: bool = False) -> bool:
        """Remove a user home directory."""
        if username not in self.users:
            return False
        entry = self.users[username]
        if backup:
            backup_path = self.home_path / f".{username}.backup"
            if backup_path.exists():
                shutil.rmtree(str(backup_path))
            shutil.copytree(str(entry.path), str(backup_path))
        shutil.rmtree(str(entry.path))
        del self.users[username]
        return True

    def get_home(self, username: str) -> Optional[HomeEntry]:
        """Get a user's home entry."""
        return self.users.get(username)

    def get_home_path(self, username: str) -> Path:
        """Get a user's home directory path."""
        return self.home_path / username

    def list_users(self) -> List[str]:
        """List all users with home directories."""
        return list(self.users.keys())

    def get_disk_usage(self, username: str) -> int:
        """Get disk usage of a user's home directory."""
        user_home = self.home_path / username
        if not user_home.exists():
            return 0
        total = 0
        for f in user_home.rglob('*'):
            if f.is_file():
                total += f.stat().st_size
        return total

    def list_dotfiles(self, username: str) -> List[str]:
        """List dotfiles in a user's home directory."""
        user_home = self.home_path / username
        if not user_home.exists():
            return []
        return [f.name for f in user_home.iterdir()
                if f.name.startswith('.') and f.is_file()]

    def list_dotdirs(self, username: str) -> List[str]:
        """List dot directories in a user's home directory."""
        user_home = self.home_path / username
        if not user_home.exists():
            return []
        return [d.name for d in user_home.iterdir()
                if d.name.startswith('.') and d.is_dir()]

    def _set_permissions(self, path: Path, uid: int, gid: int) -> None:
        """Set ownership and permissions on home directory."""
        try:
            path.chmod(0o755)
        except (OSError, PermissionError):
            pass

    def get_home_info(self, username: str) -> Dict:
        """Get comprehensive info about a user's home."""
        entry = self.users.get(username)
        if not entry:
            return {}
        return {
            "username": username,
            "path": str(entry.path),
            "uid": entry.uid,
            "gid": entry.gid,
            "shell": entry.shell,
            "disk_usage": self.get_disk_usage(username),
            "dotfiles": self.list_dotfiles(username),
            "dotdirs": self.list_dotdirs(username),
            "xdg_dirs": [d for d in self.DEFAULT_XDG_DIRS
                         if (entry.path / d).exists()],
        }
