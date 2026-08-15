"""Comprehensive tests for the UmerOS /proc virtual filesystem."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from proc.kernel_adapter import KernelAdapter, KernelRingLog, LoadAvgTracker
from proc.nodes import ProcFile, ProcDir, ProcSymlink
from proc.procfs import ProcFileSystem
from proc.pid_entries import build_pid_dir, pid_dir_signature


# ── KernelRingLog ──────────────────────────────────────────────────

class TestKernelRingLog(unittest.TestCase):
    def test_capacity_bounded(self):
        log = KernelRingLog(capacity=5)
        for i in range(10):
            log.append(f"line-{i}")
        self.assertEqual(len(log), 5)
        self.assertIn("line-5", log.tail())

    def test_tail_default(self):
        log = KernelRingLog(capacity=10)
        for i in range(3):
            log.append(f"x{i}")
        t = log.tail()
        self.assertEqual(t.count("\n"), 3)

    def test_tail_n(self):
        log = KernelRingLog(capacity=10)
        for i in range(10):
            log.append(f"x{i}")
        t = log.tail(2)
        lines = [l for l in t.splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn("x8", lines[0])

    def test_clear(self):
        log = KernelRingLog(capacity=10)
        log.append("data")
        log.clear()
        self.assertEqual(len(log), 0)
        self.assertEqual(log.tail(), "")


# ── LoadAvgTracker ─────────────────────────────────────────────────

class TestLoadAvgTracker(unittest.TestCase):
    def test_initial_values(self):
        t = LoadAvgTracker()
        one, five, fifteen = t.values()
        self.assertEqual(one, 0.0)
        self.assertEqual(five, 0.0)
        self.assertEqual(fifteen, 0.0)

    def test_update_increases(self):
        t = LoadAvgTracker()
        t.update(3, 5)
        one, _, _ = t.values()
        self.assertGreater(one, 0.0)

    def test_total_threads(self):
        t = LoadAvgTracker()
        t.update(1, 10)
        self.assertEqual(t.total_threads, 10)


# ── ProcFile ────────────────────────────────────────────────────────

class TestProcFile(unittest.TestCase):
    def test_static_content(self):
        f = ProcFile("test", content="hello")
        self.assertEqual(f.read(), "hello")

    def test_dynamic_content(self):
        f = ProcFile("test", read=lambda: "42")
        self.assertEqual(f.read(), "42")

    def test_size_zero_by_default(self):
        f = ProcFile("test", content="hello world")
        self.assertEqual(f.stat_size(), 0)

    def test_explicit_size(self):
        f = ProcFile("test", content="abc", size_zero=False)
        self.assertEqual(f.stat_size(), 3)

    def test_virtual_size(self):
        f = ProcFile("kcore", content="x", virtual_size=1024)
        self.assertEqual(f.stat_size(), 1024)

    def test_read_updates_atime(self):
        f = ProcFile("test", content="x")
        f.read()
        self.assertGreater(f.atime, 0)

    def test_write_read_only_raises(self):
        f = ProcFile("test", content="x")
        with self.assertRaises(PermissionError):
            f.write("data")

    def test_write_writable(self):
        received = []
        f = ProcFile("test", write=lambda text: received.append(text))
        f.write("data")
        self.assertEqual(received, ["data"])

    def test_writable_property(self):
        self.assertFalse(ProcFile("r").writable)
        self.assertTrue(ProcFile("w", write=lambda t: None).writable)

    def test_write_accepts_bytes(self):
        f = ProcFile("test", write=lambda text: None)
        f.write(b"bytes data")
        self.assertGreater(f.mtime, 0)


# ── ProcDir ────────────────────────────────────────────────────────

class TestProcDir(unittest.TestCase):
    def test_add_and_get(self):
        d = ProcDir("root")
        f = d.add(ProcFile("a"))
        self.assertIs(d.get("a"), f)

    def test_remove(self):
        d = ProcDir("root")
        d.add(ProcFile("a"))
        d.remove("a")
        self.assertIsNone(d.get("a"))

    def test_names_sorted(self):
        d = ProcDir("root")
        d.add(ProcFile("c"))
        d.add(ProcFile("a"))
        d.add(ProcFile("b"))
        self.assertEqual(d.names(), ["a", "b", "c"])

    def test_stat_size(self):
        d = ProcDir("root")
        self.assertEqual(d.stat_size(), 4096)


# ── ProcSymlink ───────────────────────────────────────────────────

class TestProcSymlink(unittest.TestCase):
    def test_static_target(self):
        s = ProcSymlink("self", "1000")
        self.assertEqual(s.readlink(), "1000")

    def test_callable_target(self):
        s = ProcSymlink("self", lambda: "2000")
        self.assertEqual(s.readlink(), "2000")

    def test_stat_size(self):
        s = ProcSymlink("cwd", "/home/umer")
        self.assertEqual(s.stat_size(), len("/home/umer"))


# ── KernelAdapter (standalone, no kernel) ──────────────────────────

class TestKernelAdapterStandalone(unittest.TestCase):
    def setUp(self):
        self.adapter = KernelAdapter()

    def test_tasks_empty(self):
        self.assertEqual(self.adapter.tasks(), [])

    def test_pids_empty(self):
        self.assertEqual(self.adapter.pids(), [])

    def test_current_pid_no_tasks(self):
        self.assertEqual(self.adapter.current_pid(), 0)

    def test_task_pid_0_always_exists(self):
        t = self.adapter.task(0)
        self.assertIsNotNone(t)
        self.assertEqual(t["name"], "umer_kernel")
        self.assertEqual(t["state"], "RUNNING")

    def test_memory_defaults(self):
        mem = self.adapter.memory()
        self.assertEqual(mem["total"], 4 * 1024 ** 3)
        self.assertGreater(mem["free"], 0)
        self.assertGreater(mem["total_kib"], 0)

    def test_uptime(self):
        up = self.adapter.uptime()
        self.assertGreater(up, 0)

    def test_filesystems(self):
        fs = self.adapter.filesystems()
        names = [f[1] for f in fs]
        self.assertIn("proc", names)
        self.assertIn("qfs", names)

    def test_mounts(self):
        mounts = self.adapter.mounts()
        mps = [m["mountpoint"] for m in mounts]
        self.assertIn("/", mps)
        self.assertIn("/proc", mps)

    def test_modules(self):
        mods = self.adapter.modules()
        names = [m["name"] for m in mods]
        self.assertIn("qfs", names)
        self.assertIn("procfs", names)

    def test_char_devices(self):
        devs = self.adapter.char_devices()
        names = [d[2] for d in devs]
        self.assertIn("null", names)
        self.assertIn("random", names)

    def test_block_devices(self):
        devs = self.adapter.block_devices()
        names = [d[2] for d in devs]
        self.assertIn("qfs_root", names)

    def test_net_interfaces(self):
        ifaces = self.adapter.net_interfaces()
        names = [i["name"] for i in ifaces]
        self.assertIn("lo", names)
        self.assertIn("quantum0", names)

    def test_loadavg_tracker(self):
        self.assertIsNotNone(self.adapter.loadavg)

    def test_kmsg(self):
        self.adapter.kmsg.append("test message")
        self.assertIn("test message", self.adapter.kmsg.tail())

    def test_taint_summary(self):
        self.assertIsInstance(self.adapter.taint_summary(), str)

    def test_softirq_counts_empty(self):
        self.assertEqual(self.adapter.softirq_counts(), {})

    def test_ipc_info_empty(self):
        info = self.adapter.ipc_info()
        self.assertEqual(info["queues"], {})
        self.assertEqual(info["channels"], {})

    def test_state_letter(self):
        self.assertEqual(KernelAdapter.state_letter("RUNNING"), "R")
        self.assertEqual(KernelAdapter.state_letter("READY"), "S")
        self.assertEqual(KernelAdapter.state_letter("BLOCKED"), "D")
        self.assertEqual(KernelAdapter.state_letter("DONE"), "Z")


# ── KernelAdapter (with mock kernel) ──────────────────────────────

class _MockTask:
    def __init__(self, pid, name, state="READY", priority=0.5, cpu_time=1.0):
        self.pid = pid
        self.name = name
        self.state = state
        self.priority = priority
        self.cpu_time = cpu_time
        self.parent_pid = None


class _MockScheduler:
    def __init__(self, tasks):
        self._tasks = tasks


class _MockMemory:
    PAGE_SIZE = 4096

    def stats(self):
        return {"total_pages": 1048576, "free_pages": 524288,
                "page_size": 4096, "live_allocations": 3}


class _MockKernel:
    def __init__(self):
        self.scheduler = _MockScheduler({
            1000: _MockTask(1000, "init", "RUNNING", 1.0, 5.0),
            1001: _MockTask(1001, "shell", "READY", 0.8, 2.0),
            1002: _MockTask(1002, "logger", "BLOCKED", 0.5, 0.5),
        })
        self.memory = _MockMemory()
        self._boot_time = 0.0  # will be set by adapter
        self._LOSTFOUND_AVAILABLE = False


class TestKernelAdapterWithKernel(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)

    def test_tasks_from_kernel(self):
        tasks = self.adapter.tasks()
        names = [t["name"] for t in tasks]
        self.assertIn("init", names)
        self.assertIn("shell", names)
        self.assertIn("logger", names)

    def test_pids(self):
        pids = self.adapter.pids()
        self.assertIn(1000, pids)
        self.assertIn(1001, pids)

    def test_task_detail(self):
        t = self.adapter.task(1000)
        self.assertEqual(t["name"], "init")
        self.assertEqual(t["state"], "RUNNING")

    def test_memory_from_stats(self):
        mem = self.adapter.memory()
        self.assertEqual(mem["total"], 1048576 * 4096)
        self.assertEqual(mem["free"], 524288 * 4096)
        self.assertEqual(mem["live_allocations"], 3)

    def test_current_pid_with_tasks(self):
        self.assertEqual(self.adapter.current_pid(), 1000)

    def test_state_letter_integration(self):
        self.assertEqual(KernelAdapter.state_letter("RUNNING"), "R")
        self.assertEqual(KernelAdapter.state_letter("BLOCKED"), "D")


# ── ProcFileSystem (core) ─────────────────────────────────────────

class TestProcFileSystemStandalone(unittest.TestCase):
    def setUp(self):
        self.adapter = KernelAdapter()
        self.fs = ProcFileSystem(self.adapter)

    # ── top-level listing ────────────────────────────────────────

    def test_root_has_expected_entries(self):
        names = self.fs.top_level_names()
        for expected in ["cpuinfo", "meminfo", "stat", "uptime", "version",
                        "loadavg", "interrupts", "devices", "modules", "mounts",
                        "filesystems", "partitions", "swaps", "kmsg", "ksyms",
                        "slabinfo", "net", "sys", "sysvipc", "tty", "irq",
                        "bus", "driver", "ide", "scsi", "parport", "self",
                        "ioports", "iomem", "dma", "fb", "rtc"]:
            self.assertIn(expected, names, f"missing /proc/{expected}")

    def test_no_pid_dirs_when_no_tasks(self):
        names = self.fs.top_level_names()
        pid_names = [n for n in names if n.isdigit()]
        self.assertEqual(pid_names, [])

    def test_self_symlink(self):
        target = self.fs.readlink("/proc/self")
        self.assertEqual(target, "0")

    # ── system file reads ────────────────────────────────────────

    def test_cpuinfo(self):
        data = self.fs.read("/proc/cpuinfo")
        self.assertIn("processor", data)
        self.assertIn("QuantumGenuine", data)
        self.assertIn("3.40GHz", data)

    def test_meminfo(self):
        data = self.fs.read("/proc/meminfo")
        self.assertIn("MemTotal", data)
        self.assertIn("MemFree", data)
        self.assertIn("SwapTotal", data)

    def test_uptime(self):
        data = self.fs.read("/proc/uptime")
        parts = data.strip().split()
        self.assertEqual(len(parts), 2)
        self.assertGreater(float(parts[0]), 0)

    def test_version(self):
        data = self.fs.read("/proc/version")
        self.assertIn("UmerOS", data)
        self.assertIn("gcc", data)

    def test_loadavg(self):
        data = self.fs.read("/proc/loadavg")
        parts = data.strip().split()
        self.assertGreaterEqual(len(parts), 5)
        self.assertIn("/", parts[-1])

    def test_stat(self):
        data = self.fs.read("/proc/stat")
        self.assertIn("cpu ", data)
        self.assertIn("cpu0 ", data)
        self.assertIn("cpu1 ", data)
        self.assertIn("btime", data)
        self.assertIn("intr", data)

    def test_interrupts(self):
        data = self.fs.read("/proc/interrupts")
        self.assertIn("CPU0", data)
        self.assertIn("CPU1", data)
        self.assertIn("NMI", data)
        self.assertIn("LOC", data)
        self.assertIn("ERR", data)

    def test_ioports(self):
        data = self.fs.read("/proc/ioports")
        self.assertIn("dma1", data)
        self.assertIn("timer0", data)

    def test_iomem(self):
        data = self.fs.read("/proc/iomem")
        self.assertIn("System RAM", data)
        self.assertIn("IOAPIC", data)
        self.assertIn("Local APIC", data)

    def test_devices(self):
        data = self.fs.read("/proc/devices")
        self.assertIn("Character devices", data)
        self.assertIn("null", data)
        self.assertIn("Block devices", data)

    def test_dma(self):
        data = self.fs.read("/proc/dma")
        self.assertIn("cascade", data)

    def test_filesystems(self):
        data = self.fs.read("/proc/filesystems")
        self.assertIn("proc", data)
        self.assertIn("qfs", data)

    def test_mounts(self):
        data = self.fs.read("/proc/mounts")
        self.assertIn("/ qfs", data)
        self.assertIn("/proc proc", data)

    def test_partitions(self):
        data = self.fs.read("/proc/partitions")
        self.assertIn("major", data)
        self.assertIn("minor", data)
        self.assertIn("blocks", data)
        self.assertIn("name", data)

    def test_swaps(self):
        data = self.fs.read("/proc/swaps")
        self.assertIn("qswap", data)

    def test_modules(self):
        data = self.fs.read("/proc/modules")
        self.assertIn("qfs", data)
        self.assertIn("Live", data)

    def test_slabinfo(self):
        data = self.fs.read("/proc/slabinfo")
        self.assertIn("slabinfo - version: 2.1", data)
        self.assertIn("umer_inode_cache", data)

    def test_kmsg(self):
        data = self.fs.read("/proc/kmsg")
        self.assertIn("procfs: kernel adapter online", data)

    def test_ksyms(self):
        data = self.fs.read("/proc/ksyms")
        self.assertIn("umer_kernel_text_start", data)
        self.assertIn("procfs_read", data)

    def test_rtc(self):
        data = self.fs.read("/proc/rtc")
        self.assertIn("rtc_time", data)
        self.assertIn("rtc_date", data)

    def test_mtrr(self):
        data = self.fs.read("/proc/mtrr")
        self.assertIn("write-back", data)
        self.assertIn("write-combining", data)

    def test_cmdline(self):
        data = self.fs.read("/proc/cmdline")
        self.assertIn("BOOT_IMAGE", data)

    def test_kcore(self):
        data = self.fs.read("/proc/kcore")
        self.assertIn("UmerOS kcore", data)
        st = self.fs.stat("/proc/kcore")
        self.assertGreater(st["size"], 0)

    def test_fb(self):
        data = self.fs.read("/proc/fb")
        self.assertIn("UmerGPU", data)

    def test_locks(self):
        data = self.fs.read("/proc/locks")
        self.assertEqual(data.strip(), "")

    def test_misc(self):
        data = self.fs.read("/proc/misc")
        self.assertIn("qcrypto", data)

    def test_execdomains(self):
        data = self.fs.read("/proc/execdomains")
        self.assertGreater(len(data.strip()), 0)

    # ── subdirectory reads ─────────────────────────────────────

    def test_net_dev(self):
        data = self.fs.read("/proc/net/dev")
        self.assertIn("Inter-|   Receive", data)
        self.assertIn("quantum0", data)

    def test_net_tcp(self):
        data = self.fs.read("/proc/net/tcp")
        self.assertIn("local_address", data)
        self.assertIn("rem_address", data)

    def test_net_udp(self):
        data = self.fs.read("/proc/net/udp")
        self.assertIn("sl", data)

    def test_net_route(self):
        data = self.fs.read("/proc/net/route")
        self.assertIn("Iface", data)

    def test_net_arp(self):
        data = self.fs.read("/proc/net/arp")
        self.assertIn("IP address", data)

    def test_net_unix(self):
        data = self.fs.read("/proc/net/unix")
        self.assertIn("Num", data)

    def test_net_wireless(self):
        data = self.fs.read("/proc/net/wireless")
        self.assertIn("Inter-", data)

    def test_net_sockstat(self):
        data = self.fs.read("/proc/net/sockstat")
        self.assertIn("TCP:", data)
        self.assertIn("UDP:", data)

    def test_net_icmp(self):
        data = self.fs.read("/proc/net/icmp")
        self.assertIn("Icmp: InMsgs", data)

    def test_net_snmp(self):
        data = self.fs.read("/proc/net/snmp")
        self.assertIn("Ip:", data)
        self.assertIn("Tcp:", data)

    def test_net_if_inet6(self):
        data = self.fs.read("/proc/net/if_inet6")
        self.assertIn("00000001", data)

    def test_net_tcp6(self):
        data = self.fs.read("/proc/net/tcp6")
        self.assertIn("local_address", data)

    def test_net_udp6(self):
        data = self.fs.read("/proc/net/udp6")
        self.assertIn("local_address", data)

    def test_net_rpc(self):
        data = self.fs.read("/proc/net/rpc/nfs")
        self.assertIn("proc", data)

    def test_net_bond0(self):
        data = self.fs.read("/proc/net/bond0/slaves")
        self.assertEqual(data.strip(), "")

    def test_sysvipc_msg(self):
        data = self.fs.read("/proc/sysvipc/msg")
        self.assertIn("key", data)

    def test_sysvipc_sem(self):
        data = self.fs.read("/proc/sysvipc/sem")
        self.assertIn("key", data)

    def test_sysvipc_shm(self):
        data = self.fs.read("/proc/sysvipc/shm")
        self.assertIn("key", data)

    def test_tty_drivers(self):
        data = self.fs.read("/proc/tty/drivers")
        self.assertIn("serconsole", data)

    def test_tty_ldiscs(self):
        data = self.fs.read("/proc/tty/ldiscs")
        self.assertIn("n_tty", data)

    def test_tty_driver_serial(self):
        data = self.fs.read("/proc/tty/driver/serial/serial0")
        self.assertIn("uart:16550A", data)

    def test_irq_dir_listing(self):
        names = self.fs.list("/proc/irq")
        self.assertIn("0", names)
        self.assertIn("1", names)
        self.assertIn("8", names)

    def test_irq_affinity(self):
        data = self.fs.read("/proc/irq/0/smp_affinity")
        self.assertEqual(data.strip(), "3")

    def test_bus_pci(self):
        data = self.fs.read("/proc/bus/pci/devices")
        self.assertIn("Quantum Bridge", data)

    def test_bus_usb(self):
        data = self.fs.read("/proc/bus/usb/devices")
        self.assertIn("qHCI", data)

    def test_driver_rtc(self):
        data = self.fs.read("/proc/driver/rtc")
        self.assertIn("rtc_time", data)

    def test_ide_dir_listing(self):
        names = self.fs.list("/proc/ide")
        self.assertIn("ide0", names)

    def test_ide_hda(self):
        data = self.fs.read("/proc/ide/ide0/hda/model")
        self.assertIn("QUANTUM", data)

    def test_scsi(self):
        data = self.fs.read("/proc/scsi/scsi")
        self.assertIn("QuantumSSD", data)

    def test_parport(self):
        data = self.fs.read("/proc/parport/0/hardware")
        self.assertIn("base", data)

    # ── /proc/sys reads ─────────────────────────────────────────

    def test_sys_kernel_hostname(self):
        data = self.fs.read("/proc/sys/kernel/hostname")
        self.assertEqual(data.strip(), "umeros-node1")

    def test_sys_kernel_osrelease(self):
        data = self.fs.read("/proc/sys/kernel/osrelease")
        self.assertEqual(data.strip(), "2.1.0-quantum")

    def test_sys_kernel_ostype(self):
        data = self.fs.read("/proc/sys/kernel/ostype")
        self.assertEqual(data.strip(), "UmerOS")

    def test_sys_fs_file_max(self):
        data = self.fs.read("/proc/sys/fs/file-max")
        self.assertGreater(len(data.strip()), 0)

    def test_sys_vm_overcommit(self):
        data = self.fs.read("/proc/sys/vm/overcommit_memory")
        self.assertIsNotNone(data)

    def test_sys_net_core_somaxconn(self):
        data = self.fs.read("/proc/sys/net/core/somaxconn")
        self.assertIsNotNone(data)

    def test_sys_net_ipv4_ip_forward(self):
        data = self.fs.read("/proc/sys/net/ipv4/ip_forward")
        self.assertIsNotNone(data)

    def test_sys_dev_cdrom_info(self):
        data = self.fs.read("/proc/sys/dev/cdrom/info")
        self.assertIn("qcd0", data)

    def test_sys_sunrpc_debug(self):
        data = self.fs.read("/proc/sys/sunrpc/debug")
        self.assertIn("0", data)

    # ── error handling ───────────────────────────────────────────

    def test_read_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.fs.read("/proc/nonexistent")

    def test_read_dir_raises_isdir(self):
        with self.assertRaises(IsADirectoryError):
            self.fs.read("/proc/net")

    def test_write_read_only_raises(self):
        with self.assertRaises(PermissionError):
            self.fs.write("/proc/meminfo", "bogus")

    def test_write_dir_raises(self):
        with self.assertRaises(IsADirectoryError):
            self.fs.write("/proc/net", "data")

    def test_list_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.fs.list("/proc/no_such_dir")

    def test_stat_nonexistent(self):
        self.assertIsNone(self.fs.stat("/proc/no_such_file"))

    def test_readlink_non_file(self):
        with self.assertRaises(ValueError):
            self.fs.readlink("/proc/cpuinfo")

    def test_stat_file(self):
        st = self.fs.stat("/proc/cpuinfo")
        self.assertIsNotNone(st)
        self.assertEqual(st["size"], 0)
        self.assertEqual(st["owner"], "root")
        self.assertEqual(st["is_dir"], False)

    def test_stat_dir(self):
        st = self.fs.stat("/proc/net")
        self.assertIsNotNone(st)
        self.assertEqual(st["size"], 4096)
        self.assertEqual(st["is_dir"], True)

    def test_stat_symlink(self):
        st = self.fs.stat("/proc/self")
        self.assertIsNotNone(st)
        self.assertEqual(st["is_symlink"], True)
        self.assertGreater(st["size"], 0)

    def test_exists_true(self):
        self.assertTrue(self.fs.exists("/proc/meminfo"))

    def test_exists_false(self):
        self.assertFalse(self.fs.exists("/proc/nope"))

    def test_list_dir(self):
        names = self.fs.list("/proc/net")
        self.assertIn("tcp", names)
        self.assertIn("udp", names)
        self.assertIn("dev", names)

    def test_list_file_returns_name(self):
        result = self.fs.list("/proc/cpuinfo")
        self.assertEqual(result, ["cpuinfo"])

    def test_read_path_with_leading_proc(self):
        data = self.fs.read("/proc/cpuinfo")
        data2 = self.fs.read("proc/cpuinfo")
        self.assertEqual(data, data2)

    def test_list_path_with_leading_proc(self):
        names1 = self.fs.list("/proc")
        names2 = self.fs.list("proc")
        self.assertEqual(names1, names2)


# ── ProcFileSystem with mock kernel (PID dirs) ──────────────────

class TestProcFileSystemWithTasks(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)

    def test_pid_dirs_appear(self):
        names = self.fs.top_level_names()
        self.assertIn("1000", names)
        self.assertIn("1001", names)
        self.assertIn("1002", names)

    def test_pid_dir_listing(self):
        entries = self.fs.list("/proc/1000")
        self.assertIn("cmdline", entries)
        self.assertIn("status", entries)
        self.assertIn("stat", entries)
        self.assertIn("fd", entries)
        self.assertIn("cwd", entries)
        self.assertIn("exe", entries)

    def test_pid_cmdline(self):
        data = self.fs.read("/proc/1000/cmdline")
        self.assertIn("/usr/bin/init", data)

    def test_pid_comm(self):
        data = self.fs.read("/proc/1000/comm")
        self.assertEqual(data.strip(), "init")

    def test_pid_status(self):
        data = self.fs.read("/proc/1000/status")
        self.assertIn("Name:", data)
        self.assertIn("Pid:\t1000", data)
        self.assertIn("State:\tR", data)
        self.assertIn("VmSize:", data)
        self.assertIn("VmRSS:", data)

    def test_pid_stat(self):
        data = self.fs.read("/proc/1000/stat")
        self.assertIn("(init)", data)
        self.assertIn("R", data.split()[2])

    def test_pid_statm(self):
        data = self.fs.read("/proc/1000/statm")
        parts = data.strip().split()
        self.assertEqual(len(parts), 7)
        self.assertGreater(int(parts[0]), 0)

    def test_pid_environ(self):
        data = self.fs.read("/proc/1000/environ")
        self.assertIn("HOME=/home/umer", data)
        self.assertIn("PATH=/usr/local/sbin", data)

    def test_pid_maps(self):
        data = self.fs.read("/proc/1000/maps")
        self.assertIn("/usr/bin/init", data)
        self.assertIn("[heap]", data)
        self.assertIn("[stack]", data)

    def test_pid_cwd_symlink(self):
        target = self.fs.readlink("/proc/1000/cwd")
        self.assertEqual(target, "/home/umer")

    def test_pid_exe_symlink(self):
        target = self.fs.readlink("/proc/1000/exe")
        self.assertEqual(target, "/usr/bin/init")

    def test_pid_root_symlink(self):
        target = self.fs.readlink("/proc/1000/root")
        self.assertEqual(target, "/")

    def test_pid_fd_listing(self):
        entries = self.fs.list("/proc/1000/fd")
        self.assertIn("0", entries)
        self.assertIn("1", entries)
        self.assertIn("2", entries)

    def test_pid_fd_symlinks(self):
        target = self.fs.readlink("/proc/1000/fd/0")
        self.assertEqual(target, "/dev/null")

    def test_pid_io(self):
        data = self.fs.read("/proc/1000/io")
        self.assertIn("rchar:", data)
        self.assertIn("wchar:", data)

    def test_pid_cpu(self):
        data = self.fs.read("/proc/1000/cpu")
        self.assertIn("cpu", data)

    def test_pid_oom_score_adj_writable(self):
        self.fs.write("/proc/1000/oom_score_adj", "500")
        data = self.fs.read("/proc/1000/oom_score_adj")
        self.assertEqual(data.strip(), "500")

    def test_pid_oom_score_adj_clamp(self):
        self.fs.write("/proc/1000/oom_score_adj", "9999")
        data = self.fs.read("/proc/1000/oom_score_adj")
        self.assertLessEqual(int(data.strip()), 1000)

    def test_pid_mem(self):
        data = self.fs.read("/proc/1000/mem")
        self.assertIn("memory image", data)

    def test_pid_cgroup(self):
        data = self.fs.read("/proc/1000/cgroup")
        self.assertEqual(data.strip(), "0::/")

    def test_pid_sched(self):
        data = self.fs.read("/proc/1000/sched")
        self.assertIn("init", data)

    def test_nonexistent_pid(self):
        with self.assertRaises(FileNotFoundError):
            self.fs.read("/proc/99999/status")

    def test_meminfo_updates_with_tasks(self):
        data = self.fs.read("/proc/meminfo")
        self.assertIn("MemTotal", data)


# ── /proc/sys write tests ──────────────────────────────────────────

class TestSysctlWrites(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)

    def test_hostname_write_read(self):
        self.fs.write("/proc/sys/kernel/hostname", "newhost")
        data = self.fs.read("/proc/sys/kernel/hostname")
        self.assertEqual(data.strip(), "newhost")

    def test_hostname_write_accepts_newline(self):
        self.fs.write("/proc/sys/kernel/hostname", "myhost\n")
        self.assertEqual(
            self.fs.read("/proc/sys/kernel/hostname").strip(), "myhost")

    def test_readonly_sysctl_write_raises(self):
        with self.assertRaises(PermissionError):
            self.fs.write("/proc/sys/kernel/osrelease", "9.9")

    def test_readonly_sysctl_file_readonly(self):
        with self.assertRaises(PermissionError):
            self.fs.write("/proc/sys/kernel/version", "x")

    def test_domainname_write(self):
        self.fs.write("/proc/sys/kernel/domainname", "meros.local")
        data = self.fs.read("/proc/sys/kernel/domainname")
        self.assertEqual(data.strip(), "meros.local")


# ── PID dir signature / cache ─────────────────────────────────────

class TestPidDirCache(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)

    def test_dir_signature(self):
        sig = pid_dir_signature(self.adapter, 1000)
        self.assertEqual(sig, (1000, "init", "RUNNING"))

    def test_dir_signature_nonexistent(self):
        sig = pid_dir_signature(self.adapter, 9999)
        self.assertIsNone(sig)

    def test_cached_dir_not_rebuilt(self):
        entries1 = self.fs.list("/proc/1000")
        entries2 = self.fs.list("/proc/1000")
        self.assertEqual(entries1, entries2)


# ── build_pid_dir standalone ────────────────────────────────────

class TestBuildPidDir(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)

    def test_build_init_dir(self):
        d = build_pid_dir(self.adapter, 1000)
        self.assertIn("status", d.children)
        self.assertIn("cmdline", d.children)

    def test_build_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            build_pid_dir(self.adapter, 99999)


# ── New /proc entries (TLDP gap fill) ──────────────────────────

class TestSoftirqs(unittest.TestCase):
    def setUp(self):
        self.adapter = KernelAdapter()
        self.fs = ProcFileSystem(self.adapter)

    def test_softirqs_readable(self):
        data = self.fs.read("/proc/softirqs")
        self.assertIsInstance(data, str)
        self.assertTrue(len(data) > 0)

    def test_softirqs_contains_header(self):
        data = self.fs.read("/proc/softirqs")
        self.assertIn("CPU0", data)

    def test_softirqs_contains_irq_names(self):
        data = self.fs.read("/proc/softirqs")
        self.assertIn("HI", data)
        self.assertIn("TIMER", data)
        self.assertIn("NET_TX", data)
        self.assertIn("NET_RX", data)
        self.assertIn("SCHED", data)

    def test_softirqs_counts_populated(self):
        data = self.fs.read("/proc/softirqs")
        for line in data.splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2:
                counts = parts[1:]
                self.assertTrue(all(c.isdigit() for c in counts), f"Non-numeric count in: {line}")


class TestProcFsDirectory(unittest.TestCase):
    def setUp(self):
        self.adapter = KernelAdapter()
        self.fs = ProcFileSystem(self.adapter)

    def test_fs_directory_exists(self):
        names = self.fs.list("/proc")
        self.assertIn("fs", names)

    def test_fs_directory_is_listable(self):
        entries = self.fs.list("/proc/fs")
        self.assertIn("file-nr", entries)
        self.assertIn("inodes", entries)

    def test_fs_file_nr(self):
        data = self.fs.read("/proc/fs/file-nr")
        self.assertIn("0", data)

    def test_fs_inodes(self):
        data = self.fs.read("/proc/fs/inodes")
        self.assertIn("0", data)

    def test_fs_ext4_subdir(self):
        entries = self.fs.list("/proc/fs")
        self.assertIn("ext4", entries)

    def test_fs_ext4_options(self):
        data = self.fs.read("/proc/fs/ext4/options")
        self.assertIn("relatime", data)


class TestPidLimits(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)

    def test_limits_readable(self):
        data = self.fs.read("/proc/1000/limits")
        self.assertIn("Limit", data)

    def test_limits_contains_core(self):
        data = self.fs.read("/proc/1000/limits")
        self.assertIn("Max core file size", data)

    def test_limits_contains_nproc(self):
        data = self.fs.read("/proc/1000/limits")
        self.assertIn("Max processes", data)

    def test_limits_all_pids(self):
        for pid in self.adapter.pids():
            data = self.fs.read(f"/proc/{pid}/limits")
            self.assertIn("Limit", data)


class TestPidMounts(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)

    def test_mounts_readable(self):
        data = self.fs.read("/proc/1000/mounts")
        self.assertIn("/", data)

    def test_mounts_format(self):
        data = self.fs.read("/proc/1000/mounts")
        for line in data.splitlines():
            parts = line.split()
            self.assertGreaterEqual(len(parts), 4)

    def test_mounts_contains_proc(self):
        data = self.fs.read("/proc/1000/mounts")
        self.assertIn("proc", data)


class TestPidMountinfo(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)

    def test_mountinfo_readable(self):
        data = self.fs.read("/proc/1000/mountinfo")
        self.assertIn("/", data)

    def test_mountinfo_extended_format(self):
        data = self.fs.read("/proc/1000/mountinfo")
        for line in data.splitlines():
            parts = line.split()
            self.assertGreaterEqual(len(parts), 10)

    def test_mountinfo_contains_mount_id(self):
        data = self.fs.read("/proc/1000/mountinfo")
        for line in data.splitlines()[:1]:
            parts = line.split()
            self.assertTrue(parts[0].isdigit(), "First field should be mount ID")


class TestPidNet(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)

    def test_net_directory_exists(self):
        entries = self.fs.list("/proc/1000")
        self.assertIn("net", entries)

    def test_net_dev(self):
        data = self.fs.read("/proc/1000/net/dev")
        self.assertIn("lo", data)

    def test_net_tcp(self):
        data = self.fs.read("/proc/1000/net/tcp")
        self.assertIn("sl", data)

    def test_net_udp(self):
        data = self.fs.read("/proc/1000/net/udp")
        self.assertIn("sl", data)

    def test_net_unix(self):
        data = self.fs.read("/proc/1000/net/unix")
        self.assertIn("Num", data)

    def test_net_arp(self):
        data = self.fs.read("/proc/1000/net/arp")
        self.assertIn("IP address", data)

    def test_net_route(self):
        data = self.fs.read("/proc/1000/net/route")
        self.assertIn("Destination", data)


class TestPidTask(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)

    def test_task_directory_exists(self):
        entries = self.fs.list("/proc/1000")
        self.assertIn("task", entries)

    def test_task_main_thread(self):
        entries = self.fs.list("/proc/1000/task")
        self.assertIn("1000", entries)

    def test_task_comm(self):
        data = self.fs.read("/proc/1000/task/1000/comm")
        self.assertIsInstance(data, str)
        self.assertTrue(len(data.strip()) > 0)

    def test_task_status(self):
        data = self.fs.read("/proc/1000/task/1000/status")
        self.assertIn("Name:", data)
        self.assertIn("Pid:", data)

    def test_task_stat(self):
        data = self.fs.read("/proc/1000/task/1000/stat")
        self.assertIn("(", data)

    def test_task_smaps_rollup(self):
        data = self.fs.read("/proc/1000/task/1000/smaps_rollup")
        self.assertIn("Rss:", data)


# ── Wrapper modules (for drivers/driver_service.py compatibility) ──

class TestWrapperModules(unittest.TestCase):
    def test_filesystems(self):
        from proc.filesystems import get
        fs = get()
        self.assertIsInstance(fs, list)
        self.assertIn("proc", fs)

    def test_partitions(self):
        from proc.partitions import get
        parts = get()
        self.assertIsInstance(parts, list)

    def test_swaps(self):
        from proc.swaps import get
        swaps = get()
        self.assertIsInstance(swaps, list)

    def test_interrupts(self):
        from proc.interrupts import get
        irqs = get()
        self.assertIsInstance(irqs, list)

    def test_ioports(self):
        from proc.ioports import get
        ports = get()
        self.assertIsInstance(ports, list)

    def test_dma(self):
        from proc.dma import get
        channels = get()
        self.assertIsInstance(channels, list)

    def test_modules(self):
        from proc.modules import get
        mods = get()
        self.assertIsInstance(mods, list)
        names = [m["name"] for m in mods]
        self.assertIn("qfs", names)

    def test_mounts(self):
        from proc.mounts import get
        mounts = get()
        self.assertIsInstance(mounts, list)
        mps = [m["mountpoint"] for m in mounts]
        self.assertIn("/", mps)


# ── VFS bridge ───────────────────────────────────────────────────

class _MockVFS:
    """Minimal mock of the kernel's VirtualFileSystem."""
    def __init__(self):
        self.root = ProcDir("/")
        self.root.children["proc"] = ProcDir("proc")
        self.root.children["home"] = ProcDir("home")
        self.cwd = "/home/umer"

    def _resolve(self, path):
        parts = [p for p in path.split("/") if p and p != "."]
        curr = self.root
        for p in parts:
            if not curr.is_dir or p not in curr.children:
                return None, None
            curr = curr.children[p]
        return curr, "/" + "/".join(parts)

    def read_file(self, path):
        node, _ = self._resolve(path)
        if node and not node.is_dir:
            return node.content if hasattr(node, "content") else ""
        return ""

    def write_file(self, path, data):
        pass

    def ls(self, path=None):
        if path is None:
            path = "/"
        node, _ = self._resolve(path)
        if node and node.is_dir:
            return list(node.children.keys())
        return [node.name] if node else []


