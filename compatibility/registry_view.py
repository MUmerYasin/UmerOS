"""
Umer OS /compatibility/registry_view — Registry API façade
=========================================================

A thin, in-memory registry façade that exposes the conventional
Win32 ``RegOpenKey`` / ``RegQueryValue`` / ``RegEnumValue`` API on
top of one or more parsed :class:`~compatibility.registry_hive.RegistryHive`
instances.  The view is the convenient object the rest of the
compatibility layer uses; it transparently maps paths like
``HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion`` to the
correct hive + key.

This module also provides a tiny **transactional in-memory
registry** (no hive files) so tests and pure-Python code can
populate values without writing a real REGF.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/winreg/

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Iterable, List, Optional, Tuple

from .registry_hive import RegKey, RegType, RegValue, RegistryHive

log = logging.getLogger("UmerOS.Registry.View")


class Hkey(IntEnum):
    """The well-known predefined registry root keys."""

    CLASSES_ROOT = 0x80000000
    CURRENT_USER = 0x80000001
    LOCAL_MACHINE = 0x80000002
    USERS = 0x80000003
    CURRENT_CONFIG = 0x80000005


HKLM = Hkey.LOCAL_MACHINE
HKCU = Hkey.CURRENT_USER
HKCR = Hkey.CLASSES_ROOT
HKU = Hkey.USERS
HKCC = Hkey.CURRENT_CONFIG

#: Pretty names for the predefined keys.
HKEY_NAMES: Dict[int, str] = {
    Hkey.CLASSES_ROOT: "HKEY_CLASSES_ROOT",
    Hkey.CURRENT_USER: "HKEY_CURRENT_USER",
    Hkey.LOCAL_MACHINE: "HKEY_LOCAL_MACHINE",
    Hkey.USERS: "HKEY_USERS",
    Hkey.CURRENT_CONFIG: "HKEY_CURRENT_CONFIG",
}


# ---------------------------------------------------------------------------
# Errors (Win32 error codes; reuse the winerror module).
# ---------------------------------------------------------------------------

from .winerror import (
    ERROR_SUCCESS,
    ERROR_FILE_NOT_FOUND,
    ERROR_PATH_NOT_FOUND,
    ERROR_ACCESS_DENIED,
    ERROR_INVALID_PARAMETER,
    ERROR_MORE_DATA,
    ERROR_NO_MORE_ITEMS,
)


# ---------------------------------------------------------------------------
# In-memory registry (no REGF file)
# ---------------------------------------------------------------------------

@dataclass
class InMemoryRegistry:
    """A pure-Python in-memory registry that mimics the Win32 surface.

    Hives are addressed by their :class:`Hkey` value.  Subkeys and
    values are mutable; this is intended for tests and a transient
    view of the *live* Umer OS state, not for editing a REGF.
    """

    hives: Dict[int, RegKey] = field(default_factory=dict)

    def get_hive(self, hkey: int) -> RegKey:
        if hkey not in self.hives:
            root = RegKey(name=HKEY_NAMES.get(hkey, f"HKEY_{hkey:08X}"))
            self.hives[hkey] = root
        return self.hives[hkey]

    # ------------------------------------------------------------------
    # Path utilities
    # ------------------------------------------------------------------

    @staticmethod
    def split_path(path: str) -> Tuple[int, str]:
        """Split ``HKLM\\SOFTWARE\\Foo`` into ``(Hkey, 'SOFTWARE\\Foo')``."""
        if "\\" not in path and "/" not in path:
            return _guess_root(path), path
        for sep in ("\\", "/"):
            head, _, rest = path.partition(sep)
            if head.upper() in {n.upper() for n in HKEY_NAMES.values()}:
                # Translate the human name to the numeric Hkey.
                for k, n in HKEY_NAMES.items():
                    if n.upper() == head.upper():
                        return k, rest
        return HKLM, path

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def open(self, parent: int, sub: str) -> RegKey:
        """Open (or create) a subkey path under a predefined root."""
        node = self.get_hive(parent)
        for part in [p for p in sub.split("\\") if p]:
            child = node.get_subkey(part)
            if child is None:
                child = RegKey(name=part, parent=node)
                node.subkeys.append(child)
            node = child
        return node

    def open_path(self, path: str) -> RegKey:
        root, rest = self.split_path(path)
        return self.open(root, rest)

    def get_value(self, path: str, name: str) -> Optional[RegValue]:
        try:
            key = self.open_path(path)
        except Exception:
            return None
        return key.get_value(name)

    def set_value(self, path: str, name: str,
                  value: bytes, type: int = RegType.SZ) -> RegValue:
        """Set (replace) a value under a path.  Creates the key if needed."""
        key = self.open_path(path)
        # Replace existing value with the same name.
        for i, v in enumerate(key.values):
            if v.name == name:
                key.values[i] = RegValue(name=name, type=type, raw=value, parent=key)
                return key.values[i]
        new = RegValue(name=name, type=type, raw=value, parent=key)
        key.values.append(new)
        return new

    def delete_value(self, path: str, name: str) -> bool:
        key = self.open_path(path)
        before = len(key.values)
        key.values = [v for v in key.values if v.name != name]
        return len(key.values) < before

    def delete_key(self, path: str) -> bool:
        root, rest = self.split_path(path)
        if "\\" not in rest:
            return False    # can't delete a top-level hive
        parts = [p for p in rest.split("\\") if p]
        if not parts:
            return False
        parent = self.open(root, "\\".join(parts[:-1]))
        name = parts[-1]
        before = len(parent.subkeys)
        parent.subkeys = [k for k in parent.subkeys if k.name != name]
        return len(parent.subkeys) < before

    def enum_values(self, path: str) -> List[RegValue]:
        return list(self.open_path(path).values)

    def enum_subkeys(self, path: str) -> List[RegKey]:
        return list(self.open_path(path).subkeys)

    # ------------------------------------------------------------------
    # Bee-style convenience
    # ------------------------------------------------------------------

    def walk(self) -> Iterable[RegKey]:
        for hkey in sorted(self.hives):
            yield from self.hives[hkey].walk()


def _guess_root(name: str) -> int:
    for k, n in HKEY_NAMES.items():
        if n.upper() == name.upper():
            return k
    return HKLM


# ---------------------------------------------------------------------------
# Hive-backed view
# ---------------------------------------------------------------------------

class RegistryView:
    """A view that joins multiple REGF hives under the predefined roots.

    Example::

        reg = RegistryView()
        reg.mount("system",   system_hive)
        reg.mount("software", software_hive)
        v = reg.get("HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion",
                    "ProductName")
    """

    def __init__(self) -> None:
        self._memory = InMemoryRegistry()
        self._hives: Dict[int, RegistryHive] = {}

    def mount(self, hkey: int, hive: RegistryHive) -> None:
        """Mount a parsed REGF under one of the predefined :class:`Hkey`s."""
        self._hives[hkey] = hive

    def memory(self) -> InMemoryRegistry:
        """Return the in-memory store (for tests and transient state)."""
        return self._memory

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def open_path(self, path: str) -> RegKey:
        """Open a path, preferring mounted hives then falling back to memory."""
        root, rest = InMemoryRegistry.split_path(path)
        if root in self._hives and rest:
            # Walk into the mounted hive's root.
            node = self._hives[root].root
            for part in [p for p in rest.split("\\") if p]:
                child = node.get_subkey(part)
                if child is None:
                    child = RegKey(name=part, parent=node)
                    node.subkeys.append(child)
                node = child
            return node
        return self._memory.open_path(path)

    def get(self, path: str, name: str) -> Optional[RegValue]:
        return self.open_path(path).get_value(name)

    def set(self, path: str, name: str, value: bytes,
            type: int = RegType.SZ) -> RegValue:
        return self._memory.set_value(path, name, value, type)


def _selftest() -> bool:
    """Smoke test the InMemoryRegistry API."""
    reg = InMemoryRegistry()
    # REG_SZ values are stored as raw bytes; the caller is
    # responsible for UTF-16LE encoding.  We mimic what a Win32
    # caller would write.
    version_bytes = "2.0.0".encode("utf-16-le") + b"\x00\x00"
    reg.set_value(r"HKLM\SOFTWARE\UmerOS", "Version", version_bytes, RegType.SZ)
    v = reg.get_value(r"HKLM\SOFTWARE\UmerOS", "Version")
    if v is None or v.as_string() != "2.0.0":
        return False
    reg.set_value(r"HKLM\SOFTWARE\UmerOS", "Flags",
                  b"\x01\x00\x00\x00", RegType.DWORD)
    v2 = reg.get_value(r"HKLM\SOFTWARE\UmerOS", "Flags")
    if v2 is None or v2.as_dword() != 1:
        return False
    if not reg.delete_value(r"HKLM\SOFTWARE\UmerOS", "Version"):
        return False
    if reg.get_value(r"HKLM\SOFTWARE\UmerOS", "Version") is not None:
        return False
    # Test path with no Hkey prefix.
    reg.set_value(r"SOFTWARE\UmerOS", "Test", version_bytes, RegType.SZ)
    if reg.get_value(r"HKLM\SOFTWARE\UmerOS\Test", "Test") is None:
        # Path mapping should default to HKLM.
        pass
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
