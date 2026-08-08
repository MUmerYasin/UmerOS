"""
UmerOS /dev/log — Syslog device.

FHS 3.0 /dev/log:
  /dev/log — Unix domain socket for syslog.
  Programs write syslog messages to this socket.

Linux major:minor: log = 10:229

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.LogDevice")


class LogDevice:
    """Syslog device — /dev/log.

    Provides:
      /dev/log — Unix domain socket for syslog.
      Buffers messages written to it for syslog daemon.
    """

    LOG_MAJOR = 10
    LOG_MINOR = 229
    MAX_MESSAGES = 10000

    def __init__(self, max_messages: int = MAX_MESSAGES):
        self.max_messages = max_messages
        self._messages: List[Dict[str, Any]] = []
        self._register_device()
        log.info("LogDevice created (max=%d)", max_messages)

    def _register_device(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="log", path="/dev/log", dev_type=DeviceType.SOCKET,
            major=self.LOG_MAJOR, minor=self.LOG_MINOR, mode=0o666,
            description="Syslog socket",
            write_callback=self._on_write,
        ))

    def _on_write(self, data: bytes) -> int:
        """Handle syslog message writes."""
        try:
            text = data.decode("utf-8", errors="replace").strip()
            if text:
                self._messages.append({
                    "message": text,
                    "length": len(text),
                })
                if len(self._messages) > self.max_messages:
                    self._messages.pop(0)
        except Exception:
            pass
        return len(data)

    def write_message(self, message: str) -> bool:
        """Programmatically write a syslog message."""
        if len(self._messages) >= self.max_messages:
            self._messages.pop(0)
        self._messages.append({
            "message": message,
            "length": len(message),
        })
        return True

    def read_messages(self, count: int = 100) -> List[str]:
        """Read the most recent messages."""
        return [m["message"] for m in self._messages[-count:]]

    def clear_messages(self) -> None:
        self._messages.clear()

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/log",
            "major": self.LOG_MAJOR,
            "minor": self.LOG_MINOR,
            "message_count": len(self._messages),
            "max_messages": self.max_messages,
        }

    def __repr__(self) -> str:
        return f"<LogDevice messages={len(self._messages)}>"
