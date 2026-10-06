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
License: GPL-3.0 
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
    # If the handle wraps a real file object, flush+close it so we
    # don't leak file descriptors (CPython's ResourceWarning would
    # otherwise surface when a test framework is loaded).
    data = h.data
    if hasattr(data, "close"):
        try:
            data.close()
        except OSError:
            pass
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
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    want_read = bool(access & GENERIC_READ)
    want_write = bool(access & GENERIC_WRITE)
    if not os.path.isfile(path) and creation not in (2, 5):    # OPEN_ALWAYS, CREATE_ALWAYS
        SetLastError(ERROR_FILE_NOT_FOUND)
        return 0xFFFFFFFFFFFFFFFF & 0xFFFFFFFF
    try:
        base_mode = _decode_creation_disposition(creation, want_read, want_write)
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


def _decode_creation_disposition(c: int, want_read: bool, want_write: bool) -> str:
    """Map a Win32 ``dwCreationDisposition`` + access mask to a Python file mode.

    The combination is:

    * 1 = CREATE_NEW     -> exclusive create; reads/writes both allowed
    * 2 = OPEN_ALWAYS    -> open if exists, else create; reads/writes both allowed
    * 3 = OPEN_EXISTING  -> open existing only; access depends on GENERIC_READ/WRITE
    * 4 = TRUNCATE_EXISTING -> truncate existing; access depends on read/write
    * 5 = CREATE_ALWAYS  -> always create / truncate; reads/writes both allowed

    The caller appends ``"b"`` for binary mode.
    """
    rw = "r+" if (want_read and want_write) else ("w" if want_write else "r")
    return {
        1: "x+",        # CREATE_NEW: exclusive, then read+write
        2: "a+" if (want_read and want_write) else ("a" if want_write else "r"),
        3: rw,          # OPEN_EXISTING
        4: rw if want_write else "w",  # TRUNCATE_EXISTING requires write
        5: "w+",        # CREATE_ALWAYS
    }.get(c, rw)


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


def GetCommandLineW() -> str:
    """Win32 ``GetCommandLineW`` -- Unicode flavour of GetCommandLineA."""
    return "umeros"


def GetVersionExA() -> Tuple[int, int, int, int]:
    """Return (major, minor, build, platform_id)."""
    return (10, 0, 19045, 2)   # VER_PLATFORM_WIN32_NT


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
#
# Win32 env functions dispatch to :mod:`compatibility.environment`.
# We import lazily so the win_kernel32 module stays import-safe when
# the env module is in the middle of an upgrade.

def _env():
    from . import environment
    return environment


def GetEnvironmentVariableA(name: str, buf: Optional[str] = None) -> Optional[str]:
    """Win32 ``GetEnvironmentVariableA`` semantics.

    Returns the value as a Python ``str`` (or ``None`` if the variable
    is not set -- matches the Win32 contract that distinguishes a
    missing variable from an empty one).

    The Win32 signature is::

            GetEnvironmentVariableA(lpName, lpBuffer, nSize)

    but when called from :mod:`compatibility.win32_runner` the buffer
    pointer is irrelevant -- the emulator pulls the result out of the
    Python return.
    """
    return _env().GetEnvironmentVariableA(name)


def SetEnvironmentVariableA(name: str, value: Optional[str]) -> bool:
    """Win32 ``SetEnvironmentVariableA`` semantics."""
    return _env().SetEnvironmentVariableA(name, value)


def GetEnvironmentStringsA() -> bytes:
    """Win32 ``GetEnvironmentStringsA`` -- returns the
    double-null-terminated wide-char block as bytes."""
    return _env().GetEnvironmentStringsA()


def ExpandEnvironmentStringsA(s: str) -> str:
    """Win32 ``ExpandEnvironmentStringsA`` -- substitute ``%NAME%``
    references in ``s``."""
    return _env().ExpandEnvironmentStringsA(s)


