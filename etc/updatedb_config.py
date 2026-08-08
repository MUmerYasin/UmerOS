#!/usr/bin/env python3
"""
UmerOS - /etc/updatedb.conf manager
FHS 3.0: /etc/updatedb.conf configures the locate database builder.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict

UPDATEDB_CONF = Path(os.environ.get("UMEROS_UPDATEDB", "/etc/updatedb.conf"))

DEFAULT_CONFIG = """# /etc/updatedb.conf - UmerOS locate database config
PRUNEFS="NFS nfs nfs4 fuse.sshfs fuse.sshd"
PRUNENAMES=".git .svn"
PRUNEPATHS="/tmp /var/tmp /home/.cache"
"""


class UpdatedbConfigManager:
    """Manages /etc/updatedb.conf for locate database."""

    def __init__(self, path: str = None):
        self.path = Path(path) if path else UPDATEDB_CONF

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(DEFAULT_CONFIG, encoding="utf-8")

    def read_config(self) -> Dict[str, str]:
        self._ensure_file()
        config = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                config[key.strip()] = val.strip()
        return config

    def get(self, key: str) -> str:
        return self.read_config().get(key, "")
