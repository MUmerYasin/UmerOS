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
UmerOS Priority-Inheritance Mutex (los_mux.c).

Prevents priority inversion between real-time interactive tasks (UI/shell)
and background batch tasks (quantum simulation, file scans).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, Set

log = logging.getLogger("UmerOS.Kernel.Sync.PIMutex")


class PriorityInheritanceMutex:
    """Mutex with priority inheritance to prevent priority inversion.

    When a high-priority task attempts to acquire a mutex held by a
    lower-priority task, the owner task's priority is temporarily boosted
    to the highest waiter's priority until the lock is released.
    """

    def __init__(self, name: str = "pi_mutex") -> None:
        self.name = name
        self._owner_pid: Optional[int] = None
        self._owner_priority: Optional[float] = None
        self._elevated_priority: Optional[float] = None
        self._lock = asyncio.Lock()
        self._waiters: Set[int] = set()
        self._scheduler: Any = None
        self._recursion_depth: int = 0

    def attach_scheduler(self, scheduler: Any) -> None:
        """Attach scheduler to receive priority elevation/restoration notifications."""
        self._scheduler = scheduler

    @property
    def owner_pid(self) -> Optional[int]:
        """Return the PID of the current mutex owner, or None if unlocked."""
        return self._owner_pid

    @property
    def is_locked(self) -> bool:
        """Return True if the mutex is currently acquired."""
        return self._owner_pid is not None

    async def acquire(self, task_pid: int, task_priority: float = 0.5) -> bool:
        """Acquire the mutex.

        If the lock is held by another task, records this task as a waiter.
        If this task's priority is higher than the current owner's priority,
        the owner's priority is elevated.

        Args:
            task_pid: PID of the calling task.
            task_priority: Priority of the calling task [0.0, 1.0].

        Returns:
            True once the lock is acquired.
        """
        # Re-entrant acquire by the same owner
        if self._owner_pid == task_pid:
            self._recursion_depth += 1
            return True

        if self._owner_pid is not None:
            self._waiters.add(task_pid)
            # Evaluate priority inheritance
            current_active_prio = (
                self._elevated_priority
                if self._elevated_priority is not None
                else (self._owner_priority if self._owner_priority is not None else 0.0)
            )
            if task_priority > current_active_prio:
                log.info(
                    "Priority Inversion on [%s]: elevating owner PID %d from %.3f to %.3f (waiter PID %d)",
                    self.name,
                    self._owner_pid,
                    current_active_prio,
                    task_priority,
                    task_pid,
                )
                self._elevated_priority = task_priority
                if self._scheduler and hasattr(self._scheduler, "elevate_task_priority"):
                    await self._scheduler.elevate_task_priority(self._owner_pid, task_priority)

        await self._lock.acquire()
        self._owner_pid = task_pid
        self._owner_priority = task_priority
        self._elevated_priority = None
        self._recursion_depth = 1
        self._waiters.discard(task_pid)
        return True

    async def release(self, task_pid: int) -> None:
        """Release the mutex.

        If the owner's priority was elevated due to inheritance, it is restored
        to its original base priority.

        Args:
            task_pid: PID of the calling task. Must be the current owner.

        Raises:
            RuntimeError: If called by a task that does not own the mutex.
        """
        if self._owner_pid != task_pid:
            raise RuntimeError(
                f"PID {task_pid} cannot release mutex '{self.name}' owned by {self._owner_pid}"
            )

        if self._recursion_depth > 1:
            self._recursion_depth -= 1
            return

        # Restore original priority if elevated
        if self._elevated_priority is not None and self._owner_priority is not None:
            if self._scheduler and hasattr(self._scheduler, "restore_task_priority"):
                await self._scheduler.restore_task_priority(self._owner_pid, self._owner_priority)

        self._owner_pid = None
        self._owner_priority = None
        self._elevated_priority = None
        self._recursion_depth = 0
        self._lock.release()

    async def __aenter__(self):
        raise NotImplementedError("Use acquire(task_pid, priority) for priority inheritance")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
