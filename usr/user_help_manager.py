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
User Help Manager - /usr/share/user-help

Manages user help documentation:
- Quick reference guides
- How-to documents
- Tool-specific help files
- Accessibility help
- Troubleshooting guides
"""
from __future__ import annotations
from enum import IntEnum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import uuid
import json


class HelpCategory(IntEnum):
    """Help category types"""
    GETTING_STARTED = 0
    BASIC_TASKS = 1
    DESKTOP_ENVIRONMENT = 2
    NETWORKING = 3
    SECURITY = 4
    HARDWARE = 5
    TROUBLESHOOTING = 6
    ACCESSIBILITY = 7
    MULTIUSER = 8
    SYSTEM_ADMIN = 9


class HelpFormat(IntEnum):
    """Help file format"""
    PLAIN_TEXT = 0
    HTML = 1
    MAN_PAGE = 2
    INFO = 3
    MARKDOWN = 4


HELP_CATEGORY_DIRS = {
    HelpCategory.GETTING_STARTED: ["getting-started", "introduction", "basics"],
    HelpCategory.BASIC_TASKS: ["basic-tasks", "tasks", "common"],
    HelpCategory.DESKTOP_ENVIRONMENT: ["desktop", "gui", "x11", "display"],
    HelpCategory.NETWORKING: ["network", "internet", "web"],
    HelpCategory.SECURITY: ["security", "permissions", "auth"],
    HelpCategory.HARDWARE: ["hardware", "devices", "drivers"],
    HelpCategory.TROUBLESHOOTING: ["troubleshooting", "problems", "help"],
    HelpCategory.ACCESSIBILITY: ["accessibility", "a11y", "aids"],
    HelpCategory.MULTIUSER: ["multiuser", "users", "accounts"],
    HelpCategory.SYSTEM_ADMIN: ["admin", "root", "system"],
}

HELP_FORMAT_EXT = {
    HelpFormat.PLAIN_TEXT: ".txt",
    HelpFormat.HTML: ".html",
    HelpFormat.MAN_PAGE: ".man",
    HelpFormat.INFO: ".info",
    HelpFormat.MARKDOWN: ".md",
}


@dataclass
class HelpEntry:
    """A help document entry"""
    entry_id: str
    title: str
    category: HelpCategory
    format: HelpFormat
    file_path: str
    summary: str = ""
    keywords: List[str] = field(default_factory=list)
    related_entries: List[str] = field(default_factory=list)
    created: float = 0.0
    modified: float = 0.0
    size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "title": self.title,
            "category": self.category,
            "format": self.format,
            "file_path": self.file_path,
            "summary": self.summary,
            "keywords": self.keywords,
            "related_entries": self.related_entries,
            "created": self.created,
            "modified": self.modified,
            "size": self.size,
        }


@dataclass
class HelpSection:
    """A help section with entries"""
    section_name: str
    category: HelpCategory
    entries: Dict[str, HelpEntry] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_name": self.section_name,
            "category": self.category,
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "entry_count": len(self.entries),
        }


class UserHelpManager:
    """Manages /usr/share/user-help"""

    def __init__(self, base_path: str = "/usr/share/user-help"):
        self._base_path = Path(base_path)
        self._sections: Dict[str, HelpSection] = {}
        self._entries: Dict[str, HelpEntry] = {}
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize the manager"""
        if self._initialized:
            return True

        self._base_path.mkdir(parents=True, exist_ok=True)

        for cat in HelpCategory:
            section = HelpSection(
                section_name=cat.name.lower().replace("_", "-"),
                category=cat,
            )
            self._sections[section.section_name] = section

        self._initialized = True
        return True

    def refresh(self) -> bool:
        """Refresh from filesystem"""
        self._entries.clear()
        for section in self._sections.values():
            section.entries.clear()

        if not self._base_path.exists():
            return True

        for entry_file in self._base_path.rglob("*"):
            if entry_file.is_file():
                ext = entry_file.suffix.lower()
                fmt = HelpFormat.PLAIN_TEXT
                for f, e in HELP_FORMAT_EXT.items():
                    if ext == e:
                        fmt = f
                        break

                cat = self._categorize_file(entry_file)
                entry = HelpEntry(
                    entry_id=str(uuid.uuid4()),
                    title=entry_file.stem.replace("-", " ").replace("_", " ").title(),
                    category=cat,
                    format=fmt,
                    file_path=str(entry_file),
                    created=entry_file.stat().st_ctime if entry_file.exists() else 0,
                    modified=entry_file.stat().st_mtime if entry_file.exists() else 0,
                    size=entry_file.stat().st_size if entry_file.exists() else 0,
                )
                self._entries[entry.entry_id] = entry

                section_name = cat.name.lower().replace("_", "-")
                if section_name in self._sections:
                    self._sections[section_name].entries[entry.entry_id] = entry

        return True

    def _categorize_file(self, path: Path) -> HelpCategory:
        """Auto-categorize a help file"""
        parts = [p.lower() for p in path.parts]
        for cat, dirs in HELP_CATEGORY_DIRS.items():
            for d in dirs:
                if any(d in p for p in parts):
                    return cat
        return HelpCategory.BASIC_TASKS

    def list_sections(self) -> List[Dict[str, Any]]:
        """List all help sections"""
        return [s.to_dict() for s in self._sections.values()]

    def list_entries(self, category: Optional[HelpCategory] = None) -> List[Dict[str, Any]]:
        """List help entries, optionally filtered"""
        if category is None:
            return [e.to_dict() for e in self._entries.values()]
        return [e.to_dict() for e in self._entries.values() if e.category == category]

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Get a help entry by ID"""
        entry = self._entries.get(entry_id)
        return entry.to_dict() if entry else None

    def search_entries(self, query: str) -> List[Dict[str, Any]]:
        """Search help entries by title, summary, or keywords"""
        query_lower = query.lower()
        results = []
        for entry in self._entries.values():
            if (query_lower in entry.title.lower() or
                query_lower in entry.summary.lower() or
                any(query_lower in kw.lower() for kw in entry.keywords)):
                results.append(entry.to_dict())
        return results

    def get_path(self) -> Path:
        """Get the base path"""
        return self._base_path

    def get_stats(self) -> Dict[str, int]:
        """Get statistics"""
        cat_counts = {}
        for entry in self._entries.values():
            cat = entry.category.name
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        return {
            "total_entries": len(self._entries),
            "total_sections": len(self._sections),
            "categories": cat_counts,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize"""
        return {
            "base_path": str(self._base_path),
            "sections": {k: v.to_dict() for k, v in self._sections.items()},
            "stats": self.get_stats(),
        }


_manager: Optional[UserHelpManager] = None


def get_global_user_help_manager() -> UserHelpManager:
    global _manager
    if _manager is None:
        _manager = UserHelpManager()
    return _manager


def initialize(base_path: str = "/usr/share/user-help") -> bool:
    mgr = get_global_user_help_manager()
    mgr._base_path = Path(base_path)
    return mgr.initialize()


def refresh() -> bool:
    return get_global_user_help_manager().refresh()
