"""
Umer OS PID Allocator  [TODAY]
============================
Cyclic PID allocation inspired by Linux kernel/pid.c.

    Linux reference: kernel/pid.c — alloc_pid() uses idr_alloc_cyclic
    with RESERVED_PIDS floor and pid_max ceiling; free_pid() recycles.

Design:
    - PIDs are handed out sequentially from PID_RESERVED to PID_MAX.
    - Freed PIDs go onto a free-list that is reused before advancing.
    - PID 0 is always SYSTEM_PID (kernel itself).
    - PID_MAX enforces a hard ceiling complementary to the scheduler's
      MAX_TASKS limit.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
from typing import List, Optional

log = logging.getLogger("UmerOS.PID")

# ── Constants ──────────────────────────────────────────────────────────────────

PID_SYSTEM: int = 0          # Reserved for the kernel itself.
PID_RESERVED: int = 1        # PIDs below this are never allocated.
PID_INIT: int = 1000         # Traditional init process PID (not enforced).
PID_MAX: int = 32768         # Upper bound on PID values.


# ── PID Allocator ──────────────────────────────────────────────────────────────

class PidAllocator:
    """Manages unique process identifiers with cyclic reuse.

    Inspired by Linux ``kernel/pid.c``: PIDs are allocated from a
    monotonically increasing counter.  When a PID is freed it is
    placed on a free-list that is consumed before the counter advances
    past PID_MAX.  Once the counter wraps, previously freed PIDs in the
    range [PID_RESERVED, PID_MAX) become available again.

    Thread-safety: all mutations go through an ``asyncio.Lock`` held
    by the caller (the scheduler).  The allocator itself is fast-path
    and lock-free for read operations.

    Args:
        pid_min: Lowest PID to hand out (default ``PID_RESERVED + 1``).
        pid_max: Highest PID value allowed (default ``PID_MAX``).
    """

    def __init__(
        self,
        pid_min: int = PID_RESERVED + 1,
        pid_max: int = PID_MAX,
    ) -> None:
        if pid_min < PID_RESERVED + 1:
            raise ValueError(f"pid_min must be >= {PID_RESERVED + 1}")
        if pid_max <= pid_min:
            raise ValueError("pid_max must be greater than pid_min")
        self._min: int = pid_min
        self._max: int = pid_max
        self._next: int = pid_min           # next PID to try
        self._in_use: set = set()           # currently allocated PIDs
        self._free_list: List[int] = []     # recycled PIDs (LIFO)
        log.debug("PidAllocator initialised (min=%d, max=%d).", pid_min, pid_max)

    # ── Allocation ────────────────────────────────────────────────────────────

    def alloc(self) -> int:
        """Allocate and return a fresh PID.

        Prefers the free-list (LIFO), then advances ``_next``.
        When ``_next`` reaches ``_max``, wraps back to ``_min``.

        Returns:
            A unique integer PID.

        Raises:
            RuntimeError: If no PIDs are available (all in use).
        """
        # 1. Try the free-list first (reuses freed PIDs — LIFO order).
        if self._free_list:
            pid = self._free_list.pop()
            self._in_use.add(pid)
            log.debug("PID %d allocated (recycled).", pid)
            return pid

        # 2. Try the sequential counter.
        pid = self._next
        attempts = 0
        while pid in self._in_use and attempts < (self._max - self._min):
            pid += 1
            if pid > self._max:
                pid = self._min  # wrap around
            attempts += 1

        if pid in self._in_use:
            # All PIDs in range are in use — exhausted.
            raise RuntimeError(
                f"PID allocator exhausted: all PIDs in [{self._min}, {self._max}] "
                f"are in use ({len(self._in_use)} total)."
            )

        self._next = pid + 1
        if self._next > self._max:
            self._next = self._min  # wrap for next call
        self._in_use.add(pid)
        log.debug("PID %d allocated (sequential).", pid)
        return pid

    # ── Deallocation ──────────────────────────────────────────────────────────

    def free(self, pid: int) -> None:
        """Release a PID back to the allocator.

        Args:
            pid: The PID to free.

        Raises:
            ValueError: If ``pid`` is not currently allocated.
        """
        if pid == PID_SYSTEM:
            raise ValueError("Cannot free SYSTEM_PID (0).")
        if pid not in self._in_use:
            raise ValueError(f"PID {pid} is not allocated.")
        self._in_use.remove(pid)
        self._free_list.append(pid)  # LIFO reuse
        log.debug("PID %d freed.", pid)

    # ── Queries ─────────────────────────────────────────────────────────────────

    def is_live(self, pid: int) -> bool:
        """Check whether a PID is currently allocated.

        Args:
            pid: Process ID to check.

        Returns:
            True if allocated, False otherwise.
        """
        return pid in self._in_use

    def count(self) -> int:
        """Return the number of currently allocated PIDs.

        Returns:
            Integer count of live PIDs.
        """
        return len(self._in_use)

    def free_count(self) -> int:
        """Return the number of PIDs sitting on the free-list.

        Returns:
            Integer count of recyclable PIDs.
        """
        return len(self._free_list)

    def stats(self) -> dict:
        """Return allocator health statistics.

        Returns:
            Dict with live count, free-list count, range, and next-pointer.
        """
        return {
            "live": self.count(),
            "free_list": self.free_count(),
            "range": (self._min, self._max),
            "next": self._next,
        }
