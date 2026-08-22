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
PPD Manager — PostScript Printer Definitions (/usr/share/ppd)

FHS 3.0 Section 4.11.8: PPD files for print systems.

Manages:
- PPD file directories
- Printer driver definitions
- Manufacturer-specific PPD organization
- PPD file validation
"""

import os
import re
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class PPDManufacturer(Enum):
    """Known PPD manufacturers."""
    HP = "HP"
    EPSON = "Epson"
    CANON = "Canon"
    BROTHER = "Brother"
    SAMSUNG = "Samsung"
    LEXMARK = "Lexmark"
    XEROX = "Xerox"
    RICOH = "Ricoh"
    KYOCERA = "Kyocera"
    OKI = "Oki"
    DELL = "Dell"
    SHARP = "Sharp"
    KONICA_MINOLTA = "Konica Minolta"
    FUJI_XEROX = "Fuji Xerox"
    GENERIC = "Generic"
    CUSTOM = "Custom"


class PPDStatus(IntEnum):
    """Status of PPD files."""
    MISSING = 0
    PRESENT = 1
    VALID = 2
    CORRUPTED = 3


@dataclass
class PPDEntry:
    """Represents a PPD file."""
    name: str
    path: Path
    manufacturer: PPDManufacturer = PPDManufacturer.CUSTOM
    status: PPDStatus = PPDStatus.MISSING
    file_size: int = 0
    is_directory: bool = False
    is_symlink: bool = False
    printer_model: str = ""
    language_version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "manufacturer": self.manufacturer.value,
            "status": self.status.value,
            "file_size": self.file_size,
            "is_directory": self.is_directory,
            "is_symlink": self.is_symlink,
            "printer_model": self.printer_model,
            "language_version": self.language_version
        }


class PPDManager:
    """Manages /usr/share/ppd printer definitions per FHS 3.0."""

    BASE_DIR = Path("/usr/share/ppd")

    # Common manufacturers
    MANUFACTURER_MAP = {
        "hp": PPDManufacturer.HP,
        "hewlett": PPDManufacturer.HP,
        "epson": PPDManufacturer.EPSON,
        "canon": PPDManufacturer.CANON,
        "brother": PPDManufacturer.BROTHER,
        "samsung": PPDManufacturer.SAMSUNG,
        "lexmark": PPDManufacturer.LEXMARK,
        "xerox": PPDManufacturer.XEROX,
        "ricoh": PPDManufacturer.RICOH,
        "kyocera": PPDManufacturer.KYOCERA,
        "oki": PPDManufacturer.OKI,
        "dell": PPDManufacturer.DELL,
        "sharp": PPDManufacturer.SHARP,
        "konica": PPDManufacturer.KONICA_MINOLTA,
        "fuji": PPDManufacturer.FUJI_XEROX,
        "generic": PPDManufacturer.GENERIC,
    }

    def __init__(self):
        self._entries: Dict[str, PPDEntry] = {}
        self._manufacturers: Dict[str, List[str]] = {}
        self._refresh()

    def _refresh(self):
        """Refresh PPD cache."""
        self._entries.clear()
        self._manufacturers.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        self._scan_directory(self.BASE_DIR)

    def _scan_directory(self, directory: Path, prefix: str = ""):
        """Recursively scan for PPD files."""
        try:
            for entry_path in sorted(directory.iterdir()):
                if entry_path.is_dir():
                    self._scan_directory(entry_path, prefix)
                elif entry_path.is_file() or entry_path.is_symlink():
                    if entry_path.suffix.lower() in ('.ppd', '.ppd.gz', '.ppd.bz2'):
                        entry = self._create_entry(entry_path)
                        self._entries[entry.name] = entry
                        mfr = entry.manufacturer.value
                        if mfr not in self._manufacturers:
                            self._manufacturers[mfr] = []
                        self._manufacturers[mfr].append(entry.name)
        except PermissionError:
            pass

    def _create_entry(self, path: Path) -> PPDEntry:
        """Create a PPDEntry for a path."""
        name = path.name
        manufacturer = self._detect_manufacturer(path)
        status = PPDStatus.MISSING
        file_size = 0
        printer_model = ""
        language_version = ""

        if path.is_symlink():
            status = PPDStatus.PRESENT
        elif path.exists():
            file_size = path.stat().st_size
            if file_size > 0:
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(4096)
                    if '*PPD-Adobe' in content:
                        status = PPDStatus.VALID
                        printer_model = self._extract_model(content)
                        language_version = self._extract_version(content)
                    else:
                        status = PPDStatus.PRESENT
                except Exception:
                    status = PPDStatus.CORRUPTED

        return PPDEntry(
            name=name,
            path=path,
            manufacturer=manufacturer,
            status=status,
            file_size=file_size,
            is_directory=path.is_dir(),
            is_symlink=path.is_symlink(),
            printer_model=printer_model,
            language_version=language_version
        )

    def _detect_manufacturer(self, path: Path) -> PPDManufacturer:
        """Detect manufacturer from path or filename."""
        path_str = str(path).lower()
        for key, mfr in self.MANUFACTURER_MAP.items():
            if key in path_str:
                return mfr
        return PPDManufacturer.CUSTOM

    def _extract_model(self, content: str) -> str:
        """Extract printer model from PPD content."""
        match = re.search(r'\*ModelName:\s*"([^"]+)"', content)
        return match.group(1) if match else ""

    def _extract_version(self, content: str) -> str:
        """Extract language version from PPD content."""
        match = re.search(r'\*LanguageVersion:\s*"([^"]+)"', content)
        return match.group(1) if match else ""

    def list_entries(self) -> List[PPDEntry]:
        """List all PPD entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[PPDEntry]:
        """Get a specific PPD entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if a PPD entry exists."""
        return name in self._entries

    def get_manufacturers(self) -> List[str]:
        """Get all manufacturers."""
        return sorted(self._manufacturers.keys())

    def get_entries_for_manufacturer(self, manufacturer: str) -> List[PPDEntry]:
        """Get all entries for a manufacturer."""
        names = self._manufacturers.get(manufacturer, [])
        return [self._entries[n] for n in names if n in self._entries]

    def add_ppd(self, name: str, content: str = "") -> bool:
        """Add a new PPD file."""
        try:
            path = self.BASE_DIR / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self._refresh()
            return True
        except Exception:
            return False

    def remove_ppd(self, name: str) -> bool:
        """Remove a PPD file."""
        try:
            entry = self.get_entry(name)
            if entry and entry.path.exists():
                entry.path.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get PPD manager status."""
        valid = sum(1 for e in self._entries.values()
                    if e.status == PPDStatus.VALID)
        total_size = sum(e.file_size for e in self._entries.values())

        return {
            "base_dir": str(self.BASE_DIR),
            "exists": self.BASE_DIR.exists(),
            "total_entries": len(self._entries),
            "valid": valid,
            "total_size": total_size,
            "manufacturers": self.get_manufacturers(),
            "entries_by_manufacturer": {m: len(entries)
                                        for m, entries in self._manufacturers.items()}
        }


# Singleton instance
ppd_manager = PPDManager()
