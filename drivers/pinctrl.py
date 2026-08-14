"""
UmerOS Pin Control Subsystem
============================
Kernel-like pin multiplexing and configuration framework.
Manages pin states, muxing, drive strength, and pull resistors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

try:
    from .device import Device
except ImportError:
    Device = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Pin Control States
# ---------------------------------------------------------------------------
PINCTRL_STATE_DEFAULT: str = "default"
PINCTRL_STATE_IDLE: str = "idle"
PINCTRL_STATE_SLEEP: str = "sleep"
PINCTRL_STATE_STARTUP: str = "startup"
PINCTRL_STATE_GPIO: str = "gpio"


# ---------------------------------------------------------------------------
# Core Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class PinDesc:
    """Pin descriptor."""
    number: int
    name: str
    owner: str = ""           # current owner (GPIO, UART, SPI, etc.)
    _is_valid: bool = True


@dataclass
class PinGroup:
    """Named group of pins."""
    name: str
    pins: list                # list of pin numbers
    num_pins: int = 0
    function: str = ""        # function assigned to this group
    config: dict = field(default_factory=dict)  # drive strength, pull-up/down, etc.

    def __post_init__(self) -> None:
        if self.num_pins == 0:
            self.num_pins = len(self.pins)


@dataclass
class PinFunction:
    """Pin function mapping."""
    name: str
    groups: list              # list of group names
    num_groups: int = 0

    def __post_init__(self) -> None:
        if self.num_groups == 0:
            self.num_groups = len(self.groups)


@dataclass
class PinConf:
    """Pin configuration value."""
    drive_strength: int = 2   # mA
    pull_up: bool = False
    pull_down: bool = False
    open_drain: bool = False
    schmitt_trigger: bool = False
    slew_rate: int = 0        # 0=fast, 1=slow
    debounce: int = 0         # ms
    low_power_enable: bool = False


@dataclass
class PinState:
    """Pin state (set of configs for a device)."""
    name: str
    configs: dict = field(default_factory=dict)  # pin_name -> PinConf


@dataclass
class PinController:
    """Pin controller (chip)."""
    name: str
    base: int                 # base pin number
    npins: int                # number of pins
    pins: list = field(default_factory=list)        # PinDesc list
    groups: dict = field(default_factory=dict)      # name -> PinGroup
    functions: dict = field(default_factory=dict)   # name -> PinFunction
    _is_registered: bool = False


@dataclass
class PinmuxOps:
    """Pinmux operations."""
    get_functions_count: Callable | None = None
    get_function_name: Callable | None = None
    enable: Callable | None = None
    disable: Callable | None = None
    gpio_request_enable: Callable | None = None
    gpio_disable_free: Callable | None = None
    gpio_set_direction: Callable | None = None


@dataclass
class PinconfOps:
    """Pin configuration operations."""
    pin_config_get: Callable | None = None
    pin_config_set: Callable | None = None
    pin_config_dbg_show: Callable | None = None


# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_controllers: dict[str, PinController] = {}
_device_handles: dict[str, str] = {}   # dev_name -> controller_name
_pin_configs: dict[tuple[str, int], PinConf] = {}   # (ctrl, pin) -> PinConf
_pin_owners: dict[tuple[str, int], str] = {}        # (ctrl, pin) -> owner
_gpio_ranges: dict[str, dict] = {}    # dev_name -> {base, npins}


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------
def _get_controller(name: str) -> PinController:
    ctrl = _controllers.get(name)
    if ctrl is None:
        raise KeyError(f"[PINCTRL] controller {name!r} not found")
    return ctrl


def _resolve_pin(ctrl: PinController, pin: int) -> PinDesc:
    idx = pin - ctrl.base
    if idx < 0 or idx >= ctrl.npins:
        raise ValueError(
            f"[PINCTRL] pin {pin} out of range [{ctrl.base}, "
            f"{ctrl.base + ctrl.npins - 1}] on {ctrl.name!r}"
        )
    return ctrl.pins[idx]


def _conf_key(ctrl_name: str, pin: int) -> tuple[str, int]:
    return (ctrl_name, pin)


def _ensure_conf(ctrl_name: str, pin: int) -> PinConf:
    key = _conf_key(ctrl_name, pin)
    if key not in _pin_configs:
        _pin_configs[key] = PinConf()
    return _pin_configs[key]


# ---------------------------------------------------------------------------
# Pin Controller Registration
# ---------------------------------------------------------------------------
def pinctrl_register(controller: PinController) -> bool:
    """Register pin controller — like pinctrl_register()."""
    if controller.name in _controllers:
        print(f"[PINCTRL] ERROR: controller {controller.name!r} already registered")
        return False
    if not controller.pins:
        for i in range(controller.npins):
            controller.pins.append(
                PinDesc(number=controller.base + i, name=f"pin{controller.base + i}")
            )
    controller._is_registered = True
    _controllers[controller.name] = controller
    print(f"[PINCTRL] registered controller: {controller.name!r} "
          f"({controller.npins} pins, base={controller.base})")
    return True


def pinctrl_unregister(name: str) -> bool:
    """Unregister pin controller."""
    ctrl = _controllers.pop(name, None)
    if ctrl is None:
        print(f"[PINCTRL] ERROR: no controller {name!r}")
        return False
    ctrl._is_registered = False
    keys_to_remove = [k for k in _pin_configs if k[0] == name]
    for k in keys_to_remove:
        del _pin_configs[k]
    keys_to_remove = [k for k in _pin_owners if k[0] == name]
    for k in keys_to_remove:
        del _pin_owners[k]
    print(f"[PINCTRL] unregistered controller: {name!r}")
    return True


# ---------------------------------------------------------------------------
# Pinctrl Handle (per-device)
# ---------------------------------------------------------------------------
def pinctrl_get(dev_name: str) -> Optional[str]:
    """Get pinctrl handle for device — returns controller name or None."""
    ctrl_name = _device_handles.get(dev_name)
    if ctrl_name is None:
        print(f"[PINCTRL] ERROR: no pinctrl handle for device {dev_name!r}")
        return None
    print(f"[PINCTRL] get: device {dev_name!r} -> controller {ctrl_name!r}")
    return ctrl_name


def pinctrl_put(dev_name: str) -> None:
    """Release pinctrl handle."""
    if dev_name in _device_handles:
        ctrl_name = _device_handles.pop(dev_name)
        print(f"[PINCTRL] put: released handle for {dev_name!r} (was {ctrl_name!r})")
    else:
        print(f"[PINCTRL] put: no handle for {dev_name!r}, nothing to release")


def pinctrl_add_gpio_range(dev_name: str, base: int, npins: int) -> bool:
    """Add GPIO range to pinctrl."""
    if dev_name not in _device_handles:
        print(f"[PINCTRL] ERROR: device {dev_name!r} has no pinctrl handle")
        return False
    _gpio_ranges[dev_name] = {"base": base, "npins": npins}
    print(f"[PINCTRL] added GPIO range for {dev_name!r}: base={base}, npins={npins}")
    return True


# ---------------------------------------------------------------------------
# Pin State Management
# ---------------------------------------------------------------------------
def pinctrl_lookup_state(dev_name: str, state_name: str) -> Optional[PinState]:
    """Look up pin state."""
    ctrl_name = _device_handles.get(dev_name)
    if ctrl_name is None:
        print(f"[PINCTRL] ERROR: device {dev_name!r} has no pinctrl handle")
        return None
    ctrl = _controllers.get(ctrl_name)
    if ctrl is None:
        return None
    state = PinState(name=state_name)
    print(f"[PINCTRL] lookup_state: {dev_name!r} state={state_name!r} on {ctrl_name!r}")
    return state


def pinctrl_select_state(dev_name: str, state_name: str) -> bool:
    """Select pin state — like pinctrl_select_state()."""
    ctrl_name = _device_handles.get(dev_name)
    if ctrl_name is None:
        print(f"[PINCTRL] ERROR: device {dev_name!r} has no pinctrl handle")
        return False
    ctrl = _controllers.get(ctrl_name)
    if ctrl is None:
        print(f"[PINCTRL] ERROR: controller {ctrl_name!r} not found")
        return False
    print(f"[PINCTRL] select_state: {dev_name!r} -> {state_name!r} on {ctrl_name!r}")
    return True


def pinctrl_init_default_state(dev_name: str) -> bool:
    """Initialize default state."""
    return pinctrl_select_state(dev_name, PINCTRL_STATE_DEFAULT)


# ---------------------------------------------------------------------------
# GPIO Pin Operations
# ---------------------------------------------------------------------------
def pinctrl_gpio_request(controller_name: str, pin: int) -> bool:
    """Request a pin for GPIO."""
    ctrl = _get_controller(controller_name)
    desc = _resolve_pin(ctrl, pin)
    key = _conf_key(controller_name, pin)
    if key in _pin_owners and _pin_owners[key]:
        print(f"[PINCTRL] ERROR: pin {pin} ({desc.name!r}) already owned by "
              f"{_pin_owners[key]!r}")
        return False
    _pin_owners[key] = "GPIO"
    desc.owner = "GPIO"
    print(f"[PINCTRL] gpio_request: pin {pin} ({desc.name!r}) on {controller_name!r}")
    return True


def pinctrl_gpio_free(controller_name: str, pin: int) -> bool:
    """Free a GPIO pin."""
    ctrl = _get_controller(controller_name)
    desc = _resolve_pin(ctrl, pin)
    key = _conf_key(controller_name, pin)
    prev = _pin_owners.pop(key, None)
    desc.owner = ""
    print(f"[PINCTRL] gpio_free: pin {pin} ({desc.name!r}) on {controller_name!r}"
          f" (was {prev!r})")
    return True


def pinctrl_gpio_direction_input(controller_name: str, pin: int) -> bool:
    """Set pin to input."""
    ctrl = _get_controller(controller_name)
    desc = _resolve_pin(ctrl, pin)
    key = _conf_key(controller_name, pin)
    if key not in _pin_owners or not _pin_owners[key]:
        print(f"[PINCTRL] ERROR: pin {pin} not requested before set direction")
        return False
    print(f"[PINCTRL] gpio_direction_input: pin {pin} ({desc.name!r}) on "
          f"{controller_name!r}")
    return True


def pinctrl_gpio_direction_output(controller_name: str, pin: int, value: int = 0) -> bool:
    """Set pin to output."""
    ctrl = _get_controller(controller_name)
    desc = _resolve_pin(ctrl, pin)
    key = _conf_key(controller_name, pin)
    if key not in _pin_owners or not _pin_owners[key]:
        print(f"[PINCTRL] ERROR: pin {pin} not requested before set direction")
        return False
    print(f"[PINCTRL] gpio_direction_output: pin {pin} ({desc.name!r}) value={value} "
          f"on {controller_name!r}")
    return True


# ---------------------------------------------------------------------------
# Pin Configuration Functions
# ---------------------------------------------------------------------------
def pin_config_set(controller_name: str, pin: int, conf: PinConf) -> bool:
    """Set pin configuration."""
    ctrl = _get_controller(controller_name)
    _resolve_pin(ctrl, pin)
    key = _conf_key(controller_name, pin)
    _pin_configs[key] = conf
    print(f"[PINCTRL] config_set: pin {pin} on {controller_name!r}: "
          f"drive={conf.drive_strength}mA, pu={conf.pull_up}, pd={conf.pull_down}, "
          f"od={conf.open_drain}, schmitt={conf.schmitt_trigger}, "
          f"slew={conf.slew_rate}, debounce={conf.debounce}ms, "
          f"lp={conf.low_power_enable}")
    return True


def pin_config_get(controller_name: str, pin: int) -> Optional[PinConf]:
    """Get pin configuration."""
    ctrl = _get_controller(controller_name)
    _resolve_pin(ctrl, pin)
    key = _conf_key(controller_name, pin)
    conf = _pin_configs.get(key)
    if conf is None:
        conf = PinConf()
        _pin_configs[key] = conf
    print(f"[PINCTRL] config_get: pin {pin} on {controller_name!r}: "
          f"drive={conf.drive_strength}mA, pu={conf.pull_up}, pd={conf.pull_down}")
    return conf


def pin_config_set_drive_strength(controller_name: str, pin: int, mA: int) -> bool:
    """Set drive strength."""
    conf = _ensure_conf(controller_name, pin)
    conf.drive_strength = mA
    print(f"[PINCTRL] drive_strength: pin {pin} on {controller_name!r} -> {mA}mA")
    return True


def pin_config_set_pull_up(controller_name: str, pin: int) -> bool:
    """Enable pull-up."""
    conf = _ensure_conf(controller_name, pin)
    conf.pull_up = True
    conf.pull_down = False
    print(f"[PINCTRL] pull_up: pin {pin} on {controller_name!r} -> enabled")
    return True


def pin_config_set_pull_down(controller_name: str, pin: int) -> bool:
    """Enable pull-down."""
    conf = _ensure_conf(controller_name, pin)
    conf.pull_down = True
    conf.pull_up = False
    print(f"[PINCTRL] pull_down: pin {pin} on {controller_name!r} -> enabled")
    return True


def pin_config_set_open_drain(controller_name: str, pin: int) -> bool:
    """Enable open-drain."""
    conf = _ensure_conf(controller_name, pin)
    conf.open_drain = True
    print(f"[PINCTRL] open_drain: pin {pin} on {controller_name!r} -> enabled")
    return True


def pin_config_set_schmitt(controller_name: str, pin: int) -> bool:
    """Enable schmitt trigger."""
    conf = _ensure_conf(controller_name, pin)
    conf.schmitt_trigger = True
    print(f"[PINCTRL] schmitt: pin {pin} on {controller_name!r} -> enabled")
    return True


def pin_config_set_slew_rate(controller_name: str, pin: int, rate: int) -> bool:
    """Set slew rate (0=fast, 1=slow)."""
    if rate not in (0, 1):
        print(f"[PINCTRL] ERROR: invalid slew_rate {rate}, must be 0 or 1")
        return False
    conf = _ensure_conf(controller_name, pin)
    conf.slew_rate = rate
    label = "fast" if rate == 0 else "slow"
    print(f"[PINCTRL] slew_rate: pin {pin} on {controller_name!r} -> {label}")
    return True


# ---------------------------------------------------------------------------
# Pin Mapping Functions
# ---------------------------------------------------------------------------
def pinctrl_pin_name_to_pin(controller_name: str, pin_name: str) -> Optional[int]:
    """Convert pin name to number."""
    ctrl = _get_controller(controller_name)
    for desc in ctrl.pins:
        if desc.name == pin_name:
            print(f"[PINCTRL] name_to_pin: {pin_name!r} -> {desc.number} on "
                  f"{controller_name!r}")
            return desc.number
    print(f"[PINCTRL] ERROR: pin {pin_name!r} not found on {controller_name!r}")
    return None


def pinctrl_pin_get_name(controller_name: str, pin: int) -> Optional[str]:
    """Get pin name from number."""
    ctrl = _get_controller(controller_name)
    desc = _resolve_pin(ctrl, pin)
    print(f"[PINCTRL] pin_get_name: {pin} -> {desc.name!r} on {controller_name!r}")
    return desc.name


def pinctrl_get_group_pins(controller_name: str, group_name: str) -> Optional[list]:
    """Get pins in a group."""
    ctrl = _get_controller(controller_name)
    group = ctrl.groups.get(group_name)
    if group is None:
        print(f"[PINCTRL] ERROR: group {group_name!r} not found on {controller_name!r}")
        return None
    print(f"[PINCTRL] group_pins: {group_name!r} -> {group.pins} on {controller_name!r}")
    return list(group.pins)


def pinctrl_get_group_name(controller_name: str, pin: int) -> Optional[str]:
    """Get group containing pin."""
    ctrl = _get_controller(controller_name)
    for grp_name, grp in ctrl.groups.items():
        if pin in grp.pins:
            print(f"[PINCTRL] pin_to_group: pin {pin} -> group {grp_name!r} on "
                  f"{controller_name!r}")
            return grp_name
    print(f"[PINCTRL] ERROR: pin {pin} not in any group on {controller_name!r}")
    return None


# ---------------------------------------------------------------------------
# Pinmux Helpers
# ---------------------------------------------------------------------------
def pinctrl_mux_enable(controller_name: str, function_name: str,
                       group_name: str) -> bool:
    """Enable a function on a group — calls pinmux_ops.enable if present."""
    ctrl = _get_controller(controller_name)
    func = ctrl.functions.get(function_name)
    if func is None:
        print(f"[PINCTRL] ERROR: function {function_name!r} not found on "
              f"{controller_name!r}")
        return False
    group = ctrl.groups.get(group_name)
    if group is None:
        print(f"[PINCTRL] ERROR: group {group_name!r} not found on "
              f"{controller_name!r}")
        return False
    if group_name not in func.groups:
        print(f"[PINCTRL] ERROR: group {group_name!r} not in function "
              f"{function_name!r}")
        return False
    for pin_num in group.pins:
        key = _conf_key(controller_name, pin_num)
        _pin_owners[key] = function_name
        idx = pin_num - ctrl.base
        if 0 <= idx < len(ctrl.pins):
            ctrl.pins[idx].owner = function_name
    group.function = function_name
    print(f"[PINCTRL] mux_enable: {function_name!r} on group {group_name!r} "
          f"(pins {group.pins}) on {controller_name!r}")
    return True


def pinctrl_mux_disable(controller_name: str, group_name: str) -> bool:
    """Disable mux on a group."""
    ctrl = _get_controller(controller_name)
    group = ctrl.groups.get(group_name)
    if group is None:
        print(f"[PINCTRL] ERROR: group {group_name!r} not found on "
              f"{controller_name!r}")
        return False
    for pin_num in group.pins:
        key = _conf_key(controller_name, pin_num)
        _pin_owners.pop(key, None)
        idx = pin_num - ctrl.base
        if 0 <= idx < len(ctrl.pins):
            ctrl.pins[idx].owner = ""
    group.function = ""
    print(f"[PINCTRL] mux_disable: group {group_name!r} on {controller_name!r}")
    return True


# ---------------------------------------------------------------------------
# Dump / Debug
# ---------------------------------------------------------------------------
def pinctrl_dump_state() -> None:
    """Print full pin control subsystem state."""
    print("\n=== PINCTRL Subsystem State ===")
    print(f"Controllers: {len(_controllers)}")
    for ctrl in _controllers.values():
        print(f"  [{ctrl.name!r}] base={ctrl.base}, npins={ctrl.npins}")
        for desc in ctrl.pins:
            owner = desc.owner or "unused"
            print(f"    pin {desc.number}: {desc.name!r} owner={owner!r}")
        if ctrl.groups:
            print(f"    groups:")
            for gname, grp in ctrl.groups.items():
                print(f"      {gname!r}: pins={grp.pins}, func={grp.function!r}")
        if ctrl.functions:
            print(f"    functions:")
            for fname, func in ctrl.functions.items():
                print(f"      {fname!r}: groups={func.groups}")
    if _device_handles:
        print(f"Device handles: {len(_device_handles)}")
        for dev, ctrl in _device_handles.items():
            print(f"  {dev!r} -> {ctrl!r}")
    if _gpio_ranges:
        print(f"GPIO ranges: {len(_gpio_ranges)}")
        for dev, rng in _gpio_ranges.items():
            print(f"  {dev!r}: base={rng['base']}, npins={rng['npins']}")
    print("================================\n")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def demo() -> None:
    print("=" * 64)
    print("  UmerOS Pin Control Subsystem Demo")
    print("=" * 64)

    # -- Create a pin controller for an STM32-like MCU (64 pins) --
    print("\n--- Creating STM32-like Pin Controller ---")
    stm32 = PinController(name="stm32g4", base=0, npins=64)
    gpio_names = ["PA0", "PA1", "PA2", "PA3", "PA4", "PA5", "PA6", "PA7",
                  "PB0", "PB1", "PB2", "PB3", "PB4", "PB5", "PB6", "PB7",
                  "PC0", "PC1", "PC2", "PC3", "PC4", "PC5", "PC6", "PC7",
                  "PD0", "PD1", "PD2", "PD3", "PD4", "PD5", "PD6", "PD7",
                  "PE0", "PE1", "PE2", "PE3", "PE4", "PE5", "PE6", "PE7",
                  "PF0", "PF1", "PF2", "PF3", "PF4", "PF5", "PF6", "PF7"]
    for i in range(stm32.npins):
        if i < len(gpio_names):
            stm32.pins.append(PinDesc(number=i, name=gpio_names[i]))
        else:
            stm32.pins.append(PinDesc(number=i, name=f"pin{i}"))

    # -- Define pin groups --
    print("\n--- Defining Pin Groups ---")
    stm32.groups["uart1_tx"] = PinGroup(name="uart1_tx", pins=[9], function="uart1")
    stm32.groups["uart1_rx"] = PinGroup(name="uart1_rx", pins=[10], function="uart1")
    stm32.groups["uart1"] = PinGroup(name="uart1", pins=[9, 10], function="uart1")
    stm32.groups["spi1_mosi"] = PinGroup(name="spi1_mosi", pins=[5], function="spi1")
    stm32.groups["spi1_miso"] = PinGroup(name="spi1_miso", pins=[6], function="spi1")
    stm32.groups["spi1_sck"] = PinGroup(name="spi1_sck", pins=[4], function="spi1")
    stm32.groups["spi1"] = PinGroup(name="spi1", pins=[4, 5, 6], function="spi1")
    stm32.groups["i2c1_sda"] = PinGroup(name="i2c1_sda", pins=[3], function="i2c1")
    stm32.groups["i2c1_scl"] = PinGroup(name="i2c1_scl", pins=[2], function="i2c1")
    stm32.groups["i2c1"] = PinGroup(name="i2c1", pins=[2, 3], function="i2c1")

    # -- Define functions --
    print("\n--- Defining Functions ---")
    stm32.functions["gpio"] = PinFunction(
        name="gpio",
        groups=[f"gpio{i}" for i in range(8)] + [f"gpio{i}" for i in range(8, 64)],
    )
    stm32.functions["uart1"] = PinFunction(
        name="uart1",
        groups=["uart1", "uart1_tx", "uart1_rx"],
    )
    stm32.functions["spi1"] = PinFunction(
        name="spi1",
        groups=["spi1", "spi1_mosi", "spi1_miso", "spi1_sck"],
    )
    stm32.functions["i2c1"] = PinFunction(
        name="i2c1",
        groups=["i2c1", "i2c1_sda", "i2c1_scl"],
    )

    # -- Register controller --
    print("\n--- Registering Controller ---")
    pinctrl_register(stm32)

    # -- Device requests pinctrl --
    print("\n--- Device Requests Pinctrl ---")
    uart_dev = "stm32-uart1"
    spi_dev = "stm32-spi1"
    i2c_dev = "stm32-i2c1"
    _device_handles[uart_dev] = "stm32g4"
    _device_handles[spi_dev] = "stm32g4"
    _device_handles[i2c_dev] = "stm32g4"
    print(f"[PINCTRL] assigned {uart_dev!r} -> stm32g4")
    print(f"[PINCTRL] assigned {spi_dev!r} -> stm32g4")
    print(f"[PINCTRL] assigned {i2c_dev!r} -> stm32g4")

    # -- Add GPIO ranges --
    print("\n--- Adding GPIO Ranges ---")
    pinctrl_add_gpio_range(uart_dev, base=0, npins=16)
    pinctrl_add_gpio_range(spi_dev, base=0, npins=16)

    # -- Pinmux: switch UART1 pins to UART function --
    print("\n--- Pinmux: Enable UART1 ---")
    pinctrl_mux_enable("stm32g4", "uart1", "uart1")
    pinctrl_mux_disable("stm32g4", "uart1")

    # -- Pinmux: switch SPI1 pins --
    print("\n--- Pinmux: Enable SPI1 ---")
    pinctrl_mux_enable("stm32g4", "spi1", "spi1")
    pinctrl_mux_disable("stm32g4", "spi1")

    # -- Pinmux: switch I2C1 pins --
    print("\n--- Pinmux: Enable I2C1 ---")
    pinctrl_mux_enable("stm32g4", "i2c1", "i2c1")
    pinctrl_mux_disable("stm32g4", "i2c1")

    # -- GPIO request / direction --
    print("\n--- GPIO Request & Direction ---")
    pinctrl_gpio_request("stm32g4", 24)   # PD0
    pinctrl_gpio_direction_input("stm32g4", 24)
    pinctrl_gpio_request("stm32g4", 25)   # PD1
    pinctrl_gpio_direction_output("stm32g4", 25, value=1)
    pinctrl_gpio_request("stm32g4", 40)   # PF0
    pinctrl_gpio_direction_output("stm32g4", 40, value=0)

    # -- Pin configuration --
    print("\n--- Pin Configuration ---")
    conf = PinConf(drive_strength=8, pull_up=True, open_drain=True)
    pin_config_set("stm32g4", 9, conf)

    pin_config_set_drive_strength("stm32g4", 10, mA=4)
    pin_config_set_pull_up("stm32g4", 10)
    pin_config_set_pull_down("stm32g4", 40)
    pin_config_set_schmitt("stm32g4", 24)
    pin_config_set_slew_rate("stm32g4", 25, rate=1)
    pin_config_get("stm32g4", 9)
    pin_config_get("stm32g4", 10)

    # -- Pin name <-> number mapping --
    print("\n--- Pin Name Mapping ---")
    pinctrl_pin_name_to_pin("stm32g4", "PA0")
    pinctrl_pin_name_to_pin("stm32g4", "PB3")
    pinctrl_pin_get_name("stm32g4", 0)
    pinctrl_pin_get_name("stm32g4", 10)

    # -- Group queries --
    print("\n--- Group Queries ---")
    pinctrl_get_group_pins("stm32g4", "spi1")
    pinctrl_get_group_pins("stm32g4", "i2c1")
    pinctrl_get_group_name("stm32g4", 9)
    pinctrl_get_group_name("stm32g4", 5)

    # -- State transitions --
    print("\n--- State Transitions: default -> sleep -> default ---")
    pinctrl_select_state(uart_dev, PINCTRL_STATE_DEFAULT)
    pinctrl_select_state(uart_dev, PINCTRL_STATE_SLEEP)
    pinctrl_select_state(uart_dev, PINCTRL_STATE_DEFAULT)

    print("\n--- State Transitions: startup -> idle -> gpio ---")
    pinctrl_select_state(spi_dev, PINCTRL_STATE_STARTUP)
    pinctrl_select_state(spi_dev, PINCTRL_STATE_IDLE)
    pinctrl_select_state(spi_dev, PINCTRL_STATE_GPIO)

    # -- Look up state --
    print("\n--- Lookup State ---")
    pinctrl_lookup_state(i2c_dev, PINCTRL_STATE_SLEEP)

    # -- Handle put --
    print("\n--- Release Handle ---")
    pinctrl_put(uart_dev)

    # -- Final dump --
    pinctrl_dump_state()

    # -- GPIO free --
    print("\n--- GPIO Free ---")
    pinctrl_gpio_free("stm32g4", 24)
    pinctrl_gpio_free("stm32g4", 25)

    # -- Error paths --
    print("\n--- Error Paths ---")
    try:
        _get_controller("nonexistent")
    except KeyError as e:
        print(f"  caught: {e}")

    pinctrl_gpio_request("stm32g4", 9)     # already owned by uart1
    pinctrl_select_state("no-device", PINCTRL_STATE_DEFAULT)
    pinctrl_gpio_direction_output("stm32g4", 24, value=0)  # not requested
    pin_config_set_slew_rate("stm32g4", 9, rate=99)         # invalid rate

    # -- Unregister --
    print("\n--- Unregister Controller ---")
    pinctrl_unregister("stm32g4")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo()
