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
Umer OS SoftIRQ / Tasklet Subsystem
====================================
``kernel/softirq.c``.

Splits interrupt handling into a **hard-irq** top half (time
critical, runs with interrupts disabled) and a **soft-irq** bottom half
(deferred, runs with interrupts enabled).  Softirqs are a fixed set of
numbered vectors processed in priority order:

    HI_SOFTIRQ = 0, TIMER_SOFTIRQ, NET_TX_SOFTIRQ, NET_RX_SOFTIRQ,
    BLOCK_SOFTIRQ, IRQ_POLL_SOFTIRQ, TASKLET_SOFTIRQ, SCHED_SOFTIRQ,
    HRTIMER_SOFTIRQ, RCU_SOFTIRQ = 9,

Each vector has a registered handler.  Code marks a vector "pending"
with ``raise_softirq()``; the softirq daemon (ksoftirqd) later calls
``do_softirq()`` which drains pending vectors, highest priority first.
**Tasklets** are a higher-level API built on top of HI/TASKLET softirqs.

This module reproduces that model with asyncio so driver bottom-halves
can be deferred and batched.

Semantics preserved:
  * ``open_softirq(nr, handler)``  – register a softirq handler.
  * ``raise_softirq(nr)``          – mark a vector pending (wakes ksoftirqd).
  * ``do_softirq()``               – drain pending vectors in priority order.
  * Tasklet API: ``tasklet_init``, ``tasklet_schedule``, ``tasklet_kill``.
  * Per-CPU pending bitmap + count (here: single "CPU").
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional

log = logging.getLogger("UmerOS.SoftIRQ")

SoftirqFn = Callable[[], Awaitable[None]]
TaskletFn = Callable[[], Awaitable[None]]


# ── Softirq vector numbers (enum) ──────────────────────────

HI_SOFTIRQ = 0
TIMER_SOFTIRQ = 1
NET_TX_SOFTIRQ = 2
NET_RX_SOFTIRQ = 3
BLOCK_SOFTIRQ = 4
IRQ_POLL_SOFTIRQ = 5
TASKLET_SOFTIRQ = 6
SCHED_SOFTIRQ = 7
HRTIMER_SOFTIRQ = 8
RCU_SOFTIRQ = 9

# Highest valid softirq number (mirrors ``NR_SOFTIRQS`` in some configs).
NR_SOFTIRQS = 10

_SOFTIRQ_NAMES = {
    HI_SOFTIRQ: "HI", TIMER_SOFTIRQ: "TIMER",
    NET_TX_SOFTIRQ: "NET_TX", NET_RX_SOFTIRQ: "NET_RX",
    BLOCK_SOFTIRQ: "BLOCK", IRQ_POLL_SOFTIRQ: "IRQ_POLL",
    TASKLET_SOFTIRQ: "TASKLET", SCHED_SOFTIRQ: "SCHED",
    HRTIMER_SOFTIRQ: "HRTIMER", RCU_SOFTIRQ: "RCU",
}


def softirq_name(nr: int) -> str:
    return _SOFTIRQ_NAMES.get(nr, f"SOFTIRQ_{nr}")


