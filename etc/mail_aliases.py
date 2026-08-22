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
UmerOS - /etc/aliases manager
FHS 3.0: /etc/aliases is a Postfix/sendmail aliases file.
Maps mail aliases to real users or other aliases.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List, Optional

ALIASES_PATH = Path(os.environ.get("UMEROS_ALIASES", "/etc/aliases"))

DEFAULT_ALIASES = {
    "postmaster": "root",
    "abuse": "root",
    "hostmaster": "root",
    "webmaster": "root",
    "www": "root",
    "nobody": "/dev/null",
    "MAILER-DAEMON": "postmaster",
}


class MailAliasesManager:
    """Manages /etc/aliases for mail routing."""

    def __init__(self, path: str = None):
        self.path = Path(path) if path else ALIASES_PATH

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.write_aliases(DEFAULT_ALIASES)

    def read_aliases(self) -> Dict[str, str]:
        self._ensure_file()
        aliases = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                aliases[key.strip()] = val.strip()
        return aliases

    def write_aliases(self, aliases: Dict[str, str]) -> None:
        lines = ["# /etc/aliases - UmerOS mail aliases", "# Format: alias: target"]
        for alias, target in sorted(aliases.items()):
            lines.append(f"{alias}: {target}")
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def add_alias(self, alias: str, target: str) -> None:
        aliases = self.read_aliases()
        aliases[alias] = target
        self.write_aliases(aliases)

    def remove_alias(self, alias: str) -> bool:
        aliases = self.read_aliases()
        if alias in aliases:
            del aliases[alias]
            self.write_aliases(aliases)
            return True
        return False

    def lookup(self, alias: str) -> Optional[str]:
        return self.read_aliases().get(alias)
