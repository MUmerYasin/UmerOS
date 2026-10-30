"""
Umer OS /compatibility/environment — Win32 environment helpers
============================================================

Pure-Python implementation of the Win32 *environment block* surface
used by ``CreateProcess``, ``GetEnvironmentVariable``, ``SetEnvironmentVariable``,
``ExpandEnvironmentStrings`` and the registry-backed user / system
profile paths.

The environment is stored as an ordered dict so iteration order is
stable (matters for ``GetEnvironmentStrings`` which returns a
double-null-terminated block that must match the order Windows used
when constructing it).

Three scopes
-----------
Windows 10 ships environment variables in three scopes:

* **System** -- ``HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment``
* **User**   -- ``HKCU\\Environment``
* **Process** -- the in-memory block inherited by the running process.

The compatibility layer follows the same precedence: Process overrides
User which overrides System.  A :class:`EnvironmentScope` records the
provenance of every variable so :meth:`EnvironmentBlock.to_zz_block`
can re-emit the canonical Win32 ordering.

Dynamic variables
-----------------
A handful of variables are computed at expansion time:

* ``%CD%``                  - current working directory
* ``%DATE%`` / ``%TIME%``  - locale-formatted current date / time
* ``%RANDOM%``              - 0..32767 pseudo-random integer
* ``%ERRORLEVEL%``          - exit code of the last shell command
* ``%CMDCMDLINE%``          - exact command line that started cmd.exe
* ``%CMDEXTVERSION%``       - command-processor extensions version
* ``%PROMPT%``              - default ``$P$G`` style prompt
* ``%COMPUTERNAME%``        - hostname (when not already in the block)

References
----------

* https://learn.microsoft.com/en-us/windows/win32/procthread/environment-variables
* https://learn.microsoft.com/en-us/windows/deployment/usmt/usmt-recognized-environment-variables
* https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_environment_variables
* https://www3.ntu.edu.sg/home/ehchua/programming/howto/Environment_Variables.html

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
import os
import random as _random
import re
import socket
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.Env")

# ---------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------

class EnvScope(IntEnum):
    """The three Windows environment-variable scopes (precedence: high -> low)."""
    PROCESS = 3
    USER = 2
    SYSTEM = 1


# ---------------------------------------------------------------------------
# Registry paths
# ---------------------------------------------------------------------------

HKCU_ENV_PATH = r"HKCU\Environment"
HKLM_ENV_PATH = r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment"


# ---------------------------------------------------------------------------
# Canonical Win10 variables
# ---------------------------------------------------------------------------
#
# Names follow the Win32 convention of preserving the case the user typed,
# even though lookups are case-insensitive.  The canonical Win10
# catalogue (PowerShell `Get-ChildItem Env:`) is the source of truth.

#: Default values we seed for a clean block.
DEFAULT_SEED: Dict[str, str] = {
    # -- System / Kernel --
    "SystemRoot":               r"C:\Windows",
    "SystemDrive":              "C:",
    "System32":                 r"C:\Windows\System32",
    "System16":                 r"C:\Windows\System",
    "Windir":                   r"C:\Windows",        # alias of SystemRoot
    "ComSpec":                  r"C:\Windows\System32\cmd.exe",
    "OS":                       "Windows_NT",
    "PROCESSOR_ARCHITECTURE":   "AMD64",
    "PROCESSOR_IDENTIFIER":     "Intel64 Family 6 Model 0 Stepping 0, GenuineIntel",
    "PROCESSOR_LEVEL":          "6",
    "PROCESSOR_REVISION":       "0000",
    "NUMBER_OF_PROCESSORS":     "1",
    # -- Standard extension list --
    "PATHEXT":                  ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.WS;.MSC",
    # -- Filesystem roots --
    "ProgramData":              r"C:\ProgramData",
    "ProgramFiles":             r"C:\Program Files",
    "ProgramFiles(x86)":        r"C:\Program Files (x86)",
    "ProgramW6432":             r"C:\Program Files",
    "CommonProgramFiles":       r"C:\Program Files\Common Files",
    "CommonProgramFiles(x86)":  r"C:\Program Files (x86)\Common Files",
    "CommonProgramW6432":       r"C:\Program Files\Common Files",
    "CommonProgramData":        r"C:\ProgramData",
    "Public":                   r"C:\Users\Public",
    "AllUsersProfile":          r"C:\ProgramData",
    # -- User / profile (default user until we know better) --
    "USERPROFILE":              r"C:\Users\Default",
    "UserProfile":              r"C:\Users\Default",
    "HomeDrive":                "C:",
    "HomePath":                 r"\Users\Default",
    "AppData":                  r"C:\Users\Default\AppData\Roaming",
    "LocalAppData":             r"C:\Users\Default\AppData\Local",
    "Temp":                     r"C:\Windows\Temp",
    "Tmp":                      r"C:\Windows\Temp",
    # -- Profile-list anchors used by the USMT CSIDL_* templates --
    "DEFAULTUSERPROFILE":       r"C:\Users\Default",
    "PROFILESFOLDER":           r"C:\Users",
    "USERSID":                  "S-1-5-21-1004336348-1177238915-682003330-1001",
    "SYSTEMPROFILE":            r"C:\Windows\System32\config\systemprofile",
    # -- Shell hints --
    "PROMPT":                   "$P$G",
    # -- Search path (seeded with the canonical Win10 64-bit dirs) --
    "PATH":                     (r"C:\Windows\system32;C:\Windows;"
                                 r"C:\Windows\System32\Wbem;"
                                 r"C:\Windows\System32\WindowsPowerShell\v1.0"),
}


#: Names that Win32 *treats* as dynamic and re-resolves each call.
#: The string form (``%NAME%``) is expanded at lookup time, not at set.
DYNAMIC_NAMES = frozenset({
    "CD", "DATE", "TIME", "RANDOM", "ERRORLEVEL",
    "CMDCMDLINE", "CMDEXTVERSION", "PROMPT",
    "COMPUTERNAME", "USERNAME", "USERDOMAIN",
    "USERDOMAIN_ROAMINGPROFILE",
})


#: Names that Windows itself defines on a stock Win10/11 installation.
#: These are the variables ``Get-ChildItem Env:`` shows and the ones an
#: installer manifest may reference.
_MODERN_WINDOWS_VARS: Tuple[str, ...] = (
    "ALLUSERSPROFILE", "APPDATA", "CommonProgramFiles",
    "CommonProgramFiles(x86)", "CommonProgramW6432", "COMPUTERNAME",
    "ComSpec", "DATE", "ERRORLEVEL", "HOMEDRIVE", "HOMEPATH",
    "LOCALAPPDATA", "LOGONSERVER", "NUMBER_OF_PROCESSORS", "OS",
    "PATH", "PATHEXT", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
    "PROCESSOR_LEVEL", "PROCESSOR_REVISION", "ProgramData",
    "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "PROMPT",
    "PSModulePath", "PUBLIC", "RANDOM", "SESSIONNAME", "SystemDrive",
    "SystemRoot", "TEMP", "TMP", "USERDOMAIN", "USERDOMAIN_ROAMINGPROFILE",
    "USERNAME", "USERPROFILE", "WINDIR",
    # Win10 1607+ / Win11 additions that installers rely on.
    "OneDrive", "OneDriveConsumer", "OneDriveCommercial",
    "OneDriveCommercialSubscription", "PROCESSOR_ARCHITEW6432",
    "PROCESSOR_REVISION", "CommonProgramData", "PROCESSOR_LEVEL",
)


# ---------------------------------------------------------------------------
# USMT recognised-variable catalogue
# ---------------------------------------------------------------------------
#
# The User State Migration Tool recognises a larger set of names than
# Windows actually defines.  The extra names are the ``CSIDL_*`` family
# plus a handful of aliases; USMT uses them to locate folders that may
# live in different places on different machines.
#
# The two tables below mirror the Microsoft reference exactly:
#
# * :data:`USMT_USER_AND_SYSTEM` -- processed for the OS *and* in the
#   context of each user.  Usable in ``context=UserAndSystem``,
#   ``context=User`` and ``context=System`` sections.
# * :data:`USMT_USER_ONLY` -- recognised only in the user context.
#   Usable in ``context=User`` and ``context=UserAndSystem`` sections.

#: Variables processed for the operating system and in the context of
#: each user.
USMT_USER_AND_SYSTEM: Tuple[str, ...] = (
    "ALLUSERSAPPDATA",
    "ALLUSERSPROFILE",
    "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILES(X86)",
    "CSIDL_COMMON_ADMINTOOLS",
    "CSIDL_COMMON_ALTSTARTUP",
    "CSIDL_COMMON_APPDATA",
    "CSIDL_COMMON_DESKTOPDIRECTORY",
    "CSIDL_COMMON_DOCUMENTS",
    "CSIDL_COMMON_FAVORITES",
    "CSIDL_COMMON_MUSIC",
    "CSIDL_COMMON_PICTURES",
    "CSIDL_COMMON_PROGRAMS",
    "CSIDL_COMMON_STARTMENU",
    "CSIDL_COMMON_STARTUP",
    "CSIDL_COMMON_TEMPLATES",
    "CSIDL_COMMON_VIDEO",
    "CSIDL_DEFAULT_APPDATA",
    "CSIDL_DEFAULT_LOCAL_APPDATA",
    "CSIDL_DEFAULT_COOKIES",
    "CSIDL_DEFAULT_CONTACTS",
    "CSIDL_DEFAULT_DESKTOP",
    "CSIDL_DEFAULT_DOWNLOADS",
    "CSIDL_DEFAULT_FAVORITES",
    "CSIDL_DEFAULT_HISTORY",
    "CSIDL_DEFAULT_INTERNET_CACHE",
    "CSIDL_DEFAULT_PERSONAL",
    "CSIDL_DEFAULT_MYDOCUMENTS",
    "CSIDL_DEFAULT_MYPICTURES",
    "CSIDL_DEFAULT_MYMUSIC",
    "CSIDL_DEFAULT_MYVIDEO",
    "CSIDL_DEFAULT_RECENT",
    "CSIDL_DEFAULT_SENDTO",
    "CSIDL_DEFAULT_STARTMENU",
    "CSIDL_DEFAULT_PROGRAMS",
    "CSIDL_DEFAULT_STARTUP",
    "CSIDL_DEFAULT_TEMPLATES",
    "CSIDL_DEFAULT_QUICKLAUNCH",
    "CSIDL_FONTS",
    "CSIDL_PROGRAM_FILESX86",
    "CSIDL_PROGRAM_FILES_COMMONX86",
    "CSIDL_PROGRAM_FILES",
    "CSIDL_PROGRAM_FILES_COMMON",
    "CSIDL_RESOURCES",
    "CSIDL_SYSTEM",
    "CSIDL_WINDOWS",
    "DEFAULTUSERPROFILE",
    "PROFILESFOLDER",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "SYSTEM",
    "SYSTEM16",
    "SYSTEM32",
    "SYSTEMDRIVE",
    "SYSTEMPROFILE",
    "SYSTEMROOT",
    "WINDIR",
)

#: Variables recognised only in the user context.
USMT_USER_ONLY: Tuple[str, ...] = (
    "APPDATA",
    "CSIDL_ADMINTOOLS",
    "CSIDL_ALTSTARTUP",
    "CSIDL_APPDATA",
    "CSIDL_BITBUCKET",
    "CSIDL_CDBURN_AREA",
    "CSIDL_CONNECTIONS",
    "CSIDL_CONTACTS",
    "CSIDL_CONTROLS",
    "CSIDL_COOKIES",
    "CSIDL_DESKTOP",
    "CSIDL_DESKTOPDIRECTORY",
    "CSIDL_DRIVES",
    "CSIDL_FAVORITES",
    "CSIDL_HISTORY",
    "CSIDL_INTERNET",
    "CSIDL_INTERNET_CACHE",
    "CSIDL_LOCAL_APPDATA",
    "CSIDL_MYDOCUMENTS",
    "CSIDL_MYMUSIC",
    "CSIDL_MYPICTURES",
    "CSIDL_MYVIDEO",
    "CSIDL_NETHOOD",
    "CSIDL_NETWORK",
    "CSIDL_PERSONAL",
    "CSIDL_PLAYLISTS",
    "CSIDL_PRINTERS",
    "CSIDL_PRINTHOOD",
    "CSIDL_PROFILE",
    "CSIDL_PROGRAMS",
    "CSIDL_RECENT",
    "CSIDL_SENDTO",
    "CSIDL_STARTMENU",
    "CSIDL_STARTUP",
    "CSIDL_TEMPLATES",
    "HOMEPATH",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "USERSID",
)

#: Every name USMT recognises (the union of both contexts).
USMT_RECOGNISED: Tuple[str, ...] = tuple(
    sorted(set(USMT_USER_AND_SYSTEM) | set(USMT_USER_ONLY))
)

#: The USMT migration contexts a recognised variable may be used in.
USMT_CONTEXTS: Dict[str, Tuple[str, ...]] = {
    "UserAndSystem": USMT_RECOGNISED,
    "User": USMT_USER_ONLY + USMT_USER_AND_SYSTEM,
    "System": USMT_USER_AND_SYSTEM,
}

#: Recognised names that are pure aliases of a canonical Win10 variable
#: (the USMT doc says "Same as ...").  Aliases are resolved by reading
#: the target variable, never by expanding a self-referential template.
CSIDL_ENV_ALIASES: Dict[str, str] = {
    "ALLUSERSAPPDATA": "ProgramData",
    "ALLUSERSPROFILE": "AllUsersProfile",
    "APPDATA": "AppData",
    "COMMONPROGRAMFILES": "CommonProgramFiles",
    "COMMONPROGRAMFILES(X86)": "CommonProgramFiles(x86)",
    "CSIDL_APPDATA": "AppData",
    "CSIDL_LOCAL_APPDATA": "LocalAppData",
    "CSIDL_MYDOCUMENTS": "Documents",
    "CSIDL_PERSONAL": "Documents",
    "CSIDL_PROFILE": "USERPROFILE",
    "HOMEPATH": "HomePath",
    "PROGRAMFILES": "ProgramFiles",
    "PROGRAMFILES(X86)": "ProgramFiles(x86)",
    "SYSTEM": "System32",
    "SYSTEM16": "System16",
    "SYSTEM32": "System32",
    "SYSTEMROOT": "SystemRoot",
    "TEMP": "Temp",
    "TMP": "Tmp",
    "USERPROFILE": "USERPROFILE",
    "WINDIR": "Windir",
}

#: Path templates for the recognised names that are *not* simple aliases.
#: Values are expanded against the environment block on demand.
CSIDL_ENV_TEMPLATES: Dict[str, str] = {
    # -- User and system context --
    "CSIDL_COMMON_ADMINTOOLS":
        r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\Administrative Tools",
    "CSIDL_COMMON_ALTSTARTUP":
        r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\StartUp",
    "CSIDL_COMMON_APPDATA": r"%ProgramData%",
    "CSIDL_COMMON_DESKTOPDIRECTORY": r"%PUBLIC%\Desktop",
    "CSIDL_COMMON_DOCUMENTS": r"%PUBLIC%\Documents",
    "CSIDL_COMMON_FAVORITES": r"%PUBLIC%\Favorites",
    "CSIDL_COMMON_MUSIC": r"%PUBLIC%\Music",
    "CSIDL_COMMON_PICTURES": r"%PUBLIC%\Pictures",
    "CSIDL_COMMON_PROGRAMS":
        r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs",
    "CSIDL_COMMON_STARTMENU": r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu",
    "CSIDL_COMMON_STARTUP":
        r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\Startup",
    "CSIDL_COMMON_TEMPLATES": r"%ALLUSERSPROFILE%\Microsoft\Windows\Templates",
    "CSIDL_COMMON_VIDEO": r"%PUBLIC%\Videos",
    "CSIDL_DEFAULT_APPDATA": r"%DEFAULTUSERPROFILE%\AppData\Roaming",
    "CSIDL_DEFAULT_LOCAL_APPDATA": r"%DEFAULTUSERPROFILE%\AppData\Local",
    "CSIDL_DEFAULT_COOKIES":
        r"%DEFAULTUSERPROFILE%\AppData\Roaming\Microsoft\Windows\Cookies",
    "CSIDL_DEFAULT_CONTACTS": r"%DEFAULTUSERPROFILE%\Contacts",
    "CSIDL_DEFAULT_DESKTOP": r"%DEFAULTUSERPROFILE%\Desktop",
    "CSIDL_DEFAULT_DOWNLOADS": r"%DEFAULTUSERPROFILE%\Downloads",
    "CSIDL_DEFAULT_FAVORITES": r"%DEFAULTUSERPROFILE%\Favorites",
    "CSIDL_DEFAULT_HISTORY":
        r"%DEFAULTUSERPROFILE%\AppData\Local\Microsoft\Windows\History",
    "CSIDL_DEFAULT_INTERNET_CACHE":
        r"%DEFAULTUSERPROFILE%\AppData\Local\Microsoft\Windows\Internet Cache",
    "CSIDL_DEFAULT_PERSONAL": r"%DEFAULTUSERPROFILE%\Documents",
    "CSIDL_DEFAULT_MYDOCUMENTS": r"%DEFAULTUSERPROFILE%\Documents",
    "CSIDL_DEFAULT_MYPICTURES": r"%DEFAULTUSERPROFILE%\Pictures",
    "CSIDL_DEFAULT_MYMUSIC": r"%DEFAULTUSERPROFILE%\Music",
    "CSIDL_DEFAULT_MYVIDEO": r"%DEFAULTUSERPROFILE%\Videos",
    "CSIDL_DEFAULT_RECENT":
        r"%DEFAULTUSERPROFILE%\AppData\Roaming\Microsoft\Windows\Recent",
    "CSIDL_DEFAULT_SENDTO":
        r"%DEFAULTUSERPROFILE%\AppData\Roaming\Microsoft\Windows\SendTo",
    "CSIDL_DEFAULT_STARTMENU":
        r"%DEFAULTUSERPROFILE%\AppData\Roaming\Microsoft\Windows\Start Menu",
    "CSIDL_DEFAULT_PROGRAMS":
        r"%DEFAULTUSERPROFILE%\AppData\Roaming\Microsoft\Windows\Start Menu\Programs",
    "CSIDL_DEFAULT_STARTUP":
        r"%DEFAULTUSERPROFILE%\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup",
    "CSIDL_DEFAULT_TEMPLATES":
        r"%DEFAULTUSERPROFILE%\AppData\Roaming\Microsoft\Windows\Templates",
    "CSIDL_DEFAULT_QUICKLAUNCH":
        r"%DEFAULTUSERPROFILE%\AppData\Roaming\Microsoft\Internet Explorer\Quick Launch",
    "CSIDL_FONTS": r"%windir%\Fonts",
    "CSIDL_PROGRAM_FILESX86": r"%ProgramFiles(x86)%",
    "CSIDL_PROGRAM_FILES_COMMONX86": r"%ProgramFiles(x86)%\Common Files",
    "CSIDL_PROGRAM_FILES": r"%ProgramFiles%",
    "CSIDL_PROGRAM_FILES_COMMON": r"%ProgramFiles%\Common Files",
    "CSIDL_RESOURCES": r"%windir%\Resources",
    "CSIDL_SYSTEM": r"%windir%\system32",
    "CSIDL_WINDOWS": r"%windir%",
    "DEFAULTUSERPROFILE": r"%SystemDrive%\Users\Default",
    "PROFILESFOLDER": r"%SystemDrive%\Users",
    "SYSTEMDRIVE": r"%SystemDrive%",
    "SYSTEMPROFILE": r"%windir%\System32\config\systemprofile",
    # -- User context --
    "CSIDL_ADMINTOOLS":
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Administrative Tools",
    "CSIDL_ALTSTARTUP":
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\StartUp",
    "CSIDL_CDBURN_AREA": r"%LOCALAPPDATA%\Microsoft\Windows\Burn\Burn",
    "CSIDL_CONTACTS": r"%USERPROFILE%\Contacts",
    "CSIDL_COOKIES": r"%APPDATA%\Microsoft\Windows\Cookies",
    "CSIDL_DESKTOPDIRECTORY": r"%USERPROFILE%\Desktop",
    "CSIDL_FAVORITES": r"%USERPROFILE%\Favorites",
    "CSIDL_HISTORY": r"%LOCALAPPDATA%\Microsoft\Windows\History",
    "CSIDL_INTERNET_CACHE":
        r"%LOCALAPPDATA%\Microsoft\Windows\Temporary Internet Files",
    "CSIDL_MYMUSIC": r"%USERPROFILE%\Music",
    "CSIDL_MYPICTURES": r"%USERPROFILE%\Pictures",
    "CSIDL_MYVIDEO": r"%USERPROFILE%\Videos",
    "CSIDL_NETHOOD": r"%APPDATA%\Microsoft\Windows\Network Shortcuts",
    "CSIDL_PLAYLISTS": r"%USERPROFILE%\Music\Playlists",
    "CSIDL_PRINTHOOD": r"%APPDATA%\Microsoft\Windows\Printer Shortcuts",
    "CSIDL_PROGRAMS": r"%APPDATA%\Microsoft\Windows\Start Menu\Programs",
    "CSIDL_RECENT": r"%APPDATA%\Microsoft\Windows\Recent",
    "CSIDL_SENDTO": r"%APPDATA%\Microsoft\Windows\SendTo",
    "CSIDL_STARTMENU": r"%APPDATA%\Microsoft\Windows\Start Menu",
    "CSIDL_STARTUP":
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup",
    "CSIDL_TEMPLATES": r"%APPDATA%\Microsoft\Windows\Templates",
}

#: Recognised process-scoped Win10 names plus the full USMT catalogue.
#: This is the union an installer or migration tool may reference.
WIN10_RECOGNISED: Tuple[str, ...] = tuple(
    sorted(set(_MODERN_WINDOWS_VARS) | set(USMT_RECOGNISED))
)

#: The names Windows itself defines (i.e. excluding the USMT-only
#: ``CSIDL_*`` family and the migration aliases).
WIN10_SYSTEM_VARS: Tuple[str, ...] = tuple(sorted(set(_MODERN_WINDOWS_VARS)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(name: str) -> str:
    """Win32 env names are case-insensitive; we canonicalise to upper."""
    if not name:
        raise ValueError("env var name must be non-empty")
    return name.upper()


def _now_human() -> str:
    """Locale-friendly ``%DATE%`` / ``%TIME%`` formatter."""
    return time.strftime("%a %m/%d/%Y", time.localtime())


def _is_pathext_match(name: str, pathext: str) -> bool:
    """``True`` iff ``name`` ends with one of the suffixes in ``pathext``."""
    upper = name.upper()
    for ext in pathext.split(";"):
        ext = ext.strip()
        if ext and upper.endswith(ext.upper()):
            return True
    return False


def parse_path(value: str, sep: str = ";") -> List[str]:
    """Split a ``PATH``-style value into entries.  Drops blank entries."""
    for piece in value.split(sep):
        s = piece.strip()
        if s:
            yield s


def join_path(entries: Iterable[str], sep: str = ";") -> str:
    """Reverse of :func:`parse_path`."""
    return sep.join(entries)


# ---------------------------------------------------------------------------
# Dynamic resolution
# ---------------------------------------------------------------------------

class _CmdState:
    """The mutable shell state used to resolve dynamic variables."""
    errorlevel: int = 0
    cmdcmdline: str = ""
    cmdextversion: int = 2


_STATE = _CmdState()


def set_errorlevel(code: int) -> None:
    """Set the current shell error level (used to expand ``%ERRORLEVEL%``)."""
    _STATE.errorlevel = code


def set_cmdcmdline(s: str) -> None:
    """Set the cmd.exe startup command line (used to expand ``%CMDCMDLINE%``)."""
    _STATE.cmdcmdline = s


def _resolve_dynamic(name: str) -> Optional[str]:
    """Resolve a dynamic variable, returning ``None`` if not handled."""
    n = name.upper()
    if n == "CD":
        try:
            return os.getcwd()
        except OSError:
            return ""
    if n == "DATE":
        return _now_human().split(" ", 1)[-1]
    if n == "TIME":
        return time.strftime("%H:%M:%S.00", time.localtime())
    if n == "RANDOM":
        return str(_random.randint(0, 32767))
    if n == "ERRORLEVEL":
        return str(_STATE.errorlevel)
    if n == "CMDCMDLINE":
        return _STATE.cmdcmdline or "cmd.exe"
    if n == "CMDEXTVERSION":
        return str(_STATE.cmdextversion)
    if n == "PROMPT":
        # Default cmd prompt -- caller can override via the static block.
        return "$P$G"
    if n == "COMPUTERNAME":
        try:
            return socket.gethostname().upper()
        except OSError:
            return ""
    if n == "USERNAME":
        return os.environ.get("USERNAME", os.environ.get("USER", ""))
    if n == "USERDOMAIN":
        return os.environ.get("USERDOMAIN", "")
    if n == "USERDOMAIN_ROAMINGPROFILE":
        return os.environ.get("USERDOMAIN_ROAMINGPROFILE", "")
    return None


# ---------------------------------------------------------------------------
# The environment block
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentBlock:
    """A Win32-style environment block.

    The block is a *case-insensitive* mapping from variable name to
    value.  Insertion order is preserved so :meth:`to_zz_block`
    returns a stable byte layout -- that matters because Windows
    applications sometimes memcmp the block when validating.

    Two layers are tracked:

    * ``_vars`` -- the canonical name->value table (string form only).
    * ``_scopes`` -- provenance for each variable, used when emitting
      scope-prefixed debug reports.
    """

    _vars: Dict[str, str] = field(default_factory=dict)
    _scopes: Dict[str, EnvScope] = field(default_factory=dict)
    #: When ``True`` the *host* environment will be folded in at lookup
    #: time (this matches Windows' process-block merging at boot).
    host_fallback: bool = True

    # ------------------------------------------------------------------
    # Basic accessors
    # ------------------------------------------------------------------

    def __contains__(self, name: str) -> bool:
        return _normalise(name) in self._vars

    def __len__(self) -> int:
        return len(self._vars)

    def __iter__(self) -> Iterator[str]:
        return iter(self._vars.keys())

    def __getitem__(self, name: str) -> str:
        return self._vars[_normalise(name)]

    def __setitem__(self, name: str, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("env values must be str")
        key = _normalise(name)
        self._vars[key] = value
        self._scopes[key] = EnvScope.PROCESS

    def __delitem__(self, name: str) -> None:
        key = _normalise(name)
        if key in self._vars:
            del self._vars[key]
            self._scopes.pop(key, None)

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Resolve ``name`` (case-insensitive).

        Order of precedence:

        1. The block's own entry.
        2. A :func:`_resolve_dynamic` lookup for known dynamic names.
        3. ``os.environ`` when ``host_fallback`` is set.
        4. ``default``.
        """
        key = _normalise(name)
        if key in self._vars:
            return self._vars[key]
        dyn = _resolve_dynamic(key)
        if dyn is not None:
            return dyn
        if self.host_fallback:
            host = os.environ.get(key)
            if host is not None:
                return host
        return default

    def setdefault(self, name: str, default: str) -> str:
        key = _normalise(name)
        if key not in self._vars:
            self._vars[key] = default
            self._scopes[key] = EnvScope.PROCESS
        return self._vars[key]

    def update(self, items: Dict[str, str] | Iterable[Tuple[str, str]],
               *, scope: EnvScope = EnvScope.PROCESS) -> None:
        if isinstance(items, dict):
            items = items.items()
        for k, v in items:
            key = _normalise(k)
            self._vars[key] = v
            self._scopes[key] = scope

    def items(self) -> List[Tuple[str, str]]:
        """Return the static (non-computed) entries in insertion order."""
        return list(self._vars.items())

    def items_with_scope(self) -> List[Tuple[str, str, EnvScope]]:
        """Same as :meth:`items` but with the source scope."""
        out = []
        for k, v in self._vars.items():
            out.append((k, v, self._scopes.get(k, EnvScope.PROCESS)))
        return out

    def scope_of(self, name: str) -> Optional[EnvScope]:
        return self._scopes.get(_normalise(name))

    # ------------------------------------------------------------------
    # PATH / PATHEXT helpers
    # ------------------------------------------------------------------

    def add_path_entry(self, entry: str, *, at_front: bool = False) -> bool:
        """Insert ``entry`` into ``PATH``.

        Returns ``True`` if the entry was newly added (or moved to the
        front when ``at_front=True``).
        """
        sep = ";"
        key = "PATH"
        if key not in self._vars:
            self._vars[key] = entry
            self._scopes[key] = EnvScope.PROCESS
            return True
        entries = list(parse_path(self._vars[key], sep))
        norm = entry.strip()
        if not norm:
            return False
        if at_front:
            if entries and entries[0].strip().lower() == norm.lower():
                return False
            entries.insert(0, norm)
        else:
            if any(e.strip().lower() == norm.lower() for e in entries):
                return False
            entries.append(norm)
        self._vars[key] = join_path(entries, sep)
        self._scopes[key] = EnvScope.PROCESS
        return True

    def remove_path_entry(self, entry: str) -> bool:
        """Remove ``entry`` from ``PATH``.  Returns ``True`` on success."""
        key = "PATH"
        if key not in self._vars:
            return False
        norm = entry.strip().lower()
        new = [e for e in parse_path(self._vars[key])
               if e.strip().lower() != norm]
        if len(new) == len(list(parse_path(self._vars[key]))):
            return False
        self._vars[key] = join_path(new)
        return True

    def pathext(self) -> List[str]:
        """Return the PATHEXT list (in lowercase)."""
        raw = self.get("PATHEXT") or ""
        return [e.strip().lower() for e in raw.split(";") if e.strip()]

    def matches_pathext(self, filename: str) -> bool:
        """``True`` iff ``filename`` ends in one of the ``PATHEXT`` entries."""
        return _is_pathext_match(filename, self.get("PATHEXT") or "")

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_zz_block(self) -> bytes:
        """Encode as a Win32 double-null-terminated ``LPCWSTR`` block.

        The format is::

            name1=value1\\0name2=value2\\0\\0

        where every character is encoded as UTF-16LE.
        """
        out = bytearray()
        for k, v in self._vars.items():
            out += k.encode("utf-16-le")
            out += b"=\x00"                # '=' as a UTF-16LE code unit
            out += v.encode("utf-16-le")
            out += b"\x00\x00"
        out += b"\x00\x00"
        return bytes(out)

    def to_wide_strings(self) -> List[bytes]:
        """Return each variable as a separate UTF-16LE NUL-terminated
        bytes object -- the format ``GetEnvironmentStringsW`` exposes
        when the caller walks the block one string at a time."""
        out: List[bytes] = []
        for k, v in self._vars.items():
            out.append(k.encode("utf-16-le") + b"=\x00"
                       + v.encode("utf-16-le") + b"\x00\x00")
        return out


