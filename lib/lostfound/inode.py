"""
Inode — Simulates an ext4 filesystem inode.

An inode is the on-disk data structure that describes a file, directory,
socket, symlink, device node, etc.  It stores metadata (type, permissions,
size, timestamps, link count) and a pointer to the data blocks.

In real ext4:
  - Inode numbers are unique per-filesystem.
  - The inode table is a fixed-size array indexed by inode number.
  - The ``i_links_count`` field records how many directory entries point
    to this inode.  When it reaches zero AND the inode is unlinked from
    every directory, the inode is freed (or becomes an orphan if still
    allocated).
  - An inode with data but no directory references is an "orphan".

Reference: man 5 ext4, Documentation/filesystems/ext4/inodes.rst
"""

from __future__ import annotations

import enum
import time
from typing import Any, Dict, List, Optional


class InodeType(enum.IntEnum):
    """ext4 file mode / type flags (S_IFMT bits)."""

    REGULAR   = 0o100000   # -  regular file
    DIRECTORY = 0o040000   # d  directory
    SYMLINK   = 0o120000   # l  symbolic link
    SOCKET    = 0o140000   # s  socket
    FIFO      = 0o010000   # p  named pipe
    CHARDEV   = 0o020000   # c  character device
    BLKDEV    = 0o060000   # b  block device

    @property
    def type_char(self) -> str:
        """The single-character type indicator as shown by `ls -l`."""
        return {
            InodeType.REGULAR:   "-",
            InodeType.DIRECTORY: "d",
            InodeType.SYMLINK:   "l",
            InodeType.SOCKET:    "s",
            InodeType.FIFO:      "p",
            InodeType.CHARDEV:   "c",
            InodeType.BLKDEV:    "b",
        }[self]


# Number of bytes a single filesystem block represents in this simulation.
# ext4 default block size is 4096 bytes.
DEFAULT_BLOCK_SIZE = 4096


