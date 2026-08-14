"""
FilesystemPartition — A single simulated filesystem partition.

Each partition owns:
  * an inode table (dict of inode-number -> Inode)
  * a :class:`SuperBlock`
  * its own isolated :class:`LostFoundManager`
  * a directory tree built from directory inodes (dirent lists)

A real Linux box has multiple partitions (e.g. ``/dev/sda1`` mounted at
``/boot``, ``/dev/sda2`` mounted at ``/``, ``/dev/sda3`` at ``/home``),
each with its own lost+found.  We model that by giving each partition its
own inode space.

The partition also provides the block/inode accounting helpers that fsck
and lost+found need.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .inode import DEFAULT_BLOCK_SIZE, Inode, InodeType
from .manager import LOST_FOUND_NAME, LostFoundManager
from .superblock import SuperBlock

log = logging.getLogger("UmerOS.Partition")


class FilesystemPartition:
    """A single simulated ext4-style filesystem partition.

    Args:
        name:        Device name, e.g. ``sda1``.
        mount_point: Where it is mounted, e.g. ``/`` or ``/home``.
        total_inodes: Inode table size.
        total_blocks: Block count.
        block_size:   Bytes per block.
        fs_type:      Filesystem type label (``ext4``, ``ext3``, ``ext2``).
    """

    def __init__(
        self,
        name: str = "sda1",
        mount_point: str = "/",
        total_inodes: int = 1024,
        total_blocks: int = 8192,
        block_size: int = DEFAULT_BLOCK_SIZE,
        fs_type: str = "ext4",
    ) -> None:
        self.name: str = name
        self.mount_point: str = mount_point
        self.fs_type: str = fs_type
        self.block_size: int = block_size

        self.superblock: SuperBlock = SuperBlock(
            total_inodes=total_inodes,
            total_blocks=total_blocks,
            block_size=block_size,
        )

        # inode table: ino -> Inode
        self._inodes: Dict[int, Inode] = {}
        # Next inode number to hand out.  Ino 0 is reserved (invalid).
        self._next_ino: int = 1
        self.root_ino: int = self._allocate_root()

        # Each partition gets its own isolated lost+found.
        lf_path = (mount_point.rstrip("/") + "/" + LOST_FOUND_NAME).replace("//", "/")
        if lf_path.startswith("//"):
            lf_path = lf_path[1:]
        self.lost_found: LostFoundManager = LostFoundManager(
            partition=self, path=lf_path,
        )

        log.info(
            "Partition %s mounted at %s (%s, root_ino=%d).",
            name, mount_point, fs_type, self.root_ino,
        )

    # ------------------------------------------------------------------ #
    # Root directory
    # ------------------------------------------------------------------ #

    def _allocate_root(self) -> int:
        """Allocate inode 1 as the root directory."""
        root = Inode(
            ino=1, type=InodeType.DIRECTORY,
            mode_perm=0o755, uid=0, gid=0, data=[], allocated=True, nlinks=2,
        )
        self._inodes[1] = root
        self.superblock.allocate_inode()
        # Advance the next-inode counter past the root.
        self._next_ino = 2
        return 1

    # ------------------------------------------------------------------ #
    # Inode allocation / deallocation
    # ------------------------------------------------------------------ #

    def allocate_inode(
        self,
        type: InodeType = InodeType.REGULAR,
        mode_perm: int = 0o644,
        uid: int = 0,
        gid: int = 0,
        data: Any = b"",
        target: Optional[str] = None,
        nlinks: Optional[int] = None,
    ) -> Inode:
        """Allocate a fresh inode and return it."""
        if self.superblock.free_inodes <= 0:
            raise OSError("ENOSPC: no free inodes on partition.")
        ino = self._next_ino
        self._next_ino += 1
        inode = Inode(
            ino=ino, type=type, mode_perm=mode_perm,
            uid=uid, gid=gid, data=data, target=target,
            allocated=True, nlinks=nlinks,
        )
        self._inodes[ino] = inode
        self.superblock.allocate_inode()
        self.superblock.allocate_blocks(max(1, inode.blocks))
        return inode

    def free_inode(self, ino: int) -> bool:
        """Mark an inode as freed."""
        inode = self._inodes.get(ino)
        if inode is None or not inode.allocated:
            return False
        inode.allocated = False
        inode.nlinks = 0
        inode.deleted = True
        self.superblock.free_one_inode()
        self.superblock.free_blocks_n(max(1, inode.blocks))
        return True

    def get_inode(self, ino: int) -> Optional[Inode]:
        """Return the inode with the given number, or None."""
        return self._inodes.get(ino)

    def iter_inodes(self) -> Iterator[Tuple[int, Inode]]:
        """Iterate over all inodes (allocated or not)."""
        for ino in sorted(self._inodes):
            yield ino, self._inodes[ino]

    def iter_allocated_inodes(self) -> Iterator[Tuple[int, Inode]]:
        """Iterate only over allocated inodes."""
        for ino, inode in self.iter_inodes():
            if inode.allocated:
                yield ino, inode

    # ------------------------------------------------------------------ #
    # Path-based operations (convenience layer on top of inodes)
    # ------------------------------------------------------------------ #

    def _resolve(self, path: str) -> Optional[Inode]:
        """Resolve a VFS-style path to an inode, or None."""
        if not path or path == "/":
            return self._inodes[self.root_ino]
        parts = [p for p in path.split("/") if p and p != "."]
        # Handle ".."
        resolved: List[str] = []
        for p in parts:
            if p == "..":
                if resolved:
                    resolved.pop()
            else:
                resolved.append(p)
        cur = self._inodes[self.root_ino]
        for p in resolved:
            if cur.type != InodeType.DIRECTORY:
                return None
            child_ino = cur.find_dirent(p)
            if child_ino is None:
                return None
            cur = self._inodes.get(child_ino)
            if cur is None:
                return None
        return cur

    def create_file(
        self, path: str, data: bytes = b"", mode_perm: int = 0o644,
        uid: int = 0, gid: int = 0,
    ) -> Inode:
        """Create a regular file at ``path``."""
        parent_path, name = self._split_path(path)
        parent = self._resolve(parent_path)
        if parent is None or parent.type != InodeType.DIRECTORY:
            raise FileNotFoundError(f"Parent directory not found: {parent_path}")
        if parent.find_dirent(name) is not None:
            raise FileExistsError(f"File exists: {path}")
        inode = self.allocate_inode(
            InodeType.REGULAR, mode_perm=mode_perm, uid=uid, gid=gid,
            data=data,
        )
        parent.add_dirent(name, inode.ino)
        return inode

    def create_directory(
        self, path: str, mode_perm: int = 0o755, uid: int = 0, gid: int = 0,
    ) -> Inode:
        """Create a directory at ``path``."""
        parent_path, name = self._split_path(path)
        parent = self._resolve(parent_path)
        if parent is None or parent.type != InodeType.DIRECTORY:
            raise FileNotFoundError(f"Parent directory not found: {parent_path}")
        if parent.find_dirent(name) is not None:
            raise FileExistsError(f"Directory exists: {path}")
        inode = self.allocate_inode(
            InodeType.DIRECTORY, mode_perm=mode_perm, uid=uid, gid=gid,
            data=[], nlinks=2,
        )
        parent.add_dirent(name, inode.ino)
        # Creating a subdir bumps the parent's nlinks by 1 (the subdir's "..").
        parent.nlinks += 1
        return inode

    def create_symlink(self, path: str, target: str) -> Inode:
        """Create a symbolic link at ``path`` pointing to ``target``."""
        parent_path, name = self._split_path(path)
        parent = self._resolve(parent_path)
        if parent is None or parent.type != InodeType.DIRECTORY:
            raise FileNotFoundError(f"Parent directory not found: {parent_path}")
        if parent.find_dirent(name) is not None:
            raise FileExistsError(f"Symlink exists: {path}")
        inode = self.allocate_inode(
            InodeType.SYMLINK, mode_perm=0o777, data=b"", target=target,
        )
        parent.add_dirent(name, inode.ino)
        return inode

    def unlink(self, path: str) -> bool:
        """Remove a directory entry and decrement the target's nlinks.

        If nlinks reaches zero the inode becomes an *orphan candidate* —
        it is still allocated (data present) but unreferenced.  fsck will
        later recover it into lost+found.
        """
        parent_path, name = self._split_path(path)
        parent = self._resolve(parent_path)
        if parent is None or parent.type != InodeType.DIRECTORY:
            return False
        try:
            target_ino = parent.remove_dirent(name)
        except KeyError:
            return False
        target = self._inodes.get(target_ino)
        if target is not None:
            target.nlinks = max(0, target.nlinks - 1)
            if target.nlinks == 0:
                target.deleted = True
                # NOTE: we deliberately do NOT free the inode here.
                # It is now an orphan that fsck can recover.
        return True

    def read_file(self, path: str) -> bytes:
        inode = self._resolve(path)
        if inode is None:
            raise FileNotFoundError(path)
        if inode.type != InodeType.REGULAR:
            raise IsADirectoryError(path)
        return inode.data if isinstance(inode.data, (bytes, bytearray)) else b""

    def list_dir(self, path: str = "/") -> List[Tuple[str, int]]:
        """Return [(name, ino), ...] for a directory."""
        inode = self._resolve(path)
        if inode is None or inode.type != InodeType.DIRECTORY:
            return []
        return inode.list_dirents()

    # ------------------------------------------------------------------ #
    # Damage / corruption simulation (for testing fsck)
    # ------------------------------------------------------------------ #

    def orphan_inode(self, ino: int) -> bool:
        """Manually orphan an inode: drop all directory references to it
        but leave it allocated.  Returns True if the inode existed."""
        inode = self._inodes.get(ino)
        if inode is None:
            return False
        # Remove every dirent in every directory that points at it.
        for _, d in list(self._inodes.items()):
            if d.type == InodeType.DIRECTORY:
                for name, target_ino in list(d.list_dirents()):
                    if target_ino == ino:
                        try:
                            d.remove_dirent(name)
                        except KeyError:
                            pass
        inode.nlinks = 0
        inode.deleted = True
        return True

    def corrupt_inode(self, ino: int) -> bool:
        """Mark an inode as corrupted (fsck will skip it)."""
        inode = self._inodes.get(ino)
        if inode is None:
            return False
        inode.corrupted = True
        return True

    def break_link_count(self, ino: int, fake_nlinks: int) -> bool:
        """Force an inode's nlinks to a wrong value (to trigger Phase 2)."""
        inode = self._inodes.get(ino)
        if inode is None:
            return False
        inode.nlinks = fake_nlinks
        return True

    def lose_superblock_blocks(self) -> None:
        """Corrupt the superblock's free-block count."""
        self.superblock.free_blocks = self.superblock.total_blocks + 999

    # ------------------------------------------------------------------ #
    # Accounting helpers (used by fsck)
    # ------------------------------------------------------------------ #

    def register_lost_found_entry(self, name: str, ino: int) -> bool:
        """Add a dirent inside the lost+found directory inode of this partition.

        This is called by LostFoundManager.recover() so that the partition's
        dirent tree actually references the recovered inode — otherwise a
        second fsck run would re-detect it as an orphan.
        """
        from .manager import LOST_FOUND_NAME
        root = self._inodes.get(self.root_ino)
        if root is None:
            return False
        lf_ino = root.find_dirent(LOST_FOUND_NAME)
        if lf_ino is None:
            return False
        lf_dir = self._inodes.get(lf_ino)
        if lf_dir is None or lf_dir.type != InodeType.DIRECTORY:
            return False
        try:
            lf_dir.add_dirent(name, ino)
        except FileExistsError:
            return False
        return True

    def unregister_lost_found_entry(self, name: str) -> bool:
        """Remove a dirent from the lost+found directory inode (for purges)."""
        from .manager import LOST_FOUND_NAME
        root = self._inodes.get(self.root_ino)
        if root is None:
            return False
        lf_ino = root.find_dirent(LOST_FOUND_NAME)
        if lf_ino is None:
            return False
        lf_dir = self._inodes.get(lf_ino)
        if lf_dir is None or lf_dir.type != InodeType.DIRECTORY:
            return False
        try:
            lf_dir.remove_dirent(name)
        except KeyError:
            return False
        return True

    def used_inode_count(self) -> int:
        return sum(1 for _, i in self._inodes.values() if False) or sum(
            1 for _, i in self.iter_inodes() if i.allocated
        )

    def used_block_count(self) -> int:
        return sum(
            max(1, i.blocks) for _, i in self.iter_inodes() if i.allocated
        )

    # ------------------------------------------------------------------ #
    # mkfs-style setup
    # ------------------------------------------------------------------ #

    def mkfs(self) -> Dict[str, Any]:
        """Simulate ``mkfs.ext4``: ensure root + lost+found exist with
        preallocated blocks.  Returns a summary dict."""
        # Make sure lost+found exists and is preallocated.
        lf_result = self.lost_found.mklost_found()
        # Add lost+found as a dirent of the root directory.
        root = self._inodes[self.root_ino]
        if root.find_dirent(LOST_FOUND_NAME) is None:
            lf_inode = self.allocate_inode(
                InodeType.DIRECTORY, mode_perm=0o700, data=[], nlinks=2,
            )
            root.add_dirent(LOST_FOUND_NAME, lf_inode.ino)
            root.nlinks += 1
        return {
            "partition":     self.name,
            "mount_point":   self.mount_point,
            "fs_type":       self.fs_type,
            "root_ino":      self.root_ino,
            "lost_found":    lf_result,
            "superblock":    self.superblock.to_dict(),
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _split_path(self, path: str) -> Tuple[str, str]:
        """Split ``/a/b/c`` into ``(/a/b, c)``."""
        if not path.startswith("/"):
            path = "/" + path
        path = path.rstrip("/")
        if path == "" or path == "/":
            return "/", ""
        idx = path.rfind("/")
        parent = path[:idx] if idx > 0 else "/"
        name = path[idx + 1:]
        return parent, name

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":            self.name,
            "mount_point":     self.mount_point,
            "fs_type":         self.fs_type,
            "block_size":      self.block_size,
            "superblock":      self.superblock.to_dict(),
            "lost_found":      self.lost_found.stats(),
            "inode_count":     len(self._inodes),
            "allocated_inodes": self.used_inode_count(),
            "used_blocks":     self.used_block_count(),
        }

    def __repr__(self) -> str:
        return (
            f"FilesystemPartition({self.name}@{self.mount_point}, "
            f"{self.fs_type}, inodes={len(self._inodes)})"
        )
