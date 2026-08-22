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
UmerOS /dev/block — Block device symlinks.

FHS 3.0 /dev/block:
  /dev/block/ — Directory of symlinks to block devices, named by
  major:minor number (e.g. 8:0 → /dev/sda).

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.BlockDevices")


class BlockDeviceLinks:
    """Block device symlinks — /dev/block/.

    Provides:
      /dev/block/8:0   → /dev/sda
      /dev/block/7:0   → /dev/loop0
      etc.
    """

    def __init__(self):
        self._links: Dict[str, str] = {}  # dev_num_str -> target_path
        self._register_directory()
        self._create_default_links()
        log.info("BlockDeviceLinks created")

    def _register_directory(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="block", path="/dev/block", dev_type=DeviceType.DIRECTORY,
            description="Block device symlinks",
        ))

    def _create_default_links(self) -> None:
        defaults = [
            ("8:0",   "/dev/sda"),
            ("8:16",  "/dev/sdb"),
            ("8:32",  "/dev/sdc"),
            ("33:0",  "/dev/hda"),
            ("253:0", "/dev/vda"),
            ("7:0",   "/dev/loop0"),
            ("7:1",   "/dev/loop1"),
            ("11:0",  "/dev/sr0"),
            ("259:0", "/dev/nvme0n1"),
        ]
        for dev_num, target in defaults:
            self.add_link(dev_num, target)

    def add_link(self, dev_num: str, target_path: str) -> bool:
        """Create a block device symlink."""
        path = f"/dev/block/{dev_num}"
        if path in self._links:
            return False
        mgr = DeviceManager.get_instance()
        node = DeviceNode(
            name=dev_num, path=path, dev_type=DeviceType.SYMLINK,
            symlink_target=target_path,
            description=f"Block symlink {dev_num} → {target_path}",
        )
        if mgr.create_node(node):
            self._links[dev_num] = target_path
            return True
        return False

    def remove_link(self, dev_num: str) -> bool:
        path = f"/dev/block/{dev_num}"
        if path not in self._links:
            return False
        mgr = DeviceManager.get_instance()
        mgr.remove_node(path)
        del self._links[dev_num]
        return True

    def list_links(self) -> Dict[str, str]:
        return dict(self._links)

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/block",
            "link_count": len(self._links),
            "links": self._links,
        }

    def __repr__(self) -> str:
        return f"<BlockDeviceLinks links={len(self._links)}>"
