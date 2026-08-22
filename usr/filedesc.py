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
UmerOS filedesc Module
======================
kernel file descriptor APIs: pidfd, eventfd, signalfd, timerfd.

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
EBADF: int = 9
EBUSY: int = 16
EAGAIN: int = 11

EFD_SEMAPHORE: int = 0x00000001
EFD_NONBLOCK: int = 0x00000800
EFD_CLOEXEC: int = 0x00002000

SFD_NONBLOCK: int = 0x00002000
SFD_CLOEXEC: int = 0x00002000
SFD_SIGNAL_MASK: int = 0xFFFFFFFF

TFD_NONBLOCK: int = 0x00002000
TFD_CLOEXEC: int = 0x00002000
TFD_TIMER_ABSTIME: int = 0x00000001
TFD_TIMER_CANCEL_ON_SET: int = 0x00000002

TFD_SHARED_FCNTL_FLAGS: int = TFD_NONBLOCK | TFD_CLOEXEC

PIDFD_NONBLOCK: int = 0x00000800

SIG_BLOCK: int = 0
SIG_UNBLOCK: int = 1
SIG_SETMASK: int = 2

SIGRTMIN: int = 32
SIGRTMAX: int = 64


# ============================================================================
# filedesc Enums
# ============================================================================

class EventfdFlags(IntEnum):
    """Eventfd flags."""
    EFD_SEMAPHORE: int = EFD_SEMAPHORE
    EFD_NONBLOCK: int = EFD_NONBLOCK
    EFD_CLOEXEC: int = EFD_CLOEXEC


class SignalfdFlags(IntEnum):
    """Signalfd flags."""
    SFD_NONBLOCK: int = SFD_NONBLOCK
    SFD_CLOEXEC: int = SFD_CLOEXEC
    SFD_SIGNAL_MASK: int = SFD_SIGNAL_MASK


class TimerfdFlags(IntEnum):
    """Timerfd flags."""
    TFD_NONBLOCK: int = TFD_NONBLOCK
    TFD_CLOEXEC: int = TFD_CLOEXEC
    TFD_TIMER_ABSTIME: int = TFD_TIMER_ABSTIME
    TFD_TIMER_CANCEL_ON_SET: int = TFD_TIMER_CANCEL_ON_SET


class PidfdFlags(IntEnum):
    """Pidfd flags."""
    PIDFD_NONBLOCK: int = PIDFD_NONBLOCK


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class SignalInfo:
    """Signal information for signalfd."""
    ssi_signo: int = 0
    ssi_errno: int = 0
    ssi_code: int = 0
    ssi_pid: int = 0
    ssi_uid: int = 0
    ssi_fd: int = 0
    ssi_tid: int = 0
    ssi_band: int = 0
    ssi_overrun: int = 0
    ssi_siginfo: Any = None
    ssi_addr: int = 0
    ssi_addr_lsb: int = 0
    ssi_addr_index: int = 0
    ssi_sys_private: int = 0


@dataclass
class TimerSpec:
    """Timer specification."""
    it_interval_sec: int = 0
    it_interval_nsec: int = 0
    it_value_sec: int = 0
    it_value_nsec: int = 0

    @property
    def is_zero(self) -> bool:
        """Check if timer is disarmed."""
        return self.it_value_sec == 0 and self.it_value_nsec == 0

    @property
    def interval_ns(self) -> int:
        """Get interval in nanoseconds."""
        return self.it_interval_sec * 1_000_000_000 + self.it_interval_nsec

    @property
    def value_ns(self) -> int:
        """Get value in nanoseconds."""
        return self.it_value_sec * 1_000_000_000 + self.it_value_nsec


@dataclass
class PidfdInfo:
    """Process information for pidfd."""
    pid: int = 0
    ppid: int = 0
    pgid: int = 0
    sid: int = 0
    uid: int = 0
    gid: int = 0
    tgid: int = 0
    state: str = ""
    name: str = ""
    exit_code: int = 0
    signal: int = 0


@dataclass
class EventfdState:
    """Eventfd internal state."""
    counter: int = 0
    flags: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    read_waiters: int = 0
    write_waiters: int = 0

    def read(self, count: int = 1) -> int:
        """Read the eventfd counter."""
        with self.lock:
            val = self.counter
            if self.flags & EFD_SEMAPHORE:
                if self.counter > 0:
                    self.counter -= 1
            else:
                self.counter = 0
            return val

    def write(self, val: int) -> int:
        """Write to the eventfd counter."""
        with self.lock:
            if val == 0xFFFFFFFFFFFFFFFF:
                return EAGAIN
            if self.counter + val > 0xFFFFFFFFFFFFFFFF:
                return EAGAIN
            self.counter += val
            return SUCCESS

    def poll_state(self) -> bool:
        """Check if readable."""
        if self.flags & EFD_SEMAPHORE:
            return self.counter > 0
        return self.counter > 0


