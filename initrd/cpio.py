"""
Umer OS Initrd CPIO
===================
Read and write **CPIO "newc"** archives, the format used by every
modern initramfs.

The newc format is a simple record stream:

    +--------+--------+--------+-----+--------+--------+
    | "070701" magic                     (6 bytes)
    +--------+--------+--------+-----+--------+--------+
    | ino  (8) | mode (8) | uid (8) | gid (8) | nlink (8)
    +--------+--------+--------+-----+--------+--------+
    | mtime (8) | filesize (8) | devmajor (8) | devminor (8)
    +--------+--------+--------+-----+--------+--------+
    | rdevmajor (8) | rdevminor (8) | namesize (8) | check (8)
    +--------+--------+--------+-----+--------+--------+
    | filename (namesize, NUL-terminated, 4-byte aligned)
    +--------+--------+--------+-----+--------+--------+
    | file data (filesize, 4-byte aligned)
    +--------+--------+--------+-----+--------+--------+
    | next entry ... | "TRAILER!!!" (10 bytes) | padding
    +--------+--------+--------+-----+--------+--------+

UmerOS doesn't ship a C compiler toolchain for the kernel's
``initramfs_list.txt`` flow, so this module is the host-side tool that
turns a Python description of an initrd into a real cpio archive that
the bootloader can hand to the kernel.

The runtime side (``initrd.linuxrc``) never parses cpio itself - the
kernel has already unpacked the archive into a tmpfs by the time
``/init`` runs. The reader is provided so that tests and the
``initrd.builder`` can inspect existing initramfs images (e.g. an
Arch ``archlinux-*.img``) without spawning an external ``cpio``.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import io
import logging
import os
import stat
import struct
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional

log = logging.getLogger("UmerOS.Initrd.CPIO")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

C_MAGIC     = b"070701"      # newc
C_TRAILER   = b"TRAILER!!!"
C_ISREG     = 0o100000
C_ISDIR     = 0o040000
C_ISLNK     = 0o120000
C_ISSOCK    = 0o140000
C_ISFIFO    = 0o010000
C_ISBLK     = 0o060000
C_ISCHR     = 0o020000

HEADER_FMT  = "6s8s8s8s8s8s8s8s8s8s8s8s8s8s"
HEADER_SIZE = 110  # 6 + 13*8


# ---------------------------------------------------------------------------
# Entry dataclass
# ---------------------------------------------------------------------------

@dataclass
class CpioEntry:
    """A single record inside a newc archive."""

    name: str
    data: bytes = b""
    mode: int = 0o644
    uid: int = 0
    gid: int = 0
    ino: int = 0
    nlink: int = 1
    mtime: int = 0
    devmajor: int = 0
    devminor: int = 0
    rdevmajor: int = 0
    rdevminor: int = 0
    target: Optional[str] = None  # symlink target

    # -- internal ---------------------------------------------------------

    def filetype(self) -> int:
        return self.mode & 0o170000

    def is_dir(self) -> bool:
        return self.filetype() == C_ISDIR

    def is_symlink(self) -> bool:
        return self.filetype() == C_ISLNK

    def is_regular(self) -> bool:
        return self.filetype() == C_ISREG

    def is_device(self) -> bool:
        return self.filetype() in (C_ISBLK, C_ISCHR)

    # -- header encoding --------------------------------------------------

    def _header_bytes(self) -> bytes:
        namesize = len(self.name.encode("utf-8")) + 1  # include NUL
        data_size = len(self.data) if self.is_regular() else 0
        if self.is_symlink() and self.target is not None:
            data_size = len(self.target.encode("utf-8")) + 1

        header = struct.pack(
            HEADER_FMT,
            C_MAGIC,
            f"{self.ino:08x}".encode(),
            f"{self.mode:08x}".encode(),
            f"{self.uid:08x}".encode(),
            f"{self.gid:08x}".encode(),
            f"{self.nlink:08x}".encode(),
            f"{self.mtime:08x}".encode(),
            f"{data_size:08x}".encode(),
            f"{self.devmajor:08x}".encode(),
            f"{self.devminor:08x}".encode(),
            f"{self.rdevmajor:08x}".encode(),
            f"{self.rdevminor:08x}".encode(),
            f"{namesize:08x}".encode(),
            f"{0:08x}".encode(),  # check
        )
        return header

    # -- serialization ----------------------------------------------------

    def pack(self) -> bytes:
        """Encode this entry (header + name + data) as bytes."""
        out = bytearray()
        out += self._header_bytes()
        name_bytes = self.name.encode("utf-8") + b"\x00"
        out += name_bytes
        out += _align(len(name_bytes), 4)

        if self.is_regular():
            out += self.data
            out += _align(len(self.data), 4)
        elif self.is_symlink() and self.target is not None:
            target_bytes = self.target.encode("utf-8") + b"\x00"
            out += target_bytes
            out += _align(len(target_bytes), 4)

        return bytes(out)


# ---------------------------------------------------------------------------
# Alignment helper
# ---------------------------------------------------------------------------

def _align(n: int, multiple: int) -> bytes:
    """Return the pad bytes required to bring ``n`` up to a multiple of 4."""
    rem = n % multiple
    if rem == 0:
        return b""
    return b"\x00" * (multiple - rem)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def pack_archive(entries: Iterable[CpioEntry]) -> bytes:
    """Serialize ``entries`` (followed by the mandatory TRAILER) into bytes.

    The TRAILER record's filename is the literal ``"TRAILER!!!"``; the
    kernel stops reading when it encounters it.
    """
    buf = io.BytesIO()
    count = 0
    for entry in entries:
        buf.write(entry.pack())
        count += 1
    trailer = CpioEntry(name="TRAILER!!!", mode=0, nlink=1)
    buf.write(trailer.pack())
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

def _read_header(stream: io.BufferedIOBase) -> Optional[CpioEntry]:
    """Read one cpio entry header from ``stream``.

    Returns ``None`` at EOF or when the next 6 bytes are not the newc
    magic.  Raises ``ValueError`` on a malformed record.
    """
    raw = stream.read(HEADER_SIZE)
    if not raw or len(raw) < HEADER_SIZE:
        return None
    if raw[:6] != C_MAGIC:
        return None
    fields = struct.unpack(HEADER_FMT, raw)
    (
        _magic,
        ino, mode, uid, gid, nlink, mtime, filesize,
        devmajor, devminor, rdevmajor, rdevminor, namesize, _check,
    ) = fields
    name_raw = stream.read(int(namesize, 16))
    if len(name_raw) < int(namesize, 16):
        raise ValueError("cpio: truncated name")
    pad = _align(int(namesize, 16), 4)
    if pad:
        stream.read(len(pad))
    name = name_raw.rstrip(b"\x00").decode("utf-8", errors="replace")
    if name == C_TRAILER.decode():
        return CpioEntry(name="TRAILER!!!", mode=0, nlink=1)
    fsize = int(filesize, 16)
    data = stream.read(fsize)
    if len(data) < fsize:
        raise ValueError(f"cpio: truncated data for {name!r}")
    pad = _align(fsize, 4)
    if pad:
        stream.read(len(pad))

    target: Optional[str] = None
    if int(mode, 16) & 0o170000 == C_ISLNK and fsize > 0:
        target = data.rstrip(b"\x00").decode("utf-8", errors="replace")
        data = b""

    return CpioEntry(
        name=name,
        data=data,
        mode=int(mode, 16),
        uid=int(uid, 16),
        gid=int(gid, 16),
        ino=int(ino, 16),
        nlink=int(nlink, 16),
        mtime=int(mtime, 16),
        devmajor=int(devmajor, 16),
        devminor=int(devminor, 16),
        rdevmajor=int(rdevmajor, 16),
        rdevminor=int(rdevminor, 16),
        target=target,
    )


def unpack_archive(blob: bytes) -> List[CpioEntry]:
    """Parse a newc archive and return the list of entries inside it."""
    stream = io.BytesIO(blob)
    out: List[CpioEntry] = []
    while True:
        entry = _read_header(stream)
        if entry is None:
            break
        if entry.name == "TRAILER!!!":
            break
        out.append(entry)
    return out


def iter_archive(blob: bytes) -> Iterator[CpioEntry]:
    """Yield entries one at a time without materialising the whole list."""
    stream = io.BytesIO(blob)
    while True:
        entry = _read_header(stream)
        if entry is None:
            return
        if entry.name == "TRAILER!!!":
            return
        yield entry


# ---------------------------------------------------------------------------
# Builders for typical FS roots
# ---------------------------------------------------------------------------

def newc_dir(name: str, mode: int = 0o755, ino: int = 1) -> CpioEntry:
    """Build a directory entry.  ``ino`` is required so files sort cleanly."""
    return CpioEntry(name=name, mode=mode | C_ISDIR, nlink=2, ino=ino)


def newc_file(name: str, data: bytes, mode: int = 0o644, ino: int = 2) -> CpioEntry:
    """Build a regular file entry."""
    return CpioEntry(name=name, data=data, mode=mode | C_ISREG, ino=ino)


def newc_symlink(name: str, target: str, ino: int = 3) -> CpioEntry:
    """Build a symbolic link entry."""
    return CpioEntry(
        name=name,
        target=target,
        mode=0o777 | C_ISLNK,
        ino=ino,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Round-trip a small archive and confirm every entry survives."""
    entries = [
        newc_dir("."),
        newc_dir("bin"),
        newc_dir("etc"),
        newc_file("init", b"#!/bin/sh\necho UmerOS\n", mode=0o755),
        newc_file("etc/hostname", b"umer-os\n"),
        newc_symlink("bin/sh", "/bin/busybox"),
    ]
    blob = pack_archive(entries)
    rt = unpack_archive(blob)
    by_name = {e.name: e for e in rt}
    ok = (
        by_name.get("init") and by_name["init"].data == b"#!/bin/sh\necho UmerOS\n"
        and by_name.get("bin/sh") and by_name["bin/sh"].target == "/bin/busybox"
        and by_name.get("etc/hostname") and by_name["etc/hostname"].data == b"umer-os\n"
    )
    return ok


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("cpio roundtrip:", "OK" if _selftest() else "FAIL")
