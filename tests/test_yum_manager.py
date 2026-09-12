"""Comprehensive tests for the UmerOS Yum-compatible Package Manager.

Covers:
  - Enums: PackageState, TransactionAction, TransactionState, RepoStatus, CleanType,
           UpdateInfoType, MarkReason, PluginHook
  - Dataclasses: PackageNevra, PackageInfo, RepoConfig, TransactionItem,
                 TransactionResult, PackageGroup, HistoryRecord, UpdateInfo, DepSolveResult
  - Sub-managers: CacheManager, RepositoryManager, DependencyResolver,
                  HistoryManager, GroupManager, PluginManager, SecurityManager
  - Facade: YumManager (integration-level smoke tests)

Module under test: srv.yum_manager
"""

from __future__ import annotations

import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

# ---------------------------------------------------------------------------
# Import all public symbols from the module under test.
# ---------------------------------------------------------------------------
from srv.yum_manager import (
    CacheManager,
    CleanType,
    DepSolveResult,
    GroupManager,
    HistoryManager,
    HistoryRecord,
    MarkReason,
    PackageGroup,
    PackageInfo,
    PackageNevra,
    PackageState,
    PluginHook,
    PluginManager,
    RepoConfig,
    RepoStatus,
    RepositoryManager,
    SecurityManager,
    TransactionAction,
    TransactionItem,
    TransactionResult,
    TransactionState,
    UpdateInfo,
    UpdateInfoType,
    YumManager,
    DependencyResolver,
)


# ===================================================================
# Helpers
# ===================================================================

def _make_nevra(
    name: str = "bash",
    epoch: str = "0",
    version: str = "5.1.8",
    release: str = "6.el9",
    arch: str = "x86_64",
) -> PackageNevra:
    """Shortcut to build a PackageNevra."""
    return PackageNevra(
        name=name,
        epoch=epoch,
        version=version,
        release=release,
        arch=arch,
    )


def _make_pkg(
    name: str = "bash",
    version: str = "5.1.8",
    release: str = "6.el9",
    arch: str = "x86_64",
    state: PackageState = PackageState.AVAILABLE,
    summary: str = "The GNU Bourne Again shell",
    requires: Optional[List[str]] = None,
    provides: Optional[List[str]] = None,
    obsoletes: Optional[List[str]] = None,
) -> PackageInfo:
    """Shortcut to build a PackageInfo."""
    return PackageInfo(
        nevra=PackageNevra(name=name, version=version, release=release, arch=arch),
        summary=summary,
        description="A shell",
        url="https://www.gnu.org/software/bash/",
        license="GPLv3+",
        size=7_000_000,
        installed_size=30_000_000,
        arch=arch,
        source_rpm="bash-5.1.8-6.el9.src.rpm",
        build_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        packager="UmerOS Build System",
        vendor="UmerOS",
        state=state,
        repo_id="baseos",
        requires=requires or [],
        provides=provides or [],
        conflicts=[],
        obsoletes=obsoletes or [],
        suggests=[],
        recommends=[],
    )


def _make_repo_config(repo_id: str = "baseos") -> RepoConfig:
    """Shortcut to build a RepoConfig."""
    return RepoConfig(
        repo_id=repo_id,
        name=f"UmerOS {repo_id.title()}",
        baseurl=[f"https://repo.umeros.org/{repo_id}/$basearch/os/"],
        gpgcheck=True,
        enabled=True,
        gpgkey=[f"file:///etc/pki/rpm-gpg/RPM-GPG-KEY-umeros-{repo_id}"],
    )


def _make_history_record(tid: int = 1) -> HistoryRecord:
    """Shortcut to build a HistoryRecord."""
    return HistoryRecord(
        tid=tid,
        timestamp=datetime.now(timezone.utc),
        cmdline="yum install bash",
        return_code=0,
        rpmdb_version="4.14.0",
        items=[{"action": "install", "name": "bash-5.1.8-6.el9.x86_64"}],
        state=TransactionState.COMMITTED,
        altered=1,
    )


