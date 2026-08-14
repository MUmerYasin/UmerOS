"""
UmerOS System Calls Module
===========================
Kernel system call interfaces for userspace.
Implements unshare, futex2, restartable sequences, mseal.

Reference: docs.kernel.org/userspace-api/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import time
import threading


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOMEM: int = 12
EPERM: int = 13
ENOSYS: int = 38


class CloneFlags(IntEnum):
    """Clone flags for unshare/clone."""
    CLONE_VM: int = 0x00000100
    CLONE_FS: int = 0x00000200
    CLONE_FILES: int = 0x00000400
    CLONE_SIGHAND: int = 0x00000800
    CLONE_PIDFD: int = 0x00200000
    CLONE_THREAD: int = 0x00100000
    CLONE_NEWNS: int = 0x00020000
    CLONE_NEWCGROUP: int = 0x02000000
    CLONE_NEWUTS: int = 0x04000000
    CLONE_NEWIPC: int = 0x08000000
    CLONE_NEWUSER: int = 0x10000000
    CLONE_NEWPID: int = 0x20000000
    CLONE_NEWNET: int = 0x40000000


class FutexOp(IntEnum):
    """Futex operations."""
    FUTEX_WAIT: int = 0
    FUTEX_WAKE: int = 1
    FUTEX_FD: int = 2
    FUTEX_REQUEUE: int = 3
    FUTEX_CMP_REQUEUE: int = 4
    FUTEX_WAKE_OP: int = 5
    FUTEX_LOCK_PI: int = 6
    FUTEX_UNLOCK_PI: int = 7
    FUTEX_TRYLOCK_PI: int = 8
    FUTEX_WAIT_BITSET: int = 9
    FUTEX_WAKE_BITSET: int = 10
    FUTEX_WAIT_REQUEUE_PI: int = 11
    FUTEX_CMP_REQUEUE_PI: int = 12


class FutexFlags(IntEnum):
    """Futex flags."""
    FUTEX_PRIVATE_FLAG: int = 128
    FUTEX_CLOCK_REALTIME: int = 256


class RseqFlags(IntEnum):
    """Restartable sequence flags."""
    RSEQ_SIG: int = 0x53053053


class RseqCS(IntEnum):
    """Rseq critical section flags."""
    RSEQ_CS_IDLE: int = 0
    RSEQ_CS_ACTIVE: int = 1
    RSEQ_CS_PREEMPTED: int = 2
    RSEQ_CS_ACTIVE_PREEMPTED: int = 3


class SealOp(IntEnum):
    """mseal operations."""
    MSEAL_SET: int = 1
    MSEAL_UNSET: int = 2


class SealFlags(IntEnum):
    """mseal flags."""
    MSEAL_WRITE: int = 1
    MSEAL_READ: int = 2
    MSEAL_EXEC: int = 4
    MSEAL_MPROTECT: int = 8


# ============================================================================
# Unshare
# ============================================================================

@dataclass
class Namespace:
    """Namespace instance."""
    name: str
    flags: int
    user_ns: int = 0
    pid: int = 0
    refs: int = 1


@dataclass
class UnshareContext:
    """Process unshare context."""
    pid: int
    namespaces: Dict[str, Namespace] = field(default_factory=dict)
    flags: int = 0


class UnshareManager:
    """Manages namespace isolation (unshare syscall)."""

    def __init__(self) -> None:
        self._contexts: Dict[int, UnshareContext] = {}
        self._ns_counter: int = 1

    def unshare(self, pid: int, flags: int) -> int:
        if pid not in self._contexts:
            self._contexts[pid] = UnshareContext(pid=pid)
        ctx = self._contexts[pid]
        ctx.flags |= flags
        ns_types = []
        if flags & CloneFlags.CLONE_NEWNS:
            ns_types.append("mount")
        if flags & CloneFlags.CLONE_NEWUTS:
            ns_types.append("uts")
        if flags & CloneFlags.CLONE_NEWIPC:
            ns_types.append("ipc")
        if flags & CloneFlags.CLONE_NEWUSER:
            ns_types.append("user")
        if flags & CloneFlags.CLONE_NEWPID:
            ns_types.append("pid")
        if flags & CloneFlags.CLONE_NEWNET:
            ns_types.append("net")
        if flags & CloneFlags.CLONE_NEWCGROUP:
            ns_types.append("cgroup")
        for ns_name in ns_types:
            ctx.namespaces[ns_name] = Namespace(
                name=ns_name,
                flags=flags,
                user_ns=self._ns_counter,
                pid=pid,
            )
            self._ns_counter += 1
        return SUCCESS

    def get_namespaces(self, pid: int) -> Dict[str, Namespace]:
        ctx = self._contexts.get(pid)
        return ctx.namespaces if ctx else {}

    def cleanup(self, pid: int) -> int:
        self._contexts.pop(pid, None)
        return SUCCESS


# ============================================================================
# Futex2
# ============================================================================

@dataclass
class FutexWaiter:
    """Futex waiter."""
    tid: int
    addr: int
    timeout_ns: int = 0
    bitset: int = 0
    woken: bool = False


@dataclass
class FutexEntry:
    """Futex hash table entry."""
    addr: int
    value: int = 0
    waiters: List[FutexWaiter] = field(default_factory=list)
    owner: int = 0
    refcount: int = 0


class Futex2Manager:
    """Futex2 syscall manager."""

    def __init__(self, max_futexes: int = 4096) -> None:
        self._futexes: Dict[int, FutexEntry] = {}
        self._max = max_futexes

    def wait(self, addr: int, expected: int, tid: int, timeout_ns: int = 0, bitset: int = 0xFFFFFFFF) -> int:
        if len(self._futexes) >= self._max:
            return ENOMEM
        if addr not in self._futexes:
            self._futexes[addr] = FutexEntry(addr=addr)
        entry = self._futexes[addr]
        if entry.value != expected:
            return EINVAL
        waiter = FutexWaiter(tid=tid, addr=addr, timeout_ns=timeout_ns, bitset=bitset)
        entry.waiters.append(waiter)
        return SUCCESS

    def wake(self, addr: int, count: int, bitset: int = 0xFFFFFFFF) -> int:
        if addr not in self._futexes:
            return 0
        entry = self._futexes[addr]
        woken: int = 0
        remaining: List[FutexWaiter] = []
        for waiter in entry.waiters:
            if waiter.bitset & bitset and woken < count:
                waiter.woken = True
                woken += 1
            else:
                remaining.append(waiter)
        entry.waiters = remaining
        return woken

    def wake_op(self, addr: int, addr2: int, val: int, val2: int, op: int) -> int:
        if addr not in self._futexes:
            return EINVAL
        entry = self._futexes[addr]
        oldval = entry.value
        if op & 1:
            entry.value = val
        elif op & 2:
            entry.value = oldval + val
        elif op & 4:
            entry.value = oldval - val
        elif op & 8:
            entry.value = oldval | val
        elif op & 16:
            entry.value = oldval & val
        woken: int = 0
        if (op >> 24) & 0xFF == 0:
            woken = self.wake(addr, val2)
        return woken

    def cmp_requeue(self, addr: int, addr2: int, expected: int, count: int) -> int:
        if addr not in self._futexes:
            return EINVAL
        entry = self._futexes[addr]
        if entry.value != expected:
            return EINVAL
        if addr2 not in self._futexes:
            self._futexes[addr2] = FutexEntry(addr=addr2)
        entry2 = self._futexes[addr2]
        requeued: int = 0
        remaining: List[FutexWaiter] = []
        for waiter in entry.waiters:
            if requeued < count:
                entry2.waiters.append(waiter)
                requeued += 1
            else:
                remaining.append(waiter)
        entry.waiters = remaining
        return requeued

    def get_value(self, addr: int) -> int:
        if addr in self._futexes:
            return self._futexes[addr].value
        return 0

    def set_value(self, addr: int, value: int) -> int:
        if addr not in self._futexes:
            self._futexes[addr] = FutexEntry(addr=addr)
        self._futexes[addr].value = value
        return SUCCESS


# ============================================================================
# Restartable Sequences (rseq)
# ============================================================================

@dataclass
class RseqCSBase:
    """Rseq critical section."""
    start_ip: int = 0
    post_commit_offset: int = 0
    abort_ip: int = 0


@dataclass
class RseqThread:
    """Per-thread rseq state."""
    tid: int
    cs: RseqCSBase = field(default_factory=RseqCSBase)
    state: RseqCS = RseqCS.RSEQ_CS_IDLE
    cpu_id: int = 0
    node_id: int = 0
    cs_flags: int = 0
    signal_pending: bool = False


class RseqManager:
    """Restartable sequences manager."""

    def __init__(self) -> None:
        self._threads: Dict[int, RseqThread] = {}

    def register_thread(self, tid: int) -> int:
        self._threads[tid] = RseqThread(tid=tid)
        return SUCCESS

    def unregister_thread(self, tid: int) -> int:
        self._threads.pop(tid, None)
        return SUCCESS

    def begin_cs(self, tid: int, cs: RseqCSBase) -> int:
        if tid not in self._threads:
            return EINVAL
        thread = self._threads[tid]
        thread.cs = cs
        thread.state = RseqCS.RSEQ_CS_ACTIVE
        return SUCCESS

    def commit_cs(self, tid: int) -> int:
        if tid not in self._threads:
            return EINVAL
        self._threads[tid].state = RseqCS.RSEQ_CS_IDLE
        self._threads[tid].cs = RseqCSBase()
        return SUCCESS

    def abort_cs(self, tid: int) -> int:
        if tid not in self._threads:
            return EINVAL
        self._threads[tid].state = RseqCS.RSEQ_CS_IDLE
        self._threads[tid].cs = RseqCSBase()
        return SUCCESS

    def get_state(self, tid: int) -> Optional[RseqThread]:
        return self._threads.get(tid)

    def preempt(self, tid: int) -> int:
        if tid not in self._threads:
            return EINVAL
        thread = self._threads[tid]
        if thread.state == RseqCS.RSEQ_CS_ACTIVE:
            thread.state = RseqCS.RSEQ_CS_PREEMPTED
            thread.signal_pending = True
        return SUCCESS


# ============================================================================
# mseal (Memory Seal)
# ============================================================================

@dataclass
class MemorySeal:
    """Memory seal entry."""
    addr: int
    size: int
    flags: int
    pid: int


class MsealManager:
    """Memory sealing manager."""

    def __init__(self) -> None:
        self._seals: List[MemorySeal] = []

    def mseal(self, addr: int, size: int, flags: int, pid: int) -> int:
        if addr == 0 or size == 0:
            return EINVAL
        for seal in self._seals:
            if seal.addr == addr and seal.pid == pid:
                return EEXIST
        self._seals.append(MemorySeal(addr=addr, size=size, flags=flags, pid=pid))
        return SUCCESS

    def check_seal(self, addr: int, pid: int, flag: int) -> bool:
        for seal in self._seals:
            if seal.pid == pid and seal.addr <= addr < seal.addr + seal.size:
                return bool(seal.flags & flag)
        return False

    def remove_seal(self, addr: int, pid: int) -> int:
        for i, seal in enumerate(self._seals):
            if seal.addr == addr and seal.pid == pid:
                self._seals.pop(i)
                return SUCCESS
        return EINVAL

    def get_seals(self, pid: int) -> List[MemorySeal]:
        return [s for s in self._seals if s.pid == pid]


# ============================================================================
# Global Instances
# ============================================================================

_global_unshare: Optional[UnshareManager] = None
_global_futex: Optional[Futex2Manager] = None
_global_rseq: Optional[RseqManager] = None
_global_mseal: Optional[MsealManager] = None


def get_unshare_manager() -> UnshareManager:
    global _global_unshare
    if _global_unshare is None:
        _global_unshare = UnshareManager()
    return _global_unshare


def get_futex_manager() -> Futex2Manager:
    global _global_futex
    if _global_futex is None:
        _global_futex = Futex2Manager()
    return _global_futex


def get_rseq_manager() -> RseqManager:
    global _global_rseq
    if _global_rseq is None:
        _global_rseq = RseqManager()
    return _global_rseq


def get_mseal_manager() -> MsealManager:
    global _global_mseal
    if _global_mseal is None:
        _global_mseal = MsealManager()
    return _global_mseal
