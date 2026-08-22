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
UmerOS - /etc/networks manager
FHS 3.0: /etc/networks describes known networks and their addresses.
Used by route and other networking tools.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List

NETWORKS_PATH = Path(os.environ.get("UMEROS_NETWORKS", "/etc/networks"))

DEFAULT_NETWORKS = """# /etc/networks - UmerOS network names
# Format: network-name address [flags]
loopback    127.0.0.0
localnet    192.168.0.0
"""


class NetworksManager:
    """Manages /etc/networks — network name to address mapping."""

    def __init__(self, path: str = None):
        self.path = Path(path) if path else NETWORKS_PATH

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(DEFAULT_NETWORKS, encoding="utf-8")

    def read_networks(self) -> Dict[str, str]:
        self._ensure_file()
        networks = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                networks[parts[0]] = parts[1]
        return networks

    def add_network(self, name: str, address: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"\n{name}    {address}")

    def remove_network(self, name: str) -> bool:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        new_lines = [l for l in lines if not l.strip().startswith(name + " ")]
        if len(new_lines) != len(lines):
            self.path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            return True
        return False

    def lookup(self, name: str) -> str:
        return self.read_networks().get(name, "")
