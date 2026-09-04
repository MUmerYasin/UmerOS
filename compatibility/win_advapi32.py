"""
Umer OS /compatibility/win_advapi32 — advapi32.dll API stubs
=========================================================

``advapi32.dll`` is the Windows Advanced API.  It owns:

* the **registry client** (``RegOpenKey``, ``RegQueryValue``, ...),
* the **service control manager** (``OpenSCManager``, ``CreateService``,
  ``StartService``),
* **security / ACL** primitives (``GetTokenInformation``,
  ``AdjustTokenPrivileges``),
* **crypto** entry points (``CryptAcquireContext``, etc.).

This module provides a focused stub subset.  Higher-fidelity
implementations (e.g. actually running a service) are outside
the scope of the pure-Python loader.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger("UmerOS.Compat.AdvApi32")

# Reuse the Win32 error codes for return values.
from .winerror import (
    ERROR_SUCCESS,
    ERROR_FILE_NOT_FOUND,
    ERROR_ACCESS_DENIED,
    ERROR_INVALID_PARAMETER,
    ERROR_MORE_DATA,
)


# ---------------------------------------------------------------------------
# Registry client
# ---------------------------------------------------------------------------

_REG_HANDLES: Dict[int, str] = {}
_NEXT_HKEY = 0x100


def RegOpenKeyA(parent: int, sub: str) -> int:
    """Open a registry key (stub).  Returns 0 (= ERROR_SUCCESS) on success."""
    global _NEXT_HKEY
    full = f"hkey={parent:#x}\\{sub}"
    _NEXT_HKEY += 1
    _REG_HANDLES[_NEXT_HKEY] = full
    return _NEXT_HKEY


def RegCloseKey(hkey: int) -> int:
    _REG_HANDLES.pop(hkey, None)
    return ERROR_SUCCESS


def RegQueryValueExA(hkey: int, value: str) -> int:
    """Look up a registry value (stub: never found)."""
    return ERROR_FILE_NOT_FOUND


def RegSetValueExA(hkey: int, value: str, data: bytes) -> int:
    """Set a registry value (stub: always succeed)."""
    return ERROR_SUCCESS


def RegEnumValueA(hkey: int, index: int) -> int:
    """Enumerate values (stub: no more items)."""
    return ERROR_FILE_NOT_FOUND


def RegEnumKeyExA(hkey: int, index: int) -> int:
    """Enumerate subkeys (stub: no more items)."""
    return ERROR_FILE_NOT_FOUND


# ---------------------------------------------------------------------------
# Service control manager
# ---------------------------------------------------------------------------

def OpenSCManagerA(machine: Optional[str], db: Optional[str],
                   access: int) -> int:
    """Open a handle to the SCM.  Returns 0 on failure (no real SCM)."""
    return 0


def CloseServiceHandle(handle: int) -> int:
    return 0


def CreateServiceA(scm: int, name: str, display: str,
                   access: int, svc_type: int, start_type: int,
                   err: int, path: str, load_order: Optional[str],
                   tag_id: Optional[str], deps: Optional[str],
                   account: Optional[str], password: Optional[str]) -> int:
    return 0


def OpenServiceA(scm: int, name: str, access: int) -> int:
    return 0


def StartServiceA(svc: int, argc: int, argv: Any) -> int:
    return 0


def QueryServiceStatus(svc: int) -> Dict[str, int]:
    return {
        "dwServiceType": 0x10,     # SERVICE_WIN32_OWN_PROCESS
        "dwCurrentState": 0x04,    # SERVICE_RUNNING
        "dwControlsAccepted": 0,
        "dwWin32ExitCode": 0,
        "dwServiceSpecificExitCode": 0,
        "dwCheckPoint": 0,
        "dwWaitHint": 0,
    }


# ---------------------------------------------------------------------------
# Security / tokens
# ---------------------------------------------------------------------------

def GetCurrentProcessToken() -> int:
    """Return a fake token handle."""
    return 0x100


def GetTokenInformation(token: int, info_class: int,
                        buffer_size: int) -> int:
    return ERROR_SUCCESS


def AdjustTokenPrivileges(token: int, disable_all: bool,
                          new_state: Any, buffer_length: int,
                          previous_state: Any, return_length: Any) -> int:
    return ERROR_SUCCESS


def ImpersonateLoggedOnUser(token: int) -> int:
    return ERROR_SUCCESS


def RevertToSelf() -> int:
    return ERROR_SUCCESS


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

EXPORTS: Dict[str, Any] = {
    "RegOpenKeyA": RegOpenKeyA,
    "RegCloseKey": RegCloseKey,
    "RegQueryValueExA": RegQueryValueExA,
    "RegSetValueExA": RegSetValueExA,
    "RegEnumValueA": RegEnumValueA,
    "RegEnumKeyExA": RegEnumKeyExA,
    "OpenSCManagerA": OpenSCManagerA,
    "CloseServiceHandle": CloseServiceHandle,
    "CreateServiceA": CreateServiceA,
    "OpenServiceA": OpenServiceA,
    "StartServiceA": StartServiceA,
    "QueryServiceStatus": QueryServiceStatus,
    "GetCurrentProcessToken": GetCurrentProcessToken,
    "GetTokenInformation": GetTokenInformation,
    "AdjustTokenPrivileges": AdjustTokenPrivileges,
    "ImpersonateLoggedOnUser": ImpersonateLoggedOnUser,
    "RevertToSelf": RevertToSelf,
}


def _selftest() -> bool:
    h = RegOpenKeyA(0x80000002, r"SOFTWARE\UmerOS")
    if h == 0:
        return False
    if RegCloseKey(h) != ERROR_SUCCESS:
        return False
    if RegQueryValueExA(h, "x") != ERROR_FILE_NOT_FOUND:
        return False
    if OpenSCManagerA(None, None, 0) != 0:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
