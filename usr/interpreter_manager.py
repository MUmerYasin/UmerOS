"""
Interpreter Manager — Language Interpreter Symlinks (/usr/bin)

FHS 3.0 Section 4.4: Language interpreter symlinks in /usr/bin.

Manages:
- perl interpreter symlink
- python interpreter symlink
- tclsh interpreter symlink
- wish interpreter symlink
- expect interpreter symlink
- Other scripting language interpreters
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class InterpreterType(Enum):
    """Types of language interpreters."""
    PERL = "perl"
    PYTHON = "python"
    PYTHON2 = "python2"
    PYTHON3 = "python3"
    TCLSH = "tclsh"
    WISH = "wish"
    EXPECT = "expect"
    RUBY = "ruby"
    LUA = "lua"
    PHP = "php"
    R = "r"
    JAVASCRIPT = "javascript"
    BASH = "bash"
    ZSH = "zsh"
    CUSTOM = "custom"


class InterpreterStatus(IntEnum):
    """Status of interpreter symlinks."""
    MISSING = 0
    PRESENT = 1
    VALID_SYMLINK = 2
    BROKEN_SYMLINK = 3
    NOT_SYMLINK = 4


@dataclass
class InterpreterEntry:
    """Represents a language interpreter symlink."""
    name: str
    path: Path
    interpreter_type: InterpreterType = InterpreterType.CUSTOM
    status: InterpreterStatus = InterpreterStatus.MISSING
    target_path: Optional[str] = None
    version: str = ""
    is_symlink: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "interpreter_type": self.interpreter_type.value,
            "status": self.status.value,
            "target_path": self.target_path,
            "version": self.version,
            "is_symlink": self.is_symlink
        }


class InterpreterManager:
    """Manages /usr/bin language interpreter symlinks per FHS 3.0.

    FHS 3.0 Section 4.4 requires that /usr/bin contains no subdirectories
    and provides symlinks for language interpreters like perl, python,
    tclsh, wish, and expect.
    """

    BASE_DIR = Path("/usr/bin")

    # FHS 3.0 required interpreter symlinks
    REQUIRED_INTERPRETERS = {
        "perl": InterpreterType.PERL,
        "python": InterpreterType.PYTHON,
        "python2": InterpreterType.PYTHON2,
        "python3": InterpreterType.PYTHON3,
        "tclsh": InterpreterType.TCLSH,
        "wish": InterpreterType.WISH,
        "expect": InterpreterType.EXPECT,
    }

    # Common interpreter names
    INTERPRETER_MAP = {
        "perl": InterpreterType.PERL,
        "python": InterpreterType.PYTHON,
        "python2": InterpreterType.PYTHON2,
        "python3": InterpreterType.PYTHON3,
        "python3.10": InterpreterType.PYTHON3,
        "python3.11": InterpreterType.PYTHON3,
        "python3.12": InterpreterType.PYTHON3,
        "tclsh": InterpreterType.TCLSH,
        "tclsh8.6": InterpreterType.TCLSH,
        "wish": InterpreterType.WISH,
        "wish8.6": InterpreterType.WISH,
        "expect": InterpreterType.EXPECT,
        "ruby": InterpreterType.RUBY,
        "lua": InterpreterType.LUA,
        "php": InterpreterType.PHP,
        "R": InterpreterType.R,
        "node": InterpreterType.JAVASCRIPT,
        "bash": InterpreterType.BASH,
        "zsh": InterpreterType.ZSH,
    }

    def __init__(self):
        self._entries: Dict[str, InterpreterEntry] = {}
        self._types: Dict[str, List[str]] = {}
        self._refresh()

    def _refresh(self):
        """Refresh interpreter symlink cache."""
        self._entries.clear()
        self._types.clear()

        for name, interp_type in self.INTERPRETER_MAP.items():
            path = self.BASE_DIR / name
            entry = self._create_entry(path, name, interp_type)
            self._entries[name] = entry
            type_key = interp_type.value
            if type_key not in self._types:
                self._types[type_key] = []
            self._types[type_key].append(name)

    def _create_entry(self, path: Path, name: str,
                      interp_type: InterpreterType) -> InterpreterEntry:
        """Create an InterpreterEntry for a path."""
        status = InterpreterStatus.MISSING
        target_path = None
        version = ""
        is_symlink = path.is_symlink()

        if is_symlink:
            try:
                target = os.readlink(path)
                target_path = str(Path(path).parent / target)
                if os.path.exists(target_path):
                    status = InterpreterStatus.VALID_SYMLINK
                else:
                    status = InterpreterStatus.BROKEN_SYMLINK
            except OSError:
                status = InterpreterStatus.BROKEN_SYMLINK
        elif path.exists():
            status = InterpreterStatus.NOT_SYMLINK

        version = self._extract_version(name)

        return InterpreterEntry(
            name=name,
            path=path,
            interpreter_type=interp_type,
            status=status,
            target_path=target_path,
            version=version,
            is_symlink=is_symlink
        )

    def _extract_version(self, name: str) -> str:
        """Extract version from interpreter name."""
        import re
        match = re.search(r'(\d+(?:\.\d+)*)', name)
        return match.group(1) if match else ""

    def list_entries(self) -> List[InterpreterEntry]:
        """List all interpreter entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[InterpreterEntry]:
        """Get a specific interpreter entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if an interpreter entry exists."""
        return name in self._entries

    def get_types(self) -> List[str]:
        """Get all interpreter types."""
        return sorted(self._types.keys())

    def get_entries_by_type(self, interp_type: InterpreterType) -> List[InterpreterEntry]:
        """Get all entries of a specific type."""
        names = self._types.get(interp_type.value, [])
        return [self._entries[n] for n in names if n in self._entries]

    def get_required_interpreters(self) -> List[InterpreterEntry]:
        """Get FHS 3.0 required interpreters."""
        return [self._entries[name] for name in self.REQUIRED_INTERPRETERS
                if name in self._entries]

    def add_interpreter(self, name: str, target: str,
                        interp_type: InterpreterType = InterpreterType.CUSTOM) -> bool:
        """Add a new interpreter symlink."""
        try:
            path = self.BASE_DIR / name
            if path.exists():
                return False
            os.symlink(target, path)
            self._refresh()
            return True
        except Exception:
            return False

    def remove_interpreter(self, name: str) -> bool:
        """Remove an interpreter symlink."""
        try:
            path = self.BASE_DIR / name
            if path.is_symlink():
                path.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def validate_required(self) -> Dict[str, bool]:
        """Validate all FHS 3.0 required interpreters exist."""
        results = {}
        for name in self.REQUIRED_INTERPRETERS:
            entry = self.get_entry(name)
            results[name] = entry is not None and entry.status in (
                InterpreterStatus.VALID_SYMLINK,
                InterpreterStatus.NOT_SYMLINK
            )
        return results

    def get_status(self) -> Dict[str, Any]:
        """Get interpreter manager status."""
        valid = sum(1 for e in self._entries.values()
                    if e.status == InterpreterStatus.VALID_SYMLINK)
        broken = sum(1 for e in self._entries.values()
                     if e.status == InterpreterStatus.BROKEN_SYMLINK)
        required = self.validate_required()

        return {
            "base_dir": str(self.BASE_DIR),
            "total_entries": len(self._entries),
            "valid_symlinks": valid,
            "broken_symlinks": broken,
            "required_interpreters": required,
            "types": self.get_types()
        }


# Singleton instance
interpreter_manager = InterpreterManager()
