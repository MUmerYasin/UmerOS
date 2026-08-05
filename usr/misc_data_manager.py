"""
Misc Data Manager — Miscellaneous Architecture-Independent Data (/usr/share/misc)

FHS 3.0 Section 4.11.7: Miscellaneous architecture-independent files.

Manages:
- ASCII character set table
- Terminal capability database (termcap, termcap.db)
- Other miscellaneous data files (airport, birthtoken, eqnchar, etc.)
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class MiscFileType(Enum):
    """Types of miscellaneous data files."""
    ASCII = "ascii"
    TERMCAP = "termcap"
    TERMCAP_DB = "termcap.db"
    AIRPORT = "airport"
    BIRTHTOKEN = "birthtoken"
    EQNCHAR = "eqnchar"
    GETOPT = "getopt"
    GPROF_CALLG = "gprof.callg"
    GPROF_FLAT = "gprof.flat"
    INTER_PHONE = "inter.phone"
    IPFW_SAMP_FILTERS = "ipfw.samp.filters"
    IPFW_SAMP_SCRIPTS = "ipfw.samp.scripts"
    KEYCAP_PCVT = "keycap.pcvt"
    MAIL_HELP = "mail.help"
    MAIL_TILDEHELP = "mail.tildehelp"
    MAN_TEMPLATE = "man.template"
    MAP3270 = "map3270"
    MDOC_TEMPLATE = "mdoc.template"
    MORE_HELP = "more.help"
    NA_PHONE = "na.phone"
    NSLOOKUP_HELP = "nslookup.help"
    OPERATOR = "operator"
    SCSI_MODES = "scsi_modes"
    SENDMAIL_HF = "sendmail.hf"
    STYLE = "style"
    UNITS_LIB = "units.lib"
    VGRINDEFS = "vgrindefs"
    VGRINDEFS_DB = "vgrindefs.db"
    ZIPCODES = "zipcodes"
    MAGIC = "magic"
    CUSTOM = "custom"


class MiscDataStatus(IntEnum):
    """Status of misc data files."""
    MISSING = 0
    PRESENT = 1
    SYMLINK = 2
    CORRUPTED = 3


@dataclass
class MiscDataEntry:
    """Represents a miscellaneous data file."""
    name: str
    path: Path
    file_type: MiscFileType = MiscFileType.CUSTOM
    status: MiscDataStatus = MiscDataStatus.MISSING
    file_size: int = 0
    is_symlink: bool = False
    symlink_target: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "file_type": self.file_type.value,
            "status": self.status.value,
            "file_size": self.file_size,
            "is_symlink": self.is_symlink,
            "symlink_target": self.symlink_target,
            "description": self.description
        }


class MiscDataManager:
    """Manages /usr/share/misc data per FHS 3.0."""

    BASE_DIR = Path("/usr/share/misc")

    # Known misc file types
    FILE_TYPE_MAP = {
        "ascii": MiscFileType.ASCII,
        "termcap": MiscFileType.TERMCAP,
        "termcap.db": MiscFileType.TERMCAP_DB,
        "airport": MiscFileType.AIRPORT,
        "birthtoken": MiscFileType.BIRTHTOKEN,
        "eqnchar": MiscFileType.EQNCHAR,
        "getopt": MiscFileType.GETOPT,
        "gprof.callg": MiscFileType.GPROF_CALLG,
        "gprof.flat": MiscFileType.GPROF_FLAT,
        "inter.phone": MiscFileType.INTER_PHONE,
        "ipfw.samp.filters": MiscFileType.IPFW_SAMP_FILTERS,
        "ipfw.samp.scripts": MiscFileType.IPFW_SAMP_SCRIPTS,
        "keycap.pcvt": MiscFileType.KEYCAP_PCVT,
        "mail.help": MiscFileType.MAIL_HELP,
        "mail.tildehelp": MiscFileType.MAIL_TILDEHELP,
        "man.template": MiscFileType.MAN_TEMPLATE,
        "map3270": MiscFileType.MAP3270,
        "mdoc.template": MiscFileType.MDOC_TEMPLATE,
        "more.help": MiscFileType.MORE_HELP,
        "na.phone": MiscFileType.NA_PHONE,
        "nslookup.help": MiscFileType.NSLOOKUP_HELP,
        "operator": MiscFileType.OPERATOR,
        "scsi_modes": MiscFileType.SCSI_MODES,
        "sendmail.hf": MiscFileType.SENDMAIL_HF,
        "style": MiscFileType.STYLE,
        "units.lib": MiscFileType.UNITS_LIB,
        "vgrindefs": MiscFileType.VGRINDEFS,
        "vgrindefs.db": MiscFileType.VGRINDEFS_DB,
        "zipcodes": MiscFileType.ZIPCODES,
        "magic": MiscFileType.MAGIC,
    }

    def __init__(self):
        self._entries: Dict[str, MiscDataEntry] = {}
        self._types: Dict[str, List[str]] = {}
        self._refresh()

    def _refresh(self):
        """Refresh misc data cache."""
        self._entries.clear()
        self._types.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        for entry_path in sorted(self.BASE_DIR.iterdir()):
            if entry_path.is_file() or entry_path.is_symlink():
                entry = self._create_entry(entry_path)
                self._entries[entry.name] = entry
                ft = entry.file_type.value
                if ft not in self._types:
                    self._types[ft] = []
                self._types[ft].append(entry.name)

    def _create_entry(self, path: Path) -> MiscDataEntry:
        """Create a MiscDataEntry for a path."""
        name = path.name
        file_type = self.FILE_TYPE_MAP.get(name, MiscFileType.CUSTOM)

        status = MiscDataStatus.MISSING
        file_size = 0
        is_symlink = path.is_symlink()
        symlink_target = None

        if is_symlink:
            status = MiscDataStatus.SYMLINK
            symlink_target = str(path.resolve())
        elif path.exists():
            file_size = path.stat().st_size
            if file_size >= 0:
                status = MiscDataStatus.PRESENT

        descriptions = {
            MiscFileType.ASCII: "ASCII character set table",
            MiscFileType.TERMCAP: "Terminal capability database",
            MiscFileType.TERMCAP_DB: "Compiled terminal capability database",
            MiscFileType.MAGIC: "File type identification magic numbers",
            MiscFileType.AIRPORT: "Airport codes",
            MiscFileType.ZIPCODES: "ZIP/postal codes",
            MiscFileType.OPERATOR: "Keyboard operator definitions",
        }

        return MiscDataEntry(
            name=name,
            path=path,
            file_type=file_type,
            status=status,
            file_size=file_size,
            is_symlink=is_symlink,
            symlink_target=symlink_target,
            description=descriptions.get(file_type, "")
        )

    def list_entries(self) -> List[MiscDataEntry]:
        """List all misc data entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[MiscDataEntry]:
        """Get a specific misc data entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if a misc data entry exists."""
        return name in self._entries

    def get_types(self) -> List[str]:
        """Get all file types."""
        return sorted(self._types.keys())

    def get_entries_by_type(self, file_type: MiscFileType) -> List[MiscDataEntry]:
        """Get all entries of a specific type."""
        names = self._types.get(file_type.value, [])
        return [self._entries[n] for n in names if n in self._entries]

    def add_entry(self, name: str, content: str = "") -> bool:
        """Add a new misc data file."""
        try:
            path = self.BASE_DIR / name
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self._refresh()
            return True
        except Exception:
            return False

    def remove_entry(self, name: str) -> bool:
        """Remove a misc data file."""
        try:
            entry = self.get_entry(name)
            if entry and entry.path.exists():
                entry.path.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get misc data manager status."""
        symlinks = sum(1 for e in self._entries.values()
                       if e.status == MiscDataStatus.SYMLINK)
        total_size = sum(e.file_size for e in self._entries.values())

        return {
            "base_dir": str(self.BASE_DIR),
            "exists": self.BASE_DIR.exists(),
            "total_entries": len(self._entries),
            "symlinks": symlinks,
            "total_size": total_size,
            "types": self.get_types()
        }


# Singleton instance
misc_data_manager = MiscDataManager()
