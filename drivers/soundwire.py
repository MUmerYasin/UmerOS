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
UmerOS SoundWire Subsystem
==========================
Kernel-like SoundWire subsystem for audio interconnect.
Implements SoundWire controllers, ports, and data channels for
multi-channel audio streaming.

Reference: drivers/soundwire/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# SoundWire Constants
# ============================================================================

SDW_SUCCESS: int = 0
SDW_ERROR: int = 1
SDW_NOT_FOUND: int = 2
SDW_BUSY: int = 3

SDW_MAX_DEVICES: int = 16
SDW_MAX_PORTS: int = 64
SDW_MAX_CHANNELS: int = 64
SDW_MAX_STREAMS: int = 8
SDW_DEFAULT_CLK_FREQ: int = 12288000  # 12.288 MHz


class SDWState(IntEnum):
    """SoundWire device state."""
    UNATTACHED: int = 0
    ATTACHED: int = 1
    ALERT: int = 2


class SDWStreamState(IntEnum):
    """SoundWire stream state."""
    FREE: int = 0
    READY: int = 1
    ACTIVE: int = 2
    PAUSED: int = 3


class SDWPortType(IntEnum):
    """SoundWire port type."""
    SOURCE: int = 0
    SINK: int = 1


class SDWDataMode(IntEnum):
    """SoundWire data mode."""
    TX: int = 0
    RX: int = 1
    FULL_DUPLEX: int = 2


# ============================================================================
# SoundWire Port
# ============================================================================

@dataclass
class SDWPort:
    """SoundWire port (mirrors struct sdw_port)."""
    port_id: int
    port_type: SDWPortType = SDWPortType.SINK
    channels: int = 2
    data_mode: SDWDataMode = SDWDataMode.FULL_DUPLEX
    word_length: int = 32
    scp_int_mask: int = 0
    hctrl: int = 0
    enabled: bool = False

    def enable(self) -> int:
        self.enabled = True
        return SDW_SUCCESS

    def disable(self) -> int:
        self.enabled = False
        return SDW_SUCCESS

    def get_info(self) -> Dict[str, Any]:
        return {
            "port_id": self.port_id,
            "type": self.port_type.name,
            "channels": self.channels,
            "word_length": self.word_length,
            "enabled": self.enabled,
        }


# ============================================================================
# SoundWire Stream
# ============================================================================

@dataclass
class SDWStream:
    """SoundWire stream (mirrors struct sdw_stream_config)."""
    name: str
    index: int
    state: SDWStreamState = SDWStreamState.FREE
    channels: int = 2
    rate: int = 48000
    word_length: int = 32
    direction: SDWDataMode = SDWDataMode.FULL_DUPLEX
    ports: List[SDWPort] = field(default_factory=list)
    ch_count: int = 0
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def prepare(self) -> int:
        if self.state != SDWStreamState.FREE:
            return SDW_ERROR
        self.state = SDWStreamState.READY
        return SDW_SUCCESS

    def enable(self) -> int:
        if self.state != SDWStreamState.READY:
            return SDW_ERROR
        self.state = SDWStreamState.ACTIVE
        return SDW_SUCCESS

    def disable(self) -> int:
        self.state = SDWStreamState.FREE
        return SDW_SUCCESS

    def pause(self) -> int:
        if self.state != SDWStreamState.ACTIVE:
            return SDW_ERROR
        self.state = SDWStreamState.PAUSED
        return SDW_SUCCESS

    def resume(self) -> int:
        if self.state != SDWStreamState.PAUSED:
            return SDW_ERROR
        self.state = SDWStreamState.ACTIVE
        return SDW_SUCCESS

    def add_port(self, port: SDWPort) -> int:
        if len(self.ports) >= SDW_MAX_PORTS:
            return SDW_ERROR
        self.ports.append(port)
        return SDW_SUCCESS

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.name,
            "channels": self.channels,
            "rate": self.rate,
            "word_length": self.word_length,
            "ports": len(self.ports),
        }


# ============================================================================
# SoundWire Device
# ============================================================================

