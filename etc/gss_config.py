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
UmerOS /etc GSS Configuration
================================
Manages GSS-API (Generic Security Service) configuration.

FHS 3.0 entries:
  /etc/gss/                    — GSS-API configuration
  /etc/gss/gssd.conf           — GSS daemon configuration
  /etc/gss/mech.d/             — GSS mechanism files

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger("UmerOS.Etc.GSSConfig")


class GSSConfigManager:
    """Manages /etc/gss/ configuration."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.gss_path = self.etc_path / "gss"

    def initialize(self) -> bool:
        try:
            self.gss_path.mkdir(parents=True, exist_ok=True)
            (self.gss_path / "mech.d").mkdir(parents=True, exist_ok=True)
            self._create_gssd_conf()
            self._create_mech_conf()
            log.info("Initialized /etc/gss/")
            return True
        except Exception as e:
            log.error("Failed to initialize GSS config: %s", e)
            return False

    def _create_gssd_conf(self) -> None:
        fp = self.gss_path / "gssd.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/gss/gssd.conf - GSS daemon configuration\n"
            "# UmerOS GSS Configuration\n\n"
            "[gssd]\n"
            "# Default realm for Kerberos\n"
            "default_realm = UMEROS.LOCAL\n\n"
            "# Use DNS to look up KDC addresses\n"
            "dns_lookup_kdc = true\n\n"
            "# Use DNS to look up realm\n"
            "dns_lookup_realm = false\n\n"
            "# Keytab file\n"
            "keytab_file = /etc/krb5.keytab\n\n"
            "# Ticket cache location\n"
            "ccache_file = /tmp/krb5cc_%u\n\n"
            "# Verbose logging\n"
            "verbose = false\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/gss/gssd.conf")

    def _create_mech_conf(self) -> None:
        fp = self.gss_path / "mech.d" / "krb5.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/gss/mech.d/krb5.conf - Kerberos GSS mechanism\n"
            "krb5  libgssapi_krb5.so.2  1.3.6.1.5.5.2\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/gss/mech.d/krb5.conf")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "gss_path_exists": self.gss_path.exists(),
            "gssd_conf_exists": (self.gss_path / "gssd.conf").exists(),
            "mech_files": len(list((self.gss_path / "mech.d").iterdir())) if (self.gss_path / "mech.d").exists() else 0,
        }
