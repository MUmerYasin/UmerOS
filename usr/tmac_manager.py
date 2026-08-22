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
Tmac Manager — Troff Macros (/usr/share/tmac)

FHS 3.0 Section 4.11.3: Troff macros not distributed with groff.

Manages:
- troff macro packages
- tmac file lookup
- Macro package metadata
- Integration with groff system
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class TmacPackage(Enum):
    """Known troff macro packages."""
    MAN = "man"
    MS = "ms"
    ME = "me"
    MT = "mt"
    MM = "mm"
    MOM = "mom"
    TEX = "tex"
    MACRO_TMAC = "macro.tmac"
    ANDOC = "andoc"
    CHARMAP = "charmap"
    PAGES = "pages"
    CUSTOM = "custom"


class TmacStatus(IntEnum):
    """Status of tmac files."""
    MISSING = 0
    PRESENT = 1
    VALID = 2
    CORRUPTED = 3


@dataclass
class TmacEntry:
    """Represents a tmac file."""
    name: str
    path: Path
    package: TmacPackage = TmacPackage.CUSTOM
    status: TmacStatus = TmacStatus.MISSING
    file_size: int = 0
    description: str = ""
    is_groff_compat: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "package": self.package.value,
            "status": self.status.value,
            "file_size": self.file_size,
            "description": self.description,
            "is_groff_compat": self.is_groff_compat
        }


class TmacManager:
    """Manages /usr/share/tmac troff macros per FHS 3.0."""

    BASE_DIR = Path("/usr/share/tmac")

    # Known tmac packages
    PACKAGE_MAP = {
        "man": TmacPackage.MAN,
        "man.tmac": TmacPackage.MAN,
        "ms": TmacPackage.MS,
        "ms.tmac": TmacPackage.MS,
        "me": TmacPackage.ME,
        "me.tmac": TmacPackage.ME,
        "mt": TmacPackage.MT,
        "mt.tmac": TmacPackage.MT,
        "mm": TmacPackage.MM,
        "mm.tmac": TmacPackage.MM,
        "mom": TmacPackage.MOM,
        "mom.tmac": TmacPackage.MOM,
        "andoc.tmac": TmacPackage.ANDOC,
        "charmap.tmac": TmacPackage.CHARMAP,
    }

    # Groff compatibility files (should be symlinks to groff directory)
    GROFF_COMPAT = {
        "tmac.an", "tmac.andoc", "tmac.docold", "tmac.m",
        "tmac.mdoc", "tmac.mdoc.doc-common", "tmac.mdoc.doc-synopsis",
        "tmac.mdoc.doc-nroff", "tmac.p", "tmac.s", "tmac.v",
    }

    def __init__(self):
        self._entries: Dict[str, TmacEntry] = {}
        self._packages: Dict[str, List[str]] = {}
        self._refresh()

    def _refresh(self):
        """Refresh tmac cache."""
        self._entries.clear()
        self._packages.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        for entry_path in sorted(self.BASE_DIR.iterdir()):
            if entry_path.is_file() or entry_path.is_symlink():
                entry = self._create_entry(entry_path)
                self._entries[entry.name] = entry
                pkg = entry.package.value
                if pkg not in self._packages:
                    self._packages[pkg] = []
                self._packages[pkg].append(entry.name)

    def _create_entry(self, path: Path) -> TmacEntry:
        """Create a TmacEntry for a path."""
        name = path.name
        package = self._detect_package(path)
        is_groff = name in self.GROFF_COMPAT or name.startswith("tmac.")

        status = TmacStatus.MISSING
        file_size = 0

        if path.is_symlink():
            status = TmacStatus.PRESENT
        elif path.exists():
            file_size = path.stat().st_size
            if file_size > 0:
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        first_lines = f.read(512)
                    if any(kw in first_lines for kw in ['.de', '.ds', '.so', '.TH', '.SH', '.PP']):
                        status = TmacStatus.VALID
                    else:
                        status = TmacStatus.PRESENT
                except Exception:
                    status = TmacStatus.CORRUPTED

        return TmacEntry(
            name=name,
            path=path,
            package=package,
            status=status,
            file_size=file_size,
            is_groff_compat=is_groff
        )

    def _detect_package(self, path: Path) -> TmacPackage:
        """Detect tmac package from filename."""
        name = path.name.lower()
        if name in self.PACKAGE_MAP:
            return self.PACKAGE_MAP[name]
        for key, pkg in self.PACKAGE_MAP.items():
            if key in name:
                return pkg
        return TmacPackage.CUSTOM

    def list_entries(self) -> List[TmacEntry]:
        """List all tmac entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[TmacEntry]:
        """Get a specific tmac entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if a tmac entry exists."""
        return name in self._entries

    def get_packages(self) -> List[str]:
        """Get all packages."""
        return sorted(self._packages.keys())

    def get_entries_by_package(self, package: TmacPackage) -> List[TmacEntry]:
        """Get all entries for a package."""
        names = self._packages.get(package.value, [])
        return [self._entries[n] for n in names if n in self._entries]

    def add_tmac(self, name: str, content: str = "") -> bool:
        """Add a new tmac file."""
        try:
            path = self.BASE_DIR / name
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self._refresh()
            return True
        except Exception:
            return False

    def remove_tmac(self, name: str) -> bool:
        """Remove a tmac file."""
        try:
            entry = self.get_entry(name)
            if entry and entry.path.exists():
                entry.path.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get tmac manager status."""
        valid = sum(1 for e in self._entries.values()
                    if e.status == TmacStatus.VALID)
        groff_compat = sum(1 for e in self._entries.values()
                           if e.is_groff_compat)

        return {
            "base_dir": str(self.BASE_DIR),
            "exists": self.BASE_DIR.exists(),
            "total_entries": len(self._entries),
            "valid": valid,
            "groff_compat": groff_compat,
            "packages": self.get_packages()
        }


# Singleton instance
tmac_manager = TmacManager()
