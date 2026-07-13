"""
Tests for Umer OS Kernel subsystems.
Covers: Task, TaskState, HybridScheduler, MemoryManager, IPCBus, CapabilityManager, UmerKernel.
"""
from __future__ import annotations

import asyncio
import time
import unittest

from kernel.scheduler import (
    HybridScheduler, NullAIManager, Task, TaskState,
)
from kernel.memory_manager import MemoryManager, PAGE_SIZE
from kernel.ipc_bus import IPCBus, IPCMessage
from kernel.capability_manager import (
    CapabilityManager, SYSTEM_PID,
    CAP_FS_READ, CAP_NET_SEND,
)
from kernel.umer_kernel import UmerKernel


# ---------------------------------------------------------------------------
# Task tests
# ---------------------------------------------------------------------------

class TestTask(unittest.TestCase):

    def test_default_state_is_ready(self):
        t = Task(pid=1, name="init")
        self.assertEqual(t.state, TaskState.READY)

    def test_state_transitions(self):
        t = Task(pid=2, name="worker")
        t.state = TaskState.RUNNING
        self.assertEqual(t.state, TaskState.RUNNING)
        t.state = TaskState.DONE
        self.assertEqual(t.state, TaskState.DONE)

    def test_priority_validation_valid(self):
        Task(pid=3, name="a", priority=0.0)
        Task(pid=4, name="b", priority=1.0)
        Task(pid=5, name="c", priority=0.5)

    def test_priority_validation_invalid_high(self):
        with self.assertRaises(ValueError):
            Task(pid=6, name="bad", priority=1.1)

    def test_priority_validation_invalid_low(self):
        with self.assertRaises(ValueError):
            Task(pid=7, name="bad", priority=-0.1)

    def test_schedule_score_increases_with_priority(self):
        t_low  = Task(pid=10, name="low",  priority=0.1)
        t_high = Task(pid=11, name="high", priority=0.9)
        self.assertGreater(t_high.schedule_score, t_low.schedule_score)

    def test_schedule_score_decreases_with_cpu_time(self):
        t = Task(pid=12, name="cpu_hog", priority=0.8)
        score_before = t.schedule_score
        t.cpu_time = 100.0
        self.assertLess(t.schedule_score, score_before)

    def test_quantum_state_defaults(self):
        t = Task(pid=20, name="q")
        self.assertIn("superposition", t.quantum_state)
        self.assertAlmostEqual(t.quantum_state["superposition"], 0.5)


class TestTaskState(unittest.TestCase):

    def test_constants(self):
        self.assertEqual(TaskState.READY,   "READY")
        self.assertEqual(TaskState.RUNNING, "RUNNING")
        self.assertEqual(TaskState.BLOCKED, "BLOCKED")
        self.assertEqual(TaskState.DONE,    "DONE")


# ---------------------------------------------------------------------------
# HybridScheduler tests
# ---------------------------------------------------------------------------

class TestHybridScheduler(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.sched = HybridScheduler()

    async def test_empty_scheduler_len(self):
        self.assertEqual(len(self.sched), 0)

    async def test_add_task_increases_len(self):
        t = Task(pid=1, name="t1", priority=0.5)
        await self.sched.add_task(t)
        self.assertEqual(len(self.sched), 1)

    async def test_get_task_by_pid(self):
        t = Task(pid=2, name="t2", priority=0.7)
        await self.sched.add_task(t)
        retrieved = await self.sched.get_task(2)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "t2")

    async def test_remove_task(self):
        t = Task(pid=3, name="t3", priority=0.3)
        await self.sched.add_task(t)
        removed = await self.sched.remove_task(3)
        self.assertIsNotNone(removed)
        self.assertEqual(len(self.sched), 0)

    async def test_tick_returns_highest_priority(self):
        await self.sched.add_task(Task(pid=10, name="low",  priority=0.1))
        await self.sched.add_task(Task(pid=11, name="high", priority=0.9))
        selected = await self.sched.tick()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.pid, 11)

    async def test_tick_empty_returns_none(self):
        result = await self.sched.tick()
        self.assertIsNone(result)

    async def test_priority_invalid_not_added(self):
        with self.assertRaises(ValueError):
            Task(pid=99, name="bad", priority=2.0)

    async def test_null_ai_manager(self):
        ai = NullAIManager()
        t  = Task(pid=50, name="x", priority=0.5)
        score = ai.predict_task_success(t)
        self.assertAlmostEqual(score, 0.5)

    async def test_stop_is_safe_when_not_started(self):
        sched = HybridScheduler()
        await sched.stop()  # must not raise

    async def test_start_and_stop(self):
        await self.sched.start(ai_manager=NullAIManager())
        self.assertTrue(self.sched._running)
        await self.sched.stop()
        self.assertFalse(self.sched._running)


