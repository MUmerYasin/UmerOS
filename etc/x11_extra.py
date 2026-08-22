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
UmerOS - /etc/X11 extended manager
FHS 3.0: /etc/X11/ additional subdirectories.
  /etc/X11/Xresources/ — X client resources
  /etc/X11/Xsessions.d/ — session startup scripts
  /etc/X11/xorg.conf.d/ — X server configuration directory
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import List

X11_DIR = Path(os.environ.get("UMEROS_X11", "/etc/X11"))
XRESOURCES_DIR = X11_DIR / "Xresources"
XSESSIONS_D_DIR = X11_DIR / "Xsessions.d"
XORG_CONF_D_DIR = X11_DIR / "xorg.conf.d"


class X11ExtraManager:
    """Manages /etc/X11 extended subdirectories."""

    def __init__(self):
        XRESOURCES_DIR.mkdir(parents=True, exist_ok=True)
        XSESSIONS_D_DIR.mkdir(parents=True, exist_ok=True)
        XORG_CONF_D_DIR.mkdir(parents=True, exist_ok=True)

    def list_xresources(self) -> List[str]:
        return sorted(f.name for f in XRESOURCES_DIR.iterdir() if f.is_file()) if XRESOURCES_DIR.exists() else []

    def list_xsessions(self) -> List[str]:
        return sorted(f.name for f in XSESSIONS_D_DIR.iterdir() if f.is_file()) if XSESSIONS_D_DIR.exists() else []

    def list_xorg_conf_d(self) -> List[str]:
        return sorted(f.name for f in XORG_CONF_D_DIR.iterdir() if f.is_file()) if XORG_CONF_D_DIR.exists() else []

    def read_xresource(self, name: str) -> str:
        p = XRESOURCES_DIR / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write_xresource(self, name: str, content: str) -> None:
        (XRESOURCES_DIR / name).write_text(content, encoding="utf-8")

    def read_xsession(self, name: str) -> str:
        p = XSESSIONS_D_DIR / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write_xsession(self, name: str, content: str) -> None:
        (XSESSIONS_D_DIR / name).write_text(content, encoding="utf-8")

    def read_xorg_conf_d(self, name: str) -> str:
        p = XORG_CONF_D_DIR / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write_xorg_conf_d(self, name: str, content: str) -> None:
        (XORG_CONF_D_DIR / name).write_text(content, encoding="utf-8")
