"""
Umer OS /compatibility/sync — Win32 synchronization primitives
============================================================

Pure-Python implementation of the four user-mode synchronization
primitives introduced in Windows Vista (and still widely used by every
Windows application):

* ``CRITICAL_SECTION`` (NT 4+) — recursive mutex.
* ``SRWLOCK`` (Vista+) — slim reader/writer lock.
* ``CONDITION_VARIABLE`` (Vista+) — condition variable; pairs with a
  critical section or an SRW lock.
* ``INIT_ONCE`` (Vista+) — one-time initialisation primitive.

The structs themselves are opaque in Win32 (their layouts are
undocumented), so we back them with Python objects addressed by
``id()`` and hand callers a small integer handle that they treat as
a pointer.

The functions follow the Win32 semantics:

* ``InitializeCriticalSection`` / ``InitializeSRWLock`` /
  ``InitializeConditionVariable`` / ``InitOnceInitialize`` are
  idempotent — calling them twice on the same object is harmless.
* ``AcquireSRWLockExclusive`` blocks until the lock is available.
* ``TryEnterCriticalSection`` / ``TryAcquireSRWLockExclusive`` return
  a boolean; ``SleepConditionVariableCS/SRW`` waits on the condition
  variable and atomically releases the lock.
* ``InitOnceExecuteOnce`` ensures the supplied callback runs exactly
  once for the first thread that wins the race; later threads wait
  for completion.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/sync/synchronization-functions
* https://learn.microsoft.com/en-us/windows/win32/sync/slim-reader-writer--srw--locks

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.Sync")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INFINITE = 0xFFFFFFFF

# SRW lock + condition-variable modes.
CONDITION_VARIABLE_LOCKMODE_SHARED = 0x01

# INIT_ONCE flags + state.
INIT_ONCE_ASYNC                  = 0x00000002
INIT_ONCE_CHECK_ONLY             = 0x00000004
INIT_ONCE_CTX_RESERVED_BITS      = 2
INIT_ONCE_INIT_FAILED            = 0x00000001

# Win32 error codes (subset).
ERROR_SUCCESS              = 0
ERROR_TIMEOUT              = 0x000005B4
ERROR_INVALID_PARAMETER    = 0x00000057
ERROR_NOT_ENOUGH_MEMORY    = 0x00000008


# ---------------------------------------------------------------------------
# CRITICAL_SECTION
# ---------------------------------------------------------------------------

@dataclass
class CriticalSection:
    """A Win32 ``CRITICAL_SECTION`` equivalent."""

    lock: threading.RLock = field(default_factory=threading.RLock)
    owner_thread: Optional[int] = None
    lock_count: int = 0
    spin_count: int = 0


def _resolve_cs(handle: int) -> Optional[CriticalSection]:
    return _HANDLES.get(handle) if handle in _HANDLES else None


def InitializeCriticalSection(handle: int) -> None:
    cs = _resolve_cs(handle)
    if cs is None:
        return
    if not cs.lock.acquire(blocking=False):
        return        # already owned by this thread -- idempotent
    cs.lock.release()


def InitializeCriticalSectionAndSpinCount(handle: int, spin_count: int) -> bool:
    cs = _resolve_cs(handle)
    if cs is None:
        return False
    cs.spin_count = spin_count
    InitializeCriticalSection(handle)
    return True


def InitializeCriticalSectionEx(handle: int, spin_count: int,
                                flags: int = 0) -> bool:
    return InitializeCriticalSectionAndSpinCount(handle, spin_count)


def EnterCriticalSection(handle: int) -> None:
    cs = _resolve_cs(handle)
    if cs is None:
        return
    cs.lock.acquire()
    cs.owner_thread = threading.get_ident()
    cs.lock_count += 1


def TryEnterCriticalSection(handle: int) -> bool:
    cs = _resolve_cs(handle)
    if cs is None:
        return False
    if cs.lock.acquire(blocking=False):
        cs.owner_thread = threading.get_ident()
        cs.lock_count += 1
        return True
    return False


def LeaveCriticalSection(handle: int) -> None:
    cs = _resolve_cs(handle)
    if cs is None:
        return
    if cs.lock_count <= 0:
        return        # unbalanced -- ignore
    cs.lock_count -= 1
    cs.lock.release()


def DeleteCriticalSection(handle: int) -> None:
    _HANDLES.pop(handle, None)


def SetCriticalSectionSpinCount(handle: int, spin_count: int) -> int:
    cs = _resolve_cs(handle)
    if cs is None:
        return 0
    cs.spin_count = spin_count
    return spin_count


# ---------------------------------------------------------------------------
# SRW Lock
# ---------------------------------------------------------------------------

class SRWMode(IntEnum):
    SHARED = 1
    EXCLUSIVE = 2


@dataclass
class SrwLock:
    """Slim reader/writer lock."""

    readers: int = 0
    writer: bool = False
    writer_event: threading.Event = field(default_factory=threading.Event)
    # Waiters that need to be released when the current writer drops
    # the lock.  ``threading.Condition`` is the simplest portable way.
    cond: threading.Condition = field(default_factory=threading.Condition)


def _resolve_srw(handle: int) -> Optional[SrwLock]:
    obj = _HANDLES.get(handle)
    if isinstance(obj, SrwLock):
        return obj
    return None


def InitializeSRWLock(handle: int) -> None:
    srw = _resolve_srw(handle)
    if srw is None:
        return
    srw.readers = 0
    srw.writer = False
    srw.writer_event.set()


def AcquireSRWLockShared(handle: int) -> None:
    srw = _resolve_srw(handle)
    if srw is None:
        return
    with srw.cond:
        while srw.writer:
            srw.cond.wait()
        srw.readers += 1


def AcquireSRWLockExclusive(handle: int) -> None:
    srw = _resolve_srw(handle)
    if srw is None:
        return
    with srw.cond:
        while srw.writer or srw.readers > 0:
            srw.cond.wait()
        srw.writer = True
        srw.writer_event.clear()


def TryAcquireSRWLockShared(handle: int) -> bool:
    srw = _resolve_srw(handle)
    if srw is None:
        return False
    with srw.cond:
        if srw.writer:
            return False
        srw.readers += 1
        return True


def TryAcquireSRWLockExclusive(handle: int) -> bool:
    srw = _resolve_srw(handle)
    if srw is None:
        return False
    with srw.cond:
        if srw.writer or srw.readers > 0:
            return False
        srw.writer = True
        srw.writer_event.clear()
        return True


def ReleaseSRWLockShared(handle: int) -> None:
    srw = _resolve_srw(handle)
    if srw is None or srw.readers <= 0:
        return
    with srw.cond:
        srw.readers -= 1
        if srw.readers == 0:
            srw.cond.notify_all()


def ReleaseSRWLockExclusive(handle: int) -> None:
    srw = _resolve_srw(handle)
    if srw is None or not srw.writer:
        return
    with srw.cond:
        srw.writer = False
        srw.writer_event.set()
        srw.cond.notify_all()


# ---------------------------------------------------------------------------
# CONDITION_VARIABLE
# ---------------------------------------------------------------------------

@dataclass
class ConditionVariable:
    cond: threading.Condition = field(default_factory=threading.Condition)
    waiters: int = 0


def _resolve_cv(handle: int) -> Optional[ConditionVariable]:
    obj = _HANDLES.get(handle)
    if isinstance(obj, ConditionVariable):
        return obj
    return None


def InitializeConditionVariable(handle: int) -> None:
    cv = _resolve_cv(handle)
    if cv is None:
        return
    cv.waiters = 0


def SleepConditionVariableCS(handle: int, cs_handle: int,
                             dw_milliseconds: int) -> bool:
    cv = _resolve_cv(handle)
    cs = _resolve_cs(cs_handle)
    if cv is None or cs is None:
        return False
    timeout = None if dw_milliseconds == INFINITE else dw_milliseconds / 1000.0
    cv.waiters += 1
    # Release CS, wait, re-acquire.
    cs.lock_count -= 1
    cs.lock.release()
    try:
        with cv.cond:
            result = cv.cond.wait(timeout=timeout)
        return result is not False
    finally:
        cs.lock.acquire()
        cs.owner_thread = threading.get_ident()
        cs.lock_count += 1
        cv.waiters -= 1


def SleepConditionVariableSRW(handle: int, srw_handle: int,
                              dw_milliseconds: int,
                              flags: int = 0) -> bool:
    cv = _resolve_cv(handle)
    srw = _resolve_srw(srw_handle)
    if cv is None or srw is None:
        return False
    timeout = None if dw_milliseconds == INFINITE else dw_milliseconds / 1000.0
    shared = bool(flags & CONDITION_VARIABLE_LOCKMODE_SHARED)
    with srw.cond:
        if shared:
            srw.readers -= 1
        else:
            srw.writer = False
            srw.writer_event.set()
    cv.waiters += 1
    try:
        with cv.cond:
            result = cv.cond.wait(timeout=timeout)
        return result is not False
    finally:
        with srw.cond:
            if shared:
                while srw.writer:
                    srw.cond.wait()
                srw.readers += 1
            else:
                while srw.writer or srw.readers > 0:
                    srw.cond.wait()
                srw.writer = True
                srw.writer_event.clear()
        cv.waiters -= 1


def WakeConditionVariable(handle: int) -> None:
    cv = _resolve_cv(handle)
    if cv is None:
        return
    with cv.cond:
        cv.cond.notify(1)


def WakeAllConditionVariable(handle: int) -> None:
    cv = _resolve_cv(handle)
    if cv is None:
        return
    with cv.cond:
        cv.cond.notify_all()


# ---------------------------------------------------------------------------
# INIT_ONCE
# ---------------------------------------------------------------------------

@dataclass
class InitOnce:
    """A one-time initialisation handle."""

    started: bool = False
    completed: bool = False
    failed: bool = False
    context: Optional[object] = None
    cond: threading.Condition = field(default_factory=threading.Condition)
    lock: threading.Lock = field(default_factory=threading.Lock)


def _resolve_init_once(handle: int) -> Optional[InitOnce]:
    obj = _HANDLES.get(handle)
    if isinstance(obj, InitOnce):
        return obj
    return None


def InitOnceInitialize(handle: int) -> None:
    io = _resolve_init_once(handle)
    if io is None:
        return
    io.started = False
    io.completed = False
    io.failed = False


def InitOnceExecuteOnce(handle: int,
                       init_fn: Callable[..., Optional[object]],
                       parameter: Optional[object] = None,
                       context_out: Optional[List[object]] = None) -> bool:
    """Synchronous one-time initialisation.

    The first thread that wins the race executes ``init_fn``; later
    threads block until ``init_fn`` returns and then receive the same
    context.  Returns ``True`` on success.
    """
    io = _resolve_init_once(handle)
    if io is None:
        return False
    with io.cond:
        while io.started and not io.completed:
            io.cond.wait()
        if io.completed:
            if context_out is not None:
                context_out.append(io.context)
            return not io.failed
        io.started = True
    try:
        result = init_fn(parameter)
    except Exception:
        with io.cond:
            io.failed = True
            io.completed = True
            io.cond.notify_all()
        return False
    with io.cond:
        io.context = result
        io.completed = True
        io.cond.notify_all()
    if context_out is not None:
        context_out.append(result)
    return True


def InitOnceBeginInitialize(handle: int, dw_flags: int,
                            f_pending_out: List[bool],
                            context_out: Optional[List[object]] = None
                            ) -> bool:
    """Asynchronous one-time initialisation: begin phase."""
    io = _resolve_init_once(handle)
    if io is None:
        return False
    with io.cond:
        if io.completed:
            f_pending_out.append(False)
            if context_out is not None:
                context_out.append(io.context)
            return True
        f_pending_out.append(True)
        return True


def InitOnceComplete(handle: int, dw_flags: int,
                     context: Optional[object]) -> bool:
    """Asynchronous one-time initialisation: complete phase."""
    io = _resolve_init_once(handle)
    if io is None:
        return False
    with io.cond:
        if io.completed:
            return not io.failed
        if dw_flags & INIT_ONCE_INIT_FAILED:
            io.failed = True
        else:
            io.context = context
        io.completed = True
        io.cond.notify_all()
    return not io.failed


# ---------------------------------------------------------------------------
# Handle table
# ---------------------------------------------------------------------------

_HANDLES: Dict[int, object] = {}
_HANDLE_COUNTER = 0xA0000000


def _store(obj: object) -> int:
    global _HANDLE_COUNTER
    _HANDLE_COUNTER += 1
    _HANDLES[_HANDLE_COUNTER] = obj
    return _HANDLE_COUNTER


def create_critical_section() -> int:
    return _store(CriticalSection())


def create_srw_lock() -> int:
    return _store(SrwLock())


def create_condition_variable() -> int:
    return _store(ConditionVariable())


def create_init_once() -> int:
    return _store(InitOnce())


def resolve_handle(handle: int) -> object:
    """Public accessor for tests."""
    return _HANDLES.get(handle)


def close_handle(handle: int) -> bool:
    return _HANDLES.pop(handle, None) is not None


# ---------------------------------------------------------------------------
# EXPORTS — Win32-shaped function table
# ---------------------------------------------------------------------------

EXPORTS = {
    "InitializeCriticalSection": InitializeCriticalSection,
    "InitializeCriticalSectionAndSpinCount": InitializeCriticalSectionAndSpinCount,
    "InitializeCriticalSectionEx": InitializeCriticalSectionEx,
    "EnterCriticalSection": EnterCriticalSection,
    "TryEnterCriticalSection": TryEnterCriticalSection,
    "LeaveCriticalSection": LeaveCriticalSection,
    "DeleteCriticalSection": DeleteCriticalSection,
    "SetCriticalSectionSpinCount": SetCriticalSectionSpinCount,
    "InitializeSRWLock": InitializeSRWLock,
    "AcquireSRWLockShared": AcquireSRWLockShared,
    "AcquireSRWLockExclusive": AcquireSRWLockExclusive,
    "TryAcquireSRWLockShared": TryAcquireSRWLockShared,
    "TryAcquireSRWLockExclusive": TryAcquireSRWLockExclusive,
    "ReleaseSRWLockShared": ReleaseSRWLockShared,
    "ReleaseSRWLockExclusive": ReleaseSRWLockExclusive,
    "InitializeConditionVariable": InitializeConditionVariable,
    "SleepConditionVariableCS": SleepConditionVariableCS,
    "SleepConditionVariableSRW": SleepConditionVariableSRW,
    "WakeConditionVariable": WakeConditionVariable,
    "WakeAllConditionVariable": WakeAllConditionVariable,
    "InitOnceInitialize": InitOnceInitialize,
    "InitOnceExecuteOnce": InitOnceExecuteOnce,
    "InitOnceBeginInitialize": InitOnceBeginInitialize,
    "InitOnceComplete": InitOnceComplete,
    "create_critical_section": create_critical_section,
    "create_srw_lock": create_srw_lock,
    "create_condition_variable": create_condition_variable,
    "create_init_once": create_init_once,
}


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    # Critical section: recursive lock.
    cs = create_critical_section()
    InitializeCriticalSection(cs)
    EnterCriticalSection(cs)
    if not TryEnterCriticalSection(cs):
        LeaveCriticalSection(cs)
        return False
    LeaveCriticalSection(cs)
    LeaveCriticalSection(cs)
    DeleteCriticalSection(cs)

    # SRW lock: exclusive blocks shared.
    srw = create_srw_lock()
    InitializeSRWLock(srw)
    AcquireSRWLockExclusive(srw)
    if TryAcquireSRWLockShared(srw):
        return False
    if TryAcquireSRWLockExclusive(srw):
        return False
    ReleaseSRWLockExclusive(srw)
    if not TryAcquireSRWLockShared(srw):
        return False
    ReleaseSRWLockShared(srw)

    # Condition variable: wake a waiter.
    cv = create_condition_variable()
    InitializeConditionVariable(cv)
    cs2 = create_critical_section()
    InitializeCriticalSection(cs2)
    EnterCriticalSection(cs2)
    woken = [False]
    def waiter():
        EnterCriticalSection(cs2)
        SleepConditionVariableCS(cv, cs2, 100)
        woken[0] = True
        LeaveCriticalSection(cs2)
    t = threading.Thread(target=waiter, daemon=True)
    t.start()
    LeaveCriticalSection(cs2)
    import time as _t
    _t.sleep(0.05)
    WakeConditionVariable(cv)
    t.join(timeout=1.0)
    if not woken[0]:
        return False

    # INIT_ONCE: callback runs exactly once even when called from
    # multiple threads.
    io = create_init_once()
    InitOnceInitialize(io)
    counter = [0]
    def init(_p):
        counter[0] += 1
        return "result"
    results: List[object] = []
    def run():
        InitOnceExecuteOnce(io, init, None, results)
    threads = [threading.Thread(target=run) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=2.0)
    if counter[0] != 1:
        return False
    if not results or not all(r == "result" for r in results):
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
