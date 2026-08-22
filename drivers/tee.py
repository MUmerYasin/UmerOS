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
UmerOS TEE Subsystem
====================
Kernel-like TEE (Trusted Execution Environment) framework.
Implements TEE device management, trusted applications,
shared memory management, and session handling.

Reference: Documentation/driver-api/tee/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# ============================================================================
# TEE Constants
# ============================================================================

TEE_SUCCESS: int = 0
TEE_ERROR_GENERIC: int = 0xFFFF0000
TEE_ERROR_ACCESS_DENIED: int = 0xFFFF0001
TEE_ERROR_BAD_PARAMETERS: int = 0xFFFF0006
TEE_ERROR_ITEM_NOT_FOUND: int = 0xFFFF0008
TEE_ERROR_NOT_SUPPORTED: int = 0xFFFF000A
TEE_ERROR_NO_DATA: int = 0xFFFF000B
TEE_ERROR_OUT_OF_MEMORY: int = 0xFFFF000C
TEE_ERROR_BUSY: int = 0xFFFF000D
TEE_ERROR_COMMUNICATION: int = 0xFFFF000E
TEE_ERROR_SECURITY: int = 0xFFFF000F
TEE_ERROR_SHORT_BUFFER: int = 0xFFFF0010

TEE_PARAM_TYPES: int = 16
TEE_MAX_PARAM_COUNT: int = 4


class TEEParamType(IntEnum):
    """TEE parameter types."""
    NONE = 0
    VALUE_INPUT = 1
    VALUE_OUTPUT = 2
    MEMREF_INPUT = 3
    MEMREF_OUTPUT = 4
    MEMREF_INOUT = 5


class TEECapType(IntEnum):
    """TEE capability types."""
    GENERIC = 0
    TEEC = 1
    OPTEE = 2
    TRUSTED_OS = 3


class TEEState(IntEnum):
    """TEE session state."""
    CLOSED = 0
    OPEN = 1
    PENDING = 2
    ERROR = 3


# ============================================================================
# TEE Shared Memory
# ============================================================================

@dataclass
class TEESharedMemory:
    """Shared memory region between normal and secure world.

    Mirrors struct tee_shm in the kernel.
    """
    id: int
    size: int
    buffer: bytearray = field(default_factory=bytearray)
    registered: bool = False
    cached: bool = False
    exclusive: bool = False
    data: Any = None

    def __post_init__(self) -> None:
        if not self.buffer:
            self.buffer = bytearray(self.size)

    def read(self, offset: int, length: int) -> bytes:
        if offset + length > self.size:
            return b''
        return bytes(self.buffer[offset:offset + length])

    def write(self, offset: int, data: bytes) -> int:
        if offset + len(data) > self.size:
            return -1
        self.buffer[offset:offset + len(data)] = data
        return len(data)


# ============================================================================
# TEE Parameter
# ============================================================================

@dataclass
class TEEParam:
    """TEE call parameter (mirrors struct tee_param)."""
    param_type: TEEParamType = TEEParamType.NONE
    value_a: int = 0
    value_b: int = 0
    shm: Optional[TEESharedMemory] = None
    shm_offset: int = 0
    shm_size: int = 0


# ============================================================================
# TEE Operation
# ============================================================================

@dataclass
class TEEOperation:
    """TEE trusted application operation (mirrors struct tee_ioctl_op)."""
    id: int = 0
    session_id: int = 0
    cmd_id: int = 0
    param_types: int = 0
    params: List[TEEParam] = field(default_factory=list)
    cancelled: bool = False
    ret_origin: int = 0
    ret_code: int = TEE_SUCCESS

    def set_param_types(self, t0: TEEParamType, t1: TEEParamType,
                        t2: TEEParamType, t3: TEEParamType) -> None:
        self.param_types = (t0 | (t1 << 4) | (t2 << 8) | (t3 << 12))

    def get_param_type(self, index: int) -> TEEParamType:
        shift = index * 4
        return TEEParamType((self.param_types >> shift) & 0x0F)


# ============================================================================
# TEE Session
# ============================================================================

@dataclass
class TEESession:
    """TEE session to a trusted application (mirrors struct tee_session)."""
    id: int
    ta_uuid: str
    state: TEEState = TEEState.OPEN
    client_id: int = 0
    operations: List[TEEOperation] = field(default_factory=list)
    _next_op_id: int = 0

    def create_operation(self, cmd_id: int, param_types: int = 0) -> TEEOperation:
        self._next_op_id += 1
        op = TEEOperation(
            id=self._next_op_id,
            session_id=self.id,
            cmd_id=cmd_id,
            param_types=param_types,
        )
        self.operations.append(op)
        return op

    def close(self) -> None:
        self.state = TEEState.CLOSED
        self.operations.clear()


