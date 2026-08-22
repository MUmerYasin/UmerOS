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
Comprehensive Test Suite for UmerOS /srv Filesystem Hierarchy System
=====================================================================

Verifies all components of the /srv subsystem 
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add project root and srv folder to sys.path
_srv_dir = Path(__file__).resolve().parent
_root_dir = _srv_dir.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))
if str(_srv_dir) not in sys.path:
    sys.path.insert(0, str(_srv_dir))


def test_imports() -> bool:
    print("=" * 60)
    print("Test 1: Module Imports")
    print("=" * 60)
    try:
        import srv
        from srv import (
            FHSValidator,
            OrganizationScheme,
            StandardProtocol,
            SrvHierarchy,
            ServiceRecord,
            ServiceConfig,
            SrvPermissionManager,
            WWWServiceHandler,
            FTPServiceHandler,
            GitServiceHandler,
            RsyncServiceHandler,
            TFTPServiceHandler,
            SambaNfsServiceHandler,
            SrvBackupManager,
            SrvManager,
        )
        print("✓ All /srv modules and classes imported successfully.")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_fhs_validation() -> bool:
    print("\n" + "=" * 60)
    print("Test 2: FHS & TLDP Validation Rules")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        srv_root = Path(tmpdir) / "srv"
        srv_root.mkdir()

        from srv.fhs import FHSValidator, OrganizationScheme

        # 1. Valid protocol path
        www_path = srv_root / "www"
        www_path.mkdir()
        res1 = FHSValidator.validate_service_path(www_path, srv_root)
        assert res1.is_compliant, "Valid /srv/www flagged as non-compliant"

        # 2. Prohibited system root directory inside /srv
        bin_path = srv_root / "bin"
        bin_path.mkdir()
        res2 = FHSValidator.validate_service_path(bin_path, srv_root)
        assert not res2.is_compliant, "Prohibited /srv/bin was not flagged"
        assert any("conflicts with root system hierarchy" in v for v in res2.violations)

        # 3. Prohibited user home directory inside /srv
        home_path = srv_root / "home"
        home_path.mkdir()
        res3 = FHSValidator.validate_service_path(home_path, srv_root)
        assert not res3.is_compliant, "User home in /srv was not flagged"

        # 4. Classification check
        scheme, proto = FHSValidator.classify_path(www_path, srv_root)
        assert scheme == OrganizationScheme.BY_PROTOCOL
        assert proto == "www"

        domain_path = srv_root / "example.com"
        scheme_d, dom = FHSValidator.classify_path(domain_path, srv_root)
        assert scheme_d == OrganizationScheme.BY_DOMAIN
        assert dom == "example.com"

        print("✓ FHS and TLDP compliance validation checks passed.")
        return True


def test_hierarchy_bootstrap_and_trees() -> bool:
    print("\n" + "=" * 60)
    print("Test 3: Hierarchy Provisioning & Bootstrap")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        srv_root = Path(tmpdir) / "srv"
        from srv.hierarchy import SrvHierarchy
        from srv.fhs import StandardProtocol

        hier = SrvHierarchy(srv_root)
        skeletons = hier.bootstrap()

        assert (srv_root / "www" / "html").exists()
        assert (srv_root / "www" / "cgi-bin").exists()
        assert (srv_root / "ftp" / "pub").exists()
        assert (srv_root / "ftp" / "incoming").exists()
        assert (srv_root / "git" / "repositories").exists()
        assert (srv_root / "rsync" / "shares").exists()
        assert (srv_root / "tftp" / "boot").exists()

        # Custom service tree
        custom_tree = hier.create_service_tree("api_service", StandardProtocol.WWW, subdirs=["data", "scripts", "uploads"])
        assert custom_tree.base_dir.exists()
        assert custom_tree.data_dir.exists()
        assert (custom_tree.base_dir / "scripts").exists()

        scan = hier.scan_hierarchy()
        assert len(scan) >= 6

        print(f"✓ Bootstrapped {len(skeletons)} standard skeletons and created custom trees successfully.")
        return True


def test_protocols() -> bool:
    print("\n" + "=" * 60)
    print("Test 4: Protocol Handlers")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        srv_root = Path(tmpdir) / "srv"
        from srv.protocols import (
            WWWServiceHandler,
            FTPServiceHandler,
            GitServiceHandler,
            RsyncServiceHandler,
            TFTPServiceHandler,
            SambaNfsServiceHandler,
        )

        # 1. WWW Vhost
        vhost = WWWServiceHandler.setup_vhost(srv_root / "www", "app.umeros.local")
        assert vhost["document_root"].exists()
        assert (vhost["document_root"] / "index.html").exists()

        # 2. FTP Tree
        ftp_res = FTPServiceHandler.setup_ftp_tree(srv_root / "ftp")
        assert (ftp_res["pub"] / "README.txt").exists()

        # 3. Git Bare Repo
        repo = GitServiceHandler.create_bare_repository(srv_root / "git", "kernel.git")
        assert (repo / "HEAD").exists()
        assert (repo / "config").exists()
        assert "kernel.git" in GitServiceHandler.list_repositories(srv_root / "git")

        # 4. Rsync Conf
        conf = RsyncServiceHandler.generate_rsyncd_conf(srv_root / "rsync", "packages")
        assert "[packages]" in conf

        # 5. TFTP PXE
        pxe = TFTPServiceHandler.setup_pxe_boot(srv_root / "tftp")
        assert (pxe["pxelinux.cfg"] / "default").exists()

        # 6. Samba/NFS
        nfs_line = SambaNfsServiceHandler.generate_nfs_export_line(srv_root / "nfs" / "exports")
        assert "/exports *(rw,sync,no_subtree_check)" in nfs_line.replace("\\", "/")

        print("✓ All protocol-specific handlers (WWW, FTP, Git, Rsync, TFTP, Samba, NFS) passed.")
        return True


