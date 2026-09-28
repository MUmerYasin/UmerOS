"""
Umer OS /compatibility/msi_runtime — msi.dll symbol surface
==========================================================

Pure-Python implementation of the Win32 Installer runtime surface
that preflight code (and most custom-action DLLs) uses to talk to
MSI.

A full MSI engine is out of scope, but the surface area is small
enough to satisfy the preflight checks ``MsiGetProperty``,
``MsiSetProperty``, ``MsiOpenPackage`` perform when custom actions
look up installation directory, log file paths, etc.

The exposed functions live in an in-memory package registry
(:class:`MsiPackage`) keyed by the package code.  Properties are
just a ``dict[str, str]`` -- the real MSI engine has 200+ built-in
properties and a custom-action invocation stack we don't
replicate.  Each function returns an *unsigned int* HRESULT-like
status code (Win32: ``ERROR_SUCCESS`` = 0, ``E_FAIL`` = 0x80004005,
``ERROR_INVALID_PARAMETER`` = 87, ``ERROR_INSTALL_PACKAGE_NOT_FOUND``
= 1615, etc.).

References
----------

* https://learn.microsoft.com/en-us/windows/win32/msi/portal

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.Msi")

# ---------------------------------------------------------------------------
# Win32 status codes (MSI subset)
# ---------------------------------------------------------------------------

ERROR_SUCCESS                  = 0
ERROR_INVALID_PARAMETER        = 87
ERROR_INSTALL_PACKAGE_NOT_FOUND = 1615
ERROR_INSTALL_PACKAGE_OPEN     = 1619
ERROR_INSTALL_PACKAGE_INVALID   = 1620
ERROR_INSTALL_FAILURE          = 1603
E_FAIL                        = 0x80004005
E_INVALIDARG                  = 0x80070057

# Install state for features and components.
INSTALLSTATE_NOTUSED          = -7
INSTALLSTATE_BADCONFIG        = -6
INSTALLSTATE_INCOMPLETE       = -5
INSTALLSTATE_SOURCEABSENT     = -4
INSTALLSTATE_MOREDATA         = -3
INSTALLSTATE_INVALIDARG       = -2
INSTALLSTATE_UNKNOWN          = -1
INSTALLSTATE_BROKEN           = 0
INSTALLSTATE_ADVERTISED       = 1
INSTALLSTATE_REMOVED          = 1
INSTALLSTATE_ABSENT           = 2
INSTALLSTATE_LOCAL            = 3
INSTALLSTATE_SOURCE           = 4
INSTALLSTATE_DEFAULT          = 5

# Built-in MSI properties that preflight code commonly queries.
BUILTIN_PROPERTIES = {
    "ProductName":         "UmerOS Installer Package",
    "ProductCode":         "",
    "ProductVersion":      "1.0.0",
    "Manufacturer":        "UmerOS Project",
    "INSTALLDIR":          "C:\\Program Files\\UmerOS",
    "INSTALLDIR64":        "C:\\Program Files\\UmerOS",
    "INSTALLDIR32":        "C:\\Program Files (x86)\\UmerOS",
    "SourceDir":           "",
    "OriginalDatabase":    "",
    "Database":            "",
    "UILevel":             "5",        # full UI
    "LogFile":             "",
    "MsiHiddenProperties": "",
    "Action":              "",
}


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass
class MsiPackage:
    """A handle to a "loaded" MSI package."""

    code: str
    name: str = ""
    version: str = "1.0.0"
    product_code: str = ""
    properties: Dict[str, str] = field(default_factory=dict)
    features: Dict[str, int] = field(default_factory=dict)
    closed: bool = False


_PACKAGES: Dict[str, MsiPackage] = {}
_PACKAGE_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def MsiOpenPackageA(package_path: str, handle_out: list) -> int:
    """Open an MSI package.

    We don't actually parse the package file -- we accept any path
    and create an in-memory record with built-in defaults plus a
    caller-provided name.

    ``handle_out`` is a single-element list the function appends the
    opaque handle to (Win32 uses an out-parameter).
    """
    if not package_path:
        return ERROR_INVALID_PARAMETER
    code = uuid.uuid5(uuid.NAMESPACE_URL, package_path).hex
    pkg = MsiPackage(code=code, name=os.path.basename(package_path),
                     product_code=f"{{{uuid.uuid5(uuid.NAMESPACE_URL, package_path + ':product')}}}".upper())
    pkg.properties.update(BUILTIN_PROPERTIES)
    pkg.properties["OriginalDatabase"] = package_path
    pkg.properties["Database"] = package_path
    pkg.properties["SourceDir"] = os.path.dirname(package_path) + "\\"
    pkg.properties["ProductCode"] = pkg.product_code
    with _PACKAGE_LOCK:
        _PACKAGES[code] = pkg
    handle_out.append(code)
    return ERROR_SUCCESS


def MsiOpenPackageW(package_path: str, handle_out: list) -> int:
    """Wide-char variant; same semantics."""
    return MsiOpenPackageA(package_path, handle_out)


def MsiCloseHandle(handle: str) -> int:
    pkg = _PACKAGES.get(handle)
    if pkg is None:
        return ERROR_INVALID_PARAMETER
    pkg.closed = True
    with _PACKAGE_LOCK:
        _PACKAGES.pop(handle, None)
    return ERROR_SUCCESS


def MsiGetPropertyA(handle: str, name: str, value_buf: list
                     ) -> Tuple[int, str]:
    """``MsiGetPropertyA`` -- returns ``(status, value)``.

    ``value_buf`` is a single-element list the function *may* use to
    return a Win32-style fixed-length buffer (we return the value
    in the tuple instead).
    """
    pkg = _PACKAGES.get(handle)
    if pkg is None or pkg.closed:
        return (ERROR_INSTALL_PACKAGE_OPEN, "")
    if not name:
        return (ERROR_INVALID_PARAMETER, "")
    val = pkg.properties.get(name, "")
    if value_buf is not None:
        value_buf.append(val)
    return (ERROR_SUCCESS, val)


def MsiSetPropertyA(handle: str, name: str, value: str) -> int:
    pkg = _PACKAGES.get(handle)
    if pkg is None or pkg.closed:
        return ERROR_INSTALL_PACKAGE_OPEN
    if not name:
        return ERROR_INVALID_PARAMETER
    pkg.properties[name] = value
    return ERROR_SUCCESS


def MsiGetFeatureStateA(handle: str, feature: str
                        ) -> Tuple[int, int]:
    pkg = _PACKAGES.get(handle)
    if pkg is None or pkg.closed:
        return (ERROR_INSTALL_PACKAGE_OPEN, INSTALLSTATE_UNKNOWN)
    state = pkg.features.get(feature, INSTALLSTATE_UNKNOWN)
    return (ERROR_SUCCESS, state)


def MsiSetFeatureStateA(handle: str, feature: str, state: int) -> int:
    pkg = _PACKAGES.get(handle)
    if pkg is None or pkg.closed:
        return ERROR_INSTALL_PACKAGE_OPEN
    pkg.features[feature] = state
    return ERROR_SUCCESS


def MsiDoActionA(handle: str, action: str) -> int:
    """``MsiDoActionA`` -- record the requested action in the package.

    A real MSI engine would invoke the action DLL; we just log the
    call so preflight code that asks "did you do X?" can find it.
    """
    pkg = _PACKAGES.get(handle)
    if pkg is None or pkg.closed:
        return ERROR_INSTALL_PACKAGE_OPEN
    pkg.properties["Action"] = action
    log.info("MsiDoAction(%s, %s)", handle, action)
    return ERROR_SUCCESS


def MsiSetInstallLevel(handle: str, level: int) -> int:
    pkg = _PACKAGES.get(handle)
    if pkg is None or pkg.closed:
        return ERROR_INSTALL_PACKAGE_OPEN
    pkg.properties["InstallLevel"] = str(level)
    return ERROR_SUCCESS


def MsiSetMode(handle: str, mode: int, value: int) -> int:
    """No-op stub; we don't model internal MSI engine flags."""
    return ERROR_SUCCESS


