"""
UmerOS /dev/tty, /dev/console, /dev/ttyN — Terminal devices.

FHS 3.0 /dev/tty:
  /dev/tty    — Controlling terminal of current process
  /dev/console — System console (kernel messages)
  /dev/tty0   — Current virtual terminal
  /dev/ttyN   — Virtual terminal N (0-63)
  /dev/ttyS0-31 — Serial ports (UART)

Linux major:minor:
  tty: 5:0, console: 5:1, tty0: 4:0, ttyS0: 4:64

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.TTY")


class TTYDevice:
    """Terminal device manager.

    Manages /dev/tty, /dev/console, /dev/ttyN, /dev/ttySN.
    Simulates a virtual terminal with input/output buffers.
    """

    # Standard major:minor pairs
    TTY_MAJOR = 5
    TTY_MINOR = 0       # /dev/tty
    CONSOLE_MAJOR = 5
    CONSOLE_MINOR = 1   # /dev/console
    VT_MAJOR = 4        # /dev/ttyN
    VT_MINOR_START = 0  # /dev/tty0 = major 4, minor 0
    SERIAL_MAJOR = 4
    SERIAL_MINOR_START = 64  # /dev/ttyS0 = major 4, minor 64

    MAX_VT = 64         # /dev/tty0 - /dev/tty63
    MAX_SERIAL = 32     # /dev/ttyS0 - /dev/ttyS31

    def __init__(self):
        self._nodes: List[DeviceNode] = []
        self._active_vt = 0
        self._console_buffer: deque = deque(maxlen=1024)
        self._vt_buffers: Dict[int, deque] = {i: deque(maxlen=256) for i in range(self.MAX_VT)}
        self._serial_buffers: Dict[int, deque] = {i: deque(maxlen=256) for i in range(self.MAX_SERIAL)}
        self._register_all()
        log.info("TTYDevice created (%d virtual terminals, %d serial ports)", self.MAX_VT, self.MAX_SERIAL)

    def _register_all(self) -> None:
        mgr = DeviceManager.get_instance()
        # /dev/tty
        mgr.create_node(DeviceNode(
            name="tty", path="/dev/tty", dev_type=DeviceType.CHAR,
            major=self.TTY_MAJOR, minor=self.TTY_MINOR, mode=0o666,
            description="Controlling terminal",
            read_callback=self._on_tty_read, write_callback=self._on_tty_write,
        ))
        # /dev/console
        mgr.create_node(DeviceNode(
            name="console", path="/dev/console", dev_type=DeviceType.CHAR,
            major=self.CONSOLE_MAJOR, minor=self.CONSOLE_MINOR, mode=0o620,
            description="System console",
            read_callback=self._on_console_read, write_callback=self._on_console_write,
        ))
        # /dev/ttyN
        for i in range(self.MAX_VT):
            mgr.create_node(DeviceNode(
                name=f"tty{i}", path=f"/dev/tty{i}", dev_type=DeviceType.CHAR,
                major=self.VT_MAJOR, minor=self.VT_MINOR_START + i, mode=0o620,
                description=f"Virtual terminal {i}",
                write_callback=lambda data, vt=i: self._on_vt_write(data, vt),
                read_callback=lambda size, vt=i: self._on_vt_read(size, vt),
            ))
        # /dev/ttySN
        for i in range(self.MAX_SERIAL):
            mgr.create_node(DeviceNode(
                name=f"ttyS{i}", path=f"/dev/ttyS{i}", dev_type=DeviceType.CHAR,
                major=self.SERIAL_MAJOR, minor=self.SERIAL_MINOR_START + i, mode=0o620,
                description=f"Serial port {i}",
                write_callback=lambda data, s=i: self._on_serial_write(data, s),
                read_callback=lambda size, s=i: self._on_serial_read(size, s),
            ))

    # ── Callbacks ─────────────────────────────────────────────────────────

    def _on_tty_read(self, size: int) -> bytes:
        return self._vt_buffers.get(self._active_vt, deque()).popleft() if self._vt_buffers.get(self._active_vt) else b""

    def _on_tty_write(self, data: bytes) -> int:
        buf = self._vt_buffers.setdefault(self._active_vt, deque())
        buf.append(data)
        return len(data)

    def _on_console_read(self, size: int) -> bytes:
        return self._console_buffer.popleft() if self._console_buffer else b""

    def _on_console_write(self, data: bytes) -> int:
        self._console_buffer.append(data)
        log.debug("console: %s", data.decode(errors="replace").strip())
        return len(data)

    def _on_vt_read(self, size: int, vt: int) -> bytes:
        buf = self._vt_buffers.get(vt, deque())
        return buf.popleft() if buf else b""

    def _on_vt_write(self, data: bytes, vt: int) -> int:
        buf = self._vt_buffers.setdefault(vt, deque())
        buf.append(data)
        return len(data)

    def _on_serial_read(self, size: int, port: int) -> bytes:
        buf = self._serial_buffers.get(port, deque())
        return buf.popleft() if buf else b""

    def _on_serial_write(self, data: bytes, port: int) -> int:
        buf = self._serial_buffers.setdefault(port, deque())
        buf.append(data)
        return len(data)

    # ── Operations ────────────────────────────────────────────────────────

    def switch_vt(self, vt_num: int) -> bool:
        if 0 <= vt_num < self.MAX_VT:
            self._active_vt = vt_num
            log.info("Switched to VT%d", vt_num)
            return True
        return False

    def write_console(self, data: bytes) -> int:
        self._console_buffer.append(data)
        return len(data)

    def read_console(self) -> Optional[bytes]:
        return self._console_buffer.popleft() if self._console_buffer else None

    def write_tty(self, tty_num: int, data: bytes) -> int:
        buf = self._vt_buffers.setdefault(tty_num, deque())
        buf.append(data)
        return len(data)

    def read_tty(self, tty_num: int) -> Optional[bytes]:
        buf = self._vt_buffers.get(tty_num, deque())
        return buf.popleft() if buf else None

    def write_serial(self, port: int, data: bytes) -> int:
        buf = self._serial_buffers.setdefault(port, deque())
        buf.append(data)
        return len(data)

    def read_serial(self, port: int) -> Optional[bytes]:
        buf = self._serial_buffers.get(port, deque())
        return buf.popleft() if buf else None

    def get_active_vt(self) -> int:
        return self._active_vt

    def get_info(self) -> Dict[str, Any]:
        return {
            "active_vt": self._active_vt,
            "console_buffer_size": len(self._console_buffer),
            "vt_count": self.MAX_VT,
            "serial_count": self.MAX_SERIAL,
            "nodes_created": 2 + self.MAX_VT + self.MAX_SERIAL,
        }

    def __repr__(self) -> str:
        return f"<TTYDevice active_vt={self._active_vt}>"
