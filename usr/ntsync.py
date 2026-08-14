"""
UmerOS ntsync Module
=====================
Kernel ntsync (NT synchronization) subsystem.
Implements Windows NT-style synchronization primitives for Wine/Proton.

Reference: docs.kernel.org/userspace-api/ntsync.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import threading
import time


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOENT: int = 2
EACCES: int = 13
EAGAIN: int = 11
ETIMEDOUT: int = 110
EBUSY: int = 16

NTSYNC_IOC_MAGIC: str = "N"

NTSYNC_MUTEX_MODE_ANY: int = 0x1
NTSYNC_SEMA_MODE_MAXIMUM: int = 0x1

NTSYNC_MAX_WAIT_OBJECTS: int = 64

NTSYNC_WAIT_INFINITE: int = 0xFFFFFFFF


# ============================================================================
# ntsync Enums
# ============================================================================

class NTSyncObjType(IntEnum):
    """NT synchronization object types."""
    NTSYNC_OBJ_SEMAPHORE: int = 1
    NTSYNC_OBJ_MUTEX: int = 2
    NTSYNC_OBJ_EVENT: int = 3


class NTSyncEventType(IntEnum):
    """NT event types."""
    NTSYNC_EVENT_AUTO_RESET: int = 0
    NTSYNC_EVENT_MANUAL_RESET: int = 1


class NTSyncWaitResult(IntEnum):
    """NT wait results."""
    NTSYNC_WAIT_OK: int = 0
    NTSYNC_WAIT_ABANDONED: int = 1
    NTSYNC_WAIT_ALERTED: int = 2
    NTSYNC_WAIT_TIMEOUT: int = 3
    NTSYNC_WAIT_FAILED: int = 4


class NTSyncIoctlCmd(IntEnum):
    """NTsync ioctl commands."""
    NTSYNC_IOC_CREATE_SEMAPHORE: int = 0
    NTSYNC_IOC_CREATE_MUTEX: int = 1
    NTSYNC_IOC_CREATE_EVENT: int = 2
    NTSYNC_IOC_SEMAPHORE_POST: int = 3
    NTSYNC_IOC_SEMAPHORE_QUERY: int = 4
    NTSYNC_IOC_MUTEX_QUERY: int = 5
    NTSYNC_IOC_EVENT_QUERY: int = 6
    NTSYNC_IOC_EVENT_SET: int = 7
    NTSYNC_IOC_EVENT_RESET: int = 8
    NTSYNC_IOC_WAIT_OBJECTS: int = 9
    NTSYNC_IOC_ALERT: int = 10


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class NTSyncSemObj:
    """NT semaphore object."""
    obj_id: int = 0
    count: int = 0
    max_count: int = 0x7FFFFFFF
    owner_tid: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    waiters: Set[int] = field(default_factory=set)

    def post(self, count: int = 1) -> int:
        """Release the semaphore (increment count)."""
        with self.lock:
            if self.count + count > self.max_count:
                return ERROR
            self.count += count
            return SUCCESS

    def try_wait(self) -> bool:
        """Try to acquire the semaphore."""
        with self.lock:
            if self.count > 0:
                self.count -= 1
                return True
            return False

    def query(self) -> Tuple[int, int]:
        """Query semaphore state."""
        with self.lock:
            return self.count, self.max_count

    def add_waiter(self, tid: int) -> None:
        """Add a waiter."""
        with self.lock:
            self.waiters.add(tid)

    def remove_waiter(self, tid: int) -> None:
        """Remove a waiter."""
        with self.lock:
            self.waiters.discard(tid)


@dataclass
class NTSyncMutexObj:
    """NT mutex object."""
    obj_id: int = 0
    owner_tid: int = 0
    count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    waiters: Set[int] = field(default_factory=set)
    abandoned: bool = False

    def try_lock(self, tid: int, any_mode: bool = False) -> int:
        """Try to acquire the mutex."""
        with self.lock:
            if self.count == 0:
                self.owner_tid = tid
                self.count = 1
                return SUCCESS
            if self.owner_tid == tid:
                self.count += 1
                return SUCCESS
            if any_mode:
                return NTSyncWaitResult.NTSYNC_WAIT_ABANDONED
            return EAGAIN

    def unlock(self, tid: int) -> int:
        """Release the mutex."""
        with self.lock:
            if self.owner_tid != tid:
                return EACCES
            self.count -= 1
            if self.count == 0:
                self.owner_tid = 0
            return SUCCESS

    def query(self) -> Tuple[int, int]:
        """Query mutex state (owner_tid, count)."""
        with self.lock:
            return self.owner_tid, self.count

    def add_waiter(self, tid: int) -> None:
        """Add a waiter."""
        with self.lock:
            self.waiters.add(tid)

    def remove_waiter(self, tid: int) -> None:
        """Remove a waiter."""
        with self.lock:
            self.waiters.discard(tid)


@dataclass
class NTSyncEventObj:
    """NT event object."""
    obj_id: int = 0
    event_type: int = NTSyncEventType.NTSYNC_EVENT_AUTO_RESET
    signaled: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)
    waiters: Set[int] = field(default_factory=set)

    def set(self) -> int:
        """Set the event (signal)."""
        with self.lock:
            self.signaled = True
            return SUCCESS

    def reset(self) -> int:
        """Reset the event."""
        with self.lock:
            self.signaled = False
            return SUCCESS

    def try_wait(self) -> bool:
        """Try to wait on the event."""
        with self.lock:
            if self.signaled:
                if self.event_type == NTSyncEventType.NTSYNC_EVENT_AUTO_RESET:
                    self.signaled = False
                return True
            return False

    def query(self) -> bool:
        """Query event state."""
        with self.lock:
            return self.signaled

    def add_waiter(self, tid: int) -> None:
        """Add a waiter."""
        with self.lock:
            self.waiters.add(tid)

    def remove_waiter(self, tid: int) -> None:
        """Remove a waiter."""
        with self.lock:
            self.waiters.discard(tid)


@dataclass
class NTSyncWaitEntry:
    """Wait entry for wait operations."""
    obj_id: int = 0
    obj_type: int = 0
    timeout: int = NTSYNC_WAIT_INFINITE
    alertable: bool = False
    index: int = 0


@dataclass
class NTSyncWaitResult:
    """Result of a wait operation."""
    index: int = 0
    reason: int = NTSyncWaitResult.NTSYNC_WAIT_OK
    owner_tid: int = 0

    def __init__(self, index: int = 0, reason: int = NTSyncWaitResult.NTSYNC_WAIT_OK,
                 owner_tid: int = 0) -> None:
        self.index = index
        self.reason = reason
        self.owner_tid = owner_tid


@dataclass
class NTSyncThreadAlert:
    """Thread alert state."""
    tid: int = 0
    alerted: bool = False

    def alert(self) -> None:
        """Set thread as alerted."""
        self.alerted = True

    def clear(self) -> bool:
        """Clear alert status and return previous state."""
        prev = self.alerted
        self.alerted = False
        return prev


# ============================================================================
# ntsync Subsystem
# ============================================================================

class NTSync:
    """ NT synchronization subsystem."""
    def __init__(self) -> None:
        self.semaphores: Dict[int, NTSyncSemObj] = {}
        self.mutexes: Dict[int, NTSyncMutexObj] = {}
        self.events: Dict[int, NTSyncEventObj] = {}
        self.thread_alerts: Dict[int, NTSyncThreadAlert] = {}
        self._next_obj_id: int = 1
        self.lock: threading.Lock = threading.Lock()

    def create_semaphore(self, initial_count: int, max_count: int) -> NTSyncSemObj:
        """Create an NT semaphore."""
        with self.lock:
            sem = NTSyncSemObj(
                obj_id=self._next_obj_id,
                count=initial_count,
                max_count=max_count
            )
            self.semaphores[self._next_obj_id] = sem
            self._next_obj_id += 1
        return sem

    def create_mutex(self, initial_owner: int = 0) -> NTSyncMutexObj:
        """Create an NT mutex."""
        with self.lock:
            mutex = NTSyncMutexObj(obj_id=self._next_obj_id)
            if initial_owner:
                mutex.owner_tid = initial_owner
                mutex.count = 1
            self.mutexes[self._next_obj_id] = mutex
            self._next_obj_id += 1
        return mutex

    def create_event(self, event_type: int = NTSyncEventType.NTSYNC_EVENT_AUTO_RESET,
                     initial_state: bool = False) -> NTSyncEventObj:
        """Create an NT event."""
        with self.lock:
            event = NTSyncEventObj(
                obj_id=self._next_obj_id,
                event_type=event_type,
                signaled=initial_state
            )
            self.events[self._next_obj_id] = event
            self._next_obj_id += 1
        return event

    def post_semaphore(self, obj_id: int, count: int = 1) -> int:
        """Post to a semaphore."""
        sem = self.semaphores.get(obj_id)
        if sem:
            return sem.post(count)
        return ENOENT

    def query_semaphore(self, obj_id: int) -> Optional[Tuple[int, int]]:
        """Query semaphore state."""
        sem = self.semaphores.get(obj_id)
        if sem:
            return sem.query()
        return None

    def lock_mutex(self, obj_id: int, tid: int, any_mode: bool = False) -> int:
        """Lock a mutex."""
        mutex = self.mutexes.get(obj_id)
        if mutex:
            return mutex.try_lock(tid, any_mode)
        return ENOENT

    def unlock_mutex(self, obj_id: int, tid: int) -> int:
        """Unlock a mutex."""
        mutex = self.mutexes.get(obj_id)
        if mutex:
            return mutex.unlock(tid)
        return ENOENT

    def query_mutex(self, obj_id: int) -> Optional[Tuple[int, int]]:
        """Query mutex state."""
        mutex = self.mutexes.get(obj_id)
        if mutex:
            return mutex.query()
        return None

    def set_event(self, obj_id: int) -> int:
        """Set an event."""
        event = self.events.get(obj_id)
        if event:
            return event.set()
        return ENOENT

    def reset_event(self, obj_id: int) -> int:
        """Reset an event."""
        event = self.events.get(obj_id)
        if event:
            return event.reset()
        return ENOENT

    def query_event(self, obj_id: int) -> Optional[bool]:
        """Query event state."""
        event = self.events.get(obj_id)
        if event:
            return event.query()
        return None

    def wait_objects(self, entries: List[NTSyncWaitEntry], tid: int,
                     timeout_ms: int = NTSYNC_WAIT_INFINITE) -> NTSyncWaitResult:
        """Wait on multiple objects."""
        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0 if timeout_ms != NTSYNC_WAIT_INFINITE else None

        while True:
            for i, entry in enumerate(entries):
                if entry.obj_type == NTSyncObjType.NTSYNC_OBJ_SEMAPHORE:
                    sem = self.semaphores.get(entry.obj_id)
                    if sem and sem.try_wait():
                        return NTSyncWaitResult(index=i, reason=NTSyncWaitResult.NTSYNC_WAIT_OK)

                elif entry.obj_type == NTSyncObjType.NTSYNC_OBJ_MUTEX:
                    mutex = self.mutexes.get(entry.obj_id)
                    if mutex:
                        result = mutex.try_lock(tid, any_mode=bool(entry.obj_type & NTSYNC_MUTEX_MODE_ANY))
                        if result == SUCCESS:
                            return NTSyncWaitResult(index=i, reason=NTSyncWaitResult.NTSYNC_WAIT_OK)

                elif entry.obj_type == NTSyncObjType.NTSYNC_OBJ_EVENT:
                    event = self.events.get(entry.obj_id)
                    if event and event.try_wait():
                        return NTSyncWaitResult(index=i, reason=NTSyncWaitResult.NTSYNC_WAIT_OK)

            if timeout_sec and (time.time() - start_time) >= timeout_sec:
                return NTSyncWaitResult(reason=NTSyncWaitResult.NTSYNC_WAIT_TIMEOUT)

            if timeout_ms == 0:
                break

            time.sleep(0.001)

        return NTSyncWaitResult(reason=NTSyncWaitResult.NTSYNC_WAIT_TIMEOUT)

    def alert_thread(self, tid: int) -> int:
        """Alert a waiting thread."""
        with self.lock:
            alert = self.thread_alerts.get(tid)
            if alert:
                alert.alert()
                return SUCCESS
            self.thread_alerts[tid] = NTSyncThreadAlert(tid=tid, alerted=True)
        return SUCCESS

    def is_thread_alerted(self, tid: int) -> bool:
        """Check if a thread is alerted."""
        alert = self.thread_alerts.get(tid)
        if alert:
            return alert.clear()
        return False

    def get_stats(self) -> Dict[str, int]:
        """Get ntsync statistics."""
        return {
            "semaphores": len(self.semaphores),
            "mutexes": len(self.mutexes),
            "events": len(self.events),
            "threads": len(self.thread_alerts),
        }


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_ntsync: Optional[NTSync] = None


def get_global_ntsync() -> NTSync:
    """Get global NTSync instance."""
    global _global_ntsync
    if _global_ntsync is None:
        _global_ntsync = NTSync()
    return _global_ntsync
