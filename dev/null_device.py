"""
UmerOS /dev/null — Discard device.

FHS 3.0 /dev/null:
  /dev/null — The null device. Writes succeed, data is discarded.
  Reads return EOF immediately. Used as /dev/zero alternative for writes.

Linux major:minor = 1:3

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Null")


class NullDevice:
    """Character device that discards all data written to it.

    /dev/null:
      - write(data) → len(data)  (data silently discarded)
      - read(n) → b""            (EOF immediately)
      - seekable → False
    """

    MAJOR = 1
    MINOR = 3
    DEV_PATH = "/dev/null"

    def __init__(self, dev_path: str = DEV_PATH):
        self.dev_path = dev_path
        self._bytes_written = 0
        self._bytes_read = 0
        self._write_count = 0
        self._read_count = 0
        self._node = DeviceNode(
            name="null",
            path=dev_path,
            dev_type=DeviceType.CHAR,
            major=self.MAJOR,
            minor=self.MINOR,
            mode=0o666,
            description="Null device — discards all data",
            write_callback=self._on_write,
            read_callback=self._on_read,
        )
        self._register()
        log.info("NullDevice created at %s", dev_path)

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(self._node)

    def _on_write(self, data: bytes) -> int:
        self._bytes_written += len(data)
        self._write_count += 1
        return len(data)

    def _on_read(self, size: int) -> bytes:
        self._read_count += 1
        return b""

    def write(self, data: bytes) -> int:
        count = self._on_write(data)
        log.debug("null: write %d bytes (total %d)", len(data), self._bytes_written)
        return count

    def read(self, size: int = 4096) -> bytes:
        self._on_read(size)
        return b""

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
        return f"<NullDevice {self.dev_path}>"
