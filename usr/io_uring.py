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
UmerOS io_uring Module
=======================
Kernel io_uring async I/O interface.
Implements submission/completion rings, SQE/CQE processing.

Reference: docs.kernel.org/userspace-api/io_uring.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import threading


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EAGAIN: int = 11
EINVAL: int = 22
EBADF: int = 9
ENOMEM: int = 12
ENOENT: int = 2
EINTR: int = 4


class IOUringOp(IntEnum):
    """io_uring opcodes."""
    IORING_OP_NOP: int = 0
    IORING_OP_READV: int = 1
    IORING_OP_WRITEV: int = 2
    IORING_OP_FSYNC: int = 3
    IORING_OP_READ_FIXED: int = 4
    IORING_OP_WRITE_FIXED: int = 5
    IORING_OP_POLL_ADD: int = 6
    IORING_OP_POLL_REMOVE: int = 7
    IORING_OP_SYNC_FILE_RANGE: int = 8
    IORING_OP_SENDMSG: int = 9
    IORING_OP_RECVMSG: int = 10
    IORING_OP_TIMEOUT: int = 11
    IORING_OP_TIMEOUT_REMOVE: int = 12
    IORING_OP_ACCEPT: int = 13
    IORING_OP_ASYNC_CANCEL: int = 14
    IORING_OP_LINK_TIMEOUT: int = 15
    IORING_OP_CONNECT: int = 16
    IORING_OP_FALLOCATE: int = 17
    IORING_OP_OPENAT: int = 18
    IORING_OP_CLOSE: int = 19
    IORING_OP_FILES_UPDATE: int = 20
    IORING_OP_STATX: int = 21
    IORING_OP_READ: int = 22
    IORING_OP_WRITE: int = 23
    IORING_OP_FADVISE: int = 24
    IORING_OP_MADVISE: int = 25
    IORING_OP_SEND: int = 26
    IORING_OP_RECV: int = 27
    IORING_OP_OPENAT2: int = 28
    IORING_OP_EPOLL_CTL: int = 29
    IORING_OP_SPLICE: int = 30
    IORING_OP_PROVIDE_BUFFERS: int = 31
    IORING_OP_REMOVE_BUFFERS: int = 32
    IORING_OP_TEE: int = 33
    IORING_OP_SHUTDOWN: int = 34
    IORING_OP_RENAMEAT: int = 35
    IORING_OP_UNLINKAT: int = 36
    IORING_OP_MKDIRAT: int = 37
    IORING_OP_FUTEX_WAIT: int = 38
    IORING_OP_FUTEX_WAKE: int = 39
    IORING_OP_FUTEX_WAITV: int = 40
    IORING_OP_FIXED_FD_INSTALL: int = 41
    IORING_OP_F_TRUNCATE: int = 42


class IOUringSQEFlags(IntEnum):
    """SQE flags."""
    IOSQE_FIXED_FILE: int = 1
    IOSQE_IO_DRAIN: int = 2
    IOSQE_IO_LINK: int = 4
    IOSQE_IO_HARDLINK: int = 8
    IOSQE_ASYNC: int = 16
    IOSQE_BUFFER_SELECT: int = 32


class IOUringSetupFlags(IntEnum):
    """io_uring setup flags."""
    IORING_SETUP_IOPOLL: int = 1
    IORING_SETUP_SQPOLL: int = 2
    IORING_SETUP_SQ_AFF: int = 4
    IORING_SETUP_CQ_NOCOUNT: int = 8
    IORING_SETUP_NOMMQ: int = 16
    IORING_SETUP_ATTACH_WQ: int = 32
    IORING_SETUP_R_DISABLED: int = 64
    IORING_SETUP_SQTASKFD: int = 128
    IORING_SETUP_SQ_ALL: int = 256


class IOUringCQFlags(IntEnum):
    """CQE overflow flags."""
    IORING_CQ_OVERFLOW: int = 1
    IORING_CQ_EVENTFD: int = 2


# ============================================================================
# io_uring Data Structures
# ============================================================================

@dataclass
class IOSQE:
    """IO Submission Queue Entry."""
    opcode: int = 0
    flags: int = 0
    ioprio: int = 0
    fd: int = -1
    off_addr: int = 0
    addr_splice_off: int = 0
    len: int = 0
    op_flags: int = 0
    user_data: int = 0
    buf_index: int = 0
    personality: int = 0
    splice_fd_in: int = 0
    __pad2: int = 0
    _submitted: bool = False


@dataclass
class IOCQE:
    """IO Completion Queue Entry."""
    user_data: int = 0
    res: int = 0
    flags: int = 0
    _consumed: bool = False


@dataclass
class IOBuffer:
    """Registered I/O buffer."""
    addr: int
    len: int
    bgid: int
    bid: int
    registered: bool = True


@dataclass
class IOFileRegistration:
    """Registered file descriptor."""
    fd: int
    fixed_file: bool = True


