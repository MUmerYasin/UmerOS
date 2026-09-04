# UmerOS /srv — Site-Specific Service Data Hierarchy
# ===================================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``/srv`` filesystem hierarchy, managing site-specific data
# served by the system (WWW, FTP, Git, Rsync, TFTP, Samba, NFS).
#
# Modules:
# --------
# fhs         - Standard protocol directories, FHSValidator
# hierarchy   - SrvHierarchy, directory provisioning, single-tree layouts
# service     - ServiceRecord, ServiceConfig, ServiceStatus, ServiceAccessMode
# permissions - SrvPermissionManager, SecurityProfile, POSIX permission audit
# protocols   - Handlers for WWW, FTP, Git, Rsync, TFTP, Samba/NFS
# backup      - SrvBackupManager, BackupManifest, snapshot and restore engine
# manager     - SrvManager (master coordinator, registry persistence, auto-discovery)
# cli         - srv_ctl command line utility
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /srv — Site-Specific Service Data Hierarchy.
"""

from __future__ import annotations

__version__ = "1.1.0"
__all__: list[str] = []

# Best-effort imports.  The previous sys.path self-injection was removed
# because it let ``srv`` shadow the top-level ``manager`` module (H76
# root cause).

try:
    from .fhs import (
        DEFAULT_SRV_ROOT,
        PROHIBITED_IN_SRV,
        STANDARD_PROTOCOL_DIRS,
        FHSValidationResult,
        FHSValidator,
        OrganizationScheme,
        StandardProtocol,
    )
    __all__ += [
        "DEFAULT_SRV_ROOT",
        "PROHIBITED_IN_SRV",
        "STANDARD_PROTOCOL_DIRS",
        "FHSValidationResult",
        "FHSValidator",
        "OrganizationScheme",
        "StandardProtocol",
    ]
except ImportError:
    pass

try:
    from .hierarchy import (
        ServiceTreeLayout,
        SrvHierarchy,
    )
    __all__ += ["ServiceTreeLayout", "SrvHierarchy"]
except ImportError:
    pass

try:
    from .service import (
        ServiceAccessMode,
        ServiceConfig,
        ServiceRecord,
        ServiceStatus,
    )
    __all__ += [
        "ServiceAccessMode",
        "ServiceConfig",
        "ServiceRecord",
        "ServiceStatus",
    ]
except ImportError:
    pass

try:
    from .permissions import (
        PermissionAuditResult,
        SecurityProfile,
        SrvPermissionManager,
    )
    __all__ += [
        "PermissionAuditResult",
        "SecurityProfile",
        "SrvPermissionManager",
    ]
except ImportError:
    pass

try:
    from .protocols import (
        FTPServiceHandler,
        GitServiceHandler,
        RsyncServiceHandler,
        SambaNfsServiceHandler,
        TFTPServiceHandler,
        WWWServiceHandler,
    )
    __all__ += [
        "FTPServiceHandler",
        "GitServiceHandler",
        "RsyncServiceHandler",
        "SambaNfsServiceHandler",
        "TFTPServiceHandler",
        "WWWServiceHandler",
    ]
except ImportError:
    pass

try:
    from .backup import (
        BackupManifest,
        SrvBackupManager,
    )
    __all__ += ["BackupManifest", "SrvBackupManager"]
except ImportError:
    pass

try:
    from .manager import (
        SrvManager,
        get_default_manager,
        get_service_path,
        list_services,
        register_service,
    )
    __all__ += [
        "SrvManager",
        "get_default_manager",
        "get_service_path",
        "list_services",
        "register_service",
    ]
except ImportError:
    pass


def _selftest() -> bool:
    """Verify every name in ``__all__`` is importable from this package."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [name for name in __all__ if not hasattr(pkg, name)]
    if missing:
        print(
            f"srv selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
