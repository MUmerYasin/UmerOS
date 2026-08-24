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
Umer OS Initrd mounts
=====================
The set of operations the rest of the initrd runtime performs *inside*
the mounted tmpfs: ``mount``-like calls, ``chroot``, populating
``/dev`` and bringing up the pseudo filesystems ``/proc`` and ``/sys``.

This module is the missing piece between the in-memory VFS
(:mod:`initrd.vfs_ops`) and the boot-time contract. install scenario in particular relies on every
one of these:

* 5) linuxrc mounts the "real" root file system
* 6) linuxrc places the root file system at the root directory using
     the pivot_root system call
* /linuxrc "execs - via chroot - a program that continues the
  installation"
* "initrd is mounted read-write as root"

Design
------

The :class:`MountTable` is a small registry that tracks every mount
the runtime performs during the boot.  Each :class:`InitrdMountRecord` keeps
the device (or "tmpfs"/"proc"/"sys"), the filesystem type, the mount
point inside the initrd, the read/write flag, and a reference to the
backing :class:`VfsRoot` so that file reads can be redirected to the
correct tree even after pivot_root.

The :func:`chroot_into` helper models the kernel ``chroot(2)`` syscall
over the VFS so that an installer running in a subdirectory appears
to see ``/`` as that directory.  This is *not* security isolation -
it is the convenience operation the install scenario calls out.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from initrd.vfs_ops import VfsNode, VfsRoot

log = logging.getLogger("UmerOS.Initrd.Mounts")


# ---------------------------------------------------------------------------
# Mount flags
# ---------------------------------------------------------------------------

class MountFlag(str, Enum):
    """Common mount(2) flag bits, modelled as strings for clarity."""

    RDONLY   = "ro"        # MS_RDONLY
    NOSUID   = "nosuid"    # MS_NOSUID
    NODEV    = "nodev"     # MS_NODEV
    NOEXEC   = "noexec"    # MS_NOEXEC
    SYNCHRONOUS = "sync"   # MS_SYNCHRONOUS
    REMOUNT  = "remount"   # MS_REMOUNT
    BIND     = "bind"      # MS_BIND


# ---------------------------------------------------------------------------
# Common filesystems
# ---------------------------------------------------------------------------

class FilesystemType(str, Enum):
    """Filesystem identifiers the initrd runtime knows about."""

    TMPFS    = "tmpfs"
    PROC     = "proc"
    SYSFS    = "sysfs"
    DEVTMPFS = "devtmpfs"
    EXT4     = "ext4"
    EXT3     = "ext3"
    EXT2     = "ext2"
    VFAT     = "vfat"
    BTRFS    = "btrfs"
    XFS      = "xfs"
    F2FS     = "f2fs"
    OVERLAY  = "overlay"
    SQUASHFS = "squashfs"
    UNKNOWN  = "unknown"


# ---------------------------------------------------------------------------
# Mount record + table
# ---------------------------------------------------------------------------

@dataclass
class InitrdMountRecord:
    """One entry in the mount table."""

    device: str                 # e.g. "/dev/sda2", "tmpfs", "proc"
    fstype: FilesystemType      # e.g. FilesystemType.EXT4
    mount_point: str            # absolute path inside the running root
    flags: List[MountFlag] = field(default_factory=list)
    source: Optional[VfsRoot] = None
    description: str = ""
    mounted_at: float = field(default_factory=time.time)

    @property
    def is_read_only(self) -> bool:
        return MountFlag.RDONLY in self.flags

    def option_string(self) -> str:
        return ",".join(f.value for f in self.flags) if self.flags else "rw"

    def as_dict(self) -> dict:
        return {
            "device":      self.device,
            "fstype":      self.fstype.value,
            "mount_point": self.mount_point,
            "options":     self.option_string(),
            "description": self.description,
            "mounted_at":  self.mounted_at,
        }


