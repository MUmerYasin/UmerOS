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
OrphanedInode — A descriptor for an inode discovered by fsck that has data
but is not referenced by any directory entry.

In a real ext4 filesystem, fsck Phase 3 walks the inode table and compares
each allocated inode against the set of inodes referenced by directory
entries.  Any allocated inode that has no directory reference is an
"orphan" and is queued for recovery into /lost+found.

Reference: ``e2fsck`` pass 3 (``pass3.c`` in e2fsprogs).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .inode import Inode, InodeType


class OrphanedInode:
    """A wrapper that records *why* an inode was flagged as an orphan
    and the metadata fsck needs to recover it.

    Attributes:
        inode:        The orphaned :class:`Inode`.
        reason:       Short string describing why it is an orphan
                      (``"no_dirent_ref"``, ``"nlinks_zero"``,
                      ``"deleted_but_allocated"``, ``"corrupted_skipped"``).
        discovered_at:Epoch seconds when fsck found it.
        recovered:    True once fsck has linked it into lost+found.
        recovered_name: The name it was given inside lost+found (e.g. ``#42``).
    """

    REASON_NO_DIRENT          = "no_dirent_ref"
    REASON_NLINKS_ZERO        = "nlinks_zero"
    REASON_DELETED_ALLOCATED  = "deleted_but_allocated"
    REASON_CORRUPTED          = "corrupted_skipped"

    def __init__(self, inode: Inode, reason: str = REASON_NO_DIRENT) -> None:
        self.inode: Inode = inode
        self.reason: str = reason
        self.recovered: bool = False
        self.recovered_name: Optional[str] = None
        import time as _t
        self.discovered_at: float = _t.time()

    @property
    def is_recoverable(self) -> bool:
        """Corrupted inodes cannot be safely recovered."""
        return self.reason != self.REASON_CORRUPTED and not self.inode.corrupted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ino":            self.inode.ino,
            "type":           self.inode.type.type_char,
            "size":           self.inode.size,
            "reason":         self.reason,
            "recoverable":    self.is_recoverable,
            "recovered":      self.recovered,
            "recovered_name": self.recovered_name,
            "discovered_at":  self.discovered_at,
        }

    def __repr__(self) -> str:
        return (
            f"OrphanedInode(ino={self.inode.ino}, reason={self.reason!r}, "
            f"recoverable={self.is_recoverable})"
        )