def GetEnvironmentVariableW(name: str) -> Optional[str]:
    return _env().GetEnvironmentVariableW(name)


def SetEnvironmentVariableW(name: str, value: Optional[str]) -> bool:
    return _env().SetEnvironmentVariableW(name, value)


def ExpandEnvironmentStringsW(s: str) -> str:
    return _env().ExpandEnvironmentStringsW(s)


def GetCurrentDirectoryA(buf_size: int = 4096) -> str:
    """Win32 ``GetCurrentDirectoryA`` -- return the current
    working directory."""
    return os.getcwd()


def SetCurrentDirectoryA(path: str) -> bool:
    """Win32 ``SetCurrentDirectoryA`` -- change the current
    working directory."""
    try:
        os.chdir(path)
        return True
    except (OSError, FileNotFoundError):
        return False


def GetComputerNameA() -> str:
    """Win32 ``GetComputerNameA`` -- return the host name."""
    import socket
    return socket.gethostname()


def GetUserNameA() -> str:
    """Win32 ``GetUserNameA`` -- return the current user name."""
    return os.environ.get("USERNAME") or os.environ.get("USER") or "User"


# ---------------------------------------------------------------------------
# Time / date
# ---------------------------------------------------------------------------

def GetSystemTimeAsFileTime(t: Optional[bytes] = None) -> bytes:
    """Win32 ``GetSystemTimeAsFileTime`` -- write a 64-bit FILETIME
    representing the current time into ``t`` (a 16-byte buffer).
    The FILETIME is the number of 100-ns intervals since 1601-01-01 UTC."""
    import time as _t
    # Convert epoch (1970) to FILETIME epoch (1601).
    epoch_diff = 116444736000000000
    filetime = int(_t.time() * 1000000) + epoch_diff
    blob = struct.pack("<Q", filetime)
    if t is not None:
        # In a real Win32, ``t`` would be a pointer; our Python
        # compatibility layer writes to a placeholder ``bytes`` arg.
        return blob
    return blob


def GetTickCount64() -> int:
    """Win32 ``GetTickCount64`` -- monotonic 64-bit millisecond counter."""
    import time as _t
    return int(_t.monotonic() * 1000)


# ---------------------------------------------------------------------------
# Process / thread
# ---------------------------------------------------------------------------

def GetCurrentProcessId() -> int:
    """Win32 ``GetCurrentProcessId`` -- return the host process id."""
    return os.getpid()


def GetCurrentThreadId() -> int:
    """Win32 ``GetCurrentThreadId`` -- return a fake thread id."""
    import threading
    return threading.get_ident() & 0xFFFFFFFF


def GetCurrentProcess() -> int:
    """Win32 ``GetCurrentProcess`` -- return the pseudo-handle ``-1``."""
    return 0xFFFFFFFFFFFFFFFF


def ExitProcess(code: int) -> None:
    """Win32 ``ExitProcess`` -- sets the emulator's exit code and halts."""
    from .x86_runner import EmulatorHalt
    raise EmulatorHalt(code)


def TerminateProcess(handle: int, code: int) -> bool:
    """Win32 ``TerminateProcess`` -- return ``True`` after setting exit code."""
    from .x86_runner import EmulatorHalt
    raise EmulatorHalt(code)


def IsProcessorFeaturePresent(feat: int) -> bool:
    """Win32 ``IsProcessorFeaturePresent`` -- return ``True`` for the
    x86 features we emulate."""
    return True


def IsDebuggerPresent() -> bool:
    """Win32 ``IsDebuggerPresent`` -- return ``False``."""
    return False


# ---------------------------------------------------------------------------
# Synchronization (critical sections)
# ---------------------------------------------------------------------------

class _CritSec:
    """Placeholder for ``CRITICAL_SECTION`` -- we don't actually lock."""

    def __init__(self) -> None:
        self.locked = False


