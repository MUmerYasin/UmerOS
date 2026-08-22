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
UmerOS Hotplug Event System
Based on Greg Kroah-Hartman's udev paper (OLS 2003)

Device hotplug events flow:
    Kernel → Netlink → udevd → Rules Engine → /dev node creation
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from .device_manager import DeviceManager
from .udev_rules import UdevAction, UdevEvent, UdevRulesEngine

logger = logging.getLogger(__name__)


class HotplugEventType(Enum):
    """Types of hotplug events."""
    DEVICE_ADD = "device_add"
    DEVICE_REMOVE = "device_remove"
    DEVICE_CHANGE = "device_change"
    SUBSYSTEM_ADD = "subsystem_add"
    SUBSYSTEM_REMOVE = "subsystem_remove"


@dataclass
class HotplugEvent:
    """A hotplug event that can be processed by the system."""
    event_type: HotplugEventType
    subsystem: str
    kernel: str
    major: int = 0
    minor: int = 0
    devpath: str = ""
    env: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "kernel"  # kernel, userspace, simulated

    def to_udev_event(self) -> UdevEvent:
        """Convert to udev-style event."""
        action = UdevAction.ADD
        if self.event_type == HotplugEventType.DEVICE_REMOVE:
            action = UdevAction.REMOVE
        elif self.event_type == HotplugEventType.DEVICE_CHANGE:
            action = UdevAction.CHANGE

        return UdevEvent(
            subsystem=self.subsystem,
            kernel=self.kernel,
            action=action,
            devpath=self.devpath,
            major=self.major,
            minor=self.minor,
            env=self.env,
        )


# Type alias for event handlers
EventHandler = Callable[[HotplugEvent], Coroutine[Any, Any, None]]