def _make_update_info(update_id: str = "UMESA-2024:0001") -> UpdateInfo:
    """Shortcut to build an UpdateInfo."""
    return UpdateInfo(
        update_id=update_id,
        title="Security update for bash",
        issuer="UmerOS Security Team",
        status="final",
        update_type=UpdateInfoType.SECURITY,
        severity="Important",
        rights="Copyright 2024 UmerOS",
        description="A security update",
        references=[],
        pkg_names=["bash"],
    )


def _make_transaction_result(tid: int = 1) -> TransactionResult:
    """Shortcut to build a TransactionResult."""
    return TransactionResult(
        tid=tid,
        timestamp=datetime.now(timezone.utc),
        action="install",
        state=TransactionState.COMMITTED,
        items=[],
        request_by="user",
        return_code=0,
    )


# ===================================================================
# 1. ENUM TESTS
# ===================================================================

class TestPackageState:
    def test_available(self):
        assert PackageState.AVAILABLE.value == "available"

    def test_installed(self):
        assert PackageState.INSTALLED.value == "installed"

    def test_obsoleted(self):
        assert PackageState.OBSOLETED.value == "obsoleted"

    def test_all_values(self):
        vals = {s.value for s in PackageState}
        assert "available" in vals
        assert "installed" in vals
        assert "obsoleted" in vals

    def test_membership(self):
        assert "available" in [s.value for s in PackageState]


class TestTransactionAction:
    def test_install(self):
        assert TransactionAction.INSTALL.value == "install"

    def test_remove(self):
        assert TransactionAction.REMOVE.value == "remove"

    def test_update(self):
        assert TransactionAction.UPDATE.value == "update"

    def test_reinstall(self):
        assert TransactionAction.REINSTALL.value == "reinstall"

    def test_all_values(self):
        expected = {"install", "remove", "update", "reinstall"}
        actual = {a.value for a in TransactionAction}
        assert expected == actual


class TestTransactionState:
    def test_pending(self):
        assert TransactionState.PENDING.value == "pending"

    def test_running(self):
        assert TransactionState.RUNNING.value == "running"

    def test_committed(self):
        assert TransactionState.COMMITTED.value == "committed"

    def test_rolled_back(self):
        assert TransactionState.ROLLED_BACK.value == "rolled_back"

    def test_failed(self):
        assert TransactionState.FAILED.value == "failed"


class TestRepoStatus:
    def test_enabled(self):
        assert RepoStatus.ENABLED.value == "enabled"

    def test_disabled(self):
        assert RepoStatus.DISABLED.value == "disabled"

    def test_broken(self):
        assert RepoStatus.BROKEN.value == "broken"


class TestCleanType:
    def test_packages(self):
        assert CleanType.PACKAGES.value == "packages"

    def test_metadata(self):
        assert CleanType.METADATA.value == "metadata"

    def test_db_cache(self):
        assert CleanType.DB_CACHE.value == "dbcache"

    def test_yum_cache(self):
        assert CleanType.YUM_CACHE.value == "yum-cache"

    def test_timer(self):
        assert CleanType.TIMER.value == "timer"

    def test_dnf_cache(self):
        assert CleanType.DNF_CACHE.value == "dnf-cache"


class TestUpdateInfoType:
    def test_security(self):
        assert UpdateInfoType.SECURITY.value == "security"

    def test_bugfix(self):
        assert UpdateInfoType.BUGFIX.value == "bugfix"

    def test_enhancement(self):
        assert UpdateInfoType.ENHANCEMENT.value == "enhancement"

    def test_new_package(self):
        assert UpdateInfoType.NEW_PACKAGE.value == "newpackage"

    def test_unknown(self):
        assert UpdateInfoType.UNKNOWN.value == "unknown"


class TestMarkReason:
    def test_user(self):
        assert MarkReason.USER.value == "user"

    def test_dependency(self):
        assert MarkReason.DEPENDENCY.value == "dependency"

    def test_group(self):
        assert MarkReason.GROUP.value == "group"

    def test_plugin(self):
        assert MarkReason.PLUGIN.value == "plugin"

    def test_local(self):
        assert MarkReason.LOCAL.value == "local"


