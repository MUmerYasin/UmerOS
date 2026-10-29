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
Unit tests for UmerOS Distributed Soft Bus (DSoftBus-inspired).

Tests:
- Beacon payload generation and parsing.
- Self-broadcast loopback rejection.
- Peer registration and active discovery list.
- Peer TTL expiration and eviction.
- Binary frame encoding, decoding, and HMAC-SHA256 signature verification.
- Tamper detection on corrupted session frames.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.softbus.discovery import SoftBusDiscovery, SoftBusPeer
from network.softbus.session import SoftBusSession


class TestSoftBusDiscovery(unittest.IsolatedAsyncioTestCase):
    async def test_make_and_parse_beacon(self):
        node_a = SoftBusDiscovery(node_name="Node-Alpha", device_class="Server")
        node_b = SoftBusDiscovery(node_name="Node-Beta", device_class="Desktop")

        beacon_bytes = node_a.make_beacon()
        self.assertIn(b"UMEROS_SOFTBUS_V1", beacon_bytes)

        # Node B parses Node A's beacon
        peer = node_b.parse_beacon(beacon_bytes, sender_host="192.168.1.50")
        self.assertIsNotNone(peer)
        self.assertEqual(peer.node_id, node_a.node_id)
        self.assertEqual(peer.node_name, "Node-Alpha")
        self.assertEqual(peer.device_class, "Server")
        self.assertEqual(peer.host, "192.168.1.50")

    async def test_self_beacon_rejection(self):
        node = SoftBusDiscovery(node_name="Solo-Node")
        beacon_bytes = node.make_beacon()
        # Parsing own beacon must return None (preventing self-echo)
        peer = node.parse_beacon(beacon_bytes, sender_host="127.0.0.1")
        self.assertIsNone(peer)

    async def test_peer_registration_and_callback(self):
        node = SoftBusDiscovery(node_name="Collector")
        discovered_events = []

        def callback(peer):
            discovered_events.append(peer)

        node.on_peer_discovered(callback)

        peer1 = SoftBusPeer(node_id="peer_uuid_1", node_name="Peer-1", host="10.0.0.1")
        await node.register_peer(peer1)

        self.assertEqual(node.peer_count(), 1)
        self.assertEqual(len(discovered_events), 1)
        self.assertEqual(discovered_events[0].node_name, "Peer-1")

        # Registering same peer again refreshes without re-triggering listener
        await node.register_peer(peer1)
        self.assertEqual(len(discovered_events), 1)

    async def test_peer_ttl_eviction(self):
        node = SoftBusDiscovery(node_name="Evictor")
        peer = SoftBusPeer(node_id="stale_peer", node_name="Old-Peer", host="10.0.0.2")
        await node.register_peer(peer)
        self.assertEqual(node.peer_count(), 1)

        # Age the peer manually past TTL
        peer.last_seen -= 10.0
        evicted = await node.evict_stale_peers(ttl=5.0)
        self.assertEqual(evicted, 1)
        self.assertEqual(node.peer_count(), 0)


class TestSoftBusSession(unittest.TestCase):
    def setUp(self):
        self.secret = b"test_secret_key_umeros_harmony_123"
        self.session = SoftBusSession(shared_secret=self.secret)

    def test_encode_and_decode_frame(self):
        payload = b'{"action": "migrate_task", "app": "text_editor", "cursor": 42}'
        frame_bytes = self.session.encode_frame(msg_type=101, msg_id=5001, payload=payload)
        self.assertGreater(len(frame_bytes), len(payload))

        valid, frame = self.session.decode_frame(frame_bytes)
        self.assertTrue(valid)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.msg_type, 101)
        self.assertEqual(frame.msg_id, 5001)
        self.assertEqual(frame.payload, payload)
        self.assertTrue(frame.is_valid)

    def test_tampered_payload_fails_verification(self):
        payload = b"OriginalSecretData"
        frame_bytes = bytearray(self.session.encode_frame(msg_type=1, msg_id=2, payload=payload))

        # Tamper with the payload byte
        frame_bytes[-1] ^= 0xFF

        valid, frame = self.session.decode_frame(bytes(frame_bytes))
        self.assertFalse(valid)
        self.assertFalse(frame.is_valid)

    def test_wrong_shared_secret_fails_verification(self):
        sender = SoftBusSession(shared_secret=b"correct_secret_key")
        receiver = SoftBusSession(shared_secret=b"wrong_secret_key")

        frame_bytes = sender.encode_frame(msg_type=2, msg_id=3, payload=b"ProtectedPayload")
        valid, frame = receiver.decode_frame(frame_bytes)
        self.assertFalse(valid)

    def test_truncated_frame_fails_decoding(self):
        valid, frame = self.session.decode_frame(b"SHORT_DATA")
        self.assertFalse(valid)
        self.assertIsNone(frame)


if __name__ == "__main__":
    unittest.main()
