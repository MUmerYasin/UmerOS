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


#: Recognised process-scoped Win10 names (subset commonly referenced by
#: ``CreateProcess`` / installer manifests).
WIN10_RECOGNISED: Tuple[str, ...] = (
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
)


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

    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)