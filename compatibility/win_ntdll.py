"""
Umer OS /compatibility/win_ntdll — ntdll.dll API stubs
===================================================

``ntdll.dll`` exposes the Windows *Native API* -- the user-mode
boundary of the NT executive.  Most of the higher-layer Win32
functions in ``kernel32`` / ``advapi32`` end up calling into
ntdll under the hood.

The native API uses a different calling convention (mostly
``stdcall`` on x86, ``x64 fastcall`` on x64) and uses the
``NTSTATUS`` return type rather than the Win32 ``HRESULT`` /
``GetLastError`` pair.

This module provides a focused stub subset.  Anything we don't
implement is left to fail with ``STATUS_NOT_IMPLEMENTED`` so the
loader can carry on.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/
* https://github.com/repnz/ntapi-doc

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger("UmerOS.Compat.Ntdll")

from .ntstatus import (
    STATUS_SUCCESS,
    STATUS_NOT_IMPLEMENTED,
    STATUS_INVALID_HANDLE,
    STATUS_INVALID_PARAMETER,
    STATUS_OBJECT_NAME_NOT_FOUND,
)


# ---------------------------------------------------------------------------
# Object Manager
# ---------------------------------------------------------------------------

def NtCreateFile(handle_out, access, attrs, io_status_block,
                 allocation_size, file_attrs, share, disposition,
                 options, ea_buffer, ea_length) -> int:
    """Stub: simulate a successful file create."""
    handle_out[0] = 0x100
    return STATUS_SUCCESS


def NtOpenFile(handle_out, access, attrs, io_status_block,
               share, options) -> int:
    handle_out[0] = 0x101
    return STATUS_SUCCESS


def NtReadFile(handle, evt, apc_routine, apc_ctx, io_status_block,
              buf, length, offset_low, offset_high, key) -> int:
    """Stub: pretend to read 0 bytes successfully."""
    return STATUS_SUCCESS


def NtWriteFile(handle, evt, apc_routine, apc_ctx, io_status_block,
               buf, length, offset_low, offset_high, key) -> int:
    return STATUS_SUCCESS


def NtClose(handle) -> int:
    return STATUS_SUCCESS


def NtQueryInformationFile(handle, info_class, buf, length,
                          returned_length) -> int:
    return STATUS_SUCCESS


def NtSetInformationFile(handle, info_class, buf, length) -> int:
    return STATUS_SUCCESS


# ---------------------------------------------------------------------------
# Process / Thread
# ---------------------------------------------------------------------------

def NtCreateProcess(handle_out, access, obj_attrs, parent_handle,
                    inherit, section_handle, debug_port, exception_port,
                    flags) -> int:
    return STATUS_NOT_IMPLEMENTED


def NtTerminateProcess(handle, status) -> int:
    return STATUS_SUCCESS


def NtCreateThread(handle_out, access, obj_attrs, process_handle,
                  client_id, thread_ctx, start_ctx, suspended) -> int:
    return STATUS_NOT_IMPLEMENTED


def NtTerminateThread(handle, status) -> int:
    return STATUS_SUCCESS


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

def NtAllocateVirtualMemory(process, base_ptr, zero_bits, size_ptr,
                             allocation_type, protect) -> int:
    """Stub: pretend to allocate memory."""
    return STATUS_SUCCESS


def NtFreeVirtualMemory(process, base_ptr, size_ptr, free_type) -> int:
    return STATUS_SUCCESS


def NtProtectVirtualMemory(process, base_ptr, size_ptr, new_protect,
                            old_protect_out) -> int:
    return STATUS_SUCCESS


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

def LdrLoadDll(search_path, flags, module_file_name, module_handle) -> int:
    """Stub: signal success but don't actually load anything."""
    module_handle[0] = 0x200
    return STATUS_SUCCESS


def LdrGetProcedureAddress(module, function_name, ordinal, flags) -> int:
    return STATUS_NOT_IMPLEMENTED


def LdrGetDllHandle(search_path, flags, module_file_name, handle_out) -> int:
    handle_out[0] = 0x201
    return STATUS_SUCCESS


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

EXPORTS: Dict[str, Any] = {
    "NtCreateFile": NtCreateFile,
    "NtOpenFile": NtOpenFile,
    "NtReadFile": NtReadFile,
    "NtWriteFile": NtWriteFile,
    "NtClose": NtClose,
    "NtQueryInformationFile": NtQueryInformationFile,
    "NtSetInformationFile": NtSetInformationFile,
    "NtCreateProcess": NtCreateProcess,
    "NtTerminateProcess": NtTerminateProcess,
    "NtCreateThread": NtCreateThread,
    "NtTerminateThread": NtTerminateThread,
    "NtAllocateVirtualMemory": NtAllocateVirtualMemory,
    "NtFreeVirtualMemory": NtFreeVirtualMemory,
    "NtProtectVirtualMemory": NtProtectVirtualMemory,
    "LdrLoadDll": LdrLoadDll,
    "LdrGetProcedureAddress": LdrGetProcedureAddress,
    "LdrGetDllHandle": LdrGetDllHandle,
}


def _selftest() -> bool:
    h = [0]
    rc = NtCreateFile(h, 0, None, None, None, 0, 0, 0, 0, None, 0)
    if rc != STATUS_SUCCESS or h[0] == 0:
        return False
    if NtClose(h[0]) != STATUS_SUCCESS:
        return False
    if NtCreateProcess(None, 0, None, 0, 0, 0, 0, 0, 0) != STATUS_NOT_IMPLEMENTED:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