def test_permissions_and_security() -> bool:
    print("\n" + "=" * 60)
    print("Test 5: Permissions & Security Audit")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        srv_root = Path(tmpdir) / "srv"
        srv_root.mkdir()
        from srv.permissions import SrvPermissionManager
        from srv.fhs import StandardProtocol

        # Create service dir
        www_dir = srv_root / "www"
        www_dir.mkdir()
        (www_dir / "html").mkdir()
        (www_dir / "uploads").mkdir()
        (www_dir / "conf").mkdir()

        res = SrvPermissionManager.apply_profile(www_dir, StandardProtocol.WWW)
        assert res["success"]

        audit = SrvPermissionManager.audit_service(www_dir)
        assert isinstance(audit.is_secure, bool)

        print("✓ Permission manager and security profiles validated.")
        return True


def test_backup_and_restore() -> bool:
    print("\n" + "=" * 60)
    print("Test 6: Backup, Archive & Restore")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        srv_root = Path(tmpdir) / "srv"
        srv_root.mkdir()
        backup_dir = Path(tmpdir) / "backups"
        backup_dir.mkdir()

        from srv.backup import SrvBackupManager

        bm = SrvBackupManager(backup_dir=backup_dir, srv_root=srv_root)

        # Create dummy service data
        my_srv = srv_root / "my_service"
        my_srv.mkdir()
        (my_srv / "data.txt").write_text("Hello UmerOS Service Data", encoding="utf-8")

        # 1. Create tar.gz backup
        tar_backup = bm.create_backup(my_srv, service_name="my_service", archive_format="tar.gz")
        assert tar_backup.exists()

        # 2. Create zip backup
        zip_backup = bm.create_backup(my_srv, service_name="my_service", archive_format="zip")
        assert zip_backup.exists()

        assert len(bm.list_backups()) >= 2

        # 3. Restore to target
        restore_target = Path(tmpdir) / "restored_srv"
        restore_target.mkdir()
        res = bm.restore_backup(tar_backup, target_root=restore_target)
        assert res["success"]
        assert (restore_target / "my_service" / "data.txt").exists()
        assert (restore_target / "my_service" / "data.txt").read_text(encoding="utf-8") == "Hello UmerOS Service Data"

        print("✓ Backup creation (tar.gz & zip) and restoration verified.")
        return True


def test_srv_manager_and_persistence() -> bool:
    print("\n" + "=" * 60)
    print("Test 7: SrvManager & Registry Persistence")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        srv_root = Path(tmpdir) / "srv"
        reg_file = Path(tmpdir) / "registry.json"

        from srv.manager import SrvManager
        from srv.fhs import StandardProtocol

        mgr = SrvManager(srv_root=srv_root, registry_path=reg_file)

        # 1. Bootstrap skeletons
        mgr.hierarchy.bootstrap()
        mgr.auto_discover()
        services = mgr.list_services()
        assert len(services) >= 5

        # 2. Create new service
        rec = mgr.create_service("test_api", protocol=StandardProtocol.WWW)
        assert rec.name == "test_api"
        assert rec.base_path == str(srv_root / "test_api")

        # 3. Check JSON persistence
        assert reg_file.exists()
        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert "test_api" in data

        # 4. Reload manager from JSON
        mgr2 = SrvManager(srv_root=srv_root, registry_path=reg_file)
        assert mgr2.get_service("test_api") is not None

        # 5. Audit & Summary
        audit_rep = mgr2.audit_all()
        assert audit_rep["total_services"] >= 6

        summary = mgr2.get_summary()
        assert summary["total_services"] >= 6
        assert "www" in summary["protocol_breakdown"]

        # 6. Global helper functions
        from srv import register_service, get_service_path, list_services
        register_service("legacy_service", str(srv_root / "legacy"))
        assert get_service_path("legacy_service") is not None

        print("✓ SrvManager, registry persistence, and audit system verified.")
        return True


def test_cli() -> bool:
    print("\n" + "=" * 60)
    print("Test 8: CLI Execution (srv_ctl)")
    print("=" * 60)
    from srv.cli import main as cli_main

    # Test summary and list
    assert cli_main(["summary"]) == 0
    assert cli_main(["list"]) == 0
    assert cli_main(["audit"]) == 0

    print("✓ CLI commands executed successfully.")
    return True


def run_all_tests() -> bool:
    tests = [
        test_imports,
        test_fhs_validation,
        test_hierarchy_bootstrap_and_trees,
        test_protocols,
        test_permissions_and_security,
        test_backup_and_restore,
        test_srv_manager_and_persistence,
        test_cli,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            if t():
                passed += 1
            else:
                failed += 1
        except Exception as ex:
            print(f"✗ Exception in {t.__name__}: {ex}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} PASSED, {failed} FAILED (Total: {len(tests)})")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
