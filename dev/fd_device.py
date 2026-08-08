"""
UmerOS /dev/stdin, /dev/stdout, /dev/stderr, /dev/fd — File descriptor devices.

FHS 3.0 /dev/fd:
  /dev/fd/N   — File descriptor N (symlink to /proc/self/fd/N)
  /dev/stdin  — Standard input  (fd 0)
  /dev/stdout — Standard output (fd 1)
  /dev/stderr — Standard error  (fd 2)

In UmerOS, these are managed by the VFS layer and point to the
current process's file descriptor table.

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Fd")


class FdDevice:
    """File descriptor device manager.

    Manages:
      /dev/stdin  (symlink → /proc/self/fd/0)
      /dev/stdout (symlink → /proc/self/fd/1)
      /dev/stderr (symlink → /proc/self/fd/2)
      /dev/fd     (directory, symlinks for each open fd)
      /dev/PID/fd (per-process fd directory, if enabled)
    """

    FD_MAJOR = 0
    FD_MINOR = 0
    MAX_FDS = 1024

    def __init__(self, max_fds: int = MAX_FDS):
        self.max_fds = max_fds
        self._fd_links: Dict[int, str] = {}  # fd_num -> target_path
        self._register_all()
        log.info("FdDevice created (max_fds=%d)", max_fds)

    def _register_all(self) -> None:
        mgr = DeviceManager.get_instance()
        # /dev/fd directory
        mgr.create_node(DeviceNode(
            name="fd", path="/dev/fd", dev_type=DeviceType.DIRECTORY,
            description="File descriptor symlinks",
        ))
        # Symlinks for stdin/stdout/stderr
        for fd_num, name in [(0, "stdin"), (1, "stdout"), (2, "stderr")]:
            mgr.create_node(DeviceNode(
                name=name, path=f"/dev/{name}", dev_type=DeviceType.SYMLINK,
                symlink_target=f"/proc/self/fd/{fd_num}",
                description=f"Standard {name}",
            ))
            self._fd_links[fd_num] = f"/proc/self/fd/{fd_num}"
        # Default fd symlinks (0, 1, 2)
        for fd_num in range(3):
            mgr.create_node(DeviceNode(
                name=str(fd_num), path=f"/dev/fd/{fd_num}", dev_type=DeviceType.SYMLINK,
                symlink_target=f"/proc/self/fd/{fd_num}",
                description=f"File descriptor {fd_num}",
            ))

    def register_fd(self, fd_num: int, target_path: str) -> bool:
        """Register a new file descriptor symlink."""
        if fd_num < 0 or fd_num >= self.max_fds:
            return False
        mgr = DeviceManager.get_instance()
        path = f"/dev/fd/{fd_num}"
        mgr.create_node(DeviceNode(
            name=str(fd_num), path=path, dev_type=DeviceType.SYMLINK,
            symlink_target=target_path,
            description=f"File descriptor {fd_num} → {target_path}",
        ))
        self._fd_links[fd_num] = target_path
        log.debug("fd %d → %s", fd_num, target_path)
        return True

    def unregister_fd(self, fd_num: int) -> bool:
        if fd_num not in self._fd_links:
            return False
        mgr = DeviceManager.get_instance()
        mgr.remove_node(f"/dev/fd/{fd_num}")
        del self._fd_links[fd_num]
        return True

    def get_fd_target(self, fd_num: int) -> Optional[str]:
        return self._fd_links.get(fd_num)

    def list_fds(self) -> Dict[int, str]:
        return dict(self._fd_links)

    def get_info(self) -> Dict[str, Any]:
        return {
            "fd_count": len(self._fd_links),
            "max_fds": self.max_fds,
            "fd_links": self._fd_links,
        }

    def __repr__(self) -> str:
        return f"<FdDevice fds={len(self._fd_links)}>"
