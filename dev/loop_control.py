"""
UmerOS /dev/loop-control — Loop device control node.

/dev/loop-control (major 10, minor 237):
  Provides ioctl interface to dynamically allocate and free
  loop devices. Used by losetup -f to find first free loop,
  and by mount/losetup to auto-allocate loop devices.

  ioctls:
    LOOP_CTL_ADD = 0x4C80  — Add new loop device
    LOOP_CTL_REMOVE = 0x4C81 — Remove loop device
    LOOP_CTL_GET_FREE = 0x4C82 — Get first free loop number

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.LoopControl")


class LoopControlDevice:
    """/dev/loop-control — Loop device management interface.

    Provides dynamic allocation and deallocation of loop devices.
    Complements the static /dev/loop0-loop7 devices from losetup.
    """

    MAJOR = 10
    MINOR = 237

    LOOP_CTL_ADD = 0x4C80
    LOOP_CTL_REMOVE = 0x4C81
    LOOP_CTL_GET_FREE = 0x4C82

    MAX_LOOPS = 256

    def __init__(self):
        self._allocated: Dict[int, bool] = {}
        self._next_id = 0
        self._register()
        log.info("LoopControlDevice /dev/loop-control created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="loop-control", path="/dev/loop-control",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o660,
            description="Loop device control",
            ioctl_callback=self._ioctl,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        if request == self.LOOP_CTL_ADD:
            loop_id = self._add_loop()
            return loop_id if loop_id >= 0 else -1
        if request == self.LOOP_CTL_REMOVE:
            return 0 if self._remove_loop(arg) else -1
        if request == self.LOOP_CTL_GET_FREE:
            return self._get_free()
        return -1

    def _add_loop(self) -> int:
        loop_id = self._next_id
        if loop_id >= self.MAX_LOOPS:
            return -1
        self._allocated[loop_id] = True
        self._next_id = loop_id + 1
        log.info("loop-control: allocated loop%d", loop_id)
        return loop_id

    def _remove_loop(self, loop_id: int) -> bool:
        if loop_id not in self._allocated:
            return False
        del self._allocated[loop_id]
        log.info("loop-control: freed loop%d", loop_id)
        return True

    def _get_free(self) -> int:
        for i in range(self.MAX_LOOPS):
            if i not in self._allocated:
                return i
        return -1

    def allocate(self) -> int:
        """Programmatic loop allocation."""
        return self._get_free()

    def free(self, loop_id: int) -> bool:
        """Programmatic loop deallocation."""
        return self._remove_loop(loop_id)

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/loop-control",
            "max_loops": self.MAX_LOOPS,
            "allocated": list(self._allocated.keys()),
            "free_count": self.MAX_LOOPS - len(self._allocated),
        }
