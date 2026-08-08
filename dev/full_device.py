"""
UmerOS /dev/full — Write-full device.

FHS 3.0 /dev/full:
  /dev/full — The full device. Reads return null bytes (like /dev/zero).
  Writes fail with errno ENOSPC (no space left on device).
  Useful for testing write failure handling.

Linux major:minor = 1:7

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import errno
import logging
from typing import Any, Dict

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Full")


class FullDevice:
    """Character device that always reports ENOSPC on write.

    /dev/full:
      - read(n) → b"\x00" * n  (like /dev/zero)
      - write(data) → raises OSError(ENOSPC)
    """

    MAJOR = 1
    MINOR = 7
    DEV_PATH = "/dev/full"

    def __init__(self, dev_path: str = DEV_PATH):
        self.dev_path = dev_path
        self._bytes_read = 0
        self._read_count = 0
        self._write_attempts = 0
        self._write_failures = 0
        self._node = DeviceNode(
            name="full",
            path=dev_path,
            dev_type=DeviceType.CHAR,
            major=self.MAJOR,
            minor=self.MINOR,
            mode=0o666,
            description="Full device — writes always fail with ENOSPC",
            write_callback=self._on_write,
            read_callback=self._on_read,
        )
        self._register()
        log.info("FullDevice created at %s", dev_path)

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(self._node)

    def _on_read(self, size: int) -> bytes:
        self._bytes_read += size
        self._read_count += 1
        return b"\x00" * size

    def _on_write(self, data: bytes) -> int:
        self._write_attempts += 1
        self._write_failures += 1
        raise OSError(errno.ENOSPC, "No space left on device", self.dev_path)

    def write(self, data: bytes) -> int:
        return self._on_write(data)

    def read(self, size: int = 4096) -> bytes:
        return self._on_read(size)

    def get_info(self) -> Dict[str, Any]:
        return {
            "device": self.dev_path,
            "type": "char",
            "major": self.MAJOR,
            "minor": self.MINOR,
            "bytes_read": self._bytes_read,
            "read_count": self._read_count,
            "write_attempts": self._write_attempts,
            "write_failures": self._write_failures,
        }

    def __repr__(self) -> str:
        return f"<FullDevice {self.dev_path}>"
