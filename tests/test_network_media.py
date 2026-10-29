"""Tests for UmerOS Network Media Management."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from media.network.network_share import (
    ShareProtocol, NetworkShare, ShareCredentials, ShareStatus, NetworkShareManager,
)
from media.network.network_mount import (
    mount_share, unmount_share, is_share_mounted, list_mounted_shares,
    set_simulation, clear_sim_mounts, NetworkMountResult,
)
from media.network.network_discovery import (
    NetworkBrowser, DiscoveredShare, discover_smb_shares, discover_nfs_exports,
)
from media.network.network_credentials import (
    CredentialStore, NetworkCredential, save_credential, load_credential, delete_credential,
)


class TestShareProtocol(unittest.TestCase):
    def test_display_names(self):
        self.assertEqual(ShareProtocol.SMB.display_name, "SMB/CIFS (Windows)")
        self.assertEqual(ShareProtocol.NFS.display_name, "NFS (Unix/Linux)")

    def test_default_ports(self):
        self.assertEqual(ShareProtocol.SMB.default_port, 445)
        self.assertEqual(ShareProtocol.NFS.default_port, 2049)
        self.assertEqual(ShareProtocol.SSHFS.default_port, 22)

    def test_mount_types(self):
        self.assertEqual(ShareProtocol.SMB.mount_type, "cifs")
        self.assertEqual(ShareProtocol.NFS.mount_type, "nfs")

    def test_uri_generation(self):
        share = NetworkShare(name="docs", protocol=ShareProtocol.SMB, host="192.168.1.10", path="/shared")
        self.assertEqual(share.uri, "//192.168.1.10/shared")
        nfs_share = NetworkShare(name="home", protocol=ShareProtocol.NFS, host="192.168.1.20", path="/home")
        self.assertEqual(nfs_share.uri, "192.168.1.20:/home")


class TestShareCredentials(unittest.TestCase):
    def test_to_mount_options_smb(self):
        creds = ShareCredentials(username="user", password="pass", domain="WORKGROUP")
        opts = creds.to_mount_options(ShareProtocol.SMB)
        self.assertIn("username=user", opts)
        self.assertIn("password=pass", opts)
        self.assertIn("domain=WORKGROUP", opts)

    def test_anonymous(self):
        creds = ShareCredentials(anonymous=True)
        opts = creds.to_mount_options(ShareProtocol.SMB)
        self.assertIn("guest", opts)

    def test_redacted(self):
        creds = ShareCredentials(username="user", password="secret")
        r = creds.redacted()
        self.assertEqual(r["password"], "***")
        self.assertEqual(r["username"], "user")


class TestNetworkShareManager(unittest.TestCase):
    def setUp(self):
        clear_sim_mounts()
        set_simulation(True)
        self.mgr = NetworkShareManager()

    def test_add_share(self):
        share = self.mgr.add_share("docs", ShareProtocol.SMB, "192.168.1.10", "/shared")
        self.assertEqual(share.name, "docs")
        self.assertEqual(self.mgr.share_count, 1)

    def test_duplicate_name_raises(self):
        self.mgr.add_share("docs", ShareProtocol.SMB, "192.168.1.10")
        with self.assertRaises(ValueError):
            self.mgr.add_share("docs", ShareProtocol.SMB, "192.168.1.10")

    def test_remove_share(self):
        self.mgr.add_share("docs", ShareProtocol.SMB, "192.168.1.10")
        self.assertTrue(self.mgr.remove_share("docs"))
        self.assertEqual(self.mgr.share_count, 0)

    def test_remove_nonexistent(self):
        self.assertFalse(self.mgr.remove_share("nonexistent"))

    def test_find_by_host(self):
        self.mgr.add_share("docs", ShareProtocol.SMB, "192.168.1.10")
        self.mgr.add_share("home", ShareProtocol.NFS, "192.168.1.20")
        results = self.mgr.find_by_host("192.168.1.10")
        self.assertEqual(len(results), 1)

    def test_find_by_protocol(self):
        self.mgr.add_share("docs", ShareProtocol.SMB, "192.168.1.10")
        self.mgr.add_share("home", ShareProtocol.NFS, "192.168.1.20")
        results = self.mgr.find_by_protocol(ShareProtocol.SMB)
        self.assertEqual(len(results), 1)

    def test_mount_unmount(self):
        self.mgr.add_share("docs", ShareProtocol.SMB, "192.168.1.10", "/shared")
        result = self.mgr.mount("docs")
        self.assertTrue(result.success)
        self.assertEqual(self.mgr.mounted_count, 1)
        result = self.mgr.unmount("docs")
        self.assertTrue(result.success)
        self.assertEqual(self.mgr.mounted_count, 0)

    def test_mount_nonexistent(self):
        result = self.mgr.mount("nonexistent")
        self.assertFalse(result.success)

    def test_to_dict(self):
        share = self.mgr.add_share("docs", ShareProtocol.SMB, "192.168.1.10")
        d = share.to_dict()
        self.assertEqual(d["name"], "docs")
        self.assertEqual(d["protocol"], "smb")


class TestNetworkMount(unittest.TestCase):
    def setUp(self):
        clear_sim_mounts()
        set_simulation(True)

    def test_mount_share(self):
        share = NetworkShare(name="test", protocol=ShareProtocol.SMB, host="192.168.1.10", path="/shared")
        result = mount_share(share)
        self.assertTrue(result.success)
        self.assertTrue(is_share_mounted(result.mount_point))

    def test_unmount_share(self):
        share = NetworkShare(name="test2", protocol=ShareProtocol.SMB, host="192.168.1.10", path="/shared")
        mount_share(share)
        result = unmount_share(share)
        self.assertTrue(result.success)
        self.assertFalse(is_share_mounted(share.mount_point))

    def test_list_mounted(self):
        share = NetworkShare(name="test3", protocol=ShareProtocol.SMB, host="192.168.1.10", path="/shared")
        mount_share(share)
        mounts = list_mounted_shares()
        self.assertTrue(len(mounts) > 0)

    def test_unmount_not_mounted(self):
        share = NetworkShare(name="test4", protocol=ShareProtocol.SMB, host="192.168.1.10", path="/shared")
        result = unmount_share(share)
        self.assertFalse(result.success)


class TestNetworkDiscovery(unittest.TestCase):
    def test_discover_smb(self):
        shares = discover_smb_shares("192.168.1.10")
        self.assertTrue(len(shares) > 0)
        self.assertTrue(any(s.name == "shared" for s in shares))

    def test_discover_nfs(self):
        exports = discover_nfs_exports("192.168.1.20")
        self.assertTrue(len(exports) > 0)

    def test_browser(self):
        browser = NetworkBrowser()
        smb = browser.discover_smb_shares("192.168.1.10")
        nfs = browser.discover_nfs_exports("192.168.1.20")
        self.assertTrue(len(smb) > 0)
        self.assertTrue(len(nfs) > 0)
        self.assertEqual(browser.discovered_count, len(smb) + len(nfs))

    def test_discovered_share_uri(self):
        share = DiscoveredShare(name="docs", host="192.168.1.10", protocol=ShareProtocol.SMB)
        self.assertEqual(share.uri, "//192.168.1.10/docs")

    def test_discover_all(self):
        browser = NetworkBrowser()
        all_shares = browser.discover_all("192.168.1.10")
        self.assertTrue(len(all_shares) >= 4)  # 3 SMB + 2 NFS (minus IPC$ filtered? no, included)


class TestNetworkCredentials(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = CredentialStore(Path(self.tmpdir))

    def test_save_load(self):
        cred = NetworkCredential(name="office", username="user", password="pass", host="192.168.1.10")
        self.assertTrue(self.store.save(cred))
        loaded = self.store.load("office")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.username, "user")
        self.assertEqual(loaded.password, "pass")

    def test_delete(self):
        cred = NetworkCredential(name="office", username="user", password="pass", host="192.168.1.10")
        self.store.save(cred)
        self.assertTrue(self.store.delete("office"))
        self.assertIsNone(self.store.load("office"))

    def test_list(self):
        cred = NetworkCredential(name="office", username="user", host="192.168.1.10")
        self.store.save(cred)
        creds = self.store.list_credentials()
        self.assertEqual(len(creds), 1)

    def test_find_by_host(self):
        cred = NetworkCredential(name="office", username="user", host="192.168.1.10")
        self.store.save(cred)
        results = self.store.find_by_host("192.168.1.10")
        self.assertEqual(len(results), 1)

    def test_convenience_functions(self):
        cred = NetworkCredential(name="test", username="admin", password="secret", host="10.0.0.1")
        save_credential(cred, Path(self.tmpdir))
        loaded = load_credential("test", Path(self.tmpdir))
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.username, "admin")
        delete_credential("test", Path(self.tmpdir))
        self.assertIsNone(load_credential("test", Path(self.tmpdir)))

    def test_redacted(self):
        cred = NetworkCredential(name="test", username="user", password="secret")
        r = cred.redacted()
        self.assertEqual(r["password"], "***")


if __name__ == "__main__":
    unittest.main()