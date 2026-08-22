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
UmerOS PHY Subsystem
=====================
Kernel-like PHY subsystem for physical layer interface management.
Implements PHY devices, providers, and configuration.

Reference: drivers/phy/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# PHY Constants
# ============================================================================

PHY_SUCCESS: int = 0
PHY_ERROR: int = 1
PHY_NOT_FOUND: int = 2
PHY_BUSY: int = 3

PHY_MAX_DEVICES: int = 64
PHY_MAX_CHANNELS: int = 8
PHY_MAX_MODES: int = 16


class PHYMode(IntEnum):
    """PHY operating modes."""
    UNKNOWN: int = 0
    USB: int = 1
    PCIE: int = 2
    SATA: int = 3
    HDMI: int = 4
    DSI: int = 5
    MIPI: int = 6
    LVDS: int = 7
    RGMII: int = 8
    SGMII: int = 9
    XGMII: int = 10
    TDM: int = 11


class PHYState(IntEnum):
    """PHY state."""
    OFF: int = 0
    ON: int = 1
    INIT: int = 2
    SUSPEND: int = 3
    RESUME: int = 4


class PHYSpeed(IntEnum):
    """PHY speed settings."""
    LOW: int = 0
    FULL: int = 1
    HIGH: int = 2


# ============================================================================
# PHY Configuration
# ============================================================================

@dataclass
class PHYConfig:
    """PHY configuration (mirrors struct phy_configuration)."""
    mode: PHYMode = PHYMode.UNKNOWN
    speed: PHYSpeed = PHYSpeed.FULL
    width: int = 1
    interface: int = 0
    clk_rate: int = 0
    tx_diff: int = 0
    rx_diff: int = 0
    vswing: int = 0
    preemphasis: int = 0
    port_num: int = 0
    lp_mode: bool = False

    def get_info(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.name,
            "speed": self.speed.name,
            "width": self.width,
            "clk_rate": self.clk_rate,
        }


# ============================================================================
# PHY Provider
# ============================================================================

@dataclass
class PHYProvider:
    """PHY provider (mirrors struct phy_provider)."""
    name: str
    index: int
    id: int = 0
    of_node: Optional[str] = None
    dev: Optional[str] = None
    num_phys: int = 0
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def get_phy(self, index: int) -> int:
        if index < 0 or index >= self.num_phys:
            return -1
        return index

    def get_phy_by_node(self, node: str) -> int:
        return 0

    def get_phy_by_phandle(self, node: str, prop: str, index: int) -> int:
        return index

    def devm_get_phy_by_phandle(self, node: str, prop: str, index: int) -> int:
        return index

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "num_phys": self.num_phys,
            "of_node": self.of_node,
        }


# ============================================================================
# PHY Device
# ============================================================================

@dataclass
class PHYDevice:
    """PHY device (mirrors struct phy)."""
    name: str
    index: int
    id: int = 0
    state: PHYState = PHYState.OFF
    mode: PHYMode = PHYMode.UNKNOWN
    config: PHYConfig = field(default_factory=PHYConfig)
    provider: Optional[PHYProvider] = None
    init_count: int = 0
    powered: bool = False
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def init(self) -> int:
        self.state = PHYState.INIT
        self.init_count += 1
        self._notify("init")
        return PHY_SUCCESS

    def exit(self) -> int:
        self.init_count -= 1
        if self.init_count <= 0:
            self.state = PHYState.OFF
            self.init_count = 0
        return PHY_SUCCESS

    def power_on(self) -> int:
        if self.state == PHYState.ON:
            return PHY_SUCCESS
        self.state = PHYState.ON
        self.powered = True
        self._notify("power_on")
        return PHY_SUCCESS

    def power_off(self) -> int:
        self.state = PHYState.OFF
        self.powered = False
        self._notify("power_off")
        return PHY_SUCCESS

    def set_mode(self, mode: PHYMode) -> int:
        self.mode = mode
        self.config.mode = mode
        return PHY_SUCCESS

    def configure(self, config: PHYConfig) -> int:
        self.config = config
        if "configure" in self._ops:
            return self._ops["configure"](config)
        return PHY_SUCCESS

    def suspend(self) -> int:
        self.state = PHYState.SUSPEND
        return PHY_SUCCESS

    def resume(self) -> int:
        self.state = PHYState.ON
        return PHY_SUCCESS

    def reset(self) -> int:
        if "reset" in self._ops:
            return self._ops["reset"]()
        return PHY_SUCCESS

    def calibrate(self) -> int:
        if "calibrate" in self._ops:
            return self._ops["calibrate"]()
        return PHY_SUCCESS

    def set_callback(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify(self, event: str) -> None:
        for cb in self._listeners:
            cb(self.name, event)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "id": self.id,
            "state": self.state.name,
            "mode": self.mode.name,
            "powered": self.powered,
            "init_count": self.init_count,
        }


# ============================================================================
# PHY Subsystem
# ============================================================================

class PHYSubsystem:
    """Central PHY subsystem managing devices and providers."""

    def __init__(self) -> None:
        self._devices: Dict[str, PHYDevice] = {}
        self._providers: Dict[str, PHYProvider] = {}
        self._next_index: int = 0

    def register_provider(self, provider: PHYProvider) -> int:
        provider.index = self._next_index
        provider.registered = True
        self._providers[provider.name] = provider
        self._next_index += 1
        return PHY_SUCCESS

    def unregister_provider(self, name: str) -> int:
        self._providers.pop(name, None)
        return PHY_SUCCESS

    def register_device(self, device: PHYDevice) -> int:
        device.index = self._next_index
        device.registered = True
        self._devices[device.name] = device
        self._next_index += 1
        return PHY_SUCCESS

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return PHY_SUCCESS

    def get_device(self, name: str) -> Optional[PHYDevice]:
        return self._devices.get(name)

    def get_provider(self, name: str) -> Optional[PHYProvider]:
        return self._providers.get(name)

    def enumerate_devices(self) -> List[PHYDevice]:
        return list(self._devices.values())

    def enumerate_providers(self) -> List[PHYProvider]:
        return list(self._providers.values())

    def get_topology(self) -> Dict[str, Any]:
        return {
            "devices": len(self._devices),
            "providers": len(self._providers),
        }


# ============================================================================
# Global PHY Instance
# ============================================================================

_global_phy: Optional[PHYSubsystem] = None


def get_global_phy() -> PHYSubsystem:
    global _global_phy
    if _global_phy is None:
        _global_phy = PHYSubsystem()
    return _global_phy


def register_phy_device(device: PHYDevice) -> int:
    return get_global_phy().register_device(device)


def phy_get(device_name: str) -> Optional[PHYDevice]:
    return get_global_phy().get_device(device_name)


def phy_power_on(device_name: str) -> int:
    dev = get_global_phy().get_device(device_name)
    return dev.power_on() if dev else PHY_ERROR


def phy_power_off(device_name: str) -> int:
    dev = get_global_phy().get_device(device_name)
    return dev.power_off() if dev else PHY_ERROR
