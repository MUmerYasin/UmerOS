"""
DConf Configuration Manager - /usr/share/dconf

Manages DConf system database:
- DConf profile definitions
- System database locks
- Default settings
- Mandatory settings
"""
from __future__ import annotations
from enum import IntEnum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Any
import uuid


class DConfEntryType(IntEnum):
    """DConf entry type"""
    PROFILE = 0
    DATABASE = 1
    LOCK = 2
    DEFAULT = 3
    MANDATORY = 4


@dataclass
class DConfEntry:
    """A DConf configuration entry"""
    entry_id: str
    name: str
    entry_type: DConfEntryType
    path: str
    content: str = ""
    db_path: str = ""
    locks: List[str] = field(default_factory=list)
    is_system: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "name": self.name,
            "entry_type": self.entry_type,
            "path": self.path,
            "content": self.content,
            "db_path": self.db_path,
            "locks": self.locks,
            "is_system": self.is_system,
        }


DCONF_PATH = "/usr/share/dconf"
DCONF_DB_PATH = "/usr/share/dconf/db"
DCONF_PROFILE_PATH = "/usr/share/dconf/profile"


class DConfManager:
    """Manages /usr/share/dconf"""

    def __init__(self):
        self._entries: Dict[str, DConfEntry] = {}
        self._profiles: Dict[str, DConfEntry] = {}
        self._databases: Dict[str, DConfEntry] = {}
        self._locks: Dict[str, DConfEntry] = {}
        self._dconf_path = Path(DCONF_PATH)
        self._db_path = Path(DCONF_DB_PATH)
        self._profile_path = Path(DCONF_PROFILE_PATH)
        self._initialized = False

    def initialize(self) -> bool:
        if self._initialized:
            return True
        self._dconf_path.mkdir(parents=True, exist_ok=True)
        self._db_path.mkdir(parents=True, exist_ok=True)
        self._profile_path.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        return True

    def refresh(self) -> bool:
        self._entries.clear()
        self._profiles.clear()
        self._databases.clear()
        self._locks.clear()

        self._scan_profiles()
        self._scan_databases()
        self._scan_locks()

        return True

    def _scan_profiles(self):
        """Scan /usr/share/dconf/profile"""
        if not self._profile_path.exists():
            return

        for profile_file in self._profile_path.iterdir():
            if profile_file.is_file():
                try:
                    content = profile_file.read_text(encoding="utf-8")
                    entry = DConfEntry(
                        entry_id=str(uuid.uuid4()),
                        name=profile_file.name,
                        entry_type=DConfEntryType.PROFILE,
                        path=str(profile_file),
                        content=content,
                        is_system=True,
                    )
                    self._entries[entry.entry_id] = entry
                    self._profiles[entry.entry_id] = entry
                except Exception:
                    continue

    def _scan_databases(self):
        """Scan /usr/share/dconf/db"""
        if not self._db_path.exists():
            return

        for db_dir in self._db_path.iterdir():
            if db_dir.is_dir():
                for db_file in db_dir.rglob("*"):
                    if db_file.is_file():
                        try:
                            content = db_file.read_text(encoding="utf-8")
                            entry = DConfEntry(
                                entry_id=str(uuid.uuid4()),
                                name=f"{db_dir.name}/{db_file.relative_to(db_dir)}",
                                entry_type=DConfEntryType.DATABASE,
                                path=str(db_file),
                                content=content,
                                db_path=str(db_dir),
                                is_system=True,
                            )
                            self._entries[entry.entry_id] = entry
                            self._databases[entry.entry_id] = entry
                        except Exception:
                            continue

    def _scan_locks(self):
        """Scan for lock files"""
        if not self._db_path.exists():
            return

        for lock_file in self._db_path.rglob("*.lock"):
            entry = DConfEntry(
                entry_id=str(uuid.uuid4()),
                name=lock_file.stem,
                entry_type=DConfEntryType.LOCK,
                path=str(lock_file),
                is_system=True,
            )
            self._entries[entry.entry_id] = entry
            self._locks[entry.entry_id] = entry

    def create_profile(self, name: str, content: str) -> Optional[Dict[str, Any]]:
        """Create a new DConf profile"""
        profile_path = self._profile_path / name
        try:
            profile_path.write_text(content, encoding="utf-8")
            entry = DConfEntry(
                entry_id=str(uuid.uuid4()),
                name=name,
                entry_type=DConfEntryType.PROFILE,
                path=str(profile_path),
                content=content,
                is_system=True,
            )
            self._entries[entry.entry_id] = entry
            self._profiles[entry.entry_id] = entry
            return entry.to_dict()
        except Exception:
            return None

    def list_profiles(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._profiles.values()]

    def list_databases(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._databases.values()]

    def list_locks(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._locks.values()]

    def list_all(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries.values()]

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        entry = self._entries.get(entry_id)
        return entry.to_dict() if entry else None

    def search_entries(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        return [
            e.to_dict() for e in self._entries.values()
            if query_lower in e.name.lower() or query_lower in e.content.lower()
        ]

    def get_path(self) -> Path:
        return self._dconf_path

    def get_db_path(self) -> Path:
        return self._db_path

    def get_profile_path(self) -> Path:
        return self._profile_path

    def get_stats(self) -> Dict[str, int]:
        type_counts = {}
        for entry in self._entries.values():
            t = entry.entry_type.name
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_entries": len(self._entries),
            "profiles": len(self._profiles),
            "databases": len(self._databases),
            "locks": len(self._locks),
            "by_type": type_counts,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dconf_path": str(self._dconf_path),
            "db_path": str(self._db_path),
            "profile_path": str(self._profile_path),
            "stats": self.get_stats(),
        }


_manager: Optional[DConfManager] = None


def get_global_dconf_manager() -> DConfManager:
    global _manager
    if _manager is None:
        _manager = DConfManager()
    return _manager


def initialize() -> bool:
    return get_global_dconf_manager().initialize()


def refresh() -> bool:
    return get_global_dconf_manager().refresh()
