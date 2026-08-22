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
Tests for the new kernel modules:
  cred.py, reboot.py, resource.py, softirq.py

ported from (cred.c, reboot.c, resource.c, softirq.c).
"""
from __future__ import annotations

import asyncio
import unittest

from kernel.cred import (
    Credentials, CredentialStore, ROOT_UID, DEFAULT_ROOT_CAPS,
)
from kernel.reboot import (
    RebootManager, SystemState, RebootAction,
    NotifierBlock, NOTIFY_STOP, NOTIFY_BAD,
)
from kernel.resource import (
    ResourceManager, Resource, ResourceConflictError,
    IORESOURCE_MEM, IORESOURCE_IO, IORESOURCE_IRQ, IORESOURCE_DMA,
)
from kernel.softirq import (
    SoftIRQManager, TaskletManager,
    HI_SOFTIRQ, TIMER_SOFTIRQ, NET_RX_SOFTIRQ, TASKLET_SOFTIRQ,
)


# ── Credentials ──────────────────────────────────────────────────────────

class TestCredentials(unittest.TestCase):

    def test_default_is_root(self):
        c = Credentials()
        self.assertEqual(c.uid, ROOT_UID)
        self.assertTrue(c.is_root())
        self.assertTrue(c.has_cap("fs.read"))

    def test_refcount_get_put(self):
        c = Credentials()
        self.assertEqual(c.usage, 1)
        c.get()
        self.assertEqual(c.usage, 2)
        c.put()
        self.assertEqual(c.usage, 1)

    def test_put_underflow_is_safe(self):
        c = Credentials()
        c.put()
        c.put()  # would go negative — clamped
        self.assertEqual(c.usage, 0)

    def test_copy_is_independent(self):
        c = Credentials()
        snap = c.copy()
        self.assertEqual(snap.usage, 1)
        snap.euid = 1000
        self.assertEqual(c.euid, ROOT_UID)  # original unchanged

    def test_user_cred_is_not_root(self):
        c = CredentialStore.user(uid=1000, gid=1000)
        self.assertFalse(c.is_root())
        self.assertEqual(c.euid, 1000)
        self.assertIn("fs.read", c.caps)

    def test_in_group_checks_supplementary(self):
        c = CredentialStore.user(1000, 1000, groups={2000, 3000})
        self.assertTrue(c.in_group(1000))
        self.assertTrue(c.in_group(2000))
        self.assertFalse(c.in_group(9999))


class TestCredentialStore(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.store = CredentialStore()

    def test_register_unregister(self):
        self.store.register(1)
        self.assertIsNotNone(self.store.get(1))
        self.store.unregister(1)
        self.assertIsNone(self.store.get(1))

    def test_commit_replaces_active(self):
        self.store.register(1)
        new = Credentials(euid=1000)
        self.assertTrue(self.store.commit(1, new))
        self.assertEqual(self.store.get(1).euid, 1000)

    def test_override_and_revert(self):
        self.store.register(1)
        override = Credentials(euid=1000)
        self.assertTrue(self.store.override(1, override))
        self.assertEqual(self.store.get(1).euid, 1000)
        self.assertTrue(self.store.revert(1))
        self.assertEqual(self.store.get(1).euid, ROOT_UID)

    def test_revert_without_override_returns_false(self):
        self.store.register(1)
        self.assertFalse(self.store.revert(1))


# ── Reboot / Power-off ───────────────────────────────────────────────────

class TestRebootManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.rm = RebootManager()

    def test_state_transitions(self):
        self.assertEqual(self.rm.system_state, SystemState.BOOTING)
        self.rm.mark_running()
        self.assertEqual(self.rm.system_state, SystemState.RUNNING)

    async def test_notifier_fires_in_priority_order(self):
        order = []

        async def h1(action, data):
            order.append("h1")
            return 0

        async def h2(action, data):
            order.append("h2")
            return 0

        self.rm.register_restart_handler(h2, priority=0, name="low")
        self.rm.register_restart_handler(h1, priority=128, name="high")
        self.rm.mark_running()
        await self.rm.kernel_restart("test")
        self.assertEqual(order, ["h1", "h2"])
        self.assertEqual(self.rm.system_state, SystemState.RESTART)

    async def test_reboot_notifier_called_for_each_action(self):
        fired = []

        async def on_reboot(action, data):
            fired.append(action)
            return 0

        self.rm.register_reboot_notifier(on_reboot, name="log")
        self.rm.mark_running()
        await self.rm.kernel_halt("halt-test")
        self.assertIn(RebootAction.HALT, fired)

    async def test_halt_idempotent(self):
        self.rm.mark_running()
        await self.rm.kernel_halt("first")
        state_after_first = self.rm.system_state
        await self.rm.kernel_halt("second")  # should be a no-op
        self.assertEqual(self.rm.system_state, state_after_first)

    async def test_notifier_stop_mask_halts_chain(self):
        called = []

        async def stopper(action, data):
            called.append("stopper")
            return NOTIFY_STOP

        async def never(action, data):
            called.append("never")
            return 0

        self.rm.register_restart_handler(stopper, priority=128)
        self.rm.register_restart_handler(never, priority=64)
        self.rm.mark_running()
        await self.rm.kernel_restart("test")
        self.assertIn("stopper", called)
        self.assertNotIn("never", called)


# ── Resource manager ─────────────────────────────────────────────────────

class TestResourceManager(unittest.TestCase):

    def setUp(self):
        self.rm = ResourceManager()

    def test_request_disjoint_regions(self):
        r1 = self.rm.request_region(0x1000, 0x100, "dev1", flags=IORESOURCE_MEM)
        r2 = self.rm.request_region(0x2000, 0x100, "dev2", flags=IORESOURCE_MEM)
        self.assertEqual(r1.size(), 0x100)
        self.assertEqual(r2.name, "dev2")

    def test_overlapping_request_raises(self):
        self.rm.request_region(0x1000, 0x100, "dev1", flags=IORESOURCE_MEM)
        with self.assertRaises(ResourceConflictError):
            self.rm.request_region(0x1050, 0x20, "bad", flags=IORESOURCE_MEM)

    def test_separate_type_trees(self):
        # I/O port and MMIO are independent trees — same address, no conflict.
        self.rm.request_region(0x1000, 0x10, "port", flags=IORESOURCE_IO)
        self.rm.request_region(0x1000, 0x10, "mem", flags=IORESOURCE_MEM)
        # Lookup respects type.
        self.assertEqual(self.rm.lookup_resource(0x1000, flags=IORESOURCE_IO).name, "port")
        self.assertEqual(self.rm.lookup_resource(0x1000, flags=IORESOURCE_MEM).name, "mem")

    def test_check_region(self):
        self.rm.request_region(0x1000, 0x100, "dev1", flags=IORESOURCE_MEM)
        self.assertFalse(self.rm.check_region(0x1000, 0x10, flags=IORESOURCE_MEM))
        self.assertTrue(self.rm.check_region(0x5000, 0x10, flags=IORESOURCE_MEM))

    def test_release_resource(self):
        r = self.rm.request_region(0x1000, 0x100, "dev1", flags=IORESOURCE_MEM)
        self.assertTrue(self.rm.release_resource(r))
        # Now free again
        self.assertTrue(self.rm.check_region(0x1000, 0x10, flags=IORESOURCE_MEM))

    def test_invalid_range_raises(self):
        with self.assertRaises(ValueError):
            Resource(start=0x100, end=0x50, name="bad")

    def test_lookup_finds_deepest(self):
        # Build a hierarchy manually.
        parent = self.rm.request_region(0x0, 0x10000, "bus",
                                        flags=IORESOURCE_MEM)
        child = Resource(0x1000, 0x10FF, name="child",
                         flags=IORESOURCE_MEM, owner="dev")
        self.rm.request_resource(parent, child)
        found = self.rm.lookup_resource(0x1050, flags=IORESOURCE_MEM)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "child")


# ── SoftIRQ / Tasklets ───────────────────────────────────────────────────

class TestSoftIRQ(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.s = SoftIRQManager()
        await self.s.start()

    async def asyncTearDown(self):
        await self.s.stop()

    async def test_raise_and_drain(self):
        log = []

        async def handler():
            log.append("fired")

        self.s.open_softirq(TIMER_SOFTIRQ, handler)
        self.s.raise_softirq(TIMER_SOFTIRQ)
        await asyncio.sleep(0.05)
        self.assertEqual(log, ["fired"])
        self.assertEqual(self.s.counts()["TIMER"], 1)

    async def test_priority_order(self):
        # Lower nr = higher priority; processed first.
        order = []

        async def hi():
            order.append("hi")

        async def low():
            order.append("low")

        self.s.open_softirq(HI_SOFTIRQ, hi)
        # NR-1 is the lowest priority softirq.
        from kernel.softirq import RCU_SOFTIRQ
        self.s.open_softirq(RCU_SOFTIRQ, low)
        self.s.raise_softirq(RCU_SOFTIRQ)
        self.s.raise_softirq(HI_SOFTIRQ)
        await asyncio.sleep(0.05)
        self.assertEqual(order, ["hi", "low"])

    async def test_duplicate_open_panics(self):
        async def h():
            pass
        self.s.open_softirq(NET_RX_SOFTIRQ, h)
        with self.assertRaises(RuntimeError):
            self.s.open_softirq(NET_RX_SOFTIRQ, h)

    async def test_raise_unregistered_is_noop(self):
        # No handler registered for SCHED — raise should be ignored.
        from kernel.softirq import SCHED_SOFTIRQ
        self.s.raise_softirq(SCHED_SOFTIRQ)  # must not raise
        await asyncio.sleep(0.02)


class TestTasklets(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.s = SoftIRQManager()
        self.tm = TaskletManager(self.s)
        await self.s.start()

    async def asyncTearDown(self):
        await self.s.stop()

    async def test_tasklet_runs_once(self):
        ran = []

        async def work():
            ran.append("work")

        t = self.tm.tasklet_init(work, name="w")
        await self.tm.tasklet_schedule(t)
        await asyncio.sleep(0.05)
        self.assertEqual(ran, ["work"])
        self.assertEqual(t.count, 1)

    async def test_non_reentrant_while_pending(self):
        ran = []

        async def work():
            ran.append("x")

        t = self.tm.tasklet_init(work)
        # Schedule twice before the daemon drains.
        await self.tm.tasklet_schedule(t)
        await self.tm.tasklet_schedule(t)
        await asyncio.sleep(0.05)
        # Should only have run once (the second schedule was a no-op).
        self.assertEqual(t.count, 1)

    async def test_hi_priority_runs_first(self):
        order = []

        async def normal_work():
            order.append("normal")

        async def hi_work():
            order.append("hi")

        n = self.tm.tasklet_init(normal_work, name="n")
        h = self.tm.tasklet_init(hi_work, name="h")
        # Schedule normal first, then HI — HI should still run first.
        await self.tm.tasklet_schedule(n)
        await self.tm.tasklet_hi_schedule(h)
        await asyncio.sleep(0.05)
        self.assertEqual(order, ["hi", "normal"])

    async def test_tasklet_kill_removes_pending(self):
        ran = []

        async def work():
            ran.append("x")

        t = self.tm.tasklet_init(work)
        await self.tm.tasklet_schedule(t)
        await self.tm.tasklet_kill(t)
        await asyncio.sleep(0.05)
        self.assertEqual(ran, [])


if __name__ == "__main__":
    unittest.main()
