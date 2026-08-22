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
UmerOS /dev/pts — Pseudo-terminal slave devices.

FHS 3.0 /dev/pts:
  /dev/pts/0, /dev/pts/1, ...  — Pseudo-terminal slave nodes.
  Each slave is paired with a master via /dev/ptmx.

 major:minor: 136:0 through 136:255

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Pts")


class PtsDevice:
    """Pseudo-terminal slave device manager — /dev/pts/.

    Provides:
      /dev/pts/0 - /dev/pts/255
      Slave devices paired with /dev/ptmx.
    """

    PTS_MAJOR = 136
    MAX_PTS = 256

    def __init__(self):
        self._slaves: Dict[int, Dict[str, Any]] = {}
        self._register_directory()
        log.info("PtsDevice created (max=%d)", self.MAX_PTS)

    def _register_directory(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="pts", path="/dev/pts", dev_type=DeviceType.DIRECTORY,
            description="Pseudo-terminal slaves",
        ))

    def allocate(self, pts_num: int) -> bool:
        """Register a new slave device node."""
        if pts_num < 0 or pts_num >= self.MAX_PTS:
            return False
        if pts_num in self._slaves:
            return False
        mgr = DeviceManager.get_instance()
        node = DeviceNode(
            name=str(pts_num), path=f"/dev/pts/{pts_num}",
            dev_type=DeviceType.CHAR, major=self.PTS_MAJOR, minor=pts_num,
            mode=0o620, description=f"PTY slave {pts_num}",
        )
        if mgr.create_node(node):
            self._slaves[pts_num] = {"active": True}
            log.info("PTS slave allocated: /dev/pts/%d", pts_num)
            return True
        return False

    def free(self, pts_num: int) -> bool:
        """Remove a slave device node."""
        if pts_num not in self._slaves:
            return False
        mgr = DeviceManager.get_instance()
        mgr.remove_node(f"/dev/pts/{pts_num}")
        del self._slaves[pts_num]
        log.info("PTS slave freed: /dev/pts/%d", pts_num)
        return True

    def get_active(self) -> List[int]:
        return list(self._slaves.keys())

    def get_info(self) -> Dict[str, Any]:
        return {
            "major": self.PTS_MAJOR,
            "max_pts": self.MAX_PTS,
            "active": len(self._slaves),
            "slaves": list(self._slaves.keys()),
        }

    def __repr__(self) -> str:
        return f"<PtsDevice active={len(self._slaves)}>"
