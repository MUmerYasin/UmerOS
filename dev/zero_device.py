"""
UmerOS /dev/zero — Zero-fill device.

FHS 3.0 /dev/zero:
  /dev/zero — The zero device. Reads return null bytes (0x00).
  Writes succeed but data is discarded (like /dev/null).
  Used for zero-filled memory mappings.

Linux major:minor = 1:5

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Zero")


class ZeroDevice:
    """Character device that produces null bytes on read.

    /dev/zero:
      - read(n) → b"\x00" * n
      - write(data) → len(data)  (data silently discarded)
      - seekable → True (from /dev/zero, offset ignored)
    """

    MAJOR = 1
    MINOR = 5
    DEV_PATH = "/dev/zero"

    def __init__(self, dev_path: str = DEV_PATH):
        self.dev_path = dev_path
        self._bytes_written = 0
        self._bytes_read = 0
        self._write_count = 0
        self._read_count = 0
        self._position = 0
        self._node = DeviceNode(
            name="zero",
            path=dev_path,
            dev_type=DeviceType.CHAR,
            major=self.MAJOR,
            minor=self.MINOR,
            mode=0o666,
            description="Zero device — returns null bytes on read",
            write_callback=self._on_write,
            read_callback=self._on_read,
        )
        self._register()
        log.info("ZeroDevice created at %s", dev_path)

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(self._node)

    def _on_write(self, data: bytes) -> int:
        self._bytes_written += len(data)
        self._write_count += 1
        return len(data)

    def _on_read(self, size: int) -> bytes:
        self._bytes_read += size
        self._read_count += 1
        self._position += size
        return b"\x00" * size

    def write(self, data: bytes) -> int:
        count = self._on_write(data)
        log.debug("zero: write %d bytes", len(data))
        return count

    def read(self, size: int = 4096) -> bytes:
        return self._on_read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._position = offset
        elif whence == 1:
            self._position += offset
        elif whence == 2:
            self._position = 0  # always zero
        return self._position

    def get_info(self) -> Dict[str, Any]:
        return {
            "device": self.dev_path,
            "type": "char",
            "major": self.MAJOR,
            "minor": self.MINOR,
            "bytes_written": self._bytes_written,
            "bytes_read": self._bytes_read,
            "write_count": self._write_count,
            "read_count": self._read_count,
        }

    def __repr__(self) -> str:
        return f"<ZeroDevice {self.dev_path}>"
