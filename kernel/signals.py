"""
Umer OS Signal Delivery  [TODAY]
=================================
Inter-task signal mechanism inspired by Linux kernel/signal.c.

    Linux reference: kernel/signal.c — __send_signal_locked queues a
    signal on the target's sigpending list.  SIGKILL bypasses blocking;
    SIGTERM/SIGINT can be caught by a registered handler.

Design:
    - Each Task maintains an asyncio.Queue of pending signal strings.
    - SIGKILL is unblockable → directly cancels the asyncio Task.
    - SIGTERM/SIGINT/SIGUSR1 can be caught by user-registered handlers.
    - Default action for SIGTERM is graceful exit.
    - Tasks cooperatively drain signals via await recv_signal().

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("UmerOS.Signals")

# ── Signal Constants ────────────────────────────────────────────────────────────

SIGKILL:  str = "SIGKILL"      # Fatal, unblockable — cancel the asyncio task.
SIGTERM: str = "SIGTERM"       # Termination request — can be caught.
SIGINT:   str = "SIGINT"        # Interrupt (Ctrl+C analog) — can be caught.
SIGUSR1:  str = "SIGUSR1"       # User-defined signal 1.
SIGUSR2:  str = "SIGUSR2"       # User-defined signal 2.
SIGCHLD:  str = "SIGCHLD"       # Child process state change.
SIGSTOP:  str = "SIGSTOP"       # Pause the task (set to BLOCKED).

ALL_SIGNALS: List[str] = [SIGKILL, SIGTERM, SIGINT, SIGUSR1, SIGUSR2, SIGCHLD, SIGSTOP]

# Default actions when no handler is registered.
DEFAULT_ACTIONS: Dict[str, str] = {
    SIGKILL:  "terminate",   # unblockable forced exit
    SIGTERM: "terminate",   # graceful exit
    SIGINT:  "terminate",   # graceful exit
    SIGUSR1: "ignore",      # no-op by default
    SIGUSR2: "ignore",      # no-op by default
    SIGCHLD: "ignore",      # informational only
    SIGSTOP: "stop",        # block the task
}

# Fatal signals that cannot be caught or ignored.
FATAL_SIGNALS: frozenset({SIGKILL})


# ── Signal Handler ────────────────────────────────────────────────────────────────

class SignalHandler:
    """Metadata for a registered signal handler.

    Attributes:
        callback: Async callable invoked when the signal is delivered.
        name:     Human-readable label for debugging.
    """

    def __init__(self, callback: Callable, name: str = "") -> None:
        self.callback = callback
        self.name = name or callback.__name__

    def __repr__(self) -> str:
        return f"SignalHandler({self.name!r})"


# ── Signal Queue (per-task) ─────────────────────────────────────────────────────

class SignalQueue:
    """Per-task pending-signal queue and handler registry.

    Inspired by Linux ``struct sigpending``.  Each task owns one instance,
    stored as ``task.signal_queue``.

    Usage::

        sq = SignalQueue()
        sq.register_handler("SIGTERM", my_shutdown_handler)
        sig = await sq.recv()          # cooperatively drain signals
        if sig == "SIGKILL":
            raise SystemExit()
    """

    def __init__(self, max_pending: int = 64) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=max_pending)
        self._handlers: Dict[str, SignalHandler] = {}
        self._ignored: set = set()

    # ── Handler management ──────────────────────────────────────────────────

    def register_handler(self, sig: str, callback: Callable, name: str = "") -> None:
        """Register an async callback for a catchable signal.

        Args:
            sig:      Signal name (e.g. ``"SIGTERM"``).
            callback: Async callable ``(sig: str) -> None``.
            name:     Optional human-readable label.

        Raises:
            ValueError: If sig is a fatal (uncatchable) signal.
        """
        if sig in FATAL_SIGNALS:
            raise ValueError(f"{sig} is a fatal signal and cannot be caught.")
        if sig not in ALL_SIGNALS:
            raise ValueError(f"Unknown signal: {sig!r}")
        self._handlers[sig] = SignalHandler(callback, name)
        self._ignored.discard(sig)
        log.debug("Signal handler registered: %s -> %s", sig, self._handlers[sig])

    def ignore_signal(self, sig: str) -> None:
        """Mark a signal as explicitly ignored (no handler, no default action).

        Args:
            sig: Signal name to ignore.
        """
        if sig in FATAL_SIGNALS:
            raise ValueError(f"{sig} cannot be ignored.")
        self._handlers.pop(sig, None)
        self._ignored.add(sig)

    def has_handler(self, sig: str) -> bool:
        """Check whether a handler is registered for the given signal.

        Returns:
            True if a handler exists.
        """
        return sig in self._handlers

    # ── Enqueue / receive ──────────────────────────────────────────────────

    def enqueue(self, sig: str) -> bool:
        """Place a signal on the pending queue.

        Returns:
            True if enqueued successfully, False if the queue is full.

        Raises:
            ValueError: If sig is not a recognised signal name.
        """
        if sig not in ALL_SIGNALS:
            raise ValueError(f"Unknown signal: {sig!r}")
        try:
            self._queue.put_nowait(sig)
            return True
        except asyncio.QueueFull:
            log.warning("Signal queue full — dropping %s", sig)
            return False

    async def recv(self) -> str:
        """Await the next pending signal.

        Returns:
            The signal string (e.g. ``"SIGTERM"``).
        """
        return await self._queue.get()

    def try_recv(self) -> Optional[str]:
        """Non-blocking receive; returns None if no signals pending.

        Returns:
            Signal string or None.
        """
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    @property
    def pending_count(self) -> int:
        """Number of signals waiting in the queue.

        Returns:
            Integer pending count.
        """
        return self._queue.qsize()

    # ── Dispatch ───────────────────────────────────────────────────────────────

    def default_action(self, sig: str) -> str:
        """Return the default action for a signal.

        If a handler is registered, the action is "handler".
        If explicitly ignored, the action is "ignore".
        Otherwise falls back to DEFAULT_ACTIONS.

        Returns:
            One of ``"handler"``, ``"ignore"``, ``"terminate"``, ``"stop"``.
        """
        if sig in self._handlers:
            return "handler"
        if sig in self._ignored:
            return "ignore"
        return DEFAULT_ACTIONS.get(sig, "ignore")

    def get_handler(self, sig: str) -> Optional[SignalHandler]:
        """Return the registered handler for a signal, or None.

        Returns:
            SignalHandler instance or None.
        """
        return self._handlers.get(sig)

    def pending_signals(self) -> List[str]:
        """Return a snapshot list of all pending signals (non-blocking).

        Returns:
            List of signal strings currently in the queue.
        """
        signals = []
        while not self._queue.empty():
            try:
                signals.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        # Re-enqueue them so nothing is lost
        for s in signals:
            try:
                self._queue.put_nowait(s)
            except asyncio.QueueFull:
                log.warning("Signal queue overflow during pending_signals().")
                break
        return signals
