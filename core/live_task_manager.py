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
UmerOS Live Task Manager (NEXT Live Window).

Maintains a registry of real-time background operations (quantum simulations,
file backups, OTA updates, AI inference jobs) and broadcasts progress updates
to the Flutter desktop shell's status bar capsule.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("UmerOS.Core.LiveTaskManager")


@dataclass
class LiveTask:
    """Represents an active, trackable background task."""

    task_id: str
    title: str
    icon: str = "settings_suggest"
    progress: float = 0.0  # 0.0 to 1.0
    status_text: str = "In progress..."
    is_completed: bool = False
    is_cancelled: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize task to dictionary representation for JSON/Flutter bridge."""
        return asdict(self)


class LiveTaskManager:
    """Registry and event dispatcher for live background tasks."""

    def __init__(self) -> None:
        self._tasks: Dict[str, LiveTask] = {}
        self._subscribers: List[Callable[[Dict[str, Any]], Any]] = []
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        task_id: str,
        title: str,
        icon: str = "hourglass_empty",
        status_text: str = "Started",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LiveTask:
        """Register a new live task and notify subscribers."""
        async with self._lock:
            task = LiveTask(
                task_id=task_id,
                title=title,
                icon=icon,
                status_text=status_text,
                metadata=metadata or {},
            )
            self._tasks[task_id] = task

        await self._notify("task_created", task)
        log.info("LiveTask created: %s ('%s')", task_id, title)
        return task

    async def update_progress(
        self,
        task_id: str,
        progress: float,
        status_text: Optional[str] = None,
    ) -> Optional[LiveTask]:
        """Update progress (0.0 to 1.0) and status text of an existing task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.is_completed or task.is_cancelled:
                return None

            task.progress = max(0.0, min(1.0, float(progress)))
            if status_text is not None:
                task.status_text = status_text
            task.updated_at = time.time()

        await self._notify("task_updated", task)
        return task

    async def complete_task(
        self,
        task_id: str,
        status_text: str = "Completed",
    ) -> Optional[LiveTask]:
        """Mark a live task as successfully finished."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.progress = 1.0
            task.is_completed = True
            task.status_text = status_text
            task.updated_at = time.time()

        await self._notify("task_completed", task)
        log.info("LiveTask completed: %s", task_id)
        return task

    async def cancel_task(
        self,
        task_id: str,
        reason: str = "Cancelled by user",
    ) -> Optional[LiveTask]:
        """Cancel a live task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.is_cancelled = True
            task.status_text = reason
            task.updated_at = time.time()

        await self._notify("task_cancelled", task)
        log.info("LiveTask cancelled: %s (%s)", task_id, reason)
        return task

    async def get_task(self, task_id: str) -> Optional[LiveTask]:
        """Look up a task by ID."""
        async with self._lock:
            return self._tasks.get(task_id)

    async def get_active_tasks(self) -> List[LiveTask]:
        """Return list of all non-completed, non-cancelled active tasks."""
        async with self._lock:
            return [t for t in self._tasks.values() if not t.is_completed and not t.is_cancelled]

    async def get_all_tasks(self) -> List[LiveTask]:
        """Return snapshot of all registered tasks."""
        async with self._lock:
            return list(self._tasks.values())

    async def clear_finished(self, max_age_seconds: float = 30.0) -> int:
        """Remove completed or cancelled tasks older than max_age_seconds."""
        now = time.time()
        removed_count = 0
        async with self._lock:
            to_remove = [
                tid
                for tid, t in self._tasks.items()
                if (t.is_completed or t.is_cancelled) and (now - t.updated_at) >= max_age_seconds
            ]
            for tid in to_remove:
                del self._tasks[tid]
                removed_count += 1
        return removed_count

    def subscribe(self, listener: Callable[[Dict[str, Any]], Any]) -> None:
        """Subscribe a callback to receive live task event streams."""
        if listener not in self._subscribers:
            self._subscribers.append(listener)

    def unsubscribe(self, listener: Callable[[Dict[str, Any]], Any]) -> None:
        """Unsubscribe a callback."""
        if listener in self._subscribers:
            self._subscribers.remove(listener)

    async def _notify(self, event_type: str, task: LiveTask) -> None:
        """Dispatch event notifications to all registered listeners."""
        payload = {
            "event": event_type,
            "task": task.to_dict(),
            "timestamp": time.time(),
        }
        for listener in list(self._subscribers):
            try:
                res = listener(payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as exc:  # noqa: BLE001
                log.warning("Subscriber notification failed: %s", exc)


# Global default instance
live_task_manager = LiveTaskManager()
