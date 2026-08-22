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
Games Data Manager — Static Game Data (/usr/share/games)

FHS 3.0 Section 4.11.3: Static data files for /usr/games.

Manages:
- Static game data files (level data, graphics, sounds)
- Game score file references (/var/games)
- Game documentation
- Architecture-independent game resources
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path

# [FIX H296] Gate privileged /usr/share/games filesystem mutation behind the
# zero-trust capability bridge. Adding game-data files and removing trees are
# privileged operations that must require the `fs.admin` capability when a
# CapabilityManager is wired (fail-closed); when no manager is wired the gate
# stays permissive (warning) so existing flows keep working.
try:
    from core.capability_gate import gate, CAP_FS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    import sys
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_FS_ADMIN


class GameDataType(Enum):
    """Types of game data files."""
    LEVEL = "level"
    GRAPHICS = "graphics"
    SOUND = "sound"
    MUSIC = "music"
    TEXTURE = "texture"
    MODEL = "model"
    MAP = "map"
    FONT = "font"
    CONFIG = "config"
    DOCUMENTATION = "documentation"
    SCORE_TEMPLATE = "score_template"
    CUSTOM = "custom"


class GamesDataStatus(IntEnum):
    """Status of game data files."""
    MISSING = 0
    PRESENT = 1
    DIRECTORY = 2
    CORRUPTED = 3


@dataclass
class GamesDataEntry:
    """Represents a game data entry."""
    name: str
    path: Path
    data_type: GameDataType = GameDataType.CUSTOM
    status: GamesDataStatus = GamesDataStatus.MISSING
    file_size: int = 0
    is_directory: bool = False
    game_name: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "data_type": self.data_type.value,
            "status": self.status.value,
            "file_size": self.file_size,
            "is_directory": self.is_directory,
            "game_name": self.game_name,
            "description": self.description
        }


