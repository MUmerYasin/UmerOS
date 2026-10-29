"""UmerOS High-Performance Synchronous IPC Fastpath & Shared Memory Transport.

Microkernel synchronous fastpath IPC with
thread-handoff scheduling and zero-copy shared memory channels.
"""
from __future__ import annotations

from .fastpath import SynchronousIPCFastpath
from .shm_transport import SharedMemoryChannel
from .message_protocol import PackedMessage, PackedHeader

__all__ = [
    "SynchronousIPCFastpath",
    "SharedMemoryChannel",
    "PackedMessage",
    "PackedHeader",
]