"""
UmerOS TEE Module
==================
Linux kernel TEE (Trusted Execution Environment) subsystem.
Implements OP-TEE interface, shared memory, and trusted commands.

Reference: docs.kernel.org/userspace-api/tee.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple
import struct
import threading


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOENT: int = 2
EACCES: int = 13
ENOMEM: int = 12
EBUSY: int = 16

TEE_IOC_MAGIC: str = "T"
TEE_IOC_VERSION: int = 0

# OP-TEE constants
OPTEE_CMD_LOGIN_PUBLIC: int = 0
OPTEE_CMD_LOGIN_USER: int = 1
OPTEE_CMD_LOGIN_GROUP: int = 2
OPTEE_CMD_LOGIN_APPLICATION: int = 4

OPTEE_MAX_PARAM_COUNT: int = 4
OPTEE_MAX_BUFFER_SIZE: int = 4096


# ============================================================================
# TEE Enums
# ============================================================================

class TEEParamType(IntEnum):
    """TEE parameter types."""
    TEE_PARAM_TYPE_NONE: int = 0
    TEE_PARAM_TYPE_VALUE_INPUT: int = 1
    TEE_PARAM_TYPE_VALUE_OUTPUT: int = 2
    TEE_PARAM_TYPE_VALUE_INOUT: int = 3
    TEE_PARAM_TYPE_MEMREF_INPUT: int = 4
    TEE_PARAM_TYPE_MEMREF_OUTPUT: int = 5
    TEE_PARAM_TYPE_MEMREF_INOUT: int = 6


class TEEOrigin(IntEnum):
    """TEE command origin."""
    TEE_ORIGIN_API: int = 0
    TEE_ORIGIN_COMMS: int = 1
    TEE_ORIGIN_TEE: int = 2
    TEE_ORIGIN_TRUSTED_APP: int = 3


class TEEError(IntEnum):
    """TEE error codes."""
    TEE_SUCCESS: int = 0
    TEE_ERROR_GENERIC: int = 0xFFFF0000 & 0xFFFFFFFF
    TEE_ERROR_ACCESS_DENIED: int = 0xFFFF0001 & 0xFFFFFFFF
    TEE_ERROR_CANCEL: int = 0xFFFF0002 & 0xFFFFFFFF
    TEE_ERROR_ACCESS_CONFLICT: int = 0xFFFF0003 & 0xFFFFFFFF
    TEE_ERROR_EXCESS_DATA: int = 0xFFFF0004 & 0xFFFFFFFF
    TEE_ERROR_BAD_FORMAT: int = 0xFFFF0005 & 0xFFFFFFFF
    TEE_ERROR_BAD_PARAMETERS: int = 0xFFFF0006 & 0xFFFFFFFF
    TEE_ERROR_BAD_STATE: int = 0xFFFF0007 & 0xFFFFFFFF
    TEE_ERROR_ITEM_NOT_FOUND: int = 0xFFFF0008 & 0xFFFFFFFF
    TEE_ERROR_NOT_IMPLEMENTED: int = 0xFFFF0009 & 0xFFFFFFFF
    TEE_ERROR_NOT_SUPPORTED: int = 0xFFFF000A & 0xFFFFFFFF
    TEE_ERROR_NO_DATA: int = 0xFFFF000B & 0xFFFFFFFF
    TEE_ERROR_OUT_OF_MEMORY: int = 0xFFFF000C & 0xFFFFFFFF
    TEE_ERROR_BUSY: int = 0xFFFF000D & 0xFFFFFFFF
    TEE_ERROR_COMMUNICATION: int = 0xFFFF000E & 0xFFFFFFFF
    TEE_ERROR_SECURITY: int = 0xFFFF000F & 0xFFFFFFFF
    TEE_ERROR_SHORT_BUFFER: int = 0xFFFF0010 & 0xFFFFFFFF


class TEEIoctlCmd(IntEnum):
    """TEE ioctl commands."""
    TEE_IOC_VERSION: int = 0
    TEE_IOC_OPEN_SESSION: int = 1
    TEE_IOC_INVOKE: int = 2
    TEE_IOC_CANCEL: int = 3
    TEE_IOC_CLOSE_SESSION: int = 4
    TEE_IOC_SHM_ALLOC: int = 5
    TEE_IOC_SHM_REGISTER: int = 6


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class TEEParam:
    """TEE parameter."""
    param_type: int = TEEParamType.TEE_PARAM_TYPE_NONE
    value_a: int = 0
    value_b: int = 0
    memref: Optional[bytes] = None
    memref_offset: int = 0
    memref_size: int = 0

    def set_value(self, a: int, b: int) -> None:
        """Set as value parameter."""
        self.param_type = TEEParamType.TEE_PARAM_TYPE_VALUE_INPUT
        self.value_a = a
        self.value_b = b

    def set_value_output(self, a: int, b: int) -> None:
        """Set as value output parameter."""
        self.param_type = TEEParamType.TEE_PARAM_TYPE_VALUE_OUTPUT
        self.value_a = a
        self.value_b = b

    def set_memref_input(self, data: bytes) -> None:
        """Set as memref input parameter."""
        self.param_type = TEEParamType.TEE_PARAM_TYPE_MEMREF_INPUT
        self.memref = data
        self.memref_size = len(data)

    def set_memref_output(self, size: int) -> None:
        """Set as memref output parameter."""
        self.param_type = TEEParamType.TEE_PARAM_TYPE_MEMREF_OUTPUT
        self.memref = b"\x00" * size
        self.memref_size = size

    def pack(self) -> bytes:
        """Pack parameter."""
        result = struct.pack("IIQQ", self.param_type, 0, self.value_a, self.value_b)
        return result

    @classmethod
    def unpack(cls, data: bytes) -> TEEParam:
        """Unpack parameter."""
        param_type, _, value_a, value_b = struct.unpack("IIQQ", data[:24])
        return cls(param_type=param_type, value_a=value_a, value_b=value_b)


@dataclass
class TEESharedMemory:
    """TEE shared memory region."""
    id: int = 0
    size: int = 0
    flags: int = 0
    buffer: Optional[bytearray] = None
    registered: bool = False
    cmd_id: int = 0

    def allocate(self, size: int, flags: int = 0) -> int:
        """Allocate shared memory."""
        self.size = size
        self.flags = flags
        self.buffer = bytearray(size)
        self.registered = True
        return SUCCESS

    def write(self, offset: int, data: bytes) -> int:
        """Write to shared memory."""
        if self.buffer is None:
            return ERROR
        if offset + len(data) > self.size:
            return EINVAL
        self.buffer[offset:offset + len(data)] = data
        return SUCCESS

    def read(self, offset: int, size: int) -> bytes:
        """Read from shared memory."""
        if self.buffer is None:
            return b""
        return bytes(self.buffer[offset:offset + size])

    def free(self) -> int:
        """Free shared memory."""
        self.buffer = None
        self.size = 0
        self.registered = False
        return SUCCESS


@dataclass
class TEECommand:
    """TEE command context."""
    cmd_id: int = 0
    session_id: int = 0
    params: List[TEEParam] = field(default_factory=lambda: [TEEParam() for _ in range(OPTEE_MAX_PARAM_COUNT)])
    origin: int = TEEOrigin.TEE_ORIGIN_API
    ret_origin: int = TEEOrigin.TEE_ORIGIN_API
    ret: int = TEEError.TEE_SUCCESS

    def set_param(self, index: int, param_type: int, value_a: int = 0, value_b: int = 0) -> None:
        """Set a command parameter."""
        if 0 <= index < OPTEE_MAX_PARAM_COUNT:
            self.params[index].param_type = param_type
            self.params[index].value_a = value_a
            self.params[index].value_b = value_b


@dataclass
class TEESession:
    """TEE session to a trusted application."""
    session_id: int = 0
    ctx_id: int = 0
    login_method: int = 0
    uuid: bytes = b""
    client_id: int = 0
    session_origin: int = TEEOrigin.TEE_ORIGIN_API
    commands: Dict[int, Callable[[TEECommand], TEECommand]] = field(default_factory=dict)

    def register_command(self, cmd_id: int, handler: Callable[[TEECommand], TEECommand]) -> None:
        """Register a command handler."""
        self.commands[cmd_id] = handler

    def invoke_command(self, cmd: TEECommand) -> TEECommand:
        """Invoke a command in this session."""
        handler = self.commands.get(cmd.cmd_id)
        if handler:
            return handler(cmd)
        cmd.ret = TEEError.TEE_ERROR_ITEM_NOT_FOUND
        return cmd


@dataclass
class TEEContext:
    """TEE context (connection to TEE)."""
    ctx_id: int = 0
    version: int = 0
    sessions: Dict[int, TEESession] = field(default_factory=dict)
    shared_memories: Dict[int, TEESharedMemory] = field(default_factory=dict)
    _next_session_id: int = 1
    _next_shm_id: int = 1

    def open_session(self, uuid: bytes, login_method: int = OPTEE_CMD_LOGIN_PUBLIC, client_id: int = 0) -> TEESession:
        """Open a session to a trusted application."""
        session = TEESession(
            session_id=self._next_session_id,
            ctx_id=self.ctx_id,
            login_method=login_method,
            uuid=uuid,
            client_id=client_id
        )
        self.sessions[self._next_session_id] = session
        self._next_session_id += 1
        return session

    def close_session(self, session_id: int) -> int:
        """Close a session."""
        self.sessions.pop(session_id, None)
        return SUCCESS

    def alloc_shared_memory(self, size: int, flags: int = 0) -> TEESharedMemory:
        """Allocate shared memory."""
        shm = TEESharedMemory(id=self._next_shm_id)
        shm.allocate(size, flags)
        self.shared_memories[self._next_shm_id] = shm
        self._next_shm_id += 1
        return shm

    def free_shared_memory(self, shm_id: int) -> int:
        """Free shared memory."""
        shm = self.shared_memories.pop(shm_id, None)
        if shm:
            shm.free()
        return SUCCESS


# ============================================================================
# TEE Subsystem
# ============================================================================

class TEE:
    """Linux TEE subsystem."""
    def __init__(self) -> None:
        self.contexts: Dict[int, TEEContext] = {}
        self._next_ctx_id: int = 1
        self.lock: threading.Lock = threading.Lock()

    def open_context(self) -> TEEContext:
        """Open a TEE context."""
        with self.lock:
            ctx = TEEContext(ctx_id=self._next_ctx_id, version=1)
            self.contexts[self._next_ctx_id] = ctx
            self._next_ctx_id += 1
        return ctx

    def close_context(self, ctx_id: int) -> int:
        """Close a TEE context."""
        with self.lock:
            self.contexts.pop(ctx_id, None)
        return SUCCESS

    def get_version(self) -> Dict[str, Any]:
        """Get TEE version info."""
        return {
            "version_major": 1,
            "version_minor": 0,
            "gen_caps": 0x1,
            "impl_id": "UmerOS-TEE",
            "impl_version": 1,
        }

    def get_context(self, ctx_id: int) -> Optional[TEEContext]:
        """Get a TEE context."""
        return self.contexts.get(ctx_id)

    def get_stats(self) -> Dict[str, int]:
        """Get TEE statistics."""
        total_sessions = sum(len(ctx.sessions) for ctx in self.contexts.values())
        total_shm = sum(len(ctx.shared_memories) for ctx in self.contexts.values())
        return {
            "contexts": len(self.contexts),
            "sessions": total_sessions,
            "shared_memories": total_shm,
        }


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_tee: Optional[TEE] = None


def get_global_tee() -> TEE:
    """Get global TEE instance."""
    global _global_tee
    if _global_tee is None:
        _global_tee = TEE()
    return _global_tee
