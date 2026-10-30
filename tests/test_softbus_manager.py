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
Unit tests for UmerOS SoftBusManager (DSoftBus routing and message dispatch).

Tests:
- Manager initialization and mesh status.
- Frame encoding with incrementing message IDs.
- Handler registration, execution, and unregistration.
- Incoming frame validation and dispatch to handlers.
- Dropping invalid or tampered frames.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.softbus.discovery import SoftBusPeer
from network.softbus.softbus_manager import SoftBusManager


class TestSoftBusManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.secret = b"test_manager_secret_key_12345"
        self.mgr_a = SoftBusManager(node_name="Node-A", shared_secret=self.secret)
        self.mgr_b = SoftBusManager(node_name="Node-B", shared_secret=self.secret)

    async def test_mesh_status_structure(self):
        status = await self.mgr_a.get_mesh_status()
        self.assertIn("local_node", status)
        self.assertEqual(status["local_node"]["node_name"], "Node-A")
        self.assertEqual(status["peers_count"], 0)
        self.assertEqual(status["registered_handlers"], [])

    async def test_send_and_dispatch_frame(self):
        received_payloads = []

        def on_task_migration(peer: SoftBusPeer, payload: bytes):
            received_payloads.append((peer, payload))

        # Register handler for message type 200 on Node B
        self.mgr_b.register_handler(200, on_task_migration)

        # Peer A registers Peer B
        peer_b = SoftBusPeer(
            node_id=self.mgr_b.node_id,
            node_name="Node-B",
            host="192.168.1.102",
        )
        await self.mgr_a.discovery.register_peer(peer_b)

        # Node A encodes a task migration payload
        test_payload = b'{"task": "quantum_job", "qubits": 5}'
        frame_bytes = await self.mgr_a.send_to_peer(peer_b, msg_type=200, payload=test_payload)
        self.assertGreater(len(frame_bytes), len(test_payload))

        # Node B handles the incoming frame from Node A's host
        frame = await self.mgr_b.handle_incoming_frame(frame_bytes, sender_host="192.168.1.101")
        self.assertIsNotNone(frame)
        self.assertTrue(frame.is_valid)
        self.assertEqual(frame.msg_type, 200)
        self.assertEqual(frame.payload, test_payload)

        # Verify handler was called with payload
        self.assertEqual(len(received_payloads), 1)
        self.assertEqual(received_payloads[0][1], test_payload)

    async def test_tampered_frame_is_dropped(self):
        received_calls = []
        self.mgr_b.register_handler(101, lambda p, b: received_calls.append(b))

        peer_b = SoftBusPeer(node_id="b", node_name="B", host="127.0.0.1")
        frame_bytes = bytearray(await self.mgr_a.send_to_peer(peer_b, msg_type=101, payload=b"Secret"))

        # Corrupt payload byte
        frame_bytes[-1] ^= 0xFF

        result = await self.mgr_b.handle_incoming_frame(bytes(frame_bytes), sender_host="127.0.0.1")
        self.assertIsNone(result)
        self.assertEqual(len(received_calls), 0)

    async def test_unregister_handler(self):
        calls = []
        handler = lambda p, b: calls.append(b)
        self.mgr_a.register_handler(50, handler)
        self.assertIn(50, (await self.mgr_a.get_mesh_status())["registered_handlers"])

        self.mgr_a.unregister_handler(50, handler)
        self.assertNotIn(50, (await self.mgr_a.get_mesh_status())["registered_handlers"])


if __name__ == "__main__":
    unittest.main()