class TestVFSBridge(unittest.TestCase):
    def setUp(self):
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)
        self.vfs = _MockVFS()

    def test_mount_replaces_static(self):
        self.fs.mount_into_vfs(self.vfs)
        # VFS read_file now goes through procfs for /proc paths
        data = self.vfs.read_file("/proc/meminfo")
        self.assertIn("MemTotal", data)

    def test_vfs_ls_proc(self):
        self.fs.mount_into_vfs(self.vfs)
        names = self.vfs.ls("/proc")
        self.assertIn("cpuinfo", names)
        self.assertIn("meminfo", names)

    def test_vfs_non_proc_unchanged(self):
        self.fs.mount_into_vfs(self.vfs)
        names = self.vfs.ls("/home")
        self.assertIsInstance(names, list)


# ── tree_snapshot ──────────────────────────────────────────────────

class TestTreeSnapshot(unittest.TestCase):
    def setUp(self):
        self.adapter = KernelAdapter()
        self.fs = ProcFileSystem(self.adapter)

    def test_snapshot_nonempty(self):
        tree = self.fs.tree_snapshot(max_depth=1)
        self.assertIn("/cpuinfo", tree)
        self.assertIn("/net/", tree)
        self.assertIn("/sys/", tree)


if __name__ == "__main__":
    unittest.main()