# ============================================================================
# TEE Device
# ============================================================================

@dataclass
class TEEDevice:
    """TEE device (mirrors struct tee_device).

    Represents a TEE capable of hosting trusted applications.
    """
    name: str
    id: int
    cap: TEECapType = TEECapType.GENERIC
    desc: str = ""
    max_sessions: int = 32
    registered: bool = False
    _sessions: Dict[int, TEESession] = field(default_factory=dict)
    _shms: Dict[int, TEESharedMemory] = field(default_factory=dict)
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _next_session_id: int = 0
    _next_shm_id: int = 0

    def open_session(self, ta_uuid: str, client_id: int = 0) -> Optional[TEESession]:
        if len(self._sessions) >= self.max_sessions:
            return None
        self._next_session_id += 1
        session = TEESession(id=self._next_session_id, ta_uuid=ta_uuid, client_id=client_id)
        self._sessions[session.id] = session
        return session

    def close_session(self, session_id: int) -> int:
        session = self._sessions.pop(session_id, None)
        if session:
            session.close()
            return TEE_SUCCESS
        return TEE_ERROR_ITEM_NOT_FOUND

    def get_session(self, session_id: int) -> Optional[TEESession]:
        return self._sessions.get(session_id)

    def allocate_shm(self, size: int, flags: int = 0) -> Optional[TEESharedMemory]:
        self._next_shm_id += 1
        shm = TEESharedMemory(id=self._next_shm_id, size=size)
        shm.exclusive = bool(flags & 0x01)
        shm.cached = bool(flags & 0x02)
        self._shms[shm.id] = shm
        return shm

    def register_shm(self, shm: TEESharedMemory) -> int:
        shm.registered = True
        self._shms[shm.id] = shm
        return TEE_SUCCESS

    def release_shm(self, shm_id: int) -> int:
        self._shms.pop(shm_id, None)
        return TEE_SUCCESS

    def invoke_ta(self, session_id: int, op: TEEOperation) -> int:
        if "invoke" in self._ops:
            return self._ops["invoke"](session_id, op)
        return TEE_SUCCESS


# ============================================================================
# TEE Driver
# ============================================================================

@dataclass
class TEEDriver:
    """TEE driver binding."""
    name: str
    ops: Dict[str, Callable] = field(default_factory=dict)
    data: Any = None


# ============================================================================
# TEE Subsystem Manager
# ============================================================================

class TEESubsystem:
    """Central TEE subsystem managing devices and sessions."""

    def __init__(self) -> None:
        self._devices: Dict[int, TEEDevice] = {}
        self._drivers: List[TEEDriver] = []
        self._next_dev_id: int = 0

    def register_device(self, device: TEEDevice) -> int:
        device.id = self._next_dev_id
        device.registered = True
        self._devices[self._next_dev_id] = device
        self._next_dev_id += 1
        return device.id

    def unregister_device(self, dev_id: int) -> int:
        self._devices.pop(dev_id, None)
        return 0

    def get_device(self, dev_id: int) -> Optional[TEEDevice]:
        return self._devices.get(dev_id)

    def enumerate_devices(self) -> List[TEEDevice]:
        return list(self._devices.values())

    def register_driver(self, driver: TEEDriver) -> int:
        self._drivers.append(driver)
        return 0

    def open_session(self, dev_id: int, ta_uuid: str,
                     client_id: int = 0) -> Optional[TEESession]:
        device = self._devices.get(dev_id)
        return device.open_session(ta_uuid, client_id) if device else None

    def close_session(self, dev_id: int, session_id: int) -> int:
        device = self._devices.get(dev_id)
        return device.close_session(session_id) if device else TEE_ERROR_GENERIC


# ============================================================================
# Global TEE Instance
# ============================================================================

_global_tee: Optional[TEESubsystem] = None


def get_global_tee() -> TEESubsystem:
    global _global_tee
    if _global_tee is None:
        _global_tee = TEESubsystem()
    return _global_tee


def register_tee_device(device: TEEDevice) -> int:
    return get_global_tee().register_device(device)


def tee_open_session(dev_id: int, ta_uuid: str) -> Optional[TEESession]:
    return get_global_tee().open_session(dev_id, ta_uuid)
