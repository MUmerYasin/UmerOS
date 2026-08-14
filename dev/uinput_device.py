"""
UmerOS /dev — User input device.

 uinput device file:
  /dev/uinput — Virtual input device injection

Major 10: uinput = 10:223

Used by: QEMU, libinput, SDL2, virtual keyboard/mouse drivers.

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.UinputDevice")


class UinputDevice:
    """User input device — /dev/uinput.

    Allows creation of virtual input devices that inject events
    into the input subsystem. Used by:
      - QEMU/KVM for virtual machine input
      - libinput for input device testing
      - SDL2 for virtual gamepad creation
      - Android emulator for touch injection

    Major 10, minor 223: /dev/uinput

    ioctl commands:
      UI_SET_EVBIT   — Enable event type
      UI_SET_KEYBIT  — Enable key code
      UI_SET_ABSBIT  — Enable absolute axis
      UI_DEV_CREATE  — Create virtual device
      UI_DEV_DESTROY — Destroy virtual device
    """

    UINPUT_MAJOR = 10
    UINPUT_MINOR = 223

    # Event types
    EV_SYN = 0x0000
    EV_KEY = 0x0001
    EV_REL = 0x0002
    EV_ABS = 0x0003
    EV_MSC = 0x0004
    EV_SW = 0x0005
    EV_LED = 0x0011
    EV_SND = 0x0012
    EV_REP = 0x0014
    EV_FF = 0x0015
    EV_PWR = 0x0016
    EV_FF_STATUS = 0x0017

    # ioctl numbers
    UI_SET_EVBIT = 0x40045564
    UI_SET_KEYBIT = 0x40045565
    UI_SET_RELBIT = 0x40045566
    UI_SET_ABSBIT = 0x40045567
    UI_SET_MSCBIT = 0x40045568
    UI_SET_LEDBIT = 0x40045569
    UI_SET_SNDBIT = 0x4004556A
    UI_SET_FFBIT = 0x4004556B
    UI_SET_SWBIT = 0x4004556D
    UI_DEV_CREATE = 0x5501
    UI_DEV_DESTROY = 0x5502
    UI_GET_VERSION = 0x80045563

    def __init__(self):
        self._enabled_events: Dict[str, List[int]] = {}
        self._virtual_devices: Dict[str, Dict[str, Any]] = {}
        self._create_device()
        log.info("UinputDevice created")

    def _create_device(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="uinput", path="/dev/uinput",
            dev_type=DeviceType.CHAR,
            major=self.UINPUT_MAJOR, minor=self.UINPUT_MINOR,
            mode=0o660,
            description="Virtual input device injection",
            ioctl_callback=lambda req, arg: self._on_ioctl(req, arg),
            write_callback=lambda data: self._on_write(data),
        ))

    def _on_ioctl(self, request: int, arg: Any) -> int:
        """Handle uinput ioctl commands."""
        if request == self.UI_DEV_CREATE:
            return self._create_virtual_device()
        elif request == self.UI_DEV_DESTROY:
            return self._destroy_virtual_device()
        elif request == self.UI_GET_VERSION:
            return 4  # uinput protocol version 4
        return 0

    def _on_write(self, data: bytes) -> int:
        """Write input events to the device."""
        return len(data)

    def _create_virtual_device(self) -> int:
        """Create a new virtual input device."""
        dev_id = f"virt{len(self._virtual_devices)}"
        self._virtual_devices[dev_id] = {
            "name": f"UmerOS Virtual Device {dev_id}",
            "events": [],
            "created": True,
        }
        log.debug("Created virtual input device: %s", dev_id)
        return 0

    def _destroy_virtual_device(self) -> int:
        """Destroy the current virtual input device."""
        if self._virtual_devices:
            dev_id = list(self._virtual_devices.keys())[-1]
            del self._virtual_devices[dev_id]
            log.debug("Destroyed virtual input device: %s", dev_id)
        return 0

    def enable_event(self, device: str, event_type: int) -> None:
        """Enable an event type on a virtual device."""
        self._enabled_events.setdefault(device, []).append(event_type)

    def get_info(self) -> Dict[str, Any]:
        return {
            "major": self.UINPUT_MAJOR,
            "minor": self.UINPUT_MINOR,
            "path": "/dev/uinput",
            "virtual_devices": len(self._virtual_devices),
        }

    def __repr__(self) -> str:
        return f"<UinputDevice virtual={len(self._virtual_devices)}>"
