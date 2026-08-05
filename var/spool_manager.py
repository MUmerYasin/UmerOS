"""
UmerOS /var Spool Management
==============================
Manages spool directories in /var.

FHS 3.0:
  /var/spool/     — Spool directories
  /var/spool/mail/ — User mailboxes
  /var/spool/cron/ — Cron jobs
  /var/spool/cups/ — CUPS print spool

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Var.SpoolManager")


@dataclass
class SpoolItem:
    """Represents an item in a spool directory."""
    name: str
    path: str
    size: int = 0
    created: float = 0
    modified: float = 0
    owner: str = ""


class SpoolManager:
    """
    Manages spool directories in /var.

    Handles mail, cron, and other spool directories.
    """

    def __init__(self, var_path: str = "/var"):
        self.var_path = Path(var_path)
        self.spool_path = self.var_path / "spool"
        self.mail_path = self.spool_path / "mail"
        self.cron_path = self.spool_path / "cron"
        self.cups_path = self.spool_path / "cups"

    # ── Spool Listing ──────────────────────────────────────────────────

    def list_spool_dirs(self) -> List[str]:
        """List all spool directories."""
        if not self.spool_path.exists():
            return []
        return [d.name for d in self.spool_path.iterdir() if d.is_dir()]

    def list_spool_items(self, directory: str) -> List[SpoolItem]:
        """List all items in a spool subdirectory."""
        spool_dir = self.spool_path / directory
        if not spool_dir.exists():
            return []
        items = []
        for item in spool_dir.iterdir():
            info = SpoolItem(
                name=item.name,
                path=str(item),
                size=item.stat().st_size if item.is_file() else 0,
                created=item.stat().st_ctime,
                modified=item.stat().st_mtime,
            )
            items.append(info)
        return items

    # ── Mail Spool ─────────────────────────────────────────────────────

    def list_mailboxes(self) -> List[str]:
        """List all mailboxes in /var/spool/mail."""
        return [item.name for item in self.list_spool_items("mail")]

    def read_mailbox(self, username: str) -> str:
        """Read a user's mailbox."""
        mailbox = self.mail_path / username
        if not mailbox.exists():
            return ""
        return mailbox.read_text(encoding="utf-8")

    def write_mailbox(self, username: str, message: str) -> bool:
        """Write to a user's mailbox."""
        mailbox = self.mail_path / username
        try:
            mailbox.parent.mkdir(parents=True, exist_ok=True)
            with open(mailbox, "a", encoding="utf-8") as f:
                f.write(message + "\n")
            return True
        except Exception as e:
            log.error("Failed to write mailbox: %s", e)
            return False

    def clear_mailbox(self, username: str) -> bool:
        """Clear a user's mailbox."""
        mailbox = self.mail_path / username
        if not mailbox.exists():
            return False
        try:
            mailbox.write_text("", encoding="utf-8")
            return True
        except Exception as e:
            log.error("Failed to clear mailbox: %s", e)
            return False

    # ── Cron Spool ─────────────────────────────────────────────────────

    def list_cron_jobs(self) -> List[str]:
        """List all cron jobs in /var/spool/cron."""
        return [item.name for item in self.list_spool_items("cron")]

    def get_cron_user(self, username: str) -> str:
        """Get cron jobs for a specific user."""
        cron_file = self.cron_path / username
        if not cron_file.exists():
            return ""
        return cron_file.read_text(encoding="utf-8")

    def set_cron_user(self, username: str, jobs: str) -> bool:
        """Set cron jobs for a user."""
        cron_file = self.cron_path / username
        try:
            cron_file.parent.mkdir(parents=True, exist_ok=True)
            cron_file.write_text(jobs + "\n", encoding="utf-8")
            return True
        except Exception as e:
            log.error("Failed to set cron jobs: %s", e)
            return False

    # ── Utility ────────────────────────────────────────────────────────

    def get_total_spool_size(self) -> int:
        """Get total size of all spool directories."""
        total = 0
        for spool_dir in self.spool_path.rglob("*"):
            if spool_dir.is_file():
                total += spool_dir.stat().st_size
        return total

    def cleanup_old_items(self, directory: str, max_age_days: int = 30) -> int:
        """Remove items older than max_age_days from a spool directory."""
        spool_dir = self.spool_path / directory
        if not spool_dir.exists():
            return 0
        cutoff = time.time() - (max_age_days * 86400)
        removed = 0
        for item in spool_dir.iterdir():
            if item.stat().st_mtime < cutoff:
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        import shutil
                        shutil.rmtree(item)
                    removed += 1
                except Exception as e:
                    log.error("Failed to remove %s: %s", item.name, e)
        return removed

    def get_summary(self) -> Dict:
        """Get summary of /var/spool contents."""
        return {
            "spool_directories": self.list_spool_dirs(),
            "mailboxes": self.list_mailboxes(),
            "cron_jobs": self.list_cron_jobs(),
            "total_size_bytes": self.get_total_spool_size(),
        }
