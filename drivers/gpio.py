"""
UmerOS GPIO Framework
=====================
Linux kernel General Purpose I/O subsystem.
Implements GPIO controllers, descriptors, IRQ handling,
debounce, open-drain/source modes, and simulated/MCU/I2C expander chips.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GPIO Flags
# ---------------------------------------------------------------------------
GPIOF_INPUT = 0x00
GPIOF_OUTPUT = 0x01
GPIOF_ACTIVE_LOW = 0x02
GPIOF_OPEN_DRAIN = 0x04
GPIOF_OPEN_SOURCE = 0x08
GPIOF_PULL_UP = 0x10
GPIOF_PULL_DOWN = 0x20
GPIOF_EXPORT = 0x40
GPIOF_EXPORT_DIR = 0x80

# ---------------------------------------------------------------------------
# IRQ Trigger Constants
# ---------------------------------------------------------------------------
GPIO_IRQ_RISING = "rising"
GPIO_IRQ_FALLING = "falling"
GPIO_IRQ_BOTH = "both"
GPIO_IRQ_HIGH = "high"
GPIO_IRQ_LOW = "low"

_VALID_TRIGGERS = {GPIO_IRQ_RISING, GPIO_IRQ_FALLING, GPIO_IRQ_BOTH, GPIO_IRQ_HIGH, GPIO_IRQ_LOW}

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_chips: Dict[str, GpioChip] = {}
_descriptors: Dict[str, GpioDesc] = {}
_irqs: Dict[int, GpioIrqData] = {}
_irq_next: int = 1
_lookup_table: List[GpioLookup] = []
_exported: Dict[str, bool] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class GpioChip:
    """GPIO controller chip"""
    name: str
    label: str
    base: int
    ngpio: int
    can_sleep: bool = False
    is_registered: bool = False
    _direction: Dict[int, str] = field(default_factory=dict)
    _value: Dict[int, int] = field(default_factory=dict)
    _active_low: Dict[int, bool] = field(default_factory=dict)
    _debounce: Dict[int, int] = field(default_factory=dict)
    _irq: Dict[int, int] = field(default_factory=dict)
    _ops: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class GpioDesc:
    """GPIO descriptor (requested)"""
    name: str
    chip_name: str
    pin: int
    direction: str = "in"
    value: int = 0
    active_low: bool = False
    debounce_ms: int = 0
    consumer: str = ""
    is_requested: bool = False
    is_open_drain: bool = False
    is_open_source: bool = False
    is_pulled_up: bool = False
    is_pulled_down: bool = False


@dataclass
class GpioIrqData:
    """GPIO IRQ data"""
    irq: int
    chip_name: str
    pin: int
    trigger: str
    handler: Any = None
    handler_data: Any = None
    is_enabled: bool = False


@dataclass
class GpioLookup:
    """GPIO lookup table entry"""
    device_name: str
    con_id: str
    chip_name: str
    pin: int
    flags: int = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _desc_key(chip_name: str, pin: int) -> str:
    return f"{chip_name}:{pin}"


def _irq_key(chip_name: str, pin: int) -> str:
    return f"{chip_name}:{pin}"


def _assert_registered(chip: GpioChip) -> None:
    if not chip.is_registered:
        raise RuntimeError(f"GPIO chip '{chip.name}' is not registered")


def _assert_pin_range(chip: GpioChip, pin: int) -> None:
    if pin < chip.base or pin >= chip.base + chip.ngpio:
        raise ValueError(
            f"Pin {pin} out of range for chip '{chip.name}' "
            f"(base={chip.base}, ngpio={chip.ngpio})"
        )


def _assert_requested(chip_name: str, pin: int) -> GpioDesc:
    key = _desc_key(chip_name, pin)
    desc = _descriptors.get(key)
    if desc is None or not desc.is_requested:
        raise RuntimeError(
            f"GPIO {chip_name}:{pin} not requested – call gpio_request() first"
        )
    return desc


def _apply_active_low(value: int, active_low: bool) -> int:
    return (value ^ 1) & 1 if active_low else value & 1


# ---------------------------------------------------------------------------
# Controller registration
# ---------------------------------------------------------------------------
def gpiochip_register(
    name: str,
    label: str,
    ngpio: int,
    base: int = 0,
    can_sleep: bool = False,
) -> GpioChip:
    """Register GPIO chip"""
    if name in _chips:
        raise ValueError(f"GPIO chip '{name}' already registered")
    chip = GpioChip(
        name=name,
        label=label,
        base=base,
        ngpio=ngpio,
        can_sleep=can_sleep,
        is_registered=True,
    )
    # Initialise all pins
    for i in range(ngpio):
        pin_num = base + i
        chip._direction[pin_num] = "in"
        chip._value[pin_num] = 0
        chip._active_low[pin_num] = False
        chip._debounce[pin_num] = 0
    _chips[name] = chip
    log.info("Registered GPIO chip '%s' (%s) with %d GPIOs (base %d)", name, label, ngpio, base)
    return chip


def gpiochip_unregister(name: str) -> None:
    """Unregister GPIO chip"""
    chip = _chips.pop(name, None)
    if chip is None:
        raise ValueError(f"GPIO chip '{name}' not found")
    # Free any remaining descriptors
    to_remove = [k for k, d in _descriptors.items() if d.chip_name == name]
    for k in to_remove:
        _descriptors.pop(k, None)
    chip.is_registered = False
    log.info("Unregistered GPIO chip '%s'", name)


def gpiochip_get(name: str) -> GpioChip:
    """Get GPIO chip"""
    chip = _chips.get(name)
    if chip is None:
        raise ValueError(f"GPIO chip '{name}' not found")
    _assert_registered(chip)
    return chip


# ---------------------------------------------------------------------------
# Request / Free
# ---------------------------------------------------------------------------
def gpio_request(chip_name: str, pin: int, consumer: str = "") -> GpioDesc:
    """Request GPIO – like gpio_request()"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    key = _desc_key(chip_name, pin)
    if key in _descriptors and _descriptors[key].is_requested:
        raise RuntimeError(
            f"GPIO {chip_name}:{pin} already requested by '{_descriptors[key].consumer}'"
        )
    desc = GpioDesc(
        name=f"gpio{pin}",
        chip_name=chip_name,
        pin=pin,
        direction=chip._direction.get(pin, "in"),
        value=chip._value.get(pin, 0),
        active_low=chip._active_low.get(pin, False),
        debounce_ms=chip._debounce.get(pin, 0),
        consumer=consumer,
        is_requested=True,
    )
    _descriptors[key] = desc
    log.debug("Requested GPIO %s:%d for '%s'", chip_name, pin, consumer)
    return desc


