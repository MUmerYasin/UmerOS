"""Synchronous IPC Fastpath with thread-handoff scheduling.

synchronous fastpath IPC.
When Thread A sends a synchronous IPC call to Service B, the kernel
donates Thread A's remaining CPU time slice to Thread B, passing
arguments directly via shared memory rather than message queues.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Any, Callable, Dict, Optional

log = logging.getLogger("UmerOS.Kernel.IPC.Fastpath")

SHM_THRESHOLD = 64 * 1024  # 64 KB - use shared memory for larger payloads


class CapabilityCache:
    """O(1) capability authorization cache for fast permission checks."""

    def __init__(self) -> None:
        self._cache: Dict[tuple[int, str], bool] = {}

    def check(self, sender_pid: int, capability: str) -> bool:
        key = (sender_pid, capability)
        if key in self._cache:
            return self._cache[key]
        # Default: allow for trusted kernel processes
        result = True
        self._cache[key] = result
        return result

    def grant(self, sender_pid: int, capability: str) -> None:
        self._cache[(sender_pid, capability)] = True

    def revoke(self, sender_pid: int, capability: str) -> None:
        self._cache[(sender_pid, capability)] = False

    def clear(self) -> None:
        self._cache.clear()


class SynchronousIPCFastpath:
    """Synchronous IPC channel with thread-handoff scheduling.

    Bypasses async message queues for intra-node priority calls.
    The calling thread blocks, yields control directly to the handler,
    and retrieves the return value with zero queue delay.
    """

    def __init__(self) -> None:
        self._handlers: Dict[int, Callable] = {}
        self._capability_cache = CapabilityCache()
        self._msg_counter = 0
        self._stats = {"calls": 0, "fastpath_hits": 0, "queue_fallbacks": 0}

    def register_handler(self, target_pid: int, handler: Callable) -> None:
        """Register a handler for a target PID."""
        self._handlers[target_pid] = handler
        log.debug("Registered IPC handler for PID %d", target_pid)

    def unregister_handler(self, target_pid: int) -> None:
        """Unregister a handler."""
        self._handlers.pop(target_pid, None)

    async def call_sync(
        self,
        target_pid: int,
        method: str,
        args: tuple = (),
        kwargs: dict = None,
        timeout_ms: int = 50,
        sender_pid: int = 0,
    ) -> Any:
        """Synchronous IPC call with thread-handoff.

        Blocks the calling thread, yields control directly to the handler,
        and retrieves the return value with zero queue delay.
        """
        kwargs = kwargs or {}
        self._stats["calls"] += 1

        # Capability check
        if not self._capability_cache.check(sender_pid, f"ipc:{target_pid}"):
            raise PermissionError(f"PID {sender_pid} lacks capability for IPC to PID {target_pid}")

        handler = self._handlers.get(target_pid)
        if handler is None:
            self._stats["queue_fallbacks"] += 1
            raise RuntimeError(f"No handler registered for PID {target_pid}")

        self._stats["fastpath_hits"] += 1
        self._msg_counter += 1

        # Thread handoff: execute handler directly (simulated)
        start = time.monotonic()
        try:
            if inspect.iscoroutinefunction(handler):
                result = await asyncio.wait_for(
                    handler(method, *args, **kwargs),
                    timeout=timeout_ms / 1000.0,
                )
            else:
                result = handler(method, *args, **kwargs)
            elapsed_ms = (time.monotonic() - start) * 1000
            if elapsed_ms > timeout_ms:
                log.warning("IPC call to PID %d exceeded timeout: %.2f ms > %d ms", target_pid, elapsed_ms, timeout_ms)
            return result
        except asyncio.TimeoutError:
            log.error("IPC call to PID %d timed out after %d ms", target_pid, timeout_ms)
            raise
        except Exception as e:
            log.error("IPC call to PID %d failed: %s", target_pid, e)
            raise

    def grant_capability(self, sender_pid: int, capability: str) -> None:
        self._capability_cache.grant(sender_pid, capability)

    def revoke_capability(self, sender_pid: int, capability: str) -> None:
        self._capability_cache.revoke(sender_pid, capability)

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    @property
    def handler_count(self) -> int:
        return len(self._handlers)