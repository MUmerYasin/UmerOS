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
UmerOS /etc D-Bus Configuration
=================================
Manages D-Bus system bus configuration.

FHS 3.0 entries:
  /etc/dbus-1/                — D-Bus configuration
  /etc/dbus-1/system.d/      — System bus policy
  /etc/dbus-1/system.conf    — System bus configuration
  /etc/dbus-1/session.conf   — Session bus configuration
  /etc/dbus-1/session.d/     — Session bus policy
  /etc/dbus-1/interfaces.d/  — D-Bus interface definitions

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("UmerOS.Etc.DBusConfig")


class DBusConfigManager:
    """Manages /etc/dbus-1/ configuration."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.dbus_path = self.etc_path / "dbus-1"

    def initialize(self) -> bool:
        try:
            (self.dbus_path / "system.d").mkdir(parents=True, exist_ok=True)
            (self.dbus_path / "session.d").mkdir(parents=True, exist_ok=True)
            (self.dbus_path / "interfaces.d").mkdir(parents=True, exist_ok=True)
            self._create_system_conf()
            self._create_session_conf()
            self._create_default_conf()
            log.info("Initialized /etc/dbus-1/")
            return True
        except Exception as e:
            log.error("Failed to initialize dbus-1 config: %s", e)
            return False

    def _create_system_conf(self) -> None:
        fp = self.dbus_path / "system.conf"
        if fp.exists():
            return
        fp.write_text(
            "<!DOCTYPE busconfig PUBLIC\n"
            "  \"-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN\"\n"
            "  \"http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd\">\n"
            "<busconfig>\n"
            "  <type>system</type>\n"
            "  <keep_environment/></include>\n"
            "  <include if_exists=\"yes\">/etc/dbus-1/system-local.conf</include>\n"
            "  <include if_exists=\"yes\">/etc/dbus-1/system.d/*.conf</include>\n"
            "  <policy context=\"default\">\n"
            "    <allow user=\"*\"/>\n"
            "    <allow own=\"*\"/>\n"
            "  </policy>\n"
            "  <policy user=\"root\">\n"
            "    <allow send_destination=\"*\"/>\n"
            "    <allow send_interface=\"*\"/>\n"
            "  </policy>\n"
            "</busconfig>\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/dbus-1/system.conf")

    def _create_session_conf(self) -> None:
        fp = self.dbus_path / "session.conf"
        if fp.exists():
            return
        fp.write_text(
            "<!DOCTYPE busconfig PUBLIC\n"
            "  \"-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN\"\n"
            "  \"http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd\">\n"
            "<busconfig>\n"
            "  <type>session</type>\n"
            "  <include if_exists=\"yes\">/etc/dbus-1/session-local.conf</include>\n"
            "  <include if_exists=\"yes\">/etc/dbus-1/session.d/*.conf</include>\n"
            "</busconfig>\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/dbus-1/session.conf")

    def _create_default_conf(self) -> None:
        fp = self.dbus_path / "session-local.conf"
        if not fp.exists():
            fp.write_text(
                "# /etc/dbus-1/session-local.conf\n"
                "# Local session bus configuration\n",
                encoding="utf-8",
            )

        fp = self.dbus_path / "system-local.conf"
        if not fp.exists():
            fp.write_text(
                "# /etc/dbus-1/system-local.conf\n"
                "# Local system bus configuration\n",
                encoding="utf-8",
            )

    def get_summary(self) -> Dict[str, Any]:
        return {
            "dbus_path_exists": self.dbus_path.exists(),
            "system_conf_exists": (self.dbus_path / "system.conf").exists(),
            "session_conf_exists": (self.dbus_path / "session.conf").exists(),
            "system_d_files": len(list((self.dbus_path / "system.d").iterdir())) if (self.dbus_path / "system.d").exists() else 0,
            "session_d_files": len(list((self.dbus_path / "session.d").iterdir())) if (self.dbus_path / "session.d").exists() else 0,
        }