def gpio_request_array(chip_name: str, pins: List[int], consumer: str = "") -> List[GpioDesc]:
    """Request multiple GPIOs"""
    descs: List[GpioDesc] = []
    try:
        for pin in pins:
            descs.append(gpio_request(chip_name, pin, consumer))
    except Exception:
        # Rollback already-requested pins
        for d in descs:
            gpio_free(d.chip_name, d.pin)
        raise
    return descs


def gpio_free(chip_name: str, pin: int) -> None:
    """Free GPIO – like gpio_free()"""
    key = _desc_key(chip_name, pin)
    desc = _descriptors.pop(key, None)
    if desc is None or not desc.is_requested:
        raise RuntimeError(f"GPIO {chip_name}:{pin} is not requested")
    # Disable any IRQ on this pin
    irq_key = _irq_key(chip_name, pin)
    irq_data = _irqs.pop(irq_key, None)
    if irq_data is not None:
        log.debug("Freed IRQ %d on GPIO %s:%d", irq_data.irq, chip_name, pin)
    log.debug("Freed GPIO %s:%d (consumer: '%s')", chip_name, pin, desc.consumer)


def gpio_free_array(chip_name: str, pins: List[int]) -> None:
    """Free multiple GPIOs"""
    for pin in pins:
        gpio_free(chip_name, pin)


# ---------------------------------------------------------------------------
# Direction
# ---------------------------------------------------------------------------
def gpio_direction_input(chip_name: str, pin: int) -> None:
    """Set GPIO as input"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    desc = _assert_requested(chip_name, pin)
    desc.direction = "in"
    chip._direction[pin] = "in"
    log.debug("GPIO %s:%d -> input", chip_name, pin)


def gpio_direction_output(chip_name: str, pin: int, value: int = 0) -> None:
    """Set GPIO as output with initial value"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    desc = _assert_requested(chip_name, pin)
    value = value & 1
    desc.direction = "out"
    desc.value = value
    chip._direction[pin] = "out"
    chip._value[pin] = value
    log.debug("GPIO %s:%d -> output (value=%d)", chip_name, pin, value)


def gpio_get_direction(chip_name: str, pin: int) -> str:
    """Get GPIO direction"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    return chip._direction.get(pin, "in")


# ---------------------------------------------------------------------------
# Value
# ---------------------------------------------------------------------------
def gpio_get_value(chip_name: str, pin: int) -> int:
    """Get GPIO value – like gpio_get_value()"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    raw = chip._value.get(pin, 0)
    desc = _descriptors.get(_desc_key(chip_name, pin))
    active_low = desc.active_low if desc else chip._active_low.get(pin, False)
    return _apply_active_low(raw, active_low)


