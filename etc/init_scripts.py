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
UmerOS /etc Init Scripts Directory
=====================================
Manages /etc/init.d/, rc.d/ runlevel scripts, and rc.local.

FHS 3.0 entries:
  /etc/init.d/       — Init scripts (SysV/LSB)
  /etc/rc.d/         — Runlevel scripts
  /etc/rc.local      — Local startup script

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("UmerOS.Etc.InitScripts")


class InitScriptsManager:
    """Manages /etc/init.d/ and rc.d/ directories."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.init_d = self.etc_path / "init.d"
        self.rc_d = self.etc_path / "rc.d"

    def initialize(self) -> bool:
        try:
            self.init_d.mkdir(parents=True, exist_ok=True)
            self.rc_d.mkdir(parents=True, exist_ok=True)
            for level in ("rc0.d", "rc1.d", "rc2.d", "rc3.d", "rc4.d", "rc5.d", "rc6.d"):
                (self.rc_d / level).mkdir(parents=True, exist_ok=True)
            self._create_rc_local()
            self._create_sample_scripts()
            log.info("Initialized /etc/init.d/ and /etc/rc.d/")
            return True
        except Exception as e:
            log.error("Failed to initialize init scripts: %s", e)
            return False

    def _create_rc_local(self) -> None:
        fp = self.etc_path / "rc.local"
        if fp.exists():
            return
        fp.write_text(
            "#!/bin/sh\n"
            "# /etc/rc.local - Local startup script\n"
            "# UmerOS Local Startup\n"
            "# Executed after all init scripts\n\n"
            "exit 0\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/rc.local")

    def _create_sample_scripts(self) -> None:
        # Sample init script: hostname
        fp = self.init_d / "hostname"
        if not fp.exists():
            fp.write_text(
                "#!/bin/sh\n"
                "# /etc/init.d/hostname - Set system hostname\n"
                "# UmerOS Init Script\n\n"
                ". /etc/default/rcS\n\n"
                "case \"$1\" in\n"
                "  start)\n"
                "    echo \"Setting hostname...\"\n"
                "    hostname -F /etc/hostname\n"
                "    ;;\n"
                "  stop)\n"
                "    ;;\n"
                "  restart)\n"
                "    $0 stop\n"
                "    $0 start\n"
                "    ;;\n"
                "  *)\n"
                "    echo \"Usage: $0 {start|stop|restart}\"\n"
                "    exit 1\n"
                "    ;;\n"
                "esac\n\n"
                "exit 0\n",
                encoding="utf-8",
            )
            log.debug("Created /etc/init.d/hostname")

        # Sample init script: networking
        fp = self.init_d / "networking"
        if not fp.exists():
            fp.write_text(
                "#!/bin/sh\n"
                "# /etc/init.d/networking - Network configuration\n"
                "# UmerOS Init Script\n\n"
                ". /etc/default/rcS\n\n"
                "case \"$1\" in\n"
                "  start)\n"
                "    echo \"Starting networking...\"\n"
                "    if [ -f /etc/network/interfaces ]; then\n"
                "        ifup -a\n"
                "    fi\n"
                "    ;;\n"
                "  stop)\n"
                "    echo \"Stopping networking...\"\n"
                "    ifdown -a 2>/dev/null || true\n"
                "    ;;\n"
                "  restart|force-reload)\n"
                "    $0 stop\n"
                "    $0 start\n"
                "    ;;\n"
                "  *)\n"
                "    echo \"Usage: $0 {start|stop|restart}\"\n"
                "    exit 1\n"
                "    ;;\n"
                "esac\n\n"
                "exit 0\n",
                encoding="utf-8",
            )
            log.debug("Created /etc/init.d/networking")

    def list_scripts(self) -> List[str]:
        """List init scripts in /etc/init.d/."""
        if not self.init_d.exists():
            return []
        return [f.name for f in self.init_d.iterdir() if f.is_file()]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "init_d_exists": self.init_d.exists(),
            "init_d_scripts": self.list_scripts(),
            "rc_d_exists": self.rc_d.exists(),
            "rc_local_exists": (self.etc_path / "rc.local").exists(),
        }
