"""
UmerOS Temporary Files Manager (/usr/tmp)
==========================================
Temporary file and workspace management.

Reference: Filesystem Hierarchy - /usr/tmp
  /usr/tmp provides temporary storage for applications and users.
  Files here are typically cleaned up periodically or on reboot.
  On modern systems, /usr/tmp is often a symlink to /var/tmp or /tmp.

UmerOS Virtualization:
  /usr/tmp provides isolated temporary workspaces for applications,
  with automatic cleanup, size limits, and access control. Each
  application gets its own temporary directory with configurable
  expiration policies.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set


# ─── Constants ───────────────────────────────────────────────────────────────

TMP_BASE_PATH = "/usr/tmp"
DEFAULT_MAX_SIZE_MB = 1024
DEFAULT_FILE_TTL = 3600
DEFAULT_DIR_TTL = 86400
MAX_TEMP_FILES = 10000
MAX_TEMP_SIZE_MB = 10240


# ─── Enums ───────────────────────────────────────────────────────────────────

class TmpFileState(IntEnum):
    """Temporary file states."""
    ACTIVE = 1
    EXPIRING = 2
    EXPIRED = 3
    PROTECTED = 4
    LOCKED = 5
    DELETED = 6


class TmpCleanupPolicy(IntEnum):
    """Cleanup policies."""
    TTL = 1
    LRU = 2
    SIZE_LIMIT = 3
    MANUAL = 4
    ON_EXIT = 5


class TmpFileType(IntEnum):
    """Types of temporary items."""
    FILE = 1
    DIRECTORY = 2
    SYMLINK = 3
    NAMED_PIPE = 4
    SOCKET = 5


class TmpAccessLevel(IntEnum):
    """Access levels."""
    PRIVATE = 1
    SHARED = 2
    READ_ONLY = 3
    RESTRICTED = 4


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class TmpFile:
    """Represents a temporary file or directory."""
    name: str
    path: str
    file_type: TmpFileType = TmpFileType.FILE
    state: TmpFileState = TmpFileState.ACTIVE
    access_level: TmpAccessLevel = TmpAccessLevel.PRIVATE
    size: int = 0
    owner: str = ""
    created_at: float = 0.0
    last_accessed: float = 0.0
    expires_at: float = 0.0
    ttl: int = 0
    content_hash: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        now = time.time()
        if self.created_at == 0.0:
            self.created_at = now
        if self.last_accessed == 0.0:
            self.last_accessed = now
        if self.ttl > 0 and self.expires_at == 0.0:
            self.expires_at = self.created_at + self.ttl

    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    def remaining_ttl(self) -> float:
        if self.expires_at <= 0:
            return -1
        remaining = self.expires_at - time.time()
        return max(0.0, remaining)

    def touch(self) -> None:
        self.last_accessed = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "type": self.file_type.name,
            "state": self.state.name,
            "access_level": self.access_level.name,
            "size": self.size,
            "owner": self.owner,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "expires_at": self.expires_at,
            "remaining_ttl": self.remaining_ttl(),
            "is_expired": self.is_expired(),
            "tags": self.tags,
        }


@dataclass
class TmpWorkspace:
    """A temporary workspace for an application."""
    name: str
    path: str
    owner: str
    created_at: float = 0.0
    expires_at: float = 0.0
    ttl: int = 0
    max_size_mb: int = DEFAULT_MAX_SIZE_MB
    max_files: int = MAX_TEMP_FILES
    files: List[TmpFile] = field(default_factory=list)
    cleanup_policy: TmpCleanupPolicy = TmpCleanupPolicy.TTL

    def __post_init__(self) -> None:
        now = time.time()
        if self.created_at == 0.0:
            self.created_at = now
        if self.ttl > 0 and self.expires_at == 0.0:
            self.expires_at = self.created_at + self.ttl

    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    def total_size_mb(self) -> float:
        total = sum(f.size for f in self.files)
        return total / (1024 * 1024)

    def file_count(self) -> int:
        return len(self.files)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "owner": self.owner,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "remaining_ttl": self.expires_at - time.time() if self.expires_at > 0 else -1,
            "max_size_mb": self.max_size_mb,
            "current_size_mb": self.total_size_mb(),
            "max_files": self.max_files,
            "current_files": self.file_count(),
            "cleanup_policy": self.cleanup_policy.name,
        }


@dataclass
class TmpSnapshot:
    """Snapshot of temporary file system state."""
    timestamp: float = 0.0
    total_files: int = 0
    total_size_mb: float = 0.0
    workspaces: int = 0
    expired_files: int = 0
    by_state: Dict[str, int] = field(default_factory=dict)
    by_owner: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_files": self.total_files,
            "total_size_mb": self.total_size_mb,
            "workspaces": self.workspaces,
            "expired_files": self.expired_files,
            "by_state": self.by_state,
            "by_owner": self.by_owner,
        }


# ─── Temporary Files Manager ────────────────────────────────────────────────

class TmpManager:
    """
    Manages /usr/tmp - Temporary Files and Workspaces.

    Responsibilities:
        - Create and manage temporary files and directories
        - Enforce TTL-based expiration policies
        - Manage temporary workspaces per application
        - Handle cleanup of expired files
        - Track disk usage and enforce limits
        - Provide snapshot and monitoring capabilities
        - Support different access levels and cleanup policies
    """

    def __init__(self) -> None:
        self._files: Dict[str, TmpFile] = {}
        self._workspaces: Dict[str, TmpWorkspace] = {}
        self._base_path = TMP_BASE_PATH
        self._max_total_size_mb = MAX_TEMP_SIZE_MB
        self._max_files = MAX_TEMP_FILES
        self._initialized = False

    def initialize(self) -> None:
        """Initialize temporary files manager."""
        if self._initialized:
            return
        self._setup_base_path()
        self._initialized = True

    def _setup_base_path(self) -> None:
        """Set up base temporary path."""
        pass

    def _generate_id(self) -> str:
        """Generate unique ID for temp items."""
        return uuid.uuid4().hex[:12]

    def _check_limits(self) -> bool:
        """Check if we're within limits."""
        if len(self._files) >= self._max_files:
            return False
        current_size = sum(f.size for f in self._files.values()) / (1024 * 1024)
        if current_size >= self._max_total_size_mb:
            return False
        return True

    # ─── File Management ─────────────────────────────────────────────────

    def create_file(
        self,
        name: str = "",
        owner: str = "",
        ttl: int = DEFAULT_FILE_TTL,
        size: int = 0,
        access_level: TmpAccessLevel = TmpAccessLevel.PRIVATE,
        tags: Optional[List[str]] = None,
    ) -> TmpFile:
        """Create a temporary file."""
        if not name:
            name = f"tmp_{self._generate_id()}"
        if not self._check_limits():
            raise RuntimeError("Temporary file limit reached")

        file_id = self._generate_id()
        path = f"{self._base_path}/{name}"

        tmp_file = TmpFile(
            name=name,
            path=path,
            file_type=TmpFileType.FILE,
            size=size,
            owner=owner,
            ttl=ttl,
            access_level=access_level,
            tags=tags or [],
        )
        self._files[file_id] = tmp_file
        return tmp_file

    def create_directory(
        self,
        name: str = "",
        owner: str = "",
        ttl: int = DEFAULT_DIR_TTL,
        access_level: TmpAccessLevel = TmpAccessLevel.PRIVATE,
    ) -> TmpFile:
        """Create a temporary directory."""
        if not name:
            name = f"dir_{self._generate_id()}"
        if not self._check_limits():
            raise RuntimeError("Temporary file limit reached")

        file_id = self._generate_id()
        path = f"{self._base_path}/{name}"

        tmp_dir = TmpFile(
            name=name,
            path=path,
            file_type=TmpFileType.DIRECTORY,
            owner=owner,
            ttl=ttl,
            access_level=access_level,
        )
        self._files[file_id] = tmp_dir
        return tmp_dir

    def get_file(self, name: str) -> Optional[TmpFile]:
        """Get temporary file by name."""
        for f in self._files.values():
            if f.name == name:
                f.touch()
                return f
        return None

    def delete_file(self, name: str) -> bool:
        """Delete a temporary file."""
        file_id = None
        for fid, f in self._files.items():
            if f.name == name:
                file_id = fid
                break
        if file_id is None:
            return False
        self._files[file_id].state = TmpFileState.DELETED
        del self._files[file_id]
        return True

    def list_files(self, owner: Optional[str] = None) -> List[TmpFile]:
        """List temporary files, optionally filtered by owner."""
        if owner:
            return [f for f in self._files.values() if f.owner == owner]
        return list(self._files.values())

    def find_files(self, query: str) -> List[TmpFile]:
        """Find files by name query."""
        query_lower = query.lower()
        return [f for f in self._files.values() if query_lower in f.name.lower()]

    def find_files_by_tag(self, tag: str) -> List[TmpFile]:
        """Find files by tag."""
        return [f for f in self._files.values() if tag in f.tags]

    def protect_file(self, name: str) -> bool:
        """Protect a file from expiration."""
        for f in self._files.values():
            if f.name == name:
                f.state = TmpFileState.PROTECTED
                f.ttl = 0
                f.expires_at = 0
                return True
        return False

    def lock_file(self, name: str) -> bool:
        """Lock a file to prevent deletion."""
        for f in self._files.values():
            if f.name == name:
                f.state = TmpFileState.LOCKED
                return True
        return False

    def unlock_file(self, name: str) -> bool:
        """Unlock a file."""
        for f in self._files.values():
            if f.name == name and f.state == TmpFileState.LOCKED:
                f.state = TmpFileState.ACTIVE
                return True
        return False

    # ─── Workspace Management ────────────────────────────────────────────

    def create_workspace(
        self,
        name: str,
        owner: str,
        ttl: int = DEFAULT_DIR_TTL,
        max_size_mb: int = DEFAULT_MAX_SIZE_MB,
        cleanup_policy: TmpCleanupPolicy = TmpCleanupPolicy.TTL,
    ) -> TmpWorkspace:
        """Create a temporary workspace."""
        if name in self._workspaces:
            raise ValueError(f"Workspace '{name}' already exists")

        path = f"{self._base_path}/{name}"
        workspace = TmpWorkspace(
            name=name,
            path=path,
            owner=owner,
            ttl=ttl,
            max_size_mb=max_size_mb,
            cleanup_policy=cleanup_policy,
        )
        self._workspaces[name] = workspace
        return workspace

    def get_workspace(self, name: str) -> Optional[TmpWorkspace]:
        """Get workspace by name."""
        return self._workspaces.get(name)

    def delete_workspace(self, name: str) -> bool:
        """Delete a workspace and its files."""
        if name not in self._workspaces:
            return False
        workspace = self._workspaces[name]
        for f in workspace.files:
            self._files.pop(f.name, None)
        del self._workspaces[name]
        return True

    def list_workspaces(self, owner: Optional[str] = None) -> List[TmpWorkspace]:
        """List workspaces, optionally filtered by owner."""
        if owner:
            return [w for w in self._workspaces.values() if w.owner == owner]
        return list(self._workspaces.values())

    def add_file_to_workspace(self, workspace_name: str, file_name: str) -> bool:
        """Add a file to a workspace."""
        workspace = self._workspaces.get(workspace_name)
        if not workspace:
            return False
        file = self.get_file(file_name)
        if not file:
            return False
        if len(workspace.files) >= workspace.max_files:
            return False
        if workspace.total_size_mb() + file.size / (1024 * 1024) > workspace.max_size_mb:
            return False
        workspace.files.append(file)
        return True

    # ─── Cleanup Management ──────────────────────────────────────────────

    def get_expired_files(self) -> List[TmpFile]:
        """Get all expired files."""
        return [f for f in self._files.values() if f.is_expired()]

    def get_locked_files(self) -> List[TmpFile]:
        """Get all locked files."""
        return [f for f in self._files.values() if f.state == TmpFileState.LOCKED]

    def get_protected_files(self) -> List[TmpFile]:
        """Get all protected files."""
        return [f for f in self._files.values() if f.state == TmpFileState.PROTECTED]

    def cleanup_expired(self) -> int:
        """Remove expired files. Returns count removed."""
        expired = self.get_expired_files()
        count = 0
        for f in expired:
            if f.state not in (TmpFileState.LOCKED, TmpFileState.PROTECTED):
                self.delete_file(f.name)
                count += 1
        return count

    def cleanup_by_owner(self, owner: str) -> int:
        """Remove all files owned by a user. Returns count removed."""
        files = self.list_files(owner=owner)
        count = 0
        for f in files:
            if f.state not in (TmpFileState.LOCKED, TmpFileState.PROTECTED):
                self.delete_file(f.name)
                count += 1
        return count

    def cleanup_all(self) -> int:
        """Remove all non-protected, non-locked files. Returns count removed."""
        count = 0
        for f in list(self._files.values()):
            if f.state not in (TmpFileState.LOCKED, TmpFileState.PROTECTED):
                self.delete_file(f.name)
                count += 1
        return count

    # ─── Snapshot & Statistics ───────────────────────────────────────────

    def take_snapshot(self) -> TmpSnapshot:
        """Take a snapshot of the temporary file system."""
        by_state: Dict[str, int] = {}
        by_owner: Dict[str, int] = {}
        total_size = 0

        for f in self._files.values():
            state_name = f.state.name
            by_state[state_name] = by_state.get(state_name, 0) + 1
            if f.owner:
                by_owner[f.owner] = by_owner.get(f.owner, 0) + 1
            total_size += f.size

        return TmpSnapshot(
            timestamp=time.time(),
            total_files=len(self._files),
            total_size_mb=total_size / (1024 * 1024),
            workspaces=len(self._workspaces),
            expired_files=len(self.get_expired_files()),
            by_state=by_state,
            by_owner=by_owner,
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get temporary file system statistics."""
        total_size = sum(f.size for f in self._files.values())
        return {
            "total_files": len(self._files),
            "total_workspaces": len(self._workspaces),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "max_files": self._max_files,
            "max_size_mb": self._max_total_size_mb,
            "expired_files": len(self.get_expired_files()),
            "locked_files": len(self.get_locked_files()),
            "protected_files": len(self.get_protected_files()),
            "owners": list(set(f.owner for f in self._files.values() if f.owner)),
        }

    def refresh(self) -> None:
        """Reset temporary files manager."""
        self._files.clear()
        self._workspaces.clear()
        self._initialized = False
        self.initialize()


# ─── Global Singleton ────────────────────────────────────────────────────────

_global_tmp_manager: Optional[TmpManager] = None


def get_global_tmp_manager() -> TmpManager:
    """Get or create the global temporary files manager."""
    global _global_tmp_manager
    if _global_tmp_manager is None:
        _global_tmp_manager = TmpManager()
        _global_tmp_manager.initialize()
    return _global_tmp_manager
