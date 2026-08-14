"""
UmerOS HSI Subsystem
====================
Kernel-like HSI (High Speed Synchronous Serial Interface) subsystem.
Implements HSI controllers, clients, and message passing for
modem and inter-processor communication.

Reference: drivers/hsi/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# HSI Constants
# ============================================================================

HSI_SUCCESS: int = 0
HSI_ERROR: int = 1
HSI_TIMEOUT: int = 2
HSI_NOT_FOUND: int = 3
HSI_BUSY: int = 4

HSI_MSG_MAX_SIZE: int = 4096
HSI_MAX_PORTS: int = 16
HSI_MAX_CHANNELS: int = 16
HSI_DEFAULT_MTU: int = 4096


class HSIChannelState(IntEnum):
    """HSI channel state."""
    FREE: int = 0
    RESERVED: int = 1
    CONNECTED: int = 2


class HSIMsgType(IntEnum):
    """HSI message type."""
    DATA: int = 0
    COMMAND: int = 1
    EVENT: int = 2


# ============================================================================
# HSI Message
# ============================================================================

@dataclass
class HSIMessage:
    """HSI message (mirrors struct hsi_msg)."""
    msg_id: int = 0
    channel: int = 0
    msg_type: HSIMsgType = HSIMsgType.DATA
    data: bytes = b''
    length: int = 0
    status: int = 0
    timestamp: float = 0.0
    complete: bool = False
    _callback: Optional[Callable] = field(default=None, repr=False)

    def set_data(self, data: bytes) -> None:
        self.data = data
        self.length = len(data)

    def get_data(self) -> bytes:
        return self.data

    def mark_complete(self, status: int = 0) -> None:
        self.complete = True
        self.status = status
        if self._callback:
            self._callback(self)


# ============================================================================
# HSI Channel
# ============================================================================

@dataclass
class HSIChannel:
    """HSI channel (mirrors struct hsi_channel)."""
    channel_id: int
    state: HSIChannelState = HSIChannelState.FREE
    mtu: int = HSI_DEFAULT_MTU
    speed: int = 0  # bits per second
    flow: int = 0
    frame_size: int = 0
    _rx_queue: List[HSIMessage] = field(default_factory=list, repr=False)
    _tx_queue: List[HSIMessage] = field(default_factory=list, repr=False)
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def reserve(self) -> int:
        if self.state != HSIChannelState.FREE:
            return HSI_BUSY
        self.state = HSIChannelState.RESERVED
        return HSI_SUCCESS

    def connect(self) -> int:
        if self.state != HSIChannelState.RESERVED:
            return HSI_ERROR
        self.state = HSIChannelState.CONNECTED
        return HSI_SUCCESS

    def disconnect(self) -> int:
        self.state = HSIChannelState.FREE
        return HSI_SUCCESS

    def send_message(self, msg: HSIMessage) -> int:
        if self.state != HSIChannelState.CONNECTED:
            return HSI_ERROR
        msg.channel = self.channel_id
        self._tx_queue.append(msg)
        return HSI_SUCCESS

    def receive_message(self) -> Optional[HSIMessage]:
        return self._rx_queue.pop(0) if self._rx_queue else None

    def enqueue_rx(self, msg: HSIMessage) -> None:
        self._rx_queue.append(msg)
        self._notify_listeners(msg)

    def register_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify_listeners(self, msg: HSIMessage) -> None:
        for cb in self._listeners:
            cb(msg)

    def flush_tx(self) -> int:
        self._tx_queue.clear()
        return HSI_SUCCESS

    def flush_rx(self) -> int:
        self._rx_queue.clear()
        return HSI_SUCCESS

    def get_info(self) -> Dict[str, Any]:
        return {
            "channel": self.channel_id,
            "state": self.state.name,
            "mtu": self.mtu,
            "speed": self.speed,
            "rx_queue": len(self._rx_queue),
            "tx_queue": len(self._tx_queue),
        }


# ============================================================================
# HSI Client
# ============================================================================

@dataclass
class HSIClient:
    """HSI client (mirrors struct hsi_client)."""
    name: str
    index: int
    port: int = 0
    channel: int = 0
    tx_channel: int = 0
    rx_channel: int = 0
    tx_speed: int = 0
    rx_speed: int = 0
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def send_message(self, msg: HSIMessage) -> int:
        if "send" in self._ops:
            return self._ops["send"](self, msg)
        return HSI_ERROR

    def register_ops(self, ops: Dict[str, Callable]) -> None:
        self._ops.update(ops)


# ============================================================================
# HSI Controller Port
# ============================================================================

@dataclass
class HSIController:
    """HSI controller port (mirrors struct hsi_port)."""
    name: str
    index: int
    port_id: int = 0
    num_channels: int = 8
    channels: Dict[int, HSIChannel] = field(default_factory=dict)
    speed: int = 0
    frame_size: int = 0
    wakeup: bool = False
    registered: bool = False

    def __post_init__(self) -> None:
        for ch_id in range(self.num_channels):
            self.channels[ch_id] = HSIChannel(channel_id=ch_id)

    def get_channel(self, ch_id: int) -> Optional[HSIChannel]:
        return self.channels.get(ch_id)

    def allocate_channel(self) -> Optional[HSIChannel]:
        for ch_id, ch in self.channels.items():
            if ch.state == HSIChannelState.FREE:
                ch.reserve()
                return ch
        return None

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "port_id": self.port_id,
            "channels": len(self.channels),
            "speed": self.speed,
        }


# ============================================================================
# HSI Subsystem Manager
# ============================================================================

class HSISubsystem:
    """Central HSI subsystem managing controllers and clients."""

    def __init__(self) -> None:
        self._controllers: Dict[str, HSIController] = {}
        self._clients: Dict[str, HSIClient] = {}
        self._next_index: int = 0

    def register_controller(self, ctrl: HSIController) -> int:
        ctrl.index = self._next_index
        ctrl.registered = True
        self._controllers[ctrl.name] = ctrl
        self._next_index += 1
        return 0

    def unregister_controller(self, name: str) -> int:
        self._controllers.pop(name, None)
        return 0

    def get_controller(self, name: str) -> Optional[HSIController]:
        return self._controllers.get(name)

    def register_client(self, client: HSIClient) -> int:
        client.index = self._next_index
        client.registered = True
        self._clients[client.name] = client
        self._next_index += 1
        return 0

    def unregister_client(self, name: str) -> int:
        self._clients.pop(name, None)
        return 0

    def get_client(self, name: str) -> Optional[HSIClient]:
        return self._clients.get(name)

    def enumerate_controllers(self) -> List[HSIController]:
        return list(self._controllers.values())

    def enumerate_clients(self) -> List[HSIClient]:
        return list(self._clients.values())


# ============================================================================
# Global HSI Instance
# ============================================================================

_global_hsi: Optional[HSISubsystem] = None


def get_global_hsi() -> HSISubsystem:
    global _global_hsi
    if _global_hsi is None:
        _global_hsi = HSISubsystem()
    return _global_hsi


def register_hsi_controller(ctrl: HSIController) -> int:
    return get_global_hsi().register_controller(ctrl)


def register_hsi_client(client: HSIClient) -> int:
    return get_global_hsi().register_client(client)
