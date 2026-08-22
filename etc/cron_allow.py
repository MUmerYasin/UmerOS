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

#!/usr/bin/env python3
"""
UmerOS - /etc/cron.allow / /etc/cron.deny manager
FHS 3.0: Controls which users can use cron. If cron.allow exists, only
listed users can use cron. If it doesn't exist, cron.deny is checked.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import List

CRON_ALLOW = Path(os.environ.get("UMEROS_CRON_ALLOW", "/etc/cron.allow"))
CRON_DENY = Path(os.environ.get("UMEROS_CRON_DENY", "/etc/cron.deny"))
AT_ALLOW = Path(os.environ.get("UMEROS_AT_ALLOW", "/etc/at.allow"))
AT_DENY = Path(os.environ.get("UMEROS_AT_DENY", "/etc/at.deny"))


class CronAccessManager:
    """Manages /etc/cron.allow, cron.deny, at.allow, at.deny."""

    def __init__(self):
        for p in [CRON_ALLOW.parent, AT_ALLOW.parent]:
            p.mkdir(parents=True, exist_ok=True)

    def _read_list(self, path: Path) -> List[str]:
        if not path.exists():
            return []
        return [
            l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]

    def _write_list(self, path: Path, users: List[str]) -> None:
        lines = [f"# {path.name} - UmerOS"]
        for u in sorted(set(users)):
            lines.append(u)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ── Cron access ────────────────────────────────────────────────────
    def cron_allow_list(self) -> List[str]:
        return self._read_list(CRON_ALLOW)

    def cron_deny_list(self) -> List[str]:
        return self._read_list(CRON_DENY)

    def cron_user_allowed(self, user: str) -> bool:
        allow = self.cron_allow_list()
        if allow:
            return user in allow
        deny = self.cron_deny_list()
        return user not in deny

    def add_cron_allow(self, user: str) -> None:
        self._write_list(CRON_ALLOW, self.cron_allow_list() + [user])

    def add_cron_deny(self, user: str) -> None:
        self._write_list(CRON_DENY, self.cron_deny_list() + [user])

    # ── at access ──────────────────────────────────────────────────────
    def at_allow_list(self) -> List[str]:
        return self._read_list(AT_ALLOW)

    def at_deny_list(self) -> List[str]:
        return self._read_list(AT_DENY)

    def at_user_allowed(self, user: str) -> bool:
        allow = self.at_allow_list()
        if allow:
            return user in allow
        deny = self.at_deny_list()
        return user not in deny
