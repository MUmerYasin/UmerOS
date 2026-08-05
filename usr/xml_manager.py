"""
XML Manager — XML Data (/usr/share/xml)

FHS 3.0 Section 4.11.10: Architecture-independent XML data.

Manages:
- XML catalog files
- DTD directories (docbook, xhtml, mathml)
- XML schema files
- XSLT stylesheet collections
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class XMLCategory(Enum):
    """XML data categories."""
    CATALOG = "catalog"
    DTD = "dtd"
    SCHEMA = "schema"
    XSLT = "xslt"
    XHTML = "xhtml"
    MATHML = "mathml"
    DOCBOOK = "docbook"
    CUSTOM = "custom"


class XMLStatus(IntEnum):
    """Status of XML entries."""
    MISSING = 0
    PRESENT = 1
    VALID = 2
    CORRUPTED = 3


@dataclass
class XMLEntry:
    """Represents an XML data entry."""
    name: str
    path: Path
    category: XMLCategory = XMLCategory.CUSTOM
    status: XMLStatus = XMLStatus.MISSING
    file_size: int = 0
    is_directory: bool = False
    is_symlink: bool = False
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "category": self.category.value,
            "status": self.status.value,
            "file_size": self.file_size,
            "is_directory": self.is_directory,
            "is_symlink": self.is_symlink,
            "description": self.description
        }


class XMLManager:
    """Manages /usr/share/xml data per FHS 3.0."""

    BASE_DIR = Path("/usr/share/xml")

    # FHS 3.0 required subdirectories
    REQUIRED_DIRS = ["docbook", "xhtml", "mathml"]

    # Known XML categories
    CATEGORY_MAP = {
        "docbook": XMLCategory.DOCBOOK,
        "xhtml": XMLCategory.XHTML,
        "mathml": XMLCategory.MATHML,
        "catalog": XMLCategory.CATALOG,
        "dtd": XMLCategory.DTD,
        "schema": XMLCategory.SCHEMA,
        "xslt": XMLCategory.XSLT,
    }

    def __init__(self):
        self._entries: Dict[str, XMLEntry] = {}
        self._categories: Dict[str, List[str]] = {}
        self._refresh()

    def _refresh(self):
        """Refresh XML data cache."""
        self._entries.clear()
        self._categories.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        self._scan_directory(self.BASE_DIR)

    def _scan_directory(self, directory: Path, depth: int = 0):
        """Recursively scan for XML files."""
        if depth > 5:
            return

        try:
            for entry_path in sorted(directory.iterdir()):
                if entry_path.is_dir():
                    entry = self._create_entry(entry_path, True)
                    self._entries[entry.name] = entry
                    cat = entry.category.value
                    if cat not in self._categories:
                        self._categories[cat] = []
                    self._categories[cat].append(entry.name)
                    self._scan_directory(entry_path, depth + 1)
                elif entry_path.is_file() or entry_path.is_symlink():
                    if entry_path.suffix.lower() in ('.xml', '.dtd', '.xsd', '.xsl', '.xslt', '.ent', '.cat'):
                        entry = self._create_entry(entry_path, False)
                        self._entries[entry.name] = entry
                        cat = entry.category.value
                        if cat not in self._categories:
                            self._categories[cat] = []
                        self._categories[cat].append(entry.name)
        except PermissionError:
            pass

    def _create_entry(self, path: Path, is_dir: bool) -> XMLEntry:
        """Create an XMLEntry for a path."""
        name = path.name
        category = self._detect_category(path)

        status = XMLStatus.MISSING
        file_size = 0

        if path.is_symlink():
            status = XMLStatus.PRESENT
        elif path.exists():
            if is_dir:
                status = XMLStatus.PRESENT
            else:
                file_size = path.stat().st_size
                if file_size > 0:
                    try:
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            first_line = f.readline(256)
                        if '<?xml' in first_line or '<!DOCTYPE' in first_line or '<!ELEMENT' in first_line:
                            status = XMLStatus.VALID
                        else:
                            status = XMLStatus.PRESENT
                    except Exception:
                        status = XMLStatus.CORRUPTED

        return XMLEntry(
            name=name,
            path=path,
            category=category,
            status=status,
            file_size=file_size,
            is_directory=is_dir,
            is_symlink=path.is_symlink()
        )

    def _detect_category(self, path: Path) -> XMLCategory:
        """Detect XML category from path."""
        parts = [p.lower() for p in path.parts]
        for part in parts:
            if part in self.CATEGORY_MAP:
                return self.CATEGORY_MAP[part]
        if path.suffix.lower() in ('.dtd', '.ent'):
            return XMLCategory.DTD
        if path.suffix.lower() in ('.xsd',):
            return XMLCategory.SCHEMA
        if path.suffix.lower() in ('.xsl', '.xslt'):
            return XMLCategory.XSLT
        return XMLCategory.CUSTOM

    def list_entries(self) -> List[XMLEntry]:
        """List all XML entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[XMLEntry]:
        """Get a specific XML entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if an XML entry exists."""
        return name in self._entries

    def get_categories(self) -> List[str]:
        """Get all categories."""
        return sorted(self._categories.keys())

    def get_entries_by_category(self, category: XMLCategory) -> List[XMLEntry]:
        """Get all entries in a category."""
        names = self._categories.get(category.value, [])
        return [self._entries[n] for n in names if n in self._entries]

    def add_directory(self, name: str) -> bool:
        """Add a new XML directory."""
        try:
            dir_path = self.BASE_DIR / name
            dir_path.mkdir(parents=True, exist_ok=True)
            self._refresh()
            return True
        except Exception:
            return False

    def add_file(self, name: str, content: str = "") -> bool:
        """Add a new XML file."""
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
        """Remove an XML entry."""
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
        """Get XML manager status."""
        valid = sum(1 for e in self._entries.values()
                    if e.status == XMLStatus.VALID)
        dirs = sum(1 for e in self._entries.values()
                   if e.is_directory)
        files = sum(1 for e in self._entries.values()
                    if not e.is_directory)
        total_size = sum(e.file_size for e in self._entries.values())

        return {
            "base_dir": str(self.BASE_DIR),
            "exists": self.BASE_DIR.exists(),
            "total_entries": len(self._entries),
            "directories": dirs,
            "files": files,
            "valid": valid,
            "total_size": total_size,
            "categories": self.get_categories()
        }


# Singleton instance
xml_manager = XMLManager()
