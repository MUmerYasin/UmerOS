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
UmerOS - /etc/manpath.config manager
FHS 3.0: /etc/manpath.config configures the man-db library.
Defines manual page search paths and cat directories.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import List

MANPATH_CONFIG = Path(os.environ.get("UMEROS_MANPATH_CONFIG", "/etc/manpath.config"))

DEFAULT_CONFIG = """# /etc/manpath.config - UmerOS man-db configuration
MANDB_MAP     /usr/share/man     /usr/share/man
MANDB_MAP     /usr/local/man     /usr/local/man
MANDB_MAP     /usr/local/share/man     /usr/local/share/man
MANDB_MAP     /usr/X11R6/man     /usr/X11R6/man
"""


class ManpathConfigManager:
    """Manages /etc/manpath.config for man page search paths."""

    def __init__(self, path: str = None):
        self.path = Path(path) if path else MANPATH_CONFIG

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(DEFAULT_CONFIG, encoding="utf-8")

    def read_config(self) -> str:
        self._ensure_file()
        return self.path.read_text(encoding="utf-8")

    def get_man_paths(self) -> List[str]:
        paths = []
        for line in self.read_config().splitlines():
            line = line.strip()
            if line.startswith("MANDB_MAP"):
                parts = line.split()
                if len(parts) >= 2:
                    paths.append(parts[1])
        return paths

    def add_man_path(self, path: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"\nMANDB_MAP     {path}     {path}")
