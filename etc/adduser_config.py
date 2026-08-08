#!/usr/bin/env python3
"""
UmerOS - /etc/adduser.conf manager
FHS 3.0: /etc/adduser.conf contains configuration for the adduser and
adduser commands. Defines defaults for new user creation.
"""
from __future__ import annotations
import os, re
from pathlib import Path
from typing import Dict, List, Optional

ADDUSER_CONF = Path(os.environ.get("UMEROS_ADDUSER_CONF", "/etc/adduser.conf"))

DEFAULT_CONFIG = {
    "DSHELL": "/bin/bash",
    "DHOME": "/home",
    "DSHELLLIST": "/etc/shells",
    "FIRST_SYSTEM_UID": 100,
    "LAST_SYSTEM_UID": 999,
    "FIRST_UID": 1000,
    "LAST_UID": 59999,
    "FIRST_SYSTEM_GID": 100,
    "LAST_SYSTEM_GID": 999,
    "FIRST_GID": 1000,
    "LAST_GID": 59999,
    "USERGROUPS": "yes",
    "USERS_GID": "users",
    "DIR_MODE": "0755",
    "SETGID_HOME": "no",
    "QUOTAUSER": "",
    "SKEL_DIR": "/etc/skel",
    "SKEL_ETC_FILES": "",
}


class AdduserConfigManager:
    """Manages /etc/adduser.conf defaults for user creation."""

    def __init__(self, path: str = None):
        self.path = Path(path) if path else ADDUSER_CONF

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.write_config(DEFAULT_CONFIG)

    def read_config(self) -> Dict[str, str]:
        self._ensure_file()
        config = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^(\w+)\s*=\s*(.+)$", line)
            if m:
                config[m.group(1)] = m.group(2)
        return config

    def write_config(self, config: Dict[str, str]) -> None:
        lines = ["# /etc/adduser.conf - UmerOS adduser defaults", ""]
        for key, val in config.items():
            lines.append(f"{key} = {val}")
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def get(self, key: str, default=None) -> Optional[str]:
        return self.read_config().get(key, default)

    def set(self, key: str, value: str) -> None:
        config = self.read_config()
        config[key] = value
        self.write_config(config)

    def reset(self) -> None:
        self.write_config(DEFAULT_CONFIG)