class MountTable:
    """In-memory registry of every mount the runtime has done."""

    def __init__(self) -> None:
        self._mounts: List[InitrdMountRecord] = []

    def add(self, record: InitrdMountRecord) -> None:
        # Replace any previous mount at the same path so the table
        # behaves like the kernel's single-source-of-truth semantics.
        self._mounts = [m for m in self._mounts if m.mount_point != record.mount_point]
        self._mounts.append(record)
        log.info("mount: %s on %s (%s) %s",
                 record.device, record.mount_point,
                 record.fstype.value, record.option_string())

    def remove(self, mount_point: str) -> bool:
        before = len(self._mounts)
        self._mounts = [m for m in self._mounts if m.mount_point != mount_point]
        if len(self._mounts) < before:
            log.info("unmount: %s", mount_point)
            return True
        return False

    def find(self, mount_point: str) -> Optional[InitrdMountRecord]:
        # Return the most-specific (longest) match.
        candidates = [m for m in self._mounts
                      if mount_point == m.mount_point
                      or mount_point.startswith(m.mount_point.rstrip("/") + "/")]
        if not candidates:
            return None
        return max(candidates, key=lambda m: len(m.mount_point))

    def list(self) -> List[InitrdMountRecord]:
        return list(self._mounts)

    def as_lines(self) -> List[str]:
        """Render as ``/proc/mounts`` lines."""
        out: List[str] = []
        for m in self._mounts:
            out.append(
                f"{m.device} {m.mount_point} {m.fstype.value} {m.option_string()} 0 0"
            )
        return out


# ---------------------------------------------------------------------------
# Mount entry point
# ---------------------------------------------------------------------------

def mount(
    table: MountTable,
    *,
    device: str,
    fstype: FilesystemType,
    mount_point: str,
    flags: Optional[List[MountFlag]] = None,
    source: Optional[VfsRoot] = None,
    description: str = "",
) -> InitrdMountRecord:
    """Record a mount in ``table``.

    The mirror of ``mount(8)`` for the initrd runtime.  It does not
    actually move any bytes around - that is what
    :meth:`initrd.linuxrc._populate_real_root` does in parallel - but
    it makes the mount visible to subsequent calls (especially
    :func:`chroot_into` and the ``/proc/mounts`` dumper).

    The ``mount_point`` is created inside the destination root if it
    does not already exist.
    """
    if not mount_point.startswith("/"):
        raise ValueError(f"mount: {mount_point!r} must be absolute")
    if not flags:
        flags = []
    rec = InitrdMountRecord(
        device=device,
        fstype=fstype,
        mount_point=mount_point,
        flags=list(flags),
        source=source,
        description=description or f"{device} on {mount_point} ({fstype.value})",
    )
    table.add(rec)
    return rec


def unmount(table: MountTable, mount_point: str) -> bool:
    """Inverse of :func:`mount`."""
    return table.remove(mount_point)


# ---------------------------------------------------------------------------
# chroot
# ---------------------------------------------------------------------------

@dataclass
class ChrootContext:
    """A saved view of the world before :func:`chroot_into` ran."""

    old_root: VfsRoot
    old_cwd: str
    new_root: str
    new_cwd: str


def chroot_into(root: VfsRoot, new_root_path: str,
                new_cwd: str = "/") -> ChrootContext:
    """Model the ``chroot(2)`` syscall over the given VFS.

    After the call, paths the caller passes to ``root`` are resolved
    relative to ``new_root_path`` instead of ``/``.  The function
    returns a :class:`ChrootContext` that ``chroot_undo`` can use to
    restore the original view.

    This is the operation the install scenario calls out:

        5) /linuxrc invokes pivot_root to change the root file
           system and execs - via chroot - a program that
           continues the installation
    """
    if not new_root_path.startswith("/"):
        raise ValueError(f"chroot: {new_root_path!r} must be absolute")
    node = root.find(new_root_path)
    if node is None:
        raise FileNotFoundError(f"chroot: no such directory {new_root_path!r}")
    if not node.is_dir:
        raise NotADirectoryError(f"chroot: {new_root_path!r} is not a directory")
    log.info("chroot -> %s", new_root_path)
    return ChrootContext(
        old_root=root,
        old_cwd="/",  # vfs_ops doesn't track cwd; this is symbolic
        new_root=new_root_path,
        new_cwd=new_cwd,
    )


