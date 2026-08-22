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
UmerOS /sources — UNIX System V Signals Subsystem (Appendix A)
===================================================================

Complete implementation of the POSIX & UNIX System V signal specification,
default actions, signal masks, handlers, and dispatching engine.


Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import enum
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

log = logging.getLogger("UmerOS.Sources.Signals")


class SignalAction(str, enum.Enum):
    """Default action taken upon signal delivery."""
    TERMINATE = "Term"      # Terminate process
    CORE_DUMP = "Core"      # Terminate and dump core file
    IGNORE = "Ign"          # Ignore signal
    STOP = "Stop"          # Stop/pause process execution
    CONTINUE = "Cont"      # Resume process execution


@dataclass
class SignalSpec:
    """Specification of a UNIX signal."""
    number: int
    name: str
    action: SignalAction
    description: str
    can_catch: bool = True
    can_ignore: bool = True
    standard: str = "POSIX.1 / System V"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["action"] = self.action.value
        return d


# ── System V & POSIX Signals Table ───────────────────────────────────────

SYSTEM_V_SIGNALS: Dict[int, SignalSpec] = {
    1: SignalSpec(1, "SIGHUP", SignalAction.TERMINATE, "Hangup detected on controlling terminal or death of controlling process"),
    2: SignalSpec(2, "SIGINT", SignalAction.TERMINATE, "Interrupt from keyboard (Ctrl+C)"),
    3: SignalSpec(3, "SIGQUIT", SignalAction.CORE_DUMP, "Quit from keyboard (Ctrl+\\) and dump core"),
    4: SignalSpec(4, "SIGILL", SignalAction.CORE_DUMP, "Illegal instruction"),
    5: SignalSpec(5, "SIGTRAP", SignalAction.CORE_DUMP, "Trace / breakpoint trap"),
    6: SignalSpec(6, "SIGABRT", SignalAction.CORE_DUMP, "Abort signal from abort(3)"),
    7: SignalSpec(7, "SIGBUS", SignalAction.CORE_DUMP, "Bus error (bad memory access)"),
    8: SignalSpec(8, "SIGFPE", SignalAction.CORE_DUMP, "Floating-point exception (division by zero)"),
    9: SignalSpec(9, "SIGKILL", SignalAction.TERMINATE, "Kill signal (cannot be caught or ignored)", can_catch=False, can_ignore=False),
    10: SignalSpec(10, "SIGUSR1", SignalAction.TERMINATE, "User-defined signal 1"),
    11: SignalSpec(11, "SIGSEGV", SignalAction.CORE_DUMP, "Invalid memory reference (segmentation fault)"),
    12: SignalSpec(12, "SIGUSR2", SignalAction.TERMINATE, "User-defined signal 2"),
    13: SignalSpec(13, "SIGPIPE", SignalAction.TERMINATE, "Broken pipe: write to pipe with no readers"),
    14: SignalSpec(14, "SIGALRM", SignalAction.TERMINATE, "Timer signal from alarm(2)"),
    15: SignalSpec(15, "SIGTERM", SignalAction.TERMINATE, "Termination signal (graceful shutdown request)"),
    16: SignalSpec(16, "SIGSTKFLT", SignalAction.TERMINATE, "Stack fault on coprocessor"),
    17: SignalSpec(17, "SIGCHLD", SignalAction.IGNORE, "Child stopped or terminated"),
    18: SignalSpec(18, "SIGCONT", SignalAction.CONTINUE, "Continue if stopped"),
    19: SignalSpec(19, "SIGSTOP", SignalAction.STOP, "Stop process execution (cannot be caught or ignored)", can_catch=False, can_ignore=False),
    20: SignalSpec(20, "SIGTSTP", SignalAction.STOP, "Stop typed at terminal (Ctrl+Z)"),
    21: SignalSpec(21, "SIGTTIN", SignalAction.STOP, "Terminal input for background process"),
    22: SignalSpec(22, "SIGTTOU", SignalAction.STOP, "Terminal output for background process"),
    23: SignalSpec(23, "SIGURG", SignalAction.IGNORE, "Urgent condition on socket (out-of-band data)"),
    24: SignalSpec(24, "SIGXCPU", SignalAction.CORE_DUMP, "CPU time limit exceeded"),
    25: SignalSpec(25, "SIGXFSZ", SignalAction.CORE_DUMP, "File size limit exceeded"),
    26: SignalSpec(26, "SIGVTALRM", SignalAction.TERMINATE, "Virtual timer expired"),
    27: SignalSpec(27, "SIGPROF", SignalAction.TERMINATE, "Profiling timer expired"),
    28: SignalSpec(28, "SIGWINCH", SignalAction.IGNORE, "Window resize signal"),
    29: SignalSpec(29, "SIGIO", SignalAction.TERMINATE, "I/O now possible (SIGPOLL)"),
    30: SignalSpec(30, "SIGPWR", SignalAction.TERMINATE, "Power failure restart"),
    31: SignalSpec(31, "SIGSYS", SignalAction.CORE_DUMP, "Bad system call (SVr4 / Linux)"),
}

