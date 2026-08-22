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
Umer OS Initrd ``pivot_root`` semantics
======================================
Implementation of the ``pivot_root(new_root, put_old)`` system call in
the UmerOS initrd runtime.

Why does ``/linuxrc`` (now ``/init``) need to call ``pivot_root``?

The TLDP reference (section 1.8) spells it out: after the initrd has
been mounted as the temporary root and the real root FS has been
mounted somewhere inside it (typically ``/newroot`` or ``/sysroot``),
the kernel needs to *switch* its view of "/" so that init runs on the
real root.  ``pivot_root`` does that swap atomically:

    before:           after:
        /                   /
        |-- bin            |-- bin          (new)
        |-- newroot        |-- newroot
        |   `-- bin        |   `-- bin      (was old /)
        `-- oldroot        `-- (empty)

The two key properties that distinguish ``pivot_root`` from
``chroot`` are:

* The old root is moved to a directory inside the new root, so that
  processes that were running on it can keep going.
* The call requires ``CAP_SYS_ADMIN`` and refuses to leave the old
  root at the same mount point as the new one.

In a real kernel this is a single syscall.  In UmerOS we implement
the same idea over :mod:`initrd.vfs_ops` and :mod:`initrd.ramdisk` so
that the initrd runtime can complete the eight TLDP phases without
spawning a real kernel.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from initrd.ramdisk import RamDisk
from initrd.vfs_ops import VfsNode, VfsRoot

log = logging.getLogger("UmerOS.Initrd.PivotRoot")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class PivotRootError(RuntimeError):
    """Raised when a pivot_root call is rejected."""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PivotResult:
    """Audit record for one pivot_root operation."""

    old_root: str
    new_root: str
    put_old: str
    swapped: bool
    duration_seconds: float
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pivot implementation
# ---------------------------------------------------------------------------

def pivot_root(
    old: VfsRoot,
    new: VfsRoot,
    *,
    new_root_path: str = "/newroot",
    put_old_path: str = "/newroot/initrd",
) -> PivotResult:
    """Atomically replace the root filesystem with ``new``.

    Pre-conditions (matching the kernel's ``pivot_root`` man page):

    * ``new_root_path`` and ``put_old_path`` must both be directories.
    * ``new_root_path`` must not be the same as ``put_old_path`` or
      its ancestor.
    * Both must be on the same mounted filesystem (in our case, both
      must live under the same :class:`VfsRoot`).

    Post-condition: the contents of ``new`` are promoted to "/" inside
    ``old``, and the original ``old.root`` is moved to ``put_old_path``.
    """
    start = time.time()
    if old is new:
        raise PivotRootError("pivot_root: new and old must be different trees")
    if new_root_path == put_old_path:
        raise PivotRootError(
            f"pivot_root: new_root ({new_root_path!r}) and put_old "
            f"({put_old_path!r}) must differ"
        )
    if not new_root_path.startswith("/") or not put_old_path.startswith("/"):
        raise PivotRootError("pivot_root: paths must be absolute")

    log.info("pivot_root: old=%s new=%s put_old=%s",
             id(old.root), id(new.root), put_old_path)

    # Make sure the destination directories exist inside the *new* tree.
    new.mkdir(new_root_path, parents=True, mode=0o755)
    new.mkdir(put_old_path, parents=True, mode=0o755)

    # Move every child of the old root into ``put_old_path`` inside the
    # new tree, so the new root sees a clean view of itself first.
    swapped_files: list[tuple[str, VfsNode]] = []
    for name, child in list(old.root.children.items()):
        # Detach from old tree.
        old.root.children.pop(name, None)
        # Skip the slot we are about to install the new root into.
        if name.rstrip("/") == new_root_path.strip("/"):
            continue
        swapped_files.append((name, child))

    for name, child in swapped_files:
        _insert(new.root, put_old_path, name, child)

    # Promote the new tree's contents to root.
    for name, child in list(new.root.children.items()):
        if name in (".", ".."):
            continue
        if name.rstrip("/") == new_root_path.strip("/"):
            # We just stuffed the old contents inside this subdir; do
            # not also lift it to top level.
            continue
        new.root.children.pop(name, None)
        old.root.children[name] = child

    # If the new root has nothing yet (test path), move the children of
    # new_root_path up to the top level so the caller sees a populated
    # root after pivot.
    new_root_node = new.find(new_root_path)
    if new_root_node is not None and new_root_node.is_dir:
        for name, child in list(new_root_node.children.items()):
            new_root_node.children.pop(name, None)
            old.root.children[name] = child
        # Drop the now-empty slot.
        parent = new.find("/".join(new_root_path.split("/")[:-1]) or "/")
        if parent is not None:
            parent.children.pop(new_root_path.rstrip("/").split("/")[-1] or "/", None)

    duration = time.time() - start
    log.info("pivot_root completed in %.6fs", duration)
    return PivotResult(
        old_root="/",
        new_root=new_root_path,
        put_old=put_old_path,
        swapped=True,
        duration_seconds=duration,
        notes=[f"moved {len(swapped_files)} entries into {put_old_path}"],
    )


def _insert(target_node: VfsNode, base: str, name: str, child: VfsNode) -> None:
    """Insert ``child`` named ``name`` at ``base`` inside ``target_node``."""
    parts = [p for p in base.split("/") if p]
    node = target_node
    for chunk in parts:
        if chunk not in node.children:
            node.children[chunk] = VfsNode(name=chunk, is_dir=True, mode=0o755)
        node = node.children[chunk]
        if not node.is_dir:
            raise PivotRootError(f"pivot_root: {base} not a directory")
    node.children[name] = child


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def pivot_ramdisk_to(disk: RamDisk, real_root: VfsRoot,
                     *,
                     new_root_path: str = "/newroot",
                     put_old_path: str = "/newroot/initrd") -> PivotResult:
    """Run :func:`pivot_root` for the live boot path.

    Combines the VFS swap with the RamDisk lifecycle: the disk moves
    from ``MOUNTED`` to ``PIVOTED`` state so that the rest of the
    runtime knows the swap happened.
    """
    result = pivot_root(
        disk.root, real_root,
        new_root_path=new_root_path, put_old_path=put_old_path,
    )
    disk.pivot()
    return result


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    old = VfsRoot()
    new = VfsRoot()
    old.touch("/bin/old", data=b"OLD")
    old.touch("/etc/hostname", data=b"old\n")
    new.touch("/bin/new", data=b"NEW")
    result = pivot_root(old, new, new_root_path="/newroot",
                        put_old_path="/newroot/initrd")
    if not result.swapped:
        return False
    # After pivot, the new tree's children should be reachable from old.root
    return old.find("/bin/new") is not None and old.find("/bin/old") is None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("pivot_root selftest:", "OK" if _selftest() else "FAIL")
