# UmerOS /compatibility — Windows compatibility layer
# =====================================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``compatibility`` package implements a *pure-Python* Windows
# compatibility layer for UmerOS.
# PE binaries from Windows NT4 through Windows 11, decode the
# registry, stub the most common Win32 / NT APIs, and load PE images
# into a sandboxed UmerOS process.
#
# Highlights
# ----------
# * MZ / NE / PE32 / PE32+ parsing (``mz_loader``, ``ne_loader``,
#   ``pe_loader``, ``pe_imports``, ``pe_exports``, ``pe_relocations``,
#   ``pe_tls``, ``pe_resources``).
# * In-memory and on-disk registry (``registry_hive``,
#   ``registry_view``, ``registry_paths``).
# * Win32 / NT API stubs (``win_kernel32``, ``win_user32``,
#   ``win_gdi32``, ``win_advapi32``, ``win_ntdll``).
# * SCM stubs (``service_manager``), environment block (``environment``),
#   COM apartment (``com_support``), file attributes (``file_attrs``).
# * A high-level PE loader (``dll_loader``, ``wine_shim``).
# * Foundation helpers: SID database, GUID, error codes, NTSTATUS,
#   Unicode strings, DOS->POSIX path mapping.
#
# Stop-gap containers (``container``, ``container_engine``,
# ``syscall_shim``) are still part of the package and power the
# Linux/Android side of the compatibility story.
"""
UmerOS /compatibility — Windows compatibility layer (pure Python).

Every module
ships with a ``_selftest()`` that exercises the most important
behaviours; ``compatibility.selftest()`` runs them all.
"""

from __future__ import annotations

import logging
import pkgutil
from typing import List

__version__ = "1.1.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Compat")


# ---------------------------------------------------------------------------
# Import each module and surface the canonical public names.
# ---------------------------------------------------------------------------

_IMPORT_PLAN = {
    # ---- Stop-gap containers (Linux/Android side) ----
    "container":            ("ZeroTrustContainer",),
    "container_engine":     ("ContainerEngine",),
    "syscall_shim":         ("SyscallShim",),

    # ---- PE format ----
    "mz_loader":            ("parse_mz_header", "MzHeader"),
    "ne_loader":            ("parse_ne_header", "NeHeader"),
    "pe_loader":            ("PeFile", "PeClass", "PeSection", "PeOptionalHeader",
                             "PeDataDirectory", "PeResourceDirectoryEntry",
                             "PeImport", "PeExport"),
    "pe_imports":           ("parse_imports",),
    "pe_exports":           ("parse_exports",),
    "pe_relocations":       ("parse_relocations",),
    "pe_tls":               ("parse_tls_directory",),
    "pe_resources":         ("parse_resources",),

    # ---- Registry ----
    "registry_hive":        ("RegType", "RegValue", "RegKey",
                             "RegistryHive", "parse_hive_file"),
    "registry_view":        ("InMemoryRegistry",),
    "registry_paths":       ("hive_posix_path", "hkey_for_hive", "compat_hives_dir"),

    # ---- Foundation helpers ----
    "winerror":             ("format_win32_error", "format_hresult",
                             "HRESULT_FROM_WIN32",
                             "ERROR_SUCCESS", "ERROR_FILE_NOT_FOUND",
                             "ERROR_ACCESS_DENIED", "ERROR_INVALID_HANDLE"),
    "ntstatus":             ("format_ntstatus", "ntstatus_to_win32",
                             "STATUS_SUCCESS", "STATUS_ACCESS_VIOLATION"),
    "win_guid":             ("Guid", "IID_IUNKNOWN", "IID_IDISPATCH"),
    "win_sid":              ("Sid", "SidDatabase", "DEFAULT_DB",
                             "SID_LOCAL_SYSTEM", "SID_EVERYONE",
                             "SID_ADMINISTRATORS", "SID_USERS"),
    "win_strings":          ("UnicodeString", "wide_str", "from_wide"),
    "win_path":             ("DosPathMapper",),

    # ---- Win32 / NT API stubs ----
    "win_kernel32":         ("CreateFileA", "ReadFile", "WriteFile", "CloseHandle",
                             "GetLastError", "SetLastError", "GetTickCount",
                             "EXPORTS", "EXPORTS as KERNEL32_EXPORTS"),
    "win_user32":           ("RegisterClassExA", "CreateWindowExA", "PostMessageA",
                             "GetMessageA", "EXPORTS"),
    "win_gdi32":            ("GetDC", "ReleaseDC", "CreatePen", "DeleteObject",
                             "EXPORTS"),
    "win_advapi32":         ("RegOpenKeyA", "RegCloseKey",
                             "EXPORTS"),
    "win_ntdll":            ("NtCreateFile", "NtClose",
                             "EXPORTS"),

    # ---- Higher-level helpers ----
    "service_manager":      ("OpenSCManagerA", "CreateServiceA", "StartServiceA",
                             "ControlService", "DeleteService", "EnumServicesStatusA",
                             "ServiceStartType", "ServiceType", "ServiceState",
                             "EXPORTS"),
    "environment":          ("EnvironmentBlock", "get_default_block",
                             "GetEnvironmentVariableA", "SetEnvironmentVariableA",
                             "ExpandEnvironmentStringsA", "GetEnvironmentStringsA"),
    "com_support":          ("ComApartment", "ComObjectBase", "CoCreateInstance",
                             "EXPORTS_OLE32", "EXPORTS_OLEAUT32"),
    "file_attrs":           ("GetFileAttributesA", "SetFileAttributesA",
                             "GetFileAttributesExA", "FileAttributes",
                             "FILE_ATTRIBUTE_READONLY", "FILE_ATTRIBUTE_HIDDEN",
                             "FILE_ATTRIBUTE_ARCHIVE", "FILE_ATTRIBUTE_DIRECTORY"),

    # ---- Modern loader plumbing ----
    "api_set":              ("ApiSetNamespace", "ApiSetEntry", "ApiSetValue",
                             "parse_apiset", "fallback_namespace",
                             "is_api_set_name"),
    "forwarded":            ("ResolvedForward", "ForwarderString",
                             "follow_forward", "make_pe_resolver",
                             "make_table_resolver"),
    "dll_search":           ("DllSearchPath", "SearchLocation", "find_dll",
                             "LOAD_LIBRARY_SEARCH_DEFAULT_DIRS",
                             "LOAD_LIBRARY_SEARCH_SYSTEM32",
                             "LOAD_LIBRARY_SEARCH_APPLICATION_DIR",
                             "LOAD_LIBRARY_SEARCH_USER_DIRS",
                             "LOAD_WITH_ALTERED_SEARCH_PATH"),
    "manifest":             ("ActivationManifest", "AssemblyIdentity",
                             "Dependency", "parse_manifest", "parse_manifest_file",
                             "find_manifest_in_resources",
                             "ISOLATIONAWARE_MANIFEST_RESOURCE_ID", "RT_MANIFEST"),
    "long_path":            ("LongPath", "LongPathPrefix", "parse_long_path",
                             "make_extended", "make_extended_unc",
                             "wrap_if_needed", "is_too_long_for_win32",
                             "MAX_WIN32_PATH", "MAX_WIN32_LONG_PATH"),

    # ---- Loader + shim ----
    "dll_loader":           ("DllLoader", "ResolvedImport", "HOST_LIBRARIES",
                             "resolve_imports", "get_search_hits"),
    "wine_shim":            ("WineShim", "LaunchResult"),
}


