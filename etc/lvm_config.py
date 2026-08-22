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
UmerOS /etc LVM Configuration
================================
Manages Logical Volume Manager configuration.

FHS 3.0 entries:
  /etc/lvm/           — LVM configuration
  /etc/lvm/lvm.conf   — LVM main configuration
  /etc/lvm/lvmlocal.conf — LVM local configuration
  /etc/lvm/backup/    — LVM metadata backups
  /etc/lvm/archive/   — LVM metadata archives

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger("UmerOS.Etc.LVMConfig")


class LVMConfigManager:
    """Manages /etc/lvm/ configuration."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.lvm_path = self.etc_path / "lvm"

    def initialize(self) -> bool:
        try:
            self.lvm_path.mkdir(parents=True, exist_ok=True)
            (self.lvm_path / "backup").mkdir(parents=True, exist_ok=True)
            (self.lvm_path / "archive").mkdir(parents=True, exist_ok=True)
            self._create_lvm_conf()
            self._create_lvmlocal_conf()
            log.info("Initialized /etc/lvm/")
            return True
        except Exception as e:
            log.error("Failed to initialize LVM config: %s", e)
            return False

    def _create_lvm_conf(self) -> None:
        fp = self.lvm_path / "lvm.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/lvm/lvm.conf - LVM configuration\n"
            "# UmerOS LVM Configuration\n"
            "# See lvm.conf(5) for details.\n\n"
            "devices {\n"
            "    filter = [ \"a/.*/\" ]\n"
            "    scan = [ \"/dev\" ]\n"
            "    obtain_device_list_from_udev = 1\n"
            "    preferred_names = []\n"
            "    reject = []\n"
            "    resize_retries = 3\n"
            "}\n\n"
            "activation {\n"
            "    monitoring = 1\n"
            "    udev_sync = 1\n"
            "    udev_rules = 1\n"
            "}\n\n"
            "global {\n"
            "    use_lvmetad = 1\n"
            "    locking_type = 1\n"
            "    wait_for_locks = 1\n"
            "    priority_vgs_with_snapshot = 1\n"
            "}\n\n"
            "backup {\n"
            "    backup = 1\n"
            "    backup_dir = \"/etc/lvm/backup\"\n"
            "    archive = 1\n"
            "    archive_dir = \"/etc/lvm/archive\"\n"
            "    retain_days = 30\n"
            "    min_retain_days = 10\n"
            "}\n\n"
            "log {\n"
            "    verbose = 0\n"
            "    compact = 1\n"
            "    file = \"/var/log/lvm2.log\"\n"
            "    overwrite = 0\n"
            "    level = 5\n"
            "    syslog = 1\n"
            "}\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/lvm/lvm.conf")

    def _create_lvmlocal_conf(self) -> None:
        fp = self.lvm_path / "lvmlocal.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/lvm/lvmlocal.conf - LVM local configuration\n"
            "# UmerOS LVM Local Configuration\n\n"
            "local {\n"
            "    use_devicesfile = 0\n"
            "}\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/lvm/lvmlocal.conf")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "lvm_path_exists": self.lvm_path.exists(),
            "lvm_conf_exists": (self.lvm_path / "lvm.conf").exists(),
            "lvmlocal_conf_exists": (self.lvm_path / "lvmlocal.conf").exists(),
            "backup_count": len(list((self.lvm_path / "backup").iterdir())) if (self.lvm_path / "backup").exists() else 0,
            "archive_count": len(list((self.lvm_path / "archive").iterdir())) if (self.lvm_path / "archive").exists() else 0,
        }
