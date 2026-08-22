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
UmerOS /dev/shm — POSIX shared memory.

FHS 3.0 /dev/shm:
  /dev/shm/ — Directory for POSIX shared memory objects.
  Used by shm_open() / shm_unlink() from POSIX IPC.

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Shm")


class ShmDevice:
    """POSIX shared memory directory — /dev/shm/.

    Provides:
      /dev/shm/       — Shared memory directory
      Shared memory segments managed by the VFS layer.
    """

    def __init__(self):
        self._segments: Dict[str, Dict[str, Any]] = {}
        self._register_directory()
        log.info("ShmDevice created")

    def _register_directory(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="shm", path="/dev/shm", dev_type=DeviceType.DIRECTORY,
            description="POSIX shared memory",
        ))

    def create_segment(self, name: str, size: int = 4096) -> bool:
        """Create a shared memory segment."""
        path = f"/dev/shm/{name}"
        if path in self._segments:
            return False
        mgr = DeviceManager.get_instance()
        node = DeviceNode(
            name=name, path=path, dev_type=DeviceType.FIFO,
            mode=0o666, description=f"SHM segment {name}",
        )
        if mgr.create_node(node):
            self._segments[path] = {"name": name, "size": size}
            log.info("SHM segment created: %s (%d bytes)", name, size)
            return True
        return False

    def remove_segment(self, name: str) -> bool:
        path = f"/dev/shm/{name}"
        if path not in self._segments:
            return False
        mgr = DeviceManager.get_instance()
        mgr.remove_node(path)
        del self._segments[path]
        log.info("SHM segment removed: %s", name)
        return True

    def list_segments(self) -> List[str]:
        return [s["name"] for s in self._segments.values()]

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/shm",
            "segments": len(self._segments),
            "segment_names": self.list_segments(),
        }

    def __repr__(self) -> str:
        return f"<ShmDevice segments={len(self._segments)}>"
