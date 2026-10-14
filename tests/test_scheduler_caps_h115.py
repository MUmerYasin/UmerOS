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

"""tests — capability lifecycle wired into HybridScheduler.

The scheduler held no ``CapabilityManager``, so ``exit_task``'s documented
"revoke capabilities" step never ran (a grant leak on every task death) and
spawn registered nothing. Now:

  * spawn/``add_task``/``spawn_child`` registers the PID (zero-trust
    default-deny; no capabilities unless ``default_capabilities`` is set),
  * ``exit_task``/``remove_task`` revoke every grant,
  * ``SYSTEM_PID`` (0) is never touched,
  * no manager wired => all of the above is a no-op (backward compatible).
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.capability_gate import gate  # noqa: E402
from kernel.capability_manager import (  # noqa: E402
    CAP_FS_READ,
    CAP_PROC_SPAWN,
    SYSTEM_PID,
    CapabilityManager,
)
from kernel.scheduler import HybridScheduler, Task  # noqa: E402


def _task(pid, name="t"):
    return Task(pid=pid, name=name, priority=0.5)


class TestCapabilityLifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mgr = CapabilityManager()
        self.sched = HybridScheduler()
        self.sched.attach_capability_manager(self.mgr)

    # ── spawn registers ───────────────────────────────────────────────────
    async def test_add_task_registers_pid(self):
        await self.sched.add_task(_task(7, "t7"))
        self.assertIn(7, self.mgr.registered_pids())

    async def test_spawn_default_is_zero_trust(self):
        await self.sched.add_task(_task(8, "t8"))
        self.assertEqual(self.mgr.list_capabilities(8), frozenset())

    async def test_spawn_child_registers_pid(self):
        await self.sched.add_task(_task(1, "parent"))
        await self.sched.spawn_child(1, _task(2, "child"))
        self.assertIn(2, self.mgr.registered_pids())

    async def test_default_capabilities_granted_when_configured(self):
        sched = HybridScheduler()
        sched.attach_capability_manager(self.mgr,
                                        default_capabilities=[CAP_FS_READ])
        await sched.add_task(_task(9, "t9"))
        self.assertEqual(self.mgr.list_capabilities(9), frozenset({CAP_FS_READ}))

    # ── exit / remove revoke ──────────────────────────────────────────────
    async def test_exit_task_revokes_capabilities(self):
        await self.sched.add_task(_task(3, "t3"))
        self.mgr.grant_many(3, [CAP_FS_READ, CAP_PROC_SPAWN])
        self.assertEqual(self.mgr.list_capabilities(3),
                         frozenset({CAP_FS_READ, CAP_PROC_SPAWN}))
        ok = await self.sched.exit_task(3)
        self.assertTrue(ok)
        self.assertEqual(self.mgr.list_capabilities(3), frozenset())
        self.assertNotIn(3, self.mgr.registered_pids())

    async def test_remove_task_revokes_capabilities(self):
        await self.sched.add_task(_task(4, "t4"))
        self.mgr.grant(4, CAP_FS_READ)
        removed = await self.sched.remove_task(4)
        self.assertIsNotNone(removed)
        self.assertEqual(self.mgr.list_capabilities(4), frozenset())

    async def test_remove_unknown_pid_is_safe(self):
        self.assertIsNone(await self.sched.remove_task(999))

    async def test_system_pid_caps_survive_exit(self):
        before = self.mgr.list_capabilities(SYSTEM_PID)
        self.assertTrue(before, "SYSTEM_PID must start omnipotent")
        await self.sched.add_task(_task(SYSTEM_PID, "kernel"))
        await self.sched.exit_task(SYSTEM_PID)
        self.assertEqual(self.mgr.list_capabilities(SYSTEM_PID), before)

    # ── wiring / back-fill / backward compat ──────────────────────────────
    async def test_attach_backfills_existing_tasks(self):
        sched = HybridScheduler()
        await sched.add_task(_task(5, "t5"))  # no manager yet
        self.assertNotIn(5, self.mgr.registered_pids())
        sched.attach_capability_manager(self.mgr)
        self.assertIn(5, self.mgr.registered_pids())

    async def test_init_accepts_capability_manager_kwarg(self):
        sched = HybridScheduler(capability_manager=self.mgr)
        await sched.add_task(_task(11, "t11"))
        self.assertIn(11, self.mgr.registered_pids())

    async def test_no_manager_is_backward_compatible(self):
        sched = HybridScheduler()
        await sched.add_task(_task(6, "t6"))
        self.assertTrue(await sched.exit_task(6))  # must not raise
        self.assertEqual(len(sched), 0)


class TestGateIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._prev = gate.snapshot()
        self.mgr = CapabilityManager()
        self.sched = HybridScheduler()
        self.sched.attach_capability_manager(self.mgr)

    async def asyncTearDown(self):
        gate.restore(self._prev)

    async def test_gate_denies_after_task_exit(self):
        await self.sched.add_task(_task(42, "t42"))
        self.mgr.grant(42, CAP_FS_READ)
        gate.wire(self.mgr, principal=42)
        self.assertTrue(gate.query(CAP_FS_READ))
        await self.sched.exit_task(42)
        # Capability is gone => the gate is now fail-closed for this identity.
        self.assertFalse(gate.query(CAP_FS_READ))
        with self.assertRaises(PermissionError):
            gate.require(CAP_FS_READ)


class TestSourceInvariants(unittest.TestCase):
    def test_scheduler_source(self):
        s = (ROOT / "kernel" / "scheduler.py").read_text(encoding="utf-8")
        self.assertIn("attach_capability_manager", s)
        self.assertIn("_register_task_caps", s)
        self.assertIn("_revoke_task_caps", s)

    def test_kernel_wires_scheduler(self):
        k = (ROOT / "kernel" / "umer_kernel.py").read_text(encoding="utf-8")
        self.assertIn(
            "self.scheduler.attach_capability_manager(self.capabilities)", k
        )


class TestKernelLocalScheduler(unittest.IsolatedAsyncioTestCase):
    """The kernel instantiates its OWN local ``HybridScheduler`` stub
    (``kernel/umer_kernel.py``), *not* ``kernel.scheduler.HybridScheduler``,
    so H115 must cover both classes."""

    async def asyncSetUp(self):
        import kernel.umer_kernel as uk

        self.HS = uk.HybridScheduler
        self.mgr = CapabilityManager()
        self.sched = self.HS()
        self.sched.attach_capability_manager(self.mgr)

    async def test_local_add_task_registers(self):
        await self.sched.add_task(_task(21, "t21"))
        self.assertIn(21, self.mgr.registered_pids())

    async def test_local_exit_task_revokes(self):
        await self.sched.add_task(_task(22, "t22"))
        self.mgr.grant(22, CAP_FS_READ)
        self.assertTrue(await self.sched.exit_task(22))
        self.assertEqual(self.mgr.list_capabilities(22), frozenset())

    async def test_local_remove_task_revokes(self):
        await self.sched.add_task(_task(23, "t23"))
        self.mgr.grant(23, CAP_FS_READ)
        self.assertIsNotNone(await self.sched.remove_task(23))
        self.assertEqual(self.mgr.list_capabilities(23), frozenset())

    async def test_local_stop_revokes_all(self):
        await self.sched.add_task(_task(24, "t24"))
        self.mgr.grant(24, CAP_FS_READ)
        await self.sched.stop()
        self.assertEqual(self.mgr.list_capabilities(24), frozenset())

    async def test_local_system_pid_survives(self):
        before = self.mgr.list_capabilities(SYSTEM_PID)
        await self.sched.add_task(_task(SYSTEM_PID, "kernel"))
        await self.sched.exit_task(SYSTEM_PID)
        self.assertEqual(self.mgr.list_capabilities(SYSTEM_PID), before)

    async def test_local_no_manager_backward_compatible(self):
        sched = self.HS()
        await sched.add_task(_task(25, "t25"))
        self.assertTrue(await sched.exit_task(25))
        await sched.stop()  # must not raise


if __name__ == "__main__":
    unittest.main()
