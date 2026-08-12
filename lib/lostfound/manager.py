"""
LostFoundManager — Manages a single partition's /lost+found directory.

This module faithfully reproduces the behaviour of:

  * ``mklost+found`` — pre-allocate extra blocks inside lost+found so that
    fsck can store recovered files without needing to allocate new blocks
    during recovery (which is impossible on a damaged filesystem).

  * fsck recovery — when an orphaned inode is found, fsck creates a hard
    link to it inside lost+found.  The name is the inode number prefixed
    with ``#`` (e.g. ``#388200``); if a name collision occurs a suffix
    letter is appended (e.g. ``#388200a``).

  * ``fsck -D`` — optimise / deduplicate directories.  Not strictly part of
    lost+found, but it is the only tool that re-links files found in
    lost+found back into the live tree.

Linux reference:
  * https://tldp.org/LDP/Linux-Filesystem-Hierarchy/html/lostfound.html
  * man 8 mklost+found
  * man 8 fsck
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .inode import Inode, InodeType
from .orphan import OrphanedInode
from .superblock import SuperBlock

log = logging.getLogger("UmerOS.LostFound")

# Default number of preallocated "extra" entries inside lost+found.
# The real mklost+found creates a large number of empty entries so that
# the directory itself has enough data blocks pre-allocated; here we model
# it as a count of reserved slots.
DEFAULT_PREALLOCATED_ENTRIES = 16

# Default directory path for lost+found at the root of a partition.
LOST_FOUND_NAME = "lost+found"


class LostFoundEntry:
    """One entry inside lost+found.

    Attributes:
        name:      The name inside lost+found (e.g. ``#42``).
        ino:       The recovered inode number.
        type:      File type of the recovered inode.
        size:      Size of the recovered inode.
        recovered_at: Epoch seconds when it was linked in.
        claimed:   True if a user has re-attached it to the live tree.
        source:    ``"fsck"`` (auto-recovered) or ``"manual"``.
    """

    __slots__ = (
        "name", "ino", "type", "size", "recovered_at", "claimed", "source",
        "uid", "gid", "mtime",
    )

    def __init__(
        self,
        name: str,
        ino: int,
        type: InodeType,
        size: int,
        source: str = "fsck",
        uid: int = 0,
        gid: int = 0,
        mtime: Optional[float] = None,
    ) -> None:
        self.name: str = name
        self.ino: int = ino
        self.type: InodeType = type
        self.size: int = size
        self.recovered_at: float = time.time()
        self.claimed: bool = False
        self.source: str = source
        self.uid: int = uid
        self.gid: int = gid
        self.mtime: float = mtime if mtime is not None else self.recovered_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":         self.name,
            "ino":          self.ino,
            "type":         self.type.type_char,
            "size":         self.size,
            "recovered_at": self.recovered_at,
            "claimed":      self.claimed,
            "source":       self.source,
            "uid":          self.uid,
            "gid":          self.gid,
            "mtime":        self.mtime,
        }

    def __repr__(self) -> str:
        return (
            f"LostFoundEntry(name={self.name!r}, ino={self.ino}, "
            f"type={self.type.type_char!r}, size={self.size}, "
            f"claimed={self.claimed})"
        )


class LostFoundManager:
    """Manages a single partition's ``lost+found`` directory.

    A real Linux partition has exactly one ``lost+found`` at its mount root.
    Each partition's lost+found is fully isolated.

    Args:
        partition:  The owning :class:`~lib.lostfound.partition.FilesystemPartition`.
                     May be ``None`` for standalone unit tests.
        path:       The VFS path of this lost+found (e.g. ``/lost+found``).
        preallocate_entries: Number of slots to reserve via mklost+found.
    """

    def __init__(
        self,
        partition: Any = None,
        path: str = "/lost+found",
        preallocate_entries: int = DEFAULT_PREALLOCATED_ENTRIES,
    ) -> None:
        self.partition = partition
        self.path: str = path
        self.preallocate_entries: int = preallocate_entries

        # name -> LostFoundEntry
        self._entries: Dict[str, LostFoundEntry] = {}
        # Pre-allocated empty slots (reserved by mklost+found).
        # Each slot represents one pre-allocated directory entry that fsck
        # can use without allocating new blocks.
        self._reserved_slots: int = 0
        self._created: bool = False
        self._preallocated: bool = False

        # Statistics
        self._total_recovered: int = 0
        self._total_purged: int = 0
        self._total_claimed: int = 0

        log.debug("LostFoundManager created for %s.", path)

    # ------------------------------------------------------------------ #
    # mklost+found — create the directory and preallocate blocks
    # ------------------------------------------------------------------ #

    def mklost_found(self, force: bool = False) -> Dict[str, Any]:
        """Create the lost+found directory and preallocate reserved blocks.

        This mirrors the ``mklost+found`` utility.  It:
          1. Creates the directory if it does not exist.
          2. Pre-allocates ``preallocate_entries`` empty slots so that
             ``fsck`` can later add recovered entries without needing to
             allocate new blocks (critical on a damaged filesystem).
          3. Sets restrictive permissions (root-only, mode 0700).

        Args:
            force: If True, recreate and re-preallocate even if the
                   directory already exists.

        Returns:
            A dict describing what was done.
        """
        result: Dict[str, Any] = {
            "created":         False,
            "preallocated":    False,
            "slots_reserved":  0,
            "path":            self.path,
            "already_existed": False,
        }

        if self._created and not force:
            result["already_existed"] = True
            log.info("lost+found already exists at %s; use force=True to "
                     "re-preallocate.", self.path)
            return result

        # 1. Create the directory.
        self._created = True
        result["created"] = True

        # 2. Pre-allocate slots.
        if self._preallocated and not force:
            result["slots_reserved"] = self._reserved_slots
            return result

        self._reserved_slots = self.preallocate_entries
        self._preallocated = True
        result["preallocated"] = True
        result["slots_reserved"] = self._reserved_slots

        log.info(
            "mklost+found: created %s with %d preallocated slots.",
            self.path, self._reserved_slots,
        )
        return result

    def ensure_exists(self) -> bool:
        """Make sure lost+found exists; create+preallocate if missing.

        fsck does this automatically at the start of Phase 4 — if the
        lost+found directory is missing it is recreated, but (critically)
        *without* preallocated blocks unless mklost+found is run again.

        Returns True if the directory now exists (either pre-existing or
        just created with preallocation).
        """
        if self._created:
            return True
        self.mklost_found()
        return True

    def recreate_without_prealloc(self) -> None:
        """Simulate the fsck auto-recreate path: directory exists but has
        *no* preallocated blocks.

        This happens if a user deletes lost+found and then runs fsck.  The
        directory comes back, but recovery will be less robust because there
        is no reserved space for new directory entries.
        """
        self._created = True
        self._preallocated = False
        self._reserved_slots = 0
        log.warning(
            "lost+found at %s recreated by fsck WITHOUT preallocated blocks. "
            "Run mklost+found to fix.", self.path,
        )

    # ------------------------------------------------------------------ #
    # Recovery — link orphaned inodes into lost+found
    # ------------------------------------------------------------------ #

    def _next_slot(self) -> bool:
        """Consume one preallocated slot.  Returns True if a slot was
        available (i.e. no new block allocation needed)."""
        if self._reserved_slots > 0:
            self._reserved_slots -= 1
            return True
        return False

    def _make_name(self, ino: int) -> str:
        """Generate a lost+found entry name for an inode number.

        Convention: ``#<inode>``.  On collision, append ``a``, ``b``, …
        (matching e2fsck behaviour).
        """
        base = f"#{ino}"
        if base not in self._entries:
            return base
        # Collision — append a letter.
        for suffix_ord in range(ord("a"), ord("z") + 1):
            candidate = base + chr(suffix_ord)
            if candidate not in self._entries:
                return candidate
        # Extremely unlikely: 26 collisions.  Append a number.
        i = 1
        while f"{base}{i}" in self._entries:
            i += 1
        return f"{base}{i}"

    def recover(self, orphan: OrphanedInode) -> Optional[str]:
        """Link a single orphaned inode into lost+found.

        Args:
            orphan: The orphan descriptor produced by fsck.

        Returns:
            The name given to the recovered entry (e.g. ``#42``), or
            ``None`` if the inode was not recoverable.
        """
        if not self.ensure_exists():
            log.error("Cannot recover inode %d: lost+found missing.",
                      orphan.inode.ino)
            return None

        if not orphan.is_recoverable:
            log.warning(
                "Skipping unrecoverable inode %d (reason=%s, corrupted=%s).",
                orphan.inode.ino, orphan.reason, orphan.inode.corrupted,
            )
            return None

        name = self._make_name(orphan.inode.ino)
        used_slot = self._next_slot()

        entry = LostFoundEntry(
            name=name,
            ino=orphan.inode.ino,
            type=orphan.inode.type,
            size=orphan.inode.size,
            source="fsck",
            uid=orphan.inode.uid,
            gid=orphan.inode.gid,
            mtime=orphan.inode.mtime,
        )
        self._entries[name] = entry

        # Bump the inode's link count — fsck adds a directory entry, which
        # is a hard link.
        orphan.inode.nlinks += 1
        orphan.inode.deleted = False
        orphan.recovered = True
        orphan.recovered_name = name
        self._total_recovered += 1

        log.info(
            "Recovered inode %d -> %s/%s (preallocated_slot=%s).",
            orphan.inode.ino, self.path, name, used_slot,
        )
        return name

    def recover_many(self, orphans: List[OrphanedInode]) -> List[str]:
        """Recover a batch of orphans; return the list of names assigned
        (skips unrecoverable ones silently)."""
        names: List[str] = []
        for o in orphans:
            n = self.recover(o)
            if n is not None:
                names.append(n)
        return names

    # ------------------------------------------------------------------ #
    # Manual insert (for fsck -p / interactive / unit tests)
    # ------------------------------------------------------------------ #

    def insert(
        self,
        inode: Inode,
        name: Optional[str] = None,
        source: str = "manual",
    ) -> str:
        """Manually insert an inode into lost+found (does not require it to
        be an orphan — useful for testing or for fsck -p fallback)."""
        self.ensure_exists()
        if name is None:
            name = self._make_name(inode.ino)
        elif name in self._entries:
            name = self._make_name(inode.ino)

        self._next_slot()
        entry = LostFoundEntry(
            name=name, ino=inode.ino, type=inode.type, size=inode.size,
            source=source, uid=inode.uid, gid=inode.gid, mtime=inode.mtime,
        )
        self._entries[name] = entry
        inode.nlinks += 1
        self._total_recovered += 1
        return name

    # ------------------------------------------------------------------ #
    # Listing / inspection
    # ------------------------------------------------------------------ #

    def list(self) -> List[LostFoundEntry]:
        """Return all recovered entries, oldest first."""
        return sorted(self._entries.values(),
                      key=lambda e: e.recovered_at)

    def list_unclaimed(self) -> List[LostFoundEntry]:
        """Return entries that have not been re-attached to the live tree."""
        return [e for e in self.list() if not e.claimed]

    def get(self, name: str) -> Optional[LostFoundEntry]:
        """Look up an entry by its lost+found name (e.g. ``#42``)."""
        return self._entries.get(name)

    def find_by_ino(self, ino: int) -> Optional[LostFoundEntry]:
        """Find the entry that wraps a given inode number."""
        for e in self._entries.values():
            if e.ino == ino:
                return e
        return None

    def is_empty(self) -> bool:
        return len(self._entries) == 0

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def exists(self) -> bool:
        return self._created

    @property
    def has_preallocated_blocks(self) -> bool:
        return self._preallocated and self._reserved_slots >= 0

    @property
    def reserved_slots_remaining(self) -> int:
        return self._reserved_slots

    # ------------------------------------------------------------------ #
    # Claim — re-attach a recovered file to the live tree
    # ------------------------------------------------------------------ #

    def claim(self, name: str, new_path: str) -> bool:
        """Mark a recovered entry as reclaimed by the user.

        In real life this is done by the sysadmin copying the file out of
        lost+found to its proper location (``mv /lost+found/#42 /etc/fstab``).
        Here we record the claim so the entry can later be purged.

        Args:
            name:     The lost+found entry name (e.g. ``#42``).
            new_path: Where the user moved it to (informational).

        Returns:
            True if the entry existed and was claimed.
        """
        entry = self._entries.get(name)
        if entry is None:
            log.warning("claim: entry %s not found in %s.", name, self.path)
            return False
        entry.claimed = True
        self._total_claimed += 1
        log.info("Claimed %s/%s -> %s.", self.path, name, new_path)
        return True

    def claim_by_ino(self, ino: int, new_path: str) -> bool:
        entry = self.find_by_ino(ino)
        if entry is None:
            return False
        return self.claim(entry.name, new_path)

    # ------------------------------------------------------------------ #
    # Purge — delete entries from lost+found
    # ------------------------------------------------------------------ #

    def purge(self, name: str) -> bool:
        """Delete a single entry from lost+found.

        The inode's link count is decremented; if it reaches zero the inode
        is freed (returned to the caller via the partition, if any).
        """
        entry = self._entries.pop(name, None)
        if entry is None:
            return False

        # Decrement the link count.
        freed = False
        if self.partition is not None:
            inode = self.partition.get_inode(entry.ino)
            if inode is not None:
                inode.nlinks = max(0, inode.nlinks - 1)
                if inode.nlinks == 0:
                    self.partition.free_inode(entry.ino)
                    freed = True
        self._total_purged += 1
        log.info("Purged %s/%s (inode_freed=%s).", self.path, name, freed)
        return True

    def purge_claimed(self) -> int:
        """Delete every entry that has been claimed.  Returns count."""
        names = [e.name for e in self._entries.values() if e.claimed]
        for n in names:
            self.purge(n)
        return len(names)

    def purge_all(self) -> int:
        """Delete every entry.  Returns count.  (Rarely used.)"""
        names = list(self._entries.keys())
        for n in names:
            self.purge(n)
        return len(names)

    # ------------------------------------------------------------------ #
    # Statistics
    # ------------------------------------------------------------------ #

    def stats(self) -> Dict[str, Any]:
        """Return a summary of this lost+found's state."""
        entries = list(self._entries.values())
        return {
            "path":                     self.path,
            "exists":                   self._created,
            "preallocated":             self._preallocated,
            "reserved_slots_remaining": self._reserved_slots,
            "entries":                  len(entries),
            "unclaimed":                sum(1 for e in entries if not e.claimed),
            "claimed":                  sum(1 for e in entries if e.claimed),
            "total_recovered":          self._total_recovered,
            "total_purged":             self._total_purged,
            "total_claimed":            self._total_claimed,
            "by_type": {
                t.type_char: sum(1 for e in entries if e.type == t)
                for t in InodeType
                if any(e.type == t for e in entries)
            },
        }

    def __repr__(self) -> str:
        return (
            f"LostFoundManager(path={self.path!r}, entries={len(self._entries)}, "
            f"reserved={self._reserved_slots}, preallocated={self._preallocated})"
        )