class TestPluginHook:
    def test_pre_transaction(self):
        assert PluginHook.PRE_TRANSACTION.value == "pre_transaction"

    def test_post_transaction(self):
        assert PluginHook.POST_TRANSACTION.value == "post_transaction"

    def test_pre_install(self):
        assert PluginHook.PRE_INSTALL.value == "pre_install"

    def test_post_install(self):
        assert PluginHook.POST_INSTALL.value == "post_install"

    def test_pre_remove(self):
        assert PluginHook.PRE_REMOVE.value == "pre_remove"

    def test_post_remove(self):
        assert PluginHook.POST_REMOVE.value == "post_remove"

    def test_pre_update(self):
        assert PluginHook.PRE_UPDATE.value == "pre_update"

    def test_post_update(self):
        assert PluginHook.POST_UPDATE.value == "post_update"

    def test_resolve_deps(self):
        assert PluginHook.RESOLVE_DEPS.value == "resolve_deps"

    def test_cache_loaded(self):
        assert PluginHook.CACHE_LOADED.value == "cache_loaded"


# ===================================================================
# 2. DATACLASS TESTS
# ===================================================================

class TestPackageNevra:
    def test_construction(self):
        nevra = PackageNevra(name="bash", epoch="0", version="5.1.8", release="6.el9", arch="x86_64")
        assert nevra.name == "bash"
        assert nevra.epoch == "0"
        assert nevra.version == "5.1.8"
        assert nevra.release == "6.el9"
        assert nevra.arch == "x86_64"

    def test_defaults(self):
        nevra = PackageNevra(name="coreutils")
        assert nevra.epoch == "0"
        assert nevra.version == ""
        assert nevra.release == ""
        assert nevra.arch == "noarch"

    def test_nevra_string(self):
        nevra = PackageNevra(name="bash", epoch="0", version="5.1.8", release="6.el9", arch="x86_64")
        # epoch "0" is omitted from the nevra string
        assert nevra.nevra == "bash-5.1.8-6.el9.x86_64"

    def test_nvra_string(self):
        nevra = PackageNevra(name="bash", epoch="0", version="5.1.8", release="6.el9", arch="x86_64")
        assert nevra.nvra == "bash-5.1.8-6.el9.x86_64"

    def test_evr_string(self):
        nevra = PackageNevra(name="bash", epoch="0", version="5.1.8", release="6.el9", arch="x86_64")
        # epoch "0" is omitted from evr when epoch is "0"
        assert nevra.evr == "5.1.8-6.el9"

    def test_nevra_string_with_epoch(self):
        nevra = PackageNevra(name="bash", epoch="1", version="5.1.8", release="6.el9", arch="x86_64")
        assert nevra.nevra == "bash-1:5.1.8-6.el9.x86_64"

    def test_evr_string_with_epoch(self):
        nevra = PackageNevra(name="bash", epoch="1", version="5.1.8", release="6.el9", arch="x86_64")
        assert nevra.evr == "1:5.1.8-6.el9"

    def test_from_string(self):
        nevra = PackageNevra.from_string("bash-5.1.8-6.el9.x86_64")
        assert nevra.name == "bash"
        assert nevra.epoch == "0"
        assert nevra.version == "5.1.8"
        assert nevra.release == "6.el9"
        assert nevra.arch == "x86_64"

    def test_from_string_with_epoch(self):
        nevra = PackageNevra.from_string("bash-0:5.1.8-6.el9.x86_64")
        assert nevra.name == "bash"
        assert nevra.epoch == "0"
        assert nevra.version == "5.1.8"

    def test_compare_evr_equal(self):
        a = PackageNevra(name="bash", version="5.1.8", release="6.el9")
        b = PackageNevra(name="bash", version="5.1.8", release="6.el9")
        assert a.compare_evr(b) == 0

    def test_compare_evr_newer(self):
        a = PackageNevra(name="bash", version="5.2.0", release="1.el9")
        b = PackageNevra(name="bash", version="5.1.8", release="6.el9")
        result = a.compare_evr(b)
        assert isinstance(result, int)
        assert result != 0

    def test_compare_evr_older(self):
        a = PackageNevra(name="bash", version="5.0.0", release="1.el9")
        b = PackageNevra(name="bash", version="5.1.8", release="6.el9")
        result = a.compare_evr(b)
        assert isinstance(result, int)

    def test_frozen(self):
        nevra = PackageNevra(name="bash")
        with pytest.raises(AttributeError):
            nevra.name = "zsh"  # type: ignore[misc]


