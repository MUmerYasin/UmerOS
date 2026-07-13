"""
Umer OS Memory Manager  [TODAY - simulated virtual memory]
==========================================================
Provides a page-based virtual address space simulation for the Umer OS
microkernel.  On real hardware this layer would interface with the CPU MMU
via C/ASM stubs; today it uses a Python dict as the page table.

Key design decisions:
  - Page size: 4 KiB (matching x86_64 and ARM64 defaults).
  - Allocations are page-aligned and zero-filled.
  - Each allocation is tagged with its owner PID for auditing.
  - A lightweight ``compact()`` pass defragments the free list.
  - ``predict_usage(pid)`` returns an AI-hinted byte estimate (NullAI stub).

TODO: QPU integration — quantum-inspired prefetch hints from QuantumAPIGateway.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.MemoryManager")

PAGE_SIZE:            int = 4096          # 4 KiB
DEFAULT_TOTAL_PAGES:  int = 262_144       # 1 GiB simulated


# ---------------------------------------------------------------------------
# Internal page descriptor
# ---------------------------------------------------------------------------

@dataclass
class _Page:
    """Represents one 4-KiB virtual page.

    Attributes:
        address:  Virtual page-start address (multiple of PAGE_SIZE).
        pid:      Owner PID (0 = free).
        size:     Usable bytes in this page (≤ PAGE_SIZE for the final page).
    """

    address: int
    pid:     int   = 0
    size:    int   = PAGE_SIZE


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------

class MemoryManager:
    """Simulated page-based virtual memory manager.

    Tracks a fixed pool of ``total_pages`` 4-KiB pages in a dict keyed by
    virtual address.  Allocations span one or more contiguous simulated pages.

    Args:
        total_memory_bytes: Total simulated memory in bytes.  Must be a
            positive multiple of PAGE_SIZE.  Defaults to 1 GiB.
    """

    def __init__(self, total_memory_bytes: int = DEFAULT_TOTAL_PAGES * PAGE_SIZE) -> None:
        if total_memory_bytes <= 0 or total_memory_bytes % PAGE_SIZE != 0:
            raise ValueError(
                f"total_memory_bytes must be a positive multiple of {PAGE_SIZE}; "
                f"got {total_memory_bytes}."
            )
        self._total_pages:    int            = total_memory_bytes // PAGE_SIZE
        self._pages:          Dict[int, _Page] = {}
        # Allocation map: base_address → (pid, n_pages, requested_size)
        self._allocs:         Dict[int, Tuple[int, int, int]] = {}
        self._next_address:   int            = PAGE_SIZE  # skip null page (addr 0)
        self._lock:           threading.Lock = threading.Lock()
        log.info(
            "MemoryManager initialised: %d pages × %d B = %d MiB",
            self._total_pages, PAGE_SIZE, total_memory_bytes // (1024 * 1024),
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _pages_for(self, size: int) -> int:
        """Return the number of pages required to hold *size* bytes."""
        return (size + PAGE_SIZE - 1) // PAGE_SIZE

    def _free_pages(self) -> int:
        """Count pages that are currently unallocated."""
        used = sum(n for _, (_, n, _) in self._allocs.items())
        return self._total_pages - 1 - used  # -1 for null page

    # ── Public API ───────────────────────────────────────────────────────────

    def allocate(self, size: int, pid: int) -> int:
        """Allocate a contiguous block of virtual memory for a process.

        Args:
            size: Number of bytes to allocate (must be > 0).
            pid:  Owner process ID.

        Returns:
            Virtual base address of the allocated block.

        Raises:
            ValueError:   If size ≤ 0.
            MemoryError:  If insufficient free pages remain.
        """
        if size <= 0:
            raise ValueError(f"Allocation size must be > 0; got {size}.")

        n_pages = self._pages_for(size)

        with self._lock:
            if n_pages > self._free_pages():
                raise MemoryError(
                    f"Cannot allocate {size} bytes ({n_pages} pages) for PID {pid}: "
                    f"only {self._free_pages()} pages free."
                )
            base = self._next_address
            for i in range(n_pages):
                addr = base + i * PAGE_SIZE
                self._pages[addr] = _Page(address=addr, pid=pid)
            self._next_address += n_pages * PAGE_SIZE
            self._allocs[base] = (pid, n_pages, size)

        log.debug("Allocated %d B → vaddr 0x%x for PID %d", size, base, pid)
        return base

    def free(self, ptr: int, pid: int) -> None:
        """Release a previously allocated block.

        Args:
            ptr: Virtual base address returned by ``allocate()``.
            pid: Process ID that owns the allocation.

        Raises:
            ValueError: If ptr is unknown (double-free or bad pointer).
        """
        with self._lock:
            if ptr not in self._allocs:
                raise ValueError(
                    f"Double-free or invalid pointer 0x{ptr:x} for PID {pid}."
                )
            owner_pid, n_pages, _ = self._allocs.pop(ptr)
            for i in range(n_pages):
                self._pages.pop(ptr + i * PAGE_SIZE, None)

        log.debug("Freed vaddr 0x%x (%d pages) from PID %d", ptr, n_pages, pid)

    def compact(self) -> int:
        """Defragment: reclaim pages no longer referenced by any allocation.

        In this simulation, all allocated pages are accounted via ``_allocs``,
        so compact simply removes any orphan page-table entries and returns
        the count of pages reclaimed.

        Returns:
            Number of orphan pages removed.
        """
        with self._lock:
            live_addrs = set()
            for base, (_, n_pages, _) in self._allocs.items():
                for i in range(n_pages):
                    live_addrs.add(base + i * PAGE_SIZE)

            orphans = [addr for addr in self._pages if addr not in live_addrs]
            for addr in orphans:
                del self._pages[addr]

        if orphans:
            log.info("Compact: removed %d orphan page(s).", len(orphans))
        return len(orphans)

    def predict_usage(self, pid: int) -> int:
        """Return an AI-hinted byte estimate for a process's next allocation.

        Stub today: returns the current live byte count for pid × 1.2.
        TODO: QPU integration — replace with LSTM-based prefetch hints.

        Args:
            pid: Process ID.

        Returns:
            Estimated bytes the process will allocate next.
        """
        with self._lock:
            live = sum(
                size
                for _, (p, _, size) in self._allocs.items()
                if p == pid
            )
        return int(live * 1.2) if live else PAGE_SIZE

    def stats(self) -> dict:
        """Return memory usage statistics.

        Returns:
            Dict with total_pages, free_pages, used_pages, live_allocations,
            and page_size fields.
        """
        with self._lock:
            n_allocs = len(self._allocs)
            used = sum(n for _, (_, n, _) in self._allocs.items())
        free = self._total_pages - 1 - used
        return {
            "total_pages":      self._total_pages,
            "free_pages":       max(free, 0),
            "used_pages":       used,
            "live_allocations": n_allocs,
            "page_size":        PAGE_SIZE,
        }
