"""
UmerOS Regulator Framework
===========================
Kernel Voltage and Current Regulator subsystem.
Implements regulator supplies, consumers, constraints,
and power management operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regulator Constants
# ---------------------------------------------------------------------------
REGULATOR_MODE_IDLE: int = 0x01
REGULATOR_MODE_NORMAL: int = 0x02
REGULATOR_MODE_FAST: int = 0x04
REGULATOR_MODE_STANDBY: int = 0x08

REGULATOR_STATUS_OFF: int = 0
REGULATOR_STATUS_ON: int = 1

REGULATOR_CHANGE_VOLTAGE: int = 0x01
REGULATOR_CHANGE_CURRENT: int = 0x02
REGULATOR_CHANGE_MODE: int = 0x04
REGULATOR_CHANGE_STATUS: int = 0x08
REGULATOR_CHANGE_DRMS: int = 0x10

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_supplies: Dict[str, RegulatorSupply] = {}
_consumers: Dict[str, RegulatorConsumer] = {}
_regulators: Dict[str, Regulator] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class RegulatorConstraints:
    """Regulator operating constraints"""
    min_uV: int = 0
    max_uV: int = 0
    min_uA: int = 0
    max_uA: int = 0
    valid_modes: int = REGULATOR_MODE_NORMAL
    valid_ops: int = REGULATOR_CHANGE_VOLTAGE | REGULATOR_CHANGE_STATUS
    always_on: bool = False
    boot_on: bool = False
    apply_uV: int = 0


@dataclass
class RegulatorOps:
    """Regulator operations"""
    list_voltage: Optional[Callable] = None
    set_voltage: Optional[Callable] = None
    get_voltage: Optional[Callable] = None
    set_current: Optional[Callable] = None
    get_current: Optional[Callable] = None
    enable: Optional[Callable] = None
    disable: Optional[Callable] = None
    is_enabled: Optional[Callable] = None
    set_mode: Optional[Callable] = None
    get_mode: Optional[Callable] = None


@dataclass
class Regulator:
    """Voltage/current regulator"""
    name: str
    supply_name: str = ""
    constraints: RegulatorConstraints = field(default_factory=RegulatorConstraints)
    ops: RegulatorOps = field(default_factory=RegulatorOps)
    is_registered: bool = False
    is_enabled: bool = False
    current_voltage_uV: int = 0
    current_current_uA: int = 0
    current_mode: int = REGULATOR_MODE_NORMAL
    _consumers: List[str] = field(default_factory=list)
    _num_users: int = 0


@dataclass
class RegulatorSupply:
    """Regulator supply (input source)"""
    name: str
    is_registered: bool = False
    _regulators: List[str] = field(default_factory=list)


@dataclass
class RegulatorConsumer:
    """Regulator consumer (device using a regulator)"""
    name: str
    supply_name: str
    min_uV: int = 0
    max_uV: int = 0
    max_uA: int = 0
    is_registered: bool = False
    _regulator: Optional[Regulator] = None


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def register_supply(name: str) -> RegulatorSupply:
    """Register a regulator supply"""
    if name in _supplies:
        log.warning("Supply %s already registered", name)
        return _supplies[name]

    supply = RegulatorSupply(name=name, is_registered=True)
    _supplies[name] = supply
    log.info("Registered regulator supply: %s", name)
    return supply


def register_regulator(name: str, supply_name: str = "",
                       constraints: Optional[RegulatorConstraints] = None) -> Regulator:
    """Register a regulator"""
    if name in _regulators:
        log.warning("Regulator %s already registered", name)
        return _regulators[name]

    reg = Regulator(
        name=name,
        supply_name=supply_name,
        constraints=constraints or RegulatorConstraints(),
        is_registered=True,
    )
    _regulators[name] = reg

    if supply_name and supply_name in _supplies:
        _supplies[supply_name]._regulators.append(name)

    # Apply constraints
    if reg.constraints.always_on:
        reg.is_enabled = True
    if reg.constraints.apply_uV > 0:
        reg.current_voltage_uV = reg.constraints.apply_uV

    log.info("Registered regulator: %s (supply=%s)", name, supply_name)
    return reg


def register_consumer(name: str, supply_name: str,
                      min_uV: int = 0, max_uV: int = 0,
                      max_uA: int = 0) -> RegulatorConsumer:
    """Register a regulator consumer"""
    if name in _consumers:
        log.warning("Consumer %s already registered", name)
        return _consumers[name]

    consumer = RegulatorConsumer(
        name=name,
        supply_name=supply_name,
        min_uV=min_uV,
        max_uV=max_uV,
        max_uA=max_uA,
        is_registered=True,
    )

    # Find matching regulator
    for reg in _regulators.values():
        if reg.supply_name == supply_name or supply_name in reg.name:
            consumer._regulator = reg
            reg._consumers.append(name)
            break

    _consumers[name] = consumer
    log.info("Registered consumer: %s (supply=%s)", name, supply_name)
    return consumer


def unregister_regulator(name: str) -> bool:
    """Unregister a regulator"""
    if name not in _regulators:
        log.warning("Regulator %s not found", name)
        return False

    reg = _regulators[name]
    if reg.is_enabled and not reg.constraints.always_on:
        log.warning("Cannot unregister enabled regulator %s", name)
        return False

    del _regulators[name]
    log.info("Unregistered regulator: %s", name)
    return True


def get_regulator(name: str) -> Optional[Regulator]:
    """Get a registered regulator"""
    return _regulators.get(name)


def get_consumer(name: str) -> Optional[RegulatorConsumer]:
    """Get a registered consumer"""
    return _consumers.get(name)


def list_regulators() -> List[str]:
    """List all registered regulators"""
    return list(_regulators.keys())


def list_supplies() -> List[str]:
    """List all registered supplies"""
    return list(_supplies.keys())


def list_consumers() -> List[str]:
    """List all registered consumers"""
    return list(_consumers.keys())


# ---------------------------------------------------------------------------
# Regulator Operations
# ---------------------------------------------------------------------------
def enable_regulator(name: str) -> bool:
    """Enable a regulator"""
    reg = get_regulator(name)
    if reg is None:
        log.error("Regulator %s not found", name)
        return False

    if reg.is_enabled:
        return True

    if reg.ops.enable:
        reg.ops.enable()
    elif reg.ops.is_enabled:
        if reg.ops.is_enabled():
            reg.is_enabled = True
            return True

    reg.is_enabled = True
    reg._num_users += 1
    log.info("Enabled regulator: %s (users=%d)", name, reg._num_users)
    return True


def disable_regulator(name: str) -> bool:
    """Disable a regulator"""
    reg = get_regulator(name)
    if reg is None:
        log.error("Regulator %s not found", name)
        return False

    if reg.constraints.always_on:
        log.warning("Regulator %s is always-on, cannot disable", name)
        return False

    if reg._num_users > 1:
        reg._num_users -= 1
        log.debug("Regulator %s still in use (users=%d)", name, reg._num_users)
        return True

    if reg.ops.disable:
        reg.ops.disable()

    reg.is_enabled = False
    reg._num_users = 0
    log.info("Disabled regulator: %s", name)
    return True


def set_voltage(name: str, min_uV: int, max_uV: int) -> bool:
    """Set regulator voltage"""
    reg = get_regulator(name)
    if reg is None:
        log.error("Regulator %s not found", name)
        return False

    if not reg.constraints.valid_ops & REGULATOR_CHANGE_VOLTAGE:
        log.error("Regulator %s does not support voltage change", name)
        return False

    if min_uV < reg.constraints.min_uV or max_uV > reg.constraints.max_uV:
        log.error("Voltage %d-%d uV out of range %d-%d uV",
                  min_uV, max_uV, reg.constraints.min_uV, reg.constraints.max_uV)
        return False

    if reg.ops.set_voltage:
        reg.ops.set_voltage(min_uV)
    elif reg.ops.list_voltage:
        # Find closest valid voltage
        for v in range(reg.constraints.min_uV, reg.constraints.max_uV + 1, 25000):
            if min_uV <= v <= max_uV:
                reg.current_voltage_uV = v
                break
    else:
        reg.current_voltage_uV = min_uV

    log.info("Set voltage on %s: %d uV", name, reg.current_voltage_uV)
    return True


def get_voltage(name: str) -> int:
    """Get current regulator voltage"""
    reg = get_regulator(name)
    if reg is None:
        return 0

    if reg.ops.get_voltage:
        return reg.ops.get_voltage()
    return reg.current_voltage_uV


def set_current_limit(name: str, min_uA: int, max_uA: int) -> bool:
    """Set regulator current limit"""
    reg = get_regulator(name)
    if reg is None:
        log.error("Regulator %s not found", name)
        return False

    if min_uA < reg.constraints.min_uA or max_uA > reg.constraints.max_uA:
        log.error("Current %d-%d uA out of range %d-%d uA",
                  min_uA, max_uA, reg.constraints.min_uA, reg.constraints.max_uA)
        return False

    if reg.ops.set_current:
        reg.ops.set_current(max_uA)
    else:
        reg.current_current_uA = max_uA

    log.info("Set current limit on %s: %d uA", name, reg.current_current_uA)
    return True


def get_current_limit(name: str) -> int:
    """Get regulator current limit"""
    reg = get_regulator(name)
    if reg is None:
        return 0

    if reg.ops.get_current:
        return reg.ops.get_current()
    return reg.current_current_uA


def set_mode(name: str, mode: int) -> bool:
    """Set regulator operating mode"""
    reg = get_regulator(name)
    if reg is None:
        return False

    if not reg.constraints.valid_modes & mode:
        log.error("Regulator %s does not support mode 0x%02X", name, mode)
        return False

    if reg.ops.set_mode:
        reg.ops.set_mode(mode)
    else:
        reg.current_mode = mode

    log.debug("Set mode on %s: 0x%02X", name, mode)
    return True


def get_mode(name: str) -> int:
    """Get regulator operating mode"""
    reg = get_regulator(name)
    if reg is None:
        return REGULATOR_MODE_IDLE

    if reg.ops.get_mode:
        return reg.ops.get_mode()
    return reg.current_mode


def is_enabled(name: str) -> bool:
    """Check if regulator is enabled"""
    reg = get_regulator(name)
    if reg is None:
        return False

    if reg.ops.is_enabled:
        return reg.ops.is_enabled()
    return reg.is_enabled


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== UmerOS Regulator Framework Demo ===\n")

    # Register supplies
    register_supply("vin")
    register_supply("vbat")

    # Register regulators
    constraints = RegulatorConstraints(
        min_uV=800_000,
        max_uV=1_200_000,
        min_uA=0,
        max_uA=500_000,
    )
    register_regulator("buck1", supply_name="vin", constraints=constraints)

    constraints2 = RegulatorConstraints(
        min_uV=1_800_000,
        max_uV=3_300_000,
        always_on=True,
    )
    register_regulator("ldo1", supply_name="vin", constraints=constraints2)

    # Register consumers
    register_consumer("cpu", supply_name="buck1", min_uV=900_000, max_uV=1_100_000)
    register_consumer("io", supply_name="ldo1")

    print(f"Regulators: {list_regulators()}")
    print(f"Supplies: {list_supplies()}")
    print(f"Consumers: {list_consumers()}")

    # Enable and configure
    enable_regulator("buck1")
    set_voltage("buck1", 1_000_000, 1_000_000)
    set_mode("buck1", REGULATOR_MODE_FAST)

    print(f"\nbuck1: voltage={get_voltage('buck1')} uV, "
          f"enabled={is_enabled('buck1')}, "
          f"mode=0x{get_mode('buck1'):02X}")

    # LDO1 is always-on
    print(f"ldo1: always_on={_regulators['ldo1'].constraints.always_on}, "
          f"enabled={is_enabled('ldo1')}")
