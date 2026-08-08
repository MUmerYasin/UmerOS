"""
UmerOS /etc XDG Configuration
================================
Manages XDG Base Directory configuration.

FHS 3.0 entries:
  /etc/xdg/                  — XDG Base Directory configuration
  /etc/xdg/autostart/        — Autostart applications
  /etc/xdg/menus/            — Menu definitions
  /etc/xdg/user-dirs.conf    — User directories configuration

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger("UmerOS.Etc.XDGConfig")


class XDGConfigManager:
    """Manages /etc/xdg/ configuration."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.xdg_path = self.etc_path / "xdg"

    def initialize(self) -> bool:
        try:
            (self.xdg_path / "autostart").mkdir(parents=True, exist_ok=True)
            (self.xdg_path / "menus").mkdir(parents=True, exist_ok=True)
            self._create_user_dirs_conf()
            self._create_menu_conf()
            log.info("Initialized /etc/xdg/")
            return True
        except Exception as e:
            log.error("Failed to initialize XDG config: %s", e)
            return False

    def _create_user_dirs_conf(self) -> None:
        fp = self.xdg_path / "user-dirs.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/xdg/user-dirs.conf - User directories configuration\n"
            "# UmerOS XDG Configuration\n\n"
            "# Method to use to update user directories\n"
            "enabled=True\n\n"
            "# Default directories\n"
            "DESKTOP=$HOME/Desktop\n"
            "DOWNLOAD=$HOME/Downloads\n"
            "TEMPLATES=$HOME/Templates\n"
            "PUBLICSHARE=$HOME/Public\n"
            "DOCUMENTS=$HOME/Documents\n"
            "MUSIC=$HOME/Music\n"
            "PICTURES=$HOME/Pictures\n"
            "VIDEOS=$HOME/Videos\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/xdg/user-dirs.conf")

    def _create_menu_conf(self) -> None:
        fp = self.xdg_path / "menus" / "applications.menu"
        if fp.exists():
            return
        fp.write_text(
            "<!DOCTYPE Menu PUBLIC\n"
            "  \"-//freedesktop//DTD Menu 1.0//EN\"\n"
            "  \"http://www.freedesktop.org/standards/menu-spec/menu-1.0.dtd\">\n"
            "<Menu>\n"
            "  <Name>Applications</Name>\n"
            "  <Directory>Applications.directory</Directory>\n"
            "  <Include>\n"
            "    <Category>UmerOS</Category>\n"
            "  </Include>\n"
            "  <Menu>\n"
            "    <Name>Accessories</Name>\n"
            "    <Directory>Accessories.directory</Directory>\n"
            "    <Include><Category>Utility</Category></Include>\n"
            "  </Menu>\n"
            "  <Menu>\n"
            "    <Name>System</Name>\n"
            "    <Directory>System.directory</Directory>\n"
            "    <Include><Category>System</Category></Include>\n"
            "  </Menu>\n"
            "</Menu>\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/xdg/menus/applications.menu")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "xdg_path_exists": self.xdg_path.exists(),
            "user_dirs_conf_exists": (self.xdg_path / "user-dirs.conf").exists(),
            "autostart_files": len(list((self.xdg_path / "autostart").iterdir())) if (self.xdg_path / "autostart").exists() else 0,
            "menus_files": len(list((self.xdg_path / "menus").iterdir())) if (self.xdg_path / "menus").exists() else 0,
        }