def MsiGetMode(handle: str, mode: int) -> Tuple[int, bool]:
    pkg = _PACKAGES.get(handle)
    if pkg is None or pkg.closed:
        return (ERROR_INSTALL_PACKAGE_OPEN, False)
    return (ERROR_SUCCESS, bool(pkg.properties.get(f"Mode{mode}", "")))


# ---------------------------------------------------------------------------
# EXPORTS
# ---------------------------------------------------------------------------

EXPORTS = {
    "MsiOpenPackageA": MsiOpenPackageA,
    "MsiOpenPackageW": MsiOpenPackageW,
    "MsiCloseHandle": MsiCloseHandle,
    "MsiGetPropertyA": MsiGetPropertyA,
    "MsiSetPropertyA": MsiSetPropertyA,
    "MsiGetFeatureStateA": MsiGetFeatureStateA,
    "MsiSetFeatureStateA": MsiSetFeatureStateA,
    "MsiDoActionA": MsiDoActionA,
    "MsiSetInstallLevel": MsiSetInstallLevel,
    "MsiSetMode": MsiSetMode,
    "MsiGetMode": MsiGetMode,
}


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    h: list = []
    rc = MsiOpenPackageA(r"C:\Installer\MyApp.msi", h)
    if rc != ERROR_SUCCESS or not h:
        return False
    handle = h[0]
    rc, val = MsiGetPropertyA(handle, "ProductName", None)
    if rc != ERROR_SUCCESS or not val:
        return False
    rc = MsiSetPropertyA(handle, "INSTALLDIR", r"C:\Program Files\X")
    if rc != ERROR_SUCCESS:
        return False
    rc, val = MsiGetPropertyA(handle, "INSTALLDIR", None)
    if val != r"C:\Program Files\X":
        return False
    rc, state = MsiGetFeatureStateA(handle, "MainFeature")
    if rc != ERROR_SUCCESS or state != INSTALLSTATE_UNKNOWN:
        return False
    if MsiSetFeatureStateA(handle, "MainFeature",
                            INSTALLSTATE_LOCAL) != ERROR_SUCCESS:
        return False
    rc, state = MsiGetFeatureStateA(handle, "MainFeature")
    if state != INSTALLSTATE_LOCAL:
        return False
    if MsiDoActionA(handle, "CostInitialize") != ERROR_SUCCESS:
        return False
    if MsiCloseHandle(handle) != ERROR_SUCCESS:
        return False
    rc, val = MsiGetPropertyA(handle, "ProductName", None)
    if rc == ERROR_SUCCESS:
        return False
    return True


if __name__ == "__main__":
    import os
    import sys
    sys.exit(0 if _selftest() else 1)
