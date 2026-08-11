"""
Umer OS Initrd RAM Disk
=======================
An in-memory filesystem that stands in for Linux's tmpfs/ramfs during
the early-userspace phase of the boot.

The real kernel unpacks a cpio archive straight into a tmpfs and frees
the original initrd memory before invoking ``/init``. We have no kernel
yet - everything is user-space Python - so this module is the closest
equivalent we can offer:

* A :class:`RamDisk` instance owns a :class:`~initrd.vfs_ops.VfsRoot`
  populated by a cpio archive (or built programmatically).
* :meth:`RamDisk.materialize_from_initrd` simulates the kernel
  "convert initrd into a normal RAM disk and free initrd memory" step.
* :meth:`RamDisk.teardown` simulates the final "initrd FS is removed"
  step (TLDP phase 8).

Mount point awareness: when the host kernel mounts a real tmpfs at
``/initrd`` we discover the underlying path via :func:`detect_mount`,
so that code running inside the RAM disk can still reach back to the
host when needed (e.g. writing the next-stage image back to ``/boot``).

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, Optional

from initrd.cpio import (
    CpioEntry,
    newc_dir,
    newc_file,
    newc_symlink,
    pack_archive,
    unpack_archive,
)
from initrd.mounts import MountTable
from initrd.vfs_ops import VfsRoot, VfsNode

log = logging.getLogger("UmerOS.Initrd.RamDisk")


# ---------------------------------------------------------------------------
# State machine for one disk
# ---------------------------------------------------------------------------

class RamDiskState(Enum):
    """Lifecycle of a single RAM disk.

    Mirrors the high-level steps from the TLDP ``/initrd`` reference:

    * ``PROBED``        - object exists but no payload yet
    * ``LOADED``        - raw initrd bytes are in memory
    * ``EXTRACTED``     - the kernel has "freed initrd memory" and the
                          archive has been unpacked into the working FS
    * ``MOUNTED``       - mounted as the running root
    * ``PIVOTED``       - pivot_root has switched away
    * ``RELEASED``      - all references dropped, memory reclaimed
    """

    PROBED    = "probed"
    LOADED    = "loaded"
    EXTRACTED = "extracted"
    MOUNTED   = "mounted"
    PIVOTED   = "pivoted"
    RELEASED  = "released"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@dataclass
class RamDiskStats:
    """Lightweight counters that tools and tests can read."""

    raw_bytes: int = 0
    extracted_bytes: int = 0
    file_count: int = 0
    dir_count: int = 0
    symlink_count: int = 0
    created_at: float = field(default_factory=time.time)
    extracted_at: float = 0.0
    mounted_at: float = 0.0
    pivoted_at: float = 0.0
    released_at: float = 0.0

    def as_dict(self) -> dict:
        return {
            "raw_bytes":       self.raw_bytes,
            "extracted_bytes": self.extracted_bytes,
            "file_count":      self.file_count,
            "dir_count":       self.dir_count,
            "symlink_count":   self.symlink_count,
            "uptime_seconds":  round(time.time() - self.created_at, 6),
        }


# ---------------------------------------------------------------------------
# RAM disk implementation
# ---------------------------------------------------------------------------

class RamDisk:
    """A user-space stand-in for a Linux tmpfs.

    The :class:`RamDisk` is intentionally minimal: it owns a
    :class:`VfsRoot` plus the lifecycle state machine.  It does not
    implement its own mount syscall - that's the host kernel's job -
    but it knows how to be "mounted" and "pivoted" via the helpers in
    :mod:`initrd.pivot_root`.
    """

    DEFAULT_MAX_BYTES = 512 * 1024 * 1024  # 512 MiB, matches qfs default

    def __init__(
        self,
        name: str = "initrd",
        max_bytes: int = DEFAULT_MAX_BYTES,
        mount_point: str = "/",
    ) -> None:
        self.name = name
        self.max_bytes = max_bytes
        self.mount_point = mount_point
        self.state = RamDiskState.PROBED
        self._raw: bytes = b""
        self.root = VfsRoot(name="/")
        self.stats = RamDiskStats()
        self.metadata: Dict[str, str] = {}
        #: Track every mount the runtime performs inside the initrd.
        self.mount_table = MountTable()
        #: Read/write flag for the root mount (TLDP phase 3).
        self.read_only: bool = False
        log.debug("RamDisk(%s) created, max=%d bytes", name, max_bytes)

    # -- sizing helpers ----------------------------------------------------

    @property
    def used_bytes(self) -> int:
        return self.stats.extracted_bytes

    @property
    def free_bytes(self) -> int:
        return max(0, self.max_bytes - self.used_bytes)

    # -- lifecycle ---------------------------------------------------------

    def load(self, blob: bytes) -> None:
        """Stage 1: read the raw cpio archive into memory (TLDP step 1-2).

        After this call the disk is :attr:`RamDiskState.LOADED`.
        """
        if not blob:
            raise ValueError("RamDisk.load: empty blob")
        if len(blob) > self.max_bytes:
            raise MemoryError(
                f"RamDisk.load: {len(blob)} bytes exceeds max {self.max_bytes}"
            )
        self._raw = blob
        self.stats.raw_bytes = len(blob)
        self.state = RamDiskState.LOADED
        log.info("RamDisk(%s) LOADED %d bytes", self.name, len(blob))

    def extract(self) -> int:
        """Stage 2: unpack the cpio archive into the working FS.

        Equivalent to "the kernel converts initrd into a normal RAM
        disk and frees initrd memory" (TLDP step 2-3).

        Returns the number of entries extracted.

        After this call the disk is :attr:`RamDiskState.EXTRACTED`.
        """
        if self.state != RamDiskState.LOADED:
            raise RuntimeError(
                f"RamDisk.extract requires LOADED state, got {self.state}"
            )
        entries = unpack_archive(self._raw)
        self._populate_from_entries(entries)
        # Free the raw cpio bytes - this is the part the kernel does
        # for us in real Linux.
        self._raw = b""
        self.stats.raw_bytes = 0
        self.stats.extracted_at = time.time()
        self.state = RamDiskState.EXTRACTED
        log.info(
            "RamDisk(%s) EXTRACTED %d entries, %d bytes",
            self.name, len(entries), self.stats.extracted_bytes,
        )
        return len(entries)

    def mount(self, mount_point: str = "/", *,
             read_only: bool = False) -> None:
        """Stage 3: bind the working FS to ``mount_point`` (TLDP step 3).

        In a real kernel this is the ``mount -t tmpfs`` call. Here we
        just record the state transition.  The TLDP reference is
        explicit that the initrd is mounted **read-write** as root,
        so :attr:`read_only` defaults to ``False`` and a warning is
        logged when the caller asks for RO mode.
        """
        if self.state not in (RamDiskState.EXTRACTED, RamDiskState.MOUNTED):
            raise RuntimeError(
                f"RamDisk.mount requires EXTRACTED state, got {self.state}"
            )
        self.mount_point = mount_point
        self.read_only = read_only
        self.stats.mounted_at = time.time()
        self.state = RamDiskState.MOUNTED
        if read_only:
            log.warning("RamDisk(%s) MOUNTED READ-ONLY at %s (TLDP default is rw)",
                        self.name, mount_point)
        else:
            log.info("RamDisk(%s) MOUNTED (rw) at %s", self.name, mount_point)

    def pivot(self) -> None:
        """Stage 6: mark the disk as having been replaced by pivot_root."""
        if self.state != RamDiskState.MOUNTED:
            raise RuntimeError(
                f"RamDisk.pivot requires MOUNTED state, got {self.state}"
            )
        self.stats.pivoted_at = time.time()
        self.state = RamDiskState.PIVOTED
        log.info("RamDisk(%s) PIVOTED", self.name)

    def release(self) -> None:
        """Stage 8: drop everything (TLDP step 8)."""
        self.root = VfsRoot(name="/")
        self.stats.released_at = time.time()
        self.state = RamDiskState.RELEASED
        log.info("RamDisk(%s) RELEASED", self.name)

    # -- snapshot back to an image ---------------------------------------

    def snapshot_to_image(self) -> bytes:
        """Serialize the current RamDisk back to a cpio archive.

        This is the operation the TLDP install scenario calls out:

            7) ... the image is written from /dev/ram0 or
               /dev/rd/0 to a file

        In the host kernel this is ``dd if=/dev/ram0 of=initrd``.
        Here we walk the VFS in :attr:`root` and emit a new cpio
        archive that the caller can compress and write to disk.
        """
        if self.state in (RamDiskState.PROBED, RamDiskState.RELEASED):
            raise RuntimeError(
                f"RamDisk.snapshot_to_image requires an extracted disk, got {self.state}"
            )
        entries: list[CpioEntry] = []
        ino = 1
        # Walk the tree and emit one cpio entry per node.
        def _emit(path: str) -> None:
            nonlocal ino
            node = self.root.find(path)
            if node is None:
                return
            if node.is_dir:
                if path not in ("", "/"):
                    entries.append(newc_dir(path.lstrip("/"), mode=node.mode, ino=ino))
                    ino += 1
                for child in sorted(node.children):
                    child_path = path.rstrip("/") + "/" + child
                    _emit(child_path)
            elif node.is_symlink:
                entries.append(newc_symlink(path.lstrip("/"), node.symlink_target or "", ino=ino))
                ino += 1
            else:
                entries.append(newc_file(path.lstrip("/"), node.data, mode=node.mode, ino=ino))
                ino += 1
        _emit("/")
        return pack_archive(entries)

    def write_snapshot(self, path: str, *, archiver: str = "gzip",
                       level: int = 6) -> str:
        """Write :meth:`snapshot_to_image` to ``path`` via ``archiver``.

        Returns the path that was actually written.
        """
        from initrd.archivers import get_archiver
        raw = self.snapshot_to_image()
        compressor = get_archiver(archiver)
        out = compressor.compress(raw, level=level)
        Path(path).write_bytes(out)
        log.info("RamDisk(%s) snapshot written to %s (%d bytes, %s)",
                 self.name, path, len(out), compressor.__name__)
        return str(path)

    # -- direct content manipulation --------------------------------------

    def populate(self, entries: Iterable[CpioEntry]) -> None:
        """Replace the working FS content with ``entries``.

        Unlike :meth:`extract` this does not require a :attr:`LOADED`
        state - useful for synthetic tests and the build pipeline.
        """
        self._populate_from_entries(list(entries))
        self.state = RamDiskState.EXTRACTED
        self.stats.extracted_at = time.time()

    def add_file(self, path: str, data: bytes, mode: int = 0o644) -> None:
        """Add (or replace) a single file in the working FS."""
        node = self.root.touch(path, data=data, mode=mode)
        self.stats.extracted_bytes += len(data)
        if node.is_dir:
            self.stats.dir_count += 1
        else:
            self.stats.file_count += 1

    def add_directory(self, path: str, mode: int = 0o755) -> None:
        self.root.mkdir(path, mode=mode)
        self.stats.dir_count += 1

    def add_symlink(self, path: str, target: str) -> None:
        self.root.symlink(path, target)
        self.stats.symlink_count += 1

    # -- introspection ----------------------------------------------------

    def find(self, path: str) -> Optional[VfsNode]:
        return self.root.find(path)

    def listdir(self, path: str = "/") -> list:
        return self.root.listdir(path)

    def read(self, path: str) -> bytes:
        node = self.find(path)
        if node is None or node.is_dir:
            raise FileNotFoundError(path)
        return node.data

    # -- internals ---------------------------------------------------------

    def _populate_from_entries(self, entries: Iterable[CpioEntry]) -> None:
        """Insert ``entries`` into :attr:`root` and update the counters."""
        # Reset counters so this method is safe to call repeatedly.
        self.stats.extracted_bytes = 0
        self.stats.file_count = 0
        self.stats.dir_count = 0
        self.stats.symlink_count = 0
        for entry in entries:
            if entry.is_dir():
                # Strip the trailing "/" that cpio uses to mark dirs.
                clean = entry.name.rstrip("/")
                self.root.mkdir(clean or "/", mode=entry.mode & 0o777)
                self.stats.dir_count += 1
            elif entry.is_symlink():
                target = entry.target or ""
                self.root.symlink(entry.name, target)
                self.stats.symlink_count += 1
            elif entry.is_regular():
                self.root.touch(
                    entry.name, data=entry.data, mode=entry.mode & 0o777
                )
                self.stats.extracted_bytes += len(entry.data)
                self.stats.file_count += 1
            else:
                # Devices, FIFOs, sockets - record but skip content.
                log.debug("skipping non-regular cpio entry %r", entry.name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_mount(host_root: str = "/") -> Optional[Path]:
    """Return the host directory used as the initrd mount, if any.

    In the host OS, the real initrd shows up as a tmpfs entry in
    ``/proc/mounts`` with mount point ``/`` (during early boot) or
    ``/initrd`` (when left mounted). On systems where the procfs is
    not available we simply return ``None``.
    """
    mounts_file = Path(host_root) / "proc" / "mounts"
    if not mounts_file.is_file():
        return None
    try:
        text = mounts_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        device, mount_point, fstype = parts[0], parts[1], parts[2]
        if fstype in ("tmpfs", "ramfs") and mount_point in ("/", "/initrd"):
            log.debug("detected host initrd mount: %s on %s (%s)", device, mount_point, fstype)
            return Path(mount_point)
    return None


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Build, extract, mount, pivot, release - and assert each transition."""
    from initrd.cpio import newc_dir, newc_file

    disk = RamDisk(name="selftest", max_bytes=8 * 1024 * 1024)
    entries = [
        newc_dir("bin"),
        newc_dir("etc"),
        newc_file("init", b"#!/bin/sh\necho ok\n", mode=0o755),
        newc_file("etc/hostname", b"umer-os\n"),
    ]
    from initrd.cpio import pack_archive
    blob = pack_archive(entries)
    disk.load(blob)
    disk.extract()
    assert disk.state == RamDiskState.EXTRACTED
    assert disk.find("/init") is not None
    disk.mount("/")
    assert disk.state == RamDiskState.MOUNTED
    disk.pivot()
    assert disk.state == RamDiskState.PIVOTED
    disk.release()
    return disk.state == RamDiskState.RELEASED


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("ramdisk selftest:", "OK" if _selftest() else "FAIL")
