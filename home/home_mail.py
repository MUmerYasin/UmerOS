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
UmerOS Home Mail Manager
Manages user mailboxes: ~/Maildir/, /var/spool/mail/.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

# [FIX H84] Fail-closed path-traversal containment (CWE-22): every caller-supplied
# name (username / message id / subdir / filename) is validated as a single safe
# path segment -- or a contained multi-segment join -- before any home path is built.
try:
    from core.path_guard import PathTraversalError, safe_child, safe_join
except Exception:  # pragma: no cover - standalone fallback
    import os as _os
    import sys as _sys
    _proj = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _proj not in _sys.path:
        _sys.path.insert(0, _proj)
    from core.path_guard import PathTraversalError, safe_child, safe_join

# [FIX H85] Zero-trust capability gate for privileged /home mutations. When a
# CapabilityManager is wired the gate is fail-closed (PermissionError); standalone it
# is permissive-with-warning so existing tooling keeps working (H60/H66/H73/H80).
try:
    from core.capability_gate import gate, CAP_HOME_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    import os as _os
    import sys as _sys
    _proj = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _proj not in _sys.path:
        _sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_HOME_ADMIN


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

    def _user_home(self, username: str) -> Path:
        """Return the validated ``<home_path>/<username>`` path.

        [FIX H84] Fail-closed (CWE-22): ``username`` must be a single safe path
        segment -- a traversal attempt (``..``/separators/absolute) raises
        :class:`~core.path_guard.PathTraversalError` instead of touching disk.
        """
        return safe_child(self.home_path, username)

    def setup_maildir(self, username: str) -> bool:
        """Create Maildir structure in user's home: Maildir/{new,tmp,cur}."""
        maildir = safe_join(self._user_home(username), "Maildir")
        for subdir in ["new", "tmp", "cur"]:
            (maildir / subdir).mkdir(parents=True, exist_ok=True)
        self.mailboxes[username] = {"new": [], "tmp": [], "cur": []}
        return True

    def get_maildir_path(self, username: str) -> Path:
        """Get the Maildir path for a user."""
        return safe_join(self._user_home(username), "Maildir")

    def deliver(self, username: str, message: MailMessage) -> bool:
        """Deliver a message to a user's Maildir/new/."""
        gate.require(CAP_HOME_ADMIN)  # [FIX H85] privileged /home mutation
        if username not in self.mailboxes:
            self.setup_maildir(username)
        maildir = self.get_maildir_path(username)
        msg_file = safe_child(maildir / "new", message.id)
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
                src = safe_child(maildir / "new", msg_id)
                dst = safe_child(maildir / "cur", msg_id)
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
                    target = safe_child(maildir / folder, msg_id)
                    if target.exists():
                        target.unlink()
                    return True
        return False

    def get_spool_path(self, username: str) -> Path:
        """Get /var/spool/mail/<username> path."""
        return safe_child(self.SPOOL_DIR, username)

    def setup_spool(self, username: str) -> bool:
        """Create mail spool file."""
        gate.require(CAP_HOME_ADMIN)  # [FIX H85] privileged /home mutation
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
