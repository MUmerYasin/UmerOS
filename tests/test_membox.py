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
Unit tests for UmerOS Membox Static Memory Pool Allocator.

Tests:
- Block allocation and deallocation in O(1) time.
- Pool exhaustion raises MemoryError.
- Double-free detection raises RuntimeError.
- Boundary corruption / buffer overrun detection raises MemoryError.
- Byte read and write integrity across multiple blocks.
- Integration with MemoryManager.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kernel.membox import MemboxPool, MEMBOX_GUARD, MEMBOX_MAGIC
from kernel.memory_manager import MemoryManager


class TestMemboxPool(unittest.TestCase):
    def test_initial_pool_state(self):
        pool = MemboxPool(block_size=32, total_blocks=4, name="test_pool")
        self.assertEqual(pool.free_blocks, 4)
        self.assertEqual(pool.allocated_blocks, 0)
        self.assertEqual(pool.block_size, 32)
        self.assertEqual(pool.total_blocks, 4)

    def test_alloc_and_free_cycles(self):
        pool = MemboxPool(block_size=64, total_blocks=3)
        b0 = pool.alloc()
        b1 = pool.alloc()
        self.assertEqual(pool.allocated_blocks, 2)
        self.assertEqual(pool.free_blocks, 1)

        pool.free(b0)
        self.assertEqual(pool.allocated_blocks, 1)
        self.assertEqual(pool.free_blocks, 2)

        # Allocate again re-uses freed blocks
        b2 = pool.alloc()
        self.assertEqual(pool.allocated_blocks, 2)
        pool.free(b1)
        pool.free(b2)
        self.assertEqual(pool.allocated_blocks, 0)
        self.assertEqual(pool.free_blocks, 3)

    def test_exhaustion_raises_memory_error(self):
        pool = MemboxPool(block_size=16, total_blocks=2)
        pool.alloc()
        pool.alloc()
        self.assertEqual(pool.free_blocks, 0)
        with self.assertRaises(MemoryError):
            pool.alloc()

    def test_double_free_raises_runtime_error(self):
        pool = MemboxPool(block_size=32, total_blocks=2)
        b = pool.alloc()
        pool.free(b)
        with self.assertRaises(RuntimeError):
            pool.free(b)

    def test_invalid_block_index_raises(self):
        pool = MemboxPool(block_size=32, total_blocks=2)
        with self.assertRaises(ValueError):
            pool.free(-1)
        with self.assertRaises(ValueError):
            pool.free(99)

    def test_read_write_payload_fidelity(self):
        pool = MemboxPool(block_size=48, total_blocks=3)
        b = pool.alloc()

        payload = b"UmerOS|LiteOS|QPU_REGISTER_SAMPLE_DATA_012345"
        pool.write_block(b, payload)
        read_back = pool.read_block(b, len(payload))
        self.assertEqual(read_back, payload)

        # Test writing with offset
        pool.write_block(b, b"OVERRIDE", offset=7)
        full_read = pool.read_block(b)
        self.assertEqual(full_read[:15], b"UmerOS|OVERRIDE")

    def test_write_out_of_bounds_raises(self):
        pool = MemboxPool(block_size=16, total_blocks=1)
        b = pool.alloc()
        too_large = b"A" * 17
        with self.assertRaises(ValueError):
            pool.write_block(b, too_large)

    def test_corruption_detection_raises_memory_error(self):
        pool = MemboxPool(block_size=32, total_blocks=2)
        b = pool.alloc()

        # Simulate raw memory corruption tampering with the trailer guard
        guard_offset = b * pool._raw_block_size + 4 + pool.block_size
        pool._buffer[guard_offset] = 0x00  # corrupt the guard byte

        with self.assertRaises(MemoryError):
            pool.free(b)

    def test_memory_manager_integration(self):
        mm = MemoryManager(total_memory_bytes=4 * 1024 * 1024)
        pool = mm.create_membox_pool("ipc_headers", block_size=64, total_blocks=16)
        self.assertIsNotNone(pool)

        retrieved = mm.get_membox_pool("ipc_headers")
        self.assertEqual(retrieved, pool)

        status = mm.list_membox_pools()
        self.assertIn("ipc_headers", status)
        self.assertEqual(status["ipc_headers"]["block_size"], 64)
        self.assertEqual(status["ipc_headers"]["total_blocks"], 16)
        self.assertEqual(status["ipc_headers"]["free_blocks"], 16)

        # Duplicate name raises
        with self.assertRaises(ValueError):
            mm.create_membox_pool("ipc_headers", block_size=64, total_blocks=8)


if __name__ == "__main__":
    unittest.main()