SIGNALS_BY_NAME: Dict[str, SignalSpec] = {s.name: s for s in SYSTEM_V_SIGNALS.values()}


class SignalDispatcher:
    """Simulated signal delivery and handling subsystem for UmerOS."""

    def __init__(self) -> None:
        self._handlers: Dict[int, Callable[[int, Any], None]] = {}
        self._blocked_signals: Set[int] = set()
        self._pending_signals: List[Tuple[int, int]] = []  # (pid, signum)

    def register_handler(self, signum: int | str, handler: Callable[[int, Any], None]) -> bool:
        """Registers a custom signal handler."""
        sig = self._resolve_signal(signum)
        if not sig:
            raise ValueError(f"Unknown signal: {signum}")
        if not sig.can_catch:
            raise PermissionError(f"Cannot catch signal {sig.name} (uncatchable per POSIX).")

        self._handlers[sig.number] = handler
        return True

    def block_signal(self, signum: int | str) -> None:
        """Blocks signal from immediate delivery."""
        sig = self._resolve_signal(signum)
        if sig and sig.can_catch:
            self._blocked_signals.add(sig.number)

    def unblock_signal(self, signum: int | str) -> None:
        """Unblocks signal."""
        sig = self._resolve_signal(signum)
        if sig:
            self._blocked_signals.discard(sig.number)

    def send_signal(self, pid: int, signum: int | str, context: Optional[Any] = None) -> Dict[str, Any]:
        """
        Delivers a signal to a process or dispatches registered handler.
        """
        sig = self._resolve_signal(signum)
        if not sig:
            return {"success": False, "error": f"Unknown signal: {signum}"}

        if sig.number in self._blocked_signals:
            self._pending_signals.append((pid, sig.number))
            return {"success": True, "action": "blocked", "signal": sig.name, "pid": pid}

        handler = self._handlers.get(sig.number)
        if handler:
            handler(sig.number, context)
            return {"success": True, "action": "handled_by_custom_callback", "signal": sig.name, "pid": pid}

        # Default action
        return {
            "success": True,
            "action": f"default_{sig.action.value.lower()}",
            "signal": sig.name,
            "signum": sig.number,
            "pid": pid,
            "description": sig.description,
        }

    def _resolve_signal(self, sig: int | str) -> Optional[SignalSpec]:
        if isinstance(sig, int):
            return SYSTEM_V_SIGNALS.get(sig)
        name = str(sig).upper()
        if not name.startswith("SIG"):
            name = f"SIG{name}"
        return SIGNALS_BY_NAME.get(name)

    @classmethod
    def list_signals(cls) -> List[SignalSpec]:
        return [SYSTEM_V_SIGNALS[k] for k in sorted(SYSTEM_V_SIGNALS.keys())]

    @classmethod
    def get_signal(cls, identifier: int | str) -> Optional[SignalSpec]:
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            return SYSTEM_V_SIGNALS.get(int(identifier))
        name = str(identifier).upper()
        if not name.startswith("SIG"):
            name = f"SIG{name}"
        return SIGNALS_BY_NAME.get(name)
