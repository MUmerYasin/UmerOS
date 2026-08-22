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
UmerOS /etc Samba Configuration
==================================
Manages Samba file sharing configuration.

FHS 3.0 entries:
  /etc/samba/               — Samba configuration directory
  /etc/samba/smb.conf      — Samba configuration file
  /etc/samba/smb.conf.d/   — Additional Samba configurations
  /etc/samba/smbusers      — Samba username mapping
  /etc/samba/smbpasswd     — Samba password database

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.SambaConfig")


@dataclass
class SambaShare:
    """Represents a Samba share definition."""
    name: str
    path: str
    comment: str = ""
    read_only: bool = False
    guest_ok: bool = False
    browseable: bool = True
    writable: bool = True
    valid_users: str = ""
    force_user: str = ""
    create_mask: str = "0755"
    directory_mask: str = "0755"
    options: Dict[str, str] = field(default_factory=dict)


class SambaConfigManager:
    """
    Manages Samba file sharing configuration.

    Handles /etc/samba/smb.conf, /etc/samba/smb.conf.d/,
    and /etc/samba/smbusers.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.samba_path = self.etc_path / "samba"
        self.smb_conf_d_path = self.samba_path / "smb.conf.d"

    def initialize(self) -> bool:
        """Create all Samba configuration files with defaults."""
        try:
            self.samba_path.mkdir(parents=True, exist_ok=True)
            self._create_smb_conf()
            self._create_smb_conf_d()
            self._create_smbusers()
            log.info("Initialized Samba configuration files")
            return True
        except Exception as e:
            log.error("Failed to initialize Samba config: %s", e)
            return False

    # ── /etc/samba/smb.conf ──────────────────────────────────────────────

    def _create_smb_conf(self) -> None:
        """Create /etc/samba/smb.conf (Samba configuration)."""
        filepath = self.samba_path / "smb.conf"
        if filepath.exists():
            return
        content = """# /etc/samba/smb.conf - Samba configuration file
# UmerOS Samba Configuration
# See smb.conf(5) for details.

[global]
   workgroup = WORKGROUP
   server string = UmerOS Server
   server role = standalone server

   # Logging
   log file = /var/log/samba/log.%m
   max log size = 1000
   log level = 1

   # Security
   security = user
   map to guest = Bad User
   encrypt passwords = yes
   smb passwd file = /etc/samba/smbpasswd

   # Name resolution
   wins support = no
   dns proxy = no

   # Printing
   load printers = no
   printing = bsd
   printcap name = /dev/null
   disable spoolss = yes

   # Performance
   socket options = TCP_NODELAY IPTOS_LOWDELAY
   read raw = yes
   write raw = yes

   # Include additional configurations
   include = /etc/samba/smb.conf.d/*.conf

[homes]
   comment = Home Directories
   browseable = no
   read only = no
   create mask = 0700
   directory mask = 0700
   valid users = %S

[public]
   comment = Public Share
   path = /srv/samba/public
   browseable = yes
   read only = no
   guest ok = yes
   create mask = 0755
   directory mask = 0755
   force user = nobody
   force group = nogroup

[printers]
   comment = All Printers
   browseable = no
   path = /var/spool/samba
   printable = yes
   guest ok = no
   read only = yes
   create mask = 0700

[print$]
   comment = Printer Drivers
   path = /var/lib/samba/printers
   browseable = yes
   read only = yes
   guest ok = no
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/samba/smb.conf")

    # ── /etc/samba/smb.conf.d/ ───────────────────────────────────────────

    def _create_smb_conf_d(self) -> None:
        """Create /etc/samba/smb.conf.d/ directory with common configurations."""
        self.smb_conf_d_path.mkdir(parents=True, exist_ok=True)

        configs = {
            "global.conf": """# /etc/samba/smb.conf.d/global.conf
# Global Samba options

[global]
   workgroup = WORKGROUP
   server string = UmerOS Server
""",
            "homes.conf": """# /etc/samba/smb.conf.d/homes.conf
# Home directory sharing options

[homes]
   comment = Home Directories
   browseable = no
   read only = no
   create mask = 0700
   directory mask = 0700
""",
            "public.conf": """# /etc/samba/smb.conf.d/public.conf
# Public share options

[public]
   comment = Public Share
   path = /srv/samba/public
   browseable = yes
   read only = no
   guest ok = yes
""",
        }

        for filename, content in configs.items():
            filepath = self.smb_conf_d_path / filename
            if not filepath.exists():
                filepath.write_text(content, encoding="utf-8")
                log.debug("Created /etc/samba/smb.conf.d/%s", filename)

    # ── /etc/samba/smbusers ──────────────────────────────────────────────

    def _create_smbusers(self) -> None:
        """Create /etc/samba/smbusers (Samba username mapping)."""
        filepath = self.samba_path / "smbusers"
        if filepath.exists():
            return
        content = """# /etc/samba/smbusers - Samba username mapping
# UmerOS Samba Username Mapping
# Format: unix_user = smb_user1 smb_user2
#
# Example:
# root = administrator admin
# nobody = guest nobody
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/samba/smbusers")

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_smb_conf(self) -> Dict[str, Dict[str, str]]:
        """Parse /etc/samba/smb.conf into sections."""
        filepath = self.samba_path / "smb.conf"
        if not filepath.exists():
            return {}
        sections: Dict[str, Dict[str, str]] = {}
        current_section = "global"
        sections[current_section] = {}
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                sections[current_section] = {}
            elif "=" in line:
                key, value = line.split("=", 1)
                sections[current_section][key.strip()] = value.strip()
        return sections

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of Samba configuration."""
        return {
            "samba_path_exists": self.samba_path.exists(),
            "smb_conf_exists": (self.samba_path / "smb.conf").exists(),
            "smb_conf_d_exists": self.smb_conf_d_path.exists(),
            "smbusers_exists": (self.samba_path / "smbusers").exists(),
        }
