# UmerOS /tmp — Temporary Filesystem Hierarchy
# =============================================
# GPL-3.0 — see LICENSE and README for details.
#
# Implementation of the ``/tmp`` filesystem hierarchy, managing
# transient files, UNIX socket directories, process locks, tmpwatch /
# systemd-tmpfiles reaper policies, and high-performance TmpFS.
#
# Modules:
# --------
# fhs         - Specifications, protected socket dirs, FHSValidator
# hierarchy   - TmpHierarchy, socket directory provisioning, per-user runtimes
# secure_io   - SecureIO, race-free mktemp, SecureTempFile, SecureTempDir
# lockfile    - ProcessLock, LockMetadata, stale lock detector
# reaper      - TmpReaper, ReapReport, age/quota pruning policies
# permissions - TmpPermissionManager, sticky-bit validation & security audit
# tmpfs       - TmpFS in-memory virtual RAM filesystem
# manager     - TmpManager (master coordinator & global API)
# cli         - tmp_ctl command-line controller
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /tmp — Temporary Filesystem Hierarchy.
"""

from __future__ import annotations

__version__ = "1.1.0"
__all__: list[str] = []

# Best-effort imports.  The previous sys.path self-injection was removed
# because it shadowed the top-level ``manager`` module (H76 root cause).

try:
    from .fhs import (
        DEFAULT_TMP_ROOT,
        PROTECTED_SOCKET_DIRS,
        RECOMMENDED_PREFIXES,
        FHSValidationResult,
        FHSValidator,
    )
    __all__ += [
        "DEFAULT_TMP_ROOT",
        "PROTECTED_SOCKET_DIRS",
        "RECOMMENDED_PREFIXES",
        "FHSValidationResult",
        "FHSValidator",
    ]
except ImportError:
    pass

try:
    from .hierarchy import TmpHierarchy
    __all__ += ["TmpHierarchy"]
except ImportError:
    pass

try:
    from .secure_io import (
        SecureIO,
        SecureTempDir,
        SecureTempFile,
    )
    __all__ += ["SecureIO", "SecureTempDir", "SecureTempFile"]
except ImportError:
    pass

try:
    from .lockfile import (
        LockAcquisitionError,
        LockMetadata,
        ProcessLock,
        is_pid_alive,
    )
    __all__ += [
        "LockAcquisitionError",
        "LockMetadata",
        "ProcessLock",
        "is_pid_alive",
    ]
except ImportError:
    pass

try:
    from .reaper import (
        DEFAULT_MAX_AGE_SEC,
        ReapReport,
        TmpReaper,
    )
    __all__ += ["DEFAULT_MAX_AGE_SEC", "ReapReport", "TmpReaper"]
except ImportError:
    pass

try:
    from .permissions import (
        TmpPermissionManager,
        TmpSecurityAuditResult,
    )
    __all__ += ["TmpPermissionManager", "TmpSecurityAuditResult"]
except ImportError:
    pass

try:
    from .tmpfs import (
        DEFAULT_TMPFS_MAX_BYTES,
        TmpFS,
        TmpFSNode,
        TmpFSQuotaExceededError,
    )
    __all__ += [
        "DEFAULT_TMPFS_MAX_BYTES",
        "TmpFS",
        "TmpFSNode",
        "TmpFSQuotaExceededError",
    ]
except ImportError:
    pass

try:
    from .manager import (
        TmpManager,
        clean_temp,
        get_default_tmp_manager,
        get_temp_dir,
        get_temp_file,
        mktemp,
    )
    __all__ += [
        "TmpManager",
        "clean_temp",
        "get_default_tmp_manager",
        "get_temp_dir",
        "get_temp_file",
        "mktemp",
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
            f"tmp selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
