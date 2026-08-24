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

"""Per-process /proc/<pid> directories.

Each live scheduler task gets a full Linux-style process directory:

    cmdline  comm  environ  status  stat  statm  maps  mem  cpu
    fd/  cwd  exe  root  loginuid  oom_score  oom_score_adj  io
    cgroup  sched

Formats mirror the real procfs: ``cmdline``/``environ`` are NUL
separated, ``stat`` is the classic single-line field dump, ``status``
is the human-readable key/value block, and ``cwd``/``exe``/``root``
are symlinks.  PID 0 (the kernel itself) is addressable directly but
hidden from the /proc listing, exactly like the idle task on Linux.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from proc.nodes import ProcDir, ProcFile, ProcSymlink

# [FIX H207] Zero-trust capability gate for per-PID privileged writes.
from core.capability_gate import CAP_SYS_ADMIN, gate

_STATUS_TEXT = {
    "R": "running (on thread)", "S": "sleeping", "D": "disk sleep",
    "Z": "zombie", "T": "stopped",
}


def _cmdline_list(task: Dict[str, Any]) -> list:
    name = task["name"]
    return [f"/usr/bin/{name}", "--quantum-scheduler"]


def _environ(task: Dict[str, Any]) -> Dict[str, str]:
    return {
        "HOME": "/home/umer",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "TERM": "umer-term",
        "SHELL": "/bin/umersh",
        "USER": "umer",
        "PWD": "/home/umer",
        "LANG": "en_US.UTF-8",
        "UMEROS_VERSION": "2.1.0",
        "UMER_QUANTUM_SCHED": "1",
    }


def _nul_join(items) -> str:
    return "".join(str(item) + "\0" for item in items)


def _uid_gid(adapter, pid: int) -> tuple:
    cred_store = getattr(adapter.kernel, "cred_store", None)
    cred = None
    get_fn = getattr(cred_store, "get", None)
    if callable(get_fn):
        try:
            cred = get_fn(pid)
        except Exception:  # noqa: BLE001
            cred = None
    if cred is not None:
        uid = int(getattr(cred, "uid", getattr(cred, "euid", 0)) or 0)
        gid = int(getattr(cred, "gid", getattr(cred, "egid", 0)) or 0)
    else:
        uid, gid = (0, 0) if pid in (0, 1000) else (1000, 1000)
    return uid, gid


def _rss(adapter, pid: int) -> int:
    return adapter.memory_by_pid().get(pid, 0)


def _vmsize(adapter, task: Dict[str, Any]) -> int:
    rss = _rss(adapter, task["pid"])
    code = 4 * 1024 * 1024 + len(task["name"]) * 64 * 1024
    return rss + code


def build_pid_dir(adapter, pid: int) -> ProcDir:
    """Construct the /proc/<pid> directory for one task."""
    task = adapter.task(pid)
    if task is None:
        raise FileNotFoundError(f"no such process: {pid}")

    name = task["name"]
    state = adapter.state_letter(task["state"])
    ppid = task.get("parent_pid")
    if ppid is None:
        ppid = 0 if pid != 1000 else 0
    uid, gid = _uid_gid(adapter, pid)
    rss = _rss(adapter, pid)
    vmsize = _vmsize(adapter, task)
    owner = "root" if uid == 0 else "umer"
    dir_mode = "r-xr-xr-x"

    pid_dir = ProcDir(str(pid), mode=dir_mode, owner=owner)
    pid_dir.meta_task = task  # type: ignore[attr-defined]

    def file(fname, read, write=None, mode="r--r--r--", **kw):
        return pid_dir.add(ProcFile(fname, read=read, write=write,
                                    mode=mode, owner=owner, **kw))

    # ── identity ─────────────────────────────────────────────────
    file("cmdline", lambda: _nul_join(_cmdline_list(task)))
    file("comm", lambda: name + "\n")

    # ── environment (NUL separated, like Linux) ──────────────────
    file("environ", lambda: _nul_join(
        f"{k}={v}" for k, v in _environ(task).items()))

    # ── status — human readable block ────────────────────────────
    def _status() -> str:
        threads = 1
        pending = "0000000000000000"
        cap_full = "0000003fffffffff"
        lines = [
            f"Name:\t{name}",
            f"Umask:\t0022",
            f"State:\t{state} ({_STATUS_TEXT.get(state, 'sleeping')})",
            f"Tgid:\t{pid}",
            f"Pid:\t{pid}",
            f"PPid:\t{ppid}",
            f"TracerPid:\t0",
            f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}",
            f"Gid:\t{gid}\t{gid}\t{gid}\t{gid}",
            f"FDSize:\t64",
            f"Groups:\t{0 if gid == 0 else 1000}",
            f"NStgid:\t{pid}",
            f"NSpid:\t{pid}",
            f"NSpgid:\t{pid}",
            f"NSsid:\t{pid}",
            f"VmPeak:\t{(vmsize + 1048576) // 1024} kB",
            f"VmSize:\t{vmsize // 1024} kB",
            f"VmLck:\t0 kB",
            f"VmPin:\t0 kB",
            f"VmHWM:\t{max(rss, 4096) // 1024} kB",
            f"VmRSS:\t{max(rss, 4096) // 1024} kB",
            f"VmData:\t{rss // 1024} kB",
            f"VmStk:\t132 kB",
            f"VmExe:\t{(vmsize - rss) // 1024} kB",
            f"VmLib:\t2048 kB",
            f"VmPTE:\t64 kB",
            f"VmSwap:\t0 kB",
            f"CoreDumping:\t0",
            f"Threads:\t{threads}",
            f"SigQ:\t0/{32768 - pid}",
            f"SigPnd:\t{pending}",
            f"ShdPnd:\t{pending}",
            f"SigBlk:\t{pending}",
            f"SigIgn:\t{pending}",
            f"SigCgt:\t0000000180000000",
            f"CapInh:\t0000000000000000",
            f"CapPrm:\t{cap_full if uid == 0 else '0000000000000000'}",
            f"CapEff:\t{cap_full if uid == 0 else '0000000000000000'}",
            f"CapBnd:\t{cap_full}",
            f"CapAmb:\t0000000000000000",
            f"NoNewPrivs:\t0",
            f"Seccomp:\t0",
            f"Seccomp_filters:\t0",
            f"Speculation_Store_Bypass:\tvulnerable",
            f"Cpus_allowed:\t3",
            f"Cpus_allowed_list:\t0-1",
            f"Mems_allowed:\t00000000",
            f"voluntary_ctxt_switches:\t{int(task['cpu_time'] * 90) + 1}",
            f"nonvoluntary_ctxt_switches:\t{int(task['cpu_time'] * 12)}",
        ]
        return "\n".join(lines) + "\n"

    file("status", _status)

    # ── stat — machine readable one-liner ────────────────────────
    def _stat_line() -> str:
        hz = 100
        utime = int(task["cpu_time"] * hz)
        starttime = max(int(adapter.uptime() * hz) - utime - 10, 1)
        nice = 0
        fields = [
            pid, f"({name})", state, ppid, pid, pid, 0, 0, 0,  # tty/pgroup
            0, 0,  # tpgid, flags
            12, 34, 2, 1,  # minflt cminflt majflt cmajflt
            utime, utime // 8,  # utime stime
            0, 0,  # cutime cstime
            int(task.get("priority", 0.5) * 100), nice, 1,  # priority nice threads
            0, starttime,  # itrealvalue, starttime
            vmsize, rss // 1024 * 4,  # vsize, rss (pages)
            0, 0, 0, 0, 0, 0,  # rsslim startcode endcode startstack kstkesp kstkeip
            0, 0, 0, 0, 0,  # signal blocked sigignore sigcatch wchan
            0, 0, 0,  # 0 0 exit_signal
            int(task["cpu_time"] * 1000),  # processor (last CPU)
            1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # rt prio, policy, delayacct...
        ]
        return " ".join(str(f) for f in fields) + "\n"

    file("stat", _stat_line)

    # ── statm — memory in pages: size resident shared text lib data dt
    def _statm() -> str:
        page = 4096
        size = vmsize // page
        resident = max(rss, 4096) // page
        return f"{size} {resident} 128 64 2048 {resident} 0\n"

    file("statm", _statm)

    # ── symlinks ─────────────────────────────────────────────────
    pid_dir.add(ProcSymlink("cwd", lambda: "/home/umer", owner=owner))
    pid_dir.add(ProcSymlink(
        "exe", lambda: f"/usr/bin/{name}", owner=owner))
    pid_dir.add(ProcSymlink("root", "/", owner=owner))

    # ── fd/ — open file descriptors ──────────────────────────────
    fd_dir = ProcDir("fd", mode=dir_mode, owner=owner)
    fd_dir.add(ProcSymlink("0", "/dev/null", owner=owner))
    fd_dir.add(ProcSymlink("1", "/dev/console", owner=owner))
    fd_dir.add(ProcSymlink("2", "/dev/console", owner=owner))
    pid_dir.add(fd_dir)

    # ── maps — memory mappings ───────────────────────────────────
    def _maps() -> str:
        exe_base = 0x00400000
        lines = [
            f"{exe_base:08x}-{exe_base + 0x10000:08x} r-xp 00000000 fd:01 {pid + 10:<8} /usr/bin/{name}",
            f"{exe_base + 0x10000:08x}-{exe_base + 0x11000:08x} r--p 00010000 fd:01 {pid + 10:<8} /usr/bin/{name}",
            "7f8a40000000-7f8a40100000 rw-p 00000000 00:00 0        [heap]",
            "7f8a50000000-7f8a50021000 r--p 00000000 fd:01 4096     /usr/lib/libumer.so",
            "7f8a51000000-7f8a51400000 rw-p 00000000 00:00 0        [stack]",
            "7ffd1c000000-7ffd1c021000 rw-p 00000000 00:00 0        [vvar]",
        ]
        for base, size_bytes in _pid_allocations(adapter, pid):
            lines.append(
                f"{base:016x}-{base + max(size_bytes, 1):016x} "
                f"rw-p 00000000 00:00 0        [umer_alloc:{size_bytes}]")
        return "\n".join(lines) + "\n"

    file("maps", _maps)

    # ── mem — process memory image (root only) ───────────────────
    pid_dir.add(ProcFile(
        "mem", lambda: f"<memory image of {name} ({rss} bytes resident)>\n",
        mode="r--------", virtual_size=rss))

    # ── cpu — last/current CPU ───────────────────────────────────
    file("cpu", lambda: f"cpu {pid % 2}\n")

    # ── io — I/O statistics ──────────────────────────────────────
    def _io() -> str:
        rchar = int(task["cpu_time"] * 16384) + 4096
        return (f"rchar: {rchar}\nwchar: {rchar // 4}\n"
                f"syscr: {int(task['cpu_time'] * 90) + 8}\n"
                f"syscw: {int(task['cpu_time'] * 12) + 2}\n"
                "read_bytes: 0\nwrite_bytes: 0\n"
                "cancelled_write_bytes: 0\n")

    file("io", _io)

    # ── misc knobs ───────────────────────────────────────────────
    file("loginuid", lambda: "4294967295\n")
    file("oom_score", lambda: f"{min(pid % 100, 99)}\n")
    file("oom_score_adj",
         lambda: f"{adapter.oom_adj.get(pid, 0)}\n",
         write=lambda text, p=pid: (
             gate.require(CAP_SYS_ADMIN),  # [FIX H207] privileged per-PID kill-priority write
             adapter.oom_adj.__setitem__(
                 p, max(-1000, min(1000, int(text.strip() or 0)))))[-1],
         mode="rw-r--r--")
    file("cgroup", lambda: "0::/\n")
    file("sched", lambda: (
        f"{name} ({pid})\n"
        "se.exec_start\t\t\t0.000000\n"
        "se.vruntime\t\t\t0.000000\n"
        "nr_migrations\t\t\t0\n"))

    # ── limits -- resource limits (rlimit) ────────────────────────
    def _limits() -> str:
        header = (
            "Limit                     Soft Limit           Hard Limit"
            "           Units     \n"
        )
        rows = [
            ("Max cpu time", "            unlimited", "            unlimited",
             "           seconds   "),
            ("Max file size", "            unlimited", "            unlimited",
             "           bytes     "),
            ("Max data size", "            unlimited", "            unlimited",
             "           bytes     "),
            ("Max stack size", "            8388608",  "            unlimited",
             "           bytes     "),
            ("Max core file size", "            0",
             "            unlimited", "           bytes     "),
            ("Max resident set", "            unlimited", "            unlimited",
             "           bytes     "),
            ("Max processes", "            30718",  "            30718",
             "           processes "),
            ("Max open files", "            1024",  "            1048576",
             "           files     "),
            ("Max locked memory", "            67108864",  "            67108864",
             "           bytes     "),
            ("Max address space", "            unlimited", "            unlimited",
             "           bytes     "),
            ("Max file locks", "            unlimited", "            unlimited",
             "           locks     "),
            ("Max pending signals", "            30718",  "            30718",
             "           signals   "),
            ("Max msgqueue size", "            819200",  "            819200",
             "           bytes     "),
            ("Max nice priority", "            0",  "            0",
             "                     "),
            ("Max realtime priority", "            0",  "            0",
             "                     "),
            ("Max realtime timeout", "            unlimited", "            unlimited",
             "           us        "),
        ]
        return header + "\n".join(
            "".join(cols) for cols in rows
        ) + "\n"

    file("limits", _limits)

    # ── mounts -- process mount list ──────────────────────────────
    def _proc_mounts() -> str:
        mounts = [
            "/dev/root / ext4 ro,relatime 0 0",
            "proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0",
            "sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0",
            "devtmpfs /dev devtmpfs rw,nosuid,size=1024k 0 0",
            "tmpfs /tmp tmpfs rw,nosuid,nodev,noexec 0 0",
        ]
        return "\n".join(mounts) + "\n"

    file("mounts", _proc_mounts)

    # ── mountinfo -- extended mount info ──────────────────────────
    def _proc_mountinfo() -> str:
        entries = [
            "0 0 8:1 / / rw,relatime shared:1 - ext4 /dev/root ro,errors=continue",
            "1 0 0:10 / /proc rw,nosuid,nodev,noexec,relatime shared:9"
            " - proc proc rw,nosuid,nodev,noexec,relatime",
            "2 1 0:11 / /sys rw,nosuid,nodev,noexec,relatime shared:2"
            " - sysfs sysfs rw,nosuid,nodev,noexec,relatime",
            "3 2 0:5 / /dev rw,nosuid shared:5"
            " - devtmpfs devtmpfs rw,nosuid,size=1024k,mode=755,uid=0",
            "4 0 0:12 / /tmp rw,nosuid,nodev shared:8"
            " - tmpfs tmpfs rw,nosuid,nodev,noexec",
        ]
        return "\n".join(entries) + "\n"

    file("mountinfo", _proc_mountinfo)

    # ── net/ -- per-process network info ──────────────────────────
    net_dir = ProcDir("net")

    def _net_dev() -> str:
        return (
            "Inter-|   Receive                                                "
            "|  Transmit\n"
            " face |bytes    packets errs drop fifo frame compressed"
            "    multicast|bytes    packets errs drop fifo frame compressed\n"
            "    lo:       0       0    0    0    0     0"
            "          0         0        0       0    0    0    0     0"
            "          0\n"
            "  eth0:       0       0    0    0    0     0"
            "          0         0        0       0    0    0    0     0"
            "          0\n"
        )

    net_dir.add(ProcFile("dev", _net_dev))

    def _net_tcp() -> str:
        return (
            "  sl  local_address rem_address   st tx_queue:rx_queue"
            " tr:tm->when retrnsmt   uid  timeout inode\n"
            "   0: 0100007F:0035 00000000:0000 0A"
            " 00000000:00000000 00:00000000 0"
            "        0 12345\n"
        )

    net_dir.add(ProcFile("tcp", _net_tcp))

    def _net_tcp6() -> str:
        return (
            "  sl  local_address                         "
            "remote_address                        st "
            "tx_queue:rx_queue tr:tm->when retrnsmt   uid  timeout inode\n"
            "   0: 00000000000000000000000001000000:0035"
            " 00000000000000000000000000000000:0000 0A"
            " 00000000:00000000 00:00000000 0"
            "        0 12346\n"
        )

    net_dir.add(ProcFile("tcp6", _net_tcp6))

    def _net_udp() -> str:
        return (
            "  sl  local_address rem_address   st"
            " tx_queue:rx_queue tr:tm->when retrnsmt   uid  timeout inode\n"
            "   0: 0100007F:0035 00000000:0000 0A"
            " 00000000:00000000 00:00000000 0"
            "        0 12347\n"
        )

    net_dir.add(ProcFile("udp", _net_udp))

    def _net_unix() -> str:
        return (
            "Num       RefCount Protocol Flags    Type St Inode Path\n"
            "         1: 00000002 00000000 00000000"
            " 0001 01     1234 /run/systemd/notify\n"
        )

    net_dir.add(ProcFile("unix", _net_unix))

    def _net_arp() -> str:
        return "IP address       HW type     Flags       HW address     Mask Device\n"

    net_dir.add(ProcFile("arp", _net_arp))

    def _net_route() -> str:
        return (
            "Iface   Destination     Gateway         Flags"
            "   RefCnt Use     Metric  Mask            MTU"
            "      Window  IRTT\n"
            "eth0    00000000        0100A8C0        0003"
            "   0       0       100     00000000        0"
            "       0       0\n"
        )

    net_dir.add(ProcFile("route", _net_route))

    def _net_netstat() -> str:
        return "TcpExt: SyncookiesSent 0 SyncookiesRecv 0\n"

    net_dir.add(ProcFile("netstat", _net_netstat))

    def _net_snmp() -> str:
        return (
            "Ip:\n"
            "    Forwarding   0    DefaultTTL   64\n"
            "Tcp:\n"
            "    RtoAlgorithm 1    RtoMin   200\n"
            "Udp:\n"
            "    InDatagrams  0    NoPorts  0\n"
        )

    net_dir.add(ProcFile("snmp", _net_snmp))

    pid_dir.add(net_dir)

    # ── task/ -- per-thread info ──────────────────────────────────
    task_dir = ProcDir("task")
    # Create a thread dir for the main thread (tid == pid)
    main_tid_dir = ProcDir(str(pid))
    main_tid_dir.add(ProcFile("comm", lambda: f"{name}\n"))
    main_tid_dir.add(ProcFile("status", lambda: (
        f"Name:\t{name}\n"
        f"State:\t{state} ({_STATUS_TEXT.get(state, 'unknown')})\n"
        f"Tgid:\t{pid}\n"
        f"Pid:\t{pid}\n"
        f"PPid:\t{ppid}\n"
        f"TracerPid:\t0\n"
        f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
        f"Gid:\t0\t0\t0\t0\n"
        f"FDSize:\t1024\n"
        f"Threads:\t1\n"
    )))
    main_tid_dir.add(ProcFile("stat", lambda: f"{pid} ({name}) {state} {ppid}\n"))
    main_tid_dir.add(ProcFile("wchan", lambda: "0\n"))
    main_tid_dir.add(ProcFile("syscall", lambda: "318\n"))
    main_tid_dir.add(ProcFile("smaps_rollup", lambda: (
        f"Rss:                {max(rss, 4096) // 1024} kB\n"
        f"Pss:                {max(rss, 4096) // 1024 // 2} kB\n"
    )))
    task_dir.add(main_tid_dir)
    pid_dir.add(task_dir)

    return pid_dir


def _pid_allocations(adapter, pid: int):
    """[(base, size)] of the memory manager's live allocations for pid."""
    allocs = getattr(getattr(adapter.kernel, "memory", None), "_allocs", None)
    if not allocs:
        return []
    out = []
    for base, entry in allocs.items():
        try:
            if isinstance(entry, tuple) and len(entry) == 3:
                entry_pid, _pages, size = entry
            elif isinstance(entry, tuple) and len(entry) == 2:
                entry_pid, size = entry
            else:
                continue
            if int(entry_pid) == pid:
                out.append((int(base), int(size)))
        except (TypeError, ValueError):
            continue
    return out


def pid_dir_signature(adapter, pid: int):
    """Cheap signature used to invalidate cached pid directories."""
    task = adapter.task(pid)
    if task is None:
        return None
    return (pid, task["name"], task["state"])
