"""
Umer OS /compatibility/win_user32 — user32.dll API stubs
=======================================================

``user32.dll`` is the Windows USER subsystem.  It owns the window
manager, message loop, controls, input handling, clipboard, hooks
and a long list of small helpers.  The real DLL exports ~900
functions; this module provides a focused subset that the
pure-Python loader can satisfy to let a stub call site keep going.

The focus is on **callable stubs** that log the call, validate
the basic argument shape, and return a *default* value
(``FALSE`` / ``NULL`` / 0).  Higher-fidelity windowing would
require hooking into a real display server (X11 / Wayland / native
HID) which is outside the scope of this module.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/winuser/

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.User32")


# ---------------------------------------------------------------------------
# Fake message queue
# ---------------------------------------------------------------------------

@dataclass
class Msg:
    """A stand-in for a Windows ``MSG`` structure."""

    hwnd: int
    message: int
    wparam: int
    lparam: int
    time: int
    pt_x: int = 0
    pt_y: int = 0


_MESSAGE_QUEUE: list = []


def PostMessageA(hwnd: int, msg: int, wparam: int, lparam: int) -> bool:
    """Append a message to the global queue (no thread affinity)."""
    _MESSAGE_QUEUE.append(Msg(hwnd, msg, wparam, lparam, time=0))
    return True


def GetMessageA(msg: Optional[Msg], hwnd: int, min_: int, max_: int) -> bool:
    """Pop a message from the queue.  Returns False (= WM_QUIT) on empty."""
    if not _MESSAGE_QUEUE:
        return False
    m = _MESSAGE_QUEUE.pop(0)
    if msg is not None:
        msg.hwnd = m.hwnd
        msg.message = m.message
        msg.wparam = m.wparam
        msg.lparam = m.lparam
        msg.time = m.time
        msg.pt_x = m.pt_x
        msg.pt_y = m.pt_y
    return True


def DispatchMessageA(msg) -> int:
    """Pass-through dispatcher (no-op in the pure-Python loader)."""
    return 0


def TranslateMessage(msg) -> bool:
    """Pass-through translator (no-op in the pure-Python loader)."""
    return False


# ---------------------------------------------------------------------------
# Windows & classes
# ---------------------------------------------------------------------------

WINDOW_CLASSES: Dict[str, Dict] = {}
_NEXT_HWND = 0x100


def RegisterClassExA(wcex) -> int:
    """Register a window class.  Returns a class atom."""
    WINDOW_CLASSES[wcex.lpszClassName] = wcex
    return 0xC000 + len(WINDOW_CLASSES)


def CreateWindowExA(ex_style: int, class_name: str, window_name: str,
                    style: int, x: int, y: int, w: int, h: int,
                    parent: int, menu: int, instance: int, param: int) -> int:
    """Create a window (returns a fake HWND)."""
    global _NEXT_HWND
    if class_name not in WINDOW_CLASSES:
        return 0    # HWND is null on failure
    _NEXT_HWND += 1
    return _NEXT_HWND


def DestroyWindow(hwnd: int) -> bool:
    return hwnd != 0


def ShowWindow(hwnd: int, cmd: int) -> bool:
    return hwnd != 0


def UpdateWindow(hwnd: int) -> bool:
    return hwnd != 0


def GetMessagePos() -> int:
    """Return the current message position (x << 16 | y)."""
    return 0


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

def GetKeyState(vkey: int) -> int:
    """Return the key state (high bit = down, low bit = toggled)."""
    return 0


def GetAsyncKeyState(vkey: int) -> int:
    return 0


def GetCursorPos() -> Tuple[int, int]:
    """Return the cursor position (0, 0) in screen coordinates."""
    return (0, 0)


def SetCursorPos(x: int, y: int) -> bool:
    return True


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def MessageBoxA(hwnd: int, text: str, caption: str, type_: int) -> int:
    """Display a modal message box.  Pure-Python: just log + return IDOK."""
    log.info("MessageBox: %s -- %s", caption, text)
    return 1    # IDOK


def GetSystemMetrics(index: int) -> int:
    """Return a fake system metric.  Most callers expect 0/1/16/32 etc."""
    table = {0: 1024, 1: 768, 16: 16, 17: 16, 32: 256, 33: 32}
    return table.get(index, 0)


# ---------------------------------------------------------------------------
# Aggregate public surface
# ---------------------------------------------------------------------------

EXPORTS: Dict[str, Any] = {
    "PostMessageA": PostMessageA,
    "GetMessageA": GetMessageA,
    "DispatchMessageA": DispatchMessageA,
    "TranslateMessage": TranslateMessage,
    "RegisterClassExA": RegisterClassExA,
    "CreateWindowExA": CreateWindowExA,
    "DestroyWindow": DestroyWindow,
    "ShowWindow": ShowWindow,
    "UpdateWindow": UpdateWindow,
    "GetMessagePos": GetMessagePos,
    "GetKeyState": GetKeyState,
    "GetAsyncKeyState": GetAsyncKeyState,
    "GetCursorPos": GetCursorPos,
    "SetCursorPos": SetCursorPos,
    "MessageBoxA": MessageBoxA,
    "GetSystemMetrics": GetSystemMetrics,
}


def _selftest() -> bool:
    # Register a class, create a window, post a message, pump it.
    @dataclass
    class FakeWcex:
        lpszClassName: str
        style: int = 0
        lpfnWndProc: Optional[object] = None
        cbClsExtra: int = 0
        cbWndExtra: int = 0
        hInstance: int = 0
        hIcon: int = 0
        hCursor: int = 0
        hbrBackground: int = 0
        lpszMenuName: str = ""
        hIconSm: int = 0
    atom = RegisterClassExA(FakeWcex(lpszClassName="UmerOSWindow"))
    if atom <= 0:
        return False
    hwnd = CreateWindowExA(0, "UmerOSWindow", "Test", 0, 0, 0, 100, 100, 0, 0, 0, 0)
    if hwnd == 0:
        return False
    if not PostMessageA(hwnd, 0x0001, 0, 0):    # WM_CREATE
        return False
    msg = Msg(hwnd=0, message=0, wparam=0, lparam=0, time=0)
    if not GetMessageA(msg, 0, 0, 0):
        return False
    if msg.message != 0x0001:
        return False
    if GetSystemMetrics(0) != 1024:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
