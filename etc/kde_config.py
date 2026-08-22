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
UmerOS - /etc/kde manager
FHS 3.0: /etc/kde/ or /etc/xdg/kde/ contains KDE desktop configuration.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import List

KDE_DIR = Path(os.environ.get("UMEROS_KDE", "/etc/kde"))
XDG_KDE_DIR = Path(os.environ.get("UMEROS_XDG_KDE", "/etc/xdg/kde"))


class KDEConfigManager:
    """Manages /etc/kde/ KDE desktop configuration."""

    def __init__(self):
        KDE_DIR.mkdir(parents=True, exist_ok=True)
        XDG_KDE_DIR.mkdir(parents=True, exist_ok=True)

    def list_configs(self) -> List[str]:
        if KDE_DIR.exists():
            return sorted(f.name for f in KDE_DIR.iterdir() if f.is_file())
        return []

    def list_xdg_configs(self) -> List[str]:
        if XDG_KDE_DIR.exists():
            return sorted(f.name for f in XDG_KDE_DIR.iterdir() if f.is_file())
        return []

    def read_config(self, name: str) -> str:
        p = KDE_DIR / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write_config(self, name: str, content: str) -> None:
        KDE_DIR.mkdir(parents=True, exist_ok=True)
        (KDE_DIR / name).write_text(content, encoding="utf-8")