class SoftIRQManager:
    """Fixed-table softirq dispatcher with a background ksoftirqd task.

    Drivers register handlers with :meth:`open_softirq` and raise them
    with :meth:`raise_softirq`.  A background asyncio task (started by
    :meth:`start`) drains pending vectors in priority order, mimicking
    ksoftirqd kernel thread.
    """

    def __init__(self) -> None:
        # Per-CPU (single CPU here) pending bitmask + handlers.
        self._pending: int = 0           # bit nr set => softirq nr pending
        self._handlers: Dict[int, SoftirqFn] = {}
        self._counts: Dict[int, int] = {nr: 0 for nr in range(NR_SOFTIRQS)}
        self._wakeup: Optional[asyncio.Event] = None
        self._ksoftirqd: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()

    # ── Registration ────────────────────────────────────────────────────

    def open_softirq(self, nr: int, handler: SoftirqFn) -> None:
        """Register a handler for softirq ``nr`` (mirrors ``open_softirq``).

        Panics if the slot is already taken ( BUGs on this).
        """
        if not (0 <= nr < NR_SOFTIRQS):
            raise ValueError(f"invalid softirq number {nr}")
        if nr in self._handlers:
            raise RuntimeError(f"softirq {softirq_name(nr)} already registered")
        self._handlers[nr] = handler
        log.debug("opened softirq %s", softirq_name(nr))

    # ── Raising / draining ──────────────────────────────────────────────

    def raise_softirq(self, nr: int) -> None:
        """Mark softirq ``nr`` pending and wake the daemon.

        Safe to call from a (simulated) hard-irq context — it only sets
        a bit and signals the event.  Mirrors ``raise_softirq()``.
        """
        if nr not in self._handlers:
            log.warning("raise_softirq(%s) with no handler — ignored", softirq_name(nr))
            return
        self._pending |= (1 << nr)
        if self._wakeup is not None:
            self._wakeup.set()

    async def do_softirq(self) -> int:
        """Drain all currently-pending softirqs in priority order.

        Returns the number of vectors processed.  Mirrors
        ``__do_softirq()``: iterate from lowest nr (highest priority) to
        highest, clearing each pending bit before invoking the handler.
        """
        processed = 0
        async with self._lock:
            pending = self._pending
            self._pending = 0
        # Iterate priority order: nr 0 (HI) first.
        for nr in range(NR_SOFTIRQS):
            if not (pending & (1 << nr)):
                continue
            handler = self._handlers.get(nr)
            if handler is None:
                continue
            try:
                await handler()
            except Exception as exc:  # noqa: BLE001
                log.exception("softirq %s raised: %s", softirq_name(nr), exc)
            self._counts[nr] += 1
            processed += 1
        return processed

    # ── ksoftirqd ───────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch the background ksoftirqd loop."""
        if self._running:
            return
        self._running = True
        self._wakeup = asyncio.Event()
        self._ksoftirqd = asyncio.create_task(self._ksoftirqd_loop())
        log.info("ksoftirqd started")

    async def stop(self) -> None:
        """Stop ksoftirqd and drain any final pending work."""
        self._running = False
        if self._wakeup is not None:
            self._wakeup.set()
        if self._ksoftirqd is not None:
            self._ksoftirqd.cancel()
            try:
                await self._ksoftirqd
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._ksoftirqd = None
        # Final drain.
        await self.do_softirq()
        log.info("ksoftirqd stopped")

    async def _ksoftirqd_loop(self) -> None:
        """Background loop that drains pending softirqs when woken.

        Mimics ``run_ksoftirqd()``: sleep until woken, then call
        ``do_softirq()``.  Loops in case work was raised while draining.
        """
        assert self._wakeup is not None
        while self._running:
            await self._wakeup.wait()
            self._wakeup.clear()
            while self._pending:
                await self.do_softirq()
            # Yield to the event loop between batches.
            await asyncio.sleep(0)

    # ── Diagnostics ─────────────────────────────────────────────────────

    def pending_mask(self) -> int:
        return self._pending

    def pending_names(self) -> List[str]:
        return [softirq_name(nr) for nr in range(NR_SOFTIRQS)
                if self._pending & (1 << nr)]

    def counts(self) -> Dict[str, int]:
        return {softirq_name(nr): self._counts[nr] for nr in range(NR_SOFTIRQS)}

    def status(self) -> dict:
        return {
            "running": self._running,
            "pending": self.pending_names(),
            "counts": self.counts(),
            "registered": [softirq_name(nr) for nr in self._handlers],
        }


# ── Tasklets (built on HI/TASKLET softirqs) ──────────────────────────────

