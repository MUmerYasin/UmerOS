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

"""tests — IPC bus: authenticate every receive path + gate injection.

`try_receive()` used to return messages **without** HMAC verification, and
`send()`/`broadcast()` had **no capability gate**. Now:
  * `try_receive()` verifies HMAC (synchronous) and drains past forged
    messages, so a forged head cannot wedge the queue;
  * `send()`/`broadcast()` are gated on the **sender's** capability
    (`ipc.send` / `ipc.broadcast`).
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.capability_gate import gate  # noqa: E402
from kernel.capability_manager import (  # noqa: E402
    CAP_IPC_BROADCAST as CM_BROADCAST,
    CAP_IPC_SEND as CM_SEND,
)
from kernel.ipc_bus import (  # noqa: E402
    CAP_IPC_BROADCAST,
    CAP_IPC_SEND,
    IPCBus,
    IPCMessage,
)


class _FakeManager:
    """Wired trust source: grants per pid -> set(cap)."""

    def __init__(self, grants=None):
        self.grants = grants or {}

    def query(self, pid, cap):
        return cap in self.grants.get(pid, set())


class _BusTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bus = IPCBus()
        self._prev = gate.snapshot()
        gate.unwire()
        gate.set_strict(False)

    def tearDown(self):
        gate.restore(self._prev)

    # ── constants ─────────────────────────────────────────────────────────
    def test_cap_constants(self):
        self.assertEqual(CAP_IPC_SEND, "ipc.send")
        self.assertEqual(CAP_IPC_BROADCAST, "ipc.broadcast")
        # must match the canonical definitions in capability_manager.py
        self.assertEqual(CAP_IPC_SEND, CM_SEND)
        self.assertEqual(CAP_IPC_BROADCAST, CM_BROADCAST)

    # ── permissive when unwired (backward compatible) ─────────────────────
    async def test_send_permissive_when_unwired(self):
        self.bus.register(10)
        self.bus.register(11)
        self.assertTrue(await self.bus.send(src=10, dst=11, payload={"a": 1}))

    async def test_broadcast_permissive_when_unwired(self):
        self.bus.register(10)
        self.bus.subscribe(10, "c")
        self.assertEqual(await self.bus.broadcast(src=0, channel="c", payload={}), 1)

    # ── try_receive now verifies HMAC ─────────────────────────────────────
    async def test_try_receive_returns_valid_signed_message(self):
        self.bus.register(2)
        await self.bus.send(src=1, dst=2, payload={"hi": 1})
        msg = self.bus.try_receive(2)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.payload["hi"], 1)

    async def test_try_receive_drops_unsigned_message(self):
        self.bus.register(2)
        forged = IPCMessage(src=1, dst=2, payload={"evil": True})  # never signed
        self.bus._queues[2].put_nowait(forged)
        self.assertIsNone(self.bus.try_receive(2))

    async def test_try_receive_drops_tampered_message(self):
        self.bus.register(2)
        msg = IPCMessage(src=1, dst=2, payload={"v": 1})
        msg.sign(self.bus._key)
        msg.payload["v"] = 2  # tamper AFTER signing -> HMAC mismatch
        self.bus._queues[2].put_nowait(msg)
        self.assertIsNone(self.bus.try_receive(2))

    async def test_forged_head_does_not_wedge_valid_message(self):
        self.bus.register(2)
        self.bus._queues[2].put_nowait(IPCMessage(src=1, dst=2, payload={"evil": 1}))
        await self.bus.send(src=1, dst=2, payload={"good": 1})  # valid, behind forged
        msg = self.bus.try_receive(2)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.payload.get("good"), 1)
        self.assertEqual(self.bus.pending(2), 0)

    async def test_receive_still_verifies(self):
        self.bus.register(2)
        forged = IPCMessage(src=1, dst=2, payload={"evil": 1})
        self.bus._queues[2].put_nowait(forged)
        self.assertIsNone(await self.bus.receive(2, timeout=0.1))

    # ── send gated on the SENDER's capability ─────────────────────────────
    async def test_send_denied_in_strict_mode(self):
        gate.set_strict(True)
        with self.assertRaises(PermissionError):
            await self.bus.send(src=5, dst=6, payload={})

    async def test_send_denied_when_wired_without_cap(self):
        gate.wire(_FakeManager({5: set()}))
        with self.assertRaises(PermissionError):
            await self.bus.send(src=5, dst=6, payload={})

    async def test_send_allowed_with_cap(self):
        gate.wire(_FakeManager({5: {CAP_IPC_SEND}}))
        self.bus.register(6)
        self.assertTrue(await self.bus.send(src=5, dst=6, payload={}))

    async def test_denied_send_queues_nothing(self):
        gate.wire(_FakeManager({5: set()}))
        self.bus.register(6)
        with self.assertRaises(PermissionError):
            await self.bus.send(src=5, dst=6, payload={})
        self.assertEqual(self.bus.pending(6), 0)

    async def test_gating_is_per_sender(self):
        """PID 5 may send; PID 6 may not — the check is on src, not the kernel."""
        gate.wire(_FakeManager({5: {CAP_IPC_SEND}, 6: set()}))
        self.bus.register(7)
        self.assertTrue(await self.bus.send(src=5, dst=7, payload={}))
        with self.assertRaises(PermissionError):
            await self.bus.send(src=6, dst=7, payload={})

    # ── broadcast gated ───────────────────────────────────────────────────
    async def test_broadcast_denied_in_strict_mode(self):
        gate.set_strict(True)
        with self.assertRaises(PermissionError):
            await self.bus.broadcast(src=5, channel="c", payload={})

    async def test_broadcast_denied_when_wired_without_cap(self):
        gate.wire(_FakeManager({5: {CAP_IPC_SEND}}))  # has send, not broadcast
        self.bus.register(6)
        self.bus.subscribe(6, "c")
        with self.assertRaises(PermissionError):
            await self.bus.broadcast(src=5, channel="c", payload={})

    async def test_broadcast_allowed_with_cap(self):
        gate.wire(_FakeManager({5: {CAP_IPC_BROADCAST}}))
        self.bus.register(6)
        self.bus.subscribe(6, "c")
        self.assertEqual(await self.bus.broadcast(src=5, channel="c", payload={}), 1)


class TestSourceInvariants(unittest.TestCase):
    def test_source_gates_and_verifies(self):
        src = (ROOT / "kernel" / "ipc_bus.py").read_text(encoding="utf-8")
        self.assertIn("_gate.require(CAP_IPC_SEND, src)", src)
        self.assertIn("_gate.require(CAP_IPC_BROADCAST, src)", src)
        self.assertGreaterEqual(src.count("msg.verify(self._key)"), 2)  # receive + try_receive
        # the old "does not verify" excuse must be gone
        self.assertNotIn("Does *not* verify HMAC", src)

    def test_capability_manager_exports_send_cap(self):
        src = (ROOT / "kernel" / "capability_manager.py").read_text(encoding="utf-8")
        self.assertIn('CAP_IPC_SEND      = "ipc.send"', src)


if __name__ == "__main__":
    unittest.main()
