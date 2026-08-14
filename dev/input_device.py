"""
UmerOS /dev/input — Input device subsystem.

FHS 3.0 /dev/input:
  /dev/input/eventN  — Input event device (evdev)
  /dev/input/jsN     — Joystick device
  /dev/input/mice    — Mouse multiplexer
  /dev/input/mouseN  — Individual mouse devices

major:minor:
  event0 = 13:64, event1 = 13:65, ... event31 = 13:95
  js0 = 13:0, js1 = 13:1, ... js31 = 13:31
  mice = 13:200
  mouse0 = 13:32, mouse1 = 13:33, ... mouse15 = 13:47

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Input")


class InputDevice:
    """Input subsystem manager — /dev/input/.

    Provides:
      /dev/input/event0-event31  — evdev event nodes
      /dev/input/js0-js31        — joystick nodes
      /dev/input/mice            — mouse multiplexer
      /dev/input/mouse0-mouse15  — individual mice
    """

    EVENT_MAJOR = 13
    EVENT_MINOR_START = 64
    EVENT_COUNT = 32

    JS_MAJOR = 13
    JS_MINOR_START = 0
    JS_COUNT = 32

    MICE_MINOR = 200
    MOUSE_MAJOR = 13
    MOUSE_MINOR_START = 32
    MOUSE_COUNT = 16

    def __init__(self):
        self._events: Dict[int, Dict[str, Any]] = {}
        self._joysticks: Dict[int, Dict[str, Any]] = {}
        self._mice: Dict[int, Dict[str, Any]] = {}
        self._register_directories()
        self._register_devices()
        log.info("InputDevice created")

    def _register_directories(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="input", path="/dev/input", dev_type=DeviceType.DIRECTORY,
            description="Input devices",
        ))

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        # Event devices
        for i in range(self.EVENT_COUNT):
            major = self.EVENT_MAJOR
            minor = self.EVENT_MINOR_START + i
            mgr.create_node(DeviceNode(
                name=f"event{i}", path=f"/dev/input/event{i}",
                dev_type=DeviceType.CHAR, major=major, minor=minor,
                mode=0o660, description=f"Input event device {i}",
                read_callback=lambda size, n=i: self._on_event_read(size, n),
                write_callback=lambda data, n=i: self._on_event_write(data, n),
            ))
        # Joystick devices
        for i in range(self.JS_COUNT):
            major = self.JS_MAJOR
            minor = self.JS_MINOR_START + i
            mgr.create_node(DeviceNode(
                name=f"js{i}", path=f"/dev/input/js{i}",
                dev_type=DeviceType.CHAR, major=major, minor=minor,
                mode=0o660, description=f"Joystick device {i}",
            ))
        # Mouse multiplexer
        mgr.create_node(DeviceNode(
            name="mice", path="/dev/input/mice", dev_type=DeviceType.CHAR,
            major=self.EVENT_MAJOR, minor=self.MICE_MINOR, mode=0o660,
            description="Mouse multiplexer",
            read_callback=self._on_mice_read,
        ))
        # Individual mice
        for i in range(self.MOUSE_COUNT):
            minor = self.MOUSE_MINOR_START + i
            mgr.create_node(DeviceNode(
                name=f"mouse{i}", path=f"/dev/input/mouse{i}",
                dev_type=DeviceType.CHAR, major=self.MOUSE_MAJOR, minor=minor,
                mode=0o660, description=f"Mouse device {i}",
            ))

    def _on_event_read(self, size: int, event_num: int) -> bytes:
        info = self._events.get(event_num, {})
        buf = info.get("buffer", b"")
        if buf:
            info["buffer"] = buf[size:]
            return buf[:size]
        return b""

    def _on_event_write(self, data: bytes, event_num: int) -> int:
        info = self._events.setdefault(event_num, {"buffer": b""})
        info["buffer"] = info.get("buffer", b"") + data
        return len(data)

    def _on_mice_read(self, size: int) -> bytes:
        return b"\x00" * min(size, 3)

    def inject_event(self, event_num: int, data: bytes) -> bool:
        """Inject an event into an input device buffer."""
        if event_num < 0 or event_num >= self.EVENT_COUNT:
            return False
        self._events.setdefault(event_num, {"buffer": b""})
        self._events[event_num]["buffer"] += data
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "event_count": self.EVENT_COUNT,
            "js_count": self.JS_COUNT,
            "mouse_count": self.MOUSE_COUNT,
            "active_events": len(self._events),
            "active_joysticks": len(self._joysticks),
        }

    def __repr__(self) -> str:
        return "<InputDevice>"