@dataclass
class IOUringParams:
    """io_uring parameters."""
    sq_entries: int = 4096
    cq_entries: int = 8192
    flags: int = 0
    sq_thread_cpu: int = 0
    sq_thread_idle: int = 10000
    features: int = 0
    wq_fd: int = -1
    resv: List[int] = field(default_factory=lambda: [0, 0, 0])


# ============================================================================
# io_uring Ring Buffers
# ============================================================================

class SubmissionRing:
    """Submission queue ring buffer."""

    def __init__(self, size: int = 4096) -> None:
        self._size = size
        self._entries: List[IOSQE] = [IOSQE() for _ in range(size)]
        self._head: int = 0
        self._tail: int = 0
        self._ring_mask: int = size - 1
        self._array: List[int] = list(range(size))
        self._lock = threading.Lock()

    @property
    def head(self) -> int:
        return self._head

    @property
    def tail(self) -> int:
        return self._tail

    @property
    def entries_available(self) -> int:
        return self._size - (self._tail - self._head)

    def submit(self, sqe: IOSQE) -> int:
        with self._lock:
            if self.entries_available <= 0:
                return -EAGAIN
            idx = self._tail & self._ring_mask
            sqe._submitted = True
            self._entries[idx] = sqe
            self._tail += 1
            return SUCCESS

    def submit_batch(self, sqes: List[IOSQE]) -> int:
        with self._lock:
            for sqe in sqes:
                if self.entries_available <= 0:
                    break
                idx = self._tail & self._ring_mask
                sqe._submitted = True
                self._entries[idx] = sqe
                self._tail += 1
            return SUCCESS

    def peek(self) -> Optional[IOSQE]:
        if self._head == self._tail:
            return None
        idx = self._head & self._ring_mask
        return self._entries[idx]

    def advance_head(self, count: int = 1) -> None:
        self._head += count

    def get_sqe(self, index: int) -> IOSQE:
        return self._entries[index & self._ring_mask]


class CompletionRing:
    """Completion queue ring buffer."""

    def __init__(self, size: int = 8192) -> None:
        self._size = size
        self._entries: List[IOCQE] = [IOCQE() for _ in range(size)]
        self._head: int = 0
        self._tail: int = 0
        self._ring_mask: int = size - 1
        self._overflow: int = 0
        self._eventfd: Optional[int] = None
        self._lock = threading.Lock()

    @property
    def head(self) -> int:
        return self._head

    @property
    def tail(self) -> int:
        return self._tail

    @property
    def count(self) -> int:
        return self._tail - self._head

    @property
    def overflow_count(self) -> int:
        return self._overflow

    def post(self, user_data: int, res: int, flags: int = 0) -> int:
        with self._lock:
            if self.count >= self._size:
                self._overflow += 1
                return -ENOMEM
            idx = self._tail & self._ring_mask
            self._entries[idx] = IOCQE(user_data=user_data, res=res, flags=flags)
            self._tail += 1
            return SUCCESS

    def peek(self) -> Optional[IOCQE]:
        if self._head == self._tail:
            return None
        idx = self._head & self._ring_mask
        cqe = self._entries[idx]
        cqe._consumed = True
        return cqe

    def advance_head(self, count: int = 1) -> None:
        self._head += count

    def drain(self, max_count: int = -1) -> List[IOCQE]:
        result: List[IOCQE] = []
        count = 0
        while self._head < self._tail:
            if max_count >= 0 and count >= max_count:
                break
            cqe = self.peek()
            if cqe:
                result.append(cqe)
                self.advance_head()
                count += 1
        return result

    def set_eventfd(self, fd: int) -> None:
        self._eventfd = fd


# ============================================================================
# io_uring Context
# ============================================================================

@dataclass
class IOUringContext:
    """io_uring instance context."""
    ring_fd: int
    params: IOUringParams
    submission: SubmissionRing
    completion: CompletionRing
    registered_files: List[IOFileRegistration] = field(default_factory=list)
    registered_buffers: List[IOBuffer] = field(default_factory=list)
    enabled: bool = True
    sq_poll_thread: Optional[threading.Thread] = field(default=None, repr=False)
    _cancel_token: threading.Event = field(default_factory=threading.Event, repr=False)


# ============================================================================
# io_uring Manager
# ============================================================================

