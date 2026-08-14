"""
UmerOS Input Framework
======================
Kernel Input subsystem.
Implements input devices, event reporting (EV_KEY/EV_REL/EV_ABS/EV_SYN),
handlers (evdev, kbd, mouse), grab/exclusive access, and simulated
keyboard, mouse, touchscreen, and gamepad devices.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    from .device import Device
except ImportError:
    Device = None  # type: ignore[assignment,misc]

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bus Types
# ---------------------------------------------------------------------------
BUS_ISA: int = 0x01
BUS_PCI: int = 0x02
BUS_USB: int = 0x03
BUS_HIL: int = 0x04
BUS_BLUETOOTH: int = 0x05
BUS_VIRTUAL: int = 0x06
BUS_PLATFORM: int = 0x10
BUS_I2C: int = 0x18
BUS_SPI: int = 0x1C
BUS_HOST: int = 0x19
BUS_GSC: int = 0x1A
BUS_ISAPNP: int = 0x0501

# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------
EV_SYN: int = 0x00
EV_KEY: int = 0x01
EV_REL: int = 0x02
EV_ABS: int = 0x03
EV_MSC: int = 0x04
EV_SW: int = 0x05
EV_LED: int = 0x11
EV_SND: int = 0x12
EV_REP: int = 0x14
EV_FF: int = 0x15
EV_PWR: int = 0x16
EV_FF_STATUS: int = 0x17

# ---------------------------------------------------------------------------
# Sync Codes
# ---------------------------------------------------------------------------
SYN_REPORT: int = 0x00
SYN_CONFIG: int = 0x01
SYN_MT_REPORT: int = 0x02
SYN_DROPPED: int = 0x03

# ---------------------------------------------------------------------------
# Key Codes
# ---------------------------------------------------------------------------
KEY_RESERVED: int = 0
KEY_ESC: int = 1
KEY_1: int = 2
KEY_2: int = 3
KEY_3: int = 4
KEY_4: int = 5
KEY_5: int = 6
KEY_6: int = 7
KEY_7: int = 8
KEY_8: int = 9
KEY_9: int = 10
KEY_0: int = 11
KEY_MINUS: int = 12
KEY_EQUAL: int = 13
KEY_BACKSPACE: int = 14
KEY_TAB: int = 15
KEY_Q: int = 16
KEY_W: int = 17
KEY_E: int = 18
KEY_R: int = 19
KEY_T: int = 20
KEY_Y: int = 21
KEY_U: int = 22
KEY_I: int = 23
KEY_O: int = 24
KEY_P: int = 25
KEY_LEFTBRACE: int = 26
KEY_RIGHTBRACE: int = 27
KEY_ENTER: int = 28
KEY_LEFTCTRL: int = 29
KEY_A: int = 30
KEY_S: int = 31
KEY_D: int = 32
KEY_F: int = 33
KEY_G: int = 34
KEY_H: int = 35
KEY_J: int = 36
KEY_K: int = 37
KEY_L: int = 38
KEY_SEMICOLON: int = 39
KEY_APOSTROPHE: int = 40
KEY_GRAVE: int = 41
KEY_LEFTSHIFT: int = 42
KEY_BACKSLASH: int = 43
KEY_Z: int = 44
KEY_X: int = 45
KEY_C: int = 46
KEY_V: int = 47
KEY_B: int = 48
KEY_N: int = 49
KEY_M: int = 50
KEY_COMMA: int = 51
KEY_DOT: int = 52
KEY_SLASH: int = 53
KEY_RIGHTSHIFT: int = 54
KEY_KPASTERISK: int = 55
KEY_LEFTALT: int = 56
KEY_SPACE: int = 57
KEY_CAPSLOCK: int = 58
KEY_F1: int = 59
KEY_F2: int = 60
KEY_F3: int = 61
KEY_F4: int = 62
KEY_F5: int = 63
KEY_F6: int = 64
KEY_F7: int = 65
KEY_F8: int = 66
KEY_F9: int = 67
KEY_F10: int = 68
KEY_NUMLOCK: int = 69
KEY_SCROLLLOCK: int = 70
KEY_F11: int = 87
KEY_F12: int = 88
KEY_ENTER2: int = 96
KEY_RIGHTCTRL: int = 97
KEY_KPSLASH: int = 98
KEY_RIGHTALT: int = 100
KEY_HOME: int = 102
KEY_UP: int = 103
KEY_PAGEUP: int = 104
KEY_LEFT: int = 105
KEY_RIGHT: int = 106
KEY_END: int = 107
KEY_DOWN: int = 108
KEY_PAGEDOWN: int = 109
KEY_INSERT: int = 110
KEY_DELETE: int = 111
KEY_LEFTMETA: int = 125
KEY_RIGHTMETA: int = 126

# ---------------------------------------------------------------------------
# Relative Axes
# ---------------------------------------------------------------------------
REL_X: int = 0x00
REL_Y: int = 0x01
REL_Z: int = 0x02
REL_RX: int = 0x03
REL_RY: int = 0x04
REL_RZ: int = 0x05
REL_HWHEEL: int = 0x06
REL_DIAL: int = 0x07
REL_WHEEL: int = 0x08
REL_MISC: int = 0x09

# ---------------------------------------------------------------------------
# Absolute Axes
# ---------------------------------------------------------------------------
ABS_X: int = 0x00
ABS_Y: int = 0x01
ABS_Z: int = 0x02
ABS_RX: int = 0x03
ABS_RY: int = 0x04
ABS_RZ: int = 0x05
ABS_HAT0X: int = 0x10
ABS_HAT0Y: int = 0x11
ABS_HAT1X: int = 0x12
ABS_HAT1Y: int = 0x13
ABS_HAT2X: int = 0x14
ABS_HAT2Y: int = 0x15
ABS_HAT3X: int = 0x16
ABS_HAT3Y: int = 0x17
ABS_PRESSURE: int = 0x18
ABS_DISTANCE: int = 0x19
ABS_TILT_X: int = 0x1A
ABS_TILT_Y: int = 0x1B
ABS_TOOL_WIDTH: int = 0x1C
ABS_VOLUME: int = 0x20
ABS_MISC: int = 0x28
ABS_MT_SLOT: int = 0x2F
ABS_MT_TOUCH_MAJOR: int = 0x30
ABS_MT_TOUCH_MINOR: int = 0x31
ABS_MT_WIDTH_MAJOR: int = 0x32
ABS_MT_WIDTH_MINOR: int = 0x33
ABS_MT_ORIENTATION: int = 0x34
ABS_MT_POSITION_X: int = 0x35
ABS_MT_POSITION_Y: int = 0x36
ABS_MT_TOOL_TYPE: int = 0x37
ABS_MT_BLOB_ID: int = 0x38
ABS_MT_TRACKING_ID: int = 0x39
ABS_MT_PRESSURE: int = 0x3A
ABS_MT_DISTANCE: int = 0x3B
ABS_MT_TOOL_X: int = 0x3C
ABS_MT_TOOL_Y: int = 0x3D

# ---------------------------------------------------------------------------
# LED Codes
# ---------------------------------------------------------------------------
LED_NUML: int = 0x00
LED_CAPSL: int = 0x01
LED_SCROLLL: int = 0x02
LED_COMPOSE: int = 0x03
LED_KANA: int = 0x04
LED_SLEEP: int = 0x05
LED_SUSPEND: int = 0x06
LED_MUTE: int = 0x07
LED_MISC: int = 0x08
LED_MAIL: int = 0x09
LED_CHARGING: int = 0x0A

# ---------------------------------------------------------------------------
# Switch Codes
# ---------------------------------------------------------------------------
SW_LID: int = 0x00
SW_TABLET_MODE: int = 0x01
SW_HEADPHONE_INSERT: int = 0x02
SW_RFKILL_ALL: int = 0x03
SW_MICROPHONE_INSERT: int = 0x04
SW_DOCK: int = 0x05
SW_LINEOUT_INSERT: int = 0x06
SW_JACK_PHYSICAL_INSERT: int = 0x07
SW_VIDEOOUT_INSERT: int = 0x08
SW_CAMERA_LENS_COVER: int = 0x09
SW_KEYPAD_SLIDE: int = 0x0A
SW_FRONT_PROXIMITY: int = 0x0B
SW_ROTATE_LOCK: int = 0x0C
SW_LINEIN_INSERT: int = 0x0D

# ---------------------------------------------------------------------------
# Misc Codes
# ---------------------------------------------------------------------------
MSC_SCANCODE: int = 0x00
MSC_SERIAL: int = 0x01
MSC_PULSELED: int = 0x02
MSC_GESTURE: int = 0x03
MSC_RAW: int = 0x04
MSC_SCAN: int = 0x05
MSC_TIMESTAMP: int = 0x06

# ---------------------------------------------------------------------------
# Rep (Repeat) Codes
# ---------------------------------------------------------------------------
REP_DELAY: int = 0x00
REP_PERIOD: int = 0x01


# ---------------------------------------------------------------------------
# Core Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class InputDev:
    """Input device"""
    name: str
    phys: str = ""
    driver_name: str = ""
    bus: int = BUS_USB
    vendor: int = 0x0000
    product: int = 0x0000
    version: int = 0x0100
    evbit: int = 0
    keybit: int = 0
    relbit: int = 0
    absbit: int = 0
    swbit: int = 0
    ledbit: int = 0
    ffbit: int = 0
    mscbit: int = 0
    is_registered: bool = False
    is_open: bool = False
    _grab: str = ""
    _event_queue: list = field(default_factory=list)
    _abs_info: dict = field(default_factory=dict)
    _repeat_key: int = 0
    _repeat_period_ms: int = 250
    _repeat_delay_ms: int = 500
    _led_state: dict = field(default_factory=dict)
    _driver_data: Any = None

    def __repr__(self) -> str:
        return (
            f"InputDev(name={self.name!r}, bus=0x{self.bus:02x}, "
            f"vendor=0x{self.vendor:04x}, product=0x{self.product:04x})"
        )


@dataclass
class InputEvent:
    """Input event"""
    timestamp: float
    event_type: int
    code: int
    value: int

    def __repr__(self) -> str:
        type_names = {
            EV_SYN: "EV_SYN", EV_KEY: "EV_KEY", EV_REL: "EV_REL",
            EV_ABS: "EV_ABS", EV_MSC: "EV_MSC", EV_SW: "EV_SW",
            EV_LED: "EV_LED", EV_SND: "EV_SND", EV_REP: "EV_REP",
        }
        tname = type_names.get(self.event_type, f"0x{self.event_type:02x}")
        return f"InputEvent(t={tname}, code=0x{self.code:04x}, val={self.value})"


@dataclass
class InputAbsinfo:
    """Absolute axis info"""
    value: int = 0
    minimum: int = 0
    maximum: int = 255
    fuzz: int = 0
    flat: int = 0
    resolution: int = 0

    def __repr__(self) -> str:
        return (
            f"InputAbsinfo(val={self.value}, min={self.minimum}, "
            f"max={self.maximum}, fuzz={self.fuzz}, flat={self.flat})"
        )


@dataclass
class InputHandler:
    """Input handler (event processor)"""
    name: str
    id_table: list = field(default_factory=list)
    connect: object = None
    disconnect: object = None
    events: object = None
    is_registered: bool = False

    def __repr__(self) -> str:
        return f"InputHandler(name={self.name!r}, registered={self.is_registered})"


@dataclass
class InputHandle:
    """Handle connecting handler to device"""
    handler_name: str
    device_name: str
    minor: int = 0
    is_open: bool = False

    def __repr__(self) -> str:
        return (
            f"InputHandle(handler={self.handler_name!r}, "
            f"device={self.device_name!r}, minor={self.minor})"
        )


# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_devices: Dict[str, InputDev] = {}
_handlers: Dict[str, InputHandler] = {}
_handles: List[InputHandle] = []
_minor_counter: int = 0
_event_log: List[InputEvent] = []


# ---------------------------------------------------------------------------
# Device Management
# ---------------------------------------------------------------------------
def input_allocate_device() -> InputDev:
    """Allocate input device - like input_allocate_device()"""
    dev = InputDev(name="")
    log.debug("input_allocate_device: allocated %r", dev)
    return dev


def input_free_device(device_name: str) -> None:
    """Free input device"""
    if device_name in _devices:
        del _devices[device_name]
        log.debug("input_free_device: freed %s", device_name)
    else:
        log.warning("input_free_device: device %s not found", device_name)


def input_register_device(device_name: str) -> int:
    """Register input device - like input_register_device(). Returns minor."""
    global _minor_counter
    if device_name not in _devices:
        log.error("input_register_device: device %s not allocated", device_name)
        return -1
    dev = _devices[device_name]
    if dev.is_registered:
        log.warning("input_register_device: device %s already registered", device_name)
        return _get_device_minor(device_name)
    dev.is_registered = True
    minor = _minor_counter
    _minor_counter += 1
    _handles.append(InputHandle(handler_name="", device_name=device_name, minor=minor))
    log.info("input_register_device: %s registered as minor %d", device_name, minor)

    for handler in _handlers.values():
        if handler.is_registered and handler.connect is not None:
            handler.connect(dev)

    return minor


def input_unregister_device(device_name: str) -> None:
    """Unregister input device"""
    if device_name not in _devices:
        return
    dev = _devices[device_name]
    if not dev.is_registered:
        return
    dev.is_registered = False
    _handles[:] = [h for h in _handles if h.device_name != device_name]
    log.info("input_unregister_device: %s unregistered", device_name)


def input_get_device(device_name: str) -> Optional[InputDev]:
    """Get input device"""
    return _devices.get(device_name)


def _get_device_minor(device_name: str) -> int:
    """Get minor number for a device."""
    for h in _handles:
        if h.device_name == device_name:
            return h.minor
    return -1


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------
def input_set_capability(device_name: str, event_type: int, code: int) -> None:
    """Set device capability"""
    dev = _devices.get(device_name)
    if dev is None:
        log.error("input_set_capability: device %s not found", device_name)
        return
    dev.evbit |= (1 << event_type)
    if event_type == EV_KEY and code < 64:
        dev.keybit |= (1 << code)
    elif event_type == EV_REL:
        dev.relbit |= (1 << code)
    elif event_type == EV_ABS:
        dev.absbit |= (1 << code)
    elif event_type == EV_SW:
        dev.swbit |= (1 << code)
    elif event_type == EV_LED:
        dev.ledbit |= (1 << code)
    elif event_type == EV_FF:
        dev.ffbit |= (1 << code)
    elif event_type == EV_MSC:
        dev.mscbit |= (1 << code)
    log.debug(
        "input_set_capability: %s type=%d code=%d",
        device_name, event_type, code,
    )


def input_set_abs_params(
    device_name: str,
    axis: int,
    min_val: int,
    max_val: int,
    fuzz: int = 0,
    flat: int = 0,
) -> None:
    """Set absolute axis parameters"""
    dev = _devices.get(device_name)
    if dev is None:
        log.error("input_set_abs_params: device %s not found", device_name)
        return
    input_set_capability(device_name, EV_ABS, axis)
    dev._abs_info[axis] = InputAbsinfo(
        minimum=min_val,
        maximum=max_val,
        fuzz=fuzz,
        flat=flat,
    )
    log.debug(
        "input_set_abs_params: %s axis=%d min=%d max=%d fuzz=%d flat=%d",
        device_name, axis, min_val, max_val, fuzz, flat,
    )


def input_set_drvdata(device_name: str, data: Any) -> None:
    """Set driver private data"""
    dev = _devices.get(device_name)
    if dev is not None:
        dev._driver_data = data


def input_get_drvdata(device_name: str) -> Any:
    """Get driver private data"""
    dev = _devices.get(device_name)
    if dev is not None:
        return dev._driver_data
    return None


# ---------------------------------------------------------------------------
# Event Reporting
# ---------------------------------------------------------------------------
def input_report_key(device_name: str, code: int, value: int) -> None:
    """Report key event - like input_report_key()"""
    input_event(device_name, EV_KEY, code, value)


def input_report_rel(device_name: str, code: int, value: int) -> None:
    """Report relative axis event"""
    input_event(device_name, EV_REL, code, value)


def input_report_abs(device_name: str, code: int, value: int) -> None:
    """Report absolute axis event"""
    dev = _devices.get(device_name)
    if dev is not None and code in dev._abs_info:
        info = dev._abs_info[code]
        value = max(info.minimum, min(info.maximum, value))
    input_event(device_name, EV_ABS, code, value)


def input_report_switch(device_name: str, code: int, value: int) -> None:
    """Report switch event"""
    input_event(device_name, EV_SW, code, value)


def input_report_led(device_name: str, code: int, value: int) -> None:
    """Report LED event"""
    input_event(device_name, EV_LED, code, value)


def input_report_msc(device_name: str, code: int, value: int) -> None:
    """Report misc event"""
    input_event(device_name, EV_MSC, code, value)


def input_sync(device_name: str) -> None:
    """Sync events - like input_sync()"""
    input_event(device_name, EV_SYN, SYN_REPORT, 0)


def input_event(device_name: str, event_type: int, code: int, value: int) -> None:
    """Report generic event"""
    dev = _devices.get(device_name)
    if dev is None:
        log.error("input_event: device %s not found", device_name)
        return
    if not dev.is_registered:
        log.warning("input_event: device %s not registered", device_name)
        return
    ts = time.time()
    evt = InputEvent(timestamp=ts, event_type=event_type, code=code, value=value)
    dev._event_queue.append(evt)
    _event_log.append(evt)
    log.debug("input_event: %s %r", device_name, evt)


def input_pass_event(
    handler_name: str, device_name: str, event_type: int, code: int, value: int,
) -> None:
    """Pass event through handler"""
    handler = _handlers.get(handler_name)
    if handler is None or not handler.is_registered:
        log.error("input_pass_event: handler %s not found", handler_name)
        return
    dev = _devices.get(device_name)
    if dev is None or not dev.is_registered:
        log.error("input_pass_event: device %s not found", device_name)
        return
    if handler.events is not None and callable(handler.events):
        handler.events(dev, InputEvent(
            timestamp=time.time(),
            event_type=event_type,
            code=code,
            value=value,
        ))
    input_event(device_name, event_type, code, value)


# ---------------------------------------------------------------------------
# Grab / Exclusive Access
# ---------------------------------------------------------------------------
def input_grab_device(device_name: str, handler_name: str) -> bool:
    """Grab device exclusively"""
    dev = _devices.get(device_name)
    if dev is None:
        log.error("input_grab_device: device %s not found", device_name)
        return False
    if dev._grab:
        log.warning(
            "input_grab_device: device %s already grabbed by %s",
            device_name, dev._grab,
        )
        return False
    dev._grab = handler_name
    log.info("input_grab_device: %s grabbed by %s", device_name, handler_name)
    return True


def input_release_device(device_name: str) -> None:
    """Release grabbed device"""
    dev = _devices.get(device_name)
    if dev is not None:
        dev._grab = ""
        log.info("input_release_device: %s released", device_name)


# ---------------------------------------------------------------------------
# Repeat
# ---------------------------------------------------------------------------
def input_set_repeat_params(device_name: str, delay_ms: int, period_ms: int) -> None:
    """Set key repeat parameters"""
    dev = _devices.get(device_name)
    if dev is None:
        log.error("input_set_repeat_params: device %s not found", device_name)
        return
    dev._repeat_delay_ms = delay_ms
    dev._repeat_period_ms = period_ms
    log.debug(
        "input_set_repeat_params: %s delay=%dms period=%dms",
        device_name, delay_ms, period_ms,
    )


# ---------------------------------------------------------------------------
# LEDs
# ---------------------------------------------------------------------------
def input_set_ledstate(device_name: str, led_code: int, on: bool) -> None:
    """Set LED state"""
    dev = _devices.get(device_name)
    if dev is None:
        log.error("input_set_ledstate: device %s not found", device_name)
        return
    dev._led_state[led_code] = on
    value = 1 if on else 0
    input_report_led(device_name, led_code, value)
    log.debug(
        "input_set_ledstate: %s LED=%d on=%s",
        device_name, led_code, on,
    )


# ---------------------------------------------------------------------------
# Sysfs-like Accessors
# ---------------------------------------------------------------------------
def input_get_name(device_name: str) -> str:
    """Get device name"""
    dev = _devices.get(device_name)
    return dev.name if dev is not None else ""


def input_get_phys(device_name: str) -> str:
    """Get device physical path"""
    dev = _devices.get(device_name)
    return dev.phys if dev is not None else ""


def input_get_handler_list() -> List[str]:
    """List registered handlers"""
    return [n for n, h in _handlers.items() if h.is_registered]


def input_get_device_list() -> List[str]:
    """List registered devices"""
    return [n for n, d in _devices.items() if d.is_registered]


def input_get_event_log() -> List[InputEvent]:
    """Get the global event log"""
    return list(_event_log)


# ---------------------------------------------------------------------------
# Handler Registration
# ---------------------------------------------------------------------------
def input_register_handler(handler: InputHandler) -> None:
    """Register an input handler"""
    if handler.name in _handlers:
        log.warning("input_register_handler: %s already registered", handler.name)
        return
    handler.is_registered = True
    _handlers[handler.name] = handler
    log.info("input_register_handler: %s", handler.name)

    for dev in _devices.values():
        if dev.is_registered and handler.connect is not None:
            handler.connect(dev)


def input_unregister_handler(handler_name: str) -> None:
    """Unregister an input handler"""
    if handler_name not in _handlers:
        return
    handler = _handlers[handler_name]
    if not handler.is_registered:
        return
    handler.is_registered = False
    _handles[:] = [h for h in _handles if h.handler_name != handler_name]
    log.info("input_unregister_handler: %s", handler_name)


# ---------------------------------------------------------------------------
# Built-in Handlers
# ---------------------------------------------------------------------------
class EvdevHandler:
    """evdev handler - passes events to userspace"""

    def __init__(self) -> None:
        self.name: str = "evdev"
        self._handler = InputHandler(name=self.name)

    def register(self) -> None:
        """Register the evdev handler."""
        self._handler.connect = self._connect
        self._handler.disconnect = self._disconnect
        self._handler.events = self._events
        input_register_handler(self._handler)

    def unregister(self) -> None:
        """Unregister the evdev handler."""
        input_unregister_handler(self.name)

    @staticmethod
    def _connect(dev: InputDev) -> None:
        log.debug("evdev: connected to %s", dev.name)

    @staticmethod
    def _disconnect(dev: InputDev) -> None:
        log.debug("evdev: disconnected from %s", dev.name)

    @staticmethod
    def _events(dev: InputDev, evt: InputEvent) -> None:
        log.debug("evdev: %s -> %r", dev.name, evt)

    def __repr__(self) -> str:
        return f"EvdevHandler(name={self.name!r})"


class KbdHandler:
    """Keyboard handler - translates key codes"""

    def __init__(self) -> None:
        self.name: str = "kbd"
        self._handler = InputHandler(name=self.name)

    def register(self) -> None:
        """Register the kbd handler."""
        self._handler.connect = self._connect
        self._handler.events = self._events
        input_register_handler(self._handler)

    def unregister(self) -> None:
        """Unregister the kbd handler."""
        input_unregister_handler(self.name)

    @staticmethod
    def _connect(dev: InputDev) -> None:
        log.debug("kbd: connected to %s", dev.name)

    @staticmethod
    def _events(dev: InputDev, evt: InputEvent) -> None:
        if evt.event_type == EV_KEY and evt.value == 1:
            log.debug("kbd: key press code=0x%02x on %s", evt.code, dev.name)

    def __repr__(self) -> str:
        return f"KbdHandler(name={self.name!r})"


class MouseHandler:
    """Mouse handler - relative axis events"""

    def __init__(self) -> None:
        self.name: str = "mouse"
        self._handler = InputHandler(name=self.name)

    def register(self) -> None:
        """Register the mouse handler."""
        self._handler.connect = self._connect
        self._handler.events = self._events
        input_register_handler(self._handler)

    def unregister(self) -> None:
        """Unregister the mouse handler."""
        input_unregister_handler(self.name)

    @staticmethod
    def _connect(dev: InputDev) -> None:
        log.debug("mouse: connected to %s", dev.name)

    @staticmethod
    def _events(dev: InputDev, evt: InputEvent) -> None:
        if evt.event_type == EV_REL:
            axis = {REL_X: "X", REL_Y: "Y", REL_WHEEL: "Wheel"}.get(evt.code, f"0x{evt.code:02x}")
            log.debug("mouse: %s axis=%s delta=%d", dev.name, axis, evt.value)

    def __repr__(self) -> str:
        return f"MouseHandler(name={self.name!r})"


# ---------------------------------------------------------------------------
# Built-in Devices
# ---------------------------------------------------------------------------
class SimKeyboard:
    """Simulated keyboard (USB HID)"""

    def __init__(self, name: str = "sim-keyboard") -> None:
        self.name = name
        dev = InputDev(
            name=name,
            phys=f"usb-0000:00:14.0-1/input0",
            driver_name="sim-kbd",
            bus=BUS_USB,
            vendor=0x046D,  # Logitech
            product=0xC31C,  # K120
            version=0x0111,
        )
        _devices[name] = dev

        for code in (
            KEY_ESC, KEY_F1, KEY_F2, KEY_F3, KEY_F4, KEY_F5, KEY_F6,
            KEY_F7, KEY_F8, KEY_F9, KEY_F10, KEY_F11, KEY_F12,
            KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9, KEY_0,
            KEY_Q, KEY_W, KEY_E, KEY_R, KEY_T, KEY_Y, KEY_U, KEY_I, KEY_O, KEY_P,
            KEY_A, KEY_S, KEY_D, KEY_F, KEY_G, KEY_H, KEY_J, KEY_K, KEY_L,
            KEY_Z, KEY_X, KEY_C, KEY_V, KEY_B, KEY_N, KEY_M,
            KEY_SPACE, KEY_ENTER, KEY_BACKSPACE, KEY_TAB,
            KEY_LEFTSHIFT, KEY_RIGHTSHIFT, KEY_LEFTCTRL, KEY_RIGHTCTRL,
            KEY_LEFTALT, KEY_RIGHTALT,
            KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
            KEY_HOME, KEY_END, KEY_PAGEUP, KEY_PAGEDOWN,
            KEY_INSERT, KEY_DELETE,
        ):
            input_set_capability(name, EV_KEY, code)

        input_set_capability(name, EV_LED, LED_NUML)
        input_set_capability(name, EV_LED, LED_CAPSL)
        input_set_capability(name, EV_LED, LED_SCROLLL)
        input_set_capability(name, EV_REP, REP_DELAY)
        input_set_capability(name, EV_REP, REP_PERIOD)

        log.info("SimKeyboard: created %s", name)

    def press(self, code: int) -> None:
        """Press a key."""
        input_report_key(self.name, code, 1)
        input_sync(self.name)

    def release(self, code: int) -> None:
        """Release a key."""
        input_report_key(self.name, code, 0)
        input_sync(self.name)

    def tap(self, code: int) -> None:
        """Press and release a key."""
        self.press(code)
        self.release(code)

    def __repr__(self) -> str:
        return f"SimKeyboard(name={self.name!r})"


class SimMouse:
    """Simulated mouse (USB HID)"""

    def __init__(self, name: str = "sim-mouse") -> None:
        self.name = name
        self._x: int = 0
        self._y: int = 0
        self._buttons: Dict[int, bool] = {0: False, 1: False, 2: False}
        dev = InputDev(
            name=name,
            phys="usb-0000:00:14.0-2/input0",
            driver_name="sim-mouse",
            bus=BUS_USB,
            vendor=0x046D,
            product=0xC077,  # M100
            version=0x0111,
        )
        _devices[name] = dev

        input_set_capability(name, EV_KEY, 0x110)  # BTN_LEFT
        input_set_capability(name, EV_KEY, 0x111)  # BTN_RIGHT
        input_set_capability(name, EV_KEY, 0x112)  # BTN_MIDDLE
        input_set_capability(name, EV_REL, REL_X)
        input_set_capability(name, EV_REL, REL_Y)
        input_set_capability(name, EV_REL, REL_WHEEL)
        input_set_capability(name, EV_REL, REL_HWHEEL)

        log.info("SimMouse: created %s", name)

    def move(self, dx: int, dy: int) -> None:
        """Move the mouse by (dx, dy) pixels."""
        self._x += dx
        self._y += dy
        if dx != 0:
            input_report_rel(self.name, REL_X, dx)
        if dy != 0:
            input_report_rel(self.name, REL_Y, dy)
        input_sync(self.name)

    def scroll(self, amount: int) -> None:
        """Scroll the mouse wheel."""
        input_report_rel(self.name, REL_WHEEL, amount)
        input_sync(self.name)

    def click(self, button: int = 0) -> None:
        """Click a mouse button (0=left, 1=right, 2=middle)."""
        btn_code = 0x110 + button
        self._buttons[button] = True
        input_report_key(self.name, btn_code, 1)
        input_sync(self.name)

    def release_button(self, button: int = 0) -> None:
        """Release a mouse button."""
        btn_code = 0x110 + button
        self._buttons[button] = False
        input_report_key(self.name, btn_code, 0)
        input_sync(self.name)

    def position(self) -> tuple:
        """Return current cursor position."""
        return (self._x, self._y)

    def __repr__(self) -> str:
        return f"SimMouse(name={self.name!r}, pos={self.position()})"


class SimTouchscreen:
    """Simulated touchscreen"""

    def __init__(self, name: str = "sim-touchscreen", width: int = 1024, height: int = 600) -> None:
        self.name = name
        self.width = width
        self.height = height
        dev = InputDev(
            name=name,
            phys="virtual-touchscreen",
            driver_name="sim-ts",
            bus=BUS_VIRTUAL,
            vendor=0x0000,
            product=0x0000,
            version=0x0100,
        )
        _devices[name] = dev

        input_set_abs_params(name, ABS_X, 0, width, fuzz=2, flat=4)
        input_set_abs_params(name, ABS_Y, 0, height, fuzz=2, flat=4)
        input_set_abs_params(name, ABS_PRESSURE, 0, 255, fuzz=0, flat=0)
        input_set_abs_params(name, ABS_MT_SLOT, 0, 9, 0, 0)
        input_set_abs_params(name, ABS_MT_TRACKING_ID, 0, 65535, 0, 0)
        input_set_abs_params(name, ABS_MT_POSITION_X, 0, width, fuzz=2, flat=4)
        input_set_abs_params(name, ABS_MT_POSITION_Y, 0, height, fuzz=2, flat=4)
        input_set_abs_params(name, ABS_MT_TOUCH_MAJOR, 0, 255, 0, 0)
        input_set_abs_params(name, ABS_MT_WIDTH_MAJOR, 0, 255, 0, 0)

        input_set_capability(name, EV_KEY, 330)  # BTN_TOUCH

        log.info("SimTouchscreen: created %s (%dx%d)", name, width, height)

    def touch(self, x: int, y: int) -> None:
        """Simulate a single tap at (x, y)."""
        x = max(0, min(self.width, x))
        y = max(0, min(self.height, y))

        input_event(self.name, EV_ABS, ABS_MT_SLOT, 0)
        input_event(self.name, EV_ABS, ABS_MT_TRACKING_ID, 0)
        input_event(self.name, EV_ABS, ABS_MT_POSITION_X, x)
        input_event(self.name, EV_ABS, ABS_MT_POSITION_Y, y)
        input_event(self.name, EV_ABS, ABS_MT_TOUCH_MAJOR, 40)
        input_event(self.name, EV_ABS, ABS_MT_WIDTH_MAJOR, 50)
        input_event(self.name, EV_KEY, 330, 1)
        input_event(self.name, EV_ABS, ABS_PRESSURE, 200)
        input_event(self.name, EV_ABS, ABS_X, x)
        input_event(self.name, EV_ABS, ABS_Y, y)
        input_sync(self.name)

    def release(self) -> None:
        """Release touch."""
        input_event(self.name, EV_ABS, ABS_MT_SLOT, 0)
        input_event(self.name, EV_ABS, ABS_MT_TRACKING_ID, -1)
        input_event(self.name, EV_KEY, 330, 0)
        input_event(self.name, EV_ABS, ABS_PRESSURE, 0)
        input_sync(self.name)

    def drag(self, x1: int, y1: int, x2: int, y2: int, steps: int = 5) -> None:
        """Simulate a drag from (x1,y1) to (x2,y2)."""
        self.touch(x1, y1)
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(x1 + (x2 - x1) * t)
            cy = int(y1 + (y2 - y1) * t)
            input_event(self.name, EV_ABS, ABS_MT_SLOT, 0)
            input_event(self.name, EV_ABS, ABS_MT_POSITION_X, cx)
            input_event(self.name, EV_ABS, ABS_MT_POSITION_Y, cy)
            input_event(self.name, EV_ABS, ABS_X, cx)
            input_event(self.name, EV_ABS, ABS_Y, cy)
            input_sync(self.name)
        self.release()

    def __repr__(self) -> str:
        return f"SimTouchscreen(name={self.name!r}, {self.width}x{self.height})"


class SimGamepad:
    """Simulated gamepad with D-pad, buttons, analog sticks"""

    def __init__(self, name: str = "sim-gamepad") -> None:
        self.name = name
        dev = InputDev(
            name=name,
            phys="virtual-gamepad",
            driver_name="sim-gp",
            bus=BUS_VIRTUAL,
            vendor=0x045E,  # Microsoft
            product=0x028E,  # Xbox 360
            version=0x0110,
        )
        _devices[name] = dev

        # Axes
        input_set_abs_params(name, ABS_X, -32768, 32767, fuzz=16, flat=128)
        input_set_abs_params(name, ABS_Y, -32768, 32767, fuzz=16, flat=128)
        input_set_abs_params(name, ABS_Z, 0, 255, 0, 0)
        input_set_abs_params(name, ABS_RX, -32768, 32767, fuzz=16, flat=128)
        input_set_abs_params(name, ABS_RY, -32768, 32767, fuzz=16, flat=128)
        input_set_abs_params(name, ABS_RZ, 0, 255, 0, 0)
        input_set_abs_params(name, ABS_HAT0X, -1, 1, 0, 0)
        input_set_abs_params(name, ABS_HAT0Y, -1, 1, 0, 0)

        # Face buttons (BTN_SOUTH..BTN_NORTH = 0x130..0x133)
        for btn in (0x130, 0x131, 0x132, 0x133):
            input_set_capability(name, EV_KEY, btn)

        # Triggers and bumpers (BTN_TL=0x136, BTN_TR=0x137)
        for btn in (0x134, 0x135, 0x136, 0x137):
            input_set_capability(name, EV_KEY, btn)

        # Thumb buttons (BTN_THUMBL=0x13D, BTN_THUMBR=0x13E)
        for btn in (0x13D, 0x13E):
            input_set_capability(name, EV_KEY, btn)

        log.info("SimGamepad: created %s", name)

    def dpad(self, x: int, y: int) -> None:
        """Set D-pad position (-1/0/1 for each axis)."""
        input_report_abs(self.name, ABS_HAT0X, max(-1, min(1, x)))
        input_report_abs(self.name, ABS_HAT0Y, max(-1, min(1, y)))
        input_sync(self.name)

    def left_stick(self, x: int, y: int) -> None:
        """Set left analog stick (-32768..32767)."""
        input_report_abs(self.name, ABS_X, max(-32768, min(32767, x)))
        input_report_abs(self.name, ABS_Y, max(-32768, min(32767, y)))
        input_sync(self.name)

    def right_stick(self, x: int, y: int) -> None:
        """Set right analog stick (-32768..32767)."""
        input_report_abs(self.name, ABS_RX, max(-32768, min(32767, x)))
        input_report_abs(self.name, ABS_RY, max(-32768, min(32767, y)))
        input_sync(self.name)

    def press_button(self, btn_code: int) -> None:
        """Press a button."""
        input_report_key(self.name, btn_code, 1)
        input_sync(self.name)

    def release_button(self, btn_code: int) -> None:
        """Release a button."""
        input_report_key(self.name, btn_code, 0)
        input_sync(self.name)

    def left_trigger(self, value: int) -> None:
        """Set left trigger (0..255)."""
        input_report_abs(self.name, ABS_Z, max(0, min(255, value)))
        input_sync(self.name)

    def right_trigger(self, value: int) -> None:
        """Set right trigger (0..255)."""
        input_report_abs(self.name, ABS_RZ, max(0, min(255, value)))
        input_sync(self.name)

    def __repr__(self) -> str:
        return f"SimGamepad(name={self.name!r})"


# ---------------------------------------------------------------------------
# Dump / Debug
# ---------------------------------------------------------------------------
def input_dump_state() -> None:
    """Print the full input subsystem state."""
    print("=" * 60)
    print("  UmerOS Input Subsystem State")
    print("=" * 60)

    print("\n--- Devices ---")
    if not _devices:
        print("  (none)")
    for name, dev in _devices.items():
        minor = _get_device_minor(name)
        grab = f" [grabbed by {dev._grab}]" if dev._grab else ""
        leds = ""
        if dev._led_state:
            leds = " LEDs=" + ",".join(
                f"{k}={'on' if v else 'off'}" for k, v in dev._led_state.items()
            )
        print(
            f"  [{minor:2d}] {dev.name}: bus=0x{dev.bus:02x} "
            f"vendor=0x{dev.vendor:04x} product=0x{dev.product:04x} "
            f"registered={dev.is_registered}{grab}{leds}"
        )
        caps = []
        if dev.evbit & (1 << EV_KEY):
            keys = [f"0x{i:02x}" for i in range(64) if dev.keybit & (1 << i)]
            if keys:
                caps.append(f"KEY[{','.join(keys)}]")
        if dev.evbit & (1 << EV_REL):
            rels = [f"0x{i:02x}" for i in range(10) if dev.relbit & (1 << i)]
            if rels:
                caps.append(f"REL[{','.join(rels)}]")
        if dev.evbit & (1 << EV_ABS):
            abss = [f"0x{i:02x}" for i in range(64) if dev.absbit & (1 << i)]
            if abss:
                caps.append(f"ABS[{','.join(abss)}]")
        if dev.evbit & (1 << EV_LED):
            caps.append("LED")
        if dev.evbit & (1 << EV_REP):
            caps.append("REP")
        if dev.evbit & (1 << EV_SW):
            caps.append("SW")
        if dev.evbit & (1 << EV_MSC):
            caps.append("MSC")
        if caps:
            print(f"       caps: {' '.join(caps)}")
        if dev._abs_info:
            print(f"       absinfo: {dev._abs_info}")
        if dev._event_queue:
            print(f"       events ({len(dev._event_queue)}):")
            for evt in dev._event_queue[-5:]:
                print(f"         {evt}")
            if len(dev._event_queue) > 5:
                print(f"         ... ({len(dev._event_queue) - 5} more)")

    print("\n--- Handlers ---")
    if not _handlers:
        print("  (none)")
    for name, handler in _handlers.items():
        print(f"  {handler}")

    print("\n--- Handles ---")
    if not _handles:
        print("  (none)")
    for h in _handles:
        print(f"  {h}")

    print("\n--- Event Log (last 10) ---")
    recent = _event_log[-10:] if _event_log else []
    if not recent:
        print("  (none)")
    for evt in recent:
        print(f"  {evt}")

    print("=" * 60)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def demo() -> None:
    print("=" * 60)
    print("  UmerOS Input Framework Demo")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Create simulated devices
    # ------------------------------------------------------------------
    print("\n--- Creating Simulated Devices ---")
    kbd = SimKeyboard(name="sim-keyboard")
    mouse = SimMouse(name="sim-mouse")
    ts = SimTouchscreen(name="sim-touchscreen", width=1024, height=600)
    gp = SimGamepad(name="sim-gamepad")
    print(f"  {kbd}")
    print(f"  {mouse}")
    print(f"  {ts}")
    print(f"  {gp}")

    # ------------------------------------------------------------------
    # 2. Register devices
    # ------------------------------------------------------------------
    print("\n--- Registering Devices ---")
    input_register_device("sim-keyboard")
    input_register_device("sim-mouse")
    input_register_device("sim-touchscreen")
    input_register_device("sim-gamepad")

    # ------------------------------------------------------------------
    # 3. Register handlers (evdev)
    # ------------------------------------------------------------------
    print("\n--- Registering Handlers ---")
    evdev = EvdevHandler()
    evdev.register()
    kbd_handler = KbdHandler()
    kbd_handler.register()
    mouse_h = MouseHandler()
    mouse_h.register()

    # ------------------------------------------------------------------
    # 4. Simulate keyboard input
    # ------------------------------------------------------------------
    print("\n--- Simulating Keyboard Input ---")
    kbd.tap(KEY_ESC)
    print(f"  Tapped ESC")

    kbd.tap(KEY_A)
    kbd.tap(KEY_S)
    kbd.tap(KEY_D)
    print(f"  Tapped A, S, D")

    kbd.press(KEY_LEFT)
    kbd.release(KEY_LEFT)
    kbd.press(KEY_RIGHT)
    kbd.release(KEY_RIGHT)
    kbd.press(KEY_UP)
    kbd.release(KEY_UP)
    kbd.press(KEY_DOWN)
    kbd.release(KEY_DOWN)
    print(f"  Pressed/released arrow keys")

    kbd.tap(KEY_F1)
    kbd.tap(KEY_F2)
    kbd.tap(KEY_F3)
    print(f"  Tapped F1, F2, F3")

    kbd.tap(KEY_ENTER)
    kbd.tap(KEY_SPACE)
    kbd.tap(KEY_BACKSPACE)
    print(f"  Tapped ENTER, SPACE, BACKSPACE")

    # ------------------------------------------------------------------
    # 5. Simulate mouse input
    # ------------------------------------------------------------------
    print("\n--- Simulating Mouse Input ---")
    mouse.move(100, 50)
    print(f"  Moved to {mouse.position()}")

    mouse.move(-30, 20)
    print(f"  Moved to {mouse.position()}")

    mouse.click(0)
    mouse.release_button(0)
    print(f"  Left click at {mouse.position()}")

    mouse.click(1)
    mouse.release_button(1)
    print(f"  Right click at {mouse.position()}")

    mouse.scroll(3)
    mouse.scroll(-1)
    print(f"  Scrolled wheel")

    # ------------------------------------------------------------------
    # 6. Simulate touchscreen input
    # ------------------------------------------------------------------
    print("\n--- Simulating Touchscreen Input ---")
    ts.touch(512, 300)
    print(f"  Tapped at (512, 300)")
    ts.release()

    ts.touch(100, 100)
    ts.release()
    ts.touch(200, 200)
    ts.release()
    print(f"  Tapped at (100, 100) and (200, 200)")

    ts.drag(100, 400, 900, 200, steps=8)
    print(f"  Dragged from (100, 400) to (900, 200)")

    # ------------------------------------------------------------------
    # 7. Simulate gamepad input
    # ------------------------------------------------------------------
    print("\n--- Simulating Gamepad Input ---")
    gp.dpad(1, 0)
    print(f"  D-pad RIGHT")
    gp.dpad(0, -1)
    print(f"  D-pad UP")
    gp.dpad(0, 0)
    print(f"  D-pad CENTER")

    gp.left_stick(16384, -8192)
    print(f"  Left stick (16384, -8192)")
    gp.left_stick(0, 0)

    gp.right_stick(-16384, 16384)
    print(f"  Right stick (-16384, 16384)")
    gp.right_stick(0, 0)

    gp.press_button(0x130)  # BTN_SOUTH (A)
    gp.release_button(0x130)
    print(f"  Pressed/released BTN_SOUTH (A)")

    gp.press_button(0x131)  # BTN_EAST (B)
    gp.release_button(0x131)
    print(f"  Pressed/released BTN_EAST (B)")

    gp.press_button(0x134)  # BTN_TL
    gp.release_button(0x134)
    print(f"  Pressed/released BTN_TL (LB)")

    gp.left_trigger(200)
    gp.left_trigger(0)
    print(f"  Left trigger 0 -> 200 -> 0")

    gp.right_trigger(255)
    gp.right_trigger(0)
    print(f"  Right trigger 0 -> 255 -> 0")

    # ------------------------------------------------------------------
    # 8. Grab / exclusive access
    # ------------------------------------------------------------------
    print("\n--- Grab / Exclusive Access ---")
    result = input_grab_device("sim-keyboard", "evdev")
    print(f"  Grab sim-keyboard by evdev: {result}")
    result2 = input_grab_device("sim-keyboard", "kbd")
    print(f"  Grab sim-keyboard by kbd (should fail): {result2}")
    input_release_device("sim-keyboard")
    print(f"  Released sim-keyboard")
    result3 = input_grab_device("sim-keyboard", "kbd")
    print(f"  Grab sim-keyboard by kbd (should succeed): {result3}")
    input_release_device("sim-keyboard")

    # ------------------------------------------------------------------
    # 9. LED state setting
    # ------------------------------------------------------------------
    print("\n--- LED State Setting ---")
    input_set_ledstate("sim-keyboard", LED_CAPSL, True)
    input_set_ledstate("sim-keyboard", LED_NUML, True)
    input_set_ledstate("sim-keyboard", LED_SCROLLL, False)
    print(f"  CAPSL=on, NUML=on, SCROLLL=off")
    dev = input_get_device("sim-keyboard")
    if dev:
        print(f"  LED states: {dev._led_state}")

    # ------------------------------------------------------------------
    # 10. Device listing
    # ------------------------------------------------------------------
    print("\n--- Device Listing ---")
    devs = input_get_device_list()
    print(f"  Registered devices: {devs}")
    handlers = input_get_handler_list()
    print(f"  Registered handlers: {handlers}")

    # ------------------------------------------------------------------
    # 11. Device info accessors
    # ------------------------------------------------------------------
    print("\n--- Device Info ---")
    for dname in input_get_device_list():
        dname_out = input_get_name(dname)
        dphys = input_get_phys(dname)
        print(f"  name={dname_out!r} phys={dphys!r}")

    # ------------------------------------------------------------------
    # 12. Repeat parameters
    # ------------------------------------------------------------------
    print("\n--- Repeat Parameters ---")
    input_set_repeat_params("sim-keyboard", delay_ms=300, period_ms=50)
    dev = input_get_device("sim-keyboard")
    if dev:
        print(f"  sim-keyboard: delay={dev._repeat_delay_ms}ms period={dev._repeat_period_ms}ms")

    # ------------------------------------------------------------------
    # 13. Driver private data
    # ------------------------------------------------------------------
    print("\n--- Driver Private Data ---")
    input_set_drvdata("sim-keyboard", {"layout": "US", "backlight": True})
    pdata = input_get_drvdata("sim-keyboard")
    print(f"  sim-keyboard data: {pdata}")

    # ------------------------------------------------------------------
    # 14. Full state dump
    # ------------------------------------------------------------------
    print()
    input_dump_state()

    # ------------------------------------------------------------------
    # 15. Unregister and cleanup
    # ------------------------------------------------------------------
    print("\n--- Unregistering ---")
    input_unregister_device("sim-gamepad")
    mouse_h.unregister()
    kbd_handler.unregister()

    input_dump_state()

    print("=" * 60)
    print("  Input Framework Demo Complete")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo()
