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

"""System-wide /proc entries (everything except /proc/<pid>, /proc/sys,
/proc/net, /proc/sysvipc and /proc/tty, which live in sibling modules).

Content is generated live by handlers bound to the kernel adapter —
nothing here is stored, mirroring the real procfs "window into the
kernel" behaviour described by the Linux Filesystem Hierarchy docs.
"""
from __future__ import annotations

import datetime
import platform
import sys
from typing import TYPE_CHECKING

from proc.nodes import ProcDir, ProcFile, ProcSymlink

# [FIX H208] Zero-trust capability gate for privileged /proc/irq writes.
from core.capability_gate import CAP_SYS_ADMIN, gate

if TYPE_CHECKING:  # pragma: no cover
    from proc.procfs import ProcFileSystem

_UMER_VERSION = "2.1.0-quantum"
_GCC_VERSION = "9.3.0"

# IRQ lines exposed under /proc/irq/ (classic PC defaults).
_DEFAULT_IRQS = {
    0: "timer", 1: "i8042", 8: "rtc0", 12: "i8042",
    14: "ata_piix", 15: "ata_piix",
}


def _fmt_range(start: int, end: int, width: int = 10) -> str:
    return f"{start:0{width}x}-{end:0{width}x}"


def _cpuinfo(adapter) -> str:
    cpus = [
        {"processor": 0, "model": "UmerOS Quantum AI Accelerator CPU @ 3.40GHz",
         "mhz": 3400, "apicid": 0, "coreid": 0},
        {"processor": 1, "model": "UmerOS Quantum AI Accelerator CPU @ 3.40GHz",
         "mhz": 3400, "apicid": 1, "coreid": 0},
    ]
    flags = ("fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov "
             "pat pse36 clflush mmx fxsr sse sse2 ss ht tm pbe syscall nx "
             "rdtscp lm constant_tsc arch_perfmon pebs bts rep_good nopl "
             "xtopology nonstop_tsc cpuid tsc_known_freq pclmulqdq monitor "
             "ds_cpl vmx est tm2 ssse3 sdbg fma cx16 xtpr pdcm pcid sse4_1 "
             "sse4_2 x2apic movbe popcnt tsc_deadline_timer aes xsave avx "
             "f16c rdrand lahf_lm abm 3dnowprefetch cpuid_fault epb cat_l3 "
             "invpcid_single intel_pt ssbd mba ibrs ibpb stibp tpr_shadow "
             "flexpriority ept vpid ept_ad fsgsbase tsc_adjust bmi1 avx2 "
             "smep bmi2 erms invpcid rtm rdseed adx smap clflushopt clwb "
             "sha_ni xsaveopt xsavec xgetbv1 xsaves avx512f avx512dq "
             "quantum_su superposition entangle")
    blocks = []
    for cpu in cpus:
        blocks.append("\n".join([
            f"processor\t: {cpu['processor']}",
            "vendor_id\t: QuantumGenuine",
            "cpu family\t: 6",
            "model\t\t: 142",
            "model name\t: " + cpu["model"],
            "stepping\t: 3",
            "microcode\t: 0xffffffff",
            f"cpu MHz\t\t: {cpu['mhz']}.000",
            "cache size\t: 16384 KB",
            f"physical id\t: 0",
            "siblings\t: 2",
            f"core id\t\t: {cpu['coreid']}",
            "cpu cores\t: 2",
            f"apicid\t\t: {cpu['apicid']}",
            "initial apicid\t: " + str(cpu["apicid"]),
            "fpu\t\t: yes",
            "fpu_exception\t: yes",
            "cpuid level\t: 42",
            "wp\t\t: yes",
            "flags\t\t: " + flags,
            "bugs\t\t: quantum_decoherence",
            "bogomips\t: 6800.02",
            "clflush size\t: 64",
            "cache_alignment\t: 64",
            "address sizes\t: 39 bits physical, 48 bits virtual",
            "power management:",
            "",
        ]))
    return "\n".join(blocks)


