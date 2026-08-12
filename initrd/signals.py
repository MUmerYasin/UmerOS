"""
Umer OS Initrd PID 1 signal handling
====================================
A minimal signal layer for the initrd runtime.

When the kernel hands control to ``/init`` (the modern name for
``/linuxrc``), the init process becomes PID 1 in a brand-new
namespace.  PID 1 is special:

* The kernel will *not* deliver the default action for signals it
  has no handler for - it treats the process as immortal.
* PID 1 must ``wait()`` for any child it spawns; otherwise orphans
  become zombies forever.
* Common signals - ``SIGTERM``, ``SIGHUP``, ``SIGINT`` - are
  forwarded to PID 1 by the kernel and by every other process that
  has nothing better to do with them.

This module is the user-space equivalent of those semantics.  We do
not actually install Python signal handlers (the initrd is single
process during most of the boot) - we model the *behaviour* so that
higher layers can register interest and the runtime can record what
would have happened.

If the runtime is started from a real Linux kernel and the host
*does* send signals, the call site can opt in to install handlers by
setting ``UMEROS_INITRD_SIGNALS=1`` in the environment.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import signal
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

log = logging.getLogger("UmerOS.Initrd.Signals")


# ---------------------------------------------------------------------------
# Signal registry
# ---------------------------------------------------------------------------

class InitSignal(str, Enum):
    """The signals PID 1 sees during a normal Linux boot."""

    SIGCHLD = "SIGCHLD"   # child exited - PID 1 must reap
    SIGTERM = "SIGTERM"   # polite "please exit"
    SIGINT  = "SIGINT"    # Ctrl-C from the console
    SIGHUP  = "SIGHUP"    # terminal hang-up
    SIGUSR1 = "SIGUSR1"   # user-defined: "reload config"
    SIGUSR2 = "SIGUSR2"   # user-defined: "dump state"
    SIGPWR  = "SIGPWR"    # power failure imminent (laptops)


# Default action: signals with no handler either terminate the
# process or, in PID 1's case, are ignored.  We model both.
DEFAULT_ACTIONS: Dict[InitSignal, str] = {
    InitSignal.SIGCHLD: "reap",
    InitSignal.SIGTERM: "exit",
    InitSignal.SIGINT:  "exit",
    InitSignal.SIGHUP:  "exit",
    InitSignal.SIGUSR1: "ignore",
    InitSignal.SIGUSR2: "ignore",
    InitSignal.SIGPWR:  "exit",
}


# ---------------------------------------------------------------------------
# Event record
# ---------------------------------------------------------------------------

@dataclass
class SignalEvent:
    """One signal that PID 1 received during the boot."""

    sig: InitSignal
    received_at: float
    pid: int
    action: str
    notes: str = ""

    def as_dict(self) -> dict:
        return {
            "signal":      self.sig.value,
            "received_at": self.received_at,
            "pid":         self.pid,
            "action":      self.action,
            "notes":       self.notes,
        }


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class PID1SignalHandler:
    """Tracks signals delivered to PID 1 and dispatches to handlers.

    Two flavours of handler can be registered:

    * **Sync handler** - a plain callable invoked inline.  Use for
      reaping children, dumping state, etc.
    * **Reap handler** - a callable that accepts a synthetic child
      pid.  Return ``True`` if the child was reaped.

    The handler is intentionally decoupled from ``signal.signal()`` so
    that tests can drive it without a real OS.  When the
    environment variable ``UMEROS_INITRD_SIGNALS=1`` is set, the
    optional :meth:`install` method wires the handler into the host
    signal table so SIGCHLD/SIGTERM/etc. are routed to it.
    """

    def __init__(self) -> None:
        self._handlers: Dict[InitSignal, List[Callable]] = {}
        self._reaped: List[int] = []
        self._pending: List[SignalEvent] = []
        self._installed = False
        self._should_exit = False
        self._exit_code: Optional[int] = None
        self._reap_handler: Optional[Callable[[int], bool]] = None

    # -- registration ----------------------------------------------------

    def on(self, sig: InitSignal, fn: Optional[Callable] = None) -> Callable:
        """Register ``fn`` for ``sig``.

        Two call forms:

        * Direct: ``h.on(InitSignal.SIGUSR1, my_callback)``
        * Decorator: ``@h.on(InitSignal.SIGUSR1)`` (fn = the
          decorated function).

        Returns ``fn`` for chaining in both cases.
        """
        def _register(f: Callable) -> Callable:
            self._handlers.setdefault(sig, []).append(f)
            return f
        if fn is None:
            return _register
        return _register(fn)

    def on_reap(self, fn: Callable[[int], bool]) -> Callable:
        """Register a child-reap handler.  See class docstring."""
        self._reap_handler = fn
        return fn

    # -- dispatch --------------------------------------------------------

    def dispatch(self, sig: InitSignal, pid: int = 1,
                 notes: str = "") -> SignalEvent:
        """Record a signal and run the registered handlers."""
        action = DEFAULT_ACTIONS.get(sig, "ignore")
        event = SignalEvent(sig=sig, received_at=time.time(),
                            pid=pid, action=action, notes=notes)
        self._pending.append(event)
        log.info("pid 1 received %s from pid %d (action=%s)",
                 sig.value, pid, action)
        for fn in self._handlers.get(sig, []):
            try:
                fn(pid)
            except Exception as exc:  # noqa: BLE001
                log.error("handler for %s raised: %s", sig.value, exc)
        if action == "exit":
            self._should_exit = True
            self._exit_code = 128 + int(getattr(signal, sig.value, 0)) if hasattr(signal, sig.value) else 1
        return event

    def reap(self, child_pid: int) -> bool:
        """Record that ``child_pid`` was reaped and notify any handler.

        Returns ``True`` if the child was successfully reaped and
        recorded; ``False`` if a reap handler explicitly rejected
        the pid (e.g. because it is not a child of this process).
        """
        if self._reap_handler is not None:
            try:
                handled = self._reap_handler(child_pid)
            except Exception as exc:  # noqa: BLE001
                log.error("reap handler raised: %s", exc)
                handled = False
            if handled:
                self._reaped.append(child_pid)
                return True
            # The handler explicitly refused this pid - do not
            # record it as reaped.
            return False
        self._reaped.append(child_pid)
        return True

    # -- introspection ---------------------------------------------------

    @property
    def should_exit(self) -> bool:
        return self._should_exit

    @property
    def exit_code(self) -> Optional[int]:
        return self._exit_code

    def history(self) -> List[dict]:
        return [e.as_dict() for e in self._pending]

    def reaped(self) -> List[int]:
        return list(self._reaped)

    # -- real-signal integration (opt-in) --------------------------------

    def install(self) -> bool:
        """Wire this handler into the host signal table.

        Returns True if the install succeeded, False if the host
        refused (typical when not running as PID 1, on Windows which
        lacks ``SIGUSR1``/``SIGUSR2``, or when
        ``UMEROS_INITRD_SIGNALS`` is not set).
        """
        if self._installed:
            return True
        if os.environ.get("UMEROS_INITRD_SIGNALS") != "1":
            log.debug("PID1SignalHandler.install: env not set, skipping")
            return False
        # Map the init-side signal names to whatever the host offers.
        # Some POSIX signals (SIGUSR1/2, SIGPWR) don't exist on
        # Windows; we silently skip those.
        host_map = {
            InitSignal.SIGTERM: getattr(signal, "SIGTERM", None),
            InitSignal.SIGINT:  getattr(signal, "SIGINT",  None),
            InitSignal.SIGHUP:  getattr(signal, "SIGHUP",  None),
            InitSignal.SIGUSR1: getattr(signal, "SIGUSR1", None),
            InitSignal.SIGUSR2: getattr(signal, "SIGUSR2", None),
            InitSignal.SIGPWR:  getattr(signal, "SIGPWR",  None),
        }
        try:
            for init_sig, host_sig in host_map.items():
                if host_sig is None:
                    continue
                signal.signal(host_sig, lambda *_, s=init_sig: self.dispatch(s))
            self._installed = True
            log.info("PID1SignalHandler installed for host signals")
            return True
        except (ValueError, OSError, AttributeError) as exc:
            log.warning("PID1SignalHandler.install failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    h = PID1SignalHandler()
    events: List[InitSignal] = []

    @h.on(InitSignal.SIGUSR1)
    def _reload(pid: int) -> None:
        events.append(InitSignal.SIGUSR1)

    h.dispatch(InitSignal.SIGUSR1, pid=42)
    h.dispatch(InitSignal.SIGTERM, pid=99)
    h.reap(7)
    if h.should_exit is False:
        return False
    if h.exit_code is None or h.exit_code == 0:
        return False
    if InitSignal.SIGUSR1 not in events:
        return False
    if 7 not in h.reaped():
        return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("signals selftest:", "OK" if _selftest() else "FAIL")
