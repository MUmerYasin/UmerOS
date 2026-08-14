"""
UmerOS /media - Hotplug Event Handling
=======================================

Simulates the Linux kernel's uevent / udev subsystem for removable
media, dispatching connect / disconnect events to registered
handlers.

In a real Linux system the flow is:

    kernel uevent  ->  udevd  ->  udisksd  ->  /media/<user>/<label>

UmerOS condenses this into a single in-process event bus that the
``/media`` subsystem subscribes to.  The bus is deliberately
compatible with the data shape produced by ``pyudev`` so that
existing udev-rule logic can be ported with minimal changes.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

from .media_types import MediaDescriptor, MediaType

log = logging.getLogger("UmerOS.Media.Hotplug")


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

class HotplugAction(str, Enum):
    """The two fundamental hotplug events."""
    ADD    = "add"
    REMOVE = "remove"


@dataclass
class HotplugEvent:
    """A single hotplug event.

    Attributes:
        action:        ``ADD`` or ``REMOVE``.
        device_path:   Kernel device node, e.g. ``/dev/sdb1``.
        media_type:    Best-guess media classification.
        properties:    Arbitrary key-value dict mirroring udev
                       environment variables (``ID_FS_TYPE``,
                       ``ID_FS_LABEL``, ``DEVPATH``, etc.).
        timestamp:     Event creation time (epoch seconds).
    """

    action: HotplugAction
    device_path: str
    media_type: MediaType = MediaType.USB
    properties: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def devname(self) -> str:
        """Short device name, e.g. ``sdb1``."""
        return self.device_path.rsplit("/", 1)[-1]

    @property
    def filesystem(self) -> Optional[str]:
        return self.properties.get("ID_FS_TYPE")

    @property
    def label(self) -> Optional[str]:
        return self.properties.get("ID_FS_LABEL")

    @property
    def uuid(self) -> Optional[str]:
        return self.properties.get("ID_FS_UUID")


# ---------------------------------------------------------------------------
# Handler type
# ---------------------------------------------------------------------------

HotplugHandler = Callable[[HotplugEvent], None]


# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------

class HotplugBus:
    """In-process event bus for hotplug events.

    Handlers register for a specific :class:`MediaType` (or all
    types via ``None``).  When :meth:`emit` is called, every
    matching handler is invoked synchronously in registration order.

    Example::

        bus = HotplugBus()

        def on_usb(evt: HotplugEvent):
            print(f"USB device {evt.devname} connected")

        bus.subscribe(HotplugHandler=on_usb, media_type=MediaType.USB)
        bus.emit(HotplugEvent(action=HotplugAction.ADD, device_path="/dev/sdb1"))
    """

    def __init__(self) -> None:
        # media_type -> list of (handler, priority)
        self._handlers: Dict[Optional[MediaType], List[tuple]] = {}
        self._history: List[HotplugEvent] = []
        self._max_history = 1000

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def subscribe(
        self,
        handler: HotplugHandler,
        media_type: Optional[MediaType] = None,
        priority: int = 100,
    ) -> None:
        """Register *handler* for events of *media_type* (or all types).

        Lower *priority* values fire first.
        """
        bucket = self._handlers.setdefault(media_type, [])
        bucket.append((handler, priority))
        bucket.sort(key=lambda t: t[1])
        log.debug(
            "Subscribed %s for %s (pri=%d)",
            handler.__name__, media_type, priority,
        )

    def unsubscribe(self, handler: HotplugHandler) -> None:
        """Remove *handler* from all buckets."""
        for mt in list(self._handlers):
            self._handlers[mt] = [
                (h, p) for h, p in self._handlers[mt] if h is not handler
            ]

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    def emit(self, event: HotplugEvent) -> int:
        """Dispatch *event* to all matching handlers.

        Returns the number of handlers that were invoked.
        """
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        invoked = 0
        for mt_key, handlers in self._handlers.items():
            if mt_key is not None and mt_key != event.media_type:
                continue
            for handler, _pri in handlers:
                try:
                    handler(event)
                    invoked += 1
                except Exception:
                    log.exception(
                        "Handler %s raised for %s %s",
                        handler.__name__, event.action.value, event.device_path,
                    )
        log.info(
            "Emitted %s %s (%s) -> %d handler(s)",
            event.action.value, event.device_path,
            event.media_type.value, invoked,
        )
        return invoked

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def emit_add(
        self,
        device_path: str,
        media_type: MediaType = MediaType.USB,
        **properties: Any,
    ) -> int:
        """Shorthand for emitting an ``ADD`` event."""
        return self.emit(HotplugEvent(
            action=HotplugAction.ADD,
            device_path=device_path,
            media_type=media_type,
            properties=properties,
        ))

    def emit_remove(self, device_path: str) -> int:
        """Shorthand for emitting a ``REMOVE`` event."""
        return self.emit(HotplugEvent(
            action=HotplugAction.REMOVE,
            device_path=device_path,
        ))

    @property
    def history(self) -> List[HotplugEvent]:
        """Read-only copy of recent events."""
        return list(self._history)


# ---------------------------------------------------------------------------
# Built-in handlers
# ---------------------------------------------------------------------------

def logging_handler(event: HotplugEvent) -> None:
    """Default handler that logs every event."""
    log.info(
        "[hotplug] %s %s type=%s fs=%s label=%s",
        event.action.value,
        event.device_path,
        event.media_type.value,
        event.filesystem or "?",
        event.label or "?",
    )


def _build_default_bus() -> HotplugBus:
    """Create a module-level bus with the logging handler attached."""
    bus = HotplugBus()
    bus.subscribe(logging_handler, priority=9999)
    return bus


# Module-level singleton (lazy)
_default_bus: Optional[HotplugBus] = None


def get_default_bus() -> HotplugBus:
    """Return the module-level :class:`HotplugBus` singleton."""
    global _default_bus
    if _default_bus is None:
        _default_bus = _build_default_bus()
    return _default_bus
