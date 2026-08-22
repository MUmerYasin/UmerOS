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

"""
UmerOS /etc NetworkManager Configuration
==========================================
Manages NetworkManager configuration.

FHS 3.0 entries:
  /etc/NetworkManager/                — NetworkManager configuration
  /etc/NetworkManager/NetworkManager.conf — Main configuration
  /etc/NetworkManager/conf.d/         — Additional configuration
  /etc/NetworkManager/dispatcher.d/   — Dispatcher scripts
  /etc/NetworkManager/system-connections/ — System connections

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("UmerOS.Etc.NetworkManager")


class NetworkManagerConfigManager:
    """Manages /etc/NetworkManager/ configuration."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.nm_path = self.etc_path / "NetworkManager"

    def initialize(self) -> bool:
        try:
            (self.nm_path / "conf.d").mkdir(parents=True, exist_ok=True)
            (self.nm_path / "dispatcher.d").mkdir(parents=True, exist_ok=True)
            (self.nm_path / "system-connections").mkdir(parents=True, exist_ok=True)
            self._create_nm_conf()
            self._create_dispatcher_script()
            log.info("Initialized /etc/NetworkManager/")
            return True
        except Exception as e:
            log.error("Failed to initialize NetworkManager config: %s", e)
            return False

    def _create_nm_conf(self) -> None:
        fp = self.nm_path / "NetworkManager.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/NetworkManager/NetworkManager.conf\n"
            "# UmerOS NetworkManager Configuration\n\n"
            "[main]\n"
            "plugins=ifupdown,keyfile\n"
            "dns=systemd-resolved\n\n"
            "[ifupdown]\n"
            "managed=true\n\n"
            "[logging]\n"
            "level=INFO\n"
            "domains=ALL\n",
            encoding="utf-8",
        )
        log.debug("Created NetworkManager.conf")

    def _create_dispatcher_script(self) -> None:
        fp = self.nm_path / "dispatcher.d" / "99-default-wifi-powersave"
        if fp.exists():
            return
        fp.write_text(
            "#!/bin/sh\n"
            "# /etc/NetworkManager/dispatcher.d/99-default-wifi-powersave\n"
            "# Set WiFi power save mode\n\n"
            "INTERFACE=$1\n"
            "ACTION=$2\n\n"
            "case \"$ACTION\" in\n"
            "  up)\n"
            "    if echo \"$INTERFACE\" | grep -q '^wl'; then\n"
            "      iw dev \"$INTERFACE\" set power_save off 2>/dev/null || true\n"
            "    fi\n"
            "    ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        log.debug("Created dispatcher script")

    def list_connections(self) -> List[str]:
        """List system connections."""
        conns = self.nm_path / "system-connections"
        if not conns.exists():
            return []
        return [f.name for f in conns.iterdir() if f.is_file()]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "nm_path_exists": self.nm_path.exists(),
            "nm_conf_exists": (self.nm_path / "NetworkManager.conf").exists(),
            "connections": self.list_connections(),
            "dispatcher_scripts": len(list((self.nm_path / "dispatcher.d").iterdir())) if (self.nm_path / "dispatcher.d").exists() else 0,
        }
