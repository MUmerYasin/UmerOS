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
UmerOS - /etc/conf.d manager
FHS 3.0: /etc/conf.d/ stores configuration snippets for daemons.
Common on Gentoo. Each file is sourced by init scripts.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List

CONF_D_DIR = Path(os.environ.get("UMEROS_CONF_D", "/etc/conf.d"))

DEFAULT_FILES = {
    "hostname": "HOSTNAME=\"umerOS\"",
    "keymaps": 'KEYMAP="us"',
    "consolefont": 'FONT="lat9w-16"',
}


class ConfDManager:
    """Manages /etc/conf.d/ daemon configuration snippets."""

    def __init__(self, path: str = None):
        self.path = Path(path) if path else CONF_D_DIR

    def _ensure_dir(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        for name, content in DEFAULT_FILES.items():
            p = self.path / name
            if not p.exists():
                p.write_text(f"# /etc/conf.d/{name}\n{content}\n", encoding="utf-8")

    def list_files(self) -> List[str]:
        self._ensure_dir()
        return sorted(f.name for f in self.path.iterdir() if f.is_file())

    def read_file(self, name: str) -> str:
        p = self.path / name
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    def write_file(self, name: str, content: str) -> None:
        self._ensure_dir()
        (self.path / name).write_text(content, encoding="utf-8")

    def get_var(self, filename: str, var: str) -> str:
        content = self.read_file(filename)
        for line in content.splitlines():
            line = line.strip()
            if line.startswith(f"{var}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
        return ""
