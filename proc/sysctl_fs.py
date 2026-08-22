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

"""/proc/sys/* — runtime-tunable kernel parameters.

Each subdirectory under /proc/sys mirrors a kernel subsystem:

    fs/     file-system limits (file-max, inode-max, etc.)
    kernel/ panic timeout, hostname, domainname, osrelease, printk
    vm/     memory management knobs (overcommit_memory, etc.)
    net/    networking tunables (icmp_echo_ignore_all, etc.)
    dev/    device parameters
    sunrpc/ NFS/RPC debug toggles

Writes are validated and persisted by the kernel's ``SysctlRegistry``.
Reads format values as plain strings (``cat`` style), exactly like
the real /proc/sys on Linux.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from proc.nodes import ProcDir, ProcFile

if TYPE_CHECKING:
    from proc.procfs import ProcFileSystem


def register_sysctl_entries(fs: "ProcFileSystem") -> None:
    adapter = fs.adapter
    registry = adapter.sysctl_registry()

    sys_dir = ProcDir("sys")
    fs.root.add(sys_dir)

    def _rfile(parent, name, sysctl_path, write=None, mode="rw-r--r--",
               writable_override=None):
        """Create a read-only or writable file backed by a sysctl path."""
        readable = lambda: f"{registry.get(sysctl_path, 0)}\n"

        def writable_func(text):
            val_str = text.strip()
            meta = registry.meta(sysctl_path)
            if meta and meta.get("type") == "int":
                registry.set(sysctl_path, int(val_str))
            elif meta and meta.get("type") == "bool":
                registry.set(sysctl_path, val_str.lower() in ("1", "true", "yes"))
            else:
                registry.set(sysctl_path, val_str)

        parent.add(ProcFile(name, read=readable,
                            write=writable_func if (writable_override or write) else None,
                            mode=mode))

    # ── /proc/sys/fs/ ──────────────────────────────────────────
    fs_dir = ProcDir("fs")
    sys_dir.add(fs_dir)
    _rfile(fs_dir, "file-max", "fs.file_max", write=True)
    _rfile(fs_dir, "file-nr", "fs.file_nr", mode="r--r--r--")
    _rfile(fs_dir, "inode-max", "fs.inode_max", write=True)
    _rfile(fs_dir, "inode-nr", "fs.inode_nr", mode="r--r--r--")
    _rfile(fs_dir, "inode-state", "fs.inode_state", mode="r--r--r--")
    _rfile(fs_dir, "dentry-state", "fs.dentry_state", mode="r--r--r--")
    _rfile(fs_dir, "super-nr", "fs.super_nr", mode="r--r--r--")
    _rfile(fs_dir, "super-max", "fs.super_max", write=True)
    _rfile(fs_dir, "dquot-max", "fs.dquot_max", write=True)
    _rfile(fs_dir, "dquot-nr", "fs.dquot_nr", mode="r--r--r--")
    _rfile(fs_dir, "overflowuid", "fs.overflowuid", mode="r--r--r--")
    _rfile(fs_dir, "overflowgid", "fs.overflowgid", mode="r--r--r--")
    _rfile(fs_dir, "pipe-max-size", "fs.pipe-max-size", write=True)
    _rfile(fs_dir, "pipe-user-pages-soft", "fs.pipe_user_soft",
           write=True, mode="rw-r--r--")
    _rfile(fs_dir, "pipe-user-pages-hard", "fs.pipe_user_hard",
           write=True, mode="rw-r--r--")

    # ── /proc/sys/kernel/ ──────────────────────────────────────
    kern = ProcDir("kernel")
    sys_dir.add(kern)

    # kernel.panic_timeout, hung_task_timeout, warn_limit, panic_on_taint
    # are already registered by the kernel.  We expose them here.
    _rfile(kern, "panic_timeout", "kernel.panic_timeout", write=True)
    _rfile(kern, "hung_task_timeout", "kernel.hung_task_timeout", write=True)
    _rfile(kern, "warn_limit", "kernel.warn_limit", write=True)
    _rfile(kern, "panic_on_taint", "kernel.panic_on_taint", write=True)

    # hostname / domainname — dynamic values, not from sysctl registry
    def _hostname():
        return adapter.hostname + "\n"

    kern.add(ProcFile("hostname", _hostname,
                      write=lambda text: setattr(adapter, "hostname",
                                                  text.strip() + "\n")))
    kern.add(ProcFile("domainname",
                      lambda: getattr(adapter, "_domainname", "(none)") + "\n",
                      write=lambda text: setattr(adapter, "_domainname",
                                                  text.strip() + "\n")))
    kern.add(ProcFile("osrelease",
                      lambda: "2.1.0-quantum\n", mode="r--r--r--"))
    kern.add(ProcFile("ostype",
                      lambda: "UmerOS\n", mode="r--r--r--"))
    kern.add(ProcFile("version",
                      lambda: "#1 SMP PREEMPT QUANTUM UmerOS\n",
                      mode="r--r--r--"))
    kern.add(ProcFile("ctrl-alt-del",
                      lambda: "0\n", write=lambda text: None))
    kern.add(ProcFile("acct",
                      lambda: "4 2 30\n", write=lambda text: None))
    kern.add(ProcFile("printk",
                      lambda: "6 4 1 7\n", write=lambda text: None))
    kern.add(ProcFile("ngroups_max",
                      lambda: "65536\n", mode="r--r--r--"))
    kern.add(ProcFile("pid_max",
                      lambda: "32768\n", mode="r--r--r--"))
    kern.add(ProcFile("threads-max",
                      lambda: "14626\n", write=True))
    kern.add(ProcFile("sem",
                      lambda: "250\t32000\t32\t128\n", write=lambda text: None))
    kern.add(ProcFile("shmall",
                      lambda: "18446744073692774399\n", write=True))
    kern.add(ProcFile("shmmax",
                      lambda: "18446744073692774399\n", write=True))
    kern.add(ProcFile("shmmni",
                      lambda: "4096\n", write=True))
    kern.add(ProcFile("msgmax",
                      lambda: "8192\n", write=True))
    kern.add(ProcFile("msgmnb",
                      lambda: "16384\n", write=True))
    kern.add(ProcFile("msgmni",
                      lambda: "32000\n", write=True))
    kern.add(ProcFile("auto_msgmni",
                      lambda: "1\n", write=lambda text: None))
    kern.add(ProcFile("randomize_va_space",
                      lambda: "2\n", write=lambda text: None))

    # ── /proc/sys/vm/ ──────────────────────────────────────────
    vm = ProcDir("vm")
    sys_dir.add(vm)
    _rfile(vm, "overcommit_memory", "vm.overcommit_memory", write=True)
    _rfile(vm, "overcommit_ratio", "vm.overcommit_ratio", write=True)
    _rfile(vm, "pagecache", "vm.pagecache", write=True)
    _rfile(vm, "min_free_kbytes", "vm.min_free_kbytes", write=True)
    _rfile(vm, "swappiness", "vm.swappiness", write=True)
    _rfile(vm, "vfs_cache_pressure", "vm.vfs_cache_pressure", write=True)
    _rfile(vm, "dirty_ratio", "vm.dirty_ratio", write=True)
    _rfile(vm, "dirty_background_ratio", "vm.dirty_background_ratio",
           write=True)
    _rfile(vm, "drop_caches", "vm.drop_caches", write=True)
    _rfile(vm, "compact_memory", "vm.compact_memory", write=True)
    _rfile(vm, "stat_refresh", "vm.stat_refresh", write=True)

    # ── /proc/sys/net/ ─────────────────────────────────────────
    net_sys = ProcDir("net")
    sys_dir.add(net_sys)

    # net/core
    core = ProcDir("core")
    net_sys.add(core)
    _rfile(core, "rmem_default", "net.core.rmem_default", write=True)
    _rfile(core, "rmem_max", "net.core.rmem_max", write=True)
    _rfile(core, "wmem_default", "net.core.wmem_default", write=True)
    _rfile(core, "wmem_max", "net.core.wmem_max", write=True)
    _rfile(core, "netdev_max_backlog", "net.core.netdev_max_backlog",
           write=True)
    _rfile(core, "somaxconn", "net.core.somaxconn", write=True)
    _rfile(core, "message_burst", "net.core.message_burst", write=True)
    _rfile(core, "message_cost", "net.core.message_cost", write=True)
    _rfile(core, "optmem_max", "net.core.optmem_max", write=True)

    # net/unix
    unix_sys = ProcDir("unix")
    net_sys.add(unix_sys)
    _rfile(unix_sys, "max_dgram_qlen", "net.unix.max_dgram_qlen", write=True)
    _rfile(unix_sys, "max_dgram_qlen", "net.unix.dgram_queue_depth",
           mode="r--r--r--")

    # net/ipv4
    ipv4 = ProcDir("ipv4")
    net_sys.add(ipv4)
    _rfile(ipv4, "icmp_echo_ignore_all", "net.ipv4.icmp_echo_ignore_all",
           write=True)
    _rfile(ipv4, "icmp_echo_ignore_broadcasts",
           "net.ipv4.icmp_echo_ignore_broadcasts", write=True)
    _rfile(ipv4, "ip_forward", "net.ipv4.ip_forward", write=True)
    _rfile(ipv4, "ip_local_port_range",
           "net.ipv4.ip_local_port_range", write=True)
    _rfile(ipv4, "ip_default_ttl", "net.ipv4.ip_default_ttl", write=True)
    _rfile(ipv4, "tcp_keepalive_time", "net.ipv4.tcp_keepalive_time",
           write=True)
    _rfile(ipv4, "tcp_keepalive_probes",
           "net.ipv4.tcp_keepalive_probes", write=True)
    _rfile(ipv4, "tcp_syncookies", "net.ipv4.tcp_syncookies", write=True)
    _rfile(ipv4, "tcp_tw_reuse", "net.ipv4.tcp_tw_reuse", write=True)
    _rfile(ipv4, "tcp_max_syn_backlog",
           "net.ipv4.tcp_max_syn_backlog", write=True)

    # ── /proc/sys/dev/ ──────────────────────────────────────────
    dev = ProcDir("dev")
    sys_dir.add(dev)
    cdrom = ProcDir("cdrom")
    dev.add(cdrom)
    cdrom.add(ProcFile("info", lambda: (
        "CD-ROM information, Id: cdrom.c 3.20 2003/12/17\n\n"
        "drive name:\tqcd0\n"
        "drive speed:\t48\n"
        "drive # of slots:\t1\n"
        "Can close tray:\t1\n"
        "Can open tray:\t1\n"
        "Can lock tray:\t1\n"
        "Can change speed:\t1\n"
        "Can select disk:\t0\n"
        "Can read multisession:\t1\n"
        "Can read MCN:\t1\n"
        "Reports media changed:\t1\n"
        "Can play audio:\t1\n"
        "Can write CD-R:\t0\n"
        "Can write CD-RW:\t0\n"
        "Can read DVD:\t1\n"
        "Can write DVD-R:\t0\n"
        "Can write DVD-RAM:\t0\n"
    )))

    # ── /proc/sys/sunrpc/ ──────────────────────────────────────
    sunrpc = ProcDir("sunrpc")
    sys_dir.add(sunrpc)
    sunrpc.add(ProcFile("debug", lambda: "0 0 0 0\n"))
    sunrpc.add(ProcFile("nlm_debug", lambda: "0\n"))
    sunrpc.add(ProcFile("rpc_debug", lambda: "0\n"))
