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
UmerOS /etc Cron Jobs Directory
=================================
Manages /etc/cron.d/, cron.daily/, cron.hourly/, cron.monthly/, cron.weekly/.

FHS 3.0 entries:
  /etc/cron.d/        — System cron jobs
  /etc/cron.daily/    — Daily cron jobs
  /etc/cron.hourly/   — Hourly cron jobs
  /etc/cron.monthly/  — Monthly cron jobs
  /etc/cron.weekly/   — Weekly cron jobs

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("UmerOS.Etc.CronD")


class CronDManager:
    """Manages /etc/cron.d/ and periodic cron directories."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.cron_dirs = {
            "cron.d": self.etc_path / "cron.d",
            "cron.daily": self.etc_path / "cron.daily",
            "cron.hourly": self.etc_path / "cron.hourly",
            "cron.monthly": self.etc_path / "cron.monthly",
            "cron.weekly": self.etc_path / "cron.weekly",
        }

    def initialize(self) -> bool:
        try:
            for name, path in self.cron_dirs.items():
                path.mkdir(parents=True, exist_ok=True)
            self._create_default_jobs()
            log.info("Initialized cron.d directories")
            return True
        except Exception as e:
            log.error("Failed to initialize cron.d: %s", e)
            return False

    def _create_default_jobs(self) -> None:
        # /etc/cron.d/logrotate
        fp = self.cron_dirs["cron.d"] / "logrotate"
        if not fp.exists():
            fp.write_text(
                "# /etc/cron.d/logrotate\n"
                "# Run logrotate daily\n"
                "0 3 * * * root /usr/sbin/logrotate /etc/logrotate.conf\n",
                encoding="utf-8",
            )
            log.debug("Created /etc/cron.d/logrotate")

        # /etc/cron.d/tmpwatch
        fp = self.cron_dirs["cron.d"] / "tmpwatch"
        if not fp.exists():
            fp.write_text(
                "# /etc/cron.d/tmpwatch\n"
                "# Clean temporary files older than 10 days\n"
                "0 3 * * * root /usr/sbin/tmpwatch 240 /tmp\n",
                encoding="utf-8",
            )
            log.debug("Created /etc/cron.d/tmpwatch")

        # /etc/cron.d/sysstat
        fp = self.cron_dirs["cron.d"] / "sysstat"
        if not fp.exists():
            fp.write_text(
                "# /etc/cron.d/sysstat\n"
                "# Collect system statistics\n"
                "0 * * * * root /usr/lib/sysstat/sa1 1 1\n"
                "53 23 * * * root /usr/lib/sysstat/sa2 -A\n",
                encoding="utf-8",
            )
            log.debug("Created /etc/cron.d/sysstat")

    def list_cron_d(self) -> List[str]:
        """List jobs in /etc/cron.d/."""
        d = self.cron_dirs["cron.d"]
        if not d.exists():
            return []
        return [f.name for f in d.iterdir() if f.is_file()]

    def list_periodic(self, period: str) -> List[str]:
        """List jobs in a periodic cron directory."""
        d = self.cron_dirs.get(period)
        if not d or not d.exists():
            return []
        return [f.name for f in d.iterdir() if f.is_file()]

    def get_summary(self) -> Dict[str, Any]:
        return {
            name: {"exists": path.exists(), "files": len([f for f in path.iterdir() if f.is_file()]) if path.exists() else 0}
            for name, path in self.cron_dirs.items()
        }
