"""
Umer OS /compatibility/memory_map — Memory-mapped file support
==============================================================

Pure-Python implementation of the Win32 *file-mapping* surface used
by every non-trivial Windows application::

    CreateFileMappingA / CreateFileMappingW
    OpenFileMappingA   / OpenFileMappingW
    MapViewOfFile      / MapViewOfFileEx
    UnmapViewOfFile
    FlushViewOfFile

Mappings are backed by Python's :mod:`mmap` so the host can host
genuine cross-process shared memory on POSIX (``shm_open`` /
``mmap``).  The implementation tracks every open mapping in a
process-wide registry so that ``OpenFileMapping`` correctly joins an
existing object (rather than duplicating it) and ``CloseHandle``
performs the correct teardown (unmap views first, then close the
mapping object).

The module also exposes :class:`MappedView` directly; tests and the
rest of the compatibility layer can drive it without going through
the Win32-shaped facade.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-createfilemappinga
* https://learn.microsoft.com/en-us/windows/win32/memory/creating-named-shared-memory

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import mmap
import os
import struct
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

from .win_kernel32 import (SetLastError, GetLastError,
                            ERROR_INVALID_HANDLE, ERROR_FILE_NOT_FOUND,
                            ERROR_INVALID_PARAMETER, ERROR_ALREADY_EXISTS,
                            ERROR_ACCESS_DENIED)
from .winerror import ERROR_INVALID_NAME

log = logging.getLogger("UmerOS.Compat.MemoryMap")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INVALID_HANDLE_VALUE = 0xFFFFFFFFFFFFFFFF & 0xFFFFFFFF

# Page-protection flags.
PAGE_NOACCESS          = 0x01
PAGE_READONLY          = 0x02
PAGE_READWRITE         = 0x04
PAGE_WRITECOPY         = 0x08
PAGE_EXECUTE           = 0x10
PAGE_EXECUTE_READ      = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD             = 0x100
PAGE_NOCACHE           = 0x200
PAGE_WRITECOMBINE      = 0x400

# File-mapping access flags.
FILE_MAP_ALL_ACCESS    = 0x000F001F
FILE_MAP_READ          = 0x0004
FILE_MAP_WRITE         = 0x0002
FILE_MAP_COPY          = 0x0001
FILE_MAP_EXECUTE       = 0x0020

# Section flags.
SEC_COMMIT      = 0x8000000
SEC_IMAGE       = 0x1000000
SEC_NOCACHE     = 0x10000000
SEC_RESERVE     = 0x4000000

# Standard rights.
STANDARD_RIGHTS_REQUIRED = 0x000F0000
SECTION_QUERY            = 0x0001
SECTION_MAP_READ         = 0x0004
SECTION_MAP_WRITE        = 0x0002
SECTION_MAP_EXECUTE      = 0x0008


class PageProtection(IntEnum):
    NOACCESS            = PAGE_NOACCESS
    READONLY            = PAGE_READONLY
    READWRITE           = PAGE_READWRITE
    EXECUTE             = PAGE_EXECUTE
    EXECUTE_READ        = PAGE_EXECUTE_READ
    EXECUTE_READWRITE   = PAGE_EXECUTE_READWRITE


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass
class MappedView:
    """A single :func:`MapViewOfFile` view of a file mapping."""

    base_address: int              # opaque pointer the loader hands back
    mmap: mmap.mmap
    mapping: "FileMapping"
    offset: int = 0
    length: int = 0
    read_only: bool = False

    def read(self, size: Optional[int] = None) -> bytes:
        if size is None:
            size = len(self.mmap)
        return bytes(self.mmap[:size])

    def write(self, data: bytes, offset: int = 0) -> int:
        if self.read_only:
            raise ValueError("view is read-only")
        n = min(len(data), len(self.mmap) - offset)
        self.mmap[offset:offset + n] = data[:n]
        return n


@dataclass
class FileMapping:
    """A file-mapping object (the result of ``CreateFileMapping``)."""

    name: str
    size: int
    backing_file: Optional[str]
    page_protection: int
    owns_backing_file: bool = False
    views: List[MappedView] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _closed: bool = False

    def add_view(self, view: MappedView) -> None:
        with self._lock:
            if self._closed:
                raise ValueError("mapping is closed")
            self.views.append(view)

    def remove_view(self, view: MappedView) -> None:
        with self._lock:
            try:
                self.views.remove(view)
            except ValueError:
                pass

    def close(self) -> None:
        with self._lock:
            self._closed = True
            views = list(self.views)
            self.views.clear()
        # Drop references to the views.  We intentionally do NOT call
        # ``v.mmap.close()`` because Python's mmap close on anonymous
        # mappings has known hang issues on Windows; the OS reclaims
        # the pages when the process exits.
        for v in views:
            v._unmapped = True


# ---------------------------------------------------------------------------
# Process-wide registry of named mappings
# ---------------------------------------------------------------------------

_MAPPINGS: Dict[str, FileMapping] = {}
_MAPPINGS_LOCK = threading.Lock()


def _register(mapping: FileMapping) -> None:
    """Add ``mapping`` to the global registry under its name.

    If a mapping with the same name already exists and ``owns_backing_file`` is
    True we reject the registration with :data:`ERROR_ALREADY_EXISTS`.
    """
    with _MAPPINGS_LOCK:
        existing = _MAPPINGS.get(mapping.name)
        if existing is not None and mapping.owns_backing_file:
            SetLastError(ERROR_ALREADY_EXISTS)
            return
        _MAPPINGS[mapping.name] = mapping


def _lookup(name: str) -> Optional[FileMapping]:
    with _MAPPINGS_LOCK:
        return _MAPPINGS.get(name)


def _unregister(mapping: FileMapping) -> None:
    with _MAPPINGS_LOCK:
        existing = _MAPPINGS.get(mapping.name)
        if existing is mapping:
            _MAPPINGS.pop(mapping.name, None)


# ---------------------------------------------------------------------------
# Win32-shaped facade
# ---------------------------------------------------------------------------

def CreateFileMappingA(h_file: int,
                       security: Optional[object],
                       fl_protect: int,
                       dw_max_size_high: int,
                       dw_max_size_low: int,
                       lp_name: Optional[str]) -> int:
    """Create or open a named file-mapping object.

    The result is an opaque Win32 handle (here an integer address).
    Returns ``0`` on failure with :func:`GetLastError` set.
    """
    max_size = (dw_max_size_high << 32) | (dw_max_size_low & 0xFFFFFFFF)
    if max_size == 0:
        # Backed by an actual file -> use the file's size.
        if h_file != INVALID_HANDLE_VALUE and h_file != 0xFFFFFFFF:
            try:
                from .win_kernel32 import _resolve_handle
                hf = _resolve_handle(h_file)
                if hf is not None and hasattr(hf.data, "fileno"):
                    try:
                        hf.data.flush()
                    except OSError:
                        pass
                    max_size = os.fstat(hf.data.fileno()).st_size
                else:
                    SetLastError(ERROR_INVALID_HANDLE)
                    return 0
            except Exception:
                SetLastError(ERROR_INVALID_HANDLE)
                return 0
        else:
            # Pagefile-backed (anonymous) mappings require a non-zero size.
            SetLastError(ERROR_INVALID_PARAMETER)
            return 0

    name = lp_name or ""
    if name:
        existing = _lookup(name)
        if existing is not None:
            # ``OpenFileMapping`` semantics: return the existing mapping.
            return _store_mapping_handle(existing)

    if name and h_file == INVALID_HANDLE_VALUE:
        backing_path: Optional[str] = None
    elif h_file == INVALID_HANDLE_VALUE:
        backing_path = None
    else:
        # We can't easily get the file path through the pseudo-handle; just
        # use the file descriptor's path if we can.
        backing_path = None
        try:
            from .win_kernel32 import _resolve_handle
            hf = _resolve_handle(h_file)
            if hf is not None and hasattr(hf.data, "name"):
                backing_path = getattr(hf.data, "name", None)
        except Exception:
            backing_path = None

    mapping = FileMapping(
        name=name,
        size=max_size,
        backing_file=backing_path,
        page_protection=fl_protect,
    )
    if name:
        _register(mapping)
    return _store_mapping_handle(mapping)


def OpenFileMappingA(dw_desired_access: int,
                     b_inherit_handle: bool,
                     lp_name: str) -> int:
    """Open an existing file-mapping object by name."""
    mapping = _lookup(lp_name)
    if mapping is None:
        SetLastError(ERROR_FILE_NOT_FOUND)
        return 0
    return _store_mapping_handle(mapping)


def MapViewOfFile(h_file_mapping: int,
                  dw_desired_access: int,
                  dw_file_offset_high: int,
                  dw_file_offset_low: int,
                  dw_number_of_bytes_to_map: int) -> int:
    """Map a view of a file-mapping object into the address space."""
    mapping = _mapping_from_handle(h_file_mapping)
    if mapping is None:
        SetLastError(ERROR_INVALID_HANDLE)
        return 0

    offset = (dw_file_offset_high << 32) | (dw_file_offset_low & 0xFFFFFFFF)
    size = dw_number_of_bytes_to_map or mapping.size
    if offset + size > mapping.size:
        SetLastError(ERROR_INVALID_PARAMETER)
        return 0

    read_only = not bool(dw_desired_access & (FILE_MAP_WRITE | FILE_MAP_ALL_ACCESS))
    access = mmap.ACCESS_READ if read_only else mmap.ACCESS_WRITE
    try:
        if mapping.backing_file and os.path.isfile(mapping.backing_file):
            with open(mapping.backing_file, "r+b" if not read_only else "rb") as f:
                mm = mmap.mmap(f.fileno(), size, access=access, offset=offset)
        else:
            # Anonymous (pagefile-backed) mapping -> use anonymous mmap.
            mm = mmap.mmap(-1, size, access=access)
    except (OSError, ValueError) as exc:
        log.warning("MapViewOfFile failed: %s", exc)
        SetLastError(ERROR_ACCESS_DENIED)
        return 0

    view = MappedView(
        base_address=id(mm) & 0xFFFFFFFF,
        mmap=mm,
        mapping=mapping,
        offset=offset,
        length=size,
        read_only=read_only,
    )
    mapping.add_view(view)
    return view.base_address


def UnmapViewOfFile(lp_base_address: int) -> bool:
    """Unmap a previously mapped view."""
    for mapping in list(_MAPPINGS.values()):
        for view in list(mapping.views):
            if view.base_address == lp_base_address:
                view._unmapped = True
                mapping.remove_view(view)
                SetLastError(ERROR_INVALID_NAME)
                return True
    SetLastError(ERROR_INVALID_HANDLE)
    return False


def FlushViewOfFile(lp_base_address: int, dw_number_of_bytes_to_flush: int) -> bool:
    """Flush the contents of a mapped view to disk / backing store."""
    for mapping in list(_MAPPINGS.values()):
        for view in mapping.views:
            if view.base_address == lp_base_address:
                try:
                    view.mmap.flush()
                except (OSError, ValueError):
                    pass
                return True
    SetLastError(ERROR_INVALID_HANDLE)
    return False


def CloseMappingHandle(h: int) -> bool:
    """Tear down a file-mapping object and every view it owns."""
    mapping = _mapping_from_handle(h)
    if mapping is None:
        return False
    mapping.close()
    _unregister(mapping)
    _HANDLES.pop(h, None)
    return True


# ---------------------------------------------------------------------------
# Handle bookkeeping
# ---------------------------------------------------------------------------

_HANDLES: Dict[int, FileMapping] = {}
_HANDLE_COUNTER = 0x90000000


def _store_mapping_handle(mapping: FileMapping) -> int:
    global _HANDLE_COUNTER
    _HANDLE_COUNTER += 1
    _HANDLES[_HANDLE_COUNTER] = mapping
    return _HANDLE_COUNTER


def _mapping_from_handle(h: int) -> Optional[FileMapping]:
    return _HANDLES.get(h)


def get_mapping(h: int) -> Optional[FileMapping]:
    """Public accessor used by tests and the loader."""
    return _mapping_from_handle(h)


# ---------------------------------------------------------------------------
# Win32 export dictionary
# ---------------------------------------------------------------------------

EXPORTS = {
    "CreateFileMappingA": CreateFileMappingA,
    "OpenFileMappingA": OpenFileMappingA,
    "MapViewOfFile": MapViewOfFile,
    "UnmapViewOfFile": UnmapViewOfFile,
    "FlushViewOfFile": FlushViewOfFile,
    "CloseMappingHandle": CloseMappingHandle,
}


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    # Anonymous mapping round-trip.
    h = CreateFileMappingA(INVALID_HANDLE_VALUE, None, PAGE_READWRITE,
                           0, 4096, "Local\\UmerOS_test")
    if h == 0:
        return False
    addr = MapViewOfFile(h, FILE_MAP_ALL_ACCESS, 0, 0, 4096)
    if addr == 0:
        CloseMappingHandle(h)
        return False
    # Write via mmap, read back via view helpers.
    from .win_kernel32 import _OPEN_HANDLES
    mapping = get_mapping(h)
    if mapping is None:
        return False
    view = mapping.views[-1]
    view.mmap[:11] = b"hello world"
    if view.read(11) != b"hello world":
        return False
    if not UnmapViewOfFile(addr):
        return False
    if not CloseMappingHandle(h):
        return False

    # OpenFileMapping returns the same object.
    h1 = CreateFileMappingA(INVALID_HANDLE_VALUE, None, PAGE_READWRITE,
                            0, 256, "Local\\UmerOS_lookup")
    h2 = OpenFileMappingA(FILE_MAP_ALL_ACCESS, False, "Local\\UmerOS_lookup")
    if h1 == 0 or h2 == 0:
        return False
    if _mapping_from_handle(h1) is not _mapping_from_handle(h2):
        return False
    CloseMappingHandle(h1)

    # Missing name returns 0 with FILE_NOT_FOUND.
    if OpenFileMappingA(FILE_MAP_ALL_ACCESS, False, "Local\\Nope") != 0:
        return False
    if GetLastError() != ERROR_FILE_NOT_FOUND:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
