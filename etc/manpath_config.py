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
