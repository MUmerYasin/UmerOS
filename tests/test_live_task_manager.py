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
Unit tests for UmerOS LiveTaskManager (Live Window / backend).

Tests:
- Task registration, progress update, completion, and cancellation.
- Event subscription and notification dispatching.
- Filtering active vs completed tasks.
- Stale task clearing.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.live_task_manager import LiveTask, LiveTaskManager


class TestLiveTaskManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mgr = LiveTaskManager()

    async def test_create_and_get_task(self):
        task = await self.mgr.create_task(
            task_id="quantum_sim_1",
            title="Shor Algorithm Simulation",
            icon="auto_awesome",
            status_text="Initializing qubits",
        )
        self.assertEqual(task.task_id, "quantum_sim_1")
        self.assertEqual(task.progress, 0.0)
        self.assertFalse(task.is_completed)
        self.assertFalse(task.is_cancelled)

        retrieved = await self.mgr.get_task("quantum_sim_1")
        self.assertEqual(retrieved, task)

    async def test_update_progress(self):
        await self.mgr.create_task("backup_1", "Full System Backup")
        updated = await self.mgr.update_progress("backup_1", 0.45, "Copying /home")
        self.assertIsNotNone(updated)
        self.assertEqual(updated.progress, 0.45)
        self.assertEqual(updated.status_text, "Copying /home")

        # Boundary clamping [0.0, 1.0]
        clamped_low = await self.mgr.update_progress("backup_1", -0.5)
        self.assertEqual(clamped_low.progress, 0.0)
        clamped_high = await self.mgr.update_progress("backup_1", 1.8)
        self.assertEqual(clamped_high.progress, 1.0)

    async def test_complete_task(self):
        await self.mgr.create_task("ota_1", "System OTA Download")
        completed = await self.mgr.complete_task("ota_1", "Download finished")
        self.assertTrue(completed.is_completed)
        self.assertEqual(completed.progress, 1.0)

        # Cannot update progress on completed task
        res = await self.mgr.update_progress("ota_1", 0.5)
        self.assertIsNone(res)

    async def test_cancel_task(self):
        await self.mgr.create_task("ai_1", "Fine-tuning Local LLM")
        cancelled = await self.mgr.cancel_task("ai_1", "User pressed cancel")
        self.assertTrue(cancelled.is_cancelled)
        self.assertEqual(cancelled.status_text, "User pressed cancel")

    async def test_get_active_tasks_filter(self):
        await self.mgr.create_task("t1", "Active Task 1")
        await self.mgr.create_task("t2", "Active Task 2")
        await self.mgr.create_task("t3", "Completed Task 3")
        await self.mgr.complete_task("t3")

        active = await self.mgr.get_active_tasks()
        active_ids = [t.task_id for t in active]
        self.assertIn("t1", active_ids)
        self.assertIn("t2", active_ids)
        self.assertNotIn("t3", active_ids)

    async def test_subscriber_event_notifications(self):
        events_received = []

        def on_event(payload):
            events_received.append(payload)

        self.mgr.subscribe(on_event)

        await self.mgr.create_task("t_sub", "Subscriber Test")
        await self.mgr.update_progress("t_sub", 0.5, "Halfway")
        await self.mgr.complete_task("t_sub")

        self.assertEqual(len(events_received), 3)
        self.assertEqual(events_received[0]["event"], "task_created")
        self.assertEqual(events_received[1]["event"], "task_updated")
        self.assertEqual(events_received[2]["event"], "task_completed")

        self.mgr.unsubscribe(on_event)
        await self.mgr.create_task("t_unsub", "After Unsub")
        self.assertEqual(len(events_received), 3)

    async def test_clear_finished_tasks(self):
        await self.mgr.create_task("t_old", "Old Finished Task")
        await self.mgr.complete_task("t_old")

        # Manually age the task
        task = await self.mgr.get_task("t_old")
        task.updated_at -= 60.0

        cleared = await self.mgr.clear_finished(max_age_seconds=30.0)
        self.assertEqual(cleared, 1)
        self.assertIsNone(await self.mgr.get_task("t_old"))


if __name__ == "__main__":
    unittest.main()