def InitializeCriticalSectionEx(crit=None, spin: int = 0,
                                flags: int = 0) -> bool:
    """Win32 ``InitializeCriticalSectionEx`` -- we treat the
    ``crit`` argument as a pass-by-reference pointer.  When the caller
    passes a concrete mutable container we populate it; otherwise we
    return ``True`` without touching memory (the emulator's Win32
    caller expects us to never raise)."""
    if crit is None:
        return True
    try:
        crit.clear()
        crit["locked"] = False
    except (AttributeError, TypeError):
        # Treat unknown ``crit`` as no-op.
        pass
    return True


def EnterCriticalSection(crit=None) -> None:
    if crit is None:
        return
    try:
        crit["locked"] = True
    except (TypeError, KeyError):
        pass


def LeaveCriticalSection(crit=None) -> None:
    if crit is None:
        return
    try:
        crit["locked"] = False
    except (TypeError, KeyError):
        pass


def DeleteCriticalSection(crit=None) -> None:
    if crit is None:
        return
    try:
        crit.clear()
    except (AttributeError, TypeError):
        pass


# ---------------------------------------------------------------------------
# Structured exception handling (SEH) -- all stubs
# ---------------------------------------------------------------------------

def InitializeSListHead(native: Optional[dict] = None) -> None:
    """Win32 ``InitializeSListHead`` -- initialise a singly-linked list."""
    if native is not None:
        native.clear()
        native["head"] = 0


def SetUnhandledExceptionFilter(handler: int = 0) -> int:
    """Win32 ``SetUnhandledExceptionFilter`` -- return the previous filter."""
    return 0


def UnhandledExceptionFilter(exc: int = 0) -> int:
    """Win32 ``UnhandledExceptionFilter`` -- return ``EXCEPTION_EXECUTE_HANDLER``."""
    return 0


def RtlUnwindEx(target_frame: int = 0, target_ip: int = 0,
               exc_record: int = 0, retval: int = 0,
               context: int = 0, history: int = 0) -> None:
    """ntdll ``RtlUnwindEx`` -- no-op stub."""
    return None


def RaiseException(code: int, flags: int = 0, nargs: int = 0,
                   args: int = 0) -> None:
    """Win32 ``RaiseException`` -- return immediately (no exception)."""
    return None


def EncodePointer(ptr: int) -> int:
    """Win32 ``EncodePointer`` -- XOR with a per-process cookie (we use 0)."""
    return ptr


def RtlLookupFunctionEntryEntry() -> int:
    """ntdll ``RtlLookupFunctionEntry`` -- no unwind info => return 0."""
    return 0


def RtlPcToFileHeader(pc: int, base_out: int = 0) -> int:
    """ntdll ``RtlPcToFileHeader`` -- return 0 (no image header)."""
    return 0


def RtlCaptureContext(ctx: int = 0) -> None:
    """ntdll ``RtlCaptureContext`` -- no-op."""
    return None


def RtlVirtualUnwind(flags: int = 0, target_ip: int = 0,
                      context: int = 0, history: int = 0,
                      handler_data: int = 0) -> int:
    """ntdll ``RtlVirtualUnwind`` -- return 0."""
    return 0


# ---------------------------------------------------------------------------
# Thread-local storage
# ---------------------------------------------------------------------------

def FlsAlloc(callback: int = 0) -> int:
    """Win32 ``FlsAlloc`` -- allocate a fake TLB index."""
    return 1


def FlsGetValue(index: int) -> int:
    """Win32 ``FlsGetValue`` -- return 0 (no slot stored)."""
    return 0


def FlsSetValue(index: int, value: int) -> bool:
    """Win32 ``FlsSetValue`` -- always return ``True``."""
    return True


def FlsFree(index: int) -> bool:
    """Win32 ``FlsFree`` -- return ``True``."""
    return True


# ---------------------------------------------------------------------------
# Heap
# ---------------------------------------------------------------------------

def HeapSize(heap: int, flags: int, ptr: int) -> int:
    """Win32 ``HeapSize`` -- return a fake size of 16 bytes."""
    return 16


