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
UmerOS /tmp — Transient Process Lockfile Management Subsystem
=============================================================

Implements process mutual exclusion, atomic PID files, and stale lockfile
detection in /tmp according to Linux conventions.

Features:
---------
* Atomic lock creation with PID recording.
* Stale lock detection (checks if PID is still alive).
* Non-blocking and timeout-based acquisition.
* Context manager support (`with ProcessLock("myapp"): ...`).

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .fhs import DEFAULT_TMP_ROOT

log = logging.getLogger("UmerOS.Tmp.Lockfile")


@dataclass
class LockMetadata:
    """Metadata recorded inside a lock file."""
    name: str
    pid: int
    hostname: str
    acquired_at: float
    custom_data: Dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "LockMetadata":
        d = json.loads(text)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def is_pid_alive(pid: int) -> bool:
    """Checks if a process with the given PID is currently alive."""
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except (OSError, PermissionError):
        return False


class LockAcquisitionError(Exception):
    """Raised when a lock cannot be acquired."""
    pass


class ProcessLock:
    """
    Atomic process lock backed by a file in /tmp.
    """

    def __init__(
        self,
        name: str,
        tmp_root: Path | str = DEFAULT_TMP_ROOT,
        stale_timeout_sec: float = 3600.0,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.tmp_root = Path(tmp_root).resolve()
        self.lock_path = self.tmp_root / f"{name}.lock"
        self.stale_timeout_sec = stale_timeout_sec
        self.custom_data = custom_data or {}
        self.is_locked = False

    def acquire(self, timeout: float = 0.0, poll_interval: float = 0.1) -> bool:
        """
        Attempts to acquire the lock.
        If timeout is 0.0, attempts once and returns immediately or raises LockAcquisitionError.
        """
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        start_time = time.time()

        while True:
            # Check for existing lock
            if self.lock_path.exists():
                # Check for stale lock
                if self._check_and_break_stale():
                    pass  # Stale lock was cleaned
                else:
                    if (time.time() - start_time) >= timeout:
                        raise LockAcquisitionError(f"Could not acquire lock '{self.name}': already locked.")
                    time.sleep(poll_interval)
                    continue

            # Attempt atomic creation
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            try:
                fd = os.open(str(self.lock_path), flags, 0o644)
                try:
                    meta = LockMetadata(
                        name=self.name,
                        pid=os.getpid(),
                        hostname=socket.gethostname(),
                        acquired_at=time.time(),
                        custom_data=self.custom_data,
                    )
                    os.write(fd, meta.to_json().encode("utf-8"))
                    self.is_locked = True
                    return True
                finally:
                    os.close(fd)
            except FileExistsError:
                if (time.time() - start_time) >= timeout:
                    raise LockAcquisitionError(f"Race condition acquiring lock '{self.name}'.")
                time.sleep(poll_interval)

    def release(self) -> bool:
        """Releases the lock and deletes the lockfile."""
        if not self.lock_path.exists():
            self.is_locked = False
            return False

        try:
            self.lock_path.unlink()
            self.is_locked = False
            return True
        except OSError as e:
            log.warning(f"Failed to release lock '{self.lock_path}': {e}")
            return False

    def _check_and_break_stale(self) -> bool:
        """
        Inspects existing lock file. If the holding process is dead or lock has timed out,
        removes the stale lock.
        """
        try:
            content = self.lock_path.read_text(encoding="utf-8")
            meta = LockMetadata.from_json(content)
            
            # 1. Check if PID is alive on the same host
            if meta.hostname == socket.gethostname():
                if not is_pid_alive(meta.pid):
                    log.info(f"Breaking stale lock '{self.name}': PID {meta.pid} is no longer running.")
                    self.lock_path.unlink()
                    return True

            # 2. Check age timeout
            age = time.time() - meta.acquired_at
            if age > self.stale_timeout_sec:
                log.info(f"Breaking expired stale lock '{self.name}': age {age:.1f}s > {self.stale_timeout_sec}s.")
                self.lock_path.unlink()
                return True

            return False
        except Exception:
            # Corrupt lock file, break it
            try:
                self.lock_path.unlink()
                return True
            except OSError:
                return False

    def __enter__(self) -> "ProcessLock":
        self.acquire(timeout=5.0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    @classmethod
    def list_all_locks(cls, tmp_root: Path | str = DEFAULT_TMP_ROOT) -> List[Dict[str, Any]]:
        """Scans /tmp for active lock files and checks their status."""
        root = Path(tmp_root).resolve()
        locks = []
        if not root.exists():
            return locks

        for item in root.glob("*.lock"):
            try:
                content = item.read_text(encoding="utf-8")
                meta = LockMetadata.from_json(content)
                alive = is_pid_alive(meta.pid) if meta.hostname == socket.gethostname() else None
                locks.append({
                    "name": meta.name,
                    "file": str(item),
                    "pid": meta.pid,
                    "is_pid_alive": alive,
                    "hostname": meta.hostname,
                    "acquired_at": meta.acquired_at,
                    "age_seconds": time.time() - meta.acquired_at,
                })
            except Exception:
                locks.append({
                    "name": item.stem,
                    "file": str(item),
                    "is_corrupt": True,
                })
        return locks