class GamesDataManager:
    """Manages /usr/share/games static data per FHS 3.0.

    FHS 3.0 requires:
    - Game data in /usr/share/games must be purely static
    - Modifiable files (scores, logs) go in /var/games
    """

    BASE_DIR = Path("/usr/share/games")

    # Score file directory (modifiable, in /var)
    SCORES_DIR = Path("/var/games")

    # Common game data extensions
    DATA_TYPE_MAP = {
        ".lev": GameDataType.LEVEL,
        ".level": GameDataType.LEVEL,
        ".png": GameDataType.GRAPHICS,
        ".jpg": GameDataType.GRAPHICS,
        ".gif": GameDataType.GRAPHICS,
        ".bmp": GameDataType.GRAPHICS,
        ".svg": GameDataType.GRAPHICS,
        ".wav": GameDataType.SOUND,
        ".ogg": GameDataType.SOUND,
        ".mp3": GameDataType.SOUND,
        ".flac": GameDataType.SOUND,
        ".mid": GameDataType.MUSIC,
        ".midi": GameDataType.MUSIC,
        ".mod": GameDataType.MUSIC,
        ".it": GameDataType.MUSIC,
        ".s3m": GameDataType.MUSIC,
        ".xm": GameDataType.MUSIC,
        ".ttf": GameDataType.FONT,
        ".otf": GameDataType.FONT,
        ".cfg": GameDataType.CONFIG,
        ".conf": GameDataType.CONFIG,
        ".txt": GameDataType.DOCUMENTATION,
        ".md": GameDataType.DOCUMENTATION,
        ".html": GameDataType.DOCUMENTATION,
        ".doc": GameDataType.DOCUMENTATION,
    }

    def __init__(self):
        self._entries: Dict[str, GamesDataEntry] = {}
        self._games: Dict[str, List[str]] = {}
        self._refresh()

    def _refresh(self):
        """Refresh games data cache."""
        self._entries.clear()
        self._games.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)
        self.SCORES_DIR.mkdir(parents=True, exist_ok=True)

        self._scan_directory(self.BASE_DIR)

    def _scan_directory(self, directory: Path, depth: int = 0):
        """Recursively scan for game data files."""
        if depth > 5:
            return

        try:
            for entry_path in sorted(directory.iterdir()):
                if entry_path.is_dir():
                    entry = self._create_entry(entry_path, True)
                    self._entries[entry.name] = entry
                    game = entry.game_name or entry.name
                    if game not in self._games:
                        self._games[game] = []
                    self._games[game].append(entry.name)
                    self._scan_directory(entry_path, depth + 1)
                elif entry_path.is_file() or entry_path.is_symlink():
                    entry = self._create_entry(entry_path, False)
                    self._entries[entry.name] = entry
                    game = entry.game_name or "default"
                    if game not in self._games:
                        self._games[game] = []
                    self._games[game].append(entry.name)
        except PermissionError:
            pass

    def _create_entry(self, path: Path, is_dir: bool) -> GamesDataEntry:
        """Create a GamesDataEntry for a path."""
        name = path.name
        data_type = self._detect_data_type(path)
        game_name = self._extract_game_name(path)

        status = GamesDataStatus.MISSING
        file_size = 0

        if path.exists():
            if is_dir:
                status = GamesDataStatus.DIRECTORY
            else:
                file_size = path.stat().st_size
                status = GamesDataStatus.PRESENT

        return GamesDataEntry(
            name=name,
            path=path,
            data_type=data_type,
            status=status,
            file_size=file_size,
            is_directory=is_dir,
            game_name=game_name
        )

    def _detect_data_type(self, path: Path) -> GameDataType:
        """Detect game data type from extension."""
        suffix = path.suffix.lower()
        return self.DATA_TYPE_MAP.get(suffix, GameDataType.CUSTOM)

    def _extract_game_name(self, path: Path) -> str:
        """Extract game name from path."""
        parts = path.parts
        share_idx = None
        for i, part in enumerate(parts):
            if part == "games":
                share_idx = i
                break
        if share_idx and share_idx + 1 < len(parts):
            return parts[share_idx + 1]
        return ""

    def list_entries(self) -> List[GamesDataEntry]:
        """List all game data entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[GamesDataEntry]:
        """Get a specific game data entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if a game data entry exists."""
        return name in self._entries

    def get_games(self) -> List[str]:
        """Get all game names."""
        return sorted(self._games.keys())

    def get_entries_for_game(self, game_name: str) -> List[GamesDataEntry]:
        """Get all entries for a specific game."""
        names = self._games.get(game_name, [])
        return [self._entries[n] for n in names if n in self._entries]

    def get_scores_path(self, game_name: str) -> Path:
        """Get the scores path for a game (in /var/games)."""
        return self.SCORES_DIR / game_name

    def add_game_data(self, game_name: str, filename: str,
                      content: bytes = b"") -> bool:
        """Add a new game data file."""
        # [FIX H296] privileged /usr/share/games mutation -> requires fs.admin
        # when a CapabilityManager is wired (fail-closed); permissive otherwise.
        gate.require(CAP_FS_ADMIN)
        try:
            game_dir = self.BASE_DIR / game_name
            game_dir.mkdir(parents=True, exist_ok=True)
            file_path = game_dir / filename
            with open(file_path, 'wb') as f:
                f.write(content)
            self._refresh()
            return True
        except Exception:
            return False

    def remove_game_data(self, name: str) -> bool:
        """Remove a game data entry."""
        # [FIX H296] privileged unlink/rmtree -> requires fs.admin.
        gate.require(CAP_FS_ADMIN)
        try:
            entry = self.get_entry(name)
            if entry and entry.path.exists():
                if entry.is_directory:
                    import shutil
                    shutil.rmtree(entry.path)
                else:
                    entry.path.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get games data manager status."""
        dirs = sum(1 for e in self._entries.values()
                   if e.is_directory)
        files = sum(1 for e in self._entries.values()
                    if not e.is_directory)
        total_size = sum(e.file_size for e in self._entries.values())

        return {
            "base_dir": str(self.BASE_DIR),
            "scores_dir": str(self.SCORES_DIR),
            "exists": self.BASE_DIR.exists(),
            "scores_exists": self.SCORES_DIR.exists(),
            "total_entries": len(self._entries),
            "directories": dirs,
            "files": files,
            "total_games": len(self._games),
            "total_size": total_size,
            "games": self.get_games()
        }


# Singleton instance
games_data_manager = GamesDataManager()