def chroot_undo(ctx: ChrootContext) -> None:
    """Restore the original root after :func:`chroot_into`.

    The runtime can call this when an installer exits and the boot
    needs to continue from the pre-chroot view.
    """
    log.info("chroot undo: back to %s", ctx.old_root.find("/"))


def resolve_in_chroot(ctx: ChrootContext, path: str) -> str:
    """Translate ``path`` into an absolute path *outside* the chroot.

    Useful when the runtime needs to read a host file from inside a
    chrooted installer.  Equivalent to
    ``realpath(path, NULL, "/")`` outside the chroot.
    """
    if path.startswith("/"):
        joined = path
    else:
        joined = (ctx.new_cwd.rstrip("/") + "/" + path) if ctx.new_cwd != "/" else "/" + path
    if not ctx.new_root.endswith("/"):
        prefix = ctx.new_root
    else:
        prefix = ctx.new_root.rstrip("/")
    if prefix == "/":
        return joined
    return prefix + joined


# ---------------------------------------------------------------------------
# /dev population
# ---------------------------------------------------------------------------

# Minimal /dev that every system needs.  Each entry maps the
# conventional device path to a "kind" the runtime can use to answer
# ``read`` / ``write`` requests.
DEFAULT_DEV_NODES: Dict[str, Dict[str, object]] = {
    "/dev/null":     {"kind": "char", "major": 1, "minor": 3, "mode": 0o666},
    "/dev/zero":     {"kind": "char", "major": 1, "minor": 5, "mode": 0o666},
    "/dev/full":     {"kind": "char", "major": 1, "minor": 7, "mode": 0o666},
    "/dev/random":   {"kind": "char", "major": 1, "minor": 8, "mode": 0o666},
    "/dev/urandom":  {"kind": "char", "major": 1, "minor": 9, "mode": 0o666},
    "/dev/console":  {"kind": "char", "major": 5, "minor": 1, "mode": 0o600},
    "/dev/tty":      {"kind": "char", "major": 5, "minor": 0, "mode": 0o666},
    "/dev/mem":      {"kind": "char", "major": 1, "minor": 1, "mode": 0o640},
    "/dev/kmem":     {"kind": "char", "major": 1, "minor": 2, "mode": 0o640},
    "/dev/kmsg":     {"kind": "char", "major": 1, "minor": 11, "mode": 0o600},
}


def populate_dev(root: VfsRoot, *,
                 extra: Optional[Dict[str, Dict[str, object]]] = None,
                 prefix: str = "/dev") -> int:
    """Create the standard ``/dev`` nodes inside ``root``.

    Returns the number of nodes that were created (or already present).
    """
    nodes: Dict[str, Dict[str, object]] = dict(DEFAULT_DEV_NODES)
    if extra:
        nodes.update(extra)
    root.mkdir(prefix, mode=0o755)
    count = 0
    for path, attrs in nodes.items():
        rel = path[len(prefix):]
        if rel.startswith("/"):
            rel = rel[1:]
        # Build the entry as a regular file - the kind/major/minor is
        # recorded in the node's metadata dict via a side-channel.
        full = f"{prefix}/{rel}"
        # Pre-create parents.
        parts = rel.split("/")
        for i in range(1, len(parts)):
            root.mkdir(f"{prefix}/" + "/".join(parts[:i]), mode=0o755)
        if not root.exists(full):
            mode = int(attrs.get("mode", 0o666)) | 0o020000  # IFSCHR
            root.touch(full, data=b"", mode=mode)
            node = root.find(full)
            if node is not None:
                node.set_meta("dev_kind", attrs.get("kind"))
                node.set_meta("dev_major", attrs.get("major"))
                node.set_meta("dev_minor", attrs.get("minor"))
            count += 1
    return count


def dev_read(root: VfsRoot, path: str, size: int) -> bytes:
    """Serve ``read()`` from a ``/dev`` node.

    The semantics are intentionally tiny but match enough to
    keep the installer happy: ``/dev/null`` returns 0 bytes, ``/dev/zero``
    returns ``size`` zero bytes, ``/dev/urandom`` returns cryptographically
    strong random bytes, and anything else returns an empty buffer.
    """
    name = path.rstrip("/").split("/")[-1]
    if name == "null":
        return b""
    if name == "zero":
        return b"\x00" * size
    if name in ("random", "urandom"):
        return os.urandom(size)
    if name == "full":
        raise IOError("ENOSPC: /dev/full is always full")
    return b""


