"""
Umer OS /compatibility/win_shell32 — shell32.dll folder-path API
=================================================================

``shell32.dll`` is the Windows shell library.  This module implements the
folder-location part of its surface -- the APIs an installer or a
framework calls to discover where Windows keeps its well-known
folders.

Two generations of API live here:

``SHGetFolderPath`` / ``SHGetSpecialFolderPath``
    The legacy **CSIDL** interface.  A numeric constant identifies the
    folder.  Superseded on Vista but still widely called.

``SHGetKnownFolderPath`` / ``SHSetKnownFolderPath``
    The modern **KNOWNFOLDERID** interface.  A GUID identifies the
    folder.  This is what Microsoft recommends for all new code.

Folder paths are resolved against the :mod:`compatibility.environment`
block, so a caller can model a machine with different roots simply by
editing the environment.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetfolderpatha
* https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath
* https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shsetknownfolderpath
* https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid
* https://learn.microsoft.com/en-us/windows/win32/shell/csidl

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union

from .knownfolders import (
    CSIDL_TO_KNOWN_FOLDER,
    KNOWN_FOLDERS,
    Csidl,
    CsidlFlag,
    KnownFolder,
    KnownFolderFlag,
    resolve_csidl,
    resolve_known_folder,
)
from .win_guid import Guid

log = logging.getLogger("UmerOS.Compat.Shell32")

#: What a caller may hand us as a folder identifier: a :class:`Guid`, a
#: GUID string, or a ``FOLDERID_*`` constant name.
FolderId = Union[Guid, str, KnownFolder]


# ---------------------------------------------------------------------------
# Per-machine overrides
# ---------------------------------------------------------------------------

#: Paths installed by :func:`SHSetKnownFolderPath`, keyed by GUID.
#: A real Windows stores these in
#: ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders``.
_KNOWN_FOLDER_OVERRIDES: Dict[str, str] = {}


def set_known_folder_override(guid: str, path: str) -> None:
    """Force ``guid`` to resolve to ``path`` (test / migration helper)."""
    _KNOWN_FOLDER_OVERRIDES[guid.upper()] = path


def clear_known_folder_overrides() -> None:
    """Drop every :func:`set_known_folder_override` entry."""
    _KNOWN_FOLDER_OVERRIDES.clear()


# ---------------------------------------------------------------------------
# Identifier helpers
# ---------------------------------------------------------------------------

def _guid_key(rfid: FolderId) -> str:
    """Normalise any folder identifier to an upper-case GUID string."""
    if isinstance(rfid, Guid):
        return str(rfid).upper()
    text = str(rfid)
    bare = text.strip().strip("{}").upper()
    for kf in KNOWN_FOLDERS.values():
        if kf.guid.strip("{}").upper() == bare:
            return kf.guid.upper()
        if kf.name.upper() == text.upper():
            return kf.guid.upper()
    raise KeyError(f"unknown known-folder identifier: {rfid!r}")


def _folder_name(rfid: FolderId) -> str:
    """The ``FOLDERID_*`` constant name for ``rfid``."""
    if isinstance(rfid, KnownFolder):
        return rfid.name
    text = str(rfid)
    for kf in KNOWN_FOLDERS.values():
        if kf.name.upper() == text.upper():
            return kf.name
    bare = text.strip().strip("{}").upper()
    for kf in KNOWN_FOLDERS.values():
        if kf.guid.strip("{}").upper() == bare:
            return kf.name
    raise KeyError(f"unknown known-folder identifier: {rfid!r}")


# ---------------------------------------------------------------------------
# CSIDL interface
# ---------------------------------------------------------------------------

def SHGetFolderPathA(hwnd: int, csidl: int, hToken: int,
                     dwFlags: int = 0) -> str:
    """Resolve a legacy ``CSIDL`` folder.

    Returns the folder path, or an empty string when the CSIDL is
    unknown or cannot be resolved -- matching the Win32 convention of
    returning an empty buffer rather than raising.
    """
    value = int(csidl) & ~int(CsidlFlag.MASK)
    try:
        path = resolve_csidl(value)
    except KeyError:
        log.debug("SHGetFolderPathA: unknown CSIDL 0x%04X", value)
        return ""
    except ValueError as exc:
        log.debug("SHGetFolderPathA: %s", exc)
        return ""
    return path


def SHGetFolderPathW(hwnd: int, csidl: int, hToken: int,
                     dwFlags: int = 0) -> str:
    """Wide-char variant of :func:`SHGetFolderPathA` (same result)."""
    return SHGetFolderPathA(hwnd, csidl, hToken, dwFlags)


def SHGetSpecialFolderPathA(hwnd: int, csidl: int, dwFlags: int = 0) -> str:
    """Resolve a special folder without a token."""
    return SHGetFolderPathA(hwnd, csidl, 0, dwFlags)


def SHGetSpecialFolderPathW(hwnd: int, csidl: int, dwFlags: int = 0) -> str:
    """Wide-char variant of :func:`SHGetSpecialFolderPathA`."""
    return SHGetFolderPathA(hwnd, csidl, 0, dwFlags)


def SHGetSpecialFolderLocation(hwnd: int, csidl: int,
                                dwFlags: int = 0) -> int:
    """Return an opaque pointer to the folder's ``IShellFolder``.

    The pure-Python layer has no COM object graph, so this returns a
    synthetic, stable handle instead of ``NULL``.  Callers that only
    test for failure are satisfied; callers that dereference it are not.
    """
    value = int(csidl) & ~int(CsidlFlag.MASK)
    if value not in CSIDL_TO_KNOWN_FOLDER:
        return 0
    return 0x5F000000 | value


# ---------------------------------------------------------------------------
# KNOWNFOLDERID interface
# ---------------------------------------------------------------------------

def SHGetKnownFolderPath(rfid: FolderId, dwFlags: int = 0,
                          hToken: int = 0) -> str:
    """Resolve a Known Folder to its path.

    ``rfid`` may be a :class:`~compatibility.win_guid.Guid`, a GUID
    string, or a ``FOLDERID_*`` constant name.
    """
    try:
        name = _folder_name(rfid)
    except KeyError as exc:
        log.debug("SHGetKnownFolderPath: %s", exc)
        return ""
    kf = KNOWN_FOLDERS[name]
    override = _KNOWN_FOLDER_OVERRIDES.get(kf.guid.upper())
    if override:
        return override
    try:
        return resolve_known_folder(name)
    except ValueError as exc:
        log.debug("SHGetKnownFolderPath: %s", exc)
        return ""


def SHSetKnownFolderPath(rfid: FolderId, dwFlags: int = 0,
                          hToken: int = 0, path: str = "") -> bool:
    """Point a Known Folder at ``path``.

    Returns ``True`` on success.  The write is recorded in the
    per-machine override table so a subsequent
    :func:`SHGetKnownFolderPath` sees it.
    """
    try:
        name = _folder_name(rfid)
    except KeyError as exc:
        log.debug("SHSetKnownFolderPath: %s", exc)
        return False
    if not path:
        _KNOWN_FOLDER_OVERRIDES.pop(KNOWN_FOLDERS[name].guid.upper(), None)
        return True
    _KNOWN_FOLDER_OVERRIDES[KNOWN_FOLDERS[name].guid.upper()] = path
    return True


def SHGetKnownFolderIDList(rfid: FolderId, dwFlags: int = 0,
                            hToken: int = 0) -> int:
    """Return an opaque ``PIDLIST_ABSOLUTE`` handle for the folder.

    As with :func:`SHGetSpecialFolderLocation`, the handle is synthetic
    -- there is no shell item graph in the pure-Python layer.
    """
    try:
        name = _folder_name(rfid)
    except KeyError:
        return 0
    kf = KNOWN_FOLDERS[name]
    return 0x6F000000 | (abs(hash(kf.guid)) & 0xFFFF)


def SHChangeNotify(wEventId: int, dwFlags: int, dwItem1: int,
                   dwItem2: int) -> None:
    """Notify the shell that something changed (no-op)."""
    log.debug("SHChangeNotify: event=0x%X", wEventId)


# ---------------------------------------------------------------------------
# Aggregate public surface
# ---------------------------------------------------------------------------

EXPORTS: Dict[str, Any] = {
    "SHGetFolderPathA": SHGetFolderPathA,
    "SHGetFolderPathW": SHGetFolderPathW,
    "SHGetSpecialFolderPathA": SHGetSpecialFolderPathA,
    "SHGetSpecialFolderPathW": SHGetSpecialFolderPathW,
    "SHGetSpecialFolderLocation": SHGetSpecialFolderLocation,
    "SHGetKnownFolderPath": SHGetKnownFolderPath,
    "SHSetKnownFolderPath": SHSetKnownFolderPath,
    "SHGetKnownFolderIDList": SHGetKnownFolderIDList,
    "SHChangeNotify": SHChangeNotify,
}


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    # Legacy CSIDL lookup.
    appdata = SHGetFolderPathA(0, int(Csidl.APPDATA), 0, 0)
    if not appdata:
        return False
    if not appdata.lower().endswith("appdata\\roaming"):
        log.debug("CSIDL_APPDATA = %r", appdata)
        return False

    # The CSIDL flag bits must be masked off before lookup.
    flagged = SHGetFolderPathA(0, int(Csidl.APPDATA) | int(CsidlFlag.CREATE),
                               0, 0)
    if flagged != appdata:
        return False

    # Modern Known Folder lookup, by name and by GUID.
    documents_guid = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"
    by_name = SHGetKnownFolderPath("FOLDERID_Documents")
    by_guid = SHGetKnownFolderPath(documents_guid)
    if not by_name or by_name != by_guid:
        return False

    # A Guid object must work too.
    by_obj = SHGetKnownFolderPath(Guid.from_string(documents_guid))
    if by_obj != by_name:
        return False

    # Unknown identifiers fail soft, the way the Win32 API does.
    if SHGetKnownFolderPath("{00000000-0000-0000-0000-000000000000}") != "":
        return False
    if SHGetFolderPathA(0, 0x7FFF, 0, 0) != "":
        return False

    # Virtual folders come back as shell namespace paths.
    recycle = SHGetKnownFolderPath("FOLDERID_RecycleBinFolder")
    if not recycle.startswith("::"):
        return False

    # Writing a Known Folder is observable.
    if not SHSetKnownFolderPath("FOLDERID_Documents", 0, 0, r"C:\Docs"):
        return False
    if SHGetKnownFolderPath("FOLDERID_Documents") != r"C:\Docs":
        return False
    SHSetKnownFolderPath("FOLDERID_Documents", 0, 0, "")
    if SHGetKnownFolderPath("FOLDERID_Documents") == r"C:\Docs":
        return False

    # The special-folder wrapper agrees with the CSIDL lookup.
    if SHGetSpecialFolderPathA(0, int(Csidl.LOCAL_APPDATA)) != \
            SHGetFolderPathA(0, int(Csidl.LOCAL_APPDATA), 0, 0):
        return False

    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