@dataclass
class SignalfdState:
    """Signalfd internal state."""
    mask: int = 0
    flags: int = 0
    pending_signals: List[SignalInfo] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_signal(self, siginfo: SignalInfo) -> None:
        """Add a pending signal."""
        with self.lock:
            if self.mask & (1 << siginfo.ssi_signo):
                self.pending_signals.append(siginfo)

    def read(self, max_signals: int = 1) -> List[SignalInfo]:
        """Read pending signals."""
        with self.lock:
            signals = self.pending_signals[:max_signals]
            self.pending_signals = self.pending_signals[max_signals:]
        return signals

    def poll_state(self) -> bool:
        """Check if readable."""
        return len(self.pending_signals) > 0


@dataclass
class TimerfdState:
    """Timerfd internal state."""
    clock_id: int = 0
    flags: int = 0
    value: TimerSpec = field(default_factory=TimerSpec)
    expired_count: int = 0
    active: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_trigger: float = 0.0

    def settime(self, new_value: TimerSpec, flags: int = 0) -> TimerSpec:
        """Set the timer."""
        with self.lock:
            old_value = self.value
            self.value = new_value
            if new_value.is_zero:
                self.active = False
            else:
                self.active = True
                self.last_trigger = time.time()
            return old_value

    def gettime(self) -> TimerSpec:
        """Get the timer."""
        with self.lock:
            return self.value

    def read(self) -> int:
        """Read expired count."""
        with self.lock:
            count = self.expired_count
            self.expired_count = 0
            if self.active and self.value.it_interval_sec == 0 and self.value.it_interval_nsec == 0:
                self.active = False
            return count

    def poll_state(self) -> bool:
        """Check if readable."""
        return self.expired_count > 0


@dataclass
class PidfdState:
    """Pidfd internal state."""
    pid: int = 0
    flags: int = 0
    process_info: Optional[PidfdInfo] = None
    exited: bool = False
    exit_status: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def poll_state(self) -> bool:
        """Check if process has exited."""
        return self.exited


# ============================================================================
# File Descriptor Subsystem
# ============================================================================

