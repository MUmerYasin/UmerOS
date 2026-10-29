"""Tests for UmerOS Distributed VFS and CRDT Distributed Data Objects."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fs.dfs.distributed_vfs import DistributedVFS
from fs.dfs.crdt_object import DistributedDataObject, LWWRegister, HybridLogicalClock


class TestDistributedVFS(unittest.TestCase):
    def test_parse_local_path(self):
        vfs = DistributedVFS(node_id="node1")
        peer, path = vfs.parse_path("/home/user/file.txt")
        self.assertEqual(peer, "node1")
        self.assertEqual(path, "/home/user/file.txt")

    def test_parse_remote_path(self):
        vfs = DistributedVFS(node_id="node1")
        peer, path = vfs.parse_path("dfs://node2/shared/doc.txt")
        self.assertEqual(peer, "node2")
        self.assertEqual(path, "/shared/doc.txt")

    def test_register_evict_peer(self):
        vfs = DistributedVFS(node_id="node1")
        vfs.register_peer("node2", {"ip": "192.168.1.2"})
        self.assertIn("node2", vfs.list_peers())
        vfs.evict_peer("node2")
        self.assertNotIn("node2", vfs.list_peers())

    def test_exists_local(self):
        vfs = DistributedVFS(node_id="node1")
        self.assertTrue(vfs.exists("/tmp/test.txt"))

    def test_exists_remote_peer(self):
        vfs = DistributedVFS(node_id="node1")
        vfs.register_peer("node2", {})
        self.assertTrue(vfs.exists("dfs://node2/shared/file.txt"))

    def test_stat(self):
        vfs = DistributedVFS(node_id="node1")
        info = vfs.stat("dfs://node2/shared/file.txt")
        self.assertEqual(info["peer_id"], "node2")

    def test_readdir_remote(self):
        vfs = DistributedVFS(node_id="node1")
        vfs.register_peer("node2", {})
        entries = vfs.readdir("dfs://node2/")
        self.assertTrue(len(entries) > 0)

    def test_cache_operations(self):
        vfs = DistributedVFS(node_id="node1", cache_size=4)
        self.assertEqual(vfs.cache_size, 0)


class TestHybridLogicalClock(unittest.TestCase):
    def test_tick_increments(self):
        clock = HybridLogicalClock("node1")
        ts1 = clock.tick()
        # Force exact same physical time to test logical increment
        import unittest.mock as mock
        with mock.patch("time.time", return_value=ts1[0]):
            ts2 = clock.tick()
        self.assertGreater(ts2[1], ts1[1])  # logical increments

    def test_update_from_remote(self):
        clock = HybridLogicalClock("node1")
        clock.update(1000.0, 5)
        self.assertGreaterEqual(clock.physical, 1000.0)

    def test_compare(self):
        clock = HybridLogicalClock("node1")
        ts = clock.tick()
        self.assertEqual(clock.compare(ts[0], ts[1], ts[2]), 0)  # same


class TestLWWRegister(unittest.TestCase):
    def test_set_and_get(self):
        reg = LWWRegister("node1", initial_value="hello")
        self.assertEqual(reg.value, "hello")
        ts = reg.set("world")
        self.assertEqual(reg.value, "world")
        self.assertIsNotNone(ts)

    def test_merge_applies_newer(self):
        reg = LWWRegister("node1", initial_value="old")
        # Remote update with future timestamp
        ts = reg.clock.tick()
        future_ts = (ts[0] + 100, ts[1] + 1, "node2")
        applied = reg.merge("new", future_ts)
        self.assertTrue(applied)
        self.assertEqual(reg.value, "new")

    def test_merge_rejects_older(self):
        reg = LWWRegister("node1", initial_value="current")
        reg.set("current")  # establish local timestamp
        # Remote with past timestamp should be rejected
        applied = reg.merge("stale", (0.0, 0, "node2"))
        self.assertFalse(applied)


class TestDistributedDataObject(unittest.TestCase):
    def test_set_and_get(self):
        ddo = DistributedDataObject("node1", "test_obj")
        ddo.set("status", "active")
        self.assertEqual(ddo.get("status"), "active")

    def test_merge_remote(self):
        ddo = DistributedDataObject("node1")
        ts = ddo.set("key", "local")
        # Merge remote with higher timestamp
        future_ts = (ts[0] + 100, ts[1] + 1, "node2")
        applied = ddo.merge_remote("key", "remote", future_ts)
        self.assertTrue(applied)
        self.assertEqual(ddo.get("key"), "remote")

    def test_listener_notification(self):
        ddo = DistributedDataObject("node1")
        received = []

        def listener(key, value):
            received.append((key, value))

        ddo.add_listener(listener)
        ddo.set("x", 42)
        self.assertEqual(received, [("x", 42)])

    def test_get_state(self):
        ddo = DistributedDataObject("node1")
        ddo.set("a", 1)
        ddo.set("b", 2)
        state = ddo.get_state()
        self.assertEqual(state, {"a": 1, "b": 2})

    def test_repr(self):
        ddo = DistributedDataObject("node1", "my_obj")
        r = repr(ddo)
        self.assertIn("my_obj", r)


if __name__ == "__main__":
    unittest.main()