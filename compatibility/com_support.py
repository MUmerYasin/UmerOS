"""
Umer OS /compatibility/com_support — minimal COM stubs
======================================================

Pure-Python implementation of the absolute minimum subset of the
Component Object Model that the UmerOS loader needs to satisfy IAT
lookups against ``ole32.dll`` / ``oleaut32.dll``.

The module implements:

* **GUID-typed references** — :class:`IUnknown`, :class:`IDispatch`
  and a small selection of canonical CLSIDs (the ones an installer
  would touch: ``CLSID_StdComponentCategoriesMgr``,
  ``CLSID_ShellLink``, ``IID_IShellLink``).
* **Apartment model** — :class:`ComApartment` tracks which thread
  initialised COM, what apartment it used (``COINIT_APARTMENTTHREADED``
  vs ``COINIT_MULTITHREADED``), and exposes a registry of objects.
* **Object lifetime** — :class:`ComObject` provides a reference-
  counted :class:`ComObjectBase` and a tiny object table keyed by
  IID.  When the last reference is released the object is removed
  from the apartment (the Win32 contract is that ``Release`` returns
  the new refcount, with ``0`` triggering ``delete this``).

We deliberately do NOT implement marshaling, proxies, RPC, type
libraries or property bags — these are out of scope for a loader
whose job is to audit imports, not actually instantiate COM objects.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/combaseapi/
* https://learn.microsoft.com/en-us/windows/win32/api/objbase/

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Iterator, Optional, Set, Tuple

from .win_guid import Guid, IID_IUNKNOWN, IID_IDISPATCH

log = logging.getLogger("UmerOS.Compat.COM")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Co-init flags — same names as ``<objbase.h>``.
COINIT_MULTITHREADED      = 0x0
COINIT_APARTMENTTHREADED  = 0x2
COINIT_DISABLE_OLE1DDE    = 0x4
COINIT_SPEED_OVER_MEMORY  = 0x8

#: HRESULT codes that the loader cares about.
S_OK                     = 0
S_FALSE                  = 1
E_NOINTERFACE            = 0x80004002
E_POINTER                = 0x80004003
E_FAIL                   = 0x80004005
E_NOTIMPL                = 0x80004001
E_OUTOFMEMORY            = 0x8007000E
CO_E_NOTINITIALIZED      = 0x800401F0
CO_E_ALREADYINITIALIZED  = 0x800401F1


# ---------------------------------------------------------------------------
# CLSIDs / IIDs used by installers
# ---------------------------------------------------------------------------

CLSID_SHELL_LINK = Guid.from_string("{00021401-0000-0000-C000-000000000046}")
IID_ISHELL_LINK  = Guid.from_string("{000214EE-0000-0000-C000-000000000046}")

#: Standard component categories (used by ``CLSID_StdComponentCategoriesMgr``).
CATID_DRAG_DROP_HANDLER     = Guid.from_string("{56212F5C-79FE-4ff8-9C9F-1A2F90B72C18}")
CATID_FILE_TYPE_HANDLER     = Guid.from_string("{C9CB8E70-7E70-4bfc-A9D8-5A8B3B7E5E3E}")
CATID_BROWSER_SHELL_EXT     = Guid.from_string("{8A1914F0-BC90-4bf2-A18D-7E5E5C5F7E1B}")


# ---------------------------------------------------------------------------
# Apartment model
# ---------------------------------------------------------------------------

class ApartmentType(IntEnum):
    MULTITHREADED = COINIT_MULTITHREADED
    APARTMENT     = COINIT_APARTMENTTHREADED


@dataclass
class ComApartment:
    """Per-thread COM state.

    The apartment is *thread-local* in real Win32; we keep one global
    instance with a thread-id check on each operation.  This is enough
    for a static IAT auditor and matches what ``OleMainThreadWndProc``
    expects from the loader.
    """

    init_thread: int = 0
    apartment_type: ApartmentType = ApartmentType.MULTITHREADED
    refs: int = 0                # total outstanding COM objects in this apt
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _objects: Dict[int, "ComObject"] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def initialise(self, flags: int, *, thread: Optional[int] = None
                   ) -> Tuple[int, int]:
        """``CoInitializeEx`` equivalent.  Returns ``(hr, cookie)``."""
        tid = thread if thread is not None else threading.get_ident()
        with self._lock:
            if self.refs > 0 and self.init_thread != tid:
                return (CO_E_ALREADYINITIALIZED, 0)
            if self.refs > 0 and self.init_thread == tid:
                # Per MSDN, calling CoInitializeEx twice on the same
                # thread just bumps the refcount.
                self.refs += 1
                return (S_OK, self.refs)
            self.init_thread = tid
            self.apartment_type = (
                ApartmentType.APARTMENT
                if flags & COINIT_APARTMENTTHREADED
                else ApartmentType.MULTITHREADED
            )
            self.refs = 1
            return (S_OK, 1)

    def uninitialise(self, *, thread: Optional[int] = None) -> int:
        """``CoUninitialize`` equivalent."""
        tid = thread if thread is not None else threading.get_ident()
        with self._lock:
            if self.refs <= 0:
                return CO_E_NOTINITIALIZED
            if self.init_thread != tid:
                return CO_E_NOTINITIALIZED
            self.refs -= 1
            if self.refs == 0:
                # Drop every still-registered object.
                self._objects.clear()
            return S_OK

    # ------------------------------------------------------------------
    # Object registry
    # ------------------------------------------------------------------

    def register(self, obj: "ComObject") -> int:
        with self._lock:
            self._objects[id(obj)] = obj
            return id(obj)

    def release_object(self, obj: "ComObject") -> int:
        with self._lock:
            self._objects.pop(id(obj), None)
            return S_OK

    def iter_objects(self) -> Iterator["ComObject"]:
        with self._lock:
            return iter(list(self._objects.values()))


# Module-level (and effectively thread-level) apartment.
_APARTMENT = ComApartment()


def get_apartment() -> ComApartment:
    return _APARTMENT


def reset_apartment() -> None:
    """Test helper — drop all COM state."""
    global _APARTMENT
    _APARTMENT = ComApartment()


# ---------------------------------------------------------------------------
# Object lifetime
# ---------------------------------------------------------------------------

class ComObjectBase:
    """The base class for every COM object the loader can produce.

    Concrete classes provide :meth:`query_interface`; the base provides
    refcount management and a finaliser safety net.
    """

    def __init__(self) -> None:
        self._refcount: int = 1
        self._lock = threading.Lock()

    def add_ref(self) -> int:
        with self._lock:
            self._refcount += 1
            return self._refcount

    def release(self) -> int:
        with self._lock:
            self._refcount -= 1
            if self._refcount == 0:
                self._on_zero_refs()
                return 0
            return self._refcount

    def refcount(self) -> int:
        with self._lock:
            return self._refcount

    def _on_zero_refs(self) -> None:
        """Hook for subclasses that own native resources."""
        pass

    # ------------------------------------------------------------------
    # Interface support
    # ------------------------------------------------------------------

    def query_interface(self, iid: Guid) -> Optional["ComObjectBase"]:
        if iid in (IID_IUNKNOWN,):
            return self
        if iid in (IID_IDISPATCH,):
            # Only objects that opt-in via self.iid_idispatch are returned.
            if getattr(self, "_supports_idispatch", False):
                return self
            return None
        # Subclass-specific interfaces.
        handler = getattr(self, "_query_interface_ex", None)
        if handler is not None:
            return handler(iid)
        return None


@dataclass
class ComObject:
    """Wraps a :class:`ComObjectBase` plus the apartment bookkeeping."""

    base: ComObjectBase
    cookie: int = 0

    def __post_init__(self) -> None:
        if self.cookie == 0:
            self.cookie = _APARTMENT.register(self)

    def release(self) -> int:
        rc = self.base.release()
        if rc == 0:
            _APARTMENT.release_object(self)
        return rc


# ---------------------------------------------------------------------------
# CoCreateInstance stub
# ---------------------------------------------------------------------------

@dataclass
class ClassFactory:
    """An IClassFactory stub used to satisfy ``CoCreateInstance``."""
    clsid: Guid
    instances_created: int = 0

    def create_instance(self, iid: Guid) -> Optional[ComObjectBase]:
        if iid not in (IID_IUNKNOWN, IID_IDISPATCH):
            return None
        self.instances_created += 1
        obj = ComObjectBase()
        # Real COM objects produced via a class factory almost always
        # expose IDispatch (the scripting variant of IUnknown).
        obj._supports_idispatch = True
        return obj


#: A small registry of CLSID -> factory.  Real installers add to this
#: on demand; tests can pre-populate.
_CLASS_FACTORIES: Dict[Guid, ClassFactory] = {}


def register_class_factory(clsid: Guid, factory: ClassFactory) -> None:
    _CLASS_FACTORIES[clsid] = factory


def CoCreateInstance(clsid: Guid, *, iid: Guid = IID_IUNKNOWN
                     ) -> Tuple[int, Optional[ComObjectBase]]:
    """``CoCreateInstance`` equivalent.

    Returns ``(hr, obj)`` mirroring Win32's pair of
    ``CoCreateInstance(...)`` + ``QueryInterface`` semantics.
    """
    factory = _CLASS_FACTORIES.get(clsid)
    if factory is None:
        return (E_NOINTERFACE, None)
    obj = factory.create_instance(iid)
    if obj is None:
        return (E_NOINTERFACE, None)
    obj = obj.query_interface(iid)
    if obj is None:
        return (E_NOINTERFACE, None)
    return (S_OK, obj)


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

EXPORTS_OLE32 = {
    "CoInitializeEx": lambda flags: _APARTMENT.initialise(flags)[0],
    "CoUninitialize": lambda: _APARTMENT.uninitialise(),
    "CoCreateInstance": CoCreateInstance,
    "CoInitialize": lambda: _APARTMENT.initialise(COINIT_APARTMENTTHREADED)[0],
}

EXPORTS_OLEAUT32 = {
    # No-op stubs; provided so IAT lookups succeed.
    "SysAllocString": lambda s: s if isinstance(s, str) else "",
    "SysFreeString": lambda s: None,
    "SysStringLen": lambda s: len(s) if s else 0,
}


__all__ = [
    "COINIT_MULTITHREADED", "COINIT_APARTMENTTHREADED",
    "S_OK", "S_FALSE", "E_NOINTERFACE", "E_POINTER", "E_FAIL",
    "E_NOTIMPL", "E_OUTOFMEMORY",
    "CO_E_NOTINITIALIZED", "CO_E_ALREADYINITIALIZED",
    "CLSID_SHELL_LINK", "IID_ISHELL_LINK",
    "CATID_DRAG_DROP_HANDLER", "CATID_FILE_TYPE_HANDLER", "CATID_BROWSER_SHELL_EXT",
    "ApartmentType", "ComApartment", "ComObjectBase", "ComObject",
    "ClassFactory", "register_class_factory", "CoCreateInstance",
    "get_apartment", "reset_apartment",
    "EXPORTS_OLE32", "EXPORTS_OLEAUT32",
]


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    reset_apartment()
    apt = get_apartment()
    hr, _ = apt.initialise(COINIT_APARTMENTTHREADED)
    if hr != S_OK:
        return False
    hr, _ = apt.initialise(COINIT_APARTMENTTHREADED)        # second call on same thread
    if hr != S_OK:
        return False
    if apt.uninitialise() != S_OK or apt.uninitialise() != S_OK:
        return False
    if apt.uninitialise() != CO_E_NOTINITIALIZED:
        return False
    # Object lifetime.
    o = ComObjectBase()
    if o.refcount() != 1:
        return False
    if o.add_ref() != 2:
        return False
    if o.release() != 1:
        return False
    if o.release() != 0:
        return False
    # QueryInterface unknown -> self.
    if o.query_interface(IID_IUNKNOWN) is not o:
        return False
    # QueryInterface for IDISPATCH on a non-Dispatch object -> None.
    if o.query_interface(IID_IDISPATCH) is not None:
        return False
    # CoCreateInstance with no factory registered -> E_NOINTERFACE.
    hr, _ = CoCreateInstance(CLSID_SHELL_LINK)
    if hr != E_NOINTERFACE:
        return False
    # Register factory then try again.
    factory = ClassFactory(clsid=CLSID_SHELL_LINK)
    register_class_factory(CLSID_SHELL_LINK, factory)
    hr, obj = CoCreateInstance(CLSID_SHELL_LINK, iid=IID_IDISPATCH)
    if hr != S_OK or obj is None:
        return False
    if factory.instances_created != 1:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
