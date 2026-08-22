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
UmerOS /etc WPA Supplicant Configuration
===========================================
Manages WPA supplicant for WiFi authentication.

FHS 3.0 entries:
  /etc/wpa_supplicant/            — WPA supplicant configuration
  /etc/wpa_supplicant/wpa_supplicant.conf — Main configuration

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger("UmerOS.Etc.WPASupplicant")


class WPASupplicantManager:
    """Manages /etc/wpa_supplicant/ configuration."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.wpa_path = self.etc_path / "wpa_supplicant"

    def initialize(self) -> bool:
        try:
            self.wpa_path.mkdir(parents=True, exist_ok=True)
            self._create_wpa_supplicant_conf()
            log.info("Initialized /etc/wpa_supplicant/")
            return True
        except Exception as e:
            log.error("Failed to initialize wpa_supplicant: %s", e)
            return False

    def _create_wpa_supplicant_conf(self) -> None:
        fp = self.wpa_path / "wpa_supplicant.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/wpa_supplicant/wpa_supplicant.conf\n"
            "# UmerOS WPA Supplicant Configuration\n"
            "# See wpa_supplicant.conf(5) for details.\n\n"
            "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n"
            "update_config=1\n\n"
            "country=US\n\n"
            "# Uncomment for WiFi networks\n"
            "# network={\n"
            "#     ssid=\"MyNetwork\"\n"
            "#     psk=\"MyPassword\"\n"
            "#     key_mgmt=WPA-PSK\n"
            "# }\n\n"
            "# Open network (no password)\n"
            "# network={\n"
            "#     ssid=\"OpenNetwork\"\n"
            "#     key_mgmt=NONE\n"
            "# }\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/wpa_supplicant/wpa_supplicant.conf")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "wpa_path_exists": self.wpa_path.exists(),
            "wpa_supplicant_conf_exists": (self.wpa_path / "wpa_supplicant.conf").exists(),
        }
