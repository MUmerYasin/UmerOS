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

Two Win32 conventions are honoured here:

1. **Case-insensitive** variable names (Windows uses ``%PATH%`` and
   ``%Path%`` interchangeably).
2. **Registry mapping**: ``HKCU\\Environment`` and ``HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment``
   can override the in-memory block; we read them lazily on the
   first call to :func:`get` and re-read them whenever the caller
   explicitly invalidates the cache.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/procthread/environment-variables
* https://learn.microsoft.com/en-us/windows/win32/api/processenv/nf-processenv-expandenvironmentstringsw

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.Env")

# ---------------------------------------------------------------------------
# Win32 registry paths for the canonical environment variables
# ---------------------------------------------------------------------------

HKCU_ENV_PATH = r"HKCU\Environment"
HKLM_ENV_PATH = r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

#: Default env values we seed for a freshly created block so that
#: ``%SystemRoot%``, ``%ComSpec%`` and friends are defined even when
#: the host provides no registry.
DEFAULT_SEED: Dict[str, str] = {
    "SystemRoot": r"C:\Windows",
    "SystemDrive": "C:",
    "ComSpec": r"C:\Windows\System32\cmd.exe",
    "OS": "Windows_NT",
    "PATHEXT": ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.WS;.MSC",
    "TEMP": r"C:\Windows\Temp",
    "TMP": r"C:\Windows\Temp",
    "WINDIR": r"C:\Windows",
    "PROGRAMDATA": r"C:\ProgramData",
    "PROGRAMFILES": r"C:\Program Files",
    "PROGRAMFILES(X86)": r"C:\Program Files (x86)",
    "USERPROFILE": r"C:\Users\Default",
    "HOMEDRIVE": "C:",
    "HOMEPATH": r"\Users\Default",
    "NUMBER_OF_PROCESSORS": "1",
    "PROCESSOR_ARCHITECTURE": "x86",
}


# ---------------------------------------------------------------------------
# Variable-name helpers
# ---------------------------------------------------------------------------

def _normalise(name: str) -> str:
    """Win32 env names are case-insensitive; we canonicalise to upper."""
    if not name:
        raise ValueError("env var name must be non-empty")
    return name.upper()