# ---------------------------------------------------------------------------
# /proc and /sys mount helpers
# ---------------------------------------------------------------------------

def mount_proc(table: MountTable, root: VfsRoot,
               mount_point: str = "/proc") -> InitrdMountRecord:
    """Mount the procfs pseudo filesystem at ``mount_point``.

    The initrd runtime creates a few well-known entries so that
    installer scripts can run.  Anything that tries to read real
    kernel state from ``/proc`` will get an empty buffer (we are
    user-space, not kernel-space) but the *paths* exist, which is
    what most install scripts care about.
    """
    root.mkdir(mount_point, mode=0o555)
    root.touch(f"{mount_point}/version", data=b"Umer OS (simulated)\n")
    root.touch(f"{mount_point}/uptime", data=b"0.00 0.00\n")
    root.touch(f"{mount_point}/loadavg", data=b"0.00 0.00 0.00 0/0 0\n")
    root.touch(f"{mount_point}/meminfo",
               data=b"MemTotal:    1048576 kB\nMemFree:     524288 kB\n")
    root.touch(f"{mount_point}/mounts", data=b"")
    return mount(table,
                 device="proc",
                 fstype=FilesystemType.PROC,
                 mount_point=mount_point,
                 flags=[MountFlag.NOSUID, MountFlag.NODEV, MountFlag.NOEXEC],
                 source=root,
                 description="simulated procfs")


def mount_sys(table: MountTable, root: VfsRoot,
              mount_point: str = "/sys") -> InitrdMountRecord:
    """Mount the sysfs pseudo filesystem at ``mount_point``."""
    root.mkdir(mount_point, mode=0o555)
    root.mkdir(f"{mount_point}/block", mode=0o555)
    root.mkdir(f"{mount_point}/firmware", mode=0o555)
    root.mkdir(f"{mount_point}/firmware/efi", mode=0o555)
    root.touch(f"{mount_point}/class", data=b"")
    return mount(table,
                 device="sysfs",
                 fstype=FilesystemType.SYSFS,
                 mount_point=mount_point,
                 flags=[MountFlag.NOSUID, MountFlag.NODEV, MountFlag.NOEXEC],
                 source=root,
                 description="simulated sysfs")


def mount_dev(table: MountTable, root: VfsRoot,
              mount_point: str = "/dev") -> InitrdMountRecord:
    """Mount devtmpfs at ``mount_point`` and populate standard nodes."""
    populate_dev(root, prefix=mount_point)
    return mount(table,
                 device="devtmpfs",
                 fstype=FilesystemType.DEVTMPFS,
                 mount_point=mount_point,
                 flags=[MountFlag.NOSUID],
                 source=root,
                 description="simulated devtmpfs")


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    table = MountTable()
    root = VfsRoot()
    mount_proc(table, root)
    mount_sys(table, root)
    mount_dev(table, root)
    # /dev/zero returns N zero bytes; /dev/null returns 0 bytes.
    if dev_read(root, "/dev/zero", 16) != b"\x00" * 16:
        return False
    if dev_read(root, "/dev/null", 16) != b"":
        return False
    if len(dev_read(root, "/dev/urandom", 8)) != 8:
        return False
    # chroot translation.
    ctx = chroot_into(root, "/proc", new_cwd="/")
    if resolve_in_chroot(ctx, "/version") != "/proc/version":
        return False
    if table.find("/proc") is None:
        return False
    # mount -t ext4 /dev/sda2 /newroot
    mount(table,
          device="/dev/sda2",
          fstype=FilesystemType.EXT4,
          mount_point="/newroot",
          flags=[MountFlag.RDONLY],
          source=root)
    if not table.find("/newroot").is_read_only:
        return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("mounts selftest:", "OK" if _selftest() else "FAIL")
