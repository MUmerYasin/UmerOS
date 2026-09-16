"""
Umer OS /compatibility/service_manager — Win32 SCM stubs
========================================================

Pure-Python implementation of the Win32 *Service Control Manager*
surface used by installers, MSI, ``sc.exe`` and most Windows server
applications.  We expose the common ``OpenSCManagerA``, ``CreateServiceA``,
``OpenServiceA``, ``StartServiceA``, ``ControlService``,
``QueryServiceStatus``, ``DeleteService``, ``EnumServicesStatusA`` and
``CloseServiceHandle`` family.

The implementation is *intentionally* conservative: services are kept
in an in-memory registry, no host process is ever spawned, and
:class:`ServiceStartType.SERVICE_DISABLED` services are correctly
rejected on start.  This is exactly what the loader's IAT auditor
needs to satisfy ``OpenSCManagerW`` style imports without ever
hitting a real SCM.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/winsvc/
* https://learn.microsoft.com/en-us/windows/win32/services/service-programming-guide

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.SCM")

# ---------------------------------------------------------------------------
# Access masks
# ---------------------------------------------------------------------------

SC_MANAGER_ALL_ACCESS            = 0x000F003F
SC_MANAGER_CONNECT               = 0x00000001
SC_MANAGER_CREATE_SERVICE        = 0x00000002
SC_MANAGER_ENUMERATE_SERVICE     = 0x00000004
SC_MANAGER_LOCK                  = 0x00000008
SC_MANAGER_QUERY_LOCK_STATUS     = 0x00000010
SC_MANAGER_MODIFY_BOOT_CONFIG    = 0x00000020

SERVICE_ALL_ACCESS               = 0x000F01FF
SERVICE_QUERY_CONFIG             = 0x00000001
SERVICE_CHANGE_CONFIG            = 0x00000002
SERVICE_QUERY_STATUS             = 0x00000004
SERVICE_ENUMERATE_DEPENDENTS     = 0x00000008
SERVICE_START                    = 0x00000010
SERVICE_STOP                     = 0x00000020
SERVICE_PAUSE_CONTINUE           = 0x00000040
SERVICE_INTERROGATE              = 0x00000080
SERVICE_USER_DEFINED_CONTROL     = 0x00000100

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ServiceStartType(IntEnum):
    SERVICE_BOOT_START   = 0
    SERVICE_SYSTEM_START = 1
    SERVICE_AUTO_START   = 2
    SERVICE_DEMAND_START = 3
    SERVICE_DISABLED     = 4


class ServiceType(IntEnum):
    SERVICE_KERNEL_DRIVER         = 0x00000001
    SERVICE_FILE_SYSTEM_DRIVER    = 0x00000002
    SERVICE_WIN32_OWN_PROCESS     = 0x00000010
    SERVICE_WIN32_SHARE_PROCESS   = 0x00000020
    SERVICE_INTERACTIVE_PROCESS   = 0x00000100
    SERVICE_TYPE_ALL              = 0x000001FF


class ServiceState(IntEnum):
    """Subset of ``SERVICE_STATUS::dwCurrentState``."""
    SERVICE_STOPPED          = 0x00000001
    SERVICE_START_PENDING    = 0x00000002
    SERVICE_STOP_PENDING     = 0x00000003
    SERVICE_RUNNING          = 0x00000004
    SERVICE_CONTINUE_PENDING = 0x00000005
    SERVICE_PAUSE_PENDING    = 0x00000006
    SERVICE_PAUSED           = 0x00000007


class ServiceAcceptedControls(IntEnum):
    SERVICE_ACCEPT_NONE                 = 0x00000000
    SERVICE_ACCEPT_STOP                 = 0x00000001
    SERVICE_ACCEPT_PAUSE_CONTINUE       = 0x00000002
    SERVICE_ACCEPT_SHUTDOWN             = 0x00000004
    SERVICE_ACCEPT_PARAMCHANGE          = 0x00000008
    SERVICE_ACCEPT_NETBINDCHANGE        = 0x00000010
    SERVICE_ACCEPT_HARDWAREPROFILECHANGE = 0x00000020
    SERVICE_ACCEPT_POWEREVENT           = 0x00000040
    SERVICE_ACCEPT_SESSIONCHANGE        = 0x00000080
    SERVICE_ACCEPT_PRESHUTDOWN          = 0x00000100
    SERVICE_ACCEPT_TIMECHANGE           = 0x00000200
    SERVICE_ACCEPT_TRIGGEREVENT         = 0x00000400


class ServiceErrorControl(IntEnum):
    SERVICE_ERROR_IGNORE   = 0x00000000
    SERVICE_ERROR_NORMAL   = 0x00000001
    SERVICE_ERROR_SEVERE   = 0x00000002
    SERVICE_ERROR_CRITICAL = 0x00000003


# ---------------------------------------------------------------------------
# Service record
# ---------------------------------------------------------------------------

@dataclass
class ServiceStatus:
    """Subset of ``SERVICE_STATUS`` returned by ``QueryServiceStatus``."""
    service_type: ServiceType
    current_state: ServiceState
    controls_accepted: ServiceAcceptedControls
    win32_exit_code: int = 0
    service_specific_exit_code: int = 0
    check_point: int = 0
    wait_hint: int = 0


@dataclass
class ServiceRecord:
    """The canonical in-memory representation of a service."""
    name: str
    display_name: str
    binary_path: str
    start_type: ServiceStartType = ServiceStartType.SERVICE_DEMAND_START
    service_type: ServiceType = ServiceType.SERVICE_WIN32_OWN_PROCESS
    error_control: ServiceErrorControl = ServiceErrorControl.SERVICE_ERROR_NORMAL
    load_order_group: str = ""
    tag_id: int = 0
    dependencies: Tuple[str, ...] = ()
    account: str = "LocalSystem"
    password: str = ""
    status: ServiceStatus = field(default=None)    # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.status is None:
            self.status = ServiceStatus(
                service_type=self.service_type,
                current_state=ServiceState.SERVICE_STOPPED,
                controls_accepted=ServiceAcceptedControls.SERVICE_ACCEPT_STOP,
            )

    def is_runnable(self) -> bool:
        return self.start_type != ServiceStartType.SERVICE_DISABLED


# ---------------------------------------------------------------------------
# SCM handle table
# ---------------------------------------------------------------------------

_HANDLE_COUNTER = 0x70000000


def _new_handle() -> int:
    global _HANDLE_COUNTER
    _HANDLE_COUNTER += 1
    return _HANDLE_COUNTER


@dataclass
class ScmHandle:
    kind: str            # "scm" or "service"
    name: str
    record: Optional[ServiceRecord] = None


_HANDLES: Dict[int, ScmHandle] = {}


def _register(handle: ScmHandle) -> int:
    h = _new_handle()
    _HANDLES[h] = handle
    return h


def _resolve(h: int) -> Optional[ScmHandle]:
    return _HANDLES.get(h)


def _close(h: int) -> bool:
    return _HANDLES.pop(h, None) is not None


# ---------------------------------------------------------------------------
# Global SCM state
# ---------------------------------------------------------------------------

_SERVICES: Dict[str, ServiceRecord] = {}


def _register_default_services() -> None:
    """Pre-populate a small set of well-known services."""
    if _SERVICES:
        return
    defaults = [
        ServiceRecord(
            name="RpcSs",
            display_name="Remote Procedure Call (RPC)",
            binary_path=r"C:\Windows\System32\rpcss.exe",
            start_type=ServiceStartType.SERVICE_AUTO_START,
        ),
        ServiceRecord(
            name="EventLog",
            display_name="Windows Event Log",
            binary_path=r"C:\Windows\System32\svchost.exe",
            start_type=ServiceStartType.SERVICE_AUTO_START,
        ),
        ServiceRecord(
            name="W32Time",
            display_name="Windows Time",
            binary_path=r"C:\Windows\System32\svchost.exe",
            start_type=ServiceStartType.SERVICE_DISABLED,
        ),
    ]
    for s in defaults:
        _SERVICES[s.name] = s


_register_default_services()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def OpenSCManagerA(machine: Optional[str], dbname: Optional[str], access: int) -> int:
    """Open a handle to the SCM.  ``machine=None`` means the local SCM."""
    if (access & ~SC_MANAGER_ALL_ACCESS) != 0:
        log.warning("OpenSCManagerA: unsupported access bits %#x", access)
        # Real Win32 returns NULL (0) here; we mirror that.
        return 0
    return _register(ScmHandle(kind="scm", name=machine or "<local>"))


def CloseServiceHandle(h: int) -> bool:
    return _close(h)


def CreateServiceA(scm: int, name: str, display: str, access: int,
                   service_type: int, start_type: int, error_control: int,
                   binary_path: str, load_order_group: Optional[str],
                   tag_id: Optional[int], dependencies: Optional[str],
                   account: Optional[str], password: Optional[str]) -> int:
    if _resolve(scm) is None or _resolve(scm).kind != "scm":
        return 0
    if name in _SERVICES:
        return 0   # ERROR_SERVICE_EXISTS
    record = ServiceRecord(
        name=name,
        display_name=display,
        binary_path=binary_path,
        start_type=ServiceStartType(start_type),
        service_type=ServiceType(service_type & ServiceType.SERVICE_TYPE_ALL),
        error_control=ServiceErrorControl(error_control),
        load_order_group=load_order_group or "",
        tag_id=tag_id or 0,
        dependencies=tuple(
            d for d in (dependencies or "").split("\x00") if d
        ),
        account=account or "LocalSystem",
        password=password or "",
    )
    _SERVICES[name] = record
    return _register(ScmHandle(kind="service", name=name, record=record))


def OpenServiceA(scm: int, name: str, access: int) -> int:
    if _resolve(scm) is None or _resolve(scm).kind != "scm":
        return 0
    record = _SERVICES.get(name)
    if record is None:
        return 0
    return _register(ScmHandle(kind="service", name=name, record=record))


def DeleteService(h: int) -> bool:
    rec = _resolve(h)
    if rec is None or rec.kind != "service":
        return False
    if rec.record is not None:
        rec.record.status.current_state = ServiceState.SERVICE_STOPPED
    return _SERVICES.pop(rec.name, None) is not None


def StartServiceA(h: int, argc: int, argv: Optional[List[str]]) -> bool:
    rec = _resolve(h)
    if rec is None or rec.kind != "service" or rec.record is None:
        return False
    if not rec.record.is_runnable():
        return False
    rec.record.status.current_state = ServiceState.SERVICE_RUNNING
    return True


def ControlService(h: int, control: int) -> Optional[ServiceStatus]:
    rec = _resolve(h)
    if rec is None or rec.kind != "service" or rec.record is None:
        return None
    s = rec.record.status
    if control == 1 and s.current_state in (
        ServiceState.SERVICE_RUNNING,
        ServiceState.SERVICE_PAUSED,
    ):
        s.current_state = ServiceState.SERVICE_STOP_PENDING
        s.current_state = ServiceState.SERVICE_STOPPED
    elif control == 2 and s.current_state == ServiceState.SERVICE_RUNNING:
        s.current_state = ServiceState.SERVICE_PAUSED
    elif control == 3 and s.current_state == ServiceState.SERVICE_PAUSED:
        s.current_state = ServiceState.SERVICE_RUNNING
    return s


def QueryServiceStatus(h: int) -> Optional[ServiceStatus]:
    rec = _resolve(h)
    if rec is None or rec.kind != "service" or rec.record is None:
        return None
    return rec.record.status


def EnumServicesStatusA(scm: int, service_type: int, state: int
                        ) -> List[Tuple[str, str, ServiceStatus]]:
    if _resolve(scm) is None or _resolve(scm).kind != "scm":
        return []
    out: List[Tuple[str, str, ServiceStatus]] = []
    for name, rec in _SERVICES.items():
        if service_type and not (rec.service_type & service_type):
            continue
        if state and rec.status.current_state != ServiceState(state):
            continue
        out.append((rec.name, rec.display_name, rec.status))
    return out


def get_service(name: str) -> Optional[ServiceRecord]:
    return _SERVICES.get(name)


def reset() -> None:
    """Test helper — wipe the SCM database."""
    global _SERVICES
    _SERVICES = {}
    _HANDLES.clear()
    _register_default_services()


# ---------------------------------------------------------------------------
# EXPORTS — what ``advapi32.dll`` would advertise for the SCM.
# ---------------------------------------------------------------------------

EXPORTS = {
    "OpenSCManagerA": OpenSCManagerA,
    "CloseServiceHandle": CloseServiceHandle,
    "CreateServiceA": CreateServiceA,
    "OpenServiceA": OpenServiceA,
    "DeleteService": DeleteService,
    "StartServiceA": StartServiceA,
    "ControlService": ControlService,
    "QueryServiceStatus": QueryServiceStatus,
    "EnumServicesStatusA": EnumServicesStatusA,
}


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    reset()
    scm = OpenSCManagerA(None, None, SC_MANAGER_ALL_ACCESS)
    if scm == 0:
        return False
    h = CreateServiceA(
        scm, "UmerOS_test", "UmerOS test",
        SERVICE_ALL_ACCESS,
        int(ServiceType.SERVICE_WIN32_OWN_PROCESS),
        int(ServiceStartType.SERVICE_DEMAND_START),
        int(ServiceErrorControl.SERVICE_ERROR_NORMAL),
        r"C:\UmerOS\svc.exe",
        None, None, None, None, None,
    )
    if h == 0:
        CloseServiceHandle(scm)
        return False
    if not StartServiceA(h, 0, None):
        CloseServiceHandle(h)
        CloseServiceHandle(scm)
        return False
    st = QueryServiceStatus(h)
    if st is None or st.current_state != ServiceState.SERVICE_RUNNING:
        return False
    # Disabled services refuse to start.
    hd = CreateServiceA(
        scm, "UmerOS_disabled", "disabled",
        SERVICE_ALL_ACCESS,
        int(ServiceType.SERVICE_WIN32_OWN_PROCESS),
        int(ServiceStartType.SERVICE_DISABLED),
        int(ServiceErrorControl.SERVICE_ERROR_NORMAL),
        r"C:\UmerOS\svc.exe",
        None, None, None, None, None,
    )
    if StartServiceA(hd, 0, None):
        return False
    # Stop control.
    if ControlService(h, 1) is None:
        return False
    st = QueryServiceStatus(h)
    if st is None or st.current_state != ServiceState.SERVICE_STOPPED:
        return False
    if not DeleteService(h):
        return False
    CloseServiceHandle(h)
    CloseServiceHandle(hd)
    CloseServiceHandle(scm)
    # Enum.
    scm = OpenSCManagerA(None, None, SC_MANAGER_ALL_ACCESS)
    listing = EnumServicesStatusA(
        scm, int(ServiceType.SERVICE_WIN32_OWN_PROCESS), 0)
    if not any(name == "RpcSs" for name, _, _ in listing):
        return False
    CloseServiceHandle(scm)
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