class HotplugBus:
    """
    Event bus for device hotplug events.

    Based on the kernel→netlink→udevd flow from the udev paper:
    - Devices emit events when state changes
    - Events are broadcast to all subscribers
    - Subscribers (rules engine, device manager) process events
    """

    def __init__(self, device_manager: DeviceManager):
        self.device_manager = device_manager
        self.rules_engine = UdevRulesEngine(device_manager)
        self._handlers: dict[HotplugEventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._event_log: list[HotplugEvent] = []
        self._max_log_size = 1000

    def subscribe(
        self,
        event_type: HotplugEventType | None,
        handler: EventHandler,
    ):
        """
        Subscribe to hotplug events.

        Args:
            event_type: Specific event type to subscribe to, or None for all events
            handler: Async callback function
        """
        if event_type is None:
            self._global_handlers.append(handler)
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: HotplugEventType | None,
        handler: EventHandler,
    ):
        """Unsubscribe from hotplug events."""
        if event_type is None:
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)
        else:
            if event_type in self._handlers:
                if handler in self._handlers[event_type]:
                    self._handlers[event_type].remove(handler)

    async def emit(self, event: HotplugEvent):
        """
        Emit a hotplug event to all subscribers.

        This simulates the kernel netlink socket sending events to udevd.
        """
        # Log the event
        self._event_log.append(event)
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

        logger.debug(
            f"Hotplug: {event.event_type.value} subsystem={event.subsystem} "
            f"kernel={event.kernel} major={event.major} minor={event.minor}"
        )

        # Process through rules engine first
        udev_event = event.to_udev_event()
        self.rules_engine.process_event(udev_event)

        # Notify specific handlers
        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Handler error for {event.event_type}: {e}")

        # Notify global handlers
        for handler in self._global_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Global handler error: {e}")

    def emit_sync(self, event: HotplugEvent):
        """Synchronously emit event (for non-async contexts)."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule as a task if loop is already running
            asyncio.create_task(self.emit(event))
        else:
            loop.run_until_complete(self.emit(event))

    # Convenience methods for common device types

    async def add_block_device(
        self,
        kernel: str,
        major: int,
        minor: int,
        env: dict[str, str] | None = None,
    ):
        """Add a block device (e.g., sda, sda1)."""
        event = HotplugEvent(
            event_type=HotplugEventType.DEVICE_ADD,
            subsystem="block",
            kernel=kernel,
            major=major,
            minor=minor,
            env=env or {},
        )
        await self.emit(event)

    async def remove_block_device(self, kernel: str):
        """Remove a block device."""
        event = HotplugEvent(
            event_type=HotplugEventType.DEVICE_REMOVE,
            subsystem="block",
            kernel=kernel,
        )
        await self.emit(event)

    async def add_char_device(
        self,
        subsystem: str,
        kernel: str,
        major: int,
        minor: int,
        env: dict[str, str] | None = None,
    ):
        """Add a character device (e.g., tty, input)."""
        event = HotplugEvent(
            event_type=HotplugEventType.DEVICE_ADD,
            subsystem=subsystem,
            kernel=kernel,
            major=major,
            minor=minor,
            env=env or {},
        )
        await self.emit(event)

    async def remove_char_device(self, subsystem: str, kernel: str):
        """Remove a character device."""
        event = HotplugEvent(
            event_type=HotplugEventType.DEVICE_REMOVE,
            subsystem=subsystem,
            kernel=kernel,
        )
        await self.emit(event)

    async def add_tty(self, kernel: str, major: int, minor: int):
        """Add a TTY device."""
        await self.add_char_device("tty", kernel, major, minor)

    async def remove_tty(self, kernel: str):
        """Remove a TTY device."""
        await self.remove_char_device("tty", kernel)

    async def add_input_device(
        self,
        kernel: str,
        major: int,
        minor: int,
        name: str = "",
    ):
        """Add an input device (mouse, keyboard, etc.)."""
        env = {"NAME": name} if name else {}
        await self.add_char_device("input", kernel, major, minor, env)

    async def add_net_device(
        self,
        kernel: str,
        mac: str = "",
        driver: str = "",
    ):
        """Add a network device."""
        env = {}
        if mac:
            env["MAC"] = mac
        if driver:
            env["DRIVER"] = driver
        await self.add_char_device("net", kernel, 0, 0, env)

    def get_event_log(self, count: int = 10) -> list[HotplugEvent]:
        """Get recent hotplug events."""
        return self._event_log[-count:]

    def get_stats(self) -> dict[str, Any]:
        """Get hotplug statistics."""
        stats = {
            "total_events": len(self._event_log),
            "handlers": {
                et.value: len(handlers)
                for et, handlers in self._handlers.items()
            },
            "global_handlers": len(self._global_handlers),
        }

        # Count events by type
        event_counts = {}
        for event in self._event_log:
            key = event.event_type.value
            event_counts[key] = event_counts.get(key, 0) + 1
        stats["events_by_type"] = event_counts

        return stats


class HotplugSimulator:
    """
    Simulates device hotplug events for testing and demonstration.

    Usage:
        simulator = HotplugSimulator(hotplug_bus)
        await simulator.plug_usb_drive("sdb", vendor="SanDisk")
        await simulator.unplug_usb_drive("sdb")
    """

    def __init__(self, hotplug_bus: HotplugBus):
        self.bus = hotplug_bus
        self._next_major = 8  # Start after typical block devices
        self._devices: dict[str, HotplugEvent] = {}

    async def plug_usb_drive(
        self,
        kernel: str = "sdb",
        size_gb: int = 32,
        vendor: str = "Generic",
        product: str = "USB Storage",
        serial: str = "",
    ):
        """Simulate plugging in a USB drive."""
        major = self._next_major
        self._next_major += 1

        env = {
            "ID_VENDOR": vendor,
            "ID_MODEL": product,
            "ID_SERIAL": serial or f"{vendor}_{kernel}",
            "ID_FS_USAGE": "filesystem",
            "UDISKS_PARTITION_SIZE": str(size_gb * 1024 * 1024),
        }

        event = HotplugEvent(
            event_type=HotplugEventType.DEVICE_ADD,
            subsystem="block",
            kernel=kernel,
            major=major,
            minor=0,
            env=env,
        )

        self._devices[kernel] = event
        await self.bus.emit(event)
        return event

    async def unplug_usb_drive(self, kernel: str = "sdb"):
        """Simulate unplugging a USB drive."""
        if kernel in self._devices:
            del self._devices[kernel]

        event = HotplugEvent(
            event_type=HotplugEventType.DEVICE_REMOVE,
            subsystem="block",
            kernel=kernel,
        )
        await self.bus.emit(event)

    async def plug_tty(self, kernel: str = "ttyUSB0", baud: int = 9600):
        """Simulate plugging in a USB-serial adapter."""
        major = 188  # Typical for USB-serial
        minor = hash(kernel) % 256

        env = {
            "ID_BUS": "usb",
            "ID_VENDOR": "Prolific",
            "ID_MODEL": "USB-Serial",
            "ID_SERIAL": f"USB_Serial_{kernel}",
            "DEVLINKS": f"/dev/serial/by-id/usb-Prolific_USB-Serial-{kernel}",
        }

        event = HotplugEvent(
            event_type=HotplugEventType.DEVICE_ADD,
            subsystem="tty",
            kernel=kernel,
            major=major,
            minor=minor,
            env=env,
        )

        self._devices[kernel] = event
        await self.bus.emit(event)
        return event

    async def unplug_tty(self, kernel: str = "ttyUSB0"):
        """Simulate unplugging a USB-serial adapter."""
        if kernel in self._devices:
            del self._devices[kernel]

        event = HotplugEvent(
            event_type=HotplugEventType.DEVICE_REMOVE,
            subsystem="tty",
            kernel=kernel,
        )
        await self.bus.emit(event)

    async def plug_input_device(
        self,
        kernel: str = "event0",
        name: str = "USB Keyboard",
        vendor: int = 0x046D,  # Logitech
        product: int = 0xC31c,
    ):
        """Simulate plugging in an input device."""
        major = 13
        minor = 64 + hash(kernel) % 32

        env = {
            "NAME": name,
            "ID_INPUT_KEYBOARD": "1",
            "ID_VENDOR_ID": f"{vendor:04x}",
            "ID_MODEL_ID": f"{product:04x}",
        }

        event = HotplugEvent(
            event_type=HotplugEventType.DEVICE_ADD,
            subsystem="input",
            kernel=kernel,
            major=major,
            minor=minor,
            env=env,
        )

        self._devices[kernel] = event
        await self.bus.emit(event)
        return event

    async def plug_nvme(self, kernel: str = "nvme0n1", namespace: int = 1):
        """Simulate plugging in an NVMe drive."""
        major = 259
        minor = namespace * 16

        env = {
            "ID_BUS": "nvme",
            "ID_VENDOR": "Samsung",
            "ID_MODEL": "970 EVO Plus",
            "ID_SERIAL": f"S5FENS0N{kernel}",
            "ID_PART_TABLE_TYPE": "gpt",
        }

        event = HotplugEvent(
            event_type=HotplugEventType.DEVICE_ADD,
            subsystem="block",
            kernel=kernel,
            major=major,
            minor=minor,
            env=env,
        )

        self._devices[kernel] = event
        await self.bus.emit(event)
        return event

    def get_plugged_devices(self) -> list[str]:
        """List currently simulated plugged devices."""
        return list(self._devices.keys())
