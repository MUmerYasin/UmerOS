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
UmerOS /etc User/Group Management
===================================
Manages /etc/passwd and /etc/group files.

FHS 3.0:
  /etc/passwd — User account information
  /etc/group  — Group information
  /etc/shadow — Secure user account information
  /etc/gshadow — Secure group account information

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.PasswdGroup")


@dataclass
class ShadowEntry:
    """Represents an entry in /etc/shadow."""
    username: str
    password_hash: str = "!"
    last_changed: int = 0
    min_age: int = 0
    max_age: int = 99999
    warning_period: int = 7
    inactivity_period: int = -1
    expiration_date: int = -1
    reserved: str = ""


class PasswdGroupManager:
    """
    Manages user and group account files in /etc.

    Handles /etc/passwd, /etc/group, /etc/shadow, /etc/gshadow.
    """

    # Minimum/maximum UIDs
    MIN_UID = 1000
    MAX_UID = 60000
    SYSTEM_UID_MAX = 999
    NOBODY_UID = 65534

    def __init__(self, etc_path: str = "/etc"):
        self.etc_path = Path(etc_path)
        self.passwd_path = self.etc_path / "passwd"
        self.group_path = self.etc_path / "group"
        self.shadow_path = self.etc_path / "shadow"
        self.gshadow_path = self.etc_path / "gshadow"

    # ── passwd Operations ──────────────────────────────────────────────

    def parse_passwd(self) -> List[Dict]:
        """Parse /etc/passwd and return list of user dicts."""
        if not self.passwd_path.exists():
            return []
        users = []
        for line in self.passwd_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 7:
                try:
                    uid = int(parts[2])
                    gid = int(parts[3])
                except ValueError:
                    continue
                users.append({
                    "username": parts[0],
                    "password": parts[1],
                    "uid": uid,
                    "gid": gid,
                    "gecos": parts[4],
                    "home_dir": parts[5],
                    "shell": parts[6],
                })
        return users

    def get_user(self, username: str) -> Optional[Dict]:
        """Look up a user by username."""
        for user in self.parse_passwd():
            if user["username"] == username:
                return user
        return None

    def get_user_by_uid(self, uid: int) -> Optional[Dict]:
        """Look up a user by UID."""
        for user in self.parse_passwd():
            if user["uid"] == uid:
                return user
        return None

    def add_user(
        self,
        username: str,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
        home_dir: Optional[str] = None,
        shell: str = "/bin/bash",
        gecos: str = "",
    ) -> bool:
        """Add a user to /etc/passwd."""
        users = self.parse_passwd()

        # Check for duplicate
        if any(u["username"] == username for u in users):
            log.error("User already exists: %s", username)
            return False

        # Auto-assign UID if not provided
        if uid is None:
            existing_uids = {u["uid"] for u in users}
            uid = self.MIN_UID
            while uid in existing_uids and uid <= self.MAX_UID:
                uid += 1
            if uid > self.MAX_UID:
                log.error("No available UID")
                return False

        if gid is None:
            gid = uid
        if home_dir is None:
            home_dir = f"/home/{username}"

        users.append({
            "username": username,
            "password": "x",
            "uid": uid,
            "gid": gid,
            "gecos": gecos,
            "home_dir": home_dir,
            "shell": shell,
        })

        return self._write_passwd(users)

    def delete_user(self, username: str) -> bool:
        """Remove a user from /etc/passwd."""
        users = self.parse_passwd()
        new_users = [u for u in users if u["username"] != username]
        if len(new_users) == len(users):
            log.error("User not found: %s", username)
            return False
        return self._write_passwd(new_users)

    def modify_user(self, username: str, **kwargs) -> bool:
        """Modify fields of an existing user."""
        users = self.parse_passwd()
        for user in users:
            if user["username"] == username:
                for key, value in kwargs.items():
                    if key in user:
                        user[key] = value
                return self._write_passwd(users)
        log.error("User not found: %s", username)
        return False

    def list_users(self) -> List[str]:
        """Return list of all usernames."""
        return [u["username"] for u in self.parse_passwd()]

    def _write_passwd(self, users: List[Dict]) -> bool:
        """Write user list back to /etc/passwd."""
        lines = [
            "# /etc/passwd - User account information",
            "# Format: username:password:uid:gid:gecos:home_dir:shell",
        ]
        for u in users:
            lines.append(
                f"{u['username']}:{u['password']}:{u['uid']}:{u['gid']}:"
                f"{u['gecos']}:{u['home_dir']}:{u['shell']}"
            )
        try:
            self.passwd_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            log.info("Wrote /etc/passwd with %d users", len(users))
            return True
        except Exception as e:
            log.error("Failed to write /etc/passwd: %s", e)
            return False

    # ── group Operations ───────────────────────────────────────────────

    def parse_group(self) -> List[Dict]:
        """Parse /etc/group and return list of group dicts."""
        if not self.group_path.exists():
            return []
        groups = []
        for line in self.group_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 4:
                try:
                    gid = int(parts[2])
                except ValueError:
                    gid = -1
                members = [m for m in parts[3].split(",") if m] if parts[3] else []
                groups.append({
                    "group_name": parts[0],
                    "password": parts[1],
                    "gid": gid,
                    "members": members,
                })
        return groups

    def get_group(self, group_name: str) -> Optional[Dict]:
        """Look up a group by name."""
        for g in self.parse_group():
            if g["group_name"] == group_name:
                return g
        return None

    def add_group(self, group_name: str, gid: Optional[int] = None) -> bool:
        """Add a group to /etc/group."""
        groups = self.parse_group()
        if any(g["group_name"] == group_name for g in groups):
            log.error("Group already exists: %s", group_name)
            return False

        if gid is None:
            existing_gids = {g["gid"] for g in groups}
            gid = self.MIN_UID
            while gid in existing_gids and gid <= self.MAX_UID:
                gid += 1

        groups.append({
            "group_name": group_name,
            "password": "x",
            "gid": gid,
            "members": [],
        })
        return self._write_group(groups)

    def add_user_to_group(self, username: str, group_name: str) -> bool:
        """Add a user to a group's member list."""
        groups = self.parse_group()
        for g in groups:
            if g["group_name"] == group_name:
                if username not in g["members"]:
                    g["members"].append(username)
                return self._write_group(groups)
        log.error("Group not found: %s", group_name)
        return False

    def remove_user_from_group(self, username: str, group_name: str) -> bool:
        """Remove a user from a group's member list."""
        groups = self.parse_group()
        for g in groups:
            if g["group_name"] == group_name:
                g["members"] = [m for m in g["members"] if m != username]
                return self._write_group(groups)
        return False

    def list_groups(self) -> List[str]:
        """Return list of all group names."""
        return [g["group_name"] for g in self.parse_group()]

    def get_user_groups(self, username: str) -> List[str]:
        """Return list of groups a user belongs to."""
        groups = []
        for g in self.parse_group():
            if username in g["members"]:
                groups.append(g["group_name"])
            elif g["group_name"] == username:
                groups.append(g["group_name"])
        return groups

    def _write_group(self, groups: List[Dict]) -> bool:
        """Write group list back to /etc/group."""
        lines = [
            "# /etc/group - Group information",
            "# Format: group_name:password:gid:members",
        ]
        for g in groups:
            members = ",".join(g["members"])
            lines.append(f"{g['group_name']}:{g['password']}:{g['gid']}:{members}")
        try:
            self.group_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            log.info("Wrote /etc/group with %d groups", len(groups))
            return True
        except Exception as e:
            log.error("Failed to write /etc/group: %s", e)
            return False