def gpio_set_value(chip_name: str, pin: int, value: int) -> None:
    """Set GPIO value – like gpio_set_value()"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    desc = _assert_requested(chip_name, pin)
    if desc.direction != "out":
        raise RuntimeError(f"GPIO {chip_name}:{pin} is not configured as output")
    value = value & 1
    chip._value[pin] = value
    desc.value = value
    log.debug("GPIO %s:%d = %d", chip_name, pin, value)


def gpio_set_value_cansleep(chip_name: str, pin: int, value: int) -> None:
    """Set GPIO value (sleepable)"""
    chip = gpiochip_get(chip_name)
    if chip.can_sleep:
        time.sleep(0.001)
    gpio_set_value(chip_name, pin, value)


def gpio_get_value_cansleep(chip_name: str, pin: int) -> int:
    """Get GPIO value (sleepable)"""
    chip = gpiochip_get(chip_name)
    if chip.can_sleep:
        time.sleep(0.001)
    return gpio_get_value(chip_name, pin)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def gpio_set_active_low(chip_name: str, pin: int, active_low: bool) -> None:
    """Set active-low flag"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    chip._active_low[pin] = active_low
    desc = _descriptors.get(_desc_key(chip_name, pin))
    if desc:
        desc.active_low = active_low
    log.debug("GPIO %s:%d active_low=%s", chip_name, pin, active_low)


def gpio_set_debounce(chip_name: str, pin: int, debounce_ms: int) -> None:
    """Set debounce time"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    if debounce_ms < 0 or debounce_ms > 10000:
        raise ValueError(f"Debounce {debounce_ms}ms out of range (0-10000)")
    chip._debounce[pin] = debounce_ms
    desc = _descriptors.get(_desc_key(chip_name, pin))
    if desc:
        desc.debounce_ms = debounce_ms
    log.debug("GPIO %s:%d debounce=%dms", chip_name, pin, debounce_ms)


def gpio_set_open_drain(chip_name: str, pin: int) -> None:
    """Set open-drain mode"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    desc = _descriptors.get(_desc_key(chip_name, pin))
    if desc:
        desc.is_open_drain = True
        desc.is_open_source = False
    log.debug("GPIO %s:%d -> open-drain", chip_name, pin)


def gpio_set_open_source(chip_name: str, pin: int) -> None:
    """Set open-source mode"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    desc = _descriptors.get(_desc_key(chip_name, pin))
    if desc:
        desc.is_open_source = True
        desc.is_open_drain = False
    log.debug("GPIO %s:%d -> open-source", chip_name, pin)


def gpio_set_pull_up(chip_name: str, pin: int) -> None:
    """Set pull-up resistor"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    desc = _descriptors.get(_desc_key(chip_name, pin))
    if desc:
        desc.is_pulled_up = True
        desc.is_pulled_down = False
    log.debug("GPIO %s:%d -> pull-up", chip_name, pin)


def gpio_set_pull_down(chip_name: str, pin: int) -> None:
    """Set pull-down resistor"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    desc = _descriptors.get(_desc_key(chip_name, pin))
    if desc:
        desc.is_pulled_down = True
        desc.is_pulled_up = False
    log.debug("GPIO %s:%d -> pull-down", chip_name, pin)


# ---------------------------------------------------------------------------
# IRQ
# ---------------------------------------------------------------------------
def gpio_to_irq(chip_name: str, pin: int) -> int:
    """Convert GPIO to IRQ number"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    # IRQ = base-relative pin offset + chip base IRQ offset
    irq_num = (pin - chip.base) + chip.base + 32  # simple mapping
    chip._irq[pin] = irq_num
    return irq_num


def gpio_request_irq(
    chip_name: str,
    pin: int,
    trigger: str,
    handler: Callable,
    handler_data: Any = None,
) -> int:
    """Request IRQ on GPIO"""
    if trigger not in _VALID_TRIGGERS:
        raise ValueError(f"Invalid trigger '{trigger}'; use one of {_VALID_TRIGGERS}")
    irq_key = _irq_key(chip_name, pin)
    if irq_key in _irqs:
        raise RuntimeError(f"IRQ already configured on {chip_name}:{pin}")
    irq_num = gpio_to_irq(chip_name, pin)
    irq_data = GpioIrqData(
        irq=irq_num,
        chip_name=chip_name,
        pin=pin,
        trigger=trigger,
        handler=handler,
        handler_data=handler_data,
        is_enabled=True,
    )
    _irqs[irq_key] = irq_data
    log.debug(
        "Requested IRQ %d on GPIO %s:%d (trigger=%s)",
        irq_num, chip_name, pin, trigger,
    )
    return irq_num


