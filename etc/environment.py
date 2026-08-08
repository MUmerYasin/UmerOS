"""
UmerOS /etc Environment Configuration
========================================
Manages global environment variable configuration.

FHS 3.0 entries:
  /etc/environment      — Global environment variables
  /etc/profile          — Shell login configuration (via shell_profile)
  /etc/profile.d/       — Additional profile scripts (via shell_profile)

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("UmerOS.Etc.Environment")


class EnvironmentManager:
    """Manages /etc/environment and global environment settings."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)

    def initialize(self) -> bool:
        try:
            self._create_environment()
            log.info("Initialized /etc/environment")
            return True
        except Exception as e:
            log.error("Failed to initialize environment: %s", e)
            return False

    def _create_environment(self) -> None:
        fp = self.etc_path / "environment"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/environment - Global environment variables\n"
            "# UmerOS Environment Configuration\n"
            "# These are loaded for all users at login.\n\n"
            "PATH=\"/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin\"\n"
            "LANG=\"en_US.UTF-8\"\n"
            "LC_ALL=\"en_US.UTF-8\"\n"
            "EDITOR=\"vi\"\n"
            "PAGER=\"less\"\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/environment")

    def get_environment_vars(self) -> Dict[str, str]:
        """Parse /etc/environment into a dictionary."""
        fp = self.etc_path / "environment"
        if not fp.exists():
            return {}
        env = {}
        for line in fp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
        return env

    def get_summary(self) -> Dict[str, Any]:
        return {
            "environment_exists": (self.etc_path / "environment").exists(),
            "environment_vars": self.get_environment_vars(),
        }
