"""
SuperBlock — Simulates the ext4 superblock.

The superblock records global filesystem geometry and bookkeeping:
  - total inodes / blocks
  - free  inodes / blocks
  - mount count and max mount count before a forced fsck
  - filesystem state (clean / errors / valid)
  - last fsck time and error count
  - block size

fsck always validates the superblock first (Phase 1).  If the superblock
is corrupt, the filesystem cannot be mounted.

Reference: man 5 ext4, fsck(8) ``-f`` flag forces a check regardless of
the clean flag.
"""

from __future__ import annotations

import enum
import time
from typing import Any, Dict


class FsState(enum.Enum):
    """ext4 superblock ``s_state`` values."""

    CLEAN  = 1   # FS_CLEANLY_UMOUNTED — unmounted properly, no check needed
    DIRTY  = 2   # mounted or crashed without clean unmount
    ERRORS = 4   # FS_ERROR — errors detected


class SuperBlock:
    """Simulated ext4 superblock.

    Args:
        total_inodes:    Size of the inode table.
        total_blocks:    Total data blocks on the partition.
        block_size:      Bytes per block (default 4096).
        max_mount_count: Mounts between forced fsck runs (default 20).
    """

    def __init__(
        self,
        total_inodes: int = 1024,
        total_blocks: int = 8192,
        block_size: int = 4096,
        max_mount_count: int = 20,
    ) -> None:
        self.block_size: int = block_size
        self.total_inodes: int = total_inodes
        self.total_blocks: int = total_blocks

        # Reserve inode 0 (invalid) — real ext4 starts at ino 1 (root) and
        # uses ino 2 for the root directory.  We follow that convention.
        self.free_inodes: int = total_inodes - 1   # ino 0 reserved
        self.free_blocks: int = total_blocks

        # Mount bookkeeping
        self.mount_count: int = 0
        self.max_mount_count: int = max_mount_count
        self.last_fsck_time: float = time.time()
        self.fsck_count: int = 0

        # State
        self.state: FsState = FsState.CLEAN
        self.error_count: int = 0
        self.last_error: str = ""

        # Reserved GDT blocks (for online resizing) — not used in sim but
        # present for realism.
        self.reserved_gdt_blocks: int = 16

    # -- lifecycle --------------------------------------------------------

    def on_mount(self) -> Dict[str, Any]:
        """Called when the filesystem is mounted.

        Increments mount_count, marks FS dirty, and returns a dict that
        tells the caller whether a forced fsck is due.
        """
        self.mount_count += 1
        self.state = FsState.DIRTY
        return {
            "mount_count":      self.mount_count,
            "max_mount_count":  self.max_mount_count,
            "needs_fsck":       self.mount_count >= self.max_mount_count,
            "state":            self.state.name,
        }

    def on_unmount(self) -> None:
        """Mark the filesystem as cleanly unmounted."""
        self.state = FsState.CLEAN

    def mark_clean(self) -> None:
        """Called by fsck after a successful, error-free check."""
        self.state = FsState.CLEAN
        self.last_fsck_time = time.time()
        self.fsck_count += 1
        self.mount_count = 0   # reset the mount counter

    def mark_errors(self, message: str = "") -> None:
        """Record a filesystem error."""
        self.state = FsState.ERRORS
        self.error_count += 1
        self.last_error = message

    def allocate_inode(self) -> bool:
        """Account for one inode being marked in-use."""
        if self.free_inodes <= 0:
            return False
        self.free_inodes -= 1
        return True

    def free_one_inode(self) -> None:
        """Account for one inode being freed."""
        self.free_inodes += 1

    def allocate_blocks(self, n: int = 1) -> bool:
        """Account for ``n`` blocks being allocated."""
        if self.free_blocks < n:
            return False
        self.free_blocks -= n
        return True

    def free_blocks_n(self, n: int = 1) -> None:
        """Account for ``n`` blocks being freed."""
        self.free_blocks += n

    # -- inspection -------------------------------------------------------

    def needs_check(self, force: bool = False) -> bool:
        """Return True if a fsck should run.

        Mirrors fsck(8): run if force=True, if FS is dirty, if error state
        is set, or if the mount count has exceeded max_mount_count.
        """
        if force:
            return True
        if self.state != FsState.CLEAN:
            return True
        if self.mount_count >= self.max_mount_count:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "block_size":         self.block_size,
            "total_inodes":       self.total_inodes,
            "free_inodes":        self.free_inodes,
            "total_blocks":       self.total_blocks,
            "free_blocks":        self.free_blocks,
            "mount_count":        self.mount_count,
            "max_mount_count":    self.max_mount_count,
            "state":              self.state.name,
            "error_count":        self.error_count,
            "last_error":         self.last_error,
            "fsck_count":         self.fsck_count,
            "last_fsck_time":     self.last_fsck_time,
            "reserved_gdt":       self.reserved_gdt_blocks,
        }

    def __repr__(self) -> str:
        return (
            f"SuperBlock(state={self.state.name}, "
            f"inodes={self.free_inodes}/{self.total_inodes} free, "
            f"blocks={self.free_blocks}/{self.total_blocks} free, "
            f"mounts={self.mount_count}/{self.max_mount_count})"
        )
