"""
Terminfo Manager — Terminal Capability Database (/usr/share/terminfo)

FHS 3.0 Section 4.11.3: Terminal capability database.

Manages:
- terminfo database directories (by first letter)
- Terminal capability entries
- Compiled terminfo files
- Terminal type lookup
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Set
from pathlib import Path


class TerminalCategory(Enum):
    """Terminal categories."""
    UNKNOWN = "unknown"
    VT100 = "vt100"
    VT220 = "vt220"
    VT320 = "vt320"
    VT420 = "vt420"
    VT520 = "vt520"
    XTERM = "xterm"
    XTERM_COLOR = "xterm-color"
    XTERM_256COLOR = "xterm-256color"
    LINUX = "linux"
    ANSI = "ansi"
    DUMB = "dumb"
    rxvt = "rxvt"
    SCREEN = "screen"
    TMUX = "tmux"
    PUTTY = "putty"
    CONSOLE = "console"
    CUSTOM = "custom"


class TerminfoStatus(IntEnum):
    """Status of terminfo entries."""
    MISSING = 0
    PRESENT = 1
    COMPILED = 2
    CORRUPTED = 3


@dataclass
class TerminfoEntry:
    """Represents a terminfo entry."""
    name: str
    path: Path
    category: TerminalCategory = TerminalCategory.UNKNOWN
    status: TerminfoStatus = TerminfoStatus.MISSING
    file_size: int = 0
    is_compiled: bool = False
    is_directory: bool = False
    aliases: List[str] = field(default_factory=list)
    capabilities: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "category": self.category.value,
            "status": self.status.value,
            "file_size": self.file_size,
            "is_compiled": self.is_compiled,
            "is_directory": self.is_directory,
            "aliases": self.aliases,
            "capabilities": self.capabilities
        }


class TerminfoManager:
    """Manages /usr/share/terminfo database per FHS 3.0."""

    BASE_DIR = Path("/usr/share/terminfo")

    # Common terminal names
    COMMON_TERMINALS = {
        "xterm": TerminalCategory.XTERM,
        "xterm-color": TerminalCategory.XTERM_COLOR,
        "xterm-256color": TerminalCategory.XTERM_256COLOR,
        "vt100": TerminalCategory.VT100,
        "vt220": TerminalCategory.VT220,
        "vt320": TerminalCategory.VT320,
        "vt420": TerminalCategory.VT420,
        "vt520": TerminalCategory.VT520,
        "linux": TerminalCategory.LINUX,
        "ansi": TerminalCategory.ANSI,
        "dumb": TerminalCategory.DUMB,
        "rxvt": TerminalCategory.rxvt,
        "screen": TerminalCategory.SCREEN,
        "tmux": TerminalCategory.TMUX,
        "putty": TerminalCategory.PUTTY,
        "console": TerminalCategory.CONSOLE,
    }

    def __init__(self):
        self._entries: Dict[str, TerminfoEntry] = {}
        self._categories: Dict[str, Set[str]] = {}
        self._refresh()

    def _refresh(self):
        """Refresh terminfo database cache."""
        self._entries.clear()
        self._categories.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        for letter_dir in sorted(self.BASE_DIR.iterdir()):
            if letter_dir.is_dir() and len(letter_dir.name) == 1:
                self._scan_letter_directory(letter_dir)

    def _scan_letter_directory(self, letter_dir: Path):
        """Scan a letter directory for terminfo entries."""
        letter = letter_dir.name.lower()
        if letter not in self._categories:
            self._categories[letter] = set()

        for entry_path in sorted(letter_dir.iterdir()):
            if entry_path.is_file() or entry_path.is_symlink():
                entry = self._create_entry(entry_path)
                self._entries[entry.name] = entry
                self._categories[letter].add(entry.name)

    def _create_entry(self, path: Path) -> TerminfoEntry:
        """Create a TerminfoEntry for a path."""
        name = path.name
        category = self.COMMON_TERMINALS.get(name, TerminalCategory.CUSTOM)

        status = TerminfoStatus.MISSING
        is_compiled = False
        file_size = 0

        if path.is_symlink():
            status = TerminfoStatus.PRESENT
        elif path.exists():
            file_size = path.stat().st_size
            if file_size > 0:
                try:
                    with open(path, 'rb') as f:
                        magic = f.read(2)
                    if magic == b'\x1a\x01':
                        status = TerminfoStatus.COMPILED
                        is_compiled = True
                    else:
                        status = TerminfoStatus.PRESENT
                except Exception:
                    status = TerminfoStatus.CORRUPTED

        return TerminfoEntry(
            name=name,
            path=path,
            category=category,
            status=status,
            file_size=file_size,
            is_compiled=is_compiled,
            is_directory=path.is_dir()
        )

    def list_entries(self) -> List[TerminfoEntry]:
        """List all terminfo entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[TerminfoEntry]:
        """Get a specific terminfo entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if a terminfo entry exists."""
        return name in self._entries

    def get_entries_by_category(self, category: TerminalCategory) -> List[TerminfoEntry]:
        """Get all entries in a category."""
        return [e for e in self._entries.values()
                if e.category == category]

    def get_entries_by_letter(self, letter: str) -> List[TerminfoEntry]:
        """Get all entries starting with a letter."""
        names = self._categories.get(letter.lower(), set())
        return [self._entries[n] for n in names if n in self._entries]

    def get_letters(self) -> List[str]:
        """Get all letter directories."""
        return sorted(self._categories.keys())

    def add_entry(self, name: str) -> bool:
        """Add a new terminfo entry."""
        try:
            first_letter = name[0].lower() if name else '_'
            letter_dir = self.BASE_DIR / first_letter
            letter_dir.mkdir(parents=True, exist_ok=True)
            entry_path = letter_dir / name
            entry_path.touch()
            self._refresh()
            return True
        except Exception:
            return False

    def remove_entry(self, name: str) -> bool:
        """Remove a terminfo entry."""
        try:
            entry = self.get_entry(name)
            if entry and entry.path.exists():
                entry.path.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get terminfo manager status."""
        present = sum(1 for e in self._entries.values()
                      if e.status == TerminfoStatus.PRESENT)
        compiled = sum(1 for e in self._entries.values()
                       if e.status == TerminfoStatus.COMPILED)
        corrupted = sum(1 for e in self._entries.values()
                        if e.status == TerminfoStatus.CORRUPTED)
        total_size = sum(e.file_size for e in self._entries.values())

        return {
            "base_dir": str(self.BASE_DIR),
            "exists": self.BASE_DIR.exists(),
            "total_entries": len(self._entries),
            "present": present,
            "compiled": compiled,
            "corrupted": corrupted,
            "total_size": total_size,
            "letters": self.get_letters(),
            "categories": {cat: len(entries)
                           for cat, entries in self._categories.items()}
        }


# Singleton instance
terminfo_manager = TerminfoManager()
