"""
Umer OS /compatibility/env_registry — registry-backed environment store
======================================================================

Windows does not keep environment variables in a file.  It keeps the two
*persistent* scopes in the registry:

============================ ==============================================
Scope                        Registry key
============================ ==============================================
**User**                    ``HKCU\\Environment``
**System** (machine)        ``HKLM\\SYSTEM\\CurrentControlSet\\Control\\
                             Session Manager\\Environment``
============================ ==============================================

The third scope -- the *process* scope -- is never persisted; it lives
only in the running process's environment block.

Two registry value types matter here:

``REG_SZ``
    A plain string.  The value is used verbatim.

``REG_EXPAND_SZ``
    A string that may contain *unexpanded* ``%VAR%`` references.  The
    shell expands them when the variable is read.  ``Path`` is always
    stored as ``REG_EXPAND_SZ`` so that entries like
    ``%SystemRoot%\\system32`` keep working after the system directory
    moves.

This module wraps the in-memory registry façade from
:mod:`compatibility.registry_view` so that an installer can persist an
environment change without touching the host machine's real registry.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/sysinfo/registry-value-types
* https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-settingchange
* https://learn.microsoft.com/en-us/windows/win32/shell/environment-variables

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .registry_hive import RegType
from .registry_view import HKCU, HKLM, InMemoryRegistry, RegistryView

log = logging.getLogger("UmerOS.Compat.EnvRegistry")

#: The registry key holding the **user** environment variables.
USER_ENV_KEY = r"HKCU\Environment"

#: The registry key holding the **system** (machine) environment
#: variables.  This is the same key the Control Panel dialog writes to.
SYSTEM_ENV_KEY = (r"HKLM\SYSTEM\CurrentControlSet\Control"
                  r"\Session Manager\Environment")

#: Map a scope name to its registry key.  The keys are spelled the way
#: they appear in ``regedit`` so error messages match what an admin sees.
SCOPE_KEYS: Dict[str, str] = {
    "user": USER_ENV_KEY,
    "system": SYSTEM_ENV_KEY,
}

#: Variables that Windows stores as ``REG_EXPAND_SZ`` even though they
#: do not usually contain a reference.  ``Path`` is the important one:
#: installers routinely add ``%ProgramFiles%\\MyApp\\bin`` to it.
EXPANDABLE_BY_DEFAULT: Tuple[str, ...] = ("Path",)


@dataclass
class EnvEntry:
    """One environment variable as it exists in the registry.

    Attributes
    ----------
    name:
        The variable name, with its original spelling.
    value:
        The value as it would appear in a live environment block.
    raw:
        The value *as stored* -- for a ``REG_EXPAND_SZ`` entry this still
        contains the ``%VAR%`` references.
    expand:
        ``True`` when the registry type is ``REG_EXPAND_SZ``.
    """

    name: str
    value: str
    raw: str = ""
    expand: bool = False

    @property
    def type_name(self) -> str:
        """``REG_SZ`` or ``REG_EXPAND_SZ``."""
        return "REG_EXPAND_SZ" if self.expand else "REG_SZ"

    def to_registry_bytes(self) -> bytes:
        """Encode as the registry stores it (UTF-16LE + NUL terminator)."""
        text = self.raw if self.expand else self.value
        return text.encode("utf-16-le") + b"\x00\x00"


def _encode(value: str) -> bytes:
    """Encode a string the way the registry stores it."""
    return value.encode("utf-16-le") + b"\x00\x00"


class EnvRegistryStore:
    """Read and write the two persistent environment scopes.

    Example
    -------
    >>> reg = EnvRegistryStore()
    >>> reg.set("user", "MYAPP", r"C:\\Program Files\\MyApp")
    True
    >>> reg.get("user", "MYAPP").value
    'C:\\\\Program Files\\\\MyApp'
    >>> reg.unset("user", "MYAPP")
    True
    """

    def __init__(self, registry: Optional[object] = None) -> None:
        #: Either an :class:`~compatibility.registry_view.InMemoryRegistry`
        #: or a :class:`~compatibility.registry_view.RegistryView`.
        self.registry = registry if registry is not None else InMemoryRegistry()

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    @staticmethod
    def key_for(scope: str) -> str:
        """The registry key backing ``scope`` (``user`` / ``system``)."""
        try:
            return SCOPE_KEYS[scope.lower()]
        except KeyError as exc:
            raise KeyError(
                f"unknown environment scope: {scope!r} "
                f"(expected one of {sorted(SCOPE_KEYS)})") from exc

    def _enum(self, path: str) -> List:
        return list(self.registry.enum_values(path))

    def _get(self, path: str, name: str):
        return self.registry.get_value(path, name)

    def _set(self, path: str, name: str, data: bytes, type_: int):
        return self.registry.set_value(path, name, data, type_)

    def _delete(self, path: str, name: str) -> bool:
        return bool(self.registry.delete_value(path, name))

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def read(self, scope: str) -> Dict[str, EnvEntry]:
        """Every variable stored in ``scope``, keyed by upper-case name."""
        path = self.key_for(scope)
        out: Dict[str, EnvEntry] = {}
        try:
            values = self._enum(path)
        except Exception as exc:    # noqa: BLE001 -- best effort
            log.debug("cannot enumerate %s: %s", path, exc)
            return out
        for value in values:
            try:
                raw = value.as_string()
            except (ValueError, UnicodeDecodeError):
                # REG_DWORD / REG_BINARY are not environment variables.
                continue
            expand = value.type == RegType.EXPAND_SZ
            out[value.name.upper()] = EnvEntry(
                name=value.name, value=raw, raw=raw, expand=expand)
        return out

    def get(self, scope: str, name: str) -> Optional[EnvEntry]:
        """One variable from ``scope``, or ``None``."""
        path = self.key_for(scope)
        value = self._get(path, name)
        if value is None:
            return None
        try:
            raw = value.as_string()
        except (ValueError, UnicodeDecodeError):
            return None
        return EnvEntry(
            name=name,
            value=raw,
            raw=raw,
            expand=value.type == RegType.EXPAND_SZ,
        )

    def read_expanded(self, scope: str,
                      block=None) -> Dict[str, str]:
        """Read ``scope`` with ``REG_EXPAND_SZ`` references expanded.

        ``block`` is the environment block used to resolve ``%VAR%``
        references; it defaults to the process default block.
        """
        from .environment import ExpandEnvironmentStringsA   # local: avoid cycle
        out: Dict[str, str] = {}
        for key, entry in self.read(scope).items():
            if entry.expand:
                out[key] = ExpandEnvironmentStringsA(entry.raw, block)
            else:
                out[key] = entry.value
        return out

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def set(self, scope: str, name: str, value: str,
            *, expand: Optional[bool] = None) -> bool:
        """Define ``name`` in ``scope``.

        ``expand`` forces the registry type.  When it is ``None`` the
        type is chosen the way Windows chooses it: ``REG_EXPAND_SZ`` for
        the names in :data:`EXPANDABLE_BY_DEFAULT` (and for any value
        that already contains a ``%VAR%`` reference), ``REG_SZ``
        otherwise.

        Returns ``True`` when the stored value changed.
        """
        path = self.key_for(scope)
        if expand is None:
            expand = (name.lower() in {n.lower() for n in EXPANDABLE_BY_DEFAULT}
                      or "%" in value)
        type_ = RegType.EXPAND_SZ if expand else RegType.SZ
        stored = value if expand else value
        existing = self._get(path, name)
        if existing is not None:
            try:
                if (existing.as_string() == stored
                        and existing.type == type_):
                    return False
            except (ValueError, UnicodeDecodeError):
                pass
        self._set(path, name, _encode(stored), type_)
        return True

    def unset(self, scope: str, name: str) -> bool:
        """Remove ``name`` from ``scope``.  Returns ``True`` on success."""
        path = self.key_for(scope)
        return self._delete(path, name)

    def write(self, scope: str, entries: Dict[str, str],
              *, expand: Optional[bool] = None) -> None:
        """Replace the whole contents of ``scope`` with ``entries``."""
        path = self.key_for(scope)
        wanted = {k.upper(): v for k, v in entries.items()}
        for key, entry in list(self.read(scope).items()):
            if key not in wanted:
                self._delete(path, entry.name)
        for name, value in entries.items():
            self.set(scope, name, value, expand=expand)

    def clear(self, scope: str) -> None:
        """Remove every variable from ``scope``."""
        path = self.key_for(scope)
        for entry in list(self.read(scope).values()):
            self._delete(path, entry.name)


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    store = EnvRegistryStore()

    # 1. Writing and reading back.
    if not store.set("user", "MYAPP", r"C:\Program Files\MyApp"):
        return False
    entry = store.get("user", "MYAPP")
    if entry is None or entry.value != r"C:\Program Files\MyApp":
        return False
    if entry.expand:
        return False          # plain string -> REG_SZ

    # 2. Path is stored as REG_EXPAND_SZ so %VAR% survives.
    store.set("system", "Path", r"%SystemRoot%\system32;C:\Tools")
    path = store.get("system", "Path")
    if path is None or not path.expand:
        return False
    if path.raw != r"%SystemRoot%\system32;C:\Tools":
        return False

    # 3. REG_EXPAND_SZ values expand on read.
    from .environment import EnvironmentBlock
    blk = EnvironmentBlock()
    blk["SystemRoot"] = r"C:\Windows"
    expanded = store.read_expanded("system", blk)
    if expanded.get("PATH") != r"C:\Windows\system32;C:\Tools":
        log.debug("expanded PATH = %r", expanded.get("PATH"))
        return False

    # 4. The two scopes are independent.
    if store.get("system", "MYAPP") is not None:
        return False

    # 5. Unsetting.
    if not store.unset("user", "MYAPP"):
        return False
    if store.get("user", "MYAPP") is not None:
        return False
    if store.unset("user", "MYAPP"):
        return False

    # 6. A value containing a reference is stored expandable.
    store.set("user", "REFPATH", r"%ProgramFiles%\App")
    if not store.get("user", "REFPATH").expand:
        return False

    # 7. Writing a whole scope replaces its contents.
    store.set("user", "OLD", "1")
    store.write("user", {"NEW": "2"})
    names = {k for k in store.read("user")}
    if "OLD" in names or "NEW" not in names:
        return False

    # 8. Unknown scopes are rejected.
    try:
        store.key_for("nonsense")
    except KeyError:
        pass
    else:
        return False

    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
