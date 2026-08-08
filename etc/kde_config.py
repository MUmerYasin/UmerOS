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
