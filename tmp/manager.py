"""
UmerOS /tmp — Master Temporary Filesystem Coordinator
=====================================================

Central manager for transient files, sockets, process locks, and in-memory
buffers across the /tmp hierarchy in UmerOS.

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fhs import (
    DEFAULT_TMP_ROOT,
    PROTECTED_SOCKET_DIRS,
    FHSValidationResult,
    FHSValidator,
)
from hierarchy import TmpHierarchy
from lockfile import ProcessLock
from permissions import TmpPermissionManager, TmpSecurityAuditResult
from reaper import ReapReport, TmpReaper
from secure_io import SecureIO, SecureTempDir, SecureTempFile
from tmpfs import TmpFS

log = logging.getLogger("UmerOS.Tmp.Manager")


class TmpManager:
    """
    Master coordinator for /tmp in UmerOS.
    """

    def __init__(self, tmp_root: Path | str = DEFAULT_TMP_ROOT) -> None:
        self.root = Path(tmp_root).resolve()
        self.hierarchy = TmpHierarchy(self.root)
        self.reaper = TmpReaper(self.root)
        self.tmpfs = TmpFS()
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        """Bootstraps root and socket folders if not yet present."""
        self.hierarchy.bootstrap()

    # -------------------------------------------------------------------------
    # Secure Creation API
    # -------------------------------------------------------------------------
    def create_temp_file(
        self,
        prefix: str = "tmp.",
        suffix: str = "",
        mode: int = 0o600,
        content: Optional[bytes | str] = None,
    ) -> Path:
        """Creates an atomic temporary file with 0600 mode."""
        return SecureIO.create_temp_file(
            prefix=prefix,
            suffix=suffix,
            dir_path=self.root,
            mode=mode,
            content=content,
        )

    def create_temp_dir(
        self,
        prefix: str = "tmp.",
        suffix: str = "",
        mode: int = 0o700,
    ) -> Path:
        """Creates an atomic temporary directory with 0700 mode."""
        return SecureIO.create_temp_dir(
            prefix=prefix,
            suffix=suffix,
            dir_path=self.root,
            mode=mode,
        )

    def mktemp(
        self,
        template: str = "tmp.XXXXXXXXXX",
        directory: bool = False,
        dry_run: bool = False,
    ) -> Path:
        """Emulates POSIX mktemp utility."""
        return SecureIO.mktemp(
            template=template,
            directory=directory,
            tmp_dir=self.root,
            dry_run=dry_run,
        )

    # -------------------------------------------------------------------------
    # Lockfile API
    # -------------------------------------------------------------------------
    def lock(self, name: str, timeout: float = 0.0) -> ProcessLock:
        """Creates and acquires a named process lock."""
        lock = ProcessLock(name=name, tmp_root=self.root)
        lock.acquire(timeout=timeout)
        return lock

    def list_locks(self) -> List[Dict[str, Any]]:
        """Lists all active lock files in /tmp."""
        return ProcessLock.list_all_locks(self.root)

    # -------------------------------------------------------------------------
    # Reaper & Cleanup API
    # -------------------------------------------------------------------------
    def clean(self, max_age_seconds: Optional[float] = None, dry_run: bool = False) -> ReapReport:
        """Cleans temporary files older than age threshold."""
        return self.reaper.clean_by_age(max_age_seconds=max_age_seconds, dry_run=dry_run)

    def wipe_on_boot(self, dry_run: bool = False) -> ReapReport:
        """Cleans all transient files on system boot while preserving protected sockets."""
        return self.reaper.clean_on_boot(dry_run=dry_run)

    def enforce_quota(self, max_bytes: int, dry_run: bool = False) -> ReapReport:
        """Enforces high-water mark disk quota on /tmp."""
        return self.reaper.clean_by_quota(max_total_bytes=max_bytes, dry_run=dry_run)

    # -------------------------------------------------------------------------
    # Auditing & Inspection
    # -------------------------------------------------------------------------
    def audit_all(self) -> Dict[str, Any]:
        """Runs full FHS compliance and permission security audit."""
        fhs_res = FHSValidator.validate_tmp_root(self.root)
        sec_res = TmpPermissionManager.audit_security(self.root)
        stats = self.hierarchy.get_stats()

        return {
            "root": str(self.root),
            "fhs_compliant": fhs_res.is_compliant,
            "fhs_violations": fhs_res.violations,
            "fhs_warnings": fhs_res.warnings,
            "security_secure": sec_res.is_secure,
            "sticky_bit_set": sec_res.sticky_bit_set,
            "security_issues": sec_res.issues,
            "recommendations": fhs_res.recommendations + sec_res.recommendations,
            "stats": stats,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Returns statistics and storage metrics for /tmp."""
        stats = self.hierarchy.get_stats()
        locks = self.list_locks()
        return {
            "root": str(self.root),
            "total_size_bytes": stats["total_size_bytes"],
            "total_files": stats["total_files"],
            "total_dirs": stats["total_dirs"],
            "file_types": stats["file_types"],
            "active_locks": len(locks),
            "tmpfs_used_bytes": self.tmpfs.used_bytes,
            "tmpfs_free_bytes": self.tmpfs.free_bytes,
        }


# ── Global API Helpers ───────────────────────────────────────────────────

_global_tmp_manager: Optional[TmpManager] = None


def get_default_tmp_manager() -> TmpManager:
    global _global_tmp_manager
    if _global_tmp_manager is None:
        _global_tmp_manager = TmpManager()
    return _global_tmp_manager


def mktemp(template: str = "tmp.XXXXXXXXXX", directory: bool = False) -> Path:
    return get_default_tmp_manager().mktemp(template=template, directory=directory)


def get_temp_file(prefix: str = "tmp.", suffix: str = "") -> Path:
    return get_default_tmp_manager().create_temp_file(prefix=prefix, suffix=suffix)


def get_temp_dir(prefix: str = "tmp.", suffix: str = "") -> Path:
    return get_default_tmp_manager().create_temp_dir(prefix=prefix, suffix=suffix)


def clean_temp(max_age_seconds: Optional[float] = None) -> ReapReport:
    return get_default_tmp_manager().clean(max_age_seconds=max_age_seconds)