@dataclass
class Tasklet:
    """A deferred, non-reentrant bottom-half (mirrors ``struct tasklet_struct``).

    Attributes:
        fn:    The async function to run.
        name:  Human label.
        state: One of "idle", "sched", "run".
        count: Number of times it has executed.
    """
    fn: TaskletFn
    name: str = ""
    state: str = "idle"   # "idle" | "sched" | "run"
    count: int = 0


class TaskletManager:
    """Manages a queue of scheduled tasklets.

    Two queues: the HI queue (high priority, drained by HI_SOFTIRQ)
    and the normal queue (drained by TASKLET_SOFTIRQ). 
    ``tasklet_vec`` / ``tasklet_hi_vec`` per-CPU structures.
    """

    def __init__(self, softirq: SoftIRQManager) -> None:
        self._softirq = softirq
        self._normal: List[Tasklet] = []
        self._hi: List[Tasklet] = []
        self._lock = asyncio.Lock()
        # Register our drain handlers on the appropriate softirqs.
        softirq.open_softirq(TASKLET_SOFTIRQ, self._drain_normal)
        softirq.open_softirq(HI_SOFTIRQ, self._drain_hi)

    def tasklet_init(self, fn: TaskletFn, name: str = "") -> Tasklet:
        """Create (but do not schedule) a tasklet (mirrors ``tasklet_init``)."""
        return Tasklet(fn=fn, name=name or getattr(fn, "__name__", "tasklet"))

    async def tasklet_schedule(self, t: Tasklet) -> None:
        """Mark ``t`` for execution on the normal queue."""
        async with self._lock:
            if t.state == "sched":
                return  # already pending — tasklets are non-reentrant
            t.state = "sched"
            self._normal.append(t)
        self._softirq.raise_softirq(TASKLET_SOFTIRQ)

    async def tasklet_hi_schedule(self, t: Tasklet) -> None:
        """Mark ``t`` for execution on the high-priority queue."""
        async with self._lock:
            if t.state == "sched":
                return
            t.state = "sched"
            self._hi.append(t)
        self._softirq.raise_softirq(HI_SOFTIRQ)

    async def tasklet_kill(self, t: Tasklet) -> None:
        """Wait for ``t`` to finish if running, then disable it.

        Mirrors ``tasklet_kill()`` — used during driver teardown.
        """
        async with self._lock:
            if t in self._normal:
                self._normal.remove(t)
            if t in self._hi:
                self._hi.remove(t)
            t.state = "idle"

    # ── Drain handlers ──────────────────────────────────────────────────

    async def _drain_normal(self) -> None:
        async with self._lock:
            batch, self._normal = self._normal, []
        for t in batch:
            t.state = "run"
            try:
                await t.fn()
            except Exception as exc:  # noqa: BLE001
                log.exception("tasklet %r raised: %s", t.name, exc)
            t.count += 1
            t.state = "idle"

    async def _drain_hi(self) -> None:
        async with self._lock:
            batch, self._hi = self._hi, []
        for t in batch:
            t.state = "run"
            try:
                await t.fn()
            except Exception as exc:  # noqa: BLE001
                log.exception("HI tasklet %r raised: %s", t.name, exc)
            t.count += 1
            t.state = "idle"

    def status(self) -> dict:
        return {
            "normal_pending": len(self._normal),
            "hi_pending": len(self._hi),
        }


__all__ = [
    "SoftIRQManager",
    "Tasklet",
    "TaskletManager",
    # Softirq vector numbers
    "HI_SOFTIRQ", "TIMER_SOFTIRQ", "NET_TX_SOFTIRQ", "NET_RX_SOFTIRQ",
    "BLOCK_SOFTIRQ", "IRQ_POLL_SOFTIRQ", "TASKLET_SOFTIRQ", "SCHED_SOFTIRQ",
    "HRTIMER_SOFTIRQ", "RCU_SOFTIRQ", "NR_SOFTIRQS",
    "softirq_name",
]
