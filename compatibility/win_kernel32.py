"""
Umer OS /compatibility/win_kernel32 — kernel32.dll API stubs
==========================================================

``kernel32.dll`` is the Windows core subsystem DLL.  It exports
the user-mode wrappers around the NT executive: process / thread
management, file I/O, memory mapping, dynamic libraries, error
codes, and the registry client.  There are ~600 exports in the
real DLL; this module implements the most commonly used subset
so that a pure-Python loader can satisfy the most common
``IAT`` lookups without crashing.

Each public function:

* logs the call (DEBUG level) so tests can trace it,
* returns a *default* value that lets a stub call site proceed
  (often ``NULL``, ``FALSE``, or ``0``),
* raises :class:`NotImplementedError` only for functionality
  that the pure-Python loader cannot reasonably fake (e.g.
  creating an actual process).

The functions live in the :class:`Kernel32` namespace so that
the eventual :mod:`dll_loader` can resolve them by symbol name.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/
* https://wiki.osdev.org/Windows

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.Kernel32")

# Re-export the error codes so callers don't have to import two
# modules to interpret a return value.
from .winerror import (  # noqa: F401
    ERROR_SUCCESS,
    ERROR_INVALID_FUNCTION,
    ERROR_FILE_NOT_FOUND,
    ERROR_ACCESS_DENIED,
    ERROR_INVALID_HANDLE,
    ERROR_NOT_ENOUGH_MEMORY,
    ERROR_ALREADY_EXISTS,
    ERROR_PATH_NOT_FOUND,
    ERROR_INVALID_PARAMETER,
    ERROR_NO_MORE_FILES,
    ERROR_BROKEN_PIPE,
)


# ---------------------------------------------------------------------------
# Pseudo-handles (opaque integers; the real Win32 values are ~64-bit)
# ---------------------------------------------------------------------------

@dataclass
class PseudoHandle:
    """A fake handle.  Real Win32 handles are 64-bit pointers to
    kernel objects; here we use a small dataclass so test code can
    introspect what was opened.
    """

    kind: str           # "file", "process", "thread", "module", etc.
    path: str
    data: Any = None

    def close(self) -> None:
        self.kind = "<closed>"


# Global handle counter (the lower 32 bits of a fake pointer).
_NEXT_HANDLE = 0x1000


def _new_handle(kind: str, path: str, data: Any = None) -> PseudoHandle:
    global _NEXT_HANDLE
    _NEXT_HANDLE += 1
    return PseudoHandle(kind=kind, path=path, data=data)


# ---------------------------------------------------------------------------
# Open handles table (process-global)
# ---------------------------------------------------------------------------

_OPEN_HANDLES: Dict[int, PseudoHandle] = {}


def _store_handle(h: PseudoHandle) -> int:
    """Return an integer that mimics a Win32 HANDLE."""
    handle_id = id(h) & 0xFFFFFFFF
    _OPEN_HANDLES[handle_id] = h
    return handle_id


def _resolve_handle(handle_id: int) -> Optional[PseudoHandle]:
    return _OPEN_HANDLES.get(handle_id)


def _close_handle(handle_id: int) -> bool:
    h = _OPEN_HANDLES.pop(handle_id, None)
    if h is None:
        return False
    h.close()
    return True


# ---------------------------------------------------------------------------
# Last-error simulation (per-thread, but we use a single global slot)
# ---------------------------------------------------------------------------

_LAST_ERROR = 0


def SetLastError(err: int) -> None:
    global _LAST_ERROR
    _LAST_ERROR = err


def GetLastError() -> int:
    return _LAST_ERROR


# ---------------------------------------------------------------------------
# Process / module
# ---------------------------------------------------------------------------

def GetModuleHandleA(name: Optional[str]) -> int:
    """Return a *fake* handle to a loaded module (None = current process)."""
    if name is None:
        h = _new_handle("module", "<current>")
    else:
        h = _new_handle("module", name)
    return _store_handle(h)


def GetModuleFileNameA(handle: int, n_size: int = 260) -> str:
    """Return a fake module path."""
    h = _resolve_handle(handle)
    return h.path if h else ""


def GetCurrentProcess() -> int:
    """Return a pseudo-handle to the current process (-1 in Win32)."""
    return 0xFFFFFFFF & 0xFFFFFFFF


def GetCurrentThreadId() -> int:
    """Return the simulated thread id (= 1)."""
    return 1


def GetCurrentProcessId() -> int:
    """Return the simulated process id (= 1)."""
    return 1


def ExitProcess(code: int) -> None:
    """Terminate the process.  The pure-Python loader cannot actually exit
    the host process, so we raise :class:`SystemExit`."""
    log.info("ExitProcess(%d)", code)
    raise SystemExit(code)


def GetProcessHeap() -> int:
    return _store_handle(_new_handle("heap", "<process>"))


def HeapAlloc(heap: int, flags: int, size: int) -> int:
    return _store_handle(
        _new_handle("mem", f"<{size} bytes>", data=bytearray(size)),
    )


def HeapFree(heap: int, flags: int, mem: int) -> bool:
    return _close_handle(mem)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def CreateFileA(path: str, access: int, share: int,
                security: Any, creation: int, flags: int,
                template: int) -> int:
    """Open / create a file.  Returns INVALID_HANDLE_VALUE on failure."""
    if not os.path.isfile(path) and creation not in (2, 3):    # OPEN_ALWAYS, CREATE_ALWAYS
        SetLastError(ERROR_FILE_NOT_FOUND)
        return 0xFFFFFFFFFFFFFFFF & 0xFFFFFFFF
    try:
        base_mode = _decode_creation_disposition(creation)
        if base_mode in ("x", "w", "w+"):
            f = open(path, base_mode + "b")
        else:
            f = open(path, base_mode + "b")
    except OSError as exc:
        SetLastError(ERROR_ACCESS_DENIED)
        log.warning("CreateFileA(%s): %s", path, exc)
        return 0xFFFFFFFFFFFFFFFF & 0xFFFFFFFF
    h = _new_handle("file", path, data=f)
    SetLastError(ERROR_SUCCESS)
    return _store_handle(h)


def ReadFile(handle: int, size: int) -> Tuple[bool, bytes]:
    h = _resolve_handle(handle)
    if h is None or not hasattr(h.data, "read"):
        SetLastError(ERROR_INVALID_HANDLE)
        return False, b""
    try:
        buf = h.data.read(size)
    except OSError:
        SetLastError(ERROR_INVALID_HANDLE)
        return False, b""
    SetLastError(ERROR_SUCCESS)
    return True, buf


def WriteFile(handle: int, buf: bytes) -> Tuple[bool, int]:
    h = _resolve_handle(handle)
    if h is None or not hasattr(h.data, "write"):
        SetLastError(ERROR_INVALID_HANDLE)
        return False, 0
    try:
        n = h.data.write(buf)
    except OSError:
        SetLastError(ERROR_INVALID_HANDLE)
        return False, 0
    SetLastError(ERROR_SUCCESS)
    return True, len(buf) if n is None else n


def CloseHandle(handle: int) -> bool:
    return _close_handle(handle)


def DeleteFileA(path: str) -> bool:
    try:
        os.remove(path)
    except OSError as exc:
        SetLastError(ERROR_ACCESS_DENIED)
        log.warning("DeleteFileA(%s): %s", path, exc)
        return False
    SetLastError(ERROR_SUCCESS)
    return True


def MoveFileA(src: str, dst: str) -> bool:
    try:
        os.rename(src, dst)
    except OSError:
        SetLastError(ERROR_ACCESS_DENIED)
        return False
    SetLastError(ERROR_SUCCESS)
    return True


def _decode_creation_disposition(c: int) -> str:
    """Map a Win32 ``dwCreationDisposition`` to a Python file mode.

    Note: we return a *base* mode (r/w/x).  The caller decides the
    text/binary suffix and the +/- to keep the table here simple.
    """
    # 1=CREATE_NEW, 2=OPEN_ALWAYS, 3=OPEN_EXISTING, 4=TRUNCATE_EXISTING,
    # 5=CREATE_ALWAYS
    return {
        1: "x",
        2: "r+",
        3: "r",
        4: "w",
        5: "w+",
    }.get(c, "r")


# ---------------------------------------------------------------------------
# Dynamic libraries
# ---------------------------------------------------------------------------

def LoadLibraryA(name: str) -> int:
    h = _new_handle("library", name)
    return _store_handle(h)


def GetProcAddress(handle: int, proc: str) -> int:
    """Return a fake function pointer (we don't actually load anything)."""
    h = _resolve_handle(handle)
    if h is None:
        SetLastError(ERROR_INVALID_HANDLE)
        return 0
    return _store_handle(_new_handle("proc", f"{h.path}!{proc}"))


def FreeLibrary(handle: int) -> bool:
    return _close_handle(handle)


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def GetTickCount() -> int:
    """Return a millisecond tick counter (real wall-clock)."""
    import time
    return int(time.monotonic() * 1000) & 0xFFFFFFFF


def Sleep(ms: int) -> None:
    import time
    time.sleep(ms / 1000.0)


def Beep(freq: int, dur_ms: int) -> bool:
    log.info("Beep(%d, %d)", freq, dur_ms)
    return True


def GetCommandLineA() -> str:
    return "umeros"


def GetVersionExA() -> Tuple[int, int, int, int]:
    """Return (major, minor, build, platform_id)."""
    return (10, 0, 19045, 2)   # VER_PLATFORM_WIN32_NT


# ---------------------------------------------------------------------------
# Aggregate public surface
# ---------------------------------------------------------------------------

EXPORTS: Dict[str, Any] = {
    "GetModuleHandleA": GetModuleHandleA,
    "GetModuleFileNameA": GetModuleFileNameA,
    "GetCurrentProcess": GetCurrentProcess,
    "GetCurrentThreadId": GetCurrentThreadId,
    "GetCurrentProcessId": GetCurrentProcessId,
    "ExitProcess": ExitProcess,
    "GetProcessHeap": GetProcessHeap,
    "HeapAlloc": HeapAlloc,
    "HeapFree": HeapFree,
    "CreateFileA": CreateFileA,
    "ReadFile": ReadFile,
    "WriteFile": WriteFile,
    "CloseHandle": CloseHandle,
    "DeleteFileA": DeleteFileA,
    "MoveFileA": MoveFileA,
    "LoadLibraryA": LoadLibraryA,
    "GetProcAddress": GetProcAddress,
    "FreeLibrary": FreeLibrary,
    "GetTickCount": GetTickCount,
    "Sleep": Sleep,
    "Beep": Beep,
    "GetCommandLineA": GetCommandLineA,
    "GetVersionExA": GetVersionExA,
    "GetLastError": GetLastError,
    "SetLastError": SetLastError,
}


def _selftest() -> bool:
    # Module handle round-trip.
    h = GetModuleHandleA("kernel32.dll")
    if h == 0 or h == 0xFFFFFFFF:
        return False
    # File I/O round-trip on a temp file.
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        path = tf.name
        tf.write(b"hello")
    try:
        h = CreateFileA(path, 0xC0000000, 0, None, 3, 0, 0)
        if h == 0xFFFFFFFF:
            return False
        ok, data = ReadFile(h, 5)
        if not ok or data != b"hello":
            return False
        if not CloseHandle(h):
            return False
    finally:
        os.remove(path)
    # Sleep briefly.
    Sleep(0)
    # Last-error.
    SetLastError(ERROR_FILE_NOT_FOUND)
    if GetLastError() != ERROR_FILE_NOT_FOUND:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
