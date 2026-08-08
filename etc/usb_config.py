#!/usr/bin/env python3
"""
UmerOS - /etc/usb manager
FHS 3.0: /etc/usb/ contains USB device configuration.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List

USB_DIR = Path(os.environ.get("UMEROS_USB", "/etc/usb"))


class USBConfigManager:
    """Manages /etc/usb/ USB device configuration."""

    def __init__(self):
        USB_DIR.mkdir(parents=True, exist_ok=True)

    def list_configs(self) -> List[str]:
        return sorted(f.name for f in USB_DIR.iterdir() if f.is_file()) if USB_DIR.exists() else []

    def read_config(self, name: str) -> str:
        p = USB_DIR / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write_config(self, name: str, content: str) -> None:
        USB_DIR.mkdir(parents=True, exist_ok=True)
        (USB_DIR / name).write_text(content, encoding="utf-8")
