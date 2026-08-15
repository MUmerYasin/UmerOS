"""
UmerOS /tmp — Temporary Filesystem Hierarchy
============================================

FHS 2.3/3.0 and TLDP-compliant implementation of the ``/tmp`` filesystem
hierarchy, managing transient files, UNIX socket directories, process locks,
tmpwatch/systemd-tmpfiles reaper policies, and high-performance TmpFS.

TLDP Reference:
https://tldp.org/LDP/Linux-Filesystem-Hierarchy/html/tmp.html

Modules:
--------
fhs         - FHS & TLDP specifications, protected socket dirs, FHSValidator
hierarchy   - TmpHierarchy, socket directory provisioning, per-user runtimes
secure_io   - SecureIO, race-free mktemp, SecureTempFile, SecureTempDir
lockfile    - ProcessLock, LockMetadata, stale lock detector
reaper      - TmpReaper, ReapReport, age/quota pruning policies
permissions - TmpPermissionManager, sticky-bit validation & security audit
tmpfs       - TmpFS in-memory virtual RAM filesystem
manager     - TmpManager (master coordinator & global API)
cli         - tmp_ctl command-line controller

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
    DEFAULT_TMP_ROOT,
    PROTECTED_SOCKET_DIRS,
    RECOMMENDED_PREFIXES,
    FHSValidationResult,
    FHSValidator,
)
from hierarchy import (
    TmpHierarchy,
)
from secure_io import (
    SecureIO,
    SecureTempDir,
    SecureTempFile,
)
from lockfile import (
    LockAcquisitionError,
    LockMetadata,
    ProcessLock,
    is_pid_alive,
)
from reaper import (
    DEFAULT_MAX_AGE_SEC,
    ReapReport,
    TmpReaper,
)
from permissions import (
    TmpPermissionManager,
    TmpSecurityAuditResult,
)
from tmpfs import (
    DEFAULT_TMPFS_MAX_BYTES,
    TmpFS,
    TmpFSNode,
    TmpFSQuotaExceededError,
)
from manager import (
    TmpManager,
    clean_temp,
    get_default_tmp_manager,
    get_temp_dir,
    get_temp_file,
    mktemp,
)

__version__ = "1.0.0"

__all__ = [
    # FHS & Standards
    "DEFAULT_TMP_ROOT",
    "PROTECTED_SOCKET_DIRS",
    "RECOMMENDED_PREFIXES",
    "FHSValidationResult",
    "FHSValidator",
    # Hierarchy
    "TmpHierarchy",
    # Secure IO
    "SecureIO",
    "SecureTempFile",
    "SecureTempDir",
    # Lockfiles
    "ProcessLock",
    "LockMetadata",
    "LockAcquisitionError",
    "is_pid_alive",
    # Reaper
    "TmpReaper",
    "ReapReport",
    "DEFAULT_MAX_AGE_SEC",
    # Permissions
    "TmpPermissionManager",
    "TmpSecurityAuditResult",
    # TmpFS
    "TmpFS",
    "TmpFSNode",
    "TmpFSQuotaExceededError",
    "DEFAULT_TMPFS_MAX_BYTES",
    # Master Manager & Helpers
    "TmpManager",
    "get_default_tmp_manager",
    "mktemp",
    "get_temp_file",
    "get_temp_dir",
    "clean_temp",
]
