# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
UmerOS Yum Package Manager
============================
Pure-Python Yum-compatible package management system for UmerOS.

Supports:
    - Package install / update / remove / upgrade / downgrade
    - Repository management (add, remove, enable, disable, list)
    - Dependency resolution (requires, suggests, recommends, conflicts, obsoletes)
    - Package groups (install, remove, list, info, mark)
    - Transaction history with rollback
    - Security updates (CVE-based advisory filtering)
    - Local package install
    - Cache management (clean, refresh)
    - Package search, list, info, provides
    - Plugin architecture (pre/post transaction hooks)
    - Autoremove (unused dependency cleanup)
    - Check-update (available updates report)
    - Distribution sync / distro-sync
    - Shell mode (interactive batch commands)

Based on RHEL Yum documentation:
    https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/7/
    html/system_administrators_guide/ch-yum

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import copy
import enum
import hashlib
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PackageState(str, enum.Enum):
    """Package lifecycle states."""
    AVAILABLE = "available"
    INSTALLED = "installed"
    UPDATED = "updated"
    DOWNGRADED = "downgraded"
    ERASED = "erased"
    OBSOLETED = "obsoleted"
    AVAILABLE_IN_REPO = "available_in_repo"
    REMOVED = "removed"


class TransactionAction(str, enum.Enum):
    """Actions performed in a transaction."""
    INSTALL = "install"
    UPDATE = "update"
    DOWNGRADE = "downgrade"
    REMOVE = "remove"
    ERASE = "erase"
    OBSOLETE = "obsolete"
    VERIFY = "verify"
    SYNC = "sync"
    REINSTALL = "reinstall"


class TransactionState(str, enum.Enum):
    """Transaction lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class RepoStatus(str, enum.Enum):
    """Repository status."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    BROKEN = "broken"


class CleanType(str, enum.Enum):
    """Cache cleanup targets."""
    ALL = "all"
    PACKAGES = "packages"
    METADATA = "metadata"
    DB_CACHE = "dbcache"
    YUM_CACHE = "yum-cache"
    TIMER = "timer"
    DNF_CACHE = "dnf-cache"


class UpdateInfoType(str, enum.Enum):
    """Security advisory types."""
    SECURITY = "security"
    BUGFIX = "bugfix"
    ENHANCEMENT = "enhancement"
    NEW_PACKAGE = "newpackage"
    UNKNOWN = "unknown"


class MarkReason(str, enum.Enum):
    """Reason for package marking."""
    USER = "user"
    DEPENDENCY = "dependency"
    GROUP = "group"
    PLUGIN = "plugin"
    LOCAL = "local"


class PluginHook(str, enum.Enum):
    """Plugin hook points."""
    PRE_TRANSACTION = "pre_transaction"
    POST_TRANSACTION = "post_transaction"
    PRE_INSTALL = "pre_install"
    POST_INSTALL = "post_install"
    PRE_REMOVE = "pre_remove"
    POST_REMOVE = "post_remove"
    PRE_UPDATE = "pre_update"
    POST_UPDATE = "post_update"
    RESOLVE_DEPS = "resolve_deps"
    CACHE_LOADED = "cache_loaded"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PackageNevra:
    """Package name-epoch-version-release-architecture identifier."""
    name: str
    epoch: str = "0"
    version: str = ""
    release: str = ""
    arch: str = "noarch"

    @property
    def nevra(self) -> str:
        """Full NEVRA string."""
        if self.epoch == "0":
            return f"{self.name}-{self.version}-{self.release}.{self.arch}"
        return f"{self.name}-{self.epoch}:{self.version}-{self.release}.{self.arch}"

    @property
    def nvra(self) -> str:
        """N-V-R.A string (no epoch)."""
        return f"{self.name}-{self.version}-{self.release}.{self.arch}"

    @property
    def evr(self) -> str:
        """Epoch:Version-Release string for comparison."""
        if self.epoch == "0":
            return f"{self.version}-{self.release}"
        return f"{self.epoch}:{self.version}-{self.release}"

    @classmethod
    def from_string(cls, s: str) -> "PackageNevra":
        """Parse a NEVRA string like ``name-epoch:version-release.arch``."""
        # Try to split arch first
        dot_idx = s.rfind(".")
        if dot_idx == -1:
            return cls(name=s, arch="noarch")
        arch = s[dot_idx + 1:]
        rest = s[:dot_idx]

        # Try to split release
        dash_idx = rest.rfind("-")
        if dash_idx == -1:
            return cls(name=rest, arch=arch)
        release = rest[dash_idx + 1:]
        rest = rest[:dash_idx]

        # Try to split version
        dash_idx = rest.rfind("-")
        if dash_idx == -1:
            return cls(name=rest, release=release, arch=arch)
        version = rest[dash_idx + 1:]
        rest = rest[:dash_idx]

        # Try to split epoch
        colon_idx = rest.find(":")
        if colon_idx == -1:
            return cls(name=rest, version=version, release=release, arch=arch)
        epoch = rest[:colon_idx]
        name = rest[colon_idx + 1:]
        return cls(name=name, epoch=epoch, version=version, release=release, arch=arch)

    def compare_evr(self, other: "PackageNevra") -> int:
        """Compare epoch:version-release. Returns -1, 0, or 1."""
        return _compare_evr(self.evr, other.evr)


def _compare_evr(a: str, b: str) -> int:
    """Compare two EVR strings (epoch:version-release)."""
    def _split_evr(evr: str) -> Tuple[int, List[str], List[str]]:
        epoch = "0"
        rest = evr
        if ":" in rest:
            epoch, rest = rest.split(":", 1)
        parts = rest.split("-", 1)
        ver = parts[0].split(".") if parts[0] else []
        rel = parts[1].split(".") if len(parts) > 1 and parts[1] else []
        return int(epoch), ver, rel

    a_epoch, a_ver, a_rel = _split_evr(a)
    b_epoch, b_ver, b_rel = _split_evr(b)

    if a_epoch != b_epoch:
        return 1 if a_epoch > b_epoch else -1

    for av, bv in zip(a_ver, b_ver):
        if av != bv:
            try:
                return 1 if int(av) > int(bv) else -1
            except ValueError:
                return 1 if av > bv else -1
    if len(a_ver) != len(b_ver):
        return 1 if len(a_ver) > len(b_ver) else -1

    for ar, br in zip(a_rel, b_rel):
        if ar != br:
            try:
                return 1 if int(ar) > int(br) else -1
            except ValueError:
                return 1 if ar > br else -1
    if len(a_rel) != len(b_rel):
        return 1 if len(a_rel) > len(b_rel) else -1

    return 0


