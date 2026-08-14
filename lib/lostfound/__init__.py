"""
UmerOS lost+found Module
=========================
A faithful simulation of the /lost+found directory and the filesystem
checker (fsck) recovery pipeline used in ext2/ext3/ext4 filesystems.

Filesystem, /lost+found is created by mkfs at the root of
each partition.  fsck scans for orphaned inodes — inodes that are allocated
(have data) but are not referenced by any directory entry — and creates hard
links to them inside /lost+found, named by their inode number (e.g. #12345).

The preallocated blocks inside /lost+found (created by mklost+found) ensure
that fsck can store recovered files without needing to allocate new blocks
during recovery — critical when the filesystem may be partially corrupted.

Components
----------
Inode               — Simulates an ext4 inode (type, mode, size, data, nlinks, timestamps).
SuperBlock          — Tracks filesystem geometry, free inode count, mount count, fs state.
OrphanedInode       — An inode that is allocated but not linked by any directory entry.
LostFoundManager    — Manages a per-partition lost+found directory:
                      - mklost+found  (preallocate blocks)
                      - recover       (link orphaned inodes into lost+found)
                      - list          (enumerate recovered files)
                      - claim         (user re-attaches a recovered file to the tree)
                      - purge         (delete recovered files)
                      - stats         (diagnostics)
FilesystemChecker   — fsck simulation:
                      - Phase 1: Check superblock and inode bitmap consistency.
                      - Phase 2: Check directory link counts vs inode nlinks.
                      - Phase 3: Scan for orphaned inodes (allocated, no directory ref).
                      - Phase 4: Verify lost+found exists and has preallocated blocks.
                      - Phase 5: Recover orphaned inodes into lost+found.
FsckReport          — Structured report from a fsck run (errors, recovered, actions).
FilesystemPartition — A simulated partition with its own inode table, superblock,
                      and lost+found instance.  Multiple partitions are isolated.

- mklost+found(8):  man8/mklost+found.8
- fsck(8):          man8/fsck.8
- ext4(5):          man5/ext4.5

Author:  UmerOS Project
Licence: Apache 2.0
"""

from .manager import LostFoundManager
from .inode import Inode, InodeType
from .superblock import SuperBlock
from .partition import FilesystemPartition
from .fsck import FilesystemChecker, FsckReport
from .orphan import OrphanedInode

__all__ = [
    "LostFoundManager",
    "Inode",
    "InodeType",
    "SuperBlock",
    "FilesystemPartition",
    "FilesystemChecker",
    "FsckReport",
    "OrphanedInode",
]
