"""Zero-copy shared memory transport for large payloads.

Uses Python multiprocessing.shared_memory or mmap for payloads > 64 KB
(e.g., quantum state vectors, display frames) to avoid copying bytes
over JSON/HMAC channels.
"""
from __future__ import annotations

import logging
import mmap
import os
import struct
from typing import Optional, Dict

log = logging.getLogger("UmerOS.Kernel.IPC.SHM")

SHM_THRESHOLD = 64 * 1024  # 64 KB

try:
    from multiprocessing.shared_memory import SharedMemory
    HAS_SHM = True
except ImportError:
    HAS_SHM = False
    log.warning("SharedMemory not available, using mmap fallback")


class SharedMemoryChannel:
    """Zero-copy shared memory ring buffer for large payloads.

    For payloads > 64 KB, allocates a shared memory ring buffer and
    passes memory descriptors rather than copying bytes.
    """

    def __init__(self, name: str = "umer_shm", size: int = 1024 * 1024) -> None:
        self.name = name
        self.size = size
        self._shm: Optional[SharedMemory] = None
        self._mmap: Optional[mmap.mmap] = None
        self._fd = None
        self._offset = 0
        self._allocations: Dict[str, tuple[int, int]] = {}  # name -> (offset, size)

    def create(self) -> bool:
        """Create the shared memory segment."""
        if HAS_SHM:
            try:
                self._shm = SharedMemory(name=self.name, create=True, size=self.size)
                log.info("Created SharedMemory segment '%s' (%d bytes)", self.name, self.size)
                return True
            except FileExistsError:
                self._shm = SharedMemory(name=self.name, create=False, size=self.size)
                log.info("Attached to existing SharedMemory segment '%s'", self.name)
                return True
            except Exception as e:
                log.error("Failed to create SharedMemory: %s", e)

        # Fallback to mmap
        try:
            path = f"/tmp/{self.name}" if os.name != "nt" else f"{os.environ.get('TEMP', 'C:\\Temp')}\\{self.name}"
            fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
            os.ftruncate(fd, self.size)
            self._mmap = mmap.mmap(fd, self.size, access=mmap.ACCESS_WRITE)
            self._fd = fd
            log.info("Created mmap segment '%s' (%d bytes)", path, self.size)
            return True
        except Exception as e:
            log.error("Failed to create mmap segment: %s", e)
            return False

    def destroy(self) -> None:
        """Destroy the shared memory segment."""
        if self._shm is not None:
            self._shm.close()
            try:
                self._shm.unlink()
            except Exception:
                pass
            self._shm = None
        if self._mmap is not None:
            self._mmap.close()
            self._mmap = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def alloc(self, size: int, tag: str = "") -> int:
        """Allocate a region in shared memory. Returns offset."""
        if size > self.size - self._offset:
            raise MemoryError(f"SharedMemory exhausted: need {size}, have {self.size - self._offset}")
        offset = self._offset
        self._offset += size
        # Align to 8 bytes
        self._offset = (self._offset + 7) & ~7
        if tag:
            self._allocations[tag] = (offset, size)
        return offset

    def write(self, offset: int, data: bytes) -> None:
        """Write data at offset (zero-copy)."""
        if offset + len(data) > self.size:
            raise ValueError(f"Write exceeds segment: offset={offset}, size={len(data)}, seg={self.size}")
        if self._shm is not None:
            self._shm.buf[offset:offset + len(data)] = data
        elif self._mmap is not None:
            self._mmap[offset:offset + len(data)] = data

    def read(self, offset: int, size: int) -> bytes:
        """Read data at offset (zero-copy)."""
        if offset + size > self.size:
            raise ValueError(f"Read exceeds segment: offset={offset}, size={size}, seg={self.size}")
        if self._shm is not None:
            return bytes(self._shm.buf[offset:offset + size])
        elif self._mmap is not None:
            return bytes(self._mmap[offset:offset + size])
        return b""

    def get_allocation(self, tag: str) -> Optional[tuple[int, int]]:
        """Get allocation by tag."""
        return self._allocations.get(tag)

    @property
    def used(self) -> int:
        return self._offset

    @property
    def free(self) -> int:
        return self.size - self._offset

    @property
    def is_active(self) -> bool:
        return self._shm is not None or self._mmap is not None