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
UmerOS losetup — Loop device management.

FHS 3.0 /dev:
  losetup — Set up and control loop devices. Loop devices allow
  mounting a file as a block device (e.g., ISO images, disk images).

  Usage:
    losetup -a                    List all loop devices
    losetup /dev/loopN FILE       Attach FILE to /dev/loopN
    losetup -d /dev/loopN         Detach /dev/loopN
    losetup -f                    Find first free loop device

 major:minor: loop0 = 7:0, loop1 = 7:1, ... loop7 = 7:7

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Loopsetup")


class LosetupCommand:
    """losetup — Loop device management.

    Usage:
        losetup [-a]                    List attached loop devices
        losetup /dev/loopN FILE         Attach file to loop device
        losetup -d /dev/loopN           Detach loop device
        losetup -f                      Find first free loop device
        losetup --help                  Show help
    """

    MAJOR = 7
    MAX_LOOPS = 8

    def __init__(self):
        self._attachments: Dict[int, str] = {}  # loop_num -> file_path
        self._register_loop_devices()

    def _register_loop_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_LOOPS):
            mgr.create_node(DeviceNode(
                name=f"loop{i}", path=f"/dev/loop{i}", dev_type=DeviceType.BLOCK,
                major=self.MAJOR, minor=i, mode=0o660,
                description=f"Loop device {i}",
            ))

    def execute(self, args: List[str], stdin=None, stdout=None) -> int:
        if not args or "--help" in args or "-h" in args:
            self._print_help(stdout)
            return 0

        if "-a" in args or "--list" in args:
            return self._cmd_list(stdout)
        elif "-f" in args or "--find" in args:
            return self._cmd_find(stdout)
        elif "-d" in args or "--detach" in args:
            idx = args.index("-d") if "-d" in args else args.index("--detach")
            if idx + 1 < len(args):
                return self._cmd_detach(args[idx + 1], stdout)
            else:
                if stdout:
                    stdout.write("losetup: specify device to detach\n")
                return 1
        elif args[0] == "-o" or args[0].startswith("--offset"):
            # losetup -o OFFSET /dev/loopN FILE
            if len(args) >= 3:
                return self._cmd_attach(args[1], args[2], stdout)
        else:
            # losetup /dev/loopN FILE
            if len(args) >= 2:
                return self._cmd_attach(args[0], args[1], stdout)
            elif len(args) == 1:
                return self._cmd_status(args[0], stdout)

        if stdout:
            stdout.write("losetup: invalid arguments\n")
        return 1

    def _cmd_list(self, stdout) -> int:
        if not self._attachments:
            if stdout:
                stdout.write("No loop devices attached\n")
            return 0
        if stdout:
            for loop_num, file_path in sorted(self._attachments.items()):
                stdout.write(f"/dev/loop{loop_num}: [{file_path}]\n")
        return 0

    def _cmd_find(self, stdout) -> int:
        for i in range(self.MAX_LOOPS):
            if i not in self._attachments:
                if stdout:
                    stdout.write(f"/dev/loop{i}\n")
                return 0
        if stdout:
            stdout.write("losetup: no free loop devices\n")
        return 1

    def _cmd_attach(self, device: str, file_path: str, stdout) -> int:
        loop_num = self._parse_loop_num(device)
        if loop_num is None:
            if stdout:
                stdout.write(f"losetup: '{device}' is not a loop device\n")
            return 1
        if loop_num in self._attachments:
            if stdout:
                stdout.write(f"losetup: {device} is already in use\n")
            return 1
        self._attachments[loop_num] = file_path
        if stdout:
            stdout.write(f"{device}: [{file_path}]\n")
        log.info("losetup: attached %s -> %s", device, file_path)
        return 0

    def _cmd_detach(self, device: str, stdout) -> int:
        loop_num = self._parse_loop_num(device)
        if loop_num is None or loop_num not in self._attachments:
            if stdout:
                stdout.write(f"losetup: '{device}' is not attached\n")
            return 1
        file_path = self._attachments.pop(loop_num)
        if stdout:
            stdout.write(f"Detached {device} from [{file_path}]\n")
        log.info("losetup: detached %s", device)
        return 0

    def _cmd_status(self, device: str, stdout) -> int:
        loop_num = self._parse_loop_num(device)
        if loop_num is None:
            if stdout:
                stdout.write(f"losetup: '{device}' is not a loop device\n")
            return 1
        file_path = self._attachments.get(loop_num)
        if file_path:
            if stdout:
                stdout.write(f"{device}: [{file_path}]\n")
        else:
            if stdout:
                stdout.write(f"{device}: not attached\n")
        return 0

    def _parse_loop_num(self, device: str) -> Optional[int]:
        name = device.split("/")[-1]
        if name.startswith("loop"):
            try:
                num = int(name[4:])
                if 0 <= num < self.MAX_LOOPS:
                    return num
            except ValueError:
                pass
        return None

    def attach(self, loop_num: int, file_path: str) -> bool:
        """Programmatic attach."""
        if loop_num < 0 or loop_num >= self.MAX_LOOPS or loop_num in self._attachments:
            return False
        self._attachments[loop_num] = file_path
        return True

    def detach(self, loop_num: int) -> bool:
        if loop_num in self._attachments:
            del self._attachments[loop_num]
            return True
        return False

    def get_attached(self) -> Dict[int, str]:
        return dict(self._attachments)

    def find_free(self) -> Optional[int]:
        for i in range(self.MAX_LOOPS):
            if i not in self._attachments:
                return i
        return None

    def _print_help(self, stdout) -> None:
        if stdout:
            stdout.write("losetup — Loop device management\n\n")
            stdout.write("Usage:\n")
            stdout.write("  losetup -a                        List attached loop devices\n")
            stdout.write("  losetup /dev/loopN FILE           Attach file to loop device\n")
            stdout.write("  losetup -d /dev/loopN             Detach loop device\n")
            stdout.write("  losetup -f                        Find first free loop device\n")

    def get_info(self) -> Dict[str, Any]:
        return {
            "max_loops": self.MAX_LOOPS,
            "attached": self._attachments,
            "free_count": self.MAX_LOOPS - len(self._attachments),
        }

    def __repr__(self) -> str:
        return f"<LoopsetupCommand attached={len(self._attachments)}>"