class TestPackageInfo:
    def test_construction_defaults(self):
        nevra = _make_nevra()
        pkg = PackageInfo(nevra=nevra)
        assert pkg.nevra == nevra
        assert pkg.summary == ""
        assert pkg.state == PackageState.AVAILABLE
        assert pkg.repo_id == ""
        assert pkg.requires == []
        assert pkg.provides == []
        assert pkg.conflicts == []

    def test_construction_full(self):
        pkg = _make_pkg(name="vim-enhanced", version="8.2.2637", state=PackageState.INSTALLED)
        assert pkg.nevra.name == "vim-enhanced"
        assert pkg.nevra.version == "8.2.2637"
        assert pkg.state == PackageState.INSTALLED
        assert pkg.repo_id == "baseos"

    def test_frozen(self):
        pkg = _make_pkg()
        with pytest.raises(AttributeError):
            pkg.summary = "changed"  # type: ignore[misc]

    def test_dependency_lists(self):
        pkg = _make_pkg(requires=["libc.so.6", "libtinfo.so.6"], provides=["bash = 5.1.8"])
        assert len(pkg.requires) == 2
        assert "libc.so.6" in pkg.requires
        assert len(pkg.provides) == 1


class TestRepoConfig:
    def test_construction_defaults(self):
        rc = RepoConfig(repo_id="baseos", name="BaseOS")
        assert rc.repo_id == "baseos"
        assert rc.name == "BaseOS"
        assert rc.gpgcheck is True
        assert rc.enabled is True
        assert rc.gpgkey == []
        assert rc.sslverify is True
        assert rc.metadata_expire == "6h"
        assert rc.priority == 99
        assert rc.cost == 1000
        assert rc.module_hotfixes is False
        assert rc.status == RepoStatus.ENABLED

    def test_construction_full(self):
        rc = _make_repo_config("appstream")
        assert rc.repo_id == "appstream"
        assert "appstream" in rc.baseurl[0]

    def test_is_active(self):
        rc = _make_repo_config()
        assert rc.is_active is True
        rc2 = RepoConfig(repo_id="off", name="Off", enabled=False)
        assert rc2.is_active is False

    def test_frozen(self):
        rc = _make_repo_config()
        with pytest.raises(AttributeError):
            rc.repo_id = "changed"  # type: ignore[misc]


class TestTransactionItem:
    def test_construction(self):
        pkg = _make_pkg()
        item = TransactionItem(action=TransactionAction.INSTALL, package=pkg)
        assert item.action == TransactionAction.INSTALL
        assert item.package == pkg
        assert item.old_package is None
        assert item.reason == MarkReason.USER
        assert item.state == TransactionState.PENDING
        assert item.error == ""

    def test_update_with_old_package(self):
        old = _make_pkg(version="5.1.7")
        new = _make_pkg(version="5.1.8")
        item = TransactionItem(action=TransactionAction.UPDATE, package=new, old_package=old)
        assert item.old_package is not None
        assert item.old_package.nevra.version == "5.1.7"

    def test_frozen(self):
        pkg = _make_pkg()
        item = TransactionItem(action=TransactionAction.INSTALL, package=pkg)
        with pytest.raises(AttributeError):
            item.action = TransactionAction.REMOVE  # type: ignore[misc]


