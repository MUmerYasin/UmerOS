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
Spool Manager — Spool Symlinks (/usr/spool -> /var/spool)

FHS 3.0 Section 4.3: Symlink compatibility for /usr/spool.

Manages:
- /usr/spool -> /var/spool symlink
- /usr/spool/locks -> /var/lock symlink
- /usr/tmp -> /var/tmp symlink (if not handled elsewhere)
- Spool directory validation
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class SpoolType(Enum):
    """Types of spool directories."""
    SPOOL = "spool"
    LOCKS = "locks"
    MAIL = "mail"
    LPD = "lpd"
    UUCP = "uucp"
    NEWS = "news"
    SPOOL_TMP = "tmp"
    CUSTOM = "custom"


class SpoolStatus(IntEnum):
    """Status of spool symlinks."""
    MISSING = 0
    VALID_SYMLINK = 1
    BROKEN_SYMLINK = 2
    NOT_SYMLINK = 3
    DIRECTORY_EXISTS = 4


@dataclass
class SpoolEntry:
    """Represents a spool symlink."""
    name: str
    path: Path
    target: Path
    spool_type: SpoolType = SpoolType.SPOOL
    status: SpoolStatus = SpoolStatus.MISSING
    is_symlink: bool = False
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "target": str(self.target),
            "spool_type": self.spool_type.value,
            "status": self.status.value,
            "is_symlink": self.is_symlink,
            "description": self.description
        }


class SpoolManager:
    """Manages /usr/spool symlinks per FHS 3.0.

    FHS 3.0 Section 4.3 requires:
    - /usr/spool -> /var/spool
    - /usr/spool/locks -> /var/lock
    - /usr/tmp -> /var/tmp (symlink compatibility)
    """

    # FHS 3.0 required symlinks
    REQUIRED_SYMLINKS = {
        "spool": {
            "path": Path("/usr/spool"),
            "target": Path("/var/spool"),
            "type": SpoolType.SPOOL,
            "description": "FHS 3.0 required: /usr/spool -> /var/spool"
        },
        "spool_locks": {
            "path": Path("/usr/spool/locks"),
            "target": Path("/var/lock"),
            "type": SpoolType.LOCKS,
            "description": "FHS 3.0 required: /usr/spool/locks -> /var/lock"
        },
    }

    # Optional symlinks (common on many systems)
    OPTIONAL_SYMLINKS = {
        "tmp": {
            "path": Path("/usr/tmp"),
            "target": Path("/var/tmp"),
            "type": SpoolType.SPOOL_TMP,
            "description": "Optional: /usr/tmp -> /var/tmp"
        },
    }

    def __init__(self):
        self._entries: Dict[str, SpoolEntry] = {}
        self._refresh()

    def _refresh(self):
        """Refresh spool symlink cache."""
        self._entries.clear()

        all_links = {**self.REQUIRED_SYMLINKS, **self.OPTIONAL_SYMLINKS}

        for name, config in all_links.items():
            entry = self._create_entry(name, config)
            self._entries[name] = entry

    def _create_entry(self, name: str, config: dict) -> SpoolEntry:
        """Create a SpoolEntry for a symlink."""
        path = config["path"]
        target = config["target"]
        spool_type = config["type"]
        description = config["description"]

        status = SpoolStatus.MISSING
        is_symlink = path.is_symlink()

        if is_symlink:
            try:
                actual_target = os.readlink(path)
                if os.path.exists(actual_target) or Path(actual_target).exists():
                    status = SpoolStatus.VALID_SYMLINK
                else:
                    status = SpoolStatus.BROKEN_SYMLINK
            except OSError:
                status = SpoolStatus.BROKEN_SYMLINK
        elif path.exists():
            if path.is_dir():
                status = SpoolStatus.DIRECTORY_EXISTS
            else:
                status = SpoolStatus.NOT_SYMLINK

        return SpoolEntry(
            name=name,
            path=path,
            target=target,
            spool_type=spool_type,
            status=status,
            is_symlink=is_symlink,
            description=description
        )

    def list_entries(self) -> List[SpoolEntry]:
        """List all spool entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[SpoolEntry]:
        """Get a specific spool entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if a spool entry exists."""
        return name in self._entries

    def get_required_symlinks(self) -> List[SpoolEntry]:
        """Get FHS 3.0 required symlinks."""
        return [self._entries[name] for name in self.REQUIRED_SYMLINKS
                if name in self._entries]

    def validate_required(self) -> Dict[str, bool]:
        """Validate all FHS 3.0 required symlinks."""
        results = {}
        for name in self.REQUIRED_SYMLINKS:
            entry = self.get_entry(name)
            results[name] = entry is not None and entry.status == SpoolStatus.VALID_SYMLINK
        return results

    def create_symlink(self, name: str, path: Path, target: Path) -> bool:
        """Create a new spool symlink."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() or path.is_symlink():
                return False
            os.symlink(str(target), path)
            self._refresh()
            return True
        except Exception:
            return False

    def remove_symlink(self, name: str) -> bool:
        """Remove a spool symlink."""
        try:
            entry = self.get_entry(name)
            if entry and entry.path.is_symlink():
                entry.path.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get spool manager status."""
        valid = sum(1 for e in self._entries.values()
                    if e.status == SpoolStatus.VALID_SYMLINK)
        broken = sum(1 for e in self._entries.values()
                     if e.status == SpoolStatus.BROKEN_SYMLINK)
        required = self.validate_required()

        return {
            "total_entries": len(self._entries),
            "valid_symlinks": valid,
            "broken_symlinks": broken,
            "required_valid": required,
            "all_required_valid": all(required.values()),
            "entries": {name: e.to_dict() for name, e in self._entries.items()}
        }


# Singleton instance
spool_manager = SpoolManager()
