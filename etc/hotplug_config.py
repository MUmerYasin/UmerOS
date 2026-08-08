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
