"""Tests for UmerOS Tools subsystem."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.system_info import get_system_info, get_cpu_info, get_memory_info, SystemInfo
from tools.disk_tools import DiskManager, get_disk_usage, list_partitions
from tools.network_tools import NetworkDiagnostics, ping_host, dns_lookup
from tools.process_tools import ProcessManager, list_processes, get_process_info
from tools.installer import install_umer_os, verify_installation, get_install_info


class TestSystemInfo(unittest.TestCase):
    def test_get_system_info(self):
        info = get_system_info()
        self.assertEqual(info.os_name, "UmerOS")
        self.assertIsNotNone(info.cpu)
        self.assertIsNotNone(info.memory)

    def test_get_cpu_info(self):
        cpu = get_cpu_info()
        self.assertGreaterEqual(cpu.cores, 1)
        self.assertIsNotNone(cpu.architecture)

    def test_get_memory_info(self):
        mem = get_memory_info()
        self.assertGreaterEqual(mem.total_bytes, 0)

    def test_to_dict(self):
        info = get_system_info()
        d = info.to_dict()
        self.assertIn("os_name", d)
        self.assertIn("cpu", d)
        self.assertIn("memory", d)


class TestDiskTools(unittest.TestCase):
    def test_get_disk_usage(self):
        usage = get_disk_usage("/")
        self.assertIn("total", usage)
        self.assertIn("used", usage)
        self.assertIn("free", usage)

    def test_disk_manager_scan(self):
        mgr = DiskManager()
        parts = mgr.scan()
        self.assertIsInstance(parts, list)

    def test_list_partitions(self):
        parts = list_partitions()
        self.assertIsInstance(parts, list)


class TestNetworkTools(unittest.TestCase):
    def test_dns_lookup_localhost(self):
        result = dns_lookup("localhost")
        self.assertTrue(len(result.addresses) > 0 or result.error is not None)

    def test_network_diagnostics_ping(self):
        nd = NetworkDiagnostics()
        result = nd.ping("127.0.0.1", count=1)
        self.assertIsInstance(result.success, bool)

    def test_check_port(self):
        nd = NetworkDiagnostics()
        # Port 0 should not be open
        result = nd.check_port("127.0.0.1", 1, timeout=1.0)
        self.assertIsInstance(result, bool)


class TestProcessTools(unittest.TestCase):
    def test_list_processes(self):
        procs = list_processes()
        self.assertTrue(len(procs) > 0)

    def test_process_manager_scan(self):
        mgr = ProcessManager()
        procs = mgr.scan()
        self.assertTrue(len(procs) > 0)
        self.assertGreater(mgr.process_count, 0)

    def test_get_process_info(self):
        info = get_process_info(1)
        # May or may not exist depending on platform
        self.assertTrue(info is None or isinstance(info.pid, int))


class TestInstaller(unittest.TestCase):
    def test_verify_nonexistent(self):
        result = verify_installation("/nonexistent/path/umeros")
        self.assertFalse(result.valid)

    def test_get_install_info(self):
        info = get_install_info("/nonexistent/path/umeros")
        self.assertFalse(info["exists"])

    def test_install_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = install_umer_os(target_dir=os.path.join(tmpdir, "umeros"), dry_run=True)
            self.assertTrue(result.success or len(result.errors) == 0)


if __name__ == "__main__":
    unittest.main()