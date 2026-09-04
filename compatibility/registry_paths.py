"""
Umer OS /compatibility/registry_paths — Registry <-> POSIX mapping
===============================================================

Windows stores the registry under ``%SystemRoot%\\System32\\config``
(NTUSER hive is per-user at ``%USERPROFILE%\\NTUSER.DAT``).  The
compatibility layer maps those locations to a deterministic POSIX
path under :data:`REGISTRY_POSIX_ROOT`.

The mapping is intentionally straightforward -- each top-level
hive becomes a single file under ``config/``::

    C:\\Windows\\System32\\config\\SOFTWARE
        ->  /compat/c/Windows/System32/config/SOFTWARE

    C:\\Windows\\System32\\config\\SYSTEM
        ->  /compat/c/Windows/System32/config/SYSTEM

    C:\\Users\\<user>\\NTUSER.DAT
        ->  /compat/c/Users/<user>/NTUSER.DAT

A *hive-less* view (testing, in-memory) is also supported by
:func:`hive_path`.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/sysinfo/registry-element-size-limits

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import os
import re
from typing import Dict, Optional

from .win_path import DosPathMapper


#: POSIX root for all Windows-style files.
REGISTRY_POSIX_ROOT = "/compat/c/Windows/System32/config"

#: Per-user NTUSER.DAT directory under the mapped "Users" tree.
NTUSER_POSIX_PATTERN = "/compat/c/Users/{user}/NTUSER.DAT"

#: Map a hive's *internal* name (the file basename in
#: ``%SystemRoot%\\System32\\config``) to its Windows path.
HIVE_WINDOWS_NAMES: Dict[str, str] = {
    "SYSTEM":      r"C:\Windows\System32\config\SYSTEM",
    "SOFTWARE":    r"C:\Windows\System32\config\SOFTWARE",
    "SECURITY":    r"C:\Windows\System32\config\SECURITY",
    "SAM":         r"C:\Windows\System32\config\SAM",
    "DEFAULT":     r"C:\Windows\System32\config\DEFAULT",
    "NTUSER.DAT":  r"C:\Users\{user}\NTUSER.DAT",
    "UsrClass.dat": r"C:\Users\{user}\AppData\Local\Microsoft\Windows\UsrClass.dat",
}

#: Translate the hive's basename to the Hkey it is normally mounted on.
#: ``NTUSER.DAT`` and ``UsrClass.dat`` are per-user, so the actual
#: mount depends on the user; we use ``Hkey.CURRENT_USER`` as the
#: *default* mount.
HIVE_TO_HKEY: Dict[str, int] = {
    "SYSTEM":      0x80000005,   # HKLM\SYSTEM
    "SOFTWARE":    0x80000002,   # HKLM\SOFTWARE
    "SECURITY":    0x80000002,
    "SAM":         0x80000002,
    "DEFAULT":     0x80000001,
    "NTUSER.DAT":  0x80000001,
    "UsrClass.dat": 0x80000000,
}


#: Canonical *case-insensitive* alias for the hive basenames.
HIVE_ALIASES: Dict[str, str] = {
    "SYSTEM":      "SYSTEM",
    "SOFTWARE":    "SOFTWARE",
    "SECURITY":    "SECURITY",
    "SAM":         "SAM",
    "DEFAULT":     "DEFAULT",
    "NTUSER":      "NTUSER.DAT",
    "USRCLASS":    "UsrClass.dat",
}


def hive_basename(hive_path: str) -> str:
    """Return the canonical basename for ``hive_path`` (case-insensitive)."""
    base = os.path.basename(hive_path)
    upper = base.upper()
    return HIVE_ALIASES.get(upper, base)


def hive_posix_path(hive_path: str, *, user: Optional[str] = None,
                    compat_root: Optional[str] = None) -> str:
    """Return the POSIX path that holds ``hive_path`` under :data:`REGISTRY_POSIX_ROOT`."""
    base = hive_basename(hive_path)
    if base == "NTUSER.DAT":
        if not user:
            raise ValueError("NTUSER.DAT requires a 'user' argument")
        return NTUSER_POSIX_PATTERN.format(user=user)
    root = compat_root or REGISTRY_POSIX_ROOT
    return os.path.join(root, base)


def hive_windows_path(hive_name: str, *, user: Optional[str] = None) -> str:
    """Return the Windows path for a given hive name."""
    template = HIVE_WINDOWS_NAMES.get(hive_name.upper())
    if template is None:
        raise KeyError(f"unknown hive name: {hive_name!r}")
    if "{user}" in template and not user:
        raise ValueError(f"hive {hive_name!r} requires a 'user' argument")
    return template.format(user=user or "")


def hkey_for_hive(hive_name: str) -> int:
    """Return the predefined :class:`~.registry_view.Hkey` a hive is normally mounted on."""
    upper = hive_name.upper()
    if upper == "NTUSER":
        upper = "NTUSER.DAT"
    if upper == "USRCLASS":
        upper = "UsrClass.dat"
    return HIVE_TO_HKEY[upper]


__all__ = [
    "REGISTRY_POSIX_ROOT",
    "NTUSER_POSIX_PATTERN",
    "HIVE_WINDOWS_NAMES",
    "HIVE_TO_HKEY",
    "HIVE_ALIASES",
    "hive_basename",
    "hive_posix_path",
    "hive_windows_path",
    "hkey_for_hive",
]


def _selftest() -> bool:
    if hive_basename(r"C:\Windows\System32\config\SOFTWARE") != "SOFTWARE":
        return False
    if hive_basename(r"C:\Users\Alice\NTUSER.DAT") != "NTUSER.DAT":
        return False
    if hive_posix_path("SOFTWARE") != os.path.join(
        REGISTRY_POSIX_ROOT, "SOFTWARE"):
        return False
    if hive_posix_path("NTUSER.DAT", user="Alice") != "/compat/c/Users/Alice/NTUSER.DAT":
        return False
    if hkey_for_hive("SOFTWARE") != 0x80000002:
        return False
    if hkey_for_hive("NTUSER") != 0x80000001:
        return False
    if hkey_for_hive("NTUSER.DAT") != 0x80000001:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
