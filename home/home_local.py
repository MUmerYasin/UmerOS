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
UmerOS ~/.local/ Hierarchy Manager
Manages ~/.local/share, ~/.local/bin, ~/.local/lib, ~/.local/state.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import shutil


@dataclass
class LocalEntry:
    """An entry in ~/.local/."""
    name: str
    path: Path
    is_dir: bool = True
    size: int = 0


class HomeLocalManager:
    """Manages ~/.local/ hierarchy per FHS."""

    SUBDIRS = {
        "share": "Architecture-independent data (icons, docs, etc.)",
        "bin": "User-specific executables",
        "lib": "User-specific libraries",
        "lib64": "User-specific 64-bit libraries",
        "state": "User-specific mutable state (logs, history, etc.)",
        "games": "User-specific game data",
    }

    def __init__(self, home_path: str = "/home"):
        self.home_path = Path(home_path)

    def setup_local(self, username: str) -> List[str]:
        """Create ~/.local/ hierarchy for a user."""
        user_home = self.home_path / username
        local_dir = user_home / ".local"
        created = []

        for subdir, desc in self.SUBDIRS.items():
            path = local_dir / subdir
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                created.append(subdir)

        return created

    def get_local_path(self, username: str, subdir: str = "") -> Path:
        """Get ~/.local/ or ~/.local/<subdir>/ path."""
        user_home = self.home_path / username
        if subdir:
            return user_home / ".local" / subdir
        return user_home / ".local"

    def list_local(self, username: str) -> List[Dict]:
        """List contents of ~/.local/."""
        local_dir = self.get_local_path(username)
        if not local_dir.exists():
            return []
        entries = []
        for item in sorted(local_dir.iterdir()):
            entries.append({
                "name": item.name,
                "path": str(item),
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0,
            })
        return entries

    def install_binary(self, username: str, src_path: str,
                       name: str = "") -> Optional[str]:
        """Install a binary to ~/.local/bin/."""
        src = Path(src_path)
        if not src.exists():
            return None
        bin_dir = self.get_local_path(username, "bin")
        bin_dir.mkdir(parents=True, exist_ok=True)
        dest = bin_dir / (name or src.name)
        shutil.copy2(str(src), str(dest))
        dest.chmod(0o755)
        return str(dest)

    def install_data(self, username: str, src_path: str,
                     subdir: str = "share") -> Optional[str]:
        """Install data to ~/.local/<subdir>/."""
        src = Path(src_path)
        if not src.exists():
            return None
        data_dir = self.get_local_path(username, subdir)
        data_dir.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            dest = data_dir / src.name
            shutil.copytree(str(src), str(dest), dirs_exist_ok=True)
        else:
            dest = data_dir / src.name
            shutil.copy2(str(src), str(dest))
        return str(dest)

    def get_disk_usage(self, username: str) -> Dict[str, int]:
        """Get disk usage per subdirectory in ~/.local/."""
        local_dir = self.get_local_path(username)
        usage = {}
        for item in local_dir.iterdir():
            if item.is_dir():
                total = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                usage[item.name] = total
        return usage

    def remove_local(self, username: str, subdir: str) -> bool:
        """Remove a ~/.local/<subdir>/ directory."""
        target = self.get_local_path(username, subdir)
        if target.exists() and target.is_dir():
            shutil.rmtree(str(target))
            return True
        return False
