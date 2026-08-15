"""UmerOS /proc virtual filesystem (procfs).

Provides a complete, Linux-compatible simulation of the ``/proc``
pseudo-filesystem described in the TLDP Linux Filesystem Hierarchy
documentation:

* **System files**: cpuinfo, meminfo, stat, interrupts, iomem, ioports,
  dma, kcore, kmsg, ksyms, partitions, swaps, slabinfo, devices,
  modules, mounts, filesystems, locks, fb, rtc, apm, mtrr, execdomains,
  bus/ (pci, usb, input), driver/ (rtc), ide/ (hda), scsi/, irq/, parport/
* **Per-process**: ``/proc/<pid>/`` with cmdline, environ, status, stat,
  statm, maps, mem, cpu, io, fd/, cwd, exe, root, oom_score_adj, cgroup, sched
* **/proc/sys**: writable sysctl tree (fs/, kernel/, vm/, net/, dev/, sunrpc/)
  backed by the kernel's ``SysctlRegistry``
* **/proc/net**: dev, tcp, udp, route, arp, unix, wireless, sockstat, icmp,
  snmp, ipv6 (tcp6, udp6, if_inet6), rpc/, bond0/
* **/proc/sysvipc**: msg, sem, shm (System V IPC)
* **/proc/tty**: drivers, ldiscs, driver/serial
* **/proc/self**: symlink to current task's directory

Usage (standalone)::

    from proc.procfs import ProcFileSystem
    from proc.kernel_adapter import KernelAdapter

    adapter = KernelAdapter()        # works without a kernel
    procfs = ProcFileSystem(adapter)
    print(procfs.read("/proc/meminfo"))
    print(procfs.list("/proc"))
    procfs.write("/proc/sys/kernel/hostname", "myhost")

Usage (kernel-integrated)::

    adapter = KernelAdapter(kernel=kernel)
    kernel.procfs = ProcFileSystem(adapter)
    kernel.procfs.mount_into_vfs(kernel.vfs)
    # Now cat /proc/meminfo in the shell reads live data.
"""
# Public API
from proc.procfs import ProcFileSystem
from proc.kernel_adapter import KernelAdapter

__all__ = [
    "ProcFileSystem",
    "KernelAdapter",
]
