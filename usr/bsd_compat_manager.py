"""
BSD Compat Manager — BSD Compatibility Includes (/usr/include/bsd)

FHS 3.0 Section 4.11.3 (via /usr/include): BSD compatibility header files.

Manages:
- BSD compatibility header files
- BSD-specific function declarations
- BSD library linkage
- System compatibility layer
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class BSDCompatType(Enum):
    """Types of BSD compatibility headers."""
    HEADER = "header"
    INLINE = "inline"
    MACRO = "macro"
    TYPEDEF = "typedef"
    FUNCTION = "function"
    CUSTOM = "custom"


class BSDStatus(IntEnum):
    """Status of BSD compatibility files."""
    MISSING = 0
    PRESENT = 1
    VALID = 2
    CORRUPTED = 3


@dataclass
class BSDCompatEntry:
    """Represents a BSD compatibility header."""
    name: str
    path: Path
    compat_type: BSDCompatType = BSDCompatType.HEADER
    status: BSDStatus = BSDStatus.MISSING
    file_size: int = 0
    description: str = ""
    defines: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "compat_type": self.compat_type.value,
            "status": self.status.value,
            "file_size": self.file_size,
            "description": self.description,
            "defines": self.defines,
            "functions": self.functions
        }


class BSDCompatManager:
    """Manages /usr/include/bsd compatibility headers per FHS 3.0."""

    BASE_DIR = Path("/usr/include/bsd")

    # Common BSD compatibility headers
    COMMON_HEADERS = {
        "sys": "System headers (sys/socket.h, etc.)",
        "netinet": "Network headers (netinet/in.h, etc.)",
        "arpa": "ARPA headers (arpa/inet.h, etc.)",
        "netdb": "Network database headers",
        "err.h": "Error handling functions",
        "sysexits.h": "System exit codes",
        "readpassphrase.h": "Secure password reading",
        "bsd": "Main BSD compatibility header",
        "stringlist.h": "String list manipulation",
        "queue.h": "Data structure macros",
        "tree.h": "Tree data structures",
        "imsg.h": "Inter-process messaging",
        "libutil.h": "BSD utility library",
        "login_cap.h": "Login capability database",
        "vis.h": "String visualization",
        "stdlib.h": "BSD extensions to stdlib",
        "string.h": "BSD extensions to string",
        "unistd.h": "BSD extensions to unistd",
        "stdio.h": "BSD extensions to stdio",
        "syslog.h": "BSD syslog extensions",
    }

    def __init__(self):
        self._entries: Dict[str, BSDCompatEntry] = {}
        self._headers: Dict[str, BSDCompatEntry] = {}
        self._refresh()

    def _refresh(self):
        """Refresh BSD compatibility cache."""
        self._entries.clear()
        self._headers.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        self._scan_directory(self.BASE_DIR)

    def _scan_directory(self, directory: Path, depth: int = 0):
        """Recursively scan for BSD compatibility headers."""
        if depth > 5:
            return

        try:
            for entry_path in sorted(directory.iterdir()):
                if entry_path.is_dir():
                    entry = self._create_entry(entry_path, True)
                    self._entries[entry.name] = entry
                    self._scan_directory(entry_path, depth + 1)
                elif entry_path.is_file() or entry_path.is_symlink():
                    if entry_path.suffix.lower() in ('.h', '.hxx', '.hpp'):
                        entry = self._create_entry(entry_path, False)
                        self._entries[entry.name] = entry
                        self._headers[entry.name] = entry
        except PermissionError:
            pass

    def _create_entry(self, path: Path, is_dir: bool) -> BSDCompatEntry:
        """Create a BSDCompatEntry for a path."""
        name = path.name
        compat_type = self._detect_type(path)
        description = self.COMMON_HEADERS.get(name, "")

        status = BSDStatus.MISSING
        file_size = 0
        defines = []
        functions = []

        if path.is_symlink():
            status = BSDStatus.PRESENT
        elif path.exists():
            if is_dir:
                status = BSDStatus.PRESENT
            else:
                file_size = path.stat().st_size
                if file_size > 0:
                    try:
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(8192)
                        defines = self._extract_defines(content)
                        functions = self._extract_functions(content)
                        if defines or functions or '#include' in content or '#define' in content:
                            status = BSDStatus.VALID
                        else:
                            status = BSDStatus.PRESENT
                    except Exception:
                        status = BSDStatus.CORRUPTED

        return BSDCompatEntry(
            name=name,
            path=path,
            compat_type=compat_type,
            status=status,
            file_size=file_size,
            description=description,
            defines=defines,
            functions=functions
        )

    def _detect_type(self, path: Path) -> BSDCompatType:
        """Detect BSD compat type."""
        if path.is_dir():
            return BSDCompatType.HEADER
        suffix = path.suffix.lower()
        if suffix == '.h':
            return BSDCompatType.HEADER
        return BSDCompatType.CUSTOM

    def _extract_defines(self, content: str) -> List[str]:
        """Extract #define names from header content."""
        import re
        defines = re.findall(r'#define\s+(\w+)', content)
        return defines[:20]

    def _extract_functions(self, content: str) -> List[str]:
        """Extract function declarations from header content."""
        import re
        funcs = re.findall(r'(\w+)\s*\([^)]*\)\s*;', content)
        return [f for f in funcs if not f.startswith('_')][:20]

    def list_entries(self) -> List[BSDCompatEntry]:
        """List all BSD compatibility entries."""
        return list(self._entries.values())

    def list_headers(self) -> List[BSDCompatEntry]:
        """List only header files."""
        return list(self._headers.values())

    def get_entry(self, name: str) -> Optional[BSDCompatEntry]:
        """Get a specific BSD compatibility entry."""
        return self._entries.get(name)

    def get_header(self, name: str) -> Optional[BSDCompatEntry]:
        """Get a specific header file."""
        return self._headers.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if a BSD compatibility entry exists."""
        return name in self._entries

    def has_header(self, name: str) -> bool:
        """Check if a header file exists."""
        return name in self._headers

    def add_header(self, name: str, content: str = "") -> bool:
        """Add a new BSD compatibility header."""
        try:
            path = self.BASE_DIR / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self._refresh()
            return True
        except Exception:
            return False

    def remove_entry(self, name: str) -> bool:
        """Remove a BSD compatibility entry."""
        try:
            entry = self.get_entry(name)
            if entry and entry.path.exists():
                if entry.path.is_dir():
                    import shutil
                    shutil.rmtree(entry.path)
                else:
                    entry.path.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get BSD compatibility manager status."""
        valid = sum(1 for e in self._entries.values()
                    if e.status == BSDStatus.VALID)
        total_defines = sum(len(e.defines) for e in self._entries.values())
        total_functions = sum(len(e.functions) for e in self._entries.values())

        return {
            "base_dir": str(self.BASE_DIR),
            "exists": self.BASE_DIR.exists(),
            "total_entries": len(self._entries),
            "total_headers": len(self._headers),
            "valid": valid,
            "total_defines": total_defines,
            "total_functions": total_functions
        }


# Singleton instance
bsd_compat_manager = BSDCompatManager()
