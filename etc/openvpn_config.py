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
UmerOS /etc OpenVPN Configuration
====================================
Manages OpenVPN client/server configuration.

FHS 3.0 entries:
  /etc/openvpn/               — OpenVPN configuration directory
  /etc/openvpn/server/        — Server configurations
  /etc/openvpn/client/        — Client configurations

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("UmerOS.Etc.OpenVPNConfig")


class OpenVPNConfigManager:
    """Manages /etc/openvpn/ configuration."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.openvpn_path = self.etc_path / "openvpn"

    def initialize(self) -> bool:
        try:
            (self.openvpn_path / "server").mkdir(parents=True, exist_ok=True)
            (self.openvpn_path / "client").mkdir(parents=True, exist_ok=True)
            (self.openvpn_path / "ccd").mkdir(parents=True, exist_ok=True)
            self._create_example_server_conf()
            self._create_example_client_conf()
            log.info("Initialized /etc/openvpn/")
            return True
        except Exception as e:
            log.error("Failed to initialize OpenVPN config: %s", e)
            return False

    def _create_example_server_conf(self) -> None:
        fp = self.openvpn_path / "server" / "example.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/openvpn/server/example.conf - OpenVPN server example\n"
            "# UmerOS OpenVPN Server Configuration\n"
            "# Copy this file to server.conf and modify as needed.\n\n"
            "port 1194\n"
            "proto udp\n"
            "dev tun\n\n"
            "# Certificate and key files\n"
            "ca ca.crt\n"
            "cert server.crt\n"
            "key server.key\n"
            "dh dh2048.pem\n\n"
            "# Network configuration\n"
            "server 10.8.0.0 255.255.255.0\n"
            "push \"route 192.168.1.0 255.255.255.0\"\n"
            "push \"dhcp-option DNS 8.8.8.8\"\n"
            "push \"dhcp-option DNS 8.8.4.4\"\n\n"
            "# Security\n"
            "cipher AES-256-GCM\n"
            "auth SHA256\n"
            "tls-auth ta.key 0\n\n"
            "# Logging\n"
            "status /var/log/openvpn-status.log\n"
            "log /var/log/openvpn.log\n"
            "verb 3\n\n"
            "# Keepalive\n"
            "keepalive 10 120\n\n"
            "# User and group\n"
            "user nobody\n"
            "group nogroup\n\n"
            "# Persistence\n"
            "persist-key\n"
            "persist-tun\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/openvpn/server/example.conf")

    def _create_example_client_conf(self) -> None:
        fp = self.openvpn_path / "client" / "example.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/openvpn/client/example.conf - OpenVPN client example\n"
            "# UmerOS OpenVPN Client Configuration\n"
            "# Copy this file to client.conf and modify as needed.\n\n"
            "client\n"
            "dev tun\n"
            "proto udp\n\n"
            "# Server address\n"
            "remote your-server.com 1194\n\n"
            "# Certificate and key files\n"
            "ca ca.crt\n"
            "cert client.crt\n"
            "key client.key\n\n"
            "# Security\n"
            "cipher AES-256-GCM\n"
            "auth SHA256\n"
            "tls-auth ta.key 1\n\n"
            "# Logging\n"
            "verb 3\n\n"
            "# Keepalive\n"
            "keepalive 10 120\n\n"
            "# User and group\n"
            "user nobody\n"
            "group nogroup\n\n"
            "# Persistence\n"
            "persist-key\n"
            "persist-tun\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/openvpn/client/example.conf")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "openvpn_path_exists": self.openvpn_path.exists(),
            "server_configs": self._count_configs("server"),
            "client_configs": self._count_configs("client"),
            "ccd_files": len(list((self.openvpn_path / "ccd").iterdir())) if (self.openvpn_path / "ccd").exists() else 0,
        }

    def _count_configs(self, subdir: str) -> int:
        d = self.openvpn_path / subdir
        if not d.exists():
            return 0
        return len([f for f in d.iterdir() if f.suffix == ".conf"])
