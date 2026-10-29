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
UmerOS Membox Static Memory Pool Allocator (los_membox.c).

Provides deterministic O(1) allocation and deallocation of fixed-size memory blocks
with zero internal fragmentation, cross-border corruption detection, and boundary guard tags.
Ideal for fixed-size simulated page descriptors, IPC message headers, and quantum registers.
"""

from __future__ import annotations

import struct
from typing import List, Optional

MEMBOX_MAGIC: int = 0xAA55AA55
MEMBOX_GUARD: int = 0x55AA55AA


class MemboxPool:
    """Fixed-size static block memory pool.

    Memory layout per block:
    [4 bytes Magic Header] [block_size bytes User Payload] [4 bytes Guard Trailer]
    """

    def __init__(self, block_size: int, total_blocks: int, name: str = "membox") -> None:
        if block_size < 4:
            block_size = 4
        # 4-byte align the block size
        self.block_size: int = (block_size + 3) & ~3
        if total_blocks <= 0:
            raise ValueError(f"total_blocks must be positive; got {total_blocks}")
        self.total_blocks: int = total_blocks
        self.name: str = name

        # Header (4B) + Payload (block_size) + Trailer (4B)
        self._raw_block_size: int = self.block_size + 8
        self._buffer: bytearray = bytearray(self._raw_block_size * total_blocks)
        self._free_list: List[int] = list(range(total_blocks))
        self._allocated_count: int = 0

        # Initialize magic tags for all blocks
        for i in range(total_blocks):
            offset = i * self._raw_block_size
            struct.pack_into("<I", self._buffer, offset, MEMBOX_MAGIC)
            struct.pack_into("<I", self._buffer, offset + 4 + self.block_size, MEMBOX_GUARD)

    @property
    def free_blocks(self) -> int:
        """Return the number of unallocated blocks."""
        return len(self._free_list)

    @property
    def allocated_blocks(self) -> int:
        """Return the number of currently allocated blocks."""
        return self._allocated_count

    @property
    def total_memory_bytes(self) -> int:
        """Return total bytes occupied by the pool buffer."""
        return len(self._buffer)

    def alloc(self) -> int:
        """Allocate a block index in O(1) time.

        Returns:
            The integer index of the allocated block (0 <= index < total_blocks).

        Raises:
            MemoryError: If all blocks are in use.
        """
        if not self._free_list:
            raise MemoryError(
                f"MemboxPool '{self.name}' exhausted: 0 of {self.total_blocks} blocks free."
            )
        block_idx = self._free_list.pop(0)
        self._allocated_count += 1
        return block_idx

    def free(self, block_idx: int) -> bool:
        """Free a previously allocated block back to the pool.

        Args:
            block_idx: The integer index of the block to free.

        Returns:
            True on success.

        Raises:
            ValueError: If block_idx is out of range.
            RuntimeError: If double-free is attempted.
            MemoryError: If boundary corruption / buffer overrun is detected.
        """
        if block_idx < 0 or block_idx >= self.total_blocks:
            raise ValueError(f"Invalid block index {block_idx} for pool '{self.name}'.")
        if block_idx in self._free_list:
            raise RuntimeError(f"Double-free detected on block {block_idx} in pool '{self.name}'.")

        self._verify_block(block_idx)
        self._free_list.append(block_idx)
        self._allocated_count -= 1
        return True

    def write_block(self, block_idx: int, data: bytes, offset: int = 0) -> None:
        """Write bytes into the user payload area of the specified block.

        Args:
            block_idx: Allocated block index.
            data: Bytes to write.
            offset: Byte offset within the user payload.

        Raises:
            ValueError: If write would exceed block_size.
            MemoryError: If block corruption is detected.
        """
        if block_idx < 0 or block_idx >= self.total_blocks:
            raise ValueError(f"Invalid block index: {block_idx}")
        if offset < 0 or offset + len(data) > self.block_size:
            raise ValueError(
                f"Write out of bounds: data length {len(data)} at offset {offset} "
                f"exceeds block payload size {self.block_size}."
            )
        self._verify_block(block_idx)
        buf_offset = block_idx * self._raw_block_size + 4 + offset
        self._buffer[buf_offset : buf_offset + len(data)] = data

    def read_block(self, block_idx: int, length: Optional[int] = None, offset: int = 0) -> bytes:
        """Read bytes from the user payload area of the specified block.

        Args:
            block_idx: Allocated block index.
            length: Number of bytes to read, or None to read the entire block payload.
            offset: Byte offset within the user payload.

        Returns:
            Extracted bytes.

        Raises:
            ValueError: If read range exceeds block_size.
            MemoryError: If block corruption is detected.
        """
        if block_idx < 0 or block_idx >= self.total_blocks:
            raise ValueError(f"Invalid block index: {block_idx}")
        if offset < 0 or offset >= self.block_size:
            raise ValueError(f"Read offset {offset} exceeds block payload size {self.block_size}.")
        self._verify_block(block_idx)
        read_len = (self.block_size - offset) if length is None else min(length, self.block_size - offset)
        buf_offset = block_idx * self._raw_block_size + 4 + offset
        return bytes(self._buffer[buf_offset : buf_offset + read_len])

    def _verify_block(self, block_idx: int) -> None:
        """Verify boundary guard tags to detect buffer overflows or corruption."""
        offset = block_idx * self._raw_block_size
        magic = struct.unpack_from("<I", self._buffer, offset)[0]
        guard = struct.unpack_from("<I", self._buffer, offset + 4 + self.block_size)[0]
        if magic != MEMBOX_MAGIC or guard != MEMBOX_GUARD:
            raise MemoryError(
                f"Membox corruption detected on block {block_idx} in pool '{self.name}'! "
                f"Header magic: 0x{magic:08X} (expected 0x{MEMBOX_MAGIC:08X}), "
                f"Guard trailer: 0x{guard:08X} (expected 0x{MEMBOX_GUARD:08X})."
            )
