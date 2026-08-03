"""
UmerOS NTB (Non-Transparent Bridge) Subsystem
==============================================
Linux kernel-like NTB framework for inter-system communication
across PCI Express non-transparent bridges.

Reference: drivers/ntb/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# NTB Constants
# ============================================================================

NTB_SUCCESS: int = 0
NTB_ERROR: int = 1
NTB_NOT_FOUND: int = 2
NTB_BUSY: int = 3

NTB_MAX_ENDPOINTS: int = 8
NTB_MAX_LINKS: int = 8
NTB_MAX_DOORBELLS: int = 64
NTB_MAX_SPADS: int = 16
NTB_MAX_MESSAGES: int = 64

NTB_EVENT_LINK_UP: int = 0x01
NTB_EVENT_LINK_DOWN: int = 0x02
NTB_EVENT_DB: int = 0x04
NTB_EVENT_MSG: int = 0x08


class NTBSpeed(IntEnum):
    """NTB link speed."""
    GEN1: int = 1
    GEN2: int = 2
    GEN3: int = 3
    GEN4: int = 4


class NTBWidth(IntEnum):
    """NTB link width."""
    NONE: int = 0
    x1: int = 1
    x2: int = 2
    x4: int = 4
    x8: int = 8
    x16: int = 16


class NTBState(IntEnum):
    """NTB device state."""
    DOWN: int = 0
    CONNECTING: int = 1
    UP: int = 2
    ERROR: int = 3


# ============================================================================
# NTB Transport
# ============================================================================

@dataclass
class NTBTransport:
    """NTB transport (mirrors struct ntb_transport)."""
    name: str
    index: int
    max_links: int = NTB_MAX_LINKS
    state: NTBState = NTBState.DOWN
    speed: NTBSpeed = NTBSpeed.GEN3
    width: NTBWidth = NTBWidth.x16
    payload_size: int = 4096
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def peer_register(self) -> int:
        self.state = NTBState.CONNECTING
        return NTB_SUCCESS

    def peer_unregister(self) -> int:
        self.state = NTBState.DOWN
        return NTB_SUCCESS

    def link(self) -> int:
        self.state = NTBState.UP
        self._notify("link_up")
        return NTB_SUCCESS

    def unlink(self) -> int:
        self.state = NTBState.DOWN
        self._notify("link_down")
        return NTB_SUCCESS

    def send_message(self, message: bytes, dest: int = 0) -> int:
        if self.state != NTBState.UP:
            return NTB_ERROR
        if "send" in self._ops:
            return self._ops["send"](message, dest)
        return NTB_SUCCESS

    def receive_message(self) -> Optional[bytes]:
        if "receive" in self._ops:
            return self._ops["receive"]()
        return None

    def send_data(self, offset: int, data: bytes) -> int:
        if self.state != NTBState.UP:
            return NTB_ERROR
        if "send_data" in self._ops:
            return self._ops["send_data"](offset, data)
        return NTB_SUCCESS

    def receive_data(self, offset: int, size: int) -> Optional[bytes]:
        if "receive_data" in self._ops:
            return self._ops["receive_data"](offset, size)
        return None

    def register_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify(self, event: str) -> None:
        for cb in self._listeners:
            cb(self.name, event)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.name,
            "speed": self.speed.name,
            "width": self.width.name,
            "payload_size": self.payload_size,
        }


# ============================================================================
# NTB Endpoint
# ============================================================================

@dataclass
class NTBEndpoint:
    """NTB endpoint."""
    name: str
    index: int
    port: int = 0
    transport: Optional[NTBTransport] = None
    peer_id: int = -1
    registered: bool = False

    def connect(self) -> int:
        if self.transport:
            return self.transport.link()
        return NTB_ERROR

    def disconnect(self) -> int:
        if self.transport:
            return self.transport.unlink()
        return NTB_ERROR

    def send(self, data: bytes) -> int:
        return self.transport.send_message(data) if self.transport else NTB_ERROR

    def receive(self) -> Optional[bytes]:
        return self.transport.receive_message() if self.transport else None

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "port": self.port,
            "peer_id": self.peer_id,
            "state": self.transport.state.name if self.transport else "DOWN",
        }


# ============================================================================
# NTB Device
# ============================================================================

@dataclass
class NTBDevice:
    """NTB device (mirrors struct ntb_dev)."""
    name: str
    index: int
    endpoints: Dict[int, NTBEndpoint] = field(default_factory=dict)
    doorbell_mask: int = 0
    spad_mask: int = 0
    state: NTBState = NTBState.DOWN
    registered: bool = False

    def add_endpoint(self, endpoint: NTBEndpoint) -> int:
        endpoint.index = len(self.endpoints)
        self.endpoints[endpoint.index] = endpoint
        return NTB_SUCCESS

    def remove_endpoint(self, index: int) -> int:
        self.endpoints.pop(index, None)
        return NTB_SUCCESS

    def get_endpoint(self, index: int) -> Optional[NTBEndpoint]:
        return self.endpoints.get(index)

    def ring_doorbell(self, bit: int) -> int:
        if 0 <= bit < NTB_MAX_DOORBELLS:
            self.doorbell_mask |= (1 << bit)
            return NTB_SUCCESS
        return NTB_ERROR

    def clear_doorbell(self, bit: int) -> int:
        if 0 <= bit < NTB_MAX_DOORBELLS:
            self.doorbell_mask &= ~(1 << bit)
            return NTB_SUCCESS
        return NTB_ERROR

    def write_spad(self, index: int, value: int) -> int:
        if 0 <= index < NTB_MAX_SPADS:
            return NTB_SUCCESS
        return NTB_ERROR

    def read_spad(self, index: int) -> Optional[int]:
        if 0 <= index < NTB_MAX_SPADS:
            return 0
        return None

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.name,
            "endpoints": len(self.endpoints),
            "doorbell_mask": self.doorbell_mask,
        }


# ============================================================================
# NTB Subsystem
# ============================================================================

class NTBSubsystem:
    """Central NTB subsystem managing devices and transports."""

    def __init__(self) -> None:
        self._devices: Dict[str, NTBDevice] = {}
        self._transports: Dict[str, NTBTransport] = {}
        self._next_index: int = 0

    def register_device(self, device: NTBDevice) -> int:
        device.index = self._next_index
        device.registered = True
        self._devices[device.name] = device
        self._next_index += 1
        return NTB_SUCCESS

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return NTB_SUCCESS

    def get_device(self, name: str) -> Optional[NTBDevice]:
        return self._devices.get(name)

    def register_transport(self, transport: NTBTransport) -> int:
        transport.index = self._next_index
        self._transports[transport.name] = transport
        self._next_index += 1
        return NTB_SUCCESS

    def unregister_transport(self, name: str) -> int:
        self._transports.pop(name, None)
        return NTB_SUCCESS

    def get_transport(self, name: str) -> Optional[NTBTransport]:
        return self._transports.get(name)

    def get_topology(self) -> Dict[str, Any]:
        return {
            "devices": len(self._devices),
            "transports": len(self._transports),
            "device_names": list(self._devices.keys()),
        }


# ============================================================================
# Global NTB Instance
# ============================================================================

_global_ntb: Optional[NTBSubsystem] = None


def get_global_ntb() -> NTBSubsystem:
    global _global_ntb
    if _global_ntb is None:
        _global_ntb = NTBSubsystem()
    return _global_ntb


def register_ntb_device(device: NTBDevice) -> int:
    return get_global_ntb().register_device(device)


def ntb_ring_doorbell(device_name: str, bit: int) -> int:
    dev = get_global_ntb().get_device(device_name)
    return dev.ring_doorbell(bit) if dev else NTB_ERROR