def gpio_free_irq(chip_name: str, pin: int) -> None:
    """Free IRQ on GPIO"""
    irq_key = _irq_key(chip_name, pin)
    irq_data = _irqs.pop(irq_key, None)
    if irq_data is None:
        raise RuntimeError(f"No IRQ configured on {chip_name}:{pin}")
    log.debug("Freed IRQ %d on GPIO %s:%d", irq_data.irq, chip_name, pin)


def gpio_enable_irq(chip_name: str, pin: int) -> None:
    """Enable GPIO IRQ"""
    irq_key = _irq_key(chip_name, pin)
    irq_data = _irqs.get(irq_key)
    if irq_data is None:
        raise RuntimeError(f"No IRQ configured on {chip_name}:{pin}")
    irq_data.is_enabled = True
    log.debug("Enabled IRQ on GPIO %s:%d", chip_name, pin)


def gpio_disable_irq(chip_name: str, pin: int) -> None:
    """Disable GPIO IRQ"""
    irq_key = _irq_key(chip_name, pin)
    irq_data = _irqs.get(irq_key)
    if irq_data is None:
        raise RuntimeError(f"No IRQ configured on {chip_name}:{pin}")
    irq_data.is_enabled = False
    log.debug("Disabled IRQ on GPIO %s:%d", chip_name, pin)


def gpio_trigger_irq(chip_name: str, pin: int) -> None:
    """Manually trigger GPIO IRQ (for testing)"""
    irq_key = _irq_key(chip_name, pin)
    irq_data = _irqs.get(irq_key)
    if irq_data is None:
        raise RuntimeError(f"No IRQ configured on {chip_name}:{pin}")
    if not irq_data.is_enabled:
        log.debug("IRQ on GPIO %s:%d is disabled – skipping trigger", chip_name, pin)
        return
    if irq_data.handler is not None:
        log.debug(
            "Triggering IRQ %d on GPIO %s:%d (handler=%s)",
            irq_data.irq, chip_name, pin,
            irq_data.handler.__name__ if callable(irq_data.handler) else irq_data.handler,
        )
        irq_data.handler(irq_data.irq, irq_data.handler_data)
    else:
        log.debug("IRQ %d triggered but no handler installed", irq_data.irq)


# ---------------------------------------------------------------------------
# Export (sysfs-like)
# ---------------------------------------------------------------------------
def gpio_export(chip_name: str, pin: int, direction_visible: bool = True) -> None:
    """Export GPIO to userspace"""
    chip = gpiochip_get(chip_name)
    _assert_pin_range(chip, pin)
    key = _desc_key(chip_name, pin)
    _exported[key] = direction_visible
    log.info("Exported GPIO %s:%d (dir_visible=%s)", chip_name, pin, direction_visible)


def gpio_unexport(chip_name: str, pin: int) -> None:
    """Unexport GPIO"""
    key = _desc_key(chip_name, pin)
    if key not in _exported:
        raise RuntimeError(f"GPIO {chip_name}:{pin} is not exported")
    del _exported[key]
    log.info("Unexported GPIO %s:%d", chip_name, pin)


# ---------------------------------------------------------------------------
# Bulk
# ---------------------------------------------------------------------------
def gpio_get_array_values(chip_name: str, pins: List[int]) -> List[int]:
    """Get values for array of GPIOs"""
    return [gpio_get_value(chip_name, pin) for pin in pins]


def gpio_set_array_values(chip_name: str, pin_values: List[Tuple[int, int]]) -> None:
    """Set values for array of GPIOs – pin_values is list of (pin, value)"""
    for pin, value in pin_values:
        gpio_set_value(chip_name, pin, value)


# ---------------------------------------------------------------------------
# Chip info
# ---------------------------------------------------------------------------
def gpiochip_get_ngpio(chip_name: str) -> int:
    """Get number of GPIOs in chip"""
    return gpiochip_get(chip_name).ngpio


def gpiochip_get_label(chip_name: str) -> str:
    """Get chip label"""
    return gpiochip_get(chip_name).label


def gpiochip_get_base(chip_name: str) -> int:
    """Get base GPIO number"""
    return gpiochip_get(chip_name).base


def gpio_list_chips() -> List[str]:
    """List all GPIO chips"""
    return list(_chips.keys())


def gpio_list_requested() -> List[str]:
    """List all requested GPIOs"""
    return [
        k for k, d in _descriptors.items()
        if d.is_requested
    ]


# ---------------------------------------------------------------------------
# Lookup table
# ---------------------------------------------------------------------------
def gpio_add_lookup(
    device_name: str,
    con_id: str,
    chip_name: str,
    pin: int,
    flags: int = 0,
) -> None:
    """Add a GPIO lookup table entry"""
    entry = GpioLookup(
        device_name=device_name,
        con_id=con_id,
        chip_name=chip_name,
        pin=pin,
        flags=flags,
    )
    _lookup_table.append(entry)
    log.debug("Added GPIO lookup: %s.%s -> %s:%d", device_name, con_id, chip_name, pin)