def HeapReAlloc(heap: int, flags: int, ptr: int, size: int) -> int:
    """Win32 ``HeapReAlloc`` -- return the original pointer (no-op)."""
    return ptr


# ---------------------------------------------------------------------------
# Console I/O
# ---------------------------------------------------------------------------

def GetConsoleOutputCP() -> int:
    """Win32 ``GetConsoleOutputCP`` -- return the host's console codepage."""
    import sys
    return 0 if not sys.stdout else 0x6500 / 0x100  # cp -> 6500 (UTF-8 in Win10)


def GetConsoleMode(handle: int) -> int:
    """Win32 ``GetConsoleMode`` -- return ``0`` (no flags)."""
    return 0


def WriteConsoleW(handle: int, text: str, length: int,
                  written: int = 0, reserved: int = 0) -> bool:
    """Win32 ``WriteConsoleW`` -- write the UTF-16 text to stdout."""
    if handle == 0xFFFFFFF5 or handle == 0xFFFFFFF6:        # stdout/stderr
        sys.stdout.write(text)
        sys.stdout.flush()
        return True
    return False


def GetStdHandle(which: int) -> int:
    """Win32 ``GetStdHandle`` -- return pseudo-handles."""
    if which == -11:
        return 0xFFFFFFF5        # stdin
    if which == -12:
        return 0xFFFFFFF6        # stdout
    if which == -15:
        return 0xFFFFFFF7        # stderr
    return 0xFFFFFFFFFFFFFFFF


def SetStdHandle(which: int, handle: int) -> bool:
    """Win32 ``SetStdHandle`` -- return ``True``."""
    return True


def GetStartupInfoW(info: int = 0) -> None:
    """Win32 ``GetStartupInfoW`` -- no-op stub."""
    return None


def GetModuleHandleExW(which: int, name: int = 0, handle_out: int = 0) -> int:
    """Win32 ``GetModuleHandleExW`` -- return ``0``."""
    return 0


def GetModuleHandleW(name: int = 0) -> int:
    """Win32 ``GetModuleHandleW`` -- return the process module handle."""
    return _store_handle(_new_handle("module", "module"))


def GetModuleFileNameW(handle: int, buf: int = 0, size: int = 0) -> int:
    """Win32 ``GetModuleFileNameW`` -- return ``0``."""
    return 0


# ---------------------------------------------------------------------------
# File I/O (Unicode)
# ---------------------------------------------------------------------------

def CreateFileW(path: str, access: int = 0, share: int = 0,
                security: int = 0, creation: int = 0,
                attrs: int = 0, template: int = 0) -> int:
    """Win32 ``CreateFileW`` -- wrap :func:`CreateFileA`."""
    return CreateFileA(path, access, share, security, creation,
                        attrs, template)


def FindFirstFileExW(pattern: str, info_level: int = 0,
                     data: int = 0, search_op: int = 0,
                     reserved: int = 0) -> int:
    """Win32 ``FindFirstFileExW`` -- return ``-1`` (no match)."""
    return 0xFFFFFFFF


def FindNextFileW(handle: int, data: int = 0) -> bool:
    """Win32 ``FindNextFileW`` -- return ``False``."""
    return False


def FindClose(handle: int) -> bool:
    """Win32 ``FindClose`` -- return ``True``."""
    return True


def GetFileType(handle: int) -> int:
    """Win32 ``GetFileType`` -- return ``FILE_TYPE_UNKNOWN``."""
    return 0


def FlushFileBuffers(handle: int) -> bool:
    """Win32 ``FlushFileBuffers`` -- return ``True``."""
    return True


def SetFilePointerEx(handle: int, distance: int, new_pos: int = 0,
                     method: int = 0) -> bool:
    """Win32 ``SetFilePointerEx`` -- return ``True``."""
    return True