class IOUringManager:
    """io_uring subsystem manager."""

    def __init__(self) -> None:
        self._rings: Dict[int, IOUringContext] = {}
        self._next_fd: int = 1000
        self._ops: Dict[int, Callable] = {}
        self._register_default_ops()

    def _register_default_ops(self) -> None:
        self._ops[IOUringOp.IORING_OP_NOP] = self._op_nop
        self._ops[IOUringOp.IORING_OP_READ] = self._op_read
        self._ops[IOUringOp.IORING_OP_WRITE] = self._op_write
        self._ops[IOUringOp.IORING_OP_CLOSE] = self._op_close
        self._ops[IOUringOp.IORING_OP_OPENAT] = self._op_openat
        self._ops[IOUringOp.IORING_OP_FSYNC] = self._op_fsync
        self._ops[IOUringOp.IORING_OP_POLL_ADD] = self._op_poll_add
        self._ops[IOUringOp.IORING_OP_TIMEOUT] = self._op_timeout

    def setup(self, params: Optional[IOUringParams] = None) -> int:
        if params is None:
            params = IOUringParams()
        fd = self._next_fd
        self._next_fd += 1
        submission = SubmissionRing(params.sq_entries)
        completion = CompletionRing(params.cq_entries)
        ctx = IOUringContext(
            ring_fd=fd,
            params=params,
            submission=submission,
            completion=completion,
        )
        self._rings[fd] = ctx
        return fd

    def submit(self, ring_fd: int, sqe: IOSQE) -> int:
        if ring_fd not in self._rings:
            return -EINVAL
        ctx = self._rings[ring_fd]
        return ctx.submission.submit(sqe)

    def submit_and_wait(self, ring_fd: int, sqe: IOSQE, wait_count: int = 1) -> List[IOCQE]:
        self.submit(ring_fd, sqe)
        return self.wait(ring_fd, wait_count)

    def wait(self, ring_fd: int, count: int = 1) -> List[IOCQE]:
        if ring_fd not in self._rings:
            return []
        ctx = self._rings[ring_fd]
        result: List[IOCQE] = []
        sqe = ctx.submission.peek()
        if sqe:
            ctx.submission.advance_head()
            handler = self._ops.get(sqe.opcode)
            if handler:
                res = handler(ctx, sqe)
            else:
                res = -ENOSYS
            ctx.completion.post(sqe.user_data, res)
        cqe = ctx.completion.peek()
        if cqe:
            result.append(cqe)
            ctx.completion.advance_head()
        return result

    def peek_cqe(self, ring_fd: int) -> Optional[IOCQE]:
        if ring_fd not in self._rings:
            return None
        return self._rings[ring_fd].completion.peek()

    def cqe_seen(self, ring_fd: int, count: int = 1) -> None:
        if ring_fd in self._rings:
            self._rings[ring_fd].completion.advance_head(count)

    def register_files(self, ring_fd: int, fds: List[int]) -> int:
        if ring_fd not in self._rings:
            return -EINVAL
        ctx = self._rings[ring_fd]
        for fd in fds:
            ctx.registered_files.append(IOFileRegistration(fd=fd))
        return SUCCESS

    def register_buffers(self, ring_fd: int, iovecs: List[tuple]) -> int:
        if ring_fd not in self._rings:
            return -EINVAL
        ctx = self._rings[ring_fd]
        for i, (addr, length) in enumerate(iovecs):
            ctx.registered_buffers.append(IOBuffer(addr=addr, len=length, bgid=0, bid=i))
        return SUCCESS

    def register_eventfd(self, ring_fd: int, eventfd: int) -> int:
        if ring_fd not in self._rings:
            return -EINVAL
        self._rings[ring_fd].completion.set_eventfd(eventfd)
        return SUCCESS

    def shutdown(self, ring_fd: int) -> int:
        ctx = self._rings.pop(ring_fd, None)
        if ctx is None:
            return -EINVAL
        ctx.enabled = False
        ctx._cancel_token.set()
        return SUCCESS

    def get_params(self, ring_fd: int) -> Optional[IOUringParams]:
        if ring_fd in self._rings:
            return self._rings[ring_fd].params
        return None

    # Operation handlers
    def _op_nop(self, ctx: IOUringContext, sqe: IOSQE) -> int:
        return SUCCESS

    def _op_read(self, ctx: IOUringContext, sqe: IOSQE) -> int:
        return sqe.len

    def _op_write(self, ctx: IOUringContext, sqe: IOSQE) -> int:
        return sqe.len

    def _op_close(self, ctx: IOUringContext, sqe: IOSQE) -> int:
        return SUCCESS

    def _op_openat(self, ctx: IOUringContext, sqe: IOSQE) -> int:
        return self._next_fd - 1

    def _op_fsync(self, ctx: IOUringContext, sqe: IOSQE) -> int:
        return SUCCESS

    def _op_poll_add(self, ctx: IOUringContext, sqe: IOSQE) -> int:
        return SUCCESS

    def _op_timeout(self, ctx: IOUringContext, sqe: IOSQE) -> int:
        return SUCCESS


# ============================================================================
# Global Instance
# ============================================================================

_global_io_uring: Optional[IOUringManager] = None


def get_io_uring_manager() -> IOUringManager:
    global _global_io_uring
    if _global_io_uring is None:
        _global_io_uring = IOUringManager()
    return _global_io_uring


def io_uring_setup(entries: int = 4096) -> int:
    params = IOUringParams(sq_entries=entries, cq_entries=entries * 2)
    return get_io_uring_manager().setup(params)


def io_uring_submit(ring_fd: int, opcode: int, fd: int = -1, addr: int = 0, len: int = 0, user_data: int = 0) -> int:
    sqe = IOSQE(opcode=opcode, fd=fd, off_addr=addr, len=len, user_data=user_data)
    return get_io_uring_manager().submit(ring_fd, sqe)


def io_uring_wait(ring_fd: int, count: int = 1) -> List[IOCQE]:
    return get_io_uring_manager().wait(ring_fd, count)
