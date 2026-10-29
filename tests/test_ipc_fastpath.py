"""Tests for UmerOS Synchronous IPC Fastpath and Shared Memory Transport."""
import struct
import sys
import asyncio
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kernel.ipc.fastpath import SynchronousIPCFastpath, CapabilityCache
from kernel.ipc.shm_transport import SharedMemoryChannel
from kernel.ipc.message_protocol import PackedHeader, PackedMessage, MSG_MAGIC


class TestPackedMessage(unittest.TestCase):
    def test_header_pack_unpack(self):
        header = PackedHeader(msg_id=42, sender_pid=1, target_pid=2, payload_size=0)
        packed = header.pack()
        unpacked = PackedHeader.unpack(packed)
        self.assertEqual(unpacked.magic, MSG_MAGIC)
        self.assertEqual(unpacked.msg_id, 42)
        self.assertEqual(unpacked.sender_pid, 1)
        self.assertEqual(unpacked.target_pid, 2)

    def test_message_serialize_deserialize(self):
        msg = PackedMessage(
            header=PackedHeader(msg_id=7, sender_pid=1, target_pid=2),
            payload=b"Hello, UmerOS!",
        )
        data = msg.serialize()
        restored = PackedMessage.deserialize(data)
        self.assertEqual(restored.payload, b"Hello, UmerOS!")
        self.assertEqual(restored.header.msg_id, 7)

    def test_checksum_validation(self):
        msg = PackedMessage(
            header=PackedHeader(msg_id=1),
            payload=b"test data",
        )
        data = msg.serialize()
        # Corrupt payload
        corrupted = data[:-1] + b"\x00"
        with self.assertRaises(ValueError):
            PackedMessage.deserialize(corrupted)

    def test_invalid_magic(self):
        bad_data = struct.pack("<I", 0xDEADBEEF) + b"\x00" * 32
        with self.assertRaises(ValueError):
            PackedHeader.unpack(bad_data)

    def test_total_size(self):
        msg = PackedMessage(
            header=PackedHeader(msg_id=1),
            payload=b"abc",
        )
        self.assertEqual(msg.total_size, 28 + 3)  # HEADER_SIZE + 3


class TestCapabilityCache(unittest.TestCase):
    def test_default_allow(self):
        cache = CapabilityCache()
        self.assertTrue(cache.check(1, "ipc:2"))

    def test_grant_revoke(self):
        cache = CapabilityCache()
        cache.grant(1, "cap:test")
        self.assertTrue(cache.check(1, "cap:test"))
        cache.revoke(1, "cap:test")
        self.assertFalse(cache.check(1, "cap:test"))

    def test_clear(self):
        cache = CapabilityCache()
        cache.grant(1, "cap:test")
        cache.clear()
        self.assertTrue(cache.check(1, "cap:test"))  # default allow after clear


class TestSynchronousIPCFastpath(unittest.IsolatedAsyncioTestCase):
    async def test_register_and_call(self):
        ipc = SynchronousIPCFastpath()

        async def handler(method, *args, **kwargs):
            if method == "echo":
                return args[0] if args else None
            return None

        ipc.register_handler(10, handler)
        result = await ipc.call_sync(10, "echo", ("hello",), sender_pid=1)
        self.assertEqual(result, "hello")

    async def test_no_handler_raises(self):
        ipc = SynchronousIPCFastpath()
        with self.assertRaises(RuntimeError):
            await ipc.call_sync(99, "test", sender_pid=1)

    async def test_capability_revoke_blocks(self):
        ipc = SynchronousIPCFastpath()
        ipc.revoke_capability(1, "ipc:10")

        async def handler(method, *args, **kwargs):
            return "ok"

        ipc.register_handler(10, handler)
        with self.assertRaises(PermissionError):
            await ipc.call_sync(10, "test", sender_pid=1)

    async def test_stats_tracking(self):
        ipc = SynchronousIPCFastpath()

        async def handler(method, *args, **kwargs):
            return "ok"

        ipc.register_handler(10, handler)
        await ipc.call_sync(10, "test", sender_pid=1)
        self.assertEqual(ipc.stats["calls"], 1)
        self.assertEqual(ipc.stats["fastpath_hits"], 1)

    async def test_timeout(self):
        ipc = SynchronousIPCFastpath()

        async def slow_handler(method, *args, **kwargs):
            await asyncio.sleep(1.0)
            return "ok"

        ipc.register_handler(10, slow_handler)
        with self.assertRaises(asyncio.TimeoutError):
            await ipc.call_sync(10, "test", sender_pid=1, timeout_ms=10)

    async def test_sync_handler(self):
        ipc = SynchronousIPCFastpath()

        def sync_handler(method, *args, **kwargs):
            return 42

        ipc.register_handler(10, sync_handler)
        result = await ipc.call_sync(10, "test", sender_pid=1)
        self.assertEqual(result, 42)

    async def test_unregister_handler(self):
        ipc = SynchronousIPCFastpath()

        async def handler(method, *args, **kwargs):
            return "ok"

        ipc.register_handler(10, handler)
        self.assertEqual(ipc.handler_count, 1)
        ipc.unregister_handler(10)
        self.assertEqual(ipc.handler_count, 0)


class TestSharedMemoryChannel(unittest.TestCase):
    def test_create_destroy(self):
        shm = SharedMemoryChannel(name="test_shm", size=4096)
        self.assertTrue(shm.create())
        self.assertTrue(shm.is_active)
        shm.destroy()
        self.assertFalse(shm.is_active)

    def test_alloc_write_read(self):
        shm = SharedMemoryChannel(name="test_shm2", size=4096)
        shm.create()
        offset = shm.alloc(100, tag="test_block")
        data = b"QuantumRegister|q0q1q2"
        shm.write(offset, data)
        read_back = shm.read(offset, len(data))
        self.assertEqual(read_back, data)
        shm.destroy()

    def test_free_space_tracking(self):
        shm = SharedMemoryChannel(name="test_shm3", size=4096)
        shm.create()
        self.assertEqual(shm.used, 0)
        self.assertEqual(shm.free, 4096)
        shm.alloc(100)
        self.assertGreater(shm.used, 0)
        self.assertLess(shm.free, 4096)
        shm.destroy()

    def test_overflow_raises(self):
        shm = SharedMemoryChannel(name="test_shm4", size=256)
        shm.create()
        with self.assertRaises(MemoryError):
            shm.alloc(1000)
        shm.destroy()

    def test_get_allocation(self):
        shm = SharedMemoryChannel(name="test_shm5", size=4096)
        shm.create()
        offset = shm.alloc(64, tag="my_block")
        alloc = shm.get_allocation("my_block")
        self.assertIsNotNone(alloc)
        self.assertEqual(alloc[0], offset)
        self.assertEqual(alloc[1], 64)
        shm.destroy()


if __name__ == "__main__":
    unittest.main()