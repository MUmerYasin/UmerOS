"""
UmerOS /srv — Site-Specific Service Data Hierarchy
===================================================

FHS 2.3/3.0 and compliant implementation of the ``/srv`` filesystem
hierarchy, managing site-specific data served by the system (WWW, FTP,
Git, Rsync, TFTP, Samba, NFS).


Modules:
--------
fhs         - FHS & TLDP specifications, standard protocol directories, FHSValidator
hierarchy   - SrvHierarchy, directory provisioning, single-tree layouts
service     - ServiceRecord, ServiceConfig, ServiceStatus, ServiceAccessMode
permissions - SrvPermissionManager, SecurityProfile, POSIX permission audit
protocols   - Handlers for WWW, FTP, Git, Rsync, TFTP, Samba/NFS
backup      - SrvBackupManager, BackupManifest, snapshot and restore engine
manager     - SrvManager (master coordinator, registry persistence, auto-discovery)
cli         - srv_ctl command line utility

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import sys as _sys
from os import path as _p

_this_dir = _p.dirname(_p.abspath(__file__))
if _this_dir not in _sys.path:
    _sys.path.insert(0, _this_dir)

from fhs import (
    DEFAULT_SRV_ROOT,
    PROHIBITED_IN_SRV,
    STANDARD_PROTOCOL_DIRS,
    FHSValidationResult,
    FHSValidator,
    OrganizationScheme,
    StandardProtocol,
)
from hierarchy import (
    ServiceTreeLayout,
    SrvHierarchy,
)
from service import (
    ServiceAccessMode,
    ServiceConfig,
    ServiceRecord,
    ServiceStatus,
)
from permissions import (
    PermissionAuditResult,
    SecurityProfile,
    SrvPermissionManager,
)
from protocols import (
    FTPServiceHandler,
    GitServiceHandler,
    RsyncServiceHandler,
    SambaNfsServiceHandler,
    TFTPServiceHandler,
    WWWServiceHandler,
)
from backup import (
    BackupManifest,
    SrvBackupManager,
)
from manager import (
    SrvManager,
    get_default_manager,
    get_service_path,
    list_services,
    register_service,
)

__version__ = "1.0.0"

__all__ = [
    # FHS & Standards
    "DEFAULT_SRV_ROOT",
    "STANDARD_PROTOCOL_DIRS",
    "PROHIBITED_IN_SRV",
    "OrganizationScheme",
    "StandardProtocol",
    "FHSValidationResult",
    "FHSValidator",
    # Hierarchy
    "ServiceTreeLayout",
    "SrvHierarchy",
    # Service Models
    "ServiceStatus",
    "ServiceAccessMode",
    "ServiceConfig",
    "ServiceRecord",
    # Permissions
    "SecurityProfile",
    "PermissionAuditResult",
    "SrvPermissionManager",
    # Protocol Handlers
    "WWWServiceHandler",
    "FTPServiceHandler",
    "GitServiceHandler",
    "RsyncServiceHandler",
    "TFTPServiceHandler",
    "SambaNfsServiceHandler",
    # Backup & Restore
    "BackupManifest",
    "SrvBackupManager",
    # Master Manager
    "SrvManager",
    "get_default_manager",
    "register_service",
    "get_service_path",
    "list_services",
]