class FileDesc:
    """file descriptor subsystem (pidfd/eventfd/signalfd/timerfd)."""
    def __init__(self) -> None:
        self.eventfds: Dict[int, EventfdState] = {}
        self.signalfds: Dict[int, SignalfdState] = {}
        self.timerfds: Dict[int, TimerfdState] = {}
        self.pidfds: Dict[int, PidfdState] = {}
        self._next_fd: int = 100
        self.lock: threading.Lock = threading.Lock()

    def _alloc_fd(self) -> int:
        """Allocate a file descriptor."""
        fd = self._next_fd
        self._next_fd += 1
        return fd

    # ---- Eventfd ----

    def eventfd(self, initval: int = 0, flags: int = 0) -> int:
        """Create an eventfd."""
        with self.lock:
            fd = self._alloc_fd()
            self.eventfds[fd] = EventfdState(counter=initval, flags=flags)
        return fd

    def eventfd_read(self, fd: int) -> Optional[int]:
        """Read from an eventfd."""
        state = self.eventfds.get(fd)
        if state:
            return state.read()
        return None

    def eventfd_write(self, fd: int, val: int) -> int:
        """Write to an eventfd."""
        state = self.eventfds.get(fd)
        if state:
            return state.write(val)
        return EBADF

    def eventfd_close(self, fd: int) -> int:
        """Close an eventfd."""
        with self.lock:
            if fd in self.eventfds:
                del self.eventfds[fd]
                return SUCCESS
        return EBADF

    def eventfd_poll(self, fd: int) -> bool:
        """Poll eventfd for readability."""
        state = self.eventfds.get(fd)
        if state:
            return state.poll_state()
        return False

    # ---- Signalfd ----

    def signalfd(self, fd: int, mask: int, flags: int = 0) -> int:
        """Create or modify a signalfd."""
        with self.lock:
            if fd >= 0 and fd in self.signalfds:
                self.signalfds[fd].mask = mask
                self.signalfds[fd].flags = flags
                return fd
            new_fd = self._alloc_fd()
            self.signalfds[new_fd] = SignalfdState(mask=mask, flags=flags)
        return new_fd

    def signalfd_read(self, fd: int, max_signals: int = 1) -> List[SignalInfo]:
        """Read pending signals from signalfd."""
        state = self.signalfds.get(fd)
        if state:
            return state.read(max_signals)
        return []

    def signalfd_add_signal(self, fd: int, siginfo: SignalInfo) -> int:
        """Add a signal to signalfd."""
        state = self.signalfds.get(fd)
        if state:
            state.add_signal(siginfo)
            return SUCCESS
        return EBADF

    def signalfd_close(self, fd: int) -> int:
        """Close a signalfd."""
        with self.lock:
            if fd in self.signalfds:
                del self.signalfds[fd]
                return SUCCESS
        return EBADF

    def signalfd_poll(self, fd: int) -> bool:
        """Poll signalfd for readability."""
        state = self.signalfds.get(fd)
        if state:
            return state.poll_state()
        return False

    # ---- Timerfd ----

    def timerfd(self, clock_id: int = 0, flags: int = 0) -> int:
        """Create a timerfd."""
        with self.lock:
            fd = self._alloc_fd()
            self.timerfds[fd] = TimerfdState(clock_id=clock_id, flags=flags)
        return fd

    def timerfd_settime(self, fd: int, new_value: TimerSpec,
                        flags: int = 0) -> Optional[TimerSpec]:
        """Set a timerfd timer."""
        state = self.timerfds.get(fd)
        if state:
            return state.settime(new_value, flags)
        return None

    def timerfd_gettime(self, fd: int) -> Optional[TimerSpec]:
        """Get a timerfd timer."""
        state = self.timerfds.get(fd)
        if state:
            return state.gettime()
        return None

    def timerfd_read(self, fd: int) -> Optional[int]:
        """Read expired count from timerfd."""
        state = self.timerfds.get(fd)
        if state:
            return state.read()
        return None

    def timerfd_close(self, fd: int) -> int:
        """Close a timerfd."""
        with self.lock:
            if fd in self.timerfds:
                del self.timerfds[fd]
                return SUCCESS
        return EBADF

    def timerfd_poll(self, fd: int) -> bool:
        """Poll timerfd for readability."""
        state = self.timerfds.get(fd)
        if state:
            return state.poll_state()
        return False

    # ---- Pidfd ----

    def pidfd(self, pid: int, flags: int = 0) -> int:
        """Create a pidfd for a process."""
        with self.lock:
            fd = self._alloc_fd()
            self.pidfds[fd] = PidfdState(pid=pid, flags=flags)
        return fd

    def pidfd_getpid(self, fd: int) -> Optional[int]:
        """Get PID from pidfd."""
        state = self.pidfds.get(fd)
        if state:
            return state.pid
        return None

    def pidfd_send_signal(self, fd: int, sig: int) -> int:
        """Send a signal to a pidfd process."""
        state = self.pidfds.get(fd)
        if state:
            return SUCCESS
        return EBADF

    def pidfd_wait(self, fd: int, timeout_ms: int = -1) -> Optional[PidfdInfo]:
        """Wait for pidfd process to exit."""
        state = self.pidfds.get(fd)
        if not state:
            return None
        return state.process_info

    def pidfd_close(self, fd: int) -> int:
        """Close a pidfd."""
        with self.lock:
            if fd in self.pidfds:
                del self.pidfds[fd]
                return SUCCESS
        return EBADF

    def pidfd_poll(self, fd: int) -> bool:
        """Poll pidfd for readability."""
        state = self.pidfds.get(fd)
        if state:
            return state.poll_state()
        return False

    # ---- Aggregate poll ----

    def poll_all(self) -> List[int]:
        """Poll all file descriptors for readability."""
        readable: List[int] = []
        for fd, state in self.eventfds.items():
            if state.poll_state():
                readable.append(fd)
        for fd, state in self.signalfds.items():
            if state.poll_state():
                readable.append(fd)
        for fd, state in self.timerfds.items():
            if state.poll_state():
                readable.append(fd)
        for fd, state in self.pidfds.items():
            if state.poll_state():
                readable.append(fd)
        return readable

    def close_all(self) -> None:
        """Close all file descriptors."""
        with self.lock:
            self.eventfds.clear()
            self.signalfds.clear()
            self.timerfds.clear()
            self.pidfds.clear()

    def get_stats(self) -> Dict[str, int]:
        """Get file descriptor statistics."""
        return {
            "eventfds": len(self.eventfds),
            "signalfds": len(self.signalfds),
            "timerfds": len(self.timerfds),
            "pidfds": len(self.pidfds),
        }


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_filedesc: Optional[FileDesc] = None


def get_global_filedesc() -> FileDesc:
    """Get global FileDesc instance."""
    global _global_filedesc
    if _global_filedesc is None:
        _global_filedesc = FileDesc()
    return _global_filedesc