@dataclass
class PackageInfo:
    """Full package metadata."""
    nevra: PackageNevra
    summary: str = ""
    description: str = ""
    url: str = ""
    license: str = ""
    packager: str = ""
    vendor: str = ""
    size: int = 0
    installed_size: int = 0
    build_date: str = ""
    install_date: str = ""
    source_rpm: str = ""
    arch: str = "noarch"
    os: str = ""
    state: PackageState = PackageState.AVAILABLE
    repo_id: str = ""
    requires: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    obsoletes: List[str] = field(default_factory=list)
    suggests: List[str] = field(default_factory=list)
    recommends: List[str] = field(default_factory=list)
    changelog: List[Tuple[str, str]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    rpm_tags: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.nevra.name

    @property
    def version(self) -> str:
        return self.nevra.nevra

    @property
    def evr(self) -> str:
        return self.nevra.evr


@dataclass
class RepoConfig:
    """Repository configuration."""
    repo_id: str
    name: str
    baseurl: List[str] = field(default_factory=list)
    metalink: str = ""
    mirrorlist: str = ""
    gpgcheck: bool = True
    enabled: bool = True
    gpgkey: List[str] = field(default_factory=list)
    sslverify: bool = True
    sslcacert: str = ""
    sslclientcert: str = ""
    sslclientkey: str = ""
    metadata_expire: str = "6h"
    priority: int = 99
    cost: int = 1000
    module_hotfixes: bool = False
    status: RepoStatus = RepoStatus.ENABLED
    failovermethod: str = "roundrobin"
    max_retries: int = 10
    timeout: int = 30

    @property
    def is_active(self) -> bool:
        return self.enabled and self.status == RepoStatus.ENABLED


@dataclass
class TransactionItem:
    """Single item in a transaction."""
    action: TransactionAction
    package: PackageInfo
    old_package: Optional[PackageInfo] = None
    reason: MarkReason = MarkReason.USER
    state: TransactionState = TransactionState.PENDING
    error: str = ""


@dataclass
class TransactionResult:
    """Result of a transaction execution."""
    tid: int
    timestamp: str
    action: str
    state: TransactionState
    items: List[TransactionItem] = field(default_factory=list)
    request_by: str = "user"
    return_code: int = 0
    errors: List[str] = field(default_factory=list)
    rpmdb_free_bytes: int = 0

    @property
    def success(self) -> bool:
        return self.state == TransactionState.COMMITTED


@dataclass
class PackageGroup:
    """Package group definition."""
    group_id: str
    name: str
    description: str = ""
    user_visible: bool = True
    packages: List[str] = field(default_factory=list)
    default_packages: List[str] = field(default_factory=list)
    optional_packages: List[str] = field(default_factory=list)
    conditional_packages: List[str] = field(default_factory=list)
    langonly: str = ""
    install: bool = False

    @property
    def all_packages(self) -> List[str]:
        return self.packages + self.default_packages


@dataclass
class HistoryRecord:
    """Transaction history record."""
    tid: int
    timestamp: str
    cmdline: str
    return_code: int = 0
    rpmdb_version: str = ""
    items: List[Dict[str, str]] = field(default_factory=list)
    state: TransactionState = TransactionState.COMMITTED
    altered: int = 0
    runtime: float = 0.0

    @property
    def success(self) -> bool:
        return self.return_code == 0


@dataclass
class UpdateInfo:
    """Security/update advisory for a package."""
    update_id: str
    title: str
    issuer: str = ""
    status: str = ""
    update_type: UpdateInfoType = UpdateInfoType.UNKNOWN
    severity: str = ""
    rights: str = ""
    reference_ids: List[str] = field(default_factory=list)
    description: str = ""
    issued_date: str = ""
    updated_date: str = ""
    pkg_names: List[str] = field(default_factory=list)


@dataclass
class DepSolveResult:
    """Result of dependency resolution."""
    install: List[PackageInfo] = field(default_factory=list)
    update: List[Tuple[PackageInfo, PackageInfo]] = field(default_factory=list)
    remove: List[PackageInfo] = field(default_factory=list)
    skip: List[Tuple[PackageInfo, str]] = field(default_factory=list)
    conflicts: List[Tuple[PackageInfo, PackageInfo]] = field(default_factory=list)
    obsoleted: List[Tuple[PackageInfo, PackageInfo]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.conflicts) == 0 and len(self.skip) == 0

    @property
    def total_changes(self) -> int:
        return len(self.install) + len(self.update) + len(self.remove)


# ---------------------------------------------------------------------------
# Plugin Protocol
# ---------------------------------------------------------------------------

class YumPlugin(Protocol):
    """Protocol for Yum manager plugins."""
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def hook(self) -> PluginHook: ...
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Cache Manager
# ---------------------------------------------------------------------------

class CacheManager:
    """Manages package metadata and file caches."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_cache: Dict[str, Any] = {}
        self._package_cache: Dict[str, bytes] = {}
        self._timestamp: Optional[float] = None

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    def is_fresh(self, max_age_seconds: int = 21600) -> bool:
        """Check if cache is fresh (default 6 hours)."""
        if self._timestamp is None:
            return False
        return (time.time() - self._timestamp) < max_age_seconds

    def load_metadata(self, repo_id: str) -> Optional[Dict[str, Any]]:
        """Load cached metadata for a repository."""
        cache_file = self._cache_dir / f"{repo_id}_primary.xml"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                self._metadata_cache[repo_id] = data
                return data
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def save_metadata(self, repo_id: str, metadata: Dict[str, Any]) -> None:
        """Save metadata to cache."""
        cache_file = self._cache_dir / f"{repo_id}_primary.xml"
        try:
            cache_file.write_text(
                json.dumps(metadata, indent=2, default=str),
                encoding="utf-8",
            )
            self._metadata_cache[repo_id] = metadata
            self._timestamp = time.time()
        except OSError as exc:
            logger.error("Failed to save cache for %s: %s", repo_id, exc)

    def get_cached_packages(self, repo_id: str) -> List[str]:
        """List cached package filenames for a repository."""
        repo_cache = self._cache_dir / "packages" / repo_id
        if not repo_cache.exists():
            return []
        return [
            p.name for p in repo_cache.iterdir()
            if p.is_file() and p.name.endswith((".rpm", ".xml"))
        ]

    def add_package(self, repo_id: str, filename: str, data: bytes) -> Path:
        """Cache a package file."""
        repo_cache = self._cache_dir / "packages" / repo_id
        repo_cache.mkdir(parents=True, exist_ok=True)
        pkg_path = repo_cache / filename
        pkg_path.write_bytes(data)
        return pkg_path

    def remove_package(self, repo_id: str, filename: str) -> bool:
        """Remove a cached package file."""
        pkg_path = self._cache_dir / "packages" / repo_id / filename
        if pkg_path.exists():
            pkg_path.unlink()
            return True
        return False

    def clean(self, clean_type: CleanType = CleanType.ALL) -> Dict[str, Any]:
        """Clean cache contents. Returns counts of removed items."""
        removed = {"packages": 0, "metadata": 0, "total": 0}
        if clean_type in (CleanType.ALL, CleanType.PACKAGES):
            pkg_dir = self._cache_dir / "packages"
            if pkg_dir.exists():
                for repo_dir in pkg_dir.iterdir():
                    if repo_dir.is_dir():
                        for f in repo_dir.iterdir():
                            if f.is_file():
                                f.unlink()
                                removed["packages"] += 1
        if clean_type in (CleanType.ALL, CleanType.METADATA, CleanType.DB_CACHE):
            for f in self._cache_dir.iterdir():
                if f.is_file() and f.suffix == ".xml":
                    f.unlink()
                    removed["metadata"] += 1
        removed["total"] = removed["packages"] + removed["metadata"]
        self._metadata_cache.clear()
        self._package_cache.clear()
        self._timestamp = None
        return removed

    def size(self) -> int:
        """Total cache size in bytes."""
        total = 0
        if self._cache_dir.exists():
            for f in self._cache_dir.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        return total


# ---------------------------------------------------------------------------
# Repository Manager
# ---------------------------------------------------------------------------

class RepositoryManager:
    """Manages package repository configurations."""

    def __init__(self, repos_dir: Path) -> None:
        self._repos_dir = repos_dir
        self._repos_dir.mkdir(parents=True, exist_ok=True)
        self._repos: Dict[str, RepoConfig] = {}
        self._load_repos()

    def _load_repos(self) -> None:
        """Load all .repo files from the repos directory."""
        for repo_file in self._repos_dir.glob("*.repo"):
            try:
                config = json.loads(repo_file.read_text(encoding="utf-8"))
                repo = RepoConfig(**config)
                self._repos[repo.repo_id] = repo
            except (json.JSONDecodeError, TypeError, OSError) as exc:
                logger.warning("Failed to load repo file %s: %s", repo_file, exc)

    def _save_repo(self, repo: RepoConfig) -> None:
        """Persist a repo config to disk."""
        repo_file = self._repos_dir / f"{repo.repo_id}.repo"
        try:
            repo_file.write_text(
                json.dumps(
                    {
                        "repo_id": repo.repo_id,
                        "name": repo.name,
                        "baseurl": repo.baseurl,
                        "metalink": repo.metalink,
                        "mirrorlist": repo.mirrorlist,
                        "gpgcheck": repo.gpgcheck,
                        "enabled": repo.enabled,
                        "gpgkey": repo.gpgkey,
                        "sslverify": repo.sslverify,
                        "sslcacert": repo.sslcacert,
                        "sslclientcert": repo.sslclientcert,
                        "sslclientkey": repo.sslclientkey,
                        "metadata_expire": repo.metadata_expire,
                        "priority": repo.priority,
                        "cost": repo.cost,
                        "module_hotfixes": repo.module_hotfixes,
                        "status": repo.status.value,
                        "failovermethod": repo.failovermethod,
                        "max_retries": repo.max_retries,
                        "timeout": repo.timeout,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("Failed to save repo %s: %s", repo.repo_id, exc)

    def add_repo(
        self,
        repo_id: str,
        name: str,
        baseurl: Optional[List[str]] = None,
        gpgcheck: bool = True,
        enabled: bool = True,
        priority: int = 99,
        cost: int = 1000,
        **kwargs: Any,
    ) -> RepoConfig:
        """Add a new repository."""
        if repo_id in self._repos:
            raise ValueError(f"Repository '{repo_id}' already exists")
        repo = RepoConfig(
            repo_id=repo_id,
            name=name,
            baseurl=baseurl or [],
            gpgcheck=gpgcheck,
            enabled=enabled,
            priority=priority,
            cost=cost,
            **{k: v for k, v in kwargs.items() if hasattr(RepoConfig, k)},
        )
        self._repos[repo_id] = repo
        self._save_repo(repo)
        return repo

    def remove_repo(self, repo_id: str) -> bool:
        """Remove a repository."""
        if repo_id not in self._repos:
            return False
        del self._repos[repo_id]
        repo_file = self._repos_dir / f"{repo_id}.repo"
        if repo_file.exists():
            repo_file.unlink()
        return True

    def enable_repo(self, repo_id: str) -> bool:
        """Enable a repository."""
        repo = self._repos.get(repo_id)
        if repo is None:
            return False
        repo.enabled = True
        repo.status = RepoStatus.ENABLED
        self._save_repo(repo)
        return True

    def disable_repo(self, repo_id: str) -> bool:
        """Disable a repository."""
        repo = self._repos.get(repo_id)
        if repo is None:
            return False
        repo.enabled = False
        self._save_repo(repo)
        return True

    def get_repo(self, repo_id: str) -> Optional[RepoConfig]:
        return self._repos.get(repo_id)

    def list_repos(self, enabled_only: bool = False) -> List[RepoConfig]:
        repos = list(self._repos.values())
        if enabled_only:
            repos = [r for r in repos if r.is_active]
        return repos

    def get_active_repos(self) -> List[RepoConfig]:
        return [r for r in self._repos.values() if r.is_active]

    def repo_summary(self) -> Dict[str, Any]:
        """Summary of repository state."""
        all_repos = list(self._repos.values())
        return {
            "total": len(all_repos),
            "enabled": sum(1 for r in all_repos if r.is_active),
            "disabled": sum(1 for r in all_repos if not r.is_active),
            "broken": sum(1 for r in all_repos if r.status == RepoStatus.BROKEN),
        }


# ---------------------------------------------------------------------------
# Dependency Resolver
# ---------------------------------------------------------------------------

class DependencyResolver:
    """Resolves package dependencies with conflict detection."""

    def __init__(self, package_index: Dict[str, List[PackageInfo]]) -> None:
        self._index = package_index  # name -> list of PackageInfo

    def resolve(
        self,
        request: List[Tuple[str, TransactionAction]],
        installed: Dict[str, PackageInfo],
    ) -> DepSolveResult:
        """Resolve dependencies for the given request.

        Parameters
        ----------
        request: List of (package_name, action) tuples.
        installed: Currently installed packages (name -> PackageInfo).

        Returns
        -------
        DepSolveResult with resolved install/update/remove lists.
        """
        result = DepSolveResult()
        to_install: Dict[str, PackageInfo] = {}
        to_update: Dict[str, Tuple[PackageInfo, PackageInfo]] = {}
        to_remove: Dict[str, PackageInfo] = {}

        # Phase 1: Process direct requests
        for pkg_name, action in request:
            if action in (TransactionAction.INSTALL, TransactionAction.UPDATE):
                candidates = self._index.get(pkg_name, [])
                if not candidates:
                    result.skip.append((PackageInfo(nevra=PackageNevra(name=pkg_name)), f"No package '{pkg_name}' found"))
                    continue
                best = max(candidates, key=lambda p: p.nevra)
                if pkg_name in installed:
                    old = installed[pkg_name]
                    if best.nevra.compare_evr(old.nevra) > 0:
                        to_update[pkg_name] = (old, best)
                    else:
                        result.skip.append((best, "Already up-to-date"))
                else:
                    to_install[pkg_name] = best
            elif action in (TransactionAction.REMOVE, TransactionAction.ERASE):
                if pkg_name in installed:
                    to_remove[pkg_name] = installed[pkg_name]
                else:
                    result.skip.append(
                        (PackageInfo(nevra=PackageNevra(name=pkg_name)), f"Package '{pkg_name}' not installed")
                    )
            elif action == TransactionAction.DOWNGRADE:
                candidates = self._index.get(pkg_name, [])
                if not candidates:
                    result.skip.append((PackageInfo(nevra=PackageNevra(name=pkg_name)), f"No package '{pkg_name}' found"))
                    continue
                best = min(candidates, key=lambda p: p.nevra)
                if pkg_name in installed:
                    old = installed[pkg_name]
                    if best.nevra.compare_evr(old.nevra) < 0:
                        to_update[pkg_name] = (old, best)
                    else:
                        result.skip.append((best, "Already at lower version"))
                else:
                    to_install[pkg_name] = best

        # Phase 2: Resolve requires for new installs
        queue = list(to_install.keys())
        resolved: Set[str] = set()
        while queue:
            name = queue.pop(0)
            if name in resolved:
                continue
            resolved.add(name)
            candidates = self._index.get(name, [])
            if not candidates:
                continue
            best = max(candidates, key=lambda p: p.nevra)
            for req in best.requires:
                req_name = req.split()[0] if " " in req else req.split("<")[0].split(">")[0].split("=")[0]
                if req_name and req_name not in installed and req_name not in to_install:
                    req_candidates = self._index.get(req_name, [])
                    if req_candidates:
                        req_best = max(req_candidates, key=lambda p: p.nevra)
                        if req_name not in to_install:
                            to_install[req_name] = req_best
                            queue.append(req_name)

        # Phase 3: Check conflicts
        for pkg_name, pkg in to_install.items():
            for conflict_str in pkg.conflicts:
                conflict_name = conflict_str.split()[0] if " " in conflict_str else conflict_str.split("<")[0].split(">")[0]
                if conflict_name in installed:
                    result.conflicts.append((pkg, installed[conflict_name]))
                if conflict_name in to_install and conflict_name != pkg_name:
                    result.conflicts.append((pkg, to_install[conflict_name]))

        # Phase 4: Check obsoletes
        for pkg_name, pkg in to_install.items():
            for obsolete_str in pkg.obsoletes:
                obs_name = obsolete_str.split()[0] if " " in obsolete_str else obsolete_str.split("<")[0].split(">")[0]
                if obs_name in installed and obs_name not in to_remove:
                    to_remove[obs_name] = installed[obs_name]
                    result.obsoleted.append((pkg, installed[obs_name]))

        # Build final result
        result.install = list(to_install.values())
        result.update = list(to_update.values())
        result.remove = list(to_remove.values())
        return result

    def check_requires_satisfied(
        self, pkg: PackageInfo, installed: Dict[str, PackageInfo]
    ) -> Tuple[bool, List[str]]:
        """Check if all requirements of a package are satisfied."""
        unsatisfied: List[str] = []
        for req in pkg.requires:
            req_name = req.split()[0] if " " in req else req.split("<")[0].split(">")[0].split("=")[0]
            if req_name and req_name not in installed:
                unsatisfied.append(req_name)
        return len(unsatisfied) == 0, unsatisfied

    def find_best_candidate(self, name: str) -> Optional[PackageInfo]:
        """Find the best (highest EVR) candidate for a package name."""
        candidates = self._index.get(name, [])
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.nevra)


# ---------------------------------------------------------------------------
# History Manager
# ---------------------------------------------------------------------------

class HistoryManager:
    """Manages transaction history with rollback support."""

    def __init__(self, history_dir: Path) -> None:
        self._history_dir = history_dir
        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._records: Dict[int, HistoryRecord] = {}
        self._next_tid = 1
        self._load_history()

    def _load_history(self) -> None:
        """Load history records from disk."""
        for hist_file in self._history_dir.glob("*.json"):
            try:
                data = json.loads(hist_file.read_text(encoding="utf-8"))
                record = HistoryRecord(**data)
                self._records[record.tid] = record
                if record.tid >= self._next_tid:
                    self._next_tid = record.tid + 1
            except (json.JSONDecodeError, TypeError, OSError) as exc:
                logger.warning("Failed to load history file %s: %s", hist_file, exc)

    def _save_record(self, record: HistoryRecord) -> None:
        """Save a history record to disk."""
        hist_file = self._history_dir / f"{record.tid:08d}.json"
        try:
            hist_file.write_text(
                json.dumps(
                    {
                        "tid": record.tid,
                        "timestamp": record.timestamp,
                        "cmdline": record.cmdline,
                        "return_code": record.return_code,
                        "rpmdb_version": record.rpmdb_version,
                        "items": record.items,
                        "state": record.state.value,
                        "altered": record.altered,
                        "runtime": record.runtime,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("Failed to save history record %d: %s", record.tid, exc)

    def new_tid(self) -> int:
        """Allocate a new transaction ID."""
        tid = self._next_tid
        self._next_tid += 1
        return tid

    def record_transaction(
        self,
        tid: int,
        cmdline: str,
        items: List[TransactionItem],
        return_code: int = 0,
        runtime: float = 0.0,
    ) -> HistoryRecord:
        """Record a completed transaction."""
        history_items = []
        for item in items:
            history_items.append(
                {
                    "action": item.action.value,
                    "name": item.package.name,
                    "nevra": item.package.nevra.nevra,
                    "old_nevra": item.old_package.nevra.nevra if item.old_package else "",
                }
            )
        record = HistoryRecord(
            tid=tid,
            timestamp=datetime.now().isoformat(),
            cmdline=cmdline,
            return_code=return_code,
            items=history_items,
            state=TransactionState.COMMITTED if return_code == 0 else TransactionState.FAILED,
            altered=len(items),
            runtime=runtime,
        )
        self._records[tid] = record
        self._save_record(record)
        return record

    def get_record(self, tid: int) -> Optional[HistoryRecord]:
        return self._records.get(tid)

    def list_history(
        self,
        limit: int = 20,
        before: Optional[int] = None,
        after: Optional[int] = None,
    ) -> List[HistoryRecord]:
        """List history records with optional filtering."""
        records = sorted(self._records.values(), key=lambda r: r.tid, reverse=True)
        if before is not None:
            records = [r for r in records if r.tid < before]
        if after is not None:
            records = [r for r in records if r.tid > after]
        return records[:limit]

    def user_history(self, limit: int = 50) -> List[HistoryRecord]:
        """Get user-initiated transactions."""
        records = sorted(self._records.values(), key=lambda r: r.tid, reverse=True)
        return [r for r in records if r.cmdline and "update" in r.cmdline.lower()][:limit]

    def undo_transaction(
        self, tid: int, installed: Dict[str, PackageInfo]
    ) -> Tuple[List[TransactionItem], List[str]]:
        """Generate undo items for a transaction. Returns (items, errors)."""
        record = self._records.get(tid)
        if record is None:
            return [], [f"Transaction {tid} not found"]
        undo_items: List[TransactionItem] = []
        errors: List[str] = []
        for item_data in record.items:
            action = item_data.get("action", "")
            name = item_data.get("name", "")
            nevra_str = item_data.get("nevra", "")
            old_nevra_str = item_data.get("old_nevra", "")

            if action == "install" and name in installed:
                undo_items.append(
                    TransactionItem(
                        action=TransactionAction.REMOVE,
                        package=installed[name],
                        reason=MarkReason.USER,
                    )
                )
            elif action == "remove" and old_nevra_str:
                old_nevra = PackageNevra.from_string(old_nevra_str)
                old_pkg = PackageInfo(nevra=old_nevra)
                undo_items.append(
                    TransactionItem(
                        action=TransactionAction.INSTALL,
                        package=old_pkg,
                        reason=MarkReason.USER,
                    )
                )
            elif action == "update" and old_nevra_str:
                old_nevra = PackageNevra.from_string(old_nevra_str)
                old_pkg = PackageInfo(nevra=old_nevra)
                if name in installed:
                    undo_items.append(
                        TransactionItem(
                            action=TransactionAction.DOWNGRADE,
                            package=old_pkg,
                            old_package=installed[name],
                            reason=MarkReason.USER,
                        )
                    )
            else:
                errors.append(f"Cannot undo {action} for {name}")
        return undo_items, errors

    def rollback(
        self,
        tid: int,
        installed: Dict[str, PackageInfo],
    ) -> Tuple[List[TransactionItem], List[str]]:
        """Rollback a transaction (alias for undo_transaction)."""
        return self.undo_transaction(tid, installed)


# ---------------------------------------------------------------------------
# Group Manager
# ---------------------------------------------------------------------------

class GroupManager:
    """Manages package groups."""

    def __init__(self, groups_dir: Path) -> None:
        self._groups_dir = groups_dir
        self._groups_dir.mkdir(parents=True, exist_ok=True)
        self._groups: Dict[str, PackageGroup] = {}
        self._installed_groups: Set[str] = set()
        self._load_groups()

    def _load_groups(self) -> None:
        for gf in self._groups_dir.glob("*.json"):
            try:
                data = json.loads(gf.read_text(encoding="utf-8"))
                group = PackageGroup(**data)
                self._groups[group.group_id] = group
            except (json.JSONDecodeError, TypeError, OSError):
                pass
        installed_file = self._groups_dir / "_installed.json"
        if installed_file.exists():
            try:
                self._installed_groups = set(
                    json.loads(installed_file.read_text(encoding="utf-8"))
                )
            except (json.JSONDecodeError, OSError):
                pass

    def _save_groups(self) -> None:
        for gid, group in self._groups.items():
            gf = self._groups_dir / f"{gid}.json"
            try:
                gf.write_text(
                    json.dumps(
                        {
                            "group_id": group.group_id,
                            "name": group.name,
                            "description": group.description,
                            "user_visible": group.user_visible,
                            "packages": group.packages,
                            "default_packages": group.default_packages,
                            "optional_packages": group.optional_packages,
                            "conditional_packages": group.conditional_packages,
                            "langonly": group.langonly,
                            "install": group.install,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except OSError:
                pass
        installed_file = self._groups_dir / "_installed.json"
        try:
            installed_file.write_text(
                json.dumps(list(self._installed_groups)),
                encoding="utf-8",
            )
        except OSError:
            pass

    def add_group(self, group: PackageGroup) -> None:
        self._groups[group.group_id] = group
        self._save_groups()

    def remove_group(self, group_id: str) -> bool:
        if group_id not in self._groups:
            return False
        del self._groups[group_id]
        self._installed_groups.discard(group_id)
        self._save_groups()
        return True

    def get_group(self, group_id: str) -> Optional[PackageGroup]:
        return self._groups.get(group_id)

    def list_groups(self, hidden: bool = False) -> List[PackageGroup]:
        groups = list(self._groups.values())
        if not hidden:
            groups = [g for g in groups if g.user_visible]
        return groups

    def mark_group_installed(self, group_id: str) -> bool:
        if group_id not in self._groups:
            return False
        self._installed_groups.add(group_id)
        self._groups[group_id].install = True
        self._save_groups()
        return True

    def mark_group_removed(self, group_id: str) -> bool:
        if group_id not in self._groups:
            return False
        self._installed_groups.discard(group_id)
        self._groups[group_id].install = False
        self._save_groups()
        return True

    def is_group_installed(self, group_id: str) -> bool:
        return group_id in self._installed_groups

    def get_group_packages(self, group_id: str) -> List[str]:
        group = self._groups.get(group_id)
        if group is None:
            return []
        return group.all_packages

    def search_groups(self, query: str) -> List[PackageGroup]:
        query_lower = query.lower()
        return [
            g for g in self._groups.values()
            if query_lower in g.name.lower()
            or query_lower in g.group_id.lower()
            or query_lower in g.description.lower()
        ]


# ---------------------------------------------------------------------------
# Plugin Manager
# ---------------------------------------------------------------------------

class PluginManager:
    """Manages Yum manager plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, YumPlugin] = {}
        self._hook_registry: Dict[PluginHook, List[str]] = {
            hook: [] for hook in PluginHook
        }

    def register_plugin(self, plugin: YumPlugin) -> None:
        self._plugins[plugin.name] = plugin
        self._hook_registry[plugin.hook].append(plugin.name)

    def unregister_plugin(self, name: str) -> bool:
        if name not in self._plugins:
            return False
        plugin = self._plugins.pop(name)
        self._hook_registry[plugin.hook] = [
            n for n in self._hook_registry[plugin.hook] if n != name
        ]
        return True

    def get_plugin(self, name: str) -> Optional[YumPlugin]:
        return self._plugins.get(name)

    def list_plugins(self) -> List[Dict[str, str]]:
        return [
            {"name": p.name, "version": p.version, "hook": p.hook.value}
            for p in self._plugins.values()
        ]

    def run_hook(
        self, hook: PluginHook, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run all plugins registered for a hook point."""
        current_context = context.copy()
        for plugin_name in self._hook_registry.get(hook, []):
            plugin = self._plugins.get(plugin_name)
            if plugin is not None:
                try:
                    result = plugin.execute(current_context)
                    if result:
                        current_context.update(result)
                except Exception as exc:
                    logger.error(
                        "Plugin '%s' failed on hook %s: %s",
                        plugin_name, hook.value, exc,
                    )
        return current_context


# ---------------------------------------------------------------------------
# Security Manager
# ---------------------------------------------------------------------------

class SecurityManager:
    """Handles security updates and CVE advisory tracking."""

    def __init__(self) -> None:
        self._advisories: Dict[str, UpdateInfo] = {}
        self._cve_map: Dict[str, List[str]] = {}  # cve_id -> [package_names]

    def add_advisory(self, advisory: UpdateInfo) -> None:
        self._advisories[advisory.update_id] = advisory
        for pkg_name in advisory.pkg_names:
            self._cve_map.setdefault(pkg_name, []).append(advisory.update_id)

    def get_advisory(self, update_id: str) -> Optional[UpdateInfo]:
        return self._advisories.get(update_id)

    def list_advisories(
        self,
        advisory_type: Optional[UpdateInfoType] = None,
        severity: Optional[str] = None,
    ) -> List[UpdateInfo]:
        advisories = list(self._advisories.values())
        if advisory_type is not None:
            advisories = [a for a in advisories if a.update_type == advisory_type]
        if severity is not None:
            advisories = [a for a in advisories if a.severity == severity]
        return advisories

    def security_updates(
        self, installed: Dict[str, PackageInfo], available: Dict[str, List[PackageInfo]]
    ) -> List[Tuple[PackageInfo, List[UpdateInfo]]]:
        """Find packages with security updates available."""
        results: List[Tuple[PackageInfo, List[UpdateInfo]]] = []
        for pkg_name, pkg_info in installed.items():
            pkg_advisories = self._cve_map.get(pkg_name, [])
            security_advisories = [
                self._advisories[aid]
                for aid in pkg_advisories
                if aid in self._advisories
                and self._advisories[aid].update_type == UpdateInfoType.SECURITY
            ]
            if security_advisories and pkg_name in available:
                candidates = available[pkg_name]
                newer = [
                    c for c in candidates
                    if c.nevra.compare_evr(pkg_info.nevra) > 0
                ]
                if newer:
                    results.append((pkg_info, security_advisories))
        return results

    def get_cves_for_package(self, pkg_name: str) -> List[str]:
        """Get CVE IDs affecting a package."""
        advisory_ids = self._cve_map.get(pkg_name, [])
        cves: List[str] = []
        for aid in advisory_ids:
            adv = self._advisories.get(aid)
            if adv:
                cves.extend(adv.reference_ids)
        return list(set(cves))


# ---------------------------------------------------------------------------
# Main Yum Manager (Facade)
# ---------------------------------------------------------------------------

class YumManager:
    """Comprehensive Yum-compatible package manager for UmerOS.

    Facade class that coordinates RepositoryManager, DependencyResolver,
    HistoryManager, GroupManager, PluginManager, CacheManager, and
    SecurityManager to provide full Yum functionality.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        repos_dir: Optional[Path] = None,
        history_dir: Optional[Path] = None,
        groups_dir: Optional[Path] = None,
    ) -> None:
        self._base_dir = base_dir or Path("/var/lib/umeros/yum")
        self._installed: Dict[str, PackageInfo] = {}
        self._available: Dict[str, List[PackageInfo]] = {}  # name -> candidates
        self._package_index: Dict[str, List[PackageInfo]] = {}  # full index

        # Sub-managers
        self._cache = CacheManager(cache_dir or self._base_dir / "cache")
        self._repos = RepositoryManager(repos_dir or self._base_dir / "repos")
        self._resolver = DependencyResolver(self._available)
        self._history = HistoryManager(history_dir or self._base_dir / "history")
        self._groups = GroupManager(groups_dir or self._base_dir / "groups")
        self._plugins = PluginManager()
        self._security = SecurityManager()

        self._transaction_count = 0

    # -- Public accessors --------------------------------------------------

    @property
    def cache(self) -> CacheManager:
        return self._cache

    @property
    def repos(self) -> RepositoryManager:
        return self._repos

    @property
    def history(self) -> HistoryManager:
        return self._history

    @property
    def groups(self) -> GroupManager:
        return self._groups

    @property
    def plugins(self) -> PluginManager:
        return self._plugins

    @property
    def security(self) -> SecurityManager:
        return self._security

    @property
    def installed_packages(self) -> Dict[str, PackageInfo]:
        return dict(self._installed)

    @property
    def available_packages(self) -> Dict[str, List[PackageInfo]]:
        return dict(self._available)

    # -- Package index management ------------------------------------------

    def register_package(self, pkg: PackageInfo) -> None:
        """Register a package in the available index."""
        self._available.setdefault(pkg.name, []).append(pkg)
        self._package_index.setdefault(pkg.name, []).append(pkg)

    def register_packages(self, packages: List[PackageInfo]) -> None:
        """Register multiple packages."""
        for pkg in packages:
            self.register_package(pkg)

    def mark_installed(self, pkg: PackageInfo) -> None:
        """Mark a package as installed."""
        self._installed[pkg.name] = pkg

    def mark_removed(self, pkg_name: str) -> Optional[PackageInfo]:
        """Mark a package as removed. Returns the removed package info."""
        return self._installed.pop(pkg_name, None)

    # -- Core package operations -------------------------------------------

    def install(
        self,
        packages: List[str],
        from_repo: Optional[str] = None,
        skip_broken: bool = False,
        assume_yes: bool = False,
    ) -> TransactionResult:
        """Install one or more packages."""
        tid = self._history.new_tid()
        start = time.monotonic()

        request = [(p, TransactionAction.INSTALL) for p in packages]
        deps_result = self._resolver.resolve(request, self._installed)

        if not deps_result.success and not skip_broken:
            return TransactionResult(
                tid=tid,
                timestamp=datetime.now().isoformat(),
                action="install",
                state=TransactionState.FAILED,
                errors=[
                    f"Conflict: {c[0].name} conflicts with {c[1].name}"
                    for c in deps_result.conflicts
                ]
                + [f"Skipped: {s[1]}" for s in deps_result.skip],
            )

        items: List[TransactionItem] = []
        for pkg in deps_result.install:
            items.append(
                TransactionItem(
                    action=TransactionAction.INSTALL,
                    package=pkg,
                    reason=MarkReason.USER,
                )
            )
        for old, new in deps_result.update:
            items.append(
                TransactionItem(
                    action=TransactionAction.UPDATE,
                    package=new,
                    old_package=old,
                    reason=MarkReason.USER,
                )
            )
        for pkg in deps_result.remove:
            items.append(
                TransactionItem(
                    action=TransactionAction.REMOVE,
                    package=pkg,
                    reason=MarkReason.DEPENDENCY,
                )
            )

        # Pre-transaction hook
        ctx = self._plugins.run_hook(
            PluginHook.PRE_TRANSACTION,
            {"action": "install", "items": items, "assume_yes": assume_yes},
        )
        if ctx.get("abort"):
            return TransactionResult(
                tid=tid,
                timestamp=datetime.now().isoformat(),
                action="install",
                state=TransactionState.FAILED,
                errors=["Aborted by plugin"],
            )

        # Execute
        for item in items:
            if item.action == TransactionAction.INSTALL:
                self._installed[item.package.name] = item.package
                item.state = TransactionState.COMMITTED
                self._plugins.run_hook(
                    PluginHook.POST_INSTALL, {"package": item.package}
                )
            elif item.action == TransactionAction.UPDATE:
                self._installed[item.package.name] = item.package
                item.state = TransactionState.COMMITTED
                self._plugins.run_hook(
                    PluginHook.POST_UPDATE, {"package": item.package, "old": item.old_package}
                )
            elif item.action == TransactionAction.REMOVE:
                self._installed.pop(item.package.name, None)
                item.state = TransactionState.COMMITTED
                self._plugins.run_hook(
                    PluginHook.POST_REMOVE, {"package": item.package}
                )

        # Post-transaction hook
        self._plugins.run_hook(PluginHook.POST_TRANSACTION, {"items": items})

        elapsed = time.monotonic() - start
        return_code = 0 if deps_result.success else 1 if skip_broken else 2
        result = TransactionResult(
            tid=tid,
            timestamp=datetime.now().isoformat(),
            action="install",
            state=TransactionState.COMMITTED if return_code == 0 else TransactionState.FAILED,
            items=items,
            return_code=return_code,
            runtime=elapsed,
        )
        self._history.record_transaction(
            tid=tid,
            cmdline=f"install {' '.join(packages)}",
            items=items,
            return_code=return_code,
            runtime=elapsed,
        )
        return result

    def update(
        self,
        packages: Optional[List[str]] = None,
        security_only: bool = False,
    ) -> TransactionResult:
        """Update packages. If packages is None, update all."""
        tid = self._history.new_tid()
        start = time.monotonic()

        if packages is None:
            packages = list(self._installed.keys())

        request = [(p, TransactionAction.UPDATE) for p in packages]
        deps_result = self._resolver.resolve(request, self._installed)

        items: List[TransactionItem] = []
        for old, new in deps_result.update:
            items.append(
                TransactionItem(
                    action=TransactionAction.UPDATE,
                    package=new,
                    old_package=old,
                    reason=MarkReason.USER,
                )
            )
        for pkg in deps_result.install:
            items.append(
                TransactionItem(
                    action=TransactionAction.INSTALL,
                    package=pkg,
                    reason=MarkReason.DEPENDENCY,
                )
            )

        # Execute
        for item in items:
            if item.action in (TransactionAction.UPDATE, TransactionAction.INSTALL):
                self._installed[item.package.name] = item.package
                item.state = TransactionState.COMMITTED

        elapsed = time.monotonic() - start
        result = TransactionResult(
            tid=tid,
            timestamp=datetime.now().isoformat(),
            action="update",
            state=TransactionState.COMMITTED,
            items=items,
            return_code=0,
            runtime=elapsed,
        )
        self._history.record_transaction(
            tid=tid,
            cmdline=f"update {' '.join(packages) if packages else ''}",
            items=items,
            runtime=elapsed,
        )
        return result

    def remove(
        self,
        packages: List[str],
        remove_deps: bool = False,
    ) -> TransactionResult:
        """Remove one or more packages."""
        tid = self._history.new_tid()
        start = time.monotonic()

        request = [(p, TransactionAction.REMOVE) for p in packages]
        deps_result = self._resolver.resolve(request, self._installed)

        items: List[TransactionItem] = []
        for pkg in deps_result.remove:
            items.append(
                TransactionItem(
                    action=TransactionAction.REMOVE,
                    package=pkg,
                    reason=MarkReason.USER,
                )
            )

        for item in items:
            self._installed.pop(item.package.name, None)
            item.state = TransactionState.COMMITTED

        elapsed = time.monotonic() - start
        result = TransactionResult(
            tid=tid,
            timestamp=datetime.now().isoformat(),
            action="remove",
            state=TransactionState.COMMITTED,
            items=items,
            return_code=0,
            runtime=elapsed,
        )
        self._history.record_transaction(
            tid=tid,
            cmdline=f"remove {' '.join(packages)}",
            items=items,
            runtime=elapsed,
        )
        return result

    def downgrade(self, packages: List[str]) -> TransactionResult:
        """Downgrade packages to the lowest available version."""
        tid = self._history.new_tid()
        start = time.monotonic()

        request = [(p, TransactionAction.DOWNGRADE) for p in packages]
        deps_result = self._resolver.resolve(request, self._installed)

        items: List[TransactionItem] = []
        for old, new in deps_result.update:
            items.append(
                TransactionItem(
                    action=TransactionAction.DOWNGRADE,
                    package=new,
                    old_package=old,
                    reason=MarkReason.USER,
                )
            )

        for item in items:
            self._installed[item.package.name] = item.package
            item.state = TransactionState.COMMITTED

        elapsed = time.monotonic() - start
        result = TransactionResult(
            tid=tid,
            timestamp=datetime.now().isoformat(),
            action="downgrade",
            state=TransactionState.COMMITTED if items else TransactionState.FAILED,
            items=items,
            return_code=0 if items else 1,
            runtime=elapsed,
        )
        self._history.record_transaction(
            tid=tid,
            cmdline=f"downgrade {' '.join(packages)}",
            items=items,
            return_code=result.return_code,
            runtime=elapsed,
        )
        return result

    def reinstall(self, packages: List[str]) -> TransactionResult:
        """Reinstall packages (same version)."""
        tid = self._history.new_tid()
        start = time.monotonic()
        items: List[TransactionItem] = []

        for pkg_name in packages:
            pkg = self._installed.get(pkg_name)
            if pkg is None:
                items.append(
                    TransactionItem(
                        action=TransactionAction.REINSTALL,
                        package=PackageInfo(nevra=PackageNevra(name=pkg_name)),
                        state=TransactionState.FAILED,
                        error=f"Package '{pkg_name}' not installed",
                    )
                )
                continue
            items.append(
                TransactionItem(
                    action=TransactionAction.REINSTALL,
                    package=pkg,
                    reason=MarkReason.USER,
                    state=TransactionState.COMMITTED,
                )
            )

        elapsed = time.monotonic() - start
        success_count = sum(1 for i in items if i.state == TransactionState.COMMITTED)
        result = TransactionResult(
            tid=tid,
            timestamp=datetime.now().isoformat(),
            action="reinstall",
            state=TransactionState.COMMITTED if success_count == len(packages) else TransactionState.FAILED,
            items=items,
            return_code=0 if success_count == len(packages) else 1,
            runtime=elapsed,
        )
        self._history.record_transaction(
            tid=tid,
            cmdline=f"reinstall {' '.join(packages)}",
            items=items,
            return_code=result.return_code,
            runtime=elapsed,
        )
        return result

    # -- Query operations --------------------------------------------------

    def list_installed(self, query: Optional[str] = None) -> List[PackageInfo]:
        """List installed packages, optionally filtered by name glob."""
        pkgs = list(self._installed.values())
        if query:
            pattern = re.compile(query.replace("*", ".*"), re.IGNORECASE)
            pkgs = [p for p in pkgs if pattern.search(p.name)]
        return sorted(pkgs, key=lambda p: p.name)

    def list_available(
        self, repo_id: Optional[str] = None, query: Optional[str] = None
    ) -> List[PackageInfo]:
        """List available packages."""
        pkgs: List[PackageInfo] = []
        for candidates in self._available.values():
            pkgs.extend(candidates)
        if repo_id:
            pkgs = [p for p in pkgs if p.repo_id == repo_id]
        if query:
            pattern = re.compile(query.replace("*", ".*"), re.IGNORECASE)
            pkgs = [p for p in pkgs if pattern.search(p.name)]
        return sorted(pkgs, key=lambda p: (p.name, p.nevra))

    def list_updates(self, security_only: bool = False) -> List[Tuple[PackageInfo, PackageInfo]]:
        """List available updates (installed -> available)."""
        updates: List[Tuple[PackageInfo, PackageInfo]] = []
        for pkg_name, installed_pkg in self._installed.items():
            candidates = self._available.get(pkg_name, [])
            newer = [
                c for c in candidates
                if c.nevra.compare_evr(installed_pkg.nevra) > 0
            ]
            if newer:
                best = max(newer, key=lambda p: p.nevra)
                updates.append((installed_pkg, best))
        return sorted(updates, key=lambda x: x[0].name)

    def check_update(self) -> List[Tuple[PackageInfo, PackageInfo]]:
        """Check for available updates (same as list_updates)."""
        return self.list_updates()

    def search(self, query: str) -> List[PackageInfo]:
        """Search packages by name, summary, or description."""
        pattern = re.compile(query, re.IGNORECASE)
        results: List[PackageInfo] = []
        seen: Set[str] = set()
        for candidates in self._available.values():
            for pkg in candidates:
                if pkg.name in seen:
                    continue
                if (
                    pattern.search(pkg.name)
                    or pattern.search(pkg.summary)
                    or pattern.search(pkg.description)
                ):
                    results.append(pkg)
                    seen.add(pkg.name)
        return sorted(results, key=lambda p: p.name)

    def info(self, package_name: str) -> Optional[PackageInfo]:
        """Get detailed info for a package."""
        # Check installed first
        if package_name in self._installed:
            return self._installed[package_name]
        # Check available
        candidates = self._available.get(package_name, [])
        if candidates:
            return max(candidates, key=lambda p: p.nevra)
        return None

    def provides(self, capability: str) -> List[PackageInfo]:
        """Find packages that provide a capability."""
        results: List[PackageInfo] = []
        for candidates in self._available.values():
            for pkg in candidates:
                if any(capability in prov for prov in pkg.provides):
                    results.append(pkg)
                    break
        return results

    def whatrequires(self, capability: str) -> List[PackageInfo]:
        """Find installed packages that require a capability."""
        results: List[PackageInfo] = []
        for pkg in self._installed.values():
            if any(capability in req for req in pkg.requires):
                results.append(pkg)
        return results

    def whatprovides(self, capability: str) -> List[PackageInfo]:
        """Alias for provides()."""
        return self.provides(capability)

    # -- Group operations --------------------------------------------------

    def group_install(self, group_id: str) -> TransactionResult:
        """Install all packages in a group."""
        group = self._groups.get_group(group_id)
        if group is None:
            tid = self._history.new_tid()
            return TransactionResult(
                tid=tid,
                timestamp=datetime.now().isoformat(),
                action="group_install",
                state=TransactionState.FAILED,
                errors=[f"Group '{group_id}' not found"],
            )
        pkgs = group.all_packages
        self._groups.mark_group_installed(group_id)
        return self.install(pkgs)

    def group_remove(self, group_id: str) -> TransactionResult:
        """Remove all packages in a group."""
        group = self._groups.get_group(group_id)
        if group is None:
            tid = self._history.new_tid()
            return TransactionResult(
                tid=tid,
                timestamp=datetime.now().isoformat(),
                action="group_remove",
                state=TransactionState.FAILED,
                errors=[f"Group '{group_id}' not found"],
            )
        pkgs = [p for p in group.all_packages if p in self._installed]
        self._groups.mark_group_removed(group_id)
        return self.remove(pkgs) if pkgs else TransactionResult(
            tid=self._history.new_tid(),
            timestamp=datetime.now().isoformat(),
            action="group_remove",
            state=TransactionState.COMMITTED,
        )

    def group_list(self, hidden: bool = False) -> List[PackageGroup]:
        return self._groups.list_groups(hidden=hidden)

    def group_info(self, group_id: str) -> Optional[PackageGroup]:
        return self._groups.get_group(group_id)

    def group_summary(self) -> Dict[str, Any]:
        all_groups = self._groups.list_groups(hidden=True)
        return {
            "total": len(all_groups),
            "installed": sum(1 for g in all_groups if g.install),
        }

    # -- History operations ------------------------------------------------

    def history_list(self, limit: int = 20) -> List[HistoryRecord]:
        return self._history.list_history(limit=limit)

    def history_info(self, tid: int) -> Optional[HistoryRecord]:
        return self._history.get_record(tid)

    def history_undo(self, tid: int) -> TransactionResult:
        """Undo a specific transaction."""
        undo_items, errors = self._history.undo_transaction(tid, self._installed)
        if errors and not undo_items:
            return TransactionResult(
                tid=self._history.new_tid(),
                timestamp=datetime.now().isoformat(),
                action="history_undo",
                state=TransactionState.FAILED,
                errors=errors,
            )

        for item in undo_items:
            if item.action == TransactionAction.REMOVE:
                self._installed.pop(item.package.name, None)
            elif item.action == TransactionAction.INSTALL:
                self._installed[item.package.name] = item.package
            elif item.action == TransactionAction.DOWNGRADE:
                self._installed[item.package.name] = item.package
            item.state = TransactionState.COMMITTED

        result = TransactionResult(
            tid=self._history.new_tid(),
            timestamp=datetime.now().isoformat(),
            action="history_undo",
            state=TransactionState.COMMITTED if not errors else TransactionState.FAILED,
            items=undo_items,
            return_code=0 if not errors else 1,
            errors=errors,
        )
        return result

    def history_rollback(self, tid: int) -> TransactionResult:
        """Rollback to before a specific transaction."""
        return self.history_undo(tid)

    # -- Security operations -----------------------------------------------

    def security_update_list(self) -> List[Tuple[PackageInfo, List[UpdateInfo]]]:
        """List packages with security updates."""
        return self._security.security_updates(self._installed, self._available)

    def updateinfo(
        self, package_name: Optional[str] = None
    ) -> List[UpdateInfo]:
        """List security advisories."""
        if package_name:
            adv_ids = self._security._cve_map.get(package_name, [])
            return [
                self._security._advisories[aid]
                for aid in adv_ids
                if aid in self._security._advisories
            ]
        return self._security.list_advisories()

    def cve_list(self, package_name: str) -> List[str]:
        """List CVEs for a package."""
        return self._security.get_cves_for_package(package_name)

    # -- Cache operations --------------------------------------------------

    def clean_cache(self, clean_type: CleanType = CleanType.ALL) -> Dict[str, Any]:
        """Clean package cache."""
        return self._cache.clean(clean_type)

    def refresh_metadata(self, repo_id: Optional[str] = None) -> None:
        """Refresh repository metadata."""
        repos = [repo_id] if repo_id else [
            r.repo_id for r in self._repos.get_active_repos()
        ]
        for rid in repos:
            metadata = {"last_refresh": datetime.now().isoformat(), "repo_id": rid}
            self._cache.save_metadata(rid, metadata)

    def cache_status(self) -> Dict[str, Any]:
        """Get cache status information."""
        return {
            "size_bytes": self._cache.size(),
            "is_fresh": self._cache.is_fresh(),
            "cache_dir": str(self._cache.cache_dir),
        }

    # -- Autoremove --------------------------------------------------------

    def autoremove(self) -> TransactionResult:
        """Remove unused dependencies."""
        # Find packages installed as dependencies that are no longer required
        orphans: List[str] = []
        for pkg_name, pkg in self._installed.items():
            if pkg.state != PackageState.INSTALLED:
                continue
            # Check if any installed package requires this one
            required_by = [
                other
                for other_name, other in self._installed.items()
                if other_name != pkg_name
                and any(pkg_name in req for req in other.requires)
            ]
            if not required_by:
                orphans.append(pkg_name)

        if not orphans:
            tid = self._history.new_tid()
            return TransactionResult(
                tid=tid,
                timestamp=datetime.now().isoformat(),
                action="autoremove",
                state=TransactionState.COMMITTED,
            )

        return self.remove(orphans)

    # -- Local install -----------------------------------------------------

    def local_install(self, package_path: str) -> TransactionResult:
        """Install a local RPM-like package file."""
        path = Path(package_path)
        if not path.exists():
            tid = self._history.new_tid()
            return TransactionResult(
                tid=tid,
                timestamp=datetime.now().isoformat(),
                action="local_install",
                state=TransactionState.FAILED,
                errors=[f"File not found: {package_path}"],
            )

        # Create a virtual package from the filename
        stem = path.stem
        nevra = PackageNevra.from_string(stem)
        pkg = PackageInfo(
            nevra=nevra,
            summary=f"Local package: {stem}",
            state=PackageState.AVAILABLE,
        )

        tid = self._history.new_tid()
        start = time.monotonic()

        self._installed[pkg.name] = pkg
        items = [
            TransactionItem(
                action=TransactionAction.INSTALL,
                package=pkg,
                reason=MarkReason.LOCAL,
                state=TransactionState.COMMITTED,
            )
        ]

        elapsed = time.monotonic() - start
        result = TransactionResult(
            tid=tid,
            timestamp=datetime.now().isoformat(),
            action="local_install",
            state=TransactionState.COMMITTED,
            items=items,
            return_code=0,
            runtime=elapsed,
        )
        self._history.record_transaction(
            tid=tid,
            cmdline=f"localinstall {package_path}",
            items=items,
            runtime=elapsed,
        )
        return result

    # -- Distribution sync -------------------------------------------------

    def distro_sync(self, packages: Optional[List[str]] = None) -> TransactionResult:
        """Sync installed packages to latest available versions."""
        if packages is None:
            packages = list(self._installed.keys())
        return self.update(packages)

    # -- Package statistics ------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Get package statistics."""
        return {
            "installed": len(self._installed),
            "available_repos": sum(
                len(c) for c in self._available.values()
            ),
            "updates": len(self.list_updates()),
            "security_updates": len(self.security_update_list()),
            "groups": len(self._groups.list_groups(hidden=True)),
            "repos": self._repos.repo_summary(),
            "cache_size": self._cache.size(),
            "history_transactions": len(self._history.list_history(limit=99999)),
        }

    # -- Shell mode --------------------------------------------------------

    def shell_execute(self, commands: List[str]) -> List[str]:
        """Execute a series of shell-mode commands.

        Supports: install, update, remove, list, info, search, clean,
        repo enable/disable, group list/install/remove, history list/undo,
        check-update, stats.
        """
        outputs: List[str] = []
        for cmd_line in commands:
            parts = cmd_line.strip().split()
            if not parts:
                continue
            cmd = parts[0].lower()
            args = parts[1:]

            if cmd == "install" and args:
                result = self.install(args)
                outputs.append(
                    f"Install: {len(result.items)} items, "
                    f"{'OK' if result.success else 'FAILED'}"
                )
            elif cmd == "update":
                pkgs = args if args else None
                result = self.update(pkgs)
                outputs.append(
                    f"Update: {len(result.items)} items, "
                    f"{'OK' if result.success else 'FAILED'}"
                )
            elif cmd == "remove" and args:
                result = self.remove(args)
                outputs.append(
                    f"Remove: {len(result.items)} items, "
                    f"{'OK' if result.success else 'FAILED'}"
                )
            elif cmd == "list":
                pkgs = self.list_installed()
                for p in pkgs:
                    outputs.append(f"  {p.nevra.nevra}")
            elif cmd == "info" and args:
                pkg = self.info(args[0])
                if pkg:
                    outputs.append(f"  Name: {pkg.name}")
                    outputs.append(f"  Version: {pkg.nevra.nevra}")
                    outputs.append(f"  Summary: {pkg.summary}")
                else:
                    outputs.append(f"  Package '{args[0]}' not found")
            elif cmd == "search" and args:
                results = self.search(" ".join(args))
                for p in results:
                    outputs.append(f"  {p.nevra.nevra}: {p.summary}")
            elif cmd == "clean":
                ct = CleanType.ALL
                if args:
                    try:
                        ct = CleanType(args[0])
                    except ValueError:
                        ct = CleanType.ALL
                removed = self.clean_cache(ct)
                outputs.append(f"Cleaned: {removed['total']} items")
            elif cmd == "repo" and len(args) >= 2:
                sub = args[0].lower()
                repo_id = args[1]
                if sub == "enable":
                    self._repos.enable_repo(repo_id)
                    outputs.append(f"Repo '{repo_id}' enabled")
                elif sub == "disable":
                    self._repos.disable_repo(repo_id)
                    outputs.append(f"Repo '{repo_id}' disabled")
            elif cmd == "group":
                sub = args[0].lower() if args else ""
                if sub == "list":
                    for g in self.group_list():
                        outputs.append(
                            f"  {g.group_id} - {g.name}"
                            f"{' (installed)' if g.install else ''}"
                        )
                elif sub == "install" and len(args) > 1:
                    result = self.group_install(args[1])
                    outputs.append(
                        f"Group install: {len(result.items)} items, "
                        f"{'OK' if result.success else 'FAILED'}"
                    )
                elif sub == "remove" and len(args) > 1:
                    result = self.group_remove(args[1])
                    outputs.append(
                        f"Group remove: {len(result.items)} items, "
                        f"{'OK' if result.success else 'FAILED'}"
                    )
            elif cmd == "history":
                sub = args[0].lower() if args else "list"
                if sub == "list":
                    for r in self.history_list():
                        outputs.append(
                            f"  {r.tid:8d} | {r.timestamp[:19]} | "
                            f"{r.cmdline}"
                        )
                elif sub == "undo" and len(args) > 1:
                    try:
                        tid = int(args[1])
                        result = self.history_undo(tid)
                        outputs.append(
                            f"Undo: {len(result.items)} items, "
                            f"{'OK' if result.success else 'FAILED'}"
                        )
                    except ValueError:
                        outputs.append("  Invalid transaction ID")
            elif cmd == "check-update":
                updates = self.check_update()
                if updates:
                    for old, new in updates:
                        outputs.append(
                            f"  {old.name}: {old.nevra.nevra} -> {new.nevra.nevra}"
                        )
                else:
                    outputs.append("  No updates available")
            elif cmd == "stats":
                s = self.stats()
                for k, v in s.items():
                    outputs.append(f"  {k}: {v}")
            else:
                outputs.append(f"  Unknown command: {cmd_line}")
        return outputs