# ---------------------------------------------------------------------------
# Memory protection
# ---------------------------------------------------------------------------

def VirtualProtect(addr: int, size: int, new_protect: int,
                   old_protect: int = 0) -> bool:
    """Win32 ``VirtualProtect`` -- return ``True``."""
    return True


def LoadLibraryExW(path: str, file: int = 0, flags: int = 0) -> int:
    """Win32 ``LoadLibraryExW`` -- return a fake handle."""
    return _new_handle("library", path)


# ---------------------------------------------------------------------------
# Codepage / locale
# ---------------------------------------------------------------------------

def IsValidCodePage(cp: int) -> bool:
    """Win32 ``IsValidCodePage`` -- only UTF-16 and 1252 supported."""
    return cp in (65001, 1252, 0, 437, 850)


def GetACP() -> int:
    """Win32 ``GetACP`` -- return the host ANSI codepage."""
    import sys
    return 1252


def GetOEMCP() -> int:
    """Win32 ``GetOEMCP`` -- return the host OEM codepage."""
    return 437


def GetCPInfo(cp: int, info: int = 0) -> bool:
    """Win32 ``GetCPInfo`` -- return ``True`` for supported codepages."""
    return IsValidCodePage(cp)


def MultiByteToWideChar(cp: int, flags: int, src: bytes,
                        src_len: int, dst: int = 0, dst_len: int = 0) -> int:
    """Win32 ``MultiByteToWideChar`` -- return the number of wide chars."""
    try:
        text = src[:src_len].decode("cp" + str(cp) if cp else "ascii",
                                       errors="replace")
    except (LookupError, UnicodeDecodeError):
        text = src[:src_len].decode("ascii", errors="replace")
    return len(text)


def WideCharToMultiByte(cp: int, flags: int, src: str,
                        src_len: int, dst: int = 0, dst_len: int = 0,
                        default_char: int = 0,
                        used_default: int = 0) -> int:
    """Win32 ``WideCharToMultiByte`` -- return the number of bytes."""
    if not src:
        return 0
    try:
        encoded = src[:src_len].encode("cp" + str(cp) if cp else "ascii",
                                        errors="replace")
    except (LookupError, UnicodeEncodeError):
        encoded = src[:src_len].encode("ascii", errors="replace")
    return len(encoded)


def GetStringTypeW(type_: int, src: str, src_len: int,
                  char_type: int = 0) -> int:
    """Win32 ``GetStringTypeW`` -- return 0 (no info)."""
    return 0


def CompareStringW(locale: int, flags: int, s1: str, n1: int,
                   s2: str, n2: int) -> int:
    """Win32 ``CompareStringW`` -- return CSTR_EQUAL when the entries are equal."""
    if s1[:n1] == s2[:n2]:
        return 3   # CSTR_EQUAL
    return 1   # CSTR_LESS_THAN


def LCMapStringW(locale: int, flags: int, src: str, src_len: int,
                 dst: int = 0, dst_len: int = 0) -> int:
    """Win32 ``LCMapStringW`` -- return ``src_len`` (no mapping)."""
    return src_len


# ---------------------------------------------------------------------------
# QueryPerformance
# ---------------------------------------------------------------------------

def QueryPerformanceCounter(counter: int = 0) -> bool:
    """Win32 ``QueryPerformanceCounter`` -- return ``True`` and write a fake count."""
    import time as _t
    return True


