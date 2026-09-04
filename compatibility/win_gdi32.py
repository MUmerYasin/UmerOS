"""
Umer OS /compatibility/win_gdi32 — gdi32.dll API stubs
====================================================

``gdi32.dll`` is the Windows GDI (Graphics Device Interface).  It
exports the primitives for drawing on a DC (device context):
pens, brushes, fonts, bitmaps, regions, paths.  ~600 functions in
the real DLL; this module provides a useful stub subset.

Pure-Python: we don't draw anything; we just keep a registry of
"what would have been created" so callers can release resources
deterministically.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/gdi/

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger("UmerOS.Compat.Gdi32")

_OBJECTS: Dict[int, str] = {}
_NEXT_HANDLE = 0x100


def _alloc(kind: str) -> int:
    global _NEXT_HANDLE
    _NEXT_HANDLE += 1
    _OBJECTS[_NEXT_HANDLE] = kind
    return _NEXT_HANDLE


def _release(handle: int) -> bool:
    return _OBJECTS.pop(handle, None) is not None


# --- Device contexts -------------------------------------------------------

def GetDC(hwnd: int) -> int:
    return _alloc(f"dc({hwnd})")


def ReleaseDC(hwnd: int, hdc: int) -> int:
    return 1 if _release(hdc) else 0


# --- Pens & brushes --------------------------------------------------------

def CreatePen(style: int, width: int, color: int) -> int:
    return _alloc(f"pen({style},{width},0x{color:08X})")


def CreateSolidBrush(color: int) -> int:
    return _alloc(f"brush(0x{color:08X})")


def DeleteObject(handle: int) -> bool:
    return _release(handle)


def SelectObject(hdc: int, obj: int) -> Optional[int]:
    """Returns the previously selected object, or None on failure."""
    if obj in _OBJECTS:
        return obj
    return None


# --- Drawing primitives (no-op stubs) -------------------------------------

def SetPixel(hdc: int, x: int, y: int, color: int) -> int:
    return color


def GetPixel(hdc: int, x: int, y: int) -> int:
    return 0


def MoveToEx(hdc: int, x: int, y: int, prev: Optional[list]) -> bool:
    return True


def LineTo(hdc: int, x: int, y: int) -> bool:
    return True


def Rectangle(hdc: int, left: int, top: int, right: int, bottom: int) -> bool:
    return True


def Ellipse(hdc: int, left: int, top: int, right: int, bottom: int) -> bool:
    return True


def TextOutA(hdc: int, x: int, y: int, text: str) -> bool:
    log.debug("TextOut(%d,%d,%r)", x, y, text)
    return True


# --- Fonts -----------------------------------------------------------------

def CreateFontA(height: int, width: int, esc: int, ori: int, weight: int,
                italic: int, underline: int, strike: int, charset: int,
                out: int, clip: int, quality: int, pitch: int, face: str) -> int:
    return _alloc(f"font({face})")


# --- Bitmaps --------------------------------------------------------------

def CreateCompatibleBitmap(hdc: int, w: int, h: int) -> int:
    return _alloc(f"bmp({w}x{h})")


# --- Aggregate ------------------------------------------------------------

EXPORTS: Dict[str, Any] = {
    "GetDC": GetDC,
    "ReleaseDC": ReleaseDC,
    "CreatePen": CreatePen,
    "CreateSolidBrush": CreateSolidBrush,
    "DeleteObject": DeleteObject,
    "SelectObject": SelectObject,
    "SetPixel": SetPixel,
    "GetPixel": GetPixel,
    "MoveToEx": MoveToEx,
    "LineTo": LineTo,
    "Rectangle": Rectangle,
    "Ellipse": Ellipse,
    "TextOutA": TextOutA,
    "CreateFontA": CreateFontA,
    "CreateCompatibleBitmap": CreateCompatibleBitmap,
}


def _selftest() -> bool:
    dc = GetDC(0)
    if dc == 0:
        return False
    if not ReleaseDC(0, dc):
        return False
    pen = CreatePen(0, 1, 0)
    if pen == 0:
        return False
    if not DeleteObject(pen):
        return False
    bm = CreateCompatibleBitmap(0, 100, 100)
    if not DeleteObject(bm):
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