def gpio_find_lookup(device_name: str, con_id: str) -> Optional[GpioLookup]:
    """Find GPIO lookup entry"""
    for entry in _lookup_table:
        if entry.device_name == device_name and entry.con_id == con_id:
            return entry
    return None


# ---------------------------------------------------------------------------
# Dump utility
# ---------------------------------------------------------------------------
def gpio_dump() -> None:
    """Dump all registered chips, descriptors, and IRQs"""
    print("\n=== GPIO Chips ===")
    for name, chip in _chips.items():
        status = "registered" if chip.is_registered else "unregistered"
        sleep = "sleepable" if chip.can_sleep else "fast"
        print(f"  [{status}] {chip.name} ({chip.label}): "
              f"base={chip.base} ngpio={chip.ngpio} ({sleep})")
    if _descriptors:
        print("\n=== Requested GPIOs ===")
        for key, desc in _descriptors.items():
            if not desc.is_requested:
                continue
            flags_parts: List[str] = []
            if desc.active_low:
                flags_parts.append("active-low")
            if desc.is_open_drain:
                flags_parts.append("open-drain")
            if desc.is_open_source:
                flags_parts.append("open-source")
            if desc.is_pulled_up:
                flags_parts.append("pull-up")
            if desc.is_pulled_down:
                flags_parts.append("pull-down")
            if desc.debounce_ms:
                flags_parts.append(f"debounce={desc.debounce_ms}ms")
            flags_str = " ".join(flags_parts)
            print(
                f"  {desc.chip_name}:{desc.pin} dir={desc.direction} "
                f"val={desc.value} consumer='{desc.consumer}' {flags_str}"
            )
    if _irqs:
        print("\n=== GPIO IRQs ===")
        for key, irq in _irqs.items():
            enabled = "enabled" if irq.is_enabled else "disabled"
            handler_name = (
                irq.handler.__name__ if callable(irq.handler) else str(irq.handler)
            )
            print(
                f"  IRQ {irq.irq} on {irq.chip_name}:{irq.pin} "
                f"trigger={irq.trigger} [{enabled}] handler={handler_name}"
            )
    if _exported:
        print("\n=== Exported GPIOs ===")
        for key, dir_vis in _exported.items():
            print(f"  {key} dir_visible={dir_vis}")
    if _lookup_table:
        print("\n=== GPIO Lookup Table ===")
        for entry in _lookup_table:
            print(
                f"  {entry.device_name}.{entry.con_id} -> "
                f"{entry.chip_name}:{entry.pin} flags=0x{entry.flags:02x}"
            )
    print()


# ---------------------------------------------------------------------------
# Simulated GPIO Chips
# ---------------------------------------------------------------------------
class SimGpioChip:
    """Simulated GPIO chip with configurable pins"""

    def __init__(self, name: str, label: str, ngpio: int, base: int = 0) -> None:
        self.name = name
        self.label = label
        self.ngpio = ngpio
        self.base = base
        gpiochip_register(name, label, ngpio, base)
        log.info("Created simulated GPIO chip '%s' (%s)", name, label)

    def set_pin(self, pin: int, value: int) -> None:
        """Directly set pin value (bypass direction check)"""
        chip = gpiochip_get(self.name)
        chip._value[pin] = value & 1

    def get_pin(self, pin: int) -> int:
        """Directly read pin value"""
        chip = gpiochip_get(self.name)
        return chip._value.get(pin, 0)


class McuGpioChip:
    """MCU GPIO port (PORTA, PORTB, etc.)"""

    def __init__(self, port_name: str, ngpio: int = 16, base: int = 0) -> None:
        self.port_name = port_name
        self.ngpio = ngpio
        self.base = base
        self._alt_funcs: Dict[int, str] = {}
        gpiochip_register(port_name, f"MCU {port_name}", ngpio, base)
        # Assign default alternate function names
        for i in range(ngpio):
            self._alt_funcs[base + i] = f"GPIO{port_name[-1]}_{i}"
        log.info("Created MCU GPIO port '%s' with %d pins", port_name, ngpio)

    def set_alt_func(self, pin: int, func: str) -> None:
        """Set alternate function for pin"""
        chip = gpiochip_get(self.port_name)
        _assert_pin_range(chip, pin)
        self._alt_funcs[pin] = func
        log.debug("GPIO %s:%d alt_func=%s", self.port_name, pin, func)

    def get_alt_func(self, pin: int) -> str:
        """Get current alternate function"""
        return self._alt_funcs.get(pin, "GPIO")


