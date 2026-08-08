"""
UmerOS Home Mail Manager
Manages user mailboxes: ~/Maildir/, /var/spool/mail/.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class MailMessage:
    """Represents a single mail message."""
    id: str
    from_addr: str
    to_addr: str
    subject: str
    body: str
    date: str = ""
    read: bool = False
    folder: str = "new"

    def __post_init__(self):
        if not self.date:
            self.date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")


class HomeMailManager:
    """Manages per-user mailboxes."""

    SPOOL_DIR = "/var/spool/mail"

    def __init__(self, home_path: str = "/home"):
        self.home_path = Path(home_path)
        self.mailboxes: Dict[str, Dict[str, List[MailMessage]]] = {}

    def setup_maildir(self, username: str) -> bool:
        """Create Maildir structure in user's home: Maildir/{new,tmp,cur}."""
        maildir = self.home_path / username / "Maildir"
        for subdir in ["new", "tmp", "cur"]:
            (maildir / subdir).mkdir(parents=True, exist_ok=True)
        self.mailboxes[username] = {"new": [], "tmp": [], "cur": []}
        return True

    def get_maildir_path(self, username: str) -> Path:
        """Get the Maildir path for a user."""
        return self.home_path / username / "Maildir"

    def deliver(self, username: str, message: MailMessage) -> bool:
        """Deliver a message to a user's Maildir/new/."""
        if username not in self.mailboxes:
            self.setup_maildir(username)
        maildir = self.get_maildir_path(username)
        msg_file = maildir / "new" / f"{message.id}"
        content = (
            f"From: {message.from_addr}\n"
            f"To: {message.to_addr}\n"
            f"Subject: {message.subject}\n"
            f"Date: {message.date}\n"
            f"\n"
            f"{message.body}\n"
        )
        msg_file.write_text(content, encoding='utf-8')
        self.mailboxes[username]["new"].append(message)
        return True

    def list_new(self, username: str) -> List[MailMessage]:
        """List unread messages."""
        return self.mailboxes.get(username, {}).get("new", [])

    def list_cur(self, username: str) -> List[MailMessage]:
        """List read messages."""
        return self.mailboxes.get(username, {}).get("cur", [])

    def mark_read(self, username: str, msg_id: str) -> bool:
        """Move a message from new/ to cur/."""
        mailbox = self.mailboxes.get(username, {})
        new_msgs = mailbox.get("new", [])
        for i, msg in enumerate(new_msgs):
            if msg.id == msg_id:
                msg.read = True
                msg.folder = "cur"
                mailbox["new"].pop(i)
                mailbox.setdefault("cur", []).append(msg)
                maildir = self.get_maildir_path(username)
                src = maildir / "new" / msg_id
                dst = maildir / "cur" / msg_id
                if src.exists():
                    src.rename(dst)
                return True
        return False

    def delete(self, username: str, msg_id: str) -> bool:
        """Delete a message."""
        mailbox = self.mailboxes.get(username, {})
        for folder in ["new", "cur"]:
            msgs = mailbox.get(folder, [])
            for i, msg in enumerate(msgs):
                if msg.id == msg_id:
                    msgs.pop(i)
                    maildir = self.get_maildir_path(username)
                    target = maildir / folder / msg_id
                    if target.exists():
                        target.unlink()
                    return True
        return False

    def get_spool_path(self, username: str) -> Path:
        """Get /var/spool/mail/<username> path."""
        return Path(self.SPOOL_DIR) / username

    def setup_spool(self, username: str) -> bool:
        """Create mail spool file."""
        spool = self.get_spool_path(username)
        spool.parent.mkdir(parents=True, exist_ok=True)
        if not spool.exists():
            spool.touch()
        return True

    def get_unread_count(self, username: str) -> int:
        """Get count of unread messages."""
        return len(self.list_new(username))

    def get_mailbox_stats(self, username: str) -> Dict:
        """Get mailbox statistics."""
        new = self.list_new(username)
        cur = self.list_cur(username)
        return {
            "username": username,
            "new_count": len(new),
            "cur_count": len(cur),
            "total": len(new) + len(cur),
            "maildir_path": str(self.get_maildir_path(username)),
            "spool_path": str(self.get_spool_path(username)),
        }
