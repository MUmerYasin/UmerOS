"""
UmerOS RPMsg Subsystem
=======================
Linux kernel-like RPMsg subsystem for inter-processor messaging.
Implements endpoint-based messaging between processors.

Reference: drivers/rpmsg/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import queue


# ============================================================================
# RPMsg Constants
# ============================================================================

RPMSG_SUCCESS: int = 0
RPMSG_ERROR: int = 1
RPMSG_NOT_FOUND: int = 2
RPMSG_BUSY: int = 3

RPMSG_MAX_DEVICES: int = 16
RPMSG_MAX_ENDPOINTS: int = 32
RPMSG_MAX_NAME_LEN: int = 32
RPMSG_BUFFER_SIZE: int = 512
RPMSG_MAX_MSG_SIZE: int = 496


class RPMsgState(IntEnum):
    """RPMsg endpoint state."""
    RELEASED: int = 0
    BOUND: int = 1
    PAUSED: int = 2


# ============================================================================
# RPMsg Message
# ============================================================================

@dataclass
class RPMsgMessage:
    """RPMsg message (mirrors struct rpmsg_msg)."""
    src: int = 0
    dst: int = 0
    data: bytes = b''
    len: int = 0
    callback: Optional[Callable] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.len:
            self.len = len(self.data)

    def get_info(self) -> Dict[str, Any]:
        return {
            "src": self.src,
            "dst": self.dst,
            "len": self.len,
        }


# ============================================================================
# RPMsg Endpoint
# ============================================================================

@dataclass
class RPMsgEndpoint:
    """RPMsg endpoint (mirrors struct rpmsg_endpoint)."""
    name: str
    addr: int = 0xFFFFFFFF
    dest_addr: int = 0xFFFFFFFF
    state: RPMsgState = RPMsgState.RELEASED
    cb: Optional[Callable] = field(default=None, repr=False)
    priv: Any = None
    _rx_queue: queue.Queue = field(default_factory=queue.Queue, repr=False)

    def bind(self) -> int:
        self.state = RPMsgState.BOUND
        return RPMSG_SUCCESS

    def unbind(self) -> int:
        self.state = RPMsgState.RELEASED
        return RPMSG_SUCCESS

    def pause(self) -> int:
        self.state = RPMsgState.PAUSED
        return RPMSG_SUCCESS

    def resume(self) -> int:
        self.state = RPMsgState.BOUND
        return RPMSG_SUCCESS

    def send(self, data: bytes, len_: int) -> int:
        if self.state != RPMsgState.BOUND:
            return RPMSG_ERROR
        return RPMSG_SUCCESS

    def sendto(self, data: bytes, len_: int, dst: int) -> int:
        if self.state != RPMsgState.BOUND:
            return RPMSG_ERROR
        return RPMSG_SUCCESS

    def trysend(self, data: bytes, len_: int) -> int:
        if self.state != RPMsgState.BOUND:
            return RPMSG_ERROR
        return RPMSG_SUCCESS

    def trysendto(self, data: bytes, len_: int, dst: int) -> int:
        if self.state != RPMsgState.BOUND:
            return RPMSG_ERROR
        return RPMSG_SUCCESS

    def recv(self) -> Optional[RPMsgMessage]:
        if self._rx_queue.empty():
            return None
        return self._rx_queue.get_nowait()

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "addr": self.addr,
            "dest_addr": self.dest_addr,
            "state": self.state.name,
        }


# ============================================================================
# RPMsg Device
# ============================================================================

@dataclass
class RPMsgDevice:
    """RPMsg device (mirrors struct rpmsg_device)."""
    name: str
    index: int
    endpoints: Dict[str, RPMsgEndpoint] = field(default_factory=dict)
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def create_endpoint(self, name: str, cb: Optional[Callable] = None) -> int:
        if len(self.endpoints) >= RPMSG_MAX_ENDPOINTS:
            return RPMSG_ERROR
        ep = RPMsgEndpoint(name=name, cb=cb)
        ep.addr = len(self.endpoints)
        ep.bind()
        self.endpoints[name] = ep
        return RPMSG_SUCCESS

    def destroy_endpoint(self, name: str) -> int:
        ep = self.endpoints.pop(name, None)
        if ep:
            ep.unbind()
            return RPMSG_SUCCESS
        return RPMSG_ERROR

    def get_endpoint(self, name: str) -> Optional[RPMsgEndpoint]:
        return self.endpoints.get(name)

    def send_message(self, src_name: str, dst_name: str, data: bytes) -> int:
        src_ep = self.get_endpoint(src_name)
        if not src_ep:
            return RPMSG_ERROR
        return src_ep.send(data, len(data))

    def receive_message(self, ep_name: str) -> Optional[RPMsgMessage]:
        ep = self.get_endpoint(ep_name)
        return ep.recv() if ep else None

    def register_ops(self, ops: Dict[str, Callable]) -> None:
        self._ops.update(ops)

    def register_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify(self, event: str) -> None:
        for cb in self._listeners:
            cb(self.name, event)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "endpoints": len(self.endpoints),
            "endpoints_list": list(self.endpoints.keys()),
        }


# ============================================================================
# RPMsg Subsystem
# ============================================================================

class RPMsgSubsystem:
    """Central RPMsg subsystem managing devices."""

    def __init__(self) -> None:
        self._devices: Dict[str, RPMsgDevice] = {}
        self._next_index: int = 0

    def register_device(self, device: RPMsgDevice) -> int:
        device.index = self._next_index
        device.registered = True
        self._devices[device.name] = device
        self._next_index += 1
        return RPMSG_SUCCESS

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return RPMSG_SUCCESS

    def get_device(self, name: str) -> Optional[RPMsgDevice]:
        return self._devices.get(name)

    def enumerate_devices(self) -> List[RPMsgDevice]:
        return list(self._devices.values())

    def get_topology(self) -> Dict[str, Any]:
        return {
            "devices": len(self._devices),
            "endpoints": sum(len(d.endpoints) for d in self._devices.values()),
        }


# ============================================================================
# Global RPMsg Instance
# ============================================================================

_global_rpmsg: Optional[RPMsgSubsystem] = None


def get_global_rpmsg() -> RPMsgSubsystem:
    global _global_rpmsg
    if _global_rpmsg is None:
        _global_rpmsg = RPMsgSubsystem()
    return _global_rpmsg


def register_rpmsg_device(device: RPMsgDevice) -> int:
    return get_global_rpmsg().register_device(device)


def rpmsg_create_endpoint(device: str, endpoint: str) -> int:
    dev = get_global_rpmsg().get_device(device)
    return dev.create_endpoint(endpoint) if dev else RPMSG_ERROR
