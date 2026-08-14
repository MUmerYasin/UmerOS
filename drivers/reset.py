"""
UmerOS Reset Controller Subsystem
=================================
Kernel-like reset line management framework.

Implements reset controller devices, reset lines, consumer devices,
and the full kernel reset API (assert, deassert, bulk operations).

Mirrors drivers/reset/reset-core.c and include/linux/reset-controller.h.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    from .device import Device
except ImportError:
    Device = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Reset Controller IDs
# ---------------------------------------------------------------------------
_RESET_ID_COUNTER: int = 0


def _next_reset_id() -> int:
    global _RESET_ID_COUNTER
    _RESET_ID_COUNTER += 1
    return _RESET_ID_COUNTER


# ---------------------------------------------------------------------------
# Core Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class ResetController:
    """Reset controller device.

    Each controller manages a set of reset lines for one or more
    peripheral devices.  Mirrors ``struct reset_controller_dev``.

    Attributes:
        name: Unique controller identifier.
        id: Auto-assigned numeric id.
        nr_resets: Number of reset lines managed.
        resets: List of ``ResetLine`` objects managed by this controller.
        _is_registered: Whether the controller is in the global registry.
        _ops: Controller-specific operations (e.g. assert/deassert callbacks).
    """

    name: str
    id: int = 0
    nr_resets: int = 0
    resets: list = field(default_factory=list)
    _is_registered: bool = False
    _ops: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id == 0:
            self.id = _next_reset_id()


@dataclass
class ResetLine:
    """Single reset line.

    Represents one physical or logical reset signal managed by a
    controller.  Mirrors ``struct reset_control``.

    Attributes:
        controller_name: Name of the owning controller.
        index: Line index within the controller.
        name: Human-readable label.
        asserted: True when the line is held in reset.
        active_low: True when the reset is active-low.
        _consumer: Device name currently using this line.
    """

    controller_name: str
    index: int
    name: str
    asserted: bool = False
    active_low: bool = False
    _consumer: str = ""


@dataclass
class ResetConsumer:
    """Device consuming a reset line.

    Tracks which device holds a reference to which reset line.
    Mirrors the consumer side of ``struct reset_control``.

    Attributes:
        dev_name: Consumer device name.
        controller_name: Controller holding the reset line.
        reset_index: Index of the reset line within the controller.
        _is_bound: Whether the consumer is bound to the line.
    """

    dev_name: str
    controller_name: str
    reset_index: int
    _is_bound: bool = False


# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_controllers: Dict[str, ResetController] = {}
_consumers: Dict[str, ResetConsumer] = {}
_lines: Dict[str, ResetLine] = {}   # "controller_name:index" -> ResetLine


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------
def _get_controller(name: str) -> ResetController:
    ctrl = _controllers.get(name)
    if ctrl is None:
        raise KeyError(f"[RESET] controller {name!r} not found")
    return ctrl


def _line_key(ctrl_name: str, index: int) -> str:
    return f"{ctrl_name}:{index}"


def _get_line(ctrl_name: str, index: int) -> ResetLine:
    key = _line_key(ctrl_name, index)
    line = _lines.get(key)
    if line is None:
        raise KeyError(
            f"[RESET] line index {index} not found on controller {ctrl_name!r}"
        )
    return line


def _get_consumer(dev_name: str) -> ResetConsumer:
    cons = _consumers.get(dev_name)
    if cons is None:
        raise KeyError(f"[RESET] no reset consumer for device {dev_name!r}")
    return cons


# ---------------------------------------------------------------------------
# Reset Controller Registration
# ---------------------------------------------------------------------------
def reset_controller_register(controller: ResetController) -> bool:
    """Register reset controller — like reset_controller_register().

    Populates the controller's reset line table if empty, marks it
    as registered, and stores it in the global registry.

    Returns:
        True on success, False if a controller with the same name exists.
    """
    if controller.name in _controllers:
        print(f"[RESET] ERROR: controller {controller.name!r} already registered")
        return False

    if not controller.resets:
        for i in range(controller.nr_resets):
            line = ResetLine(
                controller_name=controller.name,
                index=i,
                name=f"{controller.name}_line{i}",
            )
            controller.resets.append(line)
            _lines[_line_key(controller.name, i)] = line

    controller._is_registered = True
    _controllers[controller.name] = controller
    print(
        f"[RESET] registered controller: {controller.name!r} "
        f"(id={controller.id}, {controller.nr_resets} lines)"
    )
    return True


def reset_controller_unregister(name: str) -> bool:
    """Unregister reset controller.

    Removes the controller and all its lines from the global registries
    and unbinds any consumers still referencing those lines.

    Returns:
        True on success, False if the controller does not exist.
    """
    ctrl = _controllers.pop(name, None)
    if ctrl is None:
        print(f"[RESET] ERROR: no controller {name!r}")
        return False

    ctrl._is_registered = False

    # Remove lines and unbind consumers
    keys_to_remove = [_line_key(name, line.index) for line in ctrl.resets]
    for lk in keys_to_remove:
        _lines.pop(lk, None)

    for dev_name, cons in list(_consumers.items()):
        if cons.controller_name == name:
            cons._is_bound = False
            _consumers.pop(dev_name, None)

    print(f"[RESET] unregistered controller: {name!r}")
    return True


# ---------------------------------------------------------------------------
# Reset Control Get / Put
# ---------------------------------------------------------------------------
def reset_control_get(
    dev_name: str, controller_name: str, index: int
) -> Optional[ResetConsumer]:
    """Get reset control — like reset_control_get().

    Binds *dev_name* to the reset line at *index* on the named
    controller.

    Returns:
        The ``ResetConsumer`` on success, or ``None`` on failure.
    """
    _get_controller(controller_name)
    line = _get_line(controller_name, index)

    if dev_name in _consumers:
        existing = _consumers[dev_name]
        if existing.controller_name == controller_name and existing.reset_index == index:
            print(
                f"[RESET] get: {dev_name!r} already bound to "
                f"{controller_name!r}:{index}"
            )
            return existing
        print(
            f"[RESET] ERROR: {dev_name!r} already bound to a different "
            f"reset line ({existing.controller_name!r}:{existing.reset_index})"
        )
        return None

    cons = ResetConsumer(
        dev_name=dev_name,
        controller_name=controller_name,
        reset_index=index,
        _is_bound=True,
    )
    _consumers[dev_name] = cons
    line._consumer = dev_name
    print(
        f"[RESET] get: {dev_name!r} -> {controller_name!r}:{index} "
        f"({line.name!r})"
    )
    return cons


def reset_control_put(dev_name: str) -> bool:
    """Release reset control — like reset_control_put().

    Unbinds the consumer from its reset line and frees the consumer
    record.

    Returns:
        True on success, False if the device had no reset control.
    """
    cons = _consumers.pop(dev_name, None)
    if cons is None:
        print(f"[RESET] put: no reset control for {dev_name!r}, nothing to release")
        return False

    try:
        line = _get_line(cons.controller_name, cons.reset_index)
        line._consumer = ""
    except KeyError:
        pass

    cons._is_bound = False
    print(
        f"[RESET] put: released reset control for {dev_name!r} "
        f"(was {cons.controller_name!r}:{cons.reset_index})"
    )
    return True


# ---------------------------------------------------------------------------
# Reset Control Assert / Deassert
# ---------------------------------------------------------------------------
def reset_control_assert(dev_name: str) -> bool:
    """Assert reset (hold device in reset) — like reset_control_assert().

    Returns:
        True on success, False if the device is not bound.
    """
    cons = _get_consumer(dev_name)
    line = _get_line(cons.controller_name, cons.reset_index)

    if line.active_low:
        line.asserted = False  # active-low: deasserted means asserted
    else:
        line.asserted = True

    print(
        f"[RESET] ASSERT {dev_name!r} on {cons.controller_name!r}:"
        f"{cons.reset_index} ({line.name!r}) -> asserted={line.asserted}"
    )
    return True


def reset_control_deassert(dev_name: str) -> bool:
    """Deassert reset (release device from reset) — like reset_control_deassert().

    Returns:
        True on success, False if the device is not bound.
    """
    cons = _get_consumer(dev_name)
    line = _get_line(cons.controller_name, cons.reset_index)

    if line.active_low:
        line.asserted = True  # active-low: deasserted means asserted
    else:
        line.asserted = False

    print(
        f"[RESET] DEASSERT {dev_name!r} on {cons.controller_name!r}:"
        f"{cons.reset_index} ({line.name!r}) -> asserted={line.asserted}"
    )
    return True


def reset_control_reset(dev_name: str) -> bool:
    """Full reset cycle: assert then deassert — like reset_control_reset().

    This is a convenience wrapper that performs the standard
    assert-wait-deassert sequence required by most peripherals.

    Returns:
        True on success, False if the device is not bound.
    """
    cons = _get_consumer(dev_name)
    print(f"[RESET] FULL RESET CYCLE for {dev_name!r}")

    if not reset_control_assert(dev_name):
        return False
    if not reset_control_deassert(dev_name):
        return False

    print(f"[RESET] full reset cycle complete for {dev_name!r}")
    return True


# ---------------------------------------------------------------------------
# Reset Control Status
# ---------------------------------------------------------------------------
def reset_control_status(dev_name: str) -> int:
    """Get reset status — like reset_control_status().

    Returns:
        0 if the reset line is deasserted (not in reset),
        1 if the reset line is asserted (held in reset).
    """
    cons = _get_consumer(dev_name)
    line = _get_line(cons.controller_name, cons.reset_index)
    status = 1 if line.asserted else 0
    label = "ASSERTED (in reset)" if status else "DEASSERTED (active)"
    print(f"[RESET] status {dev_name!r}: {status} ({label})")
    return status


# ---------------------------------------------------------------------------
# Bulk Reset Operations
# ---------------------------------------------------------------------------
def reset_control_bulk_get(
    dev_name: str, count: int, indices: list[int]
) -> Optional[List[ResetConsumer]]:
    """Get multiple reset controls at once — like reset_control_bulk_get().

    Args:
        dev_name: Consumer device name.
        count: Number of reset lines to acquire.
        indices: List of line indices on the controller.

    Returns:
        List of ``ResetConsumer`` objects, or ``None`` on failure.
    """
    _get_controller(dev_name.split(".")[0] if "." in dev_name else "")

    consumers: List[ResetConsumer] = []
    for i in range(count):
        idx = indices[i] if i < len(indices) else i
        cons = reset_control_get(dev_name, dev_name.split(".")[0] if "." in dev_name else "", idx)
        if cons is None:
            # Rollback: put everything we got so far
            for c in consumers:
                reset_control_put(c.dev_name)
            print(f"[RESET] bulk_get: FAILED at index {idx}")
            return None
        consumers.append(cons)

    print(
        f"[RESET] bulk_get: {dev_name!r} acquired {count} reset "
        f"controls (indices={indices})"
    )
    return consumers


def reset_control_bulk_assert(dev_name: str, count: int) -> bool:
    """Assert multiple reset controls — like reset_control_bulk_assert().

    Returns:
        True if all lines were asserted successfully.
    """
    cons = _get_consumer(dev_name)
    ctrl_name = cons.controller_name
    ctrl = _get_controller(ctrl_name)

    success = True
    for i in range(count):
        if i < len(ctrl.resets):
            line = ctrl.resets[i]
            if line._consumer == dev_name:
                if line.active_low:
                    line.asserted = False
                else:
                    line.asserted = True
                print(
                    f"[RESET] bulk_assert: {dev_name!r} line {i} "
                    f"({line.name!r}) -> asserted={line.asserted}"
                )
            else:
                print(
                    f"[RESET] bulk_assert: line {i} not bound to "
                    f"{dev_name!r}, skipping"
                )
                success = False

    print(f"[RESET] bulk_assert complete for {dev_name!r}")
    return success


def reset_control_bulk_deassert(dev_name: str, count: int) -> bool:
    """Deassert multiple reset controls — like reset_control_bulk_deassert().

    Returns:
        True if all lines were deasserted successfully.
    """
    cons = _get_consumer(dev_name)
    ctrl_name = cons.controller_name
    ctrl = _get_controller(ctrl_name)

    success = True
    for i in range(count):
        if i < len(ctrl.resets):
            line = ctrl.resets[i]
            if line._consumer == dev_name:
                if line.active_low:
                    line.asserted = True
                else:
                    line.asserted = False
                print(
                    f"[RESET] bulk_deassert: {dev_name!r} line {i} "
                    f"({line.name!r}) -> asserted={line.asserted}"
                )
            else:
                print(
                    f"[RESET] bulk_deassert: line {i} not bound to "
                    f"{dev_name!r}, skipping"
                )
                success = False

    print(f"[RESET] bulk_deassert complete for {dev_name!r}")
    return success


# ---------------------------------------------------------------------------
# Reset Controller List
# ---------------------------------------------------------------------------
def reset_control_list() -> Dict[str, Dict[str, Any]]:
    """List all registered reset controllers and their lines.

    Returns:
        Dictionary with controller names as keys and summaries as values.
    """
    summary: Dict[str, Dict[str, Any]] = {}
    for name, ctrl in _controllers.items():
        line_info = []
        for line in ctrl.resets:
            line_info.append({
                "index": line.index,
                "name": line.name,
                "asserted": line.asserted,
                "active_low": line.active_low,
                "consumer": line._consumer or "(none)",
            })
        summary[name] = {
            "id": ctrl.id,
            "nr_resets": ctrl.nr_resets,
            "lines": line_info,
        }

    print(f"\n=== Reset Controller List ({len(summary)} controllers) ===")
    for name, info in summary.items():
        print(f"  {name!r} (id={info['id']}, {info['nr_resets']} lines):")
        for ln in info["lines"]:
            state = "ASSERTED" if ln["asserted"] else "deasserted"
            print(
                f"    [{ln['index']}] {ln['name']!r}: {state} "
                f"consumer={ln['consumer']!r}"
            )
    print("========================================\n")
    return summary


# ---------------------------------------------------------------------------
# Built-in Reset Controllers
# ---------------------------------------------------------------------------
class SimpleResetController(ResetController):
    """Simple reset controller — one line per reset.

    Typical for simple SoCs where each peripheral has a dedicated
    reset line with no GPIO or PMIC involvement.
    """

    def __init__(self, name: str, nr_resets: int) -> None:
        super().__init__(name=name, nr_resets=nr_resets)
        self._ops = {
            "assert": self._simple_assert,
            "deassert": self._simple_deassert,
        }

    @staticmethod
    def _simple_assert(line: ResetLine) -> None:
        line.asserted = True

    @staticmethod
    def _simple_deassert(line: ResetLine) -> None:
        line.asserted = False


class GpioResetController(ResetController):
    """GPIO-based reset controller.

    Uses a GPIO line to drive the reset signal of one or more
    peripherals.  Supports active-low reset lines.
    """

    def __init__(
        self, name: str, nr_resets: int, gpio_base: int = 0
    ) -> None:
        super().__init__(name=name, nr_resets=nr_resets)
        self.gpio_base: int = gpio_base
        self._ops = {
            "assert": self._gpio_assert,
            "deassert": self._gpio_deassert,
            "get_gpio": self._gpio_get,
        }

    @staticmethod
    def _gpio_assert(line: ResetLine) -> None:
        if line.active_low:
            line.asserted = False  # drive low = assert on active-low
        else:
            line.asserted = True   # drive high = assert on active-high

    @staticmethod
    def _gpio_deassert(line: ResetLine) -> None:
        if line.active_low:
            line.asserted = True   # drive high = deassert on active-low
        else:
            line.asserted = False  # drive low = deassert on active-high

    @staticmethod
    def _gpio_get(line: ResetLine) -> int:
        return line.index


class PmicResetController(ResetController):
    """PMIC reset controller.

    Resets connected peripherals through the Power Management IC.
    Typically supports longer reset pulse durations and can trigger
    full system resets.
    """

    def __init__(
        self, name: str, nr_resets: int, pmic_addr: int = 0x50
    ) -> None:
        super().__init__(name=name, nr_resets=nr_resets)
        self.pmic_addr: int = pmic_addr
        self._ops = {
            "assert": self._pmic_assert,
            "deassert": self._pmic_deassert,
            "system_reset": self._pmic_system_reset,
        }

    @staticmethod
    def _pmic_assert(line: ResetLine) -> None:
        line.asserted = True

    @staticmethod
    def _pmic_deassert(line: ResetLine) -> None:
        line.asserted = False

    def _pmic_system_reset(self) -> bool:
        print(
            f"[RESET] PMIC system reset via {self.name!r} "
            f"(addr=0x{self.pmic_addr:02x})"
        )
        return True


# ---------------------------------------------------------------------------
# Dump / Debug
# ---------------------------------------------------------------------------
def reset_dump_state() -> None:
    """Print full reset subsystem state."""
    print("\n=== RESET Subsystem State ===")
    print(f"Controllers: {len(_controllers)}")
    for ctrl in _controllers.values():
        print(
            f"  [{ctrl.name!r}] id={ctrl.id}, nr_resets={ctrl.nr_resets}, "
            f"registered={ctrl._is_registered}"
        )
        for line in ctrl.resets:
            state = "ASSERTED" if line.asserted else "deasserted"
            consumer = line._consumer or "(none)"
            print(
                f"    [{line.index}] {line.name!r}: {state} "
                f"active_low={line.active_low} consumer={consumer!r}"
            )
    if _consumers:
        print(f"Consumers: {len(_consumers)}")
        for dev_name, cons in _consumers.items():
            print(
                f"  {dev_name!r} -> {cons.controller_name!r}:"
                f"{cons.reset_index} bound={cons._is_bound}"
            )
    print("==============================\n")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def demo() -> None:
    print("=" * 64)
    print("  UmerOS Reset Controller Subsystem Demo")
    print("=" * 64)

    # -- Create built-in controllers --
    print("\n--- Creating Reset Controllers ---")
    simple = SimpleResetController(name="simple-rst", nr_resets=8)
    gpio = GpioResetController(name="gpio-rst", nr_resets=4, gpio_base=0x20)
    pmic = PmicResetController(name="pmic-rst", nr_resets=2, pmic_addr=0x58)

    # -- Register controllers --
    print("\n--- Registering Controllers ---")
    reset_controller_register(simple)
    reset_controller_register(gpio)
    reset_controller_register(pmic)

    # -- List all controllers --
    reset_control_list()

    # -- Consumer devices acquire reset controls --
    print("\n--- Consumer Devices Get Reset Controls ---")
    reset_control_get("spi-master", "simple-rst", 0)
    reset_control_get("uart0", "simple-rst", 1)
    reset_control_get("eth0", "simple-rst", 2)
    reset_control_get("i2c-bus", "gpio-rst", 0)
    reset_control_get("usb-hub", "gpio-rst", 1)
    reset_control_get("audio-codec", "pmic-rst", 0)
    reset_control_get("display-pmic", "pmic-rst", 1)

    # -- Assert / Deassert cycle --
    print("\n--- Assert / Deassert Cycle ---")
    reset_control_assert("spi-master")
    reset_control_status("spi-master")
    reset_control_deassert("spi-master")
    reset_control_status("spi-master")

    reset_control_assert("uart0")
    reset_control_status("uart0")
    reset_control_deassert("uart0")
    reset_control_status("uart0")

    # -- Full reset cycle --
    print("\n--- Full Reset Cycle (assert -> deassert) ---")
    reset_control_reset("eth0")

    # -- GPIO reset with active-low --
    print("\n--- GPIO Reset (active-low) ---")
    line = _lines.get("gpio-rst:0")
    if line:
        line.active_low = True
        print(f"  Set gpio-rst:0 to active-low")

    reset_control_assert("i2c-bus")
    reset_control_status("i2c-bus")
    reset_control_deassert("i2c-bus")
    reset_control_status("i2c-bus")

    # -- PMIC reset --
    print("\n--- PMIC Reset ---")
    reset_control_reset("audio-codec")
    reset_control_reset("display-pmic")

    # -- Bulk reset operations --
    print("\n--- Bulk Reset Operations ---")
    bulk_dev = "spi-master"
    print(f"  Bulk assert 3 lines for {bulk_dev!r}:")
    reset_control_bulk_assert(bulk_dev, 3)

    print(f"  Bulk deassert 3 lines for {bulk_dev!r}:")
    reset_control_bulk_deassert(bulk_dev, 3)

    # -- Status overview --
    print("\n--- Reset Status Overview ---")
    for dev_name in ["spi-master", "uart0", "eth0", "i2c-bus",
                     "usb-hub", "audio-codec", "display-pmic"]:
        reset_control_status(dev_name)

    # -- Final state dump --
    reset_dump_state()

    # -- Release controls --
    print("\n--- Release Reset Controls ---")
    reset_control_put("spi-master")
    reset_control_put("uart0")
    reset_control_put("eth0")
    reset_control_put("i2c-bus")
    reset_control_put("usb-hub")
    reset_control_put("audio-codec")
    reset_control_put("display-pmic")

    # -- Error paths --
    print("\n--- Error Paths ---")
    try:
        _get_controller("nonexistent")
    except KeyError as e:
        print(f"  caught: {e}")

    reset_control_get("double-bind", "simple-rst", 0)
    reset_control_get("double-bind", "simple-rst", 0)  # already bound

    reset_control_put("no-device")  # no-op

    try:
        reset_control_assert("orphan-device")
    except KeyError as e:
        print(f"  caught: {e}")

    try:
        _get_line("simple-rst", 99)
    except KeyError as e:
        print(f"  caught: {e}")

    # -- Unregister controllers --
    print("\n--- Unregister Controllers ---")
    reset_controller_unregister("simple-rst")
    reset_controller_unregister("gpio-rst")
    reset_controller_unregister("pmic-rst")

    reset_control_list()

    print("=== Demo Complete ===\n")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo()