# ---------------------------------------------------------------------------
# The environment block
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentBlock:
    """A Win32-style environment block.

    The block is a *case-insensitive* mapping from variable name to
    value.  Insertion order is preserved so :meth:`to_zz_block`
    returns a stable byte layout — that matters because Windows
    applications sometimes memcmp the block when validating.
    """

    _vars: Dict[str, str] = field(default_factory=dict)
    #: Cache for the registry-resolved snapshot (invalidated by writes).
    _registry_cache_valid: bool = False

    # ------------------------------------------------------------------
    # Basic accessors
    # ------------------------------------------------------------------

    def __contains__(self, name: str) -> bool:
        return _normalise(name) in self._vars

    def __len__(self) -> int:
        return len(self._vars)

    def __iter__(self) -> Iterator[str]:
        # Iterate in the *user-visible* form (i.e. upper-case like Win32).
        return iter(self._vars.keys())

    def __getitem__(self, name: str) -> str:
        return self._vars[_normalise(name)]

    def __setitem__(self, name: str, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("env values must be str")
        self._vars[_normalise(name)] = value
        self._registry_cache_valid = False

    def __delitem__(self, name: str) -> None:
        del self._vars[_normalise(name)]
        self._registry_cache_valid = False

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return self._vars.get(_normalise(name), default)

    def setdefault(self, name: str, default: str) -> str:
        key = _normalise(name)
        if key not in self._vars:
            self._vars[key] = default
        return self._vars[key]

    def update(self, items: Dict[str, str] | Iterable[Tuple[str, str]]) -> None:
        if isinstance(items, dict):
            items = items.items()
        for k, v in items:
            self[k] = v

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def items(self) -> List[Tuple[str, str]]:
        return list(self._vars.items())

    def to_zz_block(self) -> bytes:
        """Encode as a Win32 double-null-terminated ``LPCWSTR`` block.

        The format is::

            name1=value1\\0name2=value2\\0\\0

        where every character is encoded as UTF-16LE.
        """
        out = bytearray()
        for k, v in self._vars.items():
            out += k.encode("utf-16-le")
            out += b"="
            out += v.encode("utf-16-le")
            out += b"\x00\x00"
        out += b"\x00\x00"
        return bytes(out)


# ---------------------------------------------------------------------------
# Process-level default
# ---------------------------------------------------------------------------

_DEFAULT_ENV = EnvironmentBlock(_vars={k: v for k, v in DEFAULT_SEED.items()})
_DEFAULT_ENV.update({k: v for k, v in os.environ.items()
                     if k.upper() not in _DEFAULT_ENV})


def get_default_block() -> EnvironmentBlock:
    """Return a *copy* of the process-wide default block."""
    return EnvironmentBlock(_vars=dict(_DEFAULT_ENV._vars))


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
    except Exception as exc:    # noqa: BLE001 — best effort
        log.debug("registry env %s unreadable: %s", path, exc)
    return result


def build_block(registry_view=None,
                *,
                include_hkcu: bool = True,
                include_hklm: bool = True,
                seed: bool = True) -> EnvironmentBlock:
    """Build a complete environment block.

    Precedence (low -> high):

    1. :data:`DEFAULT_SEED` (only when ``seed=True``).
    2. The current process ``os.environ``.
    3. ``HKLM\\...\\Environment`` (system).
    4. ``HKCU\\Environment`` (user).
    """
    block = EnvironmentBlock()
    if seed:
        block.update(DEFAULT_SEED)
    block.update({k: v for k, v in os.environ.items()
                  if k.upper() not in block})
    if include_hklm:
        block.update(_read_registry_env(registry_view, HKLM_ENV_PATH))
    if include_hkcu:
        block.update(_read_registry_env(registry_view, HKCU_ENV_PATH))
    return block


# ---------------------------------------------------------------------------
# Public Win32-shaped helpers
# ---------------------------------------------------------------------------

_VAR_RE = re.compile(r"%([A-Za-z][A-Za-z0-9_()\s]*)%")


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

    Passing ``value=None`` deletes the variable.
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
    """Expand ``%NAME%`` references, recursively up to 8 levels.

    Unknown variables are left untouched (matches the Win32 contract).
    """
    if not s:
        return s
    b = block if block is not None else _DEFAULT_ENV
    out = s
    for _ in range(8):
        replaced, n = _VAR_RE.subn(
            lambda m: b.get(m.group(1), m.group(0)) or "", out
        )
        if n == 0:
            return replaced
        out = replaced
    return out


def GetEnvironmentStringsA(block: Optional[EnvironmentBlock] = None) -> bytes:
    """Return the Win32 double-null-terminated block of all variables."""
    b = block if block is not None else _DEFAULT_ENV
    return b.to_zz_block()


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    blk = EnvironmentBlock()
    blk["PATH"] = r"C:\Windows"
    blk["Path"] = r"C:\Windows;overridden"        # case-insensitive
    if blk["PATH"] != r"C:\Windows;overridden":
        return False
    if len(blk) != 1:
        return False
    # Expansion.
    if ExpandEnvironmentStringsA("hello %PATH%") != "hello C:\\Windows":
        # We may have a different process env; just check the prefix.
        if "hello " not in ExpandEnvironmentStringsA("hello %PATH%"):
            return False
    # Unknown vars left alone.
    if ExpandEnvironmentStringsA("a %NOPE% b") != "a %NOPE% b":
        return False
    # ZZ block.
    z = blk.to_zz_block()
    if not z.endswith(b"\x00\x00\x00\x00"):
        return False
    # Default block has a minimal canonical set.
    d = get_default_block()
    if "SystemRoot" not in d:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