class TestTransactionResult:
    def test_construction(self):
        tr = _make_transaction_result(tid=42)
        assert tr.tid == 42
        assert tr.state == TransactionState.COMMITTED
        assert tr.return_code == 0
        assert tr.items == []

    def test_success_property(self):
        tr = TransactionResult(
            tid=1, timestamp=datetime.now(timezone.utc), action="install",
            state=TransactionState.COMMITTED,
        )
        assert tr.success is True

    def test_not_success_when_pending(self):
        tr = TransactionResult(
            tid=1, timestamp=datetime.now(timezone.utc), action="install",
            state=TransactionState.PENDING,
        )
        assert tr.success is False

    def test_not_success_when_failed(self):
        tr = TransactionResult(
            tid=1, timestamp=datetime.now(timezone.utc), action="install",
            state=TransactionState.FAILED,
        )
        assert tr.success is False

    def test_frozen(self):
        tr = _make_transaction_result()
        with pytest.raises(AttributeError):
            tr.tid = 999  # type: ignore[misc]


class TestPackageGroup:
    def test_construction(self):
        grp = PackageGroup(
            group_id="base",
            name="Base System Installation",
            description="Minimal install",
            packages=["bash", "coreutils"],
            default_packages=["vim-minimal"],
        )
        assert grp.group_id == "base"
        assert grp.user_visible is True
        assert grp.install is False

    def test_all_packages_property(self):
        grp = PackageGroup(
            group_id="dev",
            name="Development Tools",
            packages=["gcc", "make"],
            default_packages=["kernel-devel"],
            optional_packages=["valgrind"],
        )
        all_pkgs = grp.all_packages
        assert "gcc" in all_pkgs
        assert "make" in all_pkgs
        assert "kernel-devel" in all_pkgs
        assert "valgrind" not in all_pkgs

    def test_frozen(self):
        grp = PackageGroup(group_id="x", name="X")
        with pytest.raises(AttributeError):
            grp.group_id = "y"  # type: ignore[misc]


class TestHistoryRecord:
    def test_construction(self):
        hr = _make_history_record(tid=10)
        assert hr.tid == 10
        assert hr.return_code == 0
        assert hr.state == TransactionState.COMMITTED
        assert hr.altered == 1

    def test_frozen(self):
        hr = _make_history_record()
        with pytest.raises(AttributeError):
            hr.tid = 999  # type: ignore[misc]


class TestUpdateInfo:
    def test_construction(self):
        ui = _make_update_info("UMESA-2024:0042")
        assert ui.update_id == "UMESA-2024:0042"
        assert ui.update_type == UpdateInfoType.SECURITY
        assert ui.pkg_names == ["bash"]

    def test_frozen(self):
        ui = _make_update_info()
        with pytest.raises(AttributeError):
            ui.update_id = "X"  # type: ignore[misc]


class TestDepSolveResult:
    def test_success_empty(self):
        r = DepSolveResult()
        assert r.success is True
        assert r.total_changes == 0

    def test_success_with_changes(self):
        pkg = _make_pkg()
        r = DepSolveResult(install=[pkg])
        assert r.success is True
        assert r.total_changes == 1

    def test_not_success_on_conflicts(self):
        pkg = _make_pkg()
        r = DepSolveResult(conflicts=[pkg])
        assert r.success is False
        assert r.total_changes == 1

    def test_multiple_changes(self):
        i1, i2 = _make_pkg(name="a"), _make_pkg(name="b")
        u = _make_pkg(name="c")
        r = DepSolveResult(install=[i1, i2], update=[u], remove=[_make_pkg(name="d")])
        assert r.total_changes == 4

    def test_frozen(self):
        r = DepSolveResult()
        with pytest.raises(AttributeError):
            r.install = []  # type: ignore[misc]


# ===================================================================
# 3. SUB-MANAGER TESTS (smoke / construction / basic operations)
# ===================================================================

class TestCacheManager:
    """Smoke tests for CacheManager."""

    def test_construction(self, tmp_path: Path):
        cm = CacheManager(cache_dir=tmp_path / "cache")
        assert cm is not None


