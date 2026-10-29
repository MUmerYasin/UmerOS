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
Unit tests for UmerOS Kernel Synchronization Subsystem.

Tests:
- PriorityInheritanceMutex acquire/release/re-entrancy.
- PriorityInheritanceMutex priority elevation during lock contention.
- PriorityInheritanceMutex priority restoration on release.
- EventGroup WAIT_ALL and WAIT_ANY bitmask logic.
- EventGroup auto_clear flags behavior.
- EventGroup timeout behavior.
- Integration with HybridScheduler.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kernel.sync.pi_mutex import PriorityInheritanceMutex
from kernel.sync.event_group import EventGroup
from kernel.scheduler import HybridScheduler, Task


class MockScheduler:
    def __init__(self):
        self.elevations = {}
        self.restorations = {}

    async def elevate_task_priority(self, pid: int, priority: float):
        self.elevations[pid] = priority

    async def restore_task_priority(self, pid: int, priority: float):
        self.restorations[pid] = priority


class TestPriorityInheritanceMutex(unittest.IsolatedAsyncioTestCase):
    async def test_basic_acquire_and_release(self):
        mutex = PriorityInheritanceMutex("test_mutex")
        self.assertFalse(mutex.is_locked)
        self.assertIsNone(mutex.owner_pid)

        acquired = await mutex.acquire(task_pid=1, task_priority=0.5)
        self.assertTrue(acquired)
        self.assertTrue(mutex.is_locked)
        self.assertEqual(mutex.owner_pid, 1)

        await mutex.release(task_pid=1)
        self.assertFalse(mutex.is_locked)
        self.assertIsNone(mutex.owner_pid)

    async def test_reentrant_acquire(self):
        mutex = PriorityInheritanceMutex("reentrant_mutex")
        await mutex.acquire(task_pid=2, task_priority=0.4)
        # Second acquire by same PID should succeed immediately
        await mutex.acquire(task_pid=2, task_priority=0.4)
        self.assertEqual(mutex.owner_pid, 2)

        await mutex.release(task_pid=2)
        # Still owned due to recursion
        self.assertEqual(mutex.owner_pid, 2)
        await mutex.release(task_pid=2)
        self.assertIsNone(mutex.owner_pid)

    async def test_unauthorized_release_raises(self):
        mutex = PriorityInheritanceMutex("guard_mutex")
        await mutex.acquire(task_pid=3, task_priority=0.5)
        with self.assertRaises(RuntimeError):
            await mutex.release(task_pid=4)
        await mutex.release(task_pid=3)

    async def test_priority_elevation_when_high_priority_waits(self):
        sched = MockScheduler()
        mutex = PriorityInheritanceMutex("contended_mutex")
        mutex.attach_scheduler(sched)

        # Low-priority task 10 acquires lock
        await mutex.acquire(task_pid=10, task_priority=0.2)

        # High-priority task 20 tries to acquire
        waiter_ran = False

        async def high_priority_waiter():
            nonlocal waiter_ran
            await mutex.acquire(task_pid=20, task_priority=0.9)
            waiter_ran = True
            await mutex.release(task_pid=20)

        waiter_task = asyncio.create_task(high_priority_waiter())
        # Let waiter start and contend
        await asyncio.sleep(0.02)

        # Verify low-priority owner PID 10 was elevated to 0.9
        self.assertEqual(sched.elevations.get(10), 0.9)
        self.assertFalse(waiter_ran)

        # Low-priority task releases lock -> restores original priority to 0.2
        await mutex.release(task_pid=10)
        self.assertEqual(sched.restorations.get(10), 0.2)

        await waiter_task
        self.assertTrue(waiter_ran)
        self.assertFalse(mutex.is_locked)

    async def test_integration_with_hybrid_scheduler(self):
        scheduler = HybridScheduler()
        t1 = Task(pid=100, name="low_worker", priority=0.2)
        t2 = Task(pid=200, name="high_ui", priority=0.9)
        await scheduler.add_task(t1)
        await scheduler.add_task(t2)

        mutex = PriorityInheritanceMutex("kernel_lock")
        mutex.attach_scheduler(scheduler)

        await mutex.acquire(task_pid=100, task_priority=t1.priority)

        async def waiter():
            await mutex.acquire(task_pid=200, task_priority=t2.priority)
            await mutex.release(task_pid=200)

        waiter_task = asyncio.create_task(waiter())
        await asyncio.sleep(0.02)

        # Task 100 should now have priority 0.9 in scheduler
        elevated_t1 = await scheduler.get_task(100)
        self.assertIsNotNone(elevated_t1)
        self.assertAlmostEqual(elevated_t1.priority, 0.9)

        # Release restores t1 priority
        await mutex.release(task_pid=100)
        restored_t1 = await scheduler.get_task(100)
        self.assertAlmostEqual(restored_t1.priority, 0.2)

        await waiter_task


class TestEventGroup(unittest.IsolatedAsyncioTestCase):
    async def test_wait_any_single_flag(self):
        eg = EventGroup()
        self.assertEqual(eg.flags, 0)

        task = asyncio.create_task(eg.wait(mask=0x05, mode=EventGroup.WAIT_ANY, timeout=1.0))
        await asyncio.sleep(0.01)
        self.assertFalse(task.done())

        # Setting bit 2 (0x04) matches 0x05 in WAIT_ANY
        await eg.set_flags(0x04)
        result = await task
        self.assertTrue(result)
        self.assertEqual(eg.flags, 0x04)

    async def test_wait_all_multiple_flags(self):
        eg = EventGroup()
        task = asyncio.create_task(eg.wait(mask=0x03, mode=EventGroup.WAIT_ALL, timeout=0.5))

        await eg.set_flags(0x01)
        await asyncio.sleep(0.01)
        self.assertFalse(task.done())  # Missing 0x02

        await eg.set_flags(0x02)  # Sets 0x02, now both 0x01 and 0x02 are set
        result = await task
        self.assertTrue(result)
        self.assertEqual(eg.flags, 0x03)

    async def test_auto_clear_flags(self):
        eg = EventGroup(initial_flags=0x0F)
        # Immediate wait with auto-clear
        result = await eg.wait(mask=0x03, mode=EventGroup.WAIT_ALL, auto_clear=True)
        self.assertTrue(result)
        # 0x03 was cleared from 0x0F, leaving 0x0C
        self.assertEqual(eg.flags, 0x0C)

    async def test_timeout_behavior(self):
        eg = EventGroup()
        result = await eg.wait(mask=0x80, mode=EventGroup.WAIT_ALL, timeout=0.03)
        self.assertFalse(result)

    async def test_clear_flags(self):
        eg = EventGroup(initial_flags=0xFF)
        await eg.clear_flags(0x0F)
        self.assertEqual(eg.flags, 0xF0)


if __name__ == "__main__":
    unittest.main()
