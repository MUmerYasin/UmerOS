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
pytest test suite for UmerOS /srv filesystem hierarchy.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from srv import (
    FHSValidator,
    OrganizationScheme,
    StandardProtocol,
    SrvHierarchy,
    ServiceRecord,
    ServiceConfig,
    ServiceStatus,
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


@pytest.fixture
def temp_srv():
    with tempfile.TemporaryDirectory() as tmpdir:
        srv_root = Path(tmpdir) / "srv"
        srv_root.mkdir(parents=True, exist_ok=True)
        yield srv_root


def test_fhs_validation(temp_srv):
    www = temp_srv / "www"
    www.mkdir()
    res = FHSValidator.validate_service_path(www, temp_srv)
    assert res.is_compliant

    bin_dir = temp_srv / "bin"
    bin_dir.mkdir()
    res_bin = FHSValidator.validate_service_path(bin_dir, temp_srv)
    assert not res_bin.is_compliant


def test_hierarchy_bootstrap(temp_srv):
    hier = SrvHierarchy(temp_srv)
    created = hier.bootstrap()
    assert (temp_srv / "www" / "html").exists()
    assert (temp_srv / "ftp" / "pub").exists()
    assert (temp_srv / "git" / "repositories").exists()
    assert (temp_srv / "rsync" / "shares").exists()
    assert (temp_srv / "tftp" / "boot").exists()


def test_service_tree_creation(temp_srv):
    hier = SrvHierarchy(temp_srv)
    tree = hier.create_service_tree("api", StandardProtocol.WWW, subdirs=["data", "cgi-bin", "uploads"])
    assert tree.base_dir.exists()
    assert tree.data_dir.exists()
    assert tree.cgi_dir.exists()
    assert tree.upload_dir.exists()


def test_protocol_handlers(temp_srv):
    # WWW
    vhost = WWWServiceHandler.setup_vhost(temp_srv / "www", "example.local")
    assert (vhost["document_root"] / "index.html").exists()

    # FTP
    ftp_tree = FTPServiceHandler.setup_ftp_tree(temp_srv / "ftp")
    assert (ftp_tree["pub"] / "README.txt").exists()

    # Git
    repo = GitServiceHandler.create_bare_repository(temp_srv / "git", "project.git")
    assert (repo / "HEAD").exists()

    # Rsync
    conf = RsyncServiceHandler.generate_rsyncd_conf(temp_srv / "rsync", "mirrors")
    assert "[mirrors]" in conf

    # TFTP
    pxe = TFTPServiceHandler.setup_pxe_boot(temp_srv / "tftp")
    assert (pxe["pxelinux.cfg"] / "default").exists()


def test_backup_restore(temp_srv):
    backup_dir = temp_srv / ".backups"
    bm = SrvBackupManager(backup_dir=backup_dir, srv_root=temp_srv)

    service_dir = temp_srv / "site1"
    service_dir.mkdir()
    (service_dir / "file.txt").write_text("content", encoding="utf-8")

    archive = bm.create_backup(service_dir, archive_format="tar.gz")
    assert archive.exists()

    restore_target = temp_srv / "restored"
    restore_target.mkdir()
    res = bm.restore_backup(archive, target_root=restore_target)
    assert res["success"]
    assert (restore_target / "site1" / "file.txt").read_text(encoding="utf-8") == "content"


def test_srv_manager(temp_srv):
    reg_file = temp_srv / "registry.json"
    mgr = SrvManager(srv_root=temp_srv, registry_path=reg_file)

    rec = mgr.create_service("portal", protocol=StandardProtocol.WWW)
    assert rec.name == "portal"
    assert mgr.get_service("portal") is not None

    summary = mgr.get_summary()
    assert summary["total_services"] >= 1

    audit = mgr.audit_all()
    assert audit["total_services"] >= 1


def test_restore_refuses_traversal_archive(temp_srv):
    """H265/H266: a backup archive whose member escapes via '../' must not
    write outside the restore target (filter='data' refuses the slip)."""
    import tarfile

    bm = SrvBackupManager(backup_dir=temp_srv / ".backups", srv_root=temp_srv)
    evil_archive = temp_srv / "evil.tar.gz"
    outside = temp_srv.parent / "EVIL_ESCAPE.txt"
    with tarfile.open(evil_archive, "w:gz") as tar:
        mf = tarfile.TarInfo("manifest.json")
        mf.size = 0
        tar.addfile(mf)
        # A member that tries to walk above the extraction directory.
        bad = tarfile.TarInfo("../EVIL_ESCAPE.txt")
        bad.size = 0
        tar.addfile(bad)

    # filter="data" refuses the '../' member -> restore fails closed.
    with pytest.raises(Exception):
        bm.restore_backup(evil_archive, target_root=temp_srv / "restored")

    assert not outside.exists(), "CRITICAL: backup restore path-traversal succeeded!"
