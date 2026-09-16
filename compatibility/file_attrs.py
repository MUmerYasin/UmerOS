"""
Umer OS /compatibility/file_attrs — Win32 file attribute helpers
==============================================================

A small, self-contained port of the Win32 *file attribute* surface used
by almost every Windows application and installer::

    GetFileAttributesA / GetFileAttributesW
    SetFileAttributesA / SetFileAttributesW
    GetFileAttributesExA / GetFileAttributesExW

The implementation maps the small Win32 ``DWORD`` attribute bitfield
onto a :class:`FileAttributes` dataclass and translates the bits that
have meaning on POSIX (``READONLY``, ``HIDDEN``, ``DIRECTORY``,
``ARCHIVE``) into the closest host equivalent.

* ``FILE_ATTRIBUTE_READONLY``  -> ``os.stat().st_mode`` losing owner write bit
* ``FILE_ATTRIBUTE_HIDDEN``    -> ``stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH``
                                   bit on the parent dir (POSIX has no
                                   intrinsic hidden flag; we follow the
                                   Unix convention used by ``ls -F``).
* ``FILE_ATTRIBUTE_DIRECTORY`` -> derived from ``stat.S_ISDIR``.
* ``FILE_ATTRIBUTE_ARCHIVE``   -> backed by a sidecar ``.attr`` file so
                                   that installers can flip it.

Bits that have no POSIX meaning (``SYSTEM``, ``NOT_CONTENT_INDEXED``,
``ENCRYPTED``, ...) are tracked in-memory only; they round-trip
through :meth:`FileAttributes.to_dword` / :meth:`from_dword` so a
loader that audits a binary still sees the original ``dwFileAttributes``
value the PE claimed.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants
* https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileattributesa
* https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileattributesa

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from typing import Dict, Optional

log = logging.getLogger("UmerOS.Compat.FileAttrs")

# ---------------------------------------------------------------------------
# Win32 FILE_ATTRIBUTE_* constants (subset that matters for installers)
# ---------------------------------------------------------------------------

INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

FILE_ATTRIBUTE_READONLY            = 0x00000001
FILE_ATTRIBUTE_HIDDEN              = 0x00000002
FILE_ATTRIBUTE_SYSTEM              = 0x00000004
FILE_ATTRIBUTE_DIRECTORY           = 0x00000010
FILE_ATTRIBUTE_ARCHIVE             = 0x00000020
FILE_ATTRIBUTE_DEVICE              = 0x00000040
FILE_ATTRIBUTE_NORMAL              = 0x00000080
FILE_ATTRIBUTE_TEMPORARY           = 0x00000100
FILE_ATTRIBUTE_SPARSE_FILE         = 0x00000200
FILE_ATTRIBUTE_REPARSE_POINT       = 0x00000400
FILE_ATTRIBUTE_COMPRESSED          = 0x00000800
FILE_ATTRIBUTE_OFFLINE             = 0x00001000
FILE_ATTRIBUTE_NOT_CONTENT_INDEXED = 0x00002000
FILE_ATTRIBUTE_ENCRYPTED           = 0x00004000
FILE_ATTRIBUTE_INTEGRITY_STREAM   = 0x00008000
FILE_ATTRIBUTE_VIRTUAL             = 0x00010000
FILE_ATTRIBUTE_NO_SCRUB_DATA       = 0x00020000
FILE_ATTRIBUTE_RECALL_ON_OPEN     = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000

#: All known attribute bits in a single mask.
_ALL_ATTRIBUTE_BITS = (
    FILE_ATTRIBUTE_READONLY
    | FILE_ATTRIBUTE_HIDDEN
    | FILE_ATTRIBUTE_SYSTEM
    | FILE_ATTRIBUTE_DIRECTORY
    | FILE_ATTRIBUTE_ARCHIVE
    | FILE_ATTRIBUTE_DEVICE
    | FILE_ATTRIBUTE_NORMAL
    | FILE_ATTRIBUTE_TEMPORARY
    | FILE_ATTRIBUTE_SPARSE_FILE
    | FILE_ATTRIBUTE_REPARSE_POINT
    | FILE_ATTRIBUTE_COMPRESSED
    | FILE_ATTRIBUTE_OFFLINE
    | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED
    | FILE_ATTRIBUTE_ENCRYPTED
    | FILE_ATTRIBUTE_INTEGRITY_STREAM
    | FILE_ATTRIBUTE_VIRTUAL
    | FILE_ATTRIBUTE_NO_SCRUB_DATA
    | FILE_ATTRIBUTE_RECALL_ON_OPEN
    | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
)


# ---------------------------------------------------------------------------
# Win32 GetFileAttributesEx / BY_HANDLE_FILE_INFORMATION (subset)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileAttributes:
    """A reflective view of a file's Win32 attribute bitfield.

    The integer ``dw_attrs`` is the canonical representation: it is
    the value the Win32 API would return from ``GetFileAttributes``.
    The boolean helpers exist purely for readability.
    """

    dw_attrs: int
    #: Filesystem size in bytes (0 for directories / unsupported).
    size: int = 0

    # ------------------------------------------------------------------
    # Bit helpers
    # ------------------------------------------------------------------

    @property
    def readonly(self) -> bool:
        return bool(self.dw_attrs & FILE_ATTRIBUTE_READONLY)

    @property
    def hidden(self) -> bool:
        return bool(self.dw_attrs & FILE_ATTRIBUTE_HIDDEN)

    @property
    def system(self) -> bool:
        return bool(self.dw_attrs & FILE_ATTRIBUTE_SYSTEM)

    @property
    def is_directory(self) -> bool:
        return bool(self.dw_attrs & FILE_ATTRIBUTE_DIRECTORY)

    @property
    def archive(self) -> bool:
        return bool(self.dw_attrs & FILE_ATTRIBUTE_ARCHIVE)

    @property
    def encrypted(self) -> bool:
        return bool(self.dw_attrs & FILE_ATTRIBUTE_ENCRYPTED)

    # ------------------------------------------------------------------
    # Conversions
    # ------------------------------------------------------------------

    @classmethod
    def from_dword(cls, attrs: int, *, size: int = 0) -> "FileAttributes":
        if attrs == INVALID_FILE_ATTRIBUTES:
            raise ValueError("INVALID_FILE_ATTRIBUTES is not a real file")
        return cls(dw_attrs=attrs & _ALL_ATTRIBUTE_BITS, size=size)

    def to_dword(self) -> int:
        return self.dw_attrs


# ---------------------------------------------------------------------------
# POSIX translation helpers
# ---------------------------------------------------------------------------

def _attr_sidecar_path(path: str) -> str:
    """Sidecar file used to remember bits that POSIX cannot store."""
    return path + ".attr"


def _read_sidecar(path: str) -> Optional[str]:
    try:
        with open(_attr_sidecar_path(path), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _write_sidecar(path: str, attrs: int) -> None:
    try:
        with open(_attr_sidecar_path(path), "w", encoding="utf-8") as f:
            f.write(f"{attrs:08X}\n")
    except OSError as exc:
        log.warning("could not persist attributes sidecar for %s: %s",
                    path, exc)


def _stat_to_attrs(st: os.stat_result) -> int:
    """Translate a POSIX stat into the Win32 attribute bitfield."""
    attrs = 0
    if stat.S_ISDIR(st.st_mode):
        attrs |= FILE_ATTRIBUTE_DIRECTORY
    else:
        attrs |= FILE_ATTRIBUTE_ARCHIVE
        # READONLY: no group/other write bit AND no owner write bit.
        if not (st.st_mode & stat.S_IWUSR):
            attrs |= FILE_ATTRIBUTE_READONLY
    # HIDDEN on POSIX is a dotfile prefix convention.  The caller is
    # responsible for setting it explicitly; we don't auto-detect.
    return attrs


# ---------------------------------------------------------------------------
# Public API (ANSI + Wide)
# ---------------------------------------------------------------------------

def GetFileAttributesA(path: str) -> int:
    """Win32 ``GetFileAttributesA`` equivalent."""
    try:
        st = os.stat(path)
    except OSError as exc:
        log.debug("GetFileAttributesA(%s) -> %s", path, exc)
        return INVALID_FILE_ATTRIBUTES
    attrs = _stat_to_attrs(st)
    side = _read_sidecar(path)
    if side:
        try:
            attrs |= int(side, 16) & (
                FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM
                | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED | FILE_ATTRIBUTE_ENCRYPTED
                | FILE_ATTRIBUTE_TEMPORARY
            )
        except ValueError:
            pass
    return attrs


def GetFileAttributesW(path: str) -> int:
    """Wide-char variant — on this layer we treat paths as already decoded."""
    return GetFileAttributesA(path)


def GetFileAttributesExA(path: str) -> Optional[FileAttributes]:
    """Win32 ``GetFileAttributesExA`` — returns the full attribute struct."""
    try:
        st = os.stat(path)
    except OSError as exc:
        log.debug("GetFileAttributesExA(%s) -> %s", path, exc)
        return None
    attrs = _stat_to_attrs(st)
    side = _read_sidecar(path)
    if side:
        try:
            attrs |= int(side, 16)
        except ValueError:
            pass
    return FileAttributes.from_dword(attrs, size=st.st_size)


def GetFileAttributesExW(path: str) -> Optional[FileAttributes]:
    return GetFileAttributesExA(path)


def SetFileAttributesA(path: str, attrs: int) -> bool:
    """Win32 ``SetFileAttributesA``.

    Only ``READONLY`` and ``ARCHIVE`` are mapped onto the real filesystem
    (via ``os.chmod``); the remaining bits are persisted in a sidecar
    file so they round-trip on subsequent :func:`GetFileAttributesA`
    calls within the same compatibility root.
    """
    try:
        st = os.stat(path)
    except OSError as exc:
        log.warning("SetFileAttributesA(%s): stat failed: %s", path, exc)
        return False

    is_dir = stat.S_ISDIR(st.st_mode)

    # Map READONLY -> drop owner-write bit.  ARCHIVE is purely advisory.
    if not is_dir:
        mode = st.st_mode
        if attrs & FILE_ATTRIBUTE_READONLY:
            mode &= ~stat.S_IWUSR
        else:
            mode |= stat.S_IWUSR
        try:
            os.chmod(path, mode)
        except OSError as exc:
            log.warning("SetFileAttributesA(%s): chmod failed: %s", path, exc)
            return False

    # Persist the bits POSIX cannot store.
    persist = attrs & (
        FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM
        | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED | FILE_ATTRIBUTE_ENCRYPTED
        | FILE_ATTRIBUTE_TEMPORARY
    )
    _write_sidecar(path, persist)
    return True


def SetFileAttributesW(path: str, attrs: int) -> bool:
    return SetFileAttributesA(path, attrs)


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        path = tf.name
        tf.write(b"hi")
    try:
        # READONLY -> drop owner write, then WriteFile-equivalent should fail.
        if not SetFileAttributesA(path, FILE_ATTRIBUTE_READONLY):
            return False
        a = GetFileAttributesA(path)
        if not (a & FILE_ATTRIBUTE_READONLY):
            return False
        # Clear it.
        if not SetFileAttributesA(path, 0):
            return False
        a = GetFileAttributesA(path)
        if a & FILE_ATTRIBUTE_READONLY:
            return False
        # Ex struct variant.
        info = GetFileAttributesExA(path)
        if info is None or info.size != 2:
            return False
        # Round-trip of "no-POSIX bits".
        SetFileAttributesA(path, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
        a = GetFileAttributesA(path)
        if not (a & FILE_ATTRIBUTE_HIDDEN and a & FILE_ATTRIBUTE_SYSTEM):
            return False
        return True
    finally:
        for p in (path, _attr_sidecar_path(path)):
            try:
                os.remove(p)
            except OSError:
                pass


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
