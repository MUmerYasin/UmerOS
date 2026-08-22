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
UmerOS /dev/char — Character device symlinks.

FHS 3.0 /dev/char:
  /dev/char/ — Directory of symlinks to character devices, named by
  major:minor number (e.g. 1:3 → /dev/null).

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.CharDevices")


class CharDeviceLinks:
    """Character device symlinks — /dev/char/.

    Provides:
      /dev/char/1:3    → /dev/null
      /dev/char/1:5    → /dev/zero
      /dev/char/5:0    → /dev/tty
      /dev/char/5:2    → /dev/ptmx
      etc.
    """

    def __init__(self):
        self._links: Dict[str, str] = {}
        self._register_directory()
        self._create_default_links()
        log.info("CharDeviceLinks created")

    def _register_directory(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="char", path="/dev/char", dev_type=DeviceType.DIRECTORY,
            description="Character device symlinks",
        ))

    def _create_default_links(self) -> None:
        defaults = [
            ("1:3",   "/dev/null"),
            ("1:5",   "/dev/zero"),
            ("1:7",   "/dev/full"),
            ("1:8",   "/dev/random"),
            ("1:9",   "/dev/urandom"),
            ("4:0",   "/dev/tty0"),
            ("4:64",  "/dev/ttyS0"),
            ("5:0",   "/dev/tty"),
            ("5:1",   "/dev/console"),
            ("5:2",   "/dev/ptmx"),
            ("10:200", "/dev/net/tun"),
            ("10:229", "/dev/log"),
            ("13:64", "/dev/input/event0"),
            ("13:0",  "/dev/input/js0"),
            ("13:200", "/dev/input/mice"),
            ("116:0", "/dev/snd/card0"),
            ("226:0", "/dev/dri/card0"),
        ]
        for dev_num, target in defaults:
            self.add_link(dev_num, target)

    def add_link(self, dev_num: str, target_path: str) -> bool:
        """Create a character device symlink."""
        path = f"/dev/char/{dev_num}"
        if path in self._links:
            return False
        mgr = DeviceManager.get_instance()
        node = DeviceNode(
            name=dev_num, path=path, dev_type=DeviceType.SYMLINK,
            symlink_target=target_path,
            description=f"Char symlink {dev_num} → {target_path}",
        )
        if mgr.create_node(node):
            self._links[dev_num] = target_path
            return True
        return False

    def remove_link(self, dev_num: str) -> bool:
        path = f"/dev/char/{dev_num}"
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
            "path": "/dev/char",
            "link_count": len(self._links),
            "links": self._links,
        }

    def __repr__(self) -> str:
        return f"<CharDeviceLinks links={len(self._links)}>"