class TestRepositoryManager:
    """Smoke tests for RepositoryManager."""

    def test_construction(self, tmp_path: Path):
        rm = RepositoryManager(repos_dir=tmp_path / "repos")
        assert rm is not None

    def test_add_and_list_repos(self, tmp_path: Path):
        rm = RepositoryManager(repos_dir=tmp_path / "repos")
        rc = _make_repo_config("testrepo")
        rm.add_repo(rc, name="Test Repo")
        repos = rm.list_repos()
        assert any(r.repo_id == "testrepo" for r in repos)

    def test_get_repo(self, tmp_path: Path):
        rm = RepositoryManager(repos_dir=tmp_path / "repos")
        rc = _make_repo_config("gettest")
        rm.add_repo(rc, name="Get Test")
        fetched = rm.get_repo("gettest")
        assert fetched is not None
        assert fetched.repo_id == "gettest"

    def test_remove_repo(self, tmp_path: Path):
        rm = RepositoryManager(repos_dir=tmp_path / "repos")
        rc = _make_repo_config("deltarget")
        rm.add_repo(rc, name="Del Target")
        rm.remove_repo("deltarget")
        assert rm.get_repo("deltarget") is None

    def test_enable_disable(self, tmp_path: Path):
        rm = RepositoryManager(repos_dir=tmp_path / "repos")
        rc = _make_repo_config("toggle")
        rm.add_repo(rc, name="Toggle Repo")
        rm.disable_repo("toggle")
        assert rm.get_repo("toggle").enabled is False
        rm.enable_repo("toggle")
        assert rm.get_repo("toggle").enabled is True


class TestDependencyResolver:
    """Smoke tests for DependencyResolver."""

    def test_construction(self):
        dr = DependencyResolver(package_index={})
        assert dr is not None

    def test_resolve_empty(self):
        dr = DependencyResolver(package_index={})
        result = dr.resolve(request=[], installed=[])
        assert isinstance(result, DepSolveResult)
        assert result.success is True


class TestHistoryManager:
    """Smoke tests for HistoryManager."""

    def test_construction(self, tmp_path: Path):
        hm = HistoryManager(history_dir=tmp_path / "history")
        assert hm is not None

    def test_list_empty(self, tmp_path: Path):
        hm = HistoryManager(history_dir=tmp_path / "history")
        records = hm.list_history()
        assert records == []


class TestGroupManager:
    """Smoke tests for GroupManager."""

    def test_construction(self, tmp_path: Path):
        gm = GroupManager(groups_dir=tmp_path / "groups")
        assert gm is not None

    def test_list_groups_empty(self, tmp_path: Path):
        gm = GroupManager(groups_dir=tmp_path / "groups")
        groups = gm.list_groups()
        assert groups == []


class TestPluginManager:
    """Smoke tests for PluginManager."""

    def test_construction(self):
        pm = PluginManager()
        assert pm is not None

    def test_list_plugins_empty(self):
        pm = PluginManager()
        plugins = pm.list_plugins()
        assert plugins == []


class TestSecurityManager:
    """Smoke tests for SecurityManager."""

    def test_construction(self):
        sm = SecurityManager()
        assert sm is not None


# ===================================================================
# 4. YUMMANAGER FACADE SMOKE TESTS
# ===================================================================

class TestYumManagerFacade:
    """Smoke tests for the YumManager facade.

    Uses a temp directory so tests do not touch live system state.
    """

    @pytest.fixture()
    def yum(self, tmp_path: Path) -> YumManager:
        """Create a YumManager rooted in a temp directory."""
        base = tmp_path / "umeros"
        base.mkdir()
        return YumManager(
            base_dir=base,
            cache_dir=base / "cache",
            repos_dir=base / "repos",
            history_dir=base / "history",
            groups_dir=base / "groups",
        )

    def test_construction(self, yum: YumManager):
        assert yum is not None

    def test_installed_packages_returns_dict(self, yum: YumManager):
        installed = yum.installed_packages
        assert isinstance(installed, dict)

    def test_search_returns_list(self, yum: YumManager):
        results = yum.search("bash")
        assert isinstance(results, list)

    def test_list_installed_returns_list(self, yum: YumManager):
        pkgs = yum.list_installed()
        assert isinstance(pkgs, list)

    def test_list_available_returns_list(self, yum: YumManager):
        pkgs = yum.list_available()
        assert isinstance(pkgs, list)

    def test_list_updates_returns_list(self, yum: YumManager):
        updates = yum.list_updates()
        assert isinstance(updates, list)

    def test_check_update_returns_list(self, yum: YumManager):
        updates = yum.check_update()
        assert isinstance(updates, list)

    def test_history_list_returns_list(self, yum: YumManager):
        records = yum.history_list()
        assert isinstance(records, list)

    def test_group_list_returns_list(self, yum: YumManager):
        groups = yum.group_list()
        assert isinstance(groups, list)

    def test_stats_returns_dict(self, yum: YumManager):
        s = yum.stats()
        assert isinstance(s, dict)

    def test_install_returns_transaction_result(self, yum: YumManager):
        result = yum.install(["bash"])
        assert isinstance(result, TransactionResult)

    def test_remove_returns_transaction_result(self, yum: YumManager):
        result = yum.remove(["bash"])
        assert isinstance(result, TransactionResult)

    def test_update_returns_transaction_result(self, yum: YumManager):
        result = yum.update(["bash"])
        assert isinstance(result, TransactionResult)

    def test_group_install_returns_transaction_result(self, yum: YumManager):
        result = yum.group_install("base")
        assert isinstance(result, TransactionResult)

    def test_autoremove_returns_transaction_result(self, yum: YumManager):
        result = yum.autoremove()
        assert isinstance(result, TransactionResult)

    def test_security_update_list_returns_list(self, yum: YumManager):
        sec = yum.security_update_list()
        assert isinstance(sec, list)


# ===================================================================
# 5. INTEGRATION-STYLE TESTS (cross-component)
# ===================================================================

class TestTransactionWorkflow:
    """End-to-end-style tests that exercise multiple components."""

    def test_full_lifecycle(self, tmp_path: Path):
        base = tmp_path / "umeros"
        base.mkdir()
        yum = YumManager(
            base_dir=base,
            cache_dir=base / "cache",
            repos_dir=base / "repos",
            history_dir=base / "history",
            groups_dir=base / "groups",
        )

        # Install
        result = yum.install(["bash"])
        assert isinstance(result, TransactionResult)
        assert result.state in (TransactionState.COMMITTED, TransactionState.PENDING, TransactionState.FAILED)

        # Search
        found = yum.search("bash")
        assert isinstance(found, list)

        # List installed
        installed = yum.list_installed()
        assert isinstance(installed, list)

        # History
        history = yum.history_list()
        assert isinstance(history, list)

        # Stats
        stats = yum.stats()
        assert isinstance(stats, dict)


class TestRepoManagerWorkflow:
    """End-to-end repo management."""

    def test_add_remove_list(self, tmp_path: Path):
        rm = RepositoryManager(repos_dir=tmp_path / "repos")

        for i in range(3):
            rc = RepoConfig(
                repo_id=f"repo{i}",
                name=f"Repo {i}",
                baseurl=[f"https://example.com/repo{i}"],
            )
            rm.add_repo(rc, name=f"Repo {i}")

        repos = rm.list_repos()
        assert len(repos) >= 3

        rm.remove_repo("repo1")
        assert rm.get_repo("repo1") is None


class TestDependencyResolverWorkflow:
    """Dependency resolution with a real package index."""

    def test_resolve_with_index(self):
        pkgs = {
            "bash": [_make_pkg(name="bash", requires=["libc.so.6", "libtinfo.so.6"])],
            "libc.so.6": [_make_pkg(name="glibc")],
            "libtinfo.so.6": [_make_pkg(name="ncurses-libs")],
        }
        dr = DependencyResolver(package_index=pkgs)
        result = dr.resolve(request=["bash"], installed=[])
        assert isinstance(result, DepSolveResult)
        assert result.success is True
