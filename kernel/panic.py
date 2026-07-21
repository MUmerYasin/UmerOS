"""
Umer OS Kernel Panic Handler  [TODAY]
=======================================
Fatal error handling with notifier chain, inspired by Linux kernel/panic.c.

    Linux reference: kernel/panic.c — panic() disables interrupts, prints
    a message, calls an atomic notifier chain (panic_notifier_list), then
    either hangs or reboots based on panic_timeout.

Design:
    - ``panic(message)`` is the single entry point for fatal kernel errors.
    - A notifier chain lets subsystems react before shutdown.
    - ``panic_timeout`` (sysctl) controls auto-recovery behavior:
      - 0: hang (log and stop)
      - >0: sleep N seconds then attempt re-initialisation
      - <0: immediate exit
    - An ``oops_context()`` prevents interleaved crash output.
    - A warn counter with configurable limit prevents runaway degradation.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Panic")

# ── Panic State ────────────────────────────────────────────────────────────────

_PANIC_LOCK: Optional[asyncio.Lock] = None  # set on first init


def _get_panic_lock() -> asyncio.Lock:
    """Lazily create the panic lock (cannot create before asyncio loop exists)."""
    global _PANIC_LOCK
    if _PANIC_LOCK is None:
        _PANIC_LOCK = asyncio.Lock()
    return _PANIC_LOCK


class PanicState:
    """Tracks whether the kernel is in a panicked state.

    Attributes:
        panicked:  True if panic() has been called.
        message:   The panic message (first panic only).
        time:      Monotonic timestamp of the panic.
    """

    def __init__(self) -> None:
        self.panicked: bool = False
        self.message: str = ""
        self.time: float = 0.0

    def __repr__(self) -> str:
        if self.panicked:
            return f"PanicState({self.message!r})"
        return "PanicState(ok)"


# ── Panic Notifier Chain ────────────────────────────────────────────────────────
# Inspired by Linux: ATOMIC_NOTIFIER_HEAD(panic_notifier_list)

class PanicNotifier:
    """Registry of callbacks invoked when the kernel panics.

    Subsystems register callbacks to react to fatal events (dump state,
    zero keys, flush buffers, etc.) without panic.py needing to know
    about them.  Callbacks run in priority order (lower = earlier).

    Usage::

        notifier = PanicNotifier()
        notifier.register(my_dump_callback, priority=100)
        notifier.register(my_crypto_zeroing, priority=10)
        await notifier.fire("Fatal scheduler corruption")
    """

    def __init__(self) -> None:
        # List of (priority, callback) tuples, sorted by priority ascending.
        self._callbacks: List[Tuple[int, Callable]] = []

    def register(self, callback: Callable, priority: int = 128) -> None:
        """Register a panic callback.

        Args:
            callback: Async callable ``(message: str) -> None``.
            priority: Lower values run first (default 128).
        """
        self._callbacks.append((priority, callback))
        self._callbacks.sort(key=lambda x: x[0])
        log.debug("Panic callback registered: %s (priority %d)",
                     callback.__name__, priority)

    def unregister(self, callback: Callable) -> None:
        """Remove a previously registered callback.

        Args:
            callback: The callable to remove.
        """
        self._callbacks = [(p, cb) for p, cb in self._callbacks if cb != callback]

    async def fire(self, message: str) -> None:
        """Invoke all registered callbacks in priority order.

        Args:
            message: The panic message string.
        """
        for priority, callback in self._callbacks:
            try:
                await callback(message)
            except Exception as exc:  # noqa: BLE001
                log.error("Panic callback %s failed: %s",
                         callback.__name__, exc)


# ── Oops Context (crash output coordination) ────────────────────────────────────
# Inspired by Linux: do_oops_enter_exit prevents interleaving crash logs.

class OopsContext:
    """Context manager that serialises crash output.

    Prevents multiple asyncio tasks from printing interleaved
    tracebacks simultaneously.

    Usage::

        async with kernel.oops_context():
            log.error("Something terrible happened")
            # ... print diagnostics ...
    """

    def __init__(self) -> None:
        self._lock = _get_panic_lock()

    async def __aenter__(self) -> "OopsContext":
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._lock.release()


# ── Warn Counter ────────────────────────────────────────────────────────────────
# Inspired by Linux: check_panic_on_warn() + kernel.warn_limit sysctl

class WarnCounter:
    """Rate-limited warning counter.

    If the cumulative warning count exceeds a configurable limit,
    the kernel is tainted and optionally panicked.

    Usage::

        wc = WarnCounter(limit=100, on_limit_taint=TAINT_WARN_LIMIT)
        wc.increment()  # harmless
        wc.stats()        # {"count": 1, "limit": 100}
    """

    def __init__(
        self,
        limit: int = 0,
        on_limit_taint: Optional[str] = None,
    ) -> None:
        self._count: int = 0
        self._limit: int = limit  # 0 = unlimited
        self._on_limit_taint = on_limit_taint

    def increment(self) -> bool:
        """Increment the warning counter.

        Returns:
            True if the limit has been exceeded (caller should panic if desired).
        """
        self._count += 1
        if self._limit > 0 and self._count >= self._limit:
            log.critical(
                "Warn limit exceeded: %d warnings (limit=%d)",
                self._count, self._limit,
            )
            return True
        return False

    @property
    def count(self) -> int:
        """Current warning count."""
        return self._count

    def stats(self) -> dict:
        """Return counter statistics.

        Returns:
            Dict with count and limit.
        """
        return {"count": self._count, "limit": self._limit}


# Taint flag for warn-limit exceeded (defined here to avoid circular import)
TAINT_WARN_LIMIT: str = "TAINT_WARN_LIMIT"
