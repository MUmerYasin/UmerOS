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
UmerOS - /etc/hotplug manager
FHS 3.0: /etc/hotplug/ contains hotplug agent configurations.
/etc/hotplug/usb/ — USB hotplug scripts
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import List

HOTPLUG_DIR = Path(os.environ.get("UMEROS_HOTPLUG", "/etc/hotplug"))
USB_DIR = HOTPLUG_DIR / "usb"


class HotplugConfigManager:
    """Manages /etc/hotplug/ hotplug agent configurations."""

    def __init__(self):
        HOTPLUG_DIR.mkdir(parents=True, exist_ok=True)
        USB_DIR.mkdir(parents=True, exist_ok=True)

    def list_usb_agents(self) -> List[str]:
        return sorted(f.name for f in USB_DIR.iterdir() if f.is_file()) if USB_DIR.exists() else []

    def read_agent(self, name: str) -> str:
        p = USB_DIR / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write_agent(self, name: str, content: str) -> None:
        USB_DIR.mkdir(parents=True, exist_ok=True)
        (USB_DIR / name).write_text(content, encoding="utf-8")
