"""
UmerOS Home Directories Manager
Manages standard XDG and FHS subdirectories in user homes.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import shutil


@dataclass
class DirTemplate:
    """Defines a standard user directory."""
    name: str
    description: str
    icon: str = ""
    permissions: int = 0o755


class HomeDirsManager:
    """Manages standard subdirectories in user homes."""

    XDG_USER_DIRS = [
        DirTemplate("Desktop", "Desktop items", "user-desktop"),
        DirTemplate("Documents", "Documents", "user-documents"),
        DirTemplate("Downloads", "Downloaded files", "user-download"),
        DirTemplate("Music", "Music files", "user-music"),
        DirTemplate("Pictures", "Pictures and images", "user-pictures"),
        DirTemplate("Public", "Publicly shared files", "user-publicshare"),
        DirTemplate("Templates", "File templates", "user-templates"),
        DirTemplate("Videos", "Video files", "user-videos"),
    ]

    HIDDEN_DIRS = [
        DirTemplate(".cache", "Cache data"),
        DirTemplate(".config", "Configuration files"),
        DirTemplate(".local", "Local data and binaries"),
        DirTemplate(".ssh", "SSH keys and config"),
        DirTemplate(".gnupg", "GnuPG keys"),
    ]

    def __init__(self, home_path: str = "/home"):
        self.home_path = Path(home_path)

    def setup_user_dirs(self, username: str) -> List[str]:
        """Create all standard directories for a user."""
        user_home = self.home_path / username
        created = []

        for d in self.XDG_USER_DIRS:
            path = user_home / d.name
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                path.chmod(d.permissions)
                created.append(d.name)

        for d in self.HIDDEN_DIRS:
            path = user_home / d.name
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                created.append(d.name)

        return created

    def list_user_dirs(self, username: str) -> List[Dict]:
        """List all directories in a user's home."""
        user_home = self.home_path / username
        if not user_home.exists():
            return []
        dirs = []
        for item in sorted(user_home.iterdir()):
            if item.is_dir():
                dirs.append({
                    "name": item.name,
                    "path": str(item),
                    "hidden": item.name.startswith('.'),
                })
        return dirs

    def get_xdg_dir(self, username: str, dir_name: str) -> Optional[Path]:
        """Get a specific XDG directory path."""
        user_home = self.home_path / username
        target = user_home / dir_name
        return target if target.exists() else None

    def create_xdg_defaults(self, username: str) -> Dict[str, str]:
        """Create .config/user-dirs.dirs with XDG paths."""
        user_home = self.home_path / username
        config_dir = user_home / ".config"
        config_dir.mkdir(parents=True, exist_ok=True)

        xdg_content = (
            f"XDG_DESKTOP_DIR=\"{user_home}/Desktop\"\n"
            f"XDG_DOCUMENTS_DIR=\"{user_home}/Documents\"\n"
            f"XDG_DOWNLOAD_DIR=\"{user_home}/Downloads\"\n"
            f"XDG_MUSIC_DIR=\"{user_home}/Music\"\n"
            f"XDG_PICTURES_DIR=\"{user_home}/Pictures\"\n"
            f"XDG_PUBLICSHARE_DIR=\"{user_home}/Public\"\n"
            f"XDG_TEMPLATES_DIR=\"{user_home}/Templates\"\n"
            f"XDG_VIDEOS_DIR=\"{user_home}/Videos\"\n"
        )

        dirs_file = config_dir / "user-dirs.dirs"
        dirs_file.write_text(xdg_content, encoding='utf-8')

        return {
            "XDG_DESKTOP_DIR": f"{user_home}/Desktop",
            "XDG_DOCUMENTS_DIR": f"{user_home}/Documents",
            "XDG_DOWNLOAD_DIR": f"{user_home}/Downloads",
            "XDG_MUSIC_DIR": f"{user_home}/Music",
            "XDG_PICTURES_DIR": f"{user_home}/Pictures",
            "XDG_PUBLICSHARE_DIR": f"{user_home}/Public",
            "XDG_TEMPLATES_DIR": f"{user_home}/Templates",
            "XDG_VIDEOS_DIR": f"{user_home}/Videos",
        }

    def remove_user_dirs(self, username: str, xdg_only: bool = True) -> int:
        """Remove user directories. Returns count removed."""
        user_home = self.home_path / username
        removed = 0

        if xdg_only:
            dirs_to_remove = self.XDG_USER_DIRS
        else:
            dirs_to_remove = self.XDG_USER_DIRS + self.HIDDEN_DIRS

        for d in dirs_to_remove:
            path = user_home / d.name
            if path.exists():
                shutil.rmtree(str(path))
                removed += 1

        return removed

    def get_disk_usage(self, username: str) -> Dict[str, int]:
        """Get disk usage per directory."""
        user_home = self.home_path / username
        usage = {}
        for item in user_home.iterdir():
            if item.is_dir():
                total = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                usage[item.name] = total
        return usage