def QueryPerformanceFrequency(freq: int = 0) -> bool:
    """Win32 ``QueryPerformanceFrequency`` -- return ``True``."""
    return True


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import struct  # noqa: E402  -- used by many stubs in this section


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
    "HeapSize": HeapSize,
    "HeapReAlloc": HeapReAlloc,
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
    "GetTickCount64": GetTickCount64,
    "Sleep": Sleep,
    "Beep": Beep,
    "GetCommandLineA": GetCommandLineA,
    "GetCommandLineW": GetCommandLineW,
    "GetVersionExA": GetVersionExA,
    "GetLastError": GetLastError,
    "SetLastError": SetLastError,
    # ---- environment variables
    "GetEnvironmentVariableA": GetEnvironmentVariableA,
    "SetEnvironmentVariableA": SetEnvironmentVariableA,
    "GetEnvironmentStringsA": GetEnvironmentStringsA,
    "ExpandEnvironmentStringsA": ExpandEnvironmentStringsA,
    "GetEnvironmentVariableW": GetEnvironmentVariableW,
    "SetEnvironmentVariableW": SetEnvironmentVariableW,
    "ExpandEnvironmentStringsW": ExpandEnvironmentStringsW,
    "GetCurrentDirectoryA": GetCurrentDirectoryA,
    "SetCurrentDirectoryA": SetCurrentDirectoryA,
    "GetComputerNameA": GetComputerNameA,
    "GetUserNameA": GetUserNameA,
    "GetEnvironmentStringsW": GetEnvironmentStringsA,
    "FreeEnvironmentStringsW": lambda h: True,
    "GetSystemTimeAsFileTime": GetSystemTimeAsFileTime,
    "InitializeSListHead": InitializeSListHead,
    "SetUnhandledExceptionFilter": SetUnhandledExceptionFilter,
    "UnhandledExceptionFilter": UnhandledExceptionFilter,
    "RtlUnwindEx": RtlUnwindEx,
    "RaiseException": RaiseException,
    "EncodePointer": EncodePointer,
    "RtlLookupFunctionEntry": RtlLookupFunctionEntryEntry,
    "RtlPcToFileHeader": RtlPcToFileHeader,
    "RtlCaptureContext": RtlCaptureContext,
    "RtlVirtualUnwind": RtlVirtualUnwind,
    "FlsAlloc": FlsAlloc,
    "FlsGetValue": FlsGetValue,
    "FlsSetValue": FlsSetValue,
    "FlsFree": FlsFree,
    "EnterCriticalSection": EnterCriticalSection,
    "LeaveCriticalSection": LeaveCriticalSection,
    "InitializeCriticalSectionEx": InitializeCriticalSectionEx,
    "DeleteCriticalSection": DeleteCriticalSection,
    "GetStdHandle": GetStdHandle,
    "WriteConsoleW": WriteConsoleW,
    "GetConsoleOutputCP": GetConsoleOutputCP,
    "GetConsoleMode": GetConsoleMode,
    "SetStdHandle": SetStdHandle,
    "GetStartupInfoW": GetStartupInfoW,
    "GetModuleHandleExW": GetModuleHandleExW,
    "GetModuleHandleW": GetModuleHandleW,
    "GetModuleFileNameW": GetModuleFileNameW,
    "CreateFileW": CreateFileW,
    "FindFirstFileExW": FindFirstFileExW,
    "FindNextFileW": FindNextFileW,
    "FindClose": FindClose,
    "GetFileType": GetFileType,
    "FlushFileBuffers": FlushFileBuffers,
    "SetFilePointerEx": SetFilePointerEx,
    "VirtualProtect": VirtualProtect,
    "LoadLibraryExW": LoadLibraryExW,
    "IsProcessorFeaturePresent": IsProcessorFeaturePresent,
    "IsDebuggerPresent": IsDebuggerPresent,
    "TerminateProcess": TerminateProcess,
    "IsValidCodePage": IsValidCodePage,
    "GetACP": GetACP,
    "GetOEMCP": GetOEMCP,
    "GetCPInfo": GetCPInfo,
    "MultiByteToWideChar": MultiByteToWideChar,
    "WideCharToMultiByte": WideCharToMultiByte,
    "GetStringTypeW": GetStringTypeW,
    "CompareStringW": CompareStringW,
    "LCMapStringW": LCMapStringW,
    "QueryPerformanceCounter": QueryPerformanceCounter,
    "QueryPerformanceFrequency": QueryPerformanceFrequency,
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