# ---------------------------------------------------------------------------
# MemoryManager tests
# ---------------------------------------------------------------------------

class TestMemoryManager(unittest.TestCase):

    def setUp(self):
        self.mm = MemoryManager(total_memory_bytes=4 * 1024 * 1024)  # 4 MiB

    def test_basic_alloc_returns_valid_address(self):
        addr = self.mm.allocate(1024, pid=1)
        self.assertGreater(addr, 0)
        self.assertEqual(addr % PAGE_SIZE, 0)

    def test_free_after_alloc(self):
        addr = self.mm.allocate(1024, pid=2)
        self.mm.free(addr, pid=2)
        stats = self.mm.stats()
        self.assertEqual(stats["live_allocations"], 0)

    def test_double_free_raises(self):
        addr = self.mm.allocate(512, pid=3)
        self.mm.free(addr, pid=3)
        with self.assertRaises(ValueError):
            self.mm.free(addr, pid=3)

    def test_out_of_memory_raises(self):
        # Fill all pages
        with self.assertRaises(MemoryError):
            self.mm.allocate(4 * 1024 * 1024 + 1, pid=4)

    def test_stats_returns_expected_keys(self):
        keys = self.mm.stats().keys()
        for k in ("total_pages", "free_pages", "used_pages",
                  "live_allocations", "page_size"):
            self.assertIn(k, keys)

    def test_compact_removes_orphans(self):
        self.mm.allocate(512, pid=5)
        freed = self.mm.compact()
        self.assertGreaterEqual(freed, 0)

    def test_invalid_size_raises(self):
        with self.assertRaises(ValueError):
            self.mm.allocate(0, pid=6)

    def test_predict_usage_returns_positive(self):
        self.mm.allocate(1024, pid=7)
        est = self.mm.predict_usage(7)
        self.assertGreater(est, 0)

    def test_invalid_total_memory_raises(self):
        with self.assertRaises(ValueError):
            MemoryManager(total_memory_bytes=0)

    def test_invalid_total_not_aligned_raises(self):
        with self.assertRaises(ValueError):
            MemoryManager(total_memory_bytes=5000)  # not page-aligned


# ---------------------------------------------------------------------------
# IPCBus tests
# ---------------------------------------------------------------------------

class TestIPCBus(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.bus = IPCBus()

    def test_start_is_idempotent(self):
        self.bus.start()
        self.bus.start()  # should not raise

    def test_register_creates_queue(self):
        self.bus.register(pid=1)
        self.assertIn(1, self.bus._queues)

    def test_register_idempotent(self):
        self.bus.register(10)
        self.bus.register(10)
        self.assertEqual(self.bus.pending(10), 0)

    async def test_send_receive(self):
        self.bus.register(10)
        self.bus.register(11)
        await self.bus.send(src=10, dst=11, payload={"hello": "world"})
        msg = await self.bus.receive(pid=11, timeout=1.0)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.payload["hello"], "world")

    async def test_broadcast_reaches_subscribers(self):
        self.bus.register(10)
        self.bus.register(11)
        self.bus.subscribe(10, "events")
        self.bus.subscribe(11, "events")
        count = await self.bus.broadcast(src=0, channel="events", payload={"x": 1})
        self.assertEqual(count, 2)

    def test_try_receive_empty_returns_none(self):
        self.bus.register(5)
        self.assertIsNone(self.bus.try_receive(5))

    def test_try_receive_unknown_pid_returns_none(self):
        self.assertIsNone(self.bus.try_receive(999))

    async def test_pending_count(self):
        self.bus.register(20)
        self.bus.register(21)
        await self.bus.send(src=20, dst=21, payload={})
        self.assertEqual(self.bus.pending(21), 1)

    def test_subscribe_synchronous(self):
        self.bus.register(30)
        self.bus.subscribe(30, "test_channel")  # no await — must not raise

    def test_sign_returns_hex_string(self):
        sig = self.bus.sign({"action": "test"})
        self.assertIsInstance(sig, str)
        self.assertEqual(len(sig), 64)  # SHA-256 hex

    def test_unregister_removes_queue(self):
        self.bus.register(40)
        self.bus.unregister(40)
        self.assertNotIn(40, self.bus._queues)


# ---------------------------------------------------------------------------
# CapabilityManager tests
# ---------------------------------------------------------------------------