class Inode:
    """A single simulated ext4 inode.

    Attributes:
        ino:          Inode number (unique within its filesystem).
        type:         One of :class:`InodeType`.
        mode_perm:    Low 12 bits of the mode (permission bits, e.g. 0o755).
        uid / gid:    Numeric owner / group IDs.
        size:         File size in bytes.
        blocks:       Number of 512-byte sectors "used" (st_blocks in stat).
        nlinks:       Number of hard links (directory entries) pointing here.
        atime:        Access time (epoch seconds).
        mtime:        Modification time (epoch seconds).
        ctime:        Inode change time (epoch seconds).
        data:         File payload (bytes or, for directories, the dirent list).
        target:       Symlink target string (only for SYMLINK type).
        corrupted:    True if the inode has been marked corrupted (fsck will
                      not be able to recover corrupted inodes safely).
        allocated:    True if the inode bitmap marks this inode as in-use.
        deleted:      True if ``unlink`` was called and nlinks == 0 but the
                      inode is still allocated (i.e. it is an orphan candidate).
    """

    __slots__ = (
        "ino", "type", "mode_perm", "uid", "gid",
        "size", "blocks", "nlinks",
        "atime", "mtime", "ctime",
        "data", "target", "extra",
        "corrupted", "allocated", "deleted",
    )

    def __init__(
        self,
        ino: int,
        type: InodeType = InodeType.REGULAR,
        mode_perm: int = 0o644,
        uid: int = 0,
        gid: int = 0,
        data: Any = b"",
        target: Optional[str] = None,
        allocated: bool = True,
        nlinks: Optional[int] = None,
    ) -> None:
        self.ino: int = ino
        self.type: InodeType = type
        self.mode_perm: int = mode_perm
        self.uid: int = uid
        self.gid: int = gid
        self.data: Any = data
        self.target: Optional[str] = target
        self.allocated: bool = allocated
        self.corrupted: bool = False
        self.deleted: bool = False

        # Directories normally start with nlinks=2 (. and parent's entry).
        if nlinks is not None:
            self.nlinks: int = nlinks
        elif type == InodeType.DIRECTORY:
            self.nlinks = 2
        else:
            self.nlinks = 1

        now = time.time()
        self.atime: float = now
        self.mtime: float = now
        self.ctime: float = now

        self._recompute_size_and_blocks()

    # -- internal helpers --------------------------------------------------

    def _recompute_size_and_blocks(self) -> None:
        """Recompute ``size`` and ``blocks`` from ``data``."""
        if self.type == InodeType.DIRECTORY:
            # ``data`` for a directory is a list of (name, ino) dirents.
            dirents = self.data if isinstance(self.data, list) else []
            # A directory's "size" is roughly 4096 (one block) in real ext4.
            self.size = len(dirents) * 24 + 64
        elif self.type == InodeType.SYMLINK:
            self.size = len(self.target or "")
        else:
            if isinstance(self.data, str):
                raw = self.data.encode("utf-8")
            elif isinstance(self.data, (bytes, bytearray)):
                raw = self.data
            else:
                raw = b""
            self.size = len(raw)

        # ``blocks`` counts 512-byte units (matching st_blocks).
        self.blocks = (self.size + 511) // 512
        if self.blocks == 0:
            self.blocks = 0

    # -- public API --------------------------------------------------------

    def touch(self) -> None:
        """Update mtime/ctime/atime to now."""
        now = time.time()
        self.mtime = now
        self.ctime = now
        self.atime = now

    def set_data(self, data: Any) -> None:
        """Set the file payload and recompute size/blocks."""
        self.data = data
        self._recompute_size_and_blocks()
        self.mtime = time.time()
        self.ctime = self.mtime

    def add_dirent(self, name: str, target_ino: int) -> None:
        """Add a directory entry (for DIRECTORY inodes only)."""
        if self.type != InodeType.DIRECTORY:
            raise ValueError(f"Inode {self.ino} is not a directory.")
        if not isinstance(self.data, list):
            self.data = []
        for existing_name, _ in self.data:
            if existing_name == name:
                raise FileExistsError(
                    f"Dirent '{name}' already exists in inode {self.ino}."
                )
        self.data.append((name, target_ino))
        self._recompute_size_and_blocks()
        self.touch()

    def remove_dirent(self, name: str) -> int:
        """Remove a directory entry; return the inode number it pointed to.

        Raises KeyError if not found.
        """
        if self.type != InodeType.DIRECTORY:
            raise ValueError(f"Inode {self.ino} is not a directory.")
        for i, (existing_name, target_ino) in enumerate(self.data or []):
            if existing_name == name:
                self.data.pop(i)
                self._recompute_size_and_blocks()
                self.touch()
                return target_ino
        raise KeyError(f"Dirent '{name}' not found in inode {self.ino}.")

    def find_dirent(self, name: str) -> Optional[int]:
        """Look up a child name in this directory; return its ino or None."""
        if self.type != InodeType.DIRECTORY:
            return None
        for existing_name, target_ino in (self.data or []):
            if existing_name == name:
                return target_ino
        return None

    def list_dirents(self) -> List[tuple]:
        """Return a copy of the dirent list [(name, ino), ...]."""
        if self.type != InodeType.DIRECTORY:
            return []
        return list(self.data or [])

    @property
    def mode(self) -> int:
        """Full mode word (type bits | permission bits), as returned by stat."""
        return int(self.type) | (self.mode_perm & 0o7777)

    @mode.setter
    def mode(self, value: int) -> None:
        self.type = InodeType(value & 0o170000)
        self.mode_perm = value & 0o7777

    def permission_string(self) -> str:
        """Return e.g. ``drwxr-xr-x``."""
        perm = self.mode_perm
        bits = [
            ("r", perm & 0o400), ("w", perm & 0o200), ("x", perm & 0o100),
            ("r", perm & 0o040), ("w", perm & 0o020), ("x", perm & 0o010),
            ("r", perm & 0o004), ("w", perm & 0o002), ("x", perm & 0o001),
        ]
        s = "".join(c if on else "-" for c, on in bits)
        # setuid/setgid/sticky
        special = ""
        if perm & 0o4000: special = "s" if (perm & 0o100) else "S"
        if perm & 0o2000: special = "s" if (perm & 0o010) else "S"
        if perm & 0o1000: special = "t" if (perm & 0o001) else "T"
        # Replace the execute position with the special char if set.
        if special:
            s = s[:len(s) - (3 if (perm & 0o4000) else (0))]  # no-op safe
        return self.type.type_char + s

    def is_orphan(self) -> bool:
        """An orphan is allocated, has data, but nlinks == 0."""
        return self.allocated and self.nlinks == 0 and not self.corrupted

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (for reports / debugging)."""
        return {
            "ino":         self.ino,
            "type":        self.type.type_char,
            "mode":        oct(self.mode),
            "perm":        self.permission_string(),
            "uid":         self.uid,
            "gid":         self.gid,
            "size":        self.size,
            "blocks":      self.blocks,
            "nlinks":      self.nlinks,
            "allocated":   self.allocated,
            "corrupted":   self.corrupted,
            "deleted":     self.deleted,
            "mtime":       self.mtime,
            "atime":       self.atime,
            "ctime":       self.ctime,
            "data_len":    (len(self.data) if self.data is not None else 0),
            "target":      self.target,
            "is_orphan":   self.is_orphan(),
        }

    def __repr__(self) -> str:
        return (
            f"Inode(ino={self.ino}, type={self.type.type_char!r}, "
            f"size={self.size}, nlinks={self.nlinks}, "
            f"allocated={self.allocated}, corrupted={self.corrupted})"
        )