def _meminfo(adapter) -> str:
    mem = adapter.memory()
    lines = [
        ("MemTotal", mem["total_kib"]), ("MemFree", mem["free_kib"]),
        ("MemAvailable", mem["available"] // 1024),
        ("Buffers", mem["buffers"] // 1024), ("Cached", mem["cached"] // 1024),
        ("SwapCached", 0), ("Active", mem["used"] // 2048 // 1024 * 1024 // 1024),
        ("Inactive", mem["cached"] // 2048),
        ("Active(anon)", mem["used"] // 4096), ("Inactive(anon)", 0),
        ("Active(file)", 0), ("Inactive(file)", 0),
        ("Unevictable", 0), ("Mlocked", 0),
        ("SwapTotal", mem["swap_total"] // 1024),
        ("SwapFree", mem["swap_free"] // 1024),
        ("Dirty", 0), ("Writeback", 0), ("AnonPages", mem["used"] // 4096),
        ("Mapped", mem["total"] // 16384), ("Shmem", mem["total"] // 262144),
        ("Slab", mem["slab"] // 1024),
        ("SReclaimable", mem["slab"] // 2048),
        ("SUnreclaim", mem["slab"] // 2048),
        ("KernelStack", 8192), ("PageTables", 16384),
        ("NFS_Unstable", 0), ("Bounce", 0), ("WritebackTmp", 0),
        ("CommitLimit", (mem["total"] + mem["swap_total"]) // 2048),
        ("Committed_AS", mem["used"] // 1024),
        ("VmallocTotal", 34359738367 // 1024),
        ("VmallocUsed", 0), ("VmallocChunk", 0),
        ("Percpu", 131072 // 1024),
        ("HardwareCorrupted", 0), ("AnonHugePages", 0),
        ("ShmemHugePages", 0), ("ShmemPmdMapped", 0),
        ("HugePages_Total", 0), ("HugePages_Free", 0),
        ("HugePages_Rsvd", 0), ("HugePages_Surp", 0),
        ("Hugepagesize", 2048), ("DirectMap4k", mem["total"] // 16384),
        ("DirectMap2M", mem["total"] // 2048),
    ]
    return "".join(f"{key:<16}: {value:>12} kB\n" for key, value in lines)


def _uptime(adapter) -> str:
    uptime = adapter.uptime()
    idle = uptime * 0.93  # simulated idle fraction (2 simulated CPUs)
    return f"{uptime:.2f} {idle:.2f}\n"


def _loadavg(adapter) -> str:
    runnable = sum(1 for t in adapter.tasks()
                   if adapter.state_letter(t["state"]) in ("R", "D"))
    adapter.loadavg.update(runnable, len(adapter.tasks()))
    one, five, fifteen = adapter.loadavg.values()
    last_pid = adapter.pids()[-1] if adapter.pids() else 0
    return (f"{one:.2f} {five:.2f} {fifteen:.2f} "
            f"{runnable}/{max(len(adapter.tasks()), 1)} {last_pid}\n")


def _version(adapter) -> str:
    py = platform.python_version()
    return (f"UmerOS version {_UMER_VERSION} (root@buildhost) "
            f"(gcc version {_GCC_VERSION}, Python {py}) "
            f"#1 SMP PREEMPT QUANTUM UmerOS\n")


def _cmdline(adapter) -> str:
    return "BOOT_IMAGE=/boot/vmlinuz-umer root=qfs0 ro quiet splash\0"


def _stat(adapter) -> str:
    uptime = adapter.uptime()
    hz = 100
    total_ticks = int(uptime * hz * 2)  # 2 CPUs
    idle_ticks = int(total_ticks * 0.93)
    user = int(total_ticks * 0.04)
    system = int(total_ticks * 0.03)
    nice = 0
    iowait = int(total_ticks * 0.001)
    irq = int(total_ticks * 0.002)
    softirq = int(total_ticks * 0.005)
    steal = 0
    per_cpu_idle = idle_ticks // 2
    per_cpu_rest = (total_ticks - idle_ticks) // 2
    tasks = adapter.tasks()
    running = sum(1 for t in tasks if adapter.state_letter(t["state"]) == "R")
    blocked = sum(1 for t in tasks if adapter.state_letter(t["state"]) == "D")

    softirq_counts = adapter.softirq_counts()
    intr_total = int(uptime * 128) + sum(softirq_counts.values())
    ctxt = int(uptime * 512)

    lines = [
        f"cpu  {user} {nice} {system} {idle_ticks} {iowait} {irq} {softirq} {steal} 0 0",
        f"cpu0 {per_cpu_rest // 4} {nice} {per_cpu_rest // 6} {per_cpu_idle // 2} {iowait // 2} {irq // 2} {softirq // 2} {steal} 0 0",
        f"cpu1 {per_cpu_rest // 4} {nice} {per_cpu_rest // 6} {(per_cpu_idle + 1) // 2} {(iowait + 1) // 2} {(irq + 1) // 2} {(softirq + 1) // 2} {steal} 0 0",
        f"intr {intr_total} " + " ".join(str(int(uptime * 3)) for _ in range(16)),
        f"ctxt {ctxt}",
        f"btime {int(adapter.boot_epoch())}",
        f"processes {len(tasks) + 4}",
        f"procs_running {max(running, 1)}",
        f"procs_blocked {blocked}",
        f"softirq {sum(softirq_counts.values())} " +
        " ".join(str(v) for v in softirq_counts.values()),
    ]
    return "\n".join(lines) + "\n"


def _interrupts(adapter) -> str:
    counts = adapter.softirq_counts()
    rows = [
        ("0", [int(adapter.uptime()), int(adapter.uptime())], "IO-APIC 2-edge timer"),
        ("1", [12, 3], "IO-APIC 1-edge i8042"),
        ("8", [1, 0], "IO-APIC 8-edge rtc0"),
        ("12", [4, 12], "IO-APIC 12-edge i8042"),
        ("14", [842, 771], "IO-APIC 14-edge ata_piix"),
        ("15", [23, 11], "IO-APIC 15-edge ata_piix"),
        ("NMI", [int(adapter.uptime()) * 2] * 2, "Non-maskable interrupts"),
        ("LOC", [int(adapter.uptime() * 1000)] * 2, "Local timer interrupts"),
        ("ERR", [0], "IO-APIC bus errors"),
    ]
    # Include any softirq traffic the kernel actually counted.
    for name, count in counts.items():
        if count:
            rows.append((name.upper(), [count, count],
                         f"UmerOS softirq {name}"))
    lines = ["           CPU0       CPU1"]
    for label, values, desc in rows:
        cells = " ".join(f"{v:10d}" for v in values)
        lines.append(f"{label:>4}: {cells}  {desc}")
    return "\n".join(lines) + "\n"


def _resource_tree(adapter, attr: str, fallback: list) -> str:
    """Format ioports/iomem/dma from the kernel resource tree."""
    manager = adapter.resources()
    root = getattr(manager, attr, None) if manager else None
    lines = []
    for child in getattr(root, "children", None) or []:
        width = 16 if attr == "iomem_root" else 4
        lines.append(f"{_fmt_range(child.start, child.end, width)} : {child.name}")
    if not lines:
        lines = list(fallback)
    return "\n".join(lines) + "\n"


_IOPORTS_FALLBACK = [
    "0000-001f : dma1",
    "0020-0021 : pic1",
    "0040-0043 : timer0",
    "0060-0060 : keyboard",
    "0080-008f : dma page reg",
    "00a0-00a1 : pic2",
    "00c0-00df : dma2",
    "00f0-00ff : fpu",
    "0170-0177 : ide1",
    "01f0-01f7 : ide0",
    "03c0-03df : vga+",
    "03f6-03f6 : fdc",
]

_IOMEM_FALLBACK = [
    "00000000-00000fff : Reserved",
    "00001000-0009fbff : System RAM",
    "0009fc00-0009ffff : Reserved",
    "000a0000-000bffff : PCI Bus 0000:00",
    "000c0000-000cffff : PCI Option ROM",
    "00100000-bffdffff : System RAM",
    "  01000000-016c3f7f : Kernel code",
    "  016c3f80-01a6b8ff : Kernel data",
    "bffe0000-bfffffff : Reserved",
    "e0000000-efffffff : PCI Bus 0000:00",
    "  e0000000-e0ffffff : 0000:00:02.0",
    "fec00000-fec00fff : IOAPIC 0",
    "fee00000-fee00fff : Local APIC",
    "ffffffffff000000-ffffffffffffffff : reserved",
]


def _devices(adapter) -> str:
    lines = ["Character devices:"]
    for major, minor, name in adapter.char_devices():
        lines.append(f" {major:>3} {name}")
    lines.append("")
    lines.append("Block devices:")
    for major, minor, name in adapter.block_devices():
        lines.append(f" {major:>3} {name}")
    lines.append("")
    return "\n".join(lines)


def _dma(adapter) -> str:
    return _resource_tree(adapter, "dma_root", ["4: cascade"])


def _filesystems(adapter) -> str:
    return "".join(f"{'nodev' if nodev else '':<6}{name}\n"
                   for nodev, name in adapter.filesystems())


def _mounts(adapter) -> str:
    return "".join(
        f"{m['device']} {m['mountpoint']} {m['fstype']} {m['opts']} 0 0\n"
        for m in adapter.mounts())


def _partitions(adapter) -> str:
    lines = ["major minor  #blocks  name"]
    part = adapter.partition()
    rows = [(254, 0, 4194304, "qfs_root"), (254, 16, 2097152, "qswap")]
    if part:
        rows[0] = (part["major"], part["minor"],
                   max(part["blocks_kib"], 1), part["name"])
    for major, minor, blocks, name in rows:
        lines.append(f"{major:>5} {minor:>5} {blocks:>10} {name}")
    return "\n".join(lines) + "\n"


def _swaps(adapter) -> str:
    lines = ["Filename\t\t\t\tType\t\tSize\tUsed\tPriority"]
    lines.append("/dev/qswap\t\t\t\tpartition\t2097144\t0\t-2")
    return "\n".join(lines) + "\n"


def _slabinfo(adapter) -> str:
    part = adapter.partition()
    inodes = part["total_inodes"] if part else 4096
    uptime = max(adapter.uptime(), 1)
    caches = [
        ("umer_inode_cache", inodes, int(inodes * 0.42), 120, 4),
        ("dentry_cache", int(uptime * 64) + 512, 331, 144, 8),
        ("qfs_buffer", int(uptime * 32) + 256, 205, 256, 1),
        ("task_struct", len(adapter.tasks()) + 12, 24, 292, 8),
        ("signal_cache", len(adapter.tasks()) + 12, 18, 1088, 8),
    ]
    lines = [
        "slabinfo - version: 2.1",
        "# name            <active_objs> <num_objs> <objsize> <objperslab> <pagesperslab> "
        ": tunables <limit> <batchcount> <sharedfactor> "
        ": slabdata <active_slabs> <num_slabs> <sharedavail>",
    ]
    for name, active, num, size, per_slab in caches:
        slabs = max(num // per_slab, 1)
        lines.append(
            f"{name:<22} {active:>6} {num:>6} {size:>6} {per_slab:>2}   "
            f": tunables {per_slab * 2:>3} {per_slab:>2} {0:>1}    "
            f": slabdata {slabs:>3} {slabs:>3} {0:>1}")
    return "\n".join(lines) + "\n"


def _kmsg(adapter) -> str:
    return adapter.kmsg.tail()


def _kcore(adapter) -> str:
    # Real /proc/kcore is an ELF core image the size of physical RAM.
    # We expose a header stub while reporting the full size via stat.
    total = adapter.memory()["total"]
    return ("\x7fELF\x02\x01\x01\x00" + "\x00" * 9 +
            f"<UmerOS kcore image — {total} bytes of physical memory>\n")


def _ksyms(adapter) -> str:
    syms = [
        ("ffffffff81000000", "umer_kernel_text_start"),
        ("ffffffff81001000", "umer_start_kernel"),
        ("ffffffff8100a4d0", "umer_panic"),
        ("ffffffff81012f10", "umer_alloc_pages"),
        ("ffffffff81020488", "umer_quantum_gate_x"),
        ("ffffffff81020490", "umer_quantum_entangle"),
        ("ffffffff81100000", "qfs_mount"),
        ("ffffffff81101040", "qfs_read_inode"),
        ("ffffffff81200000", "procfs_lookup"),
        ("ffffffff81200118", "procfs_read"),
        ("ffffffff81300000", "qcrypto_encrypt"),
        ("ffffffff81400000", "umer_net_send"),
        ("ffffffff81e00000", "umer_kernel_text_end"),
    ]
    return "".join(f"{addr} {name}\n" for addr, name in syms)


def _locks(adapter) -> str:
    return ""  # no POSIX/FLOCK locks held in the simulation


def _misc(adapter) -> str:
    return (" 63 qcrypto\n130 watchdog\n229 fuse\n")


def _modules(adapter) -> str:
    return "".join(
        f"{m['name']} {m['size']} {m['use_count']} "
        f"{m['deps'] or '-'} {m['state']} 0x0000000000000000\n"
        for m in adapter.modules())


def _execdomains(adapter) -> str:
    return f"{sys.platform} {sum(1 for _ in adapter.tasks())}\n"


def _fb(adapter) -> str:
    return "0 UmerGPU FB 1920 1080 32\n"


def _mtrr(adapter) -> str:
    return (
        "reg00: base=0x000000000 (    0MB), size= 2048MB, count=1: write-back\n"
        "reg01: base=0x080000000 ( 2048MB), size= 1024MB, count=1: write-back\n"
        "reg02: base=0x0c0000000 ( 3072MB), size=  512MB, count=1: write-back\n"
        "reg03: base=0x0e0000000 ( 3584MB), size=  256MB, count=1: write-back\n"
        "reg04: base=0x0f0000000 ( 3840MB), size=  128MB, count=1: write-combining\n"
    )


def _rtc(adapter) -> str:
    now = datetime.datetime.now()
    return (
        f"rtc_time\t: {now:%H:%M:%S}\n"
        f"rtc_date\t: {now:%Y-%m-%d}\n"
        "alrm_time\t: 00:00:00\n"
        "alrm_date\t: ****-**-**\n"
        "alarm_IRQ\t: no\n"
        "alrm_pending\t: no\n"
        "24hr\t\t: yes\n"
        "periodic_IRQ\t: no\n"
        "update_IRQ\t: no\n"
        "HPET_emulated\t: yes\n"
        "DST_enable\t: no\n"
        "periodic_freq\t: 1024\n"
        "batt_status\t: okay\n"
    )


def _apm(adapter) -> str:
    return "1.16 1.2 0x03 0x01 0xff 0x80 -1% -1 ?\n"


def _isapnp(adapter) -> str:
    return ""


def _video(adapter) -> str:
    return "Boot video device is 0000:00:02.0\n"


def _softirqs(adapter) -> str:
    """Render /proc/softirqs -- software interrupt statistics."""
    counts = adapter.softirq_counts()
    irq_names = [
        "HI", "TIMER", "NET_TX", "NET_RX", "BLOCK", "IRQ_POLL",
        "TASKLET", "SCHED", "HRTIMER", "RCU",
    ]
    header = f"{'':>8}" + "".join(f"{n:>12}" for n in irq_names) + "\n"
    lines = [header]
    for cpu_id in range(max(len(counts), 1)):
        vals = [counts.get(i, 0) for i in range(len(irq_names))]
        row = f"CPU{cpu_id}" + "".join(f"{v:>12}" for v in vals) + "\n"
        lines.append(row)
    return "".join(lines)


def register_system_entries(fs: "ProcFileSystem") -> None:
    """Attach every system-wide entry to the /proc root."""
    adapter = fs.adapter
    root = fs.root

    def file(name, read, **kw):
        root.add(ProcFile(name, read=read, **kw))

    # ── identity / time ──────────────────────────────────────────
    file("cmdline", lambda: _cmdline(adapter))
    file("version", lambda: _version(adapter))
    file("uptime", lambda: _uptime(adapter))
    file("loadavg", lambda: _loadavg(adapter))
    file("stat", lambda: _stat(adapter))
    file("rtc", lambda: _rtc(adapter))
    root.add(ProcFile(
        "kcore", lambda: _kcore(adapter),
        virtual_size=adapter.memory()["total"], mode="r--------"))
    file("mtrr", lambda: _mtrr(adapter), size_zero=False)

    # ── hardware tables ──────────────────────────────────────────
    file("cpuinfo", lambda: _cpuinfo(adapter))
    file("meminfo", lambda: _meminfo(adapter))
    file("devices", lambda: _devices(adapter))
    file("dma", lambda: _dma(adapter))
    file("interrupts", lambda: _interrupts(adapter))
    file("ioports", lambda: _resource_tree(
        adapter, "ioport_root", _IOPORTS_FALLBACK))
    file("iomem", lambda: _resource_tree(
        adapter, "iomem_root", _IOMEM_FALLBACK))
    file("partitions", lambda: _partitions(adapter))
    file("swaps", lambda: _swaps(adapter))
    file("fb", lambda: _fb(adapter))
    file("apm", lambda: _apm(adapter))
    file("isapnp", lambda: _isapnp(adapter))
    file("video", lambda: _video(adapter))
    file("slabinfo", lambda: _slabinfo(adapter))

    # ── kernel state ─────────────────────────────────────────────
    file("kmsg", lambda: _kmsg(adapter), mode="r--------")
    file("ksyms", lambda: _ksyms(adapter))
    file("locks", lambda: _locks(adapter))
    file("misc", lambda: _misc(adapter))
    file("modules", lambda: _modules(adapter))
    file("execdomains", lambda: _execdomains(adapter))
    file("filesystems", lambda: _filesystems(adapter))
    file("mounts", lambda: _mounts(adapter))
    file("softirqs", lambda: _softirqs(adapter))

    # ── /proc/fs/ -- filesystem-specific info ────────────────────
    fs_dir = ProcDir("fs")
    fs_dir.add(ProcFile("file-nr", lambda: "0 0 0\n"))
    fs_dir.add(ProcFile("file-nodes", lambda: "0\n"))
    fs_dir.add(ProcFile("inodes", lambda: "0 0 0\n"))
    fs_dir.add(ProcFile("dentry-state",
                        lambda: "0 0 0 0 0 0\n"))
    fs_dir.add(ProcFile("nr_block_dev_in_use", lambda: "0\n"))
    # /proc/fs/ext4/  (placeholder for ext4 stats)
    ext4 = ProcDir("ext4")
    ext4.add(ProcFile("options", lambda: "rw,relatime,data=ordered\n"))
    ext4.add(ProcFile("mb_groups", lambda: ""))
    fs_dir.add(ext4)
    # /proc/fs/xfs/
    xfs = ProcDir("xfs")
    xfs.add(ProcFile("stat", lambda: (
        "xfs_stat\n"
        "allocates: 0\n"
        "frees: 0\n")))
    fs_dir.add(xfs)
    # /proc/fs/fuse/
    fuse = ProcDir("fuse")
    fuse.add(ProcFile("connections", lambda: "0\n"))
    fuse.add(ProcFile("waiting_queue", lambda: ""))
    fuse.add(ProcFile("abort", lambda: ""))
    fs_dir.add(fuse)
    root.add(fs_dir)

    # ── /proc/irq/<n>/ — writable SMP affinity masks ─────────────
    irq_dir = ProcDir("irq")
    for irq, desc in _DEFAULT_IRQS.items():
        node = ProcDir(str(irq))
        node.add(ProcFile(
            "smp_affinity",
            lambda i=irq: adapter.irq_affinity.get(i, "3\n"),
            write=lambda text, i=irq: (
                gate.require(CAP_SYS_ADMIN),  # [FIX H208] privileged IRQ affinity write
                adapter.irq_affinity.__setitem__(
                    i, text.strip() + "\n"))[-1],
            mode="rw-r--r--"))
        node.add(ProcFile("spurious", lambda: "0 0 0 0 0 0 0 0\n"))
        node.add(ProcFile("stat", lambda: f"total 0 detected 0\n"))
        irq_dir.add(node)
    root.add(irq_dir)

    # ── /proc/bus/ — bus device inventories ──────────────────────
    bus = ProcDir("bus")
    pci = ProcDir("pci")
    pci.add(ProcFile("devices", lambda: (
        "00:00.0 Host bridge: Quantum Bridge Corp. QBC-1000 (rev 01)\n"
        "00:02.0 VGA compatible controller: UmerGPU Quantum Display Adapter\n"
        "00:1f.2 SATA controller: Quantum Storage Controller (rev 03)\n"
        "00:1f.3 SMBus: Quantum SMBus Controller\n")))
    usb = ProcDir("usb")
    usb.add(ProcFile("devices", lambda: (
        "T:  Bus=01 Lev=00 Prnt=00 Port=00 Cnt=00 Dev#=  1 Spd=480 MxCh= 2\n"
        "D:  Ver= 2.00 Cls=09(hub ) Sub=00 Prot=01 MxPS=64 #Cfgs=  1\n"
        "P:  Vendor=1d6b ProdID=0002 Rev=05.15\n"
        "S:  Manufacturer=UmerOS Linux 5.15.0-umer with qc-hcd\n"
        "S:  Product=qHCI Host Controller\n")))
    input_bus = ProcDir("input")
    input_bus.add(ProcFile("devices", lambda: (
        'I: Bus=0011 Vendor=0001 Product=0001 Name="AT Translated Set 2 keyboard"\n'
        'I: Bus=0011 Vendor=0002 Product=0013 Name="VirtualPS/2 UmerOS Mouse"\n')))
    bus.add(pci)
    bus.add(usb)
    bus.add(input_bus)
    root.add(bus)

    # ── /proc/driver/ ────────────────────────────────────────────
    driver = ProcDir("driver")
    driver.add(ProcFile("rtc", lambda: _rtc(adapter)))
    root.add(driver)

    # ── /proc/ide/ — IDE device tree ─────────────────────────────
    ide = ProcDir("ide")
    ide0 = ProcDir("ide0")
    ide0.add(ProcFile("channel", lambda: "0\n"))
    ide0.add(ProcFile("config", lambda:
                      "pci0 00:1f.1 1 0x0000 0x0000 0x0000 0x0000\n"))
    ide0.add(ProcFile("mate", lambda: "ide1\n"))
    ide0.add(ProcFile("model", lambda: "Quantum ATA Controller\n"))
    hda = ProcDir("hda")
    hda.add(ProcFile("cache", lambda: "1024k\n"))
    hda.add(ProcFile("capacity", lambda: "8388608\n"))  # 512-byte blocks
    hda.add(ProcFile("driver", lambda: "ata-piix\n"))
    hda.add(ProcFile("geometry", lambda:
                     "physical     16383/16/63\nlogical      1044/255/63\n"))
    hda.add(ProcFile("identify", lambda:
                     "\n".join(f"{i * 2:04x} 0000 0000 0000 0000"
                               for i in range(4)) + "\n"))
    hda.add(ProcFile("media", lambda: "disk\n"))
    hda.add(ProcFile("model", lambda: "UMERQUANTUM-QD4\n"))
    hda.add(ProcFile("settings", lambda:
                     "unmaskirq\t1\tdma\t1\tusing_dma\t1\n"))
    ide0.add(hda)
    ide.add(ide0)
    root.add(ide)

    # ── /proc/scsi/ ──────────────────────────────────────────────
    scsi = ProcDir("scsi")
    scsi.add(ProcFile("scsi", lambda: (
        "Attached devices:\n"
        "Host: scsi0 Channel: 00 Id: 00 Lun: 00\n"
        "  Vendor: UmerOS   Model: QuantumSSD Q1    Rev: 1.0\n"
        "  Type:   Direct-Access                    ANSI  SCSI revision: 06\n")))
    root.add(scsi)

    # ── /proc/parport/ — parallel port info ──────────────────────
    parport = ProcDir("parport")
    port0 = ProcDir("0")
    port0.add(ProcFile("autoprobe", lambda:
                       'MFG:UmerOS;MDL:QuantumLaser 300;CLS:PRINTER;\n'))
    port0.add(ProcFile("devices", lambda:
                       "lp\nactive\n"))
    port0.add(ProcFile("hardware", lambda:
                       "base:\t0x0378\nirq:\t7\ndma:\tnone\nmodes:\tSPP,ECP\n"))
    port0.add(ProcFile("irq", lambda: "7\n",
                       write=lambda text: None, mode="rw-r--r--"))
    parport.add(port0)
    root.add(parport)
