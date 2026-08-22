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
UmerOS /etc/gai.conf Configuration Manager
Manages getaddrinfo() address ordering.
"""

from pathlib import Path
from typing import List
from dataclasses import dataclass


@dataclass
class GAIConfig:
    """getaddrinfo() configuration."""
    precedence: List[str] = None
    scopev4: List[str] = None

    def __post_init__(self):
        if self.precedence is None:
            self.precedence = ["::ffff:0:0/96  100"]
        if self.scopev4 is None:
            self.scopev4 = []


class GAIConfManager:
    """Manages /etc/gai.conf - getaddrinfo() configuration."""

    def __init__(self, gaiconf_path: str = "/etc/gai.conf"):
        self.gaiconf_path = Path(gaiconf_path)
        self.config = GAIConfig()
        self._write_config()

    def add_precedence(self, mask: str, value: str) -> None:
        """Add an address precedence rule."""
        entry = f"{mask}  {value}"
        if entry not in self.config.precedence:
            self.config.precedence.append(entry)
            self._write_config()

    def add_scopev4(self, addr: str) -> None:
        """Add a scopev4 entry."""
        if addr not in self.config.scopev4:
            self.config.scopev4.append(addr)
            self._write_config()

    def remove_precedence(self, mask: str) -> bool:
        """Remove a precedence rule."""
        for i, p in enumerate(self.config.precedence):
            if mask in p:
                self.config.precedence.pop(i)
                self._write_config()
                return True
        return False

    def get_precedence(self) -> List[str]:
        """Get precedence rules."""
        return list(self.config.precedence)

    def _write_config(self) -> None:
        """Write gai.conf file."""
        content = "# /etc/gai.conf - getaddrinfo() configuration\n"
        content += "# Managed by UmerOS\n\n"
        for p in self.config.precedence:
            content += f"precedence {p}\n"
        for s in self.config.scopev4:
            content += f"scopev4 {s}\n"
        self.gaiconf_path.write_text(content, encoding='utf-8')