# ---------------------------------------------------------------------------
# Case-preserving scoped table
# ---------------------------------------------------------------------------

class _ScopedTable:
    """A case-insensitive string table that remembers the original spelling.

    Windows environment blocks preserve the case a variable was *defined*
    with even though every lookup is case-insensitive -- ``set Foo`` then
    ``set foo`` both work, but ``set`` lists the name as ``Foo``.  This
    helper reproduces that behaviour for the scoped store.
    """

    __slots__ = ("_values", "_case")

    def __init__(self, initial: Optional[Dict[str, str]] = None) -> None:
        self._values: Dict[str, str] = {}
        self._case: Dict[str, str] = {}
        if initial:
            for k, v in initial.items():
                self[k] = v

    def __setitem__(self, name: str, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("env values must be str")
        key = _normalise(name)
        self._values[key] = value
        self._case.setdefault(key, name)

    def __getitem__(self, name: str) -> str:
        return self._values[_normalise(name)]

    def __delitem__(self, name: str) -> None:
        key = _normalise(name)
        del self._values[key]
        self._case.pop(key, None)

    def __contains__(self, name: str) -> bool:
        return _normalise(name) in self._values

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the *display* (originally spelled) names."""
        return iter(self._case.values())

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return self._values.get(_normalise(name), default)

    def display_name(self, name: str) -> str:
        """The originally-spelled name for ``name``."""
        key = _normalise(name)
        return self._case.get(key, name)

    def items(self) -> List[Tuple[str, str]]:
        """``(display name, value)`` pairs in insertion order."""
        return [(self._case[k], v) for k, v in self._values.items()]

    def to_dict(self) -> Dict[str, str]:
        """A plain ``{display name: value}`` dictionary."""
        return dict(self.items())

    def keys(self) -> List[str]:
        return list(self._case.values())

    def clear(self) -> None:
        self._values.clear()
        self._case.clear()


# ---------------------------------------------------------------------------
# The three-scope store
# ---------------------------------------------------------------------------

@dataclass
class ScopedEnvironment:
    """The three Windows environment-variable scopes, with Windows precedence.

    Windows keeps environment variables in three places:

    * **Machine** (``HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session
      Manager\\Environment``) -- applies to every user of the machine.
    * **User** (``HKCU\\Environment``) -- applies to the signed-in user.
    * **Process** -- the live block of the running process.

    When the same name exists in more than one scope the highest scope
    wins: ``Process > User > System``.  This is the precedence both
    ``cmd.exe`` and PowerShell's ``$Env:NAME`` use, and the reason a
    process-scoped override shadows the machine-wide value.

    Example
    -------
    >>> env = ScopedEnvironment(system={"Path": r"C:\\Windows"})
    >>> env.set("Path", r"C:\\Tools", EnvScope.USER)
    True
    >>> env.get("PATH")
    'C:\\\\Tools'
    >>> env.scope_of("PATH")
    <EnvScope.USER: 2>
    """

    system: _ScopedTable = field(default_factory=_ScopedTable)
    user: _ScopedTable = field(default_factory=_ScopedTable)
    process: _ScopedTable = field(default_factory=_ScopedTable)
    #: When ``True`` the *host* environment is consulted for names that
    #: none of the three scopes define.
    host_fallback: bool = True

    # -- scope plumbing ------------------------------------------------

    def table(self, scope: EnvScope) -> _ScopedTable:
        """Return the raw table backing ``scope``."""
        if scope is EnvScope.SYSTEM:
            return self.system
        if scope is EnvScope.USER:
            return self.user
        if scope is EnvScope.PROCESS:
            return self.process
        raise ValueError(f"unknown scope: {scope!r}")

    @staticmethod
    def scope_order() -> Tuple[EnvScope, ...]:
        """Scopes in precedence order (highest first)."""
        return (EnvScope.PROCESS, EnvScope.USER, EnvScope.SYSTEM)

    # -- reads ---------------------------------------------------------

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Resolve ``name`` using the Windows precedence rules."""
        for scope in self.scope_order():
            table = self.table(scope)
            if name in table:
                return table[name]
        if self.host_fallback:
            host = os.environ.get(_normalise(name))
            if host is not None:
                return host
        return default

    def get_from(self, name: str, scope: EnvScope) -> Optional[str]:
        """Read ``name`` from one specific scope only."""
        return self.table(scope).get(name)

    def scope_of(self, name: str) -> Optional[EnvScope]:
        """Which scope supplies the effective value of ``name``."""
        for scope in self.scope_order():
            if name in self.table(scope):
                return scope
        return None

    def items(self, scope: Optional[EnvScope] = None
              ) -> List[Tuple[str, str]]:
        """Entries of one scope, or the effective view of all three."""
        if scope is not None:
            return self.table(scope).items()
        seen: Dict[str, Tuple[str, str]] = {}
        for sc in self.scope_order():
            for disp, value in self.table(sc).items():
                seen.setdefault(_normalise(disp), (disp, value))
        return list(seen.values())

    def names(self, scope: Optional[EnvScope] = None) -> List[str]:
        """The display names visible in ``scope`` (or the effective view)."""
        return [n for n, _ in self.items(scope)]

    def to_dict(self, scope: Optional[EnvScope] = None) -> Dict[str, str]:
        """A plain ``{name: value}`` dictionary."""
        return dict(self.items(scope))

    # -- writes --------------------------------------------------------

    def set(self, name: str, value: Optional[str],
            scope: EnvScope = EnvScope.PROCESS) -> bool:
        """Define ``name`` in ``scope``.

        Passing ``value=None`` unsets the variable, matching
        ``SetEnvironmentVariable(name, NULL)``.  Returns ``True`` when
        the table changed.
        """
        table = self.table(scope)
        if value is None:
            if name not in table:
                return False
            del table[name]
            return True
        changed = table.get(name) != value
        table[name] = value
        return changed

    def unset(self, name: str, scope: Optional[EnvScope] = None) -> bool:
        """Remove ``name`` from one scope, or from every scope."""
        scopes = self.scope_order() if scope is None else (scope,)
        changed = False
        for sc in scopes:
            table = self.table(sc)
            if name in table:
                del table[name]
                changed = True
        return changed

    def clear(self, scope: Optional[EnvScope] = None) -> None:
        """Empty one scope, or all of them."""
        scopes = self.scope_order() if scope is None else (scope,)
        for sc in scopes:
            self.table(sc).clear()

    # -- views ---------------------------------------------------------

    def effective(self) -> EnvironmentBlock:
        """Flatten the three scopes into a single :class:`EnvironmentBlock`.

        Precedence is preserved: a process value shadows the user value,
        which shadows the machine value.
        """
        blk = EnvironmentBlock(host_fallback=self.host_fallback)
        blk.update(self.system.to_dict(), scope=EnvScope.SYSTEM)
        blk.update(self.user.to_dict(), scope=EnvScope.USER)
        blk.update(self.process.to_dict(), scope=EnvScope.PROCESS)
        return blk

    def to_registry(self) -> Dict[EnvScope, Dict[str, str]]:
        """The two persistable scopes, ready to be written to the hive.

        The process scope is intentionally absent -- it is never
        persisted.
        """
        return {
            EnvScope.SYSTEM: self.system.to_dict(),
            EnvScope.USER: self.user.to_dict(),
        }

    @classmethod
    def from_registry(cls,
                      system: Optional[Dict[str, str]] = None,
                      user: Optional[Dict[str, str]] = None,
                      process: Optional[Dict[str, str]] = None,
                      *,
                      host_fallback: bool = True) -> "ScopedEnvironment":
        """Build a store from the two registry scopes plus a process block."""
        return cls(
            system=_ScopedTable(system),
            user=_ScopedTable(user),
            process=_ScopedTable(process),
            host_fallback=host_fallback,
        )

    @classmethod
    def from_block(cls, block: Optional[EnvironmentBlock] = None,
                   *, host_fallback: bool = True) -> "ScopedEnvironment":
        """Split an :class:`EnvironmentBlock` back into scoped tables."""
        env = cls(host_fallback=host_fallback)
        if block is None:
            block = get_default_block()
        for name, value, scope in block.items_with_scope():
            env.table(scope)[name] = value
        return env


def registry_path_for_scope(scope: EnvScope) -> Optional[str]:
    """The registry key that persists ``scope``.

    The process scope has no registry backing -- it only ever lives in
    the running process's block.
    """
    if scope is EnvScope.SYSTEM:
        return HKLM_ENV_PATH
    if scope is EnvScope.USER:
        return HKCU_ENV_PATH
    return None


def scope_registry_name(scope: EnvScope) -> Optional[str]:
    """The registry-scope name (``"user"`` / ``"system"``) for a scope.

    :class:`EnvScope` is an ``IntEnum``, so ``scope.value`` is the
    numeric precedence, not a name.  This helper is the single place
    that maps a scope onto the name the registry store uses.
    """
    if scope is EnvScope.USER:
        return "user"
    if scope is EnvScope.SYSTEM:
        return "system"
    return None


# ---------------------------------------------------------------------------
# USMT variable resolution
# ---------------------------------------------------------------------------

def is_recognised(name: str) -> bool:
    """``True`` when ``name`` is part of the recognised Win10/USMT set."""
    return _normalise(name) in _RECOGNISED_INDEX


_RECOGNISED_INDEX = frozenset(n.upper() for n in WIN10_RECOGNISED)


def usmt_context_for(name: str) -> Tuple[str, ...]:
    """The USMT migration contexts ``name`` may be used in."""
    key = _normalise(name)
    out = []
    for context, names in USMT_CONTEXTS.items():
        if key in {n.upper() for n in names}:
            out.append(context)
    return tuple(out)


def resolve_usmt_variable(name: str,
                          block: Optional[EnvironmentBlock] = None,
                          *,
                          app_is_32bit: bool = False,
                          os_is_64bit: bool = True) -> Optional[str]:
    """Resolve a USMT-recognised variable to the path it denotes.

    Three resolution strategies are tried in order:

    1. **Alias** -- the name is a documented synonym of a canonical Win10
       variable (``PROGRAMFILES`` is ``ProgramFiles``, ``CSIDL_APPDATA``
       is ``APPDATA``, ...).
    2. **Template** -- the name denotes a folder whose path is written
       as a ``%VAR%`` template (``CSIDL_DEFAULT_DESKTOP`` is
       ``%DEFAULTUSERPROFILE%\\Desktop``).
    3. **CSIDL** -- the name is a ``CSIDL_*`` constant, so it is
       resolved through the Known Folder catalogue.  Virtual folders
       (Desktop, Control Panel, ...) come back as ``::{GUID}`` shell
       namespace paths.

    Returns ``None`` when the name is not recognised.
    """
    key = _normalise(name)

    alias = CSIDL_ENV_ALIASES.get(key)
    if alias is not None:
        if block is not None:
            value = block.get(alias)
            if value is not None:
                return value
        else:
            value = get_default_var(alias)
            if value is not None:
                return value

    template = CSIDL_ENV_TEMPLATES.get(key)
    if template is not None:
        return ExpandEnvironmentStringsA(template, block)

    if key.startswith("CSIDL_"):
        from .knownfolders import Csidl, resolve_csidl   # local: avoid cycle
        try:
            csidl = Csidl[key[len("CSIDL_"):]]
        except ValueError:
            return None
        return resolve_csidl(csidl, app_is_32bit=app_is_32bit,
                              os_is_64bit=os_is_64bit, block=block)

    return None


def build_usmt_context(name: str,
                       block: Optional[EnvironmentBlock] = None,
                       **kwargs) -> Dict[str, str]:
    """Every recognised variable resolved to its path, for one USMT context.

    The result is directly usable as a ``MigApp.xml`` / ``MigUser.xml``
    substitution table.
    """
    if block is None:
        block = get_default_block()
    names = USMT_CONTEXTS.get(name)
    if names is None:
        raise KeyError(f"unknown USMT context: {name!r}")
    out: Dict[str, str] = {}
    for var in names:
        value = resolve_usmt_variable(var, block, **kwargs)
        if value is not None:
            out[var] = value
    return out


# ---------------------------------------------------------------------------
# Command-line inspection
# ---------------------------------------------------------------------------

def cmd_set_output(block: Optional[EnvironmentBlock] = None,
                   name: Optional[str] = None) -> str:
    """Reproduce the output of ``cmd.exe``'s ``set`` command.

    ``set`` with no argument prints every variable as ``NAME=VALUE``.
    ``set NAME`` prints just that one, or the error line
    ``Environment variable NAME not defined``.
    """
    if block is None:
        block = get_default_block()
    if name is not None:
        value = block.get(name)
        if value is None:
            return f"Environment variable {name} not defined"
        return f"{name}={value}"
    return "\r\n".join(f"{k}={v}" for k, v in block.items())


def cmd_expand(text: str, block: Optional[EnvironmentBlock] = None) -> str:
    """Expand ``%VAR%`` references the way ``cmd.exe`` does.

    Two differences from :func:`ExpandEnvironmentStringsA`:

    * An undefined variable is left as the literal ``%VAR%`` text rather
      than expanding to an empty string.  ``cmd.exe`` only removes an
      undefined reference in some contexts, and leaving it literal is
      what makes ``if defined VAR`` the idiomatic test.
    * The expansion is single-pass.  A value that itself contains
      ``%OTHER%`` is inserted verbatim, because ``cmd.exe`` expands the
      command line once, before the command runs.
    """
    if block is None:
        block = get_default_block()

    def _sub(match: "re.Match[str]") -> str:
        var = match.group(1)
        value = block.get(var)
        return value if value is not None else match.group(0)

    return _VAR_RE.sub(_sub, text)


def cmd_echo(text: str, block: Optional[EnvironmentBlock] = None) -> str:
    """Reproduce the output of ``cmd.exe``'s ``echo`` command.

    ``echo`` prints whatever follows it, followed by a single space.
    """
    return cmd_expand(text, block) + " "


def powershell_get_env(name: str,
                       block: Optional[EnvironmentBlock] = None
                       ) -> Optional[str]:
    """The value of ``$Env:NAME`` in PowerShell.

    Returns ``None`` when the variable is not defined, which is how
    PowerShell models "no value" (``$Env:NOPE`` is ``$null``).
    """
    if block is None:
        block = get_default_block()
    return block.get(name)


def powershell_env_listing(block: Optional[EnvironmentBlock] = None) -> str:
    """Reproduce the output of ``Get-ChildItem Env:``.

    PowerShell renders the Env: drive as a two-column table::

        Name                          Value
        ----                          -----
        ALLUSERSPROFILE              C:\\ProgramData
    """
    if block is None:
        block = get_default_block()
    rows = block.items()
    if not rows:
        return ""
    name_width = max(4, max(len(n) for n, _ in rows))
    value_width = max(5, max(len(v) for _, v in rows))
    out = [f"{'Name'.ljust(name_width)}  {'Value'}",
           f"{'-' * name_width}  {'-' * value_width}"]
    out.extend(f"{n.ljust(name_width)}  {v}" for n, v in rows)
    return "\r\n".join(out)


# ---------------------------------------------------------------------------
# Variable-name rules and the set / setx commands
# ---------------------------------------------------------------------------

#: Characters that may not appear in an environment-variable name.
#: ``=`` is the name/value separator in the block and NUL terminates it.
_INVALID_NAME_CHARS = ("=", "\x00")


def is_valid_variable_name(name: str) -> bool:
    """``True`` when ``name`` may be used as an environment-variable name.

    Windows accepts almost anything except the empty string, a name
    containing ``=`` (the separator) or NUL, and a name beginning with
    ``=``.  Names are otherwise case-insensitive.
    """
    if not name or not isinstance(name, str):
        return False
    if name.startswith("="):
        return False
    return not any(ch in name for ch in _INVALID_NAME_CHARS)


def cmd_set(env: "ScopedEnvironment", name: str, value: Optional[str] = None
            ) -> bool:
    """Apply the ``set`` command the way ``cmd.exe`` does.

    * ``set NAME=VALUE`` defines the variable in the **process** scope.
    * ``set NAME=`` (an empty value) *removes* the variable -- this is a
      cmd.exe behaviour that differs from the Win32 API, where
      ``SetEnvironmentVariable(name, "")`` leaves an empty variable
      behind.
    * ``set NAME`` (no ``=``) does not modify anything; it only prints
      the value, which is why ``value`` is ``None`` here.

    Returns ``True`` when the environment changed.
    """
    if not is_valid_variable_name(name):
        return False
    if value is None:
        # ``set NAME`` -- read-only, no change.
        return False
    if value == "":
        # ``set NAME=`` -- cmd.exe deletes the variable entirely.
        return env.unset(name, EnvScope.PROCESS)
    return env.set(name, value, EnvScope.PROCESS)


def setx(env: "ScopedEnvironment", name: str, value: str,
         scope: EnvScope = EnvScope.USER) -> bool:
    """Apply the ``setx`` command (Windows XP SP2 and later).

    ``setx`` differs from ``set`` in four ways that matter:

    1. It writes to the **registry**, so the value persists for future
       sessions.  The default is the user scope; machine scope requires
       elevation.
    2. It does **not** affect the environment of the shell that ran it
       -- the change only shows up in *new* processes.
    3. The value is limited to **1024 characters**.  Anything longer is
       **cropped**, not rejected -- and because the crop is applied to
       the value that is written, using ``setx`` on a long existing
       variable can silently destroy the tail of it.
    4. It **expands** any ``%VAR%`` reference in the value before
       storing it, so the stored value has no references left in it.
       Later changes to the referenced variable will no longer be
       reflected.
    """
    if not is_valid_variable_name(name):
        return False
    if scope is EnvScope.PROCESS:
        # ``setx`` cannot write to the (non-persistent) process scope.
        return False
    if len(value) > 1024:
        log.warning("setx: cropping %s from %d to 1024 characters",
                    name, len(value))
        value = value[:1024]
    # ``setx`` flattens variable references before storing.
    value = ExpandEnvironmentStringsA(value, env.effective())
    return env.set(name, value, scope)


# ---------------------------------------------------------------------------
# WOW64 redirection
# ---------------------------------------------------------------------------

def apply_wow64_redirection(block: Optional[EnvironmentBlock] = None,
                             *,
                             app_is_32bit: bool = False,
                             native_arch: str = "AMD64",
                             os_is_64bit: bool = True
                             ) -> EnvironmentBlock:
    """Return the environment a WOW64 child process would receive.

    When Windows starts a 32-bit process it rewrites a handful of
    variables so the child sees the right directories for its own
    bitness.  The official table is:

    ================= ================================== ==========
    Process           Variable                            Value
    ================= ================================== ==========
    64-bit            ``PROCESSOR_ARCHITECTURE``          AMD64
                      ``ProgramFiles``                    the 64-bit dir
                      ``ProgramW6432``                    the 64-bit dir
                      ``CommonProgramFiles``              the 64-bit dir
                      ``CommonProgramW6432``              the 64-bit dir
    32-bit            ``PROCESSOR_ARCHITECTURE``          x86
                      ``PROCESSOR_ARCHITEW6432``          the native arch
                      ``ProgramFiles``                    ``(x86)`` dir
                      ``ProgramW6432``                    the 64-bit dir
                      ``CommonProgramFiles``              ``(x86)`` dir
                      ``CommonProgramW6432``              the 64-bit dir
    ================= ================================== ==========

    On a 32-bit Windows there is no redirection at all.

    Parameters
    ----------
    block:
        The block holding the *canonical* (64-bit) values.  Defaults to
        the process default block.
    app_is_32bit:
        ``True`` when the child process is a 32-bit application.
    native_arch:
        The machine's real architecture (``AMD64``, ``ARM64``, ...).
    os_is_64bit:
        ``True`` on a 64-bit Windows installation.
    """
    if block is None:
        block = get_default_block()
    out = EnvironmentBlock(_vars=dict(block._vars),
                           _scopes=dict(block._scopes),
                           host_fallback=block.host_fallback)

    if not os_is_64bit:
        # A 32-bit OS has no WOW64 layer: nothing is redirected.
        out["PROCESSOR_ARCHITECTURE"] = "x86"
        out._vars.pop("PROCESSOR_ARCHITEW6432", None)
        return out

    program_files = out.get("ProgramFiles") or r"C:\Program Files"
    program_files_x86 = (out.get("ProgramFiles(x86)")
                         or r"C:\Program Files (x86)")
    common = out.get("CommonProgramFiles") or r"C:\Program Files\Common Files"
    common_x86 = (out.get("CommonProgramFiles(x86)")
                  or r"C:\Program Files (x86)\Common Files")

    if app_is_32bit:
        out["PROCESSOR_ARCHITECTURE"] = "x86"
        out["PROCESSOR_ARCHITEW6432"] = native_arch
        out["ProgramFiles"] = program_files_x86
        out["ProgramW6432"] = program_files
        out["CommonProgramFiles"] = common_x86
        out["CommonProgramW6432"] = common
    else:
        out["PROCESSOR_ARCHITECTURE"] = native_arch
        out._vars.pop("PROCESSOR_ARCHITEW6432", None)
        out["ProgramFiles"] = program_files
        out["ProgramW6432"] = program_files
        out["CommonProgramFiles"] = common
        out["CommonProgramW6432"] = common
    return out


# ---------------------------------------------------------------------------
# Change notification
# ---------------------------------------------------------------------------

def broadcast_environment_change(timeout: int = 1000) -> bool:
    """Notify running applications that the environment block changed.

    Windows does this by broadcasting ``WM_SETTINGCHANGE`` with
    ``lParam`` set to the string ``"Environment"``::

        SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                           "Environment", SMTO_ABORTIFHUNG, 1000, &result);

    Only ``explorer.exe`` actually acts on it -- it rebuilds its own
    environment block from the registry.  Other shells (cmd, PowerShell,
    terminals) keep the block they were started with, which is why
    Windows tells you to *restart* them for a new value to register.
    """
    from .win_user32 import broadcast_setting_change   # local: avoid cycle
    return broadcast_setting_change("Environment", timeout)


def environment_change_log() -> List[Tuple[int, str]]:
    """Every ``WM_SETTINGCHANGE`` broadcast issued so far."""
    from .win_user32 import setting_change_log   # local: avoid cycle
    return setting_change_log()


# ---------------------------------------------------------------------------
# A shell session
# ---------------------------------------------------------------------------

@dataclass
class ShellSession:
    """A shell whose environment is backed by the registry.

    This models the behaviour that trips people up on Windows: the
    registry holds the *definition*, but every running process keeps a
    **snapshot**.  Writing a variable to the registry changes what a
    *new* shell will see; the shell you are sitting in keeps the old
    value until it is restarted.

    Example
    -------
    >>> from compatibility.env_registry import EnvRegistryStore
    >>> session = ShellSession(EnvRegistryStore())
    >>> session.store.set("user", "NEWVAR", "hello")
    True
    >>> session.refresh()
    True
    >>> session.live.get("NEWVAR")
    'hello'
    >>> session.stale_names()
    ['NEWVAR']
    """

    store: object
    live: ScopedEnvironment = field(default_factory=ScopedEnvironment)
    #: The block this session started with -- what a child process
    #: inherits when it is spawned from this shell.
    inherited: EnvironmentBlock = field(default_factory=EnvironmentBlock)

    def __post_init__(self) -> None:
        if self.live.host_fallback:
            self.live.host_fallback = False

    # -- reading -------------------------------------------------------

    def live_block(self) -> EnvironmentBlock:
        """The environment this shell currently sees."""
        return self.live.effective()

    def child_block(self) -> EnvironmentBlock:
        """The environment a **child** process of this shell receives.

        ``CreateProcess`` hands the parent's environment block to the
        child unchanged.  A child started from a shell that has not been
        refreshed therefore inherits the *old* values -- which is why
        starting the installer from a stale command prompt uses the old
        ``PATH``.
        """
        blk = EnvironmentBlock(host_fallback=self.live.host_fallback)
        blk.update(self.live.system.to_dict(), scope=EnvScope.SYSTEM)
        blk.update(self.live.user.to_dict(), scope=EnvScope.USER)
        blk.update(self.live.process.to_dict(), scope=EnvScope.PROCESS)
        return blk

    def new_shell_block(self) -> EnvironmentBlock:
        """The environment a **newly launched shell** receives.

        Explorer.exe is the process that handles ``WM_SETTINGCHANGE``:
        it rebuilds its own block from the registry.  A shell launched
        from a refreshed Explorer therefore starts with the registry
        values, even though the shell you launched it from is still
        showing the old ones.  This is the "open a new command prompt"
        half of the Windows behaviour.
        """
        blk = EnvironmentBlock(host_fallback=self.live.host_fallback)
        for scope in (EnvScope.SYSTEM, EnvScope.USER):
            registry_name = scope_registry_name(scope)
            if registry_name is None:
                continue
            for key, entry in self.store.read(registry_name).items():
                blk[key] = entry.value
        blk.update(self.live.process.to_dict(), scope=EnvScope.PROCESS)
        return blk

    def new_process_block(self) -> EnvironmentBlock:
        """Alias of :meth:`new_shell_block` for readability at call sites."""
        return self.new_shell_block()

    def stale_names(self) -> List[str]:
        """The variables the registry has but this shell has not seen.

        These are exactly the ones the user is told to pick up by
        restarting their command prompt.
        """
        out: List[str] = []
        for scope in (EnvScope.SYSTEM, EnvScope.USER):
            registry_name = scope_registry_name(scope)
            if registry_name is None:
                continue
            entries = self.store.read(registry_name)
            live = self.live.table(scope)
            for key, entry in entries.items():
                if live.get(key) != entry.value:
                    if key not in {n.upper() for n in out}:
                        out.append(key)
        return sorted(out)

    # -- writing -------------------------------------------------------

    def refresh(self) -> bool:
        """Re-read the registry into this shell's live environment.

        Returns ``True`` when something changed.  A real shell cannot do
        this -- it has to be restarted -- which is why
        :meth:`stale_names` exists.
        """
        changed = False
        for scope in (EnvScope.SYSTEM, EnvScope.USER):
            registry_name = scope_registry_name(scope)
            if registry_name is None:
                continue
            entries = self.store.read(registry_name)
            live = self.live.table(scope)
            for key, entry in entries.items():
                if live.get(key) != entry.value:
                    live[key] = entry.value
                    changed = True
            for key in [k for k in live.keys() if k.upper() not in entries]:
                del live[key]
                changed = True
        return changed

    def set_persistent(self, scope: EnvScope, name: str, value: str,
                       *, notify: bool = True) -> bool:
        """Write a variable to the registry and notify the system.

        The change does **not** alter this shell's own environment --
        exactly like the Windows behaviour.
        """
        if scope is EnvScope.PROCESS:
            return self.live.set(name, value, EnvScope.PROCESS)
        registry_name = scope_registry_name(scope)
        if registry_name is None:
            return False
        changed = self.store.set(registry_name, name, value)
        if changed and notify:
            broadcast_environment_change()
        return changed

    def unset_persistent(self, scope: EnvScope, name: str,
                         *, notify: bool = True) -> bool:
        """Remove a variable from the registry and notify the system."""
        if scope is EnvScope.PROCESS:
            return self.live.unset(name, EnvScope.PROCESS)
        registry_name = scope_registry_name(scope)
        if registry_name is None:
            return False
        changed = self.store.unset(registry_name, name)
        if changed and notify:
            broadcast_environment_change()
        return changed


# ---------------------------------------------------------------------------
# Installer-relevant variables
# ---------------------------------------------------------------------------

#: The environment variables a Windows installer reads or writes, with a
#: short note on what each one is for.  This is the working set for
#: software installation: everything an installer needs in order to
#: decide *where* to install and *how* to find its own files.
INSTALLER_ENV_VARS: Dict[str, str] = {
    # -- Where to install --
    "ProgramFiles": "Native Program Files -- per-machine installs",
    "ProgramFiles(x86)": "32-bit Program Files -- 32-bit per-machine installs",
    "ProgramW6432": "Native Program Files, visible from a 32-bit process",
    "CommonProgramFiles": "Shared components, native",
    "CommonProgramFiles(x86)": "Shared components, 32-bit",
    "CommonProgramW6432": "Native shared components, visible from 32-bit",
    "LOCALAPPDATA": "Per-user application data -- per-user installs",
    "APPDATA": "Roaming per-user application data",
    "ProgramData": "Per-machine application data",
    "ALLUSERSPROFILE": "Per-machine profile root (C:\\ProgramData)",
    "USERPROFILE": "The signed-in user's profile root",
    "PUBLIC": "The Public profile",
    "SystemRoot": "The Windows directory (C:\\Windows)",
    "SystemDrive": "The drive Windows is installed on",
    # -- Working space --
    "TEMP": "Per-user temporary directory",
    "TMP": "Per-user temporary directory",
    # -- Executable resolution --
    "PATH": "The executable search path",
    "PATHEXT": "The extensions treated as executable",
    "ComSpec": "The command interpreter",
    # -- Architecture --
    "PROCESSOR_ARCHITECTURE": "x86 / AMD64 / ARM64",
    "PROCESSOR_ARCHITEW6432": "Native architecture, seen from a 32-bit process",
    "NUMBER_OF_PROCESSORS": "Logical processor count",
    "PROCESSOR_IDENTIFIER": "CPU identification string",
    "PROCESSOR_LEVEL": "CPU level",
    "PROCESSOR_REVISION": "CPU revision",
    # -- Installer plumbing --
    "ALLUSERS": "MSI context: 1=per-machine, 2=dynamic, unset=per-user",
    "MSIINSTALLPERUSER": "MSI 5.0+: force the per-user context",
    "INSTALLDIR": "Target directory requested by the installer",
    "TARGETDIR": "Target directory requested by the installer",
    # -- Common toolchains --
    "ChocolateyInstall": "Chocolatey package root",
    "JAVA_HOME": "Java runtime root",
    "GOROOT": "Go toolchain root",
    "GOPATH": "Go workspace root",
    "NUGET_PACKAGES": "NuGet package cache",
    "DOTNET_ROOT": ".NET SDK / runtime root",
    "PYTHONHOME": "Python installation root",
    "PYTHONPATH": "Python module search path",
    "NODE_PATH": "Node module search path",
    "npm_config_prefix": "Global npm prefix",
    "NVM_HOME": "nvm-windows installation root",
    "NVM_SYMLINK": "nvm-windows symlink target",
    # -- Visual Studio / Windows SDK --
    "VSINSTALLDIR": "Visual Studio installation directory",
    "VCINSTALLDIR": "Visual C++ toolchain directory",
    "WindowsSdkDir": "Windows SDK root",
    "WindowsSdkVerBinPath": "Windows SDK bin directory",
    "WindowsSdkBinPath": "Windows SDK bin directory (x86)",
    "VisualStudioVersion": "Visual Studio version number",
    "Platform": "Target platform (x64, Win32, ARM64)",
    "FrameworkDir": ".NET Framework directory",
    "FrameworkVersion": ".NET Framework version",
    "MSBuildExtensionsPath": "MSBuild extensions directory",
    "MSBuildSDKsPath": "MSBuild SDKs directory",
}


def installer_variables(block: Optional[EnvironmentBlock] = None,
                        names: Optional[Iterable[str]] = None
                        ) -> Dict[str, str]:
    """Resolve the installer-relevant variables of a block.

    Only the variables that are actually defined are returned, so the
    result is a direct answer to "what does the installer get to see?".
    """
    if block is None:
        block = get_default_block()
    wanted = names if names is not None else INSTALLER_ENV_VARS
    out: Dict[str, str] = {}
    for name in wanted:
        value = block.get(name)
        if value is not None:
            out[name] = value
    return out


# ---------------------------------------------------------------------------
# PATH search
# ---------------------------------------------------------------------------

def search_path(filename: str,
                block: Optional[EnvironmentBlock] = None,
                *,
                cwd: Optional[str] = None,
                must_exist: bool = True) -> Optional[str]:
    """Resolve ``filename`` the way the Windows shell does.

    The search order is:

    1. The current directory (implicitly, before ``PATH``).
    2. Each directory of ``PATH``, left to right.

    When ``filename`` has no extension the ``PATHEXT`` suffixes are
    tried in order.  With ``must_exist=False`` the first *candidate*
    path is returned even if nothing is on disk, which is useful when
    simulating a lookup on a machine whose file system is not present.
    """
    if block is None:
        block = get_default_block()
    if cwd is None:
        try:
            cwd = os.getcwd()
        except OSError:
            cwd = ""

    candidates: List[str] = []

    def _add(directory: str) -> None:
        if not directory:
            return
        base = os.path.join(directory, filename)
        if os.path.splitext(filename)[1]:
            candidates.append(base)
        else:
            for ext in block.pathext():
                candidates.append(base + ext)
            candidates.append(base)

    _add(cwd)
    for entry in parse_path(block.get("PATH") or ""):
        _add(entry)

    for cand in candidates:
        if not must_exist:
            return cand
        if os.path.isfile(cand):
            return cand
    return None


def which(filename: str,
          block: Optional[EnvironmentBlock] = None,
          *,
          cwd: Optional[str] = None) -> Optional[str]:
    """The full path of ``filename`` if it is reachable, else ``None``."""
    return search_path(filename, block, cwd=cwd, must_exist=True)


# ---------------------------------------------------------------------------
# Process-level default block
# ---------------------------------------------------------------------------

_DEFAULT_ENV = EnvironmentBlock(host_fallback=True)
_DEFAULT_ENV.update(DEFAULT_SEED, scope=EnvScope.SYSTEM)
_DEFAULT_ENV.update({k: v for k, v in os.environ.items()
                     if k.upper() not in _DEFAULT_ENV},
                    scope=EnvScope.PROCESS)


def get_default_block() -> EnvironmentBlock:
    """Return a *copy* of the process-wide default block."""
    return EnvironmentBlock(_vars=dict(_DEFAULT_ENV._vars),
                           _scopes=dict(_DEFAULT_ENV._scopes),
                           host_fallback=_DEFAULT_ENV.host_fallback)


def get_default_var(name: str) -> Optional[str]:
    """Lookup helper for code that doesn't want to carry a block."""
    return _DEFAULT_ENV.get(name)


# ---------------------------------------------------------------------------
# Registry-backed lookup (optional)
# ---------------------------------------------------------------------------

def _read_registry_env(registry_view, path: str) -> Dict[str, str]:
    """Read ``HKCU\\Environment`` or ``HKLM\\...\\Environment`` values.

    The :class:`~compatibility.registry_view.InMemoryRegistry` API is
    used so we don't accidentally lock the host's registry when the
    caller points us at a sandboxed view.
    """
    if registry_view is None:
        return {}
    result: Dict[str, str] = {}
    try:
        for name in registry_view.enum_values(path):
            v = registry_view.get_value(path, name)
            if v is None:
                continue
            try:
                result[name] = v.as_string()
            except (ValueError, UnicodeDecodeError):
                # Non-string types (REG_DWORD, REG_BINARY) are not env vars.
                continue
    except Exception as exc:    # noqa: BLE001 -- best effort
        log.debug("registry env %s unreadable: %s", path, exc)
    return result


def build_block(registry_view=None,
                *,
                include_hkcu: bool = True,
                include_hklm: bool = True,
                seed: bool = True,
                host_fallback: bool = True) -> EnvironmentBlock:
    """Build a complete environment block.

    Precedence (low -> high):

    1. :data:`DEFAULT_SEED` (only when ``seed=True``).
    2. ``HKLM\\...\\Environment`` (system).
    3. ``HKCU\\Environment`` (user).
    4. The current process ``os.environ`` (process, only via the
       ``host_fallback`` flag at lookup time).
    """
    block = EnvironmentBlock(host_fallback=host_fallback)
    if seed:
        block.update(DEFAULT_SEED, scope=EnvScope.SYSTEM)
    if include_hklm:
        block.update(_read_registry_env(registry_view, HKLM_ENV_PATH),
                     scope=EnvScope.SYSTEM)
    if include_hkcu:
        block.update(_read_registry_env(registry_view, HKCU_ENV_PATH),
                     scope=EnvScope.USER)
    return block


# ---------------------------------------------------------------------------
# Public Win32-shaped helpers
# ---------------------------------------------------------------------------

#: Pattern that matches ``%NAME%`` references (and also the case where
#: the variable name contains parentheses like ``%ProgramFiles(x86)%``).
_VAR_RE = re.compile(r"%([A-Za-z][A-Za-z0-9_()\s]*)%")

#: Cap on recursive expansion (matches Win32's MAX_PATH-ish safety bound).
_MAX_EXPANSION_DEPTH = 32


def _do_expand(s: str, block: EnvironmentBlock, depth: int = 0) -> str:
    """Recursive ``%NAME%`` substitution.

    Variables that are missing or contain ``None`` resolve to themselves
    (matches the Win32 contract -- an unresolvable ``%FOO%`` stays as
    ``%FOO%`` so an installer can detect it).  Cycles are broken by
    aborting after ``_MAX_EXPANSION_DEPTH`` passes.
    """
    if not s:
        return s
    if depth >= _MAX_EXPANSION_DEPTH:
        return s
    out_parts: List[str] = []
    last = 0
    for m in _VAR_RE.finditer(s):
        out_parts.append(s[last:m.start()])
        name = m.group(1).strip()
        value = block.get(name)
        if value is None or value == m.group(0):
            # Unresolvable -- emit the literal token unchanged.
            out_parts.append(m.group(0))
        else:
            out_parts.append(_do_expand(value, block, depth + 1))
        last = m.end()
    out_parts.append(s[last:])
    return "".join(out_parts)


def GetEnvironmentVariableA(name: str, block: Optional[EnvironmentBlock] = None
                            ) -> Optional[str]:
    """Return the value of ``name`` from ``block`` (or the default block).

    Returns ``None`` when the variable is not set (matches the Win32
    contract that distinguishes a missing variable from an empty one).
    """
    b = block if block is not None else _DEFAULT_ENV
    return b.get(name)


def SetEnvironmentVariableA(name: str, value: Optional[str],
                            block: Optional[EnvironmentBlock] = None) -> bool:
    """Win32 ``SetEnvironmentVariableA`` semantics.

    Passing ``value=None`` deletes the variable.  An empty string sets
    the variable to empty (which is distinct from removing it).
    """
    b = block if block is not None else _DEFAULT_ENV
    try:
        if value is None:
            if name in b:
                del b[name]
            return True
        b[name] = value
        return True
    except (ValueError, TypeError):
        return False


def ExpandEnvironmentStringsA(s: str,
                              block: Optional[EnvironmentBlock] = None) -> str:
    """Expand ``%NAME%`` references, recursively up to
    :data:`_MAX_EXPANSION_DEPTH` levels.

    Unknown variables are left untouched (matches the Win32 contract).
    """
    if not s:
        return s
    b = block if block is not None else _DEFAULT_ENV
    return _do_expand(s, b)


def GetEnvironmentStringsA(block: Optional[EnvironmentBlock] = None) -> bytes:
    """Return the Win32 double-null-terminated block of all variables."""
    b = block if block is not None else _DEFAULT_ENV
    return b.to_zz_block()


def GetEnvironmentVariableW(name: str,
                            block: Optional[EnvironmentBlock] = None
                            ) -> Optional[str]:
    """Wide-string flavour of :func:`GetEnvironmentVariableA`."""
    return GetEnvironmentVariableA(name, block)


def SetEnvironmentVariableW(name: str, value: Optional[str],
                          block: Optional[EnvironmentBlock] = None) -> bool:
    """Wide-string flavour of :func:`SetEnvironmentVariableA`."""
    return SetEnvironmentVariableA(name, value, block)


def ExpandEnvironmentStringsW(s: str,
                              block: Optional[EnvironmentBlock] = None) -> str:
    """Wide-string flavour of :func:`ExpandEnvironmentStringsA`."""
    return ExpandEnvironmentStringsA(s, block)


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    # 1. Case-insensitive lookup.
    blk = EnvironmentBlock()
    blk["PATH"] = r"C:\Windows"
    blk["Path"] = r"C:\Windows;overridden"
    if blk["PATH"] != r"C:\Windows;overridden":
        return False
    if len(blk) != 1:
        return False

    # 2. Default block has the canonical Win10 variables.
    d = get_default_block()
    for name in ("SystemRoot", "ComSpec", "OS", "PATHEXT", "AppData",
                 "LocalAppData", "ProgramData", "Public"):
        if d.get(name) is None:
            log.debug("missing canonical var: %s", name)
            return False

    # 3. Expansion.
    blk2 = EnvironmentBlock()
    blk2["FOO"] = "%BAR%"
    blk2["bar"] = "baz"
    if ExpandEnvironmentStringsA("%FOO%!", blk2) != "baz!":
        return False
    if ExpandEnvironmentStringsA("a %NOPE% b", blk2) != "a %NOPE% b":
        return False

    # 4. Double-null-terminated layout.  Each ``\0`` is a single
    # UTF-16LE code unit (2 bytes) so the block ends with ``\x00\x00``
    # (empty terminator) after the last variable's own ``\x00\x00``.
    # ``utf-16-le`` requires an even byte count -- drop the trailing
    # empty-terminator (2 bytes) before decoding.
    z = blk.to_zz_block()
    if not z.endswith(b"\x00\x00\x00\x00"):
        return False
    decoded = z[:-2].decode("utf-16-le")    # strip empty terminator
    parts = [p for p in decoded.split("\x00") if p]
    if parts != [r"PATH=C:\Windows;overridden"]:
        return False

    # 5. PATHEXT matching.
    if not blk.matches_pathext("foo.EXE"):
        return False
    if blk.matches_pathext("foo.txt"):
        return False

    # 6. PATH add/remove.
    blk3 = EnvironmentBlock()
    blk3["PATH"] = r"C:\A;C:\B"
    if not blk3.add_path_entry(r"C:\C"):
        return False
    if blk3.get("PATH") != r"C:\A;C:\B;C:\C":
        return False
    if blk3.add_path_entry(r"C:\C"):        # duplicate -> no-op
        return False
    blk3.add_path_entry(r"C:\Z", at_front=True)
    if blk3.get("PATH") != r"C:\Z;C:\A;C:\B;C:\C":
        return False
    if not blk3.remove_path_entry(r"C:\A"):
        return False
    if blk3.get("PATH") != r"C:\Z;C:\B;C:\C":
        return False

    # 7. Dynamic ``%CD%`` -- must resolve to the host cwd.
    if ExpandEnvironmentStringsA("cwd=%CD%") != f"cwd={os.getcwd()}":
        return False

    # 8. Set/Remove semantics.
    blk4 = EnvironmentBlock()
    SetEnvironmentVariableA("X", "1", blk4)
    SetEnvironmentVariableA("Y", "", blk4)
    SetEnvironmentVariableA("X", None, blk4)        # remove
    if blk4.get("X") is not None:
        return False
    if blk4.get("Y") != "":
        return False

    # 9. Recognised name catalogue.
    if "PATH" not in WIN10_RECOGNISED or "APPDATA" not in WIN10_RECOGNISED:
        return False

    # 10. The USMT catalogue has both contexts and no overlap.
    if len(USMT_USER_AND_SYSTEM) != 57 or len(USMT_USER_ONLY) != 40:
        log.debug("USMT split = %d / %d", len(USMT_USER_AND_SYSTEM),
                  len(USMT_USER_ONLY))
        return False
    if set(USMT_USER_AND_SYSTEM) & set(USMT_USER_ONLY):
        return False
    if len(USMT_RECOGNISED) != 97:
        log.debug("USMT union = %d", len(USMT_RECOGNISED))
        return False
    if not set(USMT_RECOGNISED) <= set(WIN10_RECOGNISED):
        return False

    # 11. USMT resolution: alias, template and CSIDL strategies.
    if resolve_usmt_variable("PROGRAMFILES") != r"C:\Program Files":
        return False
    desktop = resolve_usmt_variable("CSIDL_DEFAULT_DESKTOP")
    if desktop != r"C:\Users\Default\Desktop":
        log.debug("CSIDL_DEFAULT_DESKTOP = %r", desktop)
        return False
    sysdir = resolve_usmt_variable("CSIDL_SYSTEM")
    if sysdir != r"C:\Windows\system32":
        log.debug("CSIDL_SYSTEM = %r", sysdir)
        return False
    if resolve_usmt_variable("CSIDL_DESKTOP", blk) is None:
        return False
    if resolve_usmt_variable("NOT_A_REAL_VARIABLE") is not None:
        return False

    # 12. Scoped precedence: Process > User > System.
    # ``host_fallback`` is off so the host's own PATH cannot mask a
    # scope that was explicitly emptied.
    env = ScopedEnvironment(host_fallback=False)
    env.set("Path", r"C:\System", EnvScope.SYSTEM)
    env.set("Path", r"C:\User", EnvScope.USER)
    if env.get("PATH") != r"C:\User":
        return False
    env.set("Path", r"C:\Process", EnvScope.PROCESS)
    if env.get("PATH") != r"C:\Process":
        return False
    if env.scope_of("PATH") is not EnvScope.PROCESS:
        return False
    if env.get_from("PATH", EnvScope.SYSTEM) != r"C:\System":
        return False
    env.unset("Path", EnvScope.PROCESS)
    if env.get("PATH") != r"C:\User":
        return False
    env.unset("Path")
    if env.get("PATH") is not None:
        return False
    # Case is preserved for display but not for lookup.
    env.set("MyVar", "1", EnvScope.USER)
    if env.get("myvar") != "1":
        return False
    if env.names(EnvScope.USER) != ["MyVar"]:
        log.debug("scoped names = %r", env.names(EnvScope.USER))
        return False

    # 13. cmd.exe inspection.
    blk5 = EnvironmentBlock()
    blk5["FOO"] = "bar"
    if cmd_set_output(blk5) != "FOO=bar":
        return False
    if cmd_set_output(blk5, "FOO") != "FOO=bar":
        return False
    if "not defined" not in cmd_set_output(blk5, "NOPE"):
        return False
    # An undefined variable stays literal in cmd, and values are not
    # re-scanned.
    blk5["SELF"] = "%OTHER%"
    blk5["OTHER"] = "x"
    if cmd_expand("%SELF%", blk5) != "%OTHER%":
        return False
    if cmd_expand("%NOPE%", blk5) != "%NOPE%":
        return False
    if cmd_echo("hi", blk5) != "hi ":
        return False

    # 14. PowerShell inspection.
    if powershell_get_env("FOO", blk5) != "bar":
        return False
    if powershell_get_env("NOPE", blk5) is not None:
        return False
    listing = powershell_env_listing(blk5)
    if "Name" not in listing or "FOO" not in listing:
        return False

    # 15. PATH search: the current directory is searched first.
    blk6 = EnvironmentBlock()
    blk6["PATH"] = r"C:\Windows"
    blk6["PATHEXT"] = ".COM;.EXE"
    cand = search_path("cmd.exe", blk6, cwd=r"C:\Windows", must_exist=False)
    if cand != r"C:\Windows\cmd.exe":
        log.debug("search_path = %r", cand)
        return False

    # 16. A full USMT context table builds without error.
    ctx = build_usmt_context("System")
    if len(ctx) < 50:
        log.debug("System context resolved %d vars", len(ctx))
        return False

    # 17. Variable-name rules and the set / setx semantics.
    if is_valid_variable_name("") or is_valid_variable_name("A=B"):
        return False
    if not is_valid_variable_name("ProgramFiles(x86)"):
        return False
    env7 = ScopedEnvironment(host_fallback=False)
    env7.set("KEEP", "1", EnvScope.PROCESS)
    # ``set NAME=`` deletes the variable (cmd.exe semantics).
    if not cmd_set(env7, "KEEP", ""):
        return False
    if env7.get("KEEP") is not None:
        return False
    # ``set NAME`` only prints; it must not change anything.
    env7.set("KEEP", "1", EnvScope.PROCESS)
    if cmd_set(env7, "KEEP"):
        return False
    if env7.get("KEEP") != "1":
        return False
    # ``setx`` writes to the persistent scope and rejects long values.
    if not setx(env7, "PERSIST", "v", EnvScope.USER):
        return False
    if env7.get_from("PERSIST", EnvScope.USER) != "v":
        return False
    # ``setx`` CROPS at 1024 characters rather than rejecting.
    if not setx(env7, "TOOLONG", "x" * 1025, EnvScope.USER):
        return False
    if len(env7.get_from("TOOLONG", EnvScope.USER) or "") != 1024:
        return False
    if setx(env7, "PROC", "v", EnvScope.PROCESS):
        return False

    # 18. WOW64 redirection.
    base = EnvironmentBlock(host_fallback=False)
    base["ProgramFiles"] = r"C:\Program Files"
    base["ProgramFiles(x86)"] = r"C:\Program Files (x86)"
    base["CommonProgramFiles"] = r"C:\Program Files\Common Files"
    base["CommonProgramFiles(x86)"] = r"C:\Program Files (x86)\Common Files"
    w64 = apply_wow64_redirection(base, app_is_32bit=False)
    if w64.get("PROCESSOR_ARCHITECTURE") != "AMD64":
        return False
    if w64.get("ProgramFiles") != r"C:\Program Files":
        return False
    if w64.get("ProgramW6432") != r"C:\Program Files":
        return False
    if w64.get("PROCESSOR_ARCHITEW6432") is not None:
        return False
    w32 = apply_wow64_redirection(base, app_is_32bit=True)
    if w32.get("PROCESSOR_ARCHITECTURE") != "x86":
        return False
    if w32.get("PROCESSOR_ARCHITEW6432") != "AMD64":
        return False
    if w32.get("ProgramFiles") != r"C:\Program Files (x86)":
        return False
    if w32.get("ProgramW6432") != r"C:\Program Files":
        return False
    if w32.get("CommonProgramFiles") != r"C:\Program Files (x86)\Common Files":
        return False
    # On a 32-bit OS nothing is redirected.
    w32os = apply_wow64_redirection(base, app_is_32bit=True,
                                     os_is_64bit=False)
    if w32os.get("PROCESSOR_ARCHITEW6432") is not None:
        return False

    # 19. The environment-change broadcast is recorded.
    before = len(environment_change_log())
    if not broadcast_environment_change():
        return False
    if len(environment_change_log()) != before + 1:
        return False
    if environment_change_log()[-1][1] != "Environment":
        return False

    # 20. The installer variable catalogue resolves.
    ivars = installer_variables()
    if "PATH" not in ivars or "SystemRoot" not in ivars:
        return False
    for name in INSTALLER_ENV_VARS:
        if not name:
            return False

    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)