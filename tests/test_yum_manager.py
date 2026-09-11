"""Comprehensive pytest suite for srv.yum_manager.

Covers enums, dataclasses, all sub-managers, and YumManager facade.
Targets ~350 lines with ~80+ test cases.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import pytest

from srv.yum_manager import (
    CacheEntry,
    CacheManager,
    Dependency,
    DependencyResolver,
    DependencyType,
    GroupInfo,
    GroupManager,
    HistoryRecord,
    HistoryTracker,
    PackageAction,
    PackageInfo,
    PackageUpdate,
    PluginConfig,
    PluginHook,
    PluginManager,
    RepositoryInfo,
    RepoStatus,
    SecurityUpdate,
    SecurityUpdater,
    Transaction,
    TransactionManager,
    TransactionState,
    TransactionStep,
    UpdateType,
    YumConfig,
    YumManager,
    YumResult,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestEnums:
    def test_repo_status_values(self):
        assert RepoStatus.ENABLED.value == "enabled"
        assert RepoStatus.DISABLED.value == "disabled"
        assert RepoStatus.MIRRORBROKEN.value == "mirrorbroken"

    def test_package_action_values(self):
        assert PackageAction.INSTALL.value == "install"
        assert PackageAction.REMOVE.value == "remove"
        assert PackageAction.UPDATE.value == "update"
        assert PackageAction.DOWNGRADE.value == "downgrade"
        assert PackageAction.REINSTALL.value == "reinstall"
        assert PackageAction.UPGRADE.value == "upgrade"

    def test_dependency_type_values(self):
        assert DependencyType.REQUIRES.value == "requires"
        assert DependencyType.PROVIDES.value == "provides"
        assert DependencyType.CONFLICTS.value == "conflicts"
        assert DependencyType.OBSOLETES.value == "obsoletes"
        assert DependencyType.RECOMMENDS.value == "recommends"
        assert DependencyType.SUGGESTS.value == "suggests"

    def test_update_type_values(self):
        assert UpdateType.SECURITY.value == "security"
        assert UpdateType.BUGFIX.value == "bugfix"
        assert UpdateType.ENHANCEMENT.value == "enhancement"
        assert UpdateType.NORMAL.value == "normal"

    def test_transaction_state_values(self):
        assert TransactionState.PENDING.value == "pending"
        assert TransactionState.RUNNING.value == "running"
        assert TransactionState.COMPLETED.value == "completed"
        assert TransactionState.FAILED.value == "failed"
        assert TransactionState.ROLLED_BACK.value == "rolled_back"

    def test_plugin_hook_values(self):
        assert PluginHook.PRE_INSTALL.value == "pre_install"
        assert PluginHook.POST_INSTALL.value == "post_install"
        assert PluginHook.PRE_REMOVE.value == "pre_remove"
        assert PluginHook.POST_REMOVE.value == "post_remove"
        assert PluginHook.PRE_TRANSACTION.value == "pre_transaction"
        assert PluginHook.POST_TRANSACTION.value == "post_transaction"


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestPackageInfo:
    def test_creation(self):
        pkg = PackageInfo(
            name="bash",
            version="5.2.0",
            release="1.fc39",
            arch="x86_64",
            epoch=0,
            size=7800000,
            summary="GNU Bourne Again shell",
            license_="GPLv3+",
            repo="baseos",
        )
        assert pkg.name == "bash"
        assert pkg.version == "5.2.0"
        assert pkg.release == "1.fc39"
        assert pkg.arch == "x86_64"
        assert pkg.epoch == 0
        assert pkg.size == 7800000
        assert pkg.repo == "baseos"

    def test_defaults(self):
        pkg = PackageInfo(name="test", version="1.0", release="1", arch="x86_64")
        assert pkg.epoch == 0
        assert pkg.size == 0
        assert pkg.summary == ""
        assert pkg.license_ == ""
        assert pkg.repo == ""
        assert pkg.dependencies == []
        assert pkg.provides == []

    def test_equality(self):
        p1 = PackageInfo(name="bash", version="5.2", release="1", arch="x86_64")
        p2 = PackageInfo(name="bash", version="5.2", release="1", arch="x86_64")
        assert p1 == p2

    def test_inequality(self):
        p1 = PackageInfo(name="bash", version="5.2", release="1", arch="x86_64")
        p2 = PackageInfo(name="zsh", version="5.2", release="1", arch="x86_64")
        assert p1 != p2


class TestRepositoryInfo:
    def test_creation(self):
        repo = RepositoryInfo(
            id_="baseos",
            name="BaseOS",
            baseurl="https://example.com/baseos",
            status=RepoStatus.ENABLED,
            gpgcheck=True,
            gpgkey="https://example.com/RPM-GPG-KEY",
        )
        assert repo.id_ == "baseos"
        assert repo.status == RepoStatus.ENABLED
        assert repo.gpgcheck is True

    def test_defaults(self):
        repo = RepositoryInfo(id_="test", name="Test", baseurl="http://example.com")
        assert repo.status == RepoStatus.ENABLED
        assert repo.gpgcheck is True
        assert repo.ssl_verify is True
        assert repo.priority == 99
        assert repo.metadata_expire == 3600


class TestDependency:
    def test_creation(self):
        dep = Dependency(
            name="glibc",
            version="2.38",
            comparator=">=",
            dep_type=DependencyType.REQUIRES,
        )
        assert dep.name == "glibc"
        assert dep.comparator == ">="
        assert dep.dep_type == DependencyType.REQUIRES

    def test_defaults(self):
        dep = Dependency(name="test")
        assert dep.version == ""
        assert dep.comparator == ""
        assert dep.dep_type == DependencyType.REQUIRES
        assert dep.pre is False


class TestTransaction:
    def test_creation(self):
        txn = Transaction(
            id_="txn-001",
            packages=["bash", "coreutils"],
            action=PackageAction.INSTALL,
        )
        assert txn.id_ == "txn-001"
        assert txn.action == PackageAction.INSTALL
        assert txn.state == TransactionState.PENDING

    def test_defaults(self):
        txn = Transaction(id_="txn-002", packages=[], action=PackageAction.REMOVE)
        assert txn.state == TransactionState.PENDING
        assert txn.steps == []
        assert txn.error == ""
        assert txn.start_time is None
        assert txn.end_time is None


class TestTransactionStep:
    def test_creation(self):
        step = TransactionStep(
            package="bash",
            action=PackageAction.INSTALL,
            state=TransactionState.COMPLETED,
            rpm_output="Installing: bash-5.2-1.fc39.x86_64",
        )
        assert step.package == "bash"
        assert step.state == TransactionState.COMPLETED
        assert "Installing" in step.rpm_output


class TestHistoryRecord:
    def test_creation(self):
        now = datetime.now(timezone.utc)
        record = HistoryRecord(
            id_=1,
            timestamp=now,
            action="install",
            packages=["bash"],
            return_code=0,
        )
        assert record.id_ == 1
        assert record.packages == ["bash"]
        assert record.return_code == 0
        assert record.command_line == ""
        assert record.username == ""

    def test_defaults(self):
        record = HistoryRecord(
            id_=99,
            timestamp=datetime.now(timezone.utc),
            action="remove",
            packages=[],
            return_code=0,
        )
        assert record.command_line == ""
        assert record.username == ""


class TestSecurityUpdate:
    def test_creation(self):
        sec = SecurityUpdate(
            name="openssl",
            installed_version="3.1.4",
            fixed_version="3.1.5",
            severity="Critical",
            cve_ids=["CVE-2024-0001"],
            advisory_id="RHSA-2024:0001",
        )
        assert sec.severity == "Critical"
        assert "CVE-2024-0001" in sec.cve_ids
        assert sec.advisory_id == "RHSA-2024:0001"


class TestGroupInfo:
    def test_creation(self):
        grp = GroupInfo(
            id_="development-tools",
            name="Development Tools",
            packages=["gcc", "make", "git"],
        )
        assert grp.id_ == "development-tools"
        assert len(grp.packages) == 3
        assert grp.mandatory_packages == []
        assert grp.optional_packages == []

    def test_defaults(self):
        grp = GroupInfo(id_="minimal", name="Minimal Install", packages=[])
        assert grp.description == ""


class TestPackageUpdate:
    def test_creation(self):
        upd = PackageUpdate(
            name="bash",
            current_version="5.1.0",
            available_version="5.2.0",
            update_type=UpdateType.BUGFIX,
        )
        assert upd.current_version == "5.1.0"
        assert upd.update_type == UpdateType.BUGFIX
        assert upd.security_info is None


class TestCacheEntry:
    def test_creation(self):
        entry = CacheEntry(
            key="repo:baseos",
            value={"repomd.xml": "..."},
            expiry=time.time() + 3600,
        )
        assert entry.key == "repo:baseos"
        assert entry.size == 0

    def test_is_expired(self):
        entry = CacheEntry(key="k", value={}, expiry=time.time() - 1)
        assert entry.is_expired is True

    def test_not_expired(self):
        entry = CacheEntry(key="k", value={}, expiry=time.time() + 3600)
        assert entry.is_expired is False


class TestPluginConfig:
    def test_creation(self):
        plugin = PluginConfig(
            name="fastestmirror",
            enabled=True,
            hooks=[PluginHook.PRE_TRANSACTION],
        )
        assert plugin.enabled is True
        assert PluginHook.PRE_TRANSACTION in plugin.hooks
        assert plugin.config == {}

    def test_defaults(self):
        plugin = PluginConfig(name="test", enabled=False, hooks=[])
        assert plugin.config == {}


class TestYumConfig:
    def test_defaults(self):
        cfg = YumConfig()
        assert cfg.installonly_limit == 3
        assert cfg.clean_requirements_on_remove is True
        assert cfg.best is True
        assert cfg.tsflags == ""
        assert cfg.cachedir != ""
        assert cfg.logfile != ""
        assert cfg.reposdir != ""

    def test_custom(self):
        cfg = YumConfig(installonly_limit=5, best=False)
        assert cfg.installonly_limit == 5
        assert cfg.best is False


class TestYumResult:
    def test_success(self):
        r = YumResult(success=True, message="Done", packages_installed=["bash"])
        assert r.success is True
        assert r.packages_installed == ["bash"]

    def test_failure(self):
        r = YumResult(success=False, message="Error", errors=["repo not found"])
        assert r.success is False
        assert "repo not found" in r.errors

    def test_defaults(self):
        r = YumResult(success=True, message="ok")
        assert r.packages_installed == []
        assert r.packages_removed == []
        assert r.packages_updated == []
        assert r.warnings == []
        assert r.errors == []
        assert r.transactions == []
        assert r.history_id is None


# ---------------------------------------------------------------------------
# Sub-manager tests
# ---------------------------------------------------------------------------

class TestDependencyResolver:
    def test_resolve_empty(self):
        resolver = DependencyResolver()
        result = resolver.resolve([])
        assert result == []

    def test_resolve_returns_input(self):
        resolver = DependencyResolver()
        deps = [Dependency(name="glibc")]
        result = resolver.resolve(deps)
        assert len(result) == 1


class TestTransactionManager:
    def test_create_transaction(self):
        mgr = TransactionManager()
        txn = mgr.create_transaction(["bash"], PackageAction.INSTALL)
        assert txn is not None
        assert txn.state == TransactionState.PENDING
        assert "bash" in txn.packages

    def test_transaction_persistence(self, tmp_path):
        mgr = TransactionManager(state_dir=str(tmp_path))
        txn = mgr.create_transaction(["vim"], PackageAction.INSTALL)
        mgr2 = TransactionManager(state_dir=str(tmp_path))
        assert len(mgr2.transactions) >= 1


class TestHistoryTracker:
    def test_record_transaction(self):
        tracker = HistoryTracker()
        txn = Transaction(
            id_="hist-1",
            packages=["bash"],
            action=PackageAction.INSTALL,
        )
        txn.state = TransactionState.COMPLETED
        tracker.record_transaction(txn)
        assert len(tracker.records) >= 1

    def test_list_history(self):
        tracker = HistoryTracker()
        history = tracker.list_history(limit=10)
        assert isinstance(history, list)


class TestSecurityUpdater:
    def test_check_for_updates_empty(self):
        updater = SecurityUpdater()
        updates = updater.check_for_updates()
        assert isinstance(updates, list)

    def test_check_for_updates_returns_list(self):
        updater = SecurityUpdater()
        result = updater.check_for_updates()
        assert isinstance(result, list)


class TestGroupManager:
    def test_list_groups_empty(self):
        mgr = GroupManager()
        groups = mgr.list_groups()
        assert isinstance(groups, list)

    def test_list_available_groups_empty(self):
        mgr = GroupManager()
        groups = mgr.list_available_groups()
        assert isinstance(groups, list)


class TestCacheManager:
    def test_init_creates_dir(self, tmp_path):
        cache_dir = tmp_path / "yum_cache"
        mgr = CacheManager(cache_dir=str(cache_dir))
        assert cache_dir.exists()

    def test_set_get(self, tmp_path):
        mgr = CacheManager(cache_dir=str(tmp_path / "c"))
        mgr.set("key1", {"data": 1}, ttl=3600)
        val = mgr.get("key1")
        assert val == {"data": 1}

    def test_expired_entry(self, tmp_path):
        mgr = CacheManager(cache_dir=str(tmp_path / "c"))
        mgr.set("key2", "val", ttl=-1)
        val = mgr.get("key2")
        assert val is None

    def test_invalidate(self, tmp_path):
        mgr = CacheManager(cache_dir=str(tmp_path / "c"))
        mgr.set("key3", "x", ttl=3600)
        mgr.invalidate("key3")
        assert mgr.get("key3") is None

    def test_clear(self, tmp_path):
        mgr = CacheManager(cache_dir=str(tmp_path / "c"))
        mgr.set("a", 1, ttl=3600)
        mgr.set("b", 2, ttl=3600)
        mgr.clear()
        assert mgr.get("a") is None


class TestPluginManager:
    def test_empty_hooks(self):
        pmgr = PluginManager()
        assert pmgr.hooks == {}

    def test_register_plugin(self):
        pmgr = PluginManager()
        cfg = PluginConfig(
            name="test_plugin",
            enabled=True,
            hooks=[PluginHook.PRE_INSTALL],
        )
        pmgr.register(cfg)
        assert "test_plugin" in pmgr.plugins


# ---------------------------------------------------------------------------
# YumManager facade tests
# ---------------------------------------------------------------------------

class TestYumManager:
    def test_init_default(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        assert mgr is not None
        assert mgr.config is not None

    def test_init_custom_config(self, tmp_path):
        cfg = YumConfig(installonly_limit=5)
        mgr = YumManager(config=cfg, state_dir=str(tmp_path / "yum_state"))
        assert mgr.config.installonly_limit == 5

    def test_list_installed(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        installed = mgr.list_installed()
        assert isinstance(installed, list)

    def test_search_empty(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        results = mgr.search("nonexistent_pkg_xyz")
        assert isinstance(results, list)

    def test_info_package_returns_none(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        info = mgr.info("nonexistent_pkg_xyz")
        assert info is None

    def test_install_nonexistent(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        result = mgr.install("nonexistent_pkg_xyz_12345")
        assert isinstance(result, YumResult)

    def test_remove_nonexistent(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        result = mgr.remove("nonexistent_pkg_xyz_12345")
        assert isinstance(result, YumResult)

    def test_update_check(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        updates = mgr.check_updates()
        assert isinstance(updates, list)

    def test_history_list(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        history = mgr.history_list()
        assert isinstance(history, list)

    def test_cache_clean(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        cleaned = mgr.cache_clean()
        assert isinstance(cleaned, int)

    def test_repolist(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        repos = mgr.repolist()
        assert isinstance(repos, list)

    def test_group_list(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        groups = mgr.group_list()
        assert isinstance(groups, list)

    def test_security_check(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        sec = mgr.check_security()
        assert isinstance(sec, list)

    def test_transaction_history(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        txns = mgr.transaction_history()
        assert isinstance(txns, list)

    def test_plugin_list(self, tmp_path):
        mgr = YumManager(state_dir=str(tmp_path / "yum_state"))
        plugins = mgr.plugin_list()
        assert isinstance(plugins, list)


# ---------------------------------------------------------------------------
# Serialization round-trip tests
# ---------------------------------------------------------------------------

class TestSerializationRoundTrip:
    def test_package_info_to_dict(self):
        pkg = PackageInfo(
            name="bash",
            version="5.2",
            release="1.fc39",
            arch="x86_64",
        )
        d = pkg.__dict__
        assert d["name"] == "bash"
        assert d["version"] == "5.2"

    def test_repository_info_to_dict(self):
        repo = RepositoryInfo(
            id_="baseos",
            name="BaseOS",
            baseurl="https://example.com",
        )
        d = repo.__dict__
        assert d["id_"] == "baseos"
        assert d["status"] == RepoStatus.ENABLED

    def test_transaction_to_dict(self):
        txn = Transaction(
            id_="txn-1",
            packages=["vim"],
            action=PackageAction.INSTALL,
        )
        d = txn.__dict__
        assert d["id_"] == "txn-1"
        assert d["state"] == TransactionState.PENDING

    def test_history_record_to_dict(self):
        rec = HistoryRecord(
            id_=1,
            timestamp=datetime.now(timezone.utc),
            action="install",
            packages=["bash"],
            return_code=0,
        )
        d = rec.__dict__
        assert d["id_"] == 1
        assert d["action"] == "install"

    def test_plugin_config_to_dict(self):
        pc = PluginConfig(
            name="fastestmirror",
            enabled=True,
            hooks=[PluginHook.PRE_INSTALL],
        )
        d = pc.__dict__
        assert d["name"] == "fastestmirror"
        assert d["enabled"] is True

    def test_yum_config_to_dict(self):
        cfg = YumConfig()
        d = cfg.__dict__
        assert d["installonly_limit"] == 3
        assert d["best"] is True

    def test_group_info_to_dict(self):
        g = GroupInfo(id_="dev", name="Dev Tools", packages=["gcc"])
        d = g.__dict__
        assert d["id_"] == "dev"
        assert "gcc" in d["packages"]

    def test_security_update_to_dict(self):
        s = SecurityUpdate(
            name="openssl",
            installed_version="3.1.4",
            fixed_version="3.1.5",
            severity="High",
            cve_ids=["CVE-2024-1234"],
            advisory_id="RHSA-2024:9999",
        )
        d = s.__dict__
        assert d["severity"] == "High"
        assert "CVE-2024-1234" in d["cve_ids"]
