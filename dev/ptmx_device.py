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
UmerOS /dev/ptmx — Pseudo-Terminal Master.

FHS 3.0 /dev/ptmx:
  /dev/ptmx — PTY master clone device. Each open() returns a new
  master fd and creates a corresponding /dev/pts/N slave.
  /dev/pts/ — Directory of PTY slave devices (numbered 0..N).

 major:minor: ptmx = 5:2

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import os
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Ptmx")


class PtmxDevice:
    """Pseudo-terminal master/slave manager.

    /dev/ptmx:
      open() → (master_fd, slave_path)
      Master and slave are connected; writes to one appear as reads on other.

    /dev/pts/N:
      Slave end of the pseudo-terminal pair.
    """

    PTMX_MAJOR = 5
    PTMX_MINOR = 2
    PTS_MAJOR = 136
    MAX_PTS = 256  # /dev/pts/0 - /dev/pts/255

    def __init__(self):
        self._next_pts = 0
        self._pairs: Dict[int, Tuple[deque, deque]] = {}  # pts_num -> (master_buf, slave_buf)
        self._slave_nodes: List[DeviceNode] = []
        self._register_ptmx()
        log.info("PtmxDevice created (ptmx + pts/0-%d)", self.MAX_PTS - 1)

    def _register_ptmx(self) -> None:
        mgr = DeviceManager.get_instance()
        # /dev/ptmx
        mgr.create_node(DeviceNode(
            name="ptmx", path="/dev/ptmx", dev_type=DeviceType.CHAR,
            major=self.PTMX_MAJOR, minor=self.PTMX_MINOR, mode=0o666,
            description="PTY master clone device",
            read_callback=self._on_master_read,
            write_callback=self._on_master_write,
        ))
        # /dev/pts/ directory
        mgr.create_node(DeviceNode(
            name="pts", path="/dev/pts", dev_type=DeviceType.DIRECTORY,
            description="Pseudo-terminal slaves",
        ))

    def clone(self) -> int:
        """Open /dev/ptmx → allocate new PTY pair.

        Returns the slave number (N for /dev/pts/N).
        """
        if self._next_pts >= self.MAX_PTS:
            raise OSError(24, "Too many open pseudo-terminals")
        pts_num = self._next_pts
        self._next_pts += 1
        master_buf: deque = deque()
        slave_buf: deque = deque()
        self._pairs[pts_num] = (master_buf, slave_buf)
        # Register slave device node
        mgr = DeviceManager.get_instance()
        node = DeviceNode(
            name=str(pts_num),
            path=f"/dev/pts/{pts_num}",
            dev_type=DeviceType.CHAR,
            major=self.PTS_MAJOR,
            minor=pts_num,
            mode=0o620,
            description=f"PTY slave {pts_num}",
            read_callback=lambda size, n=pts_num: self._on_slave_read(size, n),
            write_callback=lambda data, n=pts_num: self._on_slave_write(data, n),
        )
        mgr.create_node(node)
        self._slave_nodes.append(node)
        log.info("PTY pair created: master <-> /dev/pts/%d", pts_num)
        return pts_num

    def _on_master_read(self, size: int) -> bytes:
        for pts_num, (m, s) in self._pairs.items():
            if s:
                return s.popleft()
        return b""

    def _on_master_write(self, data: bytes) -> int:
        for pts_num, (m, s) in self._pairs.items():
            if not m:
                m.append(data)
                return len(data)
        return 0

    def _on_slave_read(self, size: int, pts_num: int) -> bytes:
        pair = self._pairs.get(pts_num)
        if pair:
            m, s = pair
            return m.popleft() if m else b""
        return b""

    def _on_slave_write(self, data: bytes, pts_num: int) -> int:
        pair = self._pairs.get(pts_num)
        if pair:
            m, s = pair
            s.append(data)
            return len(data)
        return 0

    def write_to_master(self, pts_num: int, data: bytes) -> int:
        pair = self._pairs.get(pts_num)
        if pair:
            pair[0].append(data)
            return len(data)
        return 0

    def read_from_master(self, pts_num: int) -> Optional[bytes]:
        pair = self._pairs.get(pts_num)
        if pair:
            return pair[0].popleft() if pair[0] else None
        return None

    def write_to_slave(self, pts_num: int, data: bytes) -> int:
        pair = self._pairs.get(pts_num)
        if pair:
            pair[1].append(data)
            return len(data)
        return 0

    def read_from_slave(self, pts_num: int) -> Optional[bytes]:
        pair = self._pairs.get(pts_num)
        if pair:
            return pair[1].popleft() if pair[1] else None
        return None

    def get_active_pairs(self) -> List[int]:
        return list(self._pairs.keys())

    def close_pair(self, pts_num: int) -> bool:
        if pts_num in self._pairs:
            del self._pairs[pts_num]
            mgr = DeviceManager.get_instance()
            mgr.remove_node(f"/dev/pts/{pts_num}")
            log.info("PTY pair closed: /dev/pts/%d", pts_num)
            return True
        return False

    def get_info(self) -> Dict[str, Any]:
        return {
            "ptmx": f"/dev/ptmx ({self.PTMX_MAJOR}:{self.PTMX_MINOR})",
            "active_pairs": len(self._pairs),
            "next_pts": self._next_pts,
            "max_pts": self.MAX_PTS,
            "pairs": {n: {"master_pending": len(m), "slave_pending": len(s)} for n, (m, s) in self._pairs.items()},
        }

    def __repr__(self) -> str:
        return f"<PtmxDevice pairs={len(self._pairs)}>"