class TestCapabilityManager(unittest.TestCase):

    def setUp(self):
        self.cm = CapabilityManager()

    def test_system_pid_is_zero(self):
        self.assertEqual(SYSTEM_PID, 0)

    def test_register_adds_pid(self):
        self.cm.register(pid=1)
        self.cm.register(pid=2)
        pids = self.cm.registered_pids()
        self.assertIn(1, pids)
        self.assertIn(2, pids)

    def test_registered_pids_sorted(self):
        self.cm.register(30)
        self.cm.register(10)
        self.cm.register(20)
        pids = self.cm.registered_pids()
        self.assertEqual(pids, sorted(pids))

    def test_unregistered_query_false(self):
        result = self.cm.query(pid=999, capability=CAP_FS_READ)
        self.assertFalse(result)

    def test_grant_and_query(self):
        self.cm.register(pid=5)
        self.cm.grant(pid=5, capability=CAP_FS_READ)
        self.assertTrue(self.cm.query(pid=5, capability=CAP_FS_READ))

    def test_revoke(self):
        self.cm.register(pid=6)
        self.cm.grant(pid=6, capability=CAP_FS_READ)
        self.cm.revoke(pid=6, capability=CAP_FS_READ)
        self.assertFalse(self.cm.query(pid=6, capability=CAP_FS_READ))

    def test_check_raises_permission_error(self):
        self.cm.register(pid=7)
        with self.assertRaises(PermissionError):
            self.cm.check(pid=7, capability=CAP_NET_SEND)

    def test_check_passes_when_granted(self):
        self.cm.register(pid=8)
        self.cm.grant(pid=8, capability=CAP_NET_SEND)
        result = self.cm.check(pid=8, capability=CAP_NET_SEND)
        self.assertTrue(result)

    def test_grant_many(self):
        self.cm.register(pid=9)
        self.cm.grant_many(pid=9, capabilities=[CAP_FS_READ, CAP_NET_SEND])
        self.assertTrue(self.cm.query(9, CAP_FS_READ))
        self.assertTrue(self.cm.query(9, CAP_NET_SEND))

    def test_revoke_all(self):
        self.cm.register(pid=10)
        self.cm.grant_many(10, [CAP_FS_READ, CAP_NET_SEND])
        n = self.cm.revoke_all(10)
        self.assertEqual(n, 2)
        self.assertFalse(self.cm.query(10, CAP_FS_READ))

    def test_list_capabilities(self):
        self.cm.register(11)
        self.cm.grant(11, CAP_FS_READ)
        caps = self.cm.list_capabilities(11)
        self.assertIn(CAP_FS_READ, caps)


# ---------------------------------------------------------------------------
# UmerKernel tests
# ---------------------------------------------------------------------------

class TestUmerKernel(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.kernel = UmerKernel(total_memory_bytes=4 * 1024 * 1024)

    async def asyncTearDown(self):
        await self.kernel.shutdown()

    async def test_kernel_starts_cleanly(self):
        await self.kernel.init()
        self.assertTrue(self.kernel._running)

    async def test_uptime_increases(self):
        t0 = self.kernel.uptime()
        await asyncio.sleep(0.05)
        self.assertGreater(self.kernel.uptime(), t0)

    async def test_spawn_process_returns_pid(self):
        pid = self.kernel.spawn_process("test_service", priority=0.5)
        self.assertIsInstance(pid, int)
        self.assertGreater(pid, 0)

    async def test_spawn_multiple_pids_are_unique(self):
        p1 = self.kernel.spawn_process("svc1")
        p2 = self.kernel.spawn_process("svc2")
        self.assertNotEqual(p1, p2)

    async def test_kill_process_returns_true(self):
        pid = self.kernel.spawn_process("killable")
        result = self.kernel.kill_process(pid)
        self.assertTrue(result)

    async def test_kill_unknown_pid_returns_false(self):
        self.assertFalse(self.kernel.kill_process(99999))

    async def test_list_processes_contains_spawned(self):
        pid = self.kernel.spawn_process("listed")
        procs = self.kernel.list_processes()
        pids = [p["pid"] for p in procs]
        self.assertIn(pid, pids)

    async def test_status_has_expected_keys(self):
        status = self.kernel.status()
        for k in ("uptime_seconds", "process_count", "memory", "running"):
            self.assertIn(k, status)

    async def test_inject_ai_manager(self):
        ai = NullAIManager()
        self.kernel.inject_ai_manager(ai)
        self.assertIs(self.kernel._ai_manager, ai)


if __name__ == "__main__":
    unittest.main()