class Pca9555GpioChip:
    """PCA9555 I2C GPIO expander (16 pins)"""

    def __init__(self, name: str, i2c_addr: int = 0x20, base: int = 0) -> None:
        self.name = name
        self.i2c_addr = i2c_addr
        self.base = base
        self._input_regs = [0x00, 0x00]  # port 0, port 1
        self._output_regs = [0x00, 0x00]
        self._config_regs = [0xFF, 0xFF]  # all inputs by default
        gpiochip_register(name, f"PCA9555@0x{i2c_addr:02x}", 16, base=base)
        log.info("Created PCA9555 GPIO expander '%s' at I2C addr 0x%02x", name, i2c_addr)

    def read_input(self, pin: int) -> int:
        """Read input register for pin"""
        chip = gpiochip_get(self.name)
        _assert_pin_range(chip, pin)
        port = (pin - self.base) // 8
        bit = (pin - self.base) % 8
        return (self._input_regs[port] >> bit) & 1

    def write_output(self, pin: int, value: int) -> None:
        """Write output register for pin"""
        chip = gpiochip_get(self.name)
        _assert_pin_range(chip, pin)
        port = (pin - self.base) // 8
        bit = (pin - self.base) % 8
        if value:
            self._output_regs[port] |= 1 << bit
        else:
            self._output_regs[port] &= ~(1 << bit)
        # Simulate readback
        self._input_regs[port] = self._output_regs[port]

    def configure_direction(self, pin: int, as_output: bool) -> None:
        """Configure pin direction (True=output, False=input)"""
        chip = gpiochip_get(self.name)
        _assert_pin_range(chip, pin)
        port = (pin - self.base) // 8
        bit = (pin - self.base) % 8
        if as_output:
            self._config_regs[port] &= ~(1 << bit)  # 0 = output
        else:
            self._config_regs[port] |= 1 << bit  # 1 = input


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def demo() -> None:
    """Demonstrate the GPIO subsystem."""
    print("\n" + "=" * 60)
    print(" UmerOS GPIO Framework Demo")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Create simulated GPIO chips
    # ------------------------------------------------------------------
    print("\n--- Creating GPIO Chips ---")
    gpio0 = SimGpioChip("gpio0", "Simulated GPIO Controller 0", ngpio=8, base=0)
    gpio1 = SimGpioChip("gpio1", "Simulated GPIO Controller 1", ngpio=16, base=8)
    mcu = McuGpioChip("PORTA", ngpio=16, base=100)
    pca = Pca9555GpioChip("pca0", i2c_addr=0x20)

    gpio_dump()

    # ------------------------------------------------------------------
    # 2. Request and configure pins as input/output
    # ------------------------------------------------------------------
    print("\n--- Requesting & Configuring Pins ---")

    # Request pins as input
    led_red = gpio_request("gpio0", 0, consumer="led-red")
    led_green = gpio_request("gpio0", 1, consumer="led-green")
    btn_start = gpio_request("gpio0", 2, consumer="btn-start")
    btn_stop = gpio_request("gpio0", 3, consumer="btn-stop")

    gpio_direction_output("gpio0", 0, 0)  # LED off
    gpio_direction_output("gpio0", 1, 0)  # LED off
    gpio_direction_input("gpio0", 2)      # Button
    gpio_direction_input("gpio0", 3)      # Button

    # Request multiple pins on gpio1 as output (for bulk value demo)
    sensors = gpio_request_array("gpio1", [8, 9, 10, 11], consumer="sensors")
    for s in sensors:
        gpio_direction_output(s.chip_name, s.pin, 0)

    # Request MCU pins
    uart_tx = gpio_request("PORTA", 100, consumer="uart0-tx")
    uart_rx = gpio_request("PORTA", 101, consumer="uart0-rx")
    gpio_direction_output("PORTA", 100, 0)
    gpio_direction_input("PORTA", 101)
    mcu.set_alt_func(100, "UART0_TX")
    mcu.set_alt_func(101, "UART0_RX")

    # Request PCA9555 pins
    pca_led0 = gpio_request("pca0", 0, consumer="pca-led0")
    pca_in0 = gpio_request("pca0", 8, consumer="pca-input0")
    gpio_direction_output("pca0", 0, 0)
    gpio_direction_input("pca0", 8)
    pca.configure_direction(0, as_output=True)
    pca.configure_direction(8, as_output=False)

    gpio_dump()

    # ------------------------------------------------------------------
    # 3. Set and get pin values
    # ------------------------------------------------------------------
    print("\n--- Setting & Getting Pin Values ---")

    gpio_set_value("gpio0", 0, 1)  # LED on
    gpio_set_value("gpio0", 1, 1)  # LED on
    print(f"  LED red  = {gpio_get_value('gpio0', 0)}")
    print(f"  LED green = {gpio_get_value('gpio0', 1)}")

    # Simulate button press
    gpio0.set_pin(2, 1)
    gpio0.set_pin(3, 0)
    print(f"  Btn start = {gpio_get_value('gpio0', 2)}")
    print(f"  Btn stop  = {gpio_get_value('gpio0', 3)}")

    # Bulk set
    gpio_set_array_values("gpio1", [(8, 1), (9, 0), (10, 1), (11, 1)])
    vals = gpio_get_array_values("gpio1", [8, 9, 10, 11])
    print(f"  Sensor values: {vals}")

    # PCA9555
    pca.write_output(0, 1)
    print(f"  PCA LED0 = {pca.read_input(0)}")
    pca.write_output(0, 0)
    print(f"  PCA LED0 (off) = {pca.read_input(0)}")

    # ------------------------------------------------------------------
    # 4. Active-low and open-drain modes
    # ------------------------------------------------------------------
    print("\n--- Active-Low & Open-Drain ---")

    gpio_set_active_low("gpio0", 0, True)
    print(f"  LED red raw=1, active_low=True -> gpio_get_value={gpio_get_value('gpio0', 0)}")

    gpio_set_active_low("gpio0", 0, False)
    print(f"  LED red raw=1, active_low=False -> gpio_get_value={gpio_get_value('gpio0', 0)}")

    # Request pins 4 and 5 for open-drain/open-source demo
    gpio_request("gpio0", 4, consumer="open-drain-pin")
    gpio_request("gpio0", 5, consumer="open-source-pin")
    gpio_set_open_drain("gpio0", 4)
    desc = _descriptors.get(_desc_key("gpio0", 4))
    print(f"  gpio0:4 open_drain={desc.is_open_drain if desc else 'N/A'}")

    gpio_set_open_source("gpio0", 5)
    desc = _descriptors.get(_desc_key("gpio0", 5))
    print(f"  gpio0:5 open_source={desc.is_open_source if desc else 'N/A'}")

    # ------------------------------------------------------------------
    # 5. Debounce configuration
    # ------------------------------------------------------------------
    print("\n--- Debounce Configuration ---")

    gpio_set_debounce("gpio0", 2, 50)
    gpio_set_debounce("gpio0", 3, 100)
    desc2 = _descriptors.get(_desc_key("gpio0", 2))
    desc3 = _descriptors.get(_desc_key("gpio0", 3))
    print(f"  btn-start debounce = {desc2.debounce_ms}ms" if desc2 else "  N/A")
    print(f"  btn-stop  debounce = {desc3.debounce_ms}ms" if desc3 else "  N/A")

    # ------------------------------------------------------------------
    # 6. Pull-up / Pull-down
    # ------------------------------------------------------------------
    print("\n--- Pull-Up / Pull-Down ---")

    gpio_set_pull_up("gpio0", 2)
    gpio_set_pull_down("gpio0", 3)
    desc2 = _descriptors.get(_desc_key("gpio0", 2))
    desc3 = _descriptors.get(_desc_key("gpio0", 3))
    print(f"  btn-start: pull_up={desc2.is_pulled_up}, pull_down={desc2.is_pulled_down}" if desc2 else "  N/A")
    print(f"  btn-stop:  pull_up={desc3.is_pulled_up}, pull_down={desc3.is_pulled_down}" if desc3 else "  N/A")

    # ------------------------------------------------------------------
    # 7. GPIO-to-IRQ mapping
    # ------------------------------------------------------------------
    print("\n--- GPIO-to-IRQ Mapping ---")

    irq0 = gpio_to_irq("gpio0", 2)
    irq1 = gpio_to_irq("gpio0", 3)
    irq8 = gpio_to_irq("gpio1", 8)
    print(f"  gpio0:2 -> IRQ {irq0}")
    print(f"  gpio0:3 -> IRQ {irq1}")
    print(f"  gpio1:8 -> IRQ {irq8}")

    # ------------------------------------------------------------------
    # 8. Interrupt handling
    # ------------------------------------------------------------------
    print("\n--- Interrupt Handling ---")

    irq_log: List[str] = []

    def on_start_button(irq: int, data: Any) -> None:
        irq_log.append(f"START pressed (IRQ {irq})")

    def on_stop_button(irq: int, data: Any) -> None:
        irq_log.append(f"STOP pressed (IRQ {irq})")

    gpio_request_irq("gpio0", 2, GPIO_IRQ_RISING, on_start_button, handler_data="start")
    gpio_request_irq("gpio0", 3, GPIO_IRQ_FALLING, on_stop_button, handler_data="stop")

    # Trigger interrupts
    gpio_trigger_irq("gpio0", 2)
    gpio_trigger_irq("gpio0", 3)
    print(f"  IRQ log: {irq_log}")

    # Enable/disable
    gpio_disable_irq("gpio0", 2)
    gpio_trigger_irq("gpio0", 2)  # should be skipped
    print(f"  After disable+trigger: {irq_log}")

    gpio_enable_irq("gpio0", 2)
    gpio_trigger_irq("gpio0", 2)
    print(f"  After enable+trigger: {irq_log}")

    # ------------------------------------------------------------------
    # 9. Export / Unexport
    # ------------------------------------------------------------------
    print("\n--- GPIO Export (sysfs) ---")

    gpio_export("gpio0", 0, direction_visible=True)
    gpio_export("gpio0", 2, direction_visible=False)
    gpio_unexport("gpio0", 2)
    print(f"  Exported keys: {list(_exported.keys())}")

    # ------------------------------------------------------------------
    # 10. GPIO lookup table
    # ------------------------------------------------------------------
    print("\n--- GPIO Lookup Table ---")

    gpio_add_lookup("spi0", "cs-gpio", "gpio0", 4, flags=GPIOF_OUTPUT)
    gpio_add_lookup("spi0", "miso", "gpio0", 5, flags=GPIOF_INPUT)
    gpio_add_lookup("i2c0", "sda", "PORTA", 102, flags=GPIOF_INPUT | GPIOF_PULL_UP)
    gpio_add_lookup("i2c0", "scl", "PORTA", 103, flags=GPIOF_INPUT | GPIOF_PULL_UP)

    for entry in _lookup_table:
        print(f"  {entry.device_name}.{entry.con_id} -> {entry.chip_name}:{entry.pin}")

    found = gpio_find_lookup("spi0", "cs-gpio")
    if found:
        print(f"  Found: {found.device_name}.{found.con_id} -> {found.chip_name}:{found.pin}")

    # ------------------------------------------------------------------
    # 11. Bulk operations
    # ------------------------------------------------------------------
    print("\n--- Bulk Operations ---")

    gpio_set_array_values("gpio1", [(8, 0), (9, 1), (10, 0), (11, 1)])
    vals = gpio_get_array_values("gpio1", [8, 9, 10, 11])
    print(f"  gpio1 sensor values: {vals}")

    gpio_request_array("gpio1", [12, 13, 14, 15], consumer="led-bar")
    for p in [12, 13, 14, 15]:
        gpio_direction_output("gpio1", p, 0)
    gpio_set_array_values("gpio1", [(12, 1), (13, 1), (14, 0), (15, 1)])
    vals = gpio_get_array_values("gpio1", [12, 13, 14, 15])
    print(f"  gpio1 led-bar values: {vals}")

    # ------------------------------------------------------------------
    # 12. Chip info and listing
    # ------------------------------------------------------------------
    print("\n--- Chip Info & Listing ---")

    for chip_name in gpio_list_chips():
        chip = gpiochip_get(chip_name)
        ngpio = gpiochip_get_ngpio(chip_name)
        label = gpiochip_get_label(chip_name)
        base = gpiochip_get_base(chip_name)
        print(f"  {chip_name}: label='{label}' base={base} ngpio={ngpio}")

    print(f"\n  Requested GPIOs: {gpio_list_requested()}")

    # ------------------------------------------------------------------
    # 13. MCU alternate function dump
    # ------------------------------------------------------------------
    print("\n--- MCU Alternate Functions ---")
    mcu_chip = gpiochip_get("PORTA")
    for p in range(100, 104):
        func = mcu.get_alt_func(p)
        print(f"  PORTA:{p} = {func}")

    # ------------------------------------------------------------------
    # 14. PCA9555 register dump
    # ------------------------------------------------------------------
    print("\n--- PCA9555 Registers ---")
    print(f"  Config:   {pca._config_regs}")
    print(f"  Output:   {pca._output_regs}")
    print(f"  Input:    {pca._input_regs}")

    # ------------------------------------------------------------------
    # 15. Free and cleanup
    # ------------------------------------------------------------------
    print("\n--- Freeing GPIOs ---")
    gpio_free("gpio0", 0)
    gpio_free("gpio0", 1)
    gpio_free_array("gpio1", [8, 9, 10, 11])
    gpio_free("gpio0", 4)
    gpio_free("gpio0", 5)
    gpio_unexport("gpio0", 0)
    print("  Freed all demo GPIOs")

    # ------------------------------------------------------------------
    # Final dump
    # ------------------------------------------------------------------
    gpio_dump()
    print("=" * 60)
    print(" GPIO Framework Demo Complete")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Module-level init
# ---------------------------------------------------------------------------
def init() -> None:
    """Initialise the GPIO framework."""
    log.info("GPIO framework loaded")


if __name__ == "__main__":
    init()
    demo()