def _try_import(module_name: str, names: tuple[str, ...]) -> None:
    """Import ``module_name`` and bind ``names`` into this package."""
    global __all__
    try:
        mod = __import__(f"{__name__}.{module_name}", fromlist=names)
    except ImportError as exc:
        log.debug("skipped optional module %s: %s", module_name, exc)
        return
    for n in names:
        if n == "EXPORTS":
            # Surface both as ``<module>_EXPORTS`` for unambiguous access.
            target = f"{module_name.upper().rstrip('_')}_EXPORTS"
            globals()[target] = mod.EXPORTS
            __all__.append(target)
            continue
        if hasattr(mod, n):
            globals()[n] = getattr(mod, n)
            __all__.append(n)


for _mod, _names in _IMPORT_PLAN.items():
    _try_import(_mod, _names)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def selftest() -> bool:
    """Run every ``_selftest()`` exposed by sub-modules."""
    failures: List[str] = []
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        try:
            mod = __import__(f"{__name__}.{module_info.name}", fromlist=["_selftest"])
        except Exception as exc:    # noqa: BLE001
            failures.append(f"{module_info.name}: import failed ({exc})")
            continue
        if not hasattr(mod, "_selftest"):
            continue
        try:
            ok = mod._selftest()
        except Exception as exc:    # noqa: BLE001
            failures.append(f"{module_info.name}: {exc!r}")
            continue
        if not ok:
            failures.append(module_info.name)
    if failures:
        for f in failures:
            print(f"compatibility selftest FAIL: {f}", flush=True)
        return False
    return True


def info() -> dict:
    """Return a dict with the public API surface area for diagnostics."""
    return {
        "version": __version__,
        "public_names": sorted(__all__),
        "module_count": sum(1 for _ in pkgutil.iter_modules(__path__)
                            if not _.name.startswith("_")),
    }
