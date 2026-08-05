"""
Sendmail Manager — Sendmail Symlink Management (/usr/lib/sendmail)

FHS 3.0 Section 4.6: /usr/lib/sendmail symlink.

Manages:
- /usr/lib/sendmail symlink
- /usr/sbin/sendmail symlink
- Mail transfer agent symlinks
- Postfix/Exim/other MTA symlinks
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class MTAType(Enum):
    """Mail Transfer Agent types."""
    SENDMAIL = "sendmail"
    POSTFIX = "postfix"
    EXIM = "exim"
    QMAIL = "qmail"
    SSMTP = "ssmtp"
    MSMTP = "msmtp"
    CUSTOM = "custom"


class SendmailStatus(IntEnum):
    """Status of sendmail symlinks."""
    MISSING = 0
    PRESENT = 1
    VALID_SYMLINK = 2
    BROKEN_SYMLINK = 3
    NOT_SYMLINK = 4
    FILE_EXISTS = 5


@dataclass
class SendmailEntry:
    """Represents a sendmail symlink."""
    name: str
    path: Path
    mta_type: MTAType = MTAType.SENDMAIL
    status: SendmailStatus = SendmailStatus.MISSING
    target_path: Optional[str] = None
    is_symlink: bool = False
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "mta_type": self.mta_type.value,
            "status": self.status.value,
            "target_path": self.target_path,
            "is_symlink": self.is_symlink,
            "description": self.description
        }


class SendmailManager:
    """Manages /usr/lib/sendmail symlinks per FHS 3.0.

    FHS 3.0 Section 4.6 requires /usr/lib/sendmail to be a symlink
    pointing to the actual mail transfer agent binary.
    """

    # /usr/lib/sendmail (FHS 3.0 required)
    LIB_SENDMAIL = Path("/usr/lib/sendmail")

    # /usr/sbin/sendmail (common location)
    SBIN_SENDMAIL = Path("/usr/sbin/sendmail")

    # Common MTA paths
    MTA_PATHS = {
        MTAType.SENDMAIL: ["/usr/sbin/sendmail", "/usr/lib/sendmail"],
        MTAType.POSTFIX: ["/usr/sbin/sendmail", "/usr/lib/sendmail"],
        MTAType.EXIM: ["/usr/sbin/sendmail", "/usr/lib/sendmail"],
        MTAType.QMAIL: ["/usr/sbin/sendmail", "/var/qmail/bin/sendmail"],
        MTAType.SSMTP: ["/usr/sbin/ssmtp", "/usr/lib/sendmail"],
        MTAType.MSMTP: ["/usr/bin/msmtp", "/usr/lib/sendmail"],
    }

    def __init__(self):
        self._entries: Dict[str, SendmailEntry] = {}
        self._refresh()

    def _refresh(self):
        """Refresh sendmail symlink cache."""
        self._entries.clear()

        entries = [
            ("sendmail_lib", self.LIB_SENDMAIL),
            ("sendmail_sbin", self.SBIN_SENDMAIL),
        ]

        for name, path in entries:
            entry = self._create_entry(path, name)
            self._entries[name] = entry

    def _create_entry(self, path: Path, name: str) -> SendmailEntry:
        """Create a SendmailEntry for a path."""
        mta_type = self._detect_mta(path)
        status = SendmailStatus.MISSING
        target_path = None
        is_symlink = path.is_symlink()

        if is_symlink:
            try:
                target = os.readlink(path)
                target_path = str(Path(path).parent / target)
                if os.path.exists(target_path):
                    status = SendmailStatus.VALID_SYMLINK
                else:
                    status = SendmailStatus.BROKEN_SYMLINK
            except OSError:
                status = SendmailStatus.BROKEN_SYMLINK
        elif path.exists():
            status = SendmailStatus.FILE_EXISTS

        descriptions = {
            "sendmail_lib": "FHS 3.0 required /usr/lib/sendmail symlink",
            "sendmail_sbin": "Mail transfer agent in /usr/sbin",
        }

        return SendmailEntry(
            name=name,
            path=path,
            mta_type=mta_type,
            status=status,
            target_path=target_path,
            is_symlink=is_symlink,
            description=descriptions.get(name, "")
        )

    def _detect_mta(self, path: Path) -> MTAType:
        """Detect MTA type from symlink target."""
        if not path.is_symlink():
            return MTAType.SENDMAIL
        try:
            target = os.readlink(path)
            target_lower = str(target).lower()
            if "postfix" in target_lower:
                return MTAType.POSTFIX
            if "exim" in target_lower:
                return MTAType.EXIM
            if "qmail" in target_lower:
                return MTAType.QMAIL
            if "ssmtp" in target_lower:
                return MTAType.SSMTP
            if "msmtp" in target_lower:
                return MTAType.MSMTP
            return MTAType.SENDMAIL
        except OSError:
            return MTAType.SENDMAIL

    def list_entries(self) -> List[SendmailEntry]:
        """List all sendmail entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[SendmailEntry]:
        """Get a specific sendmail entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if a sendmail entry exists."""
        return name in self._entries

    def get_lib_sendmail(self) -> Optional[SendmailEntry]:
        """Get /usr/lib/sendmail entry."""
        return self._entries.get("sendmail_lib")

    def has_lib_sendmail(self) -> bool:
        """Check if /usr/lib/sendmail exists."""
        return self.LIB_SENDMAIL.exists()

    def create_sendmail_symlink(self, target: str) -> bool:
        """Create /usr/lib/sendmail symlink."""
        try:
            if self.LIB_SENDMAIL.exists() or self.LIB_SENDMAIL.is_symlink():
                return False
            os.symlink(target, self.LIB_SENDMAIL)
            self._refresh()
            return True
        except Exception:
            return False

    def remove_sendmail_symlink(self) -> bool:
        """Remove /usr/lib/sendmail symlink."""
        try:
            if self.LIB_SENDMAIL.is_symlink():
                self.LIB_SENDMAIL.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get sendmail manager status."""
        valid = sum(1 for e in self._entries.values()
                    if e.status == SendmailStatus.VALID_SYMLINK)
        broken = sum(1 for e in self._entries.values()
                     if e.status == SendmailStatus.BROKEN_SYMLINK)

        return {
            "lib_sendmail": str(self.LIB_SENDMAIL),
            "sbin_sendmail": str(self.SBIN_SENDMAIL),
            "lib_sendmail_exists": self.LIB_SENDMAIL.exists(),
            "lib_sendmail_is_symlink": self.LIB_SENDMAIL.is_symlink(),
            "sbin_sendmail_exists": self.SBIN_SENDMAIL.exists(),
            "sbin_sendmail_is_symlink": self.SBIN_SENDMAIL.is_symlink(),
            "total_entries": len(self._entries),
            "valid_symlinks": valid,
            "broken_symlinks": broken,
            "entries": {name: e.to_dict() for name, e in self._entries.items()}
        }


# Singleton instance
sendmail_manager = SendmailManager()