@dataclass
class SDWDevice:
    """SoundWire device (mirrors struct sdw_slave)."""
    name: str
    index: int
    dev_num: int = 0
    state: SDWState = SDWState.UNATTACHED
    mfg_id: int = 0
    part_id: int = 0
    class_id: int = 0
    ports: Dict[int, SDWPort] = field(default_factory=dict)
    streams: List[SDWStream] = field(default_factory=list)
    wake_capable: bool = False
    clock_suspend: bool = False
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def attach(self) -> int:
        self.state = SDWState.ATTACHED
        return SDW_SUCCESS

    def detach(self) -> int:
        self.state = SDWState.UNATTACHED
        return SDW_SUCCESS

    def alert(self) -> int:
        self.state = SDWState.ALERT
        return SDW_SUCCESS

    def add_port(self, port: SDWPort) -> int:
        self.ports[port.port_id] = port
        return SDW_SUCCESS

    def get_port(self, port_id: int) -> Optional[SDWPort]:
        return self.ports.get(port_id)

    def add_stream(self, stream: SDWStream) -> int:
        self.streams.append(stream)
        return SDW_SUCCESS

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dev_num": self.dev_num,
            "state": self.state.name,
            "mfg_id": self.mfg_id,
            "part_id": self.part_id,
            "ports": len(self.ports),
            "streams": len(self.streams),
        }


# ============================================================================
# SoundWire Controller
# ============================================================================

@dataclass
class SDWController:
    """SoundWire controller (mirrors struct sdw_master)."""
    name: str
    index: int
    num_devices: int = 0
    max_devices: int = SDW_MAX_DEVICES
    clk_freq: int = SDW_DEFAULT_CLK_FREQ
    devices: Dict[int, SDWDevice] = field(default_factory=dict)
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def add_device(self, device: SDWDevice) -> int:
        if len(self.devices) >= self.max_devices:
            return SDW_ERROR
        device.dev_num = len(self.devices)
        self.devices[device.dev_num] = device
        self.num_devices = len(self.devices)
        return SDW_SUCCESS

    def remove_device(self, dev_num: int) -> int:
        self.devices.pop(dev_num, None)
        self.num_devices = len(self.devices)
        return SDW_SUCCESS

    def get_device(self, dev_num: int) -> Optional[SDWDevice]:
        return self.devices.get(dev_num)

    def scan_devices(self) -> int:
        for dev in self.devices.values():
            dev.attach()
        return SDW_SUCCESS

    def read_register(self, dev_num: int, reg: int) -> Optional[int]:
        if "read" in self._ops:
            return self._ops["read"](dev_num, reg)
        return None

    def write_register(self, dev_num: int, reg: int, value: int) -> int:
        if "write" in self._ops:
            return self._ops["write"](dev_num, reg, value)
        return SDW_ERROR

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "devices": self.num_devices,
            "clk_freq": self.clk_freq,
        }


# ============================================================================
# SoundWire Subsystem
# ============================================================================

class SDWSubsystem:
    """Central SoundWire subsystem managing controllers and devices."""

    def __init__(self) -> None:
        self._controllers: Dict[str, SDWController] = {}
        self._next_index: int = 0

    def register_controller(self, ctrl: SDWController) -> int:
        ctrl.index = self._next_index
        ctrl.registered = True
        self._controllers[ctrl.name] = ctrl
        self._next_index += 1
        return SDW_SUCCESS

    def unregister_controller(self, name: str) -> int:
        self._controllers.pop(name, None)
        return SDW_SUCCESS

    def get_controller(self, name: str) -> Optional[SDWController]:
        return self._controllers.get(name)

    def enumerate_controllers(self) -> List[SDWController]:
        return list(self._controllers.values())

    def get_topology(self) -> Dict[str, Any]:
        return {
            "controllers": len(self._controllers),
            "devices": sum(c.num_devices for c in self._controllers.values()),
        }


# ============================================================================
# Global SoundWire Instance
# ============================================================================

_global_sdw: Optional[SDWSubsystem] = None


def get_global_sdw() -> SDWSubsystem:
    global _global_sdw
    if _global_sdw is None:
        _global_sdw = SDWSubsystem()
    return _global_sdw


def register_sdw_controller(ctrl: SDWController) -> int:
    return get_global_sdw().register_controller(ctrl)


def sdw_add_device(controller: str, device: SDWDevice) -> int:
    ctrl = get_global_sdw().get_controller(controller)
    return ctrl.add_device(device) if ctrl else SDW_ERROR
