/// UmerOS /usr Manager — Userspace API & System Services
///
/// Desktop control panel for the UmerOS /usr subsystem.
/// Manages syscalls, io_uring, seccomp, landlock, ELF loader,
/// procfs, sysfs, netlink, TEE, perf, and more.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class UsrManagerApp extends StatefulWidget {
  const UsrManagerApp({super.key});

  @override
  State<UsrManagerApp> createState() => _UsrManagerAppState();
}

class _UsrManagerAppState extends State<UsrManagerApp> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      children: [
        Container(
          decoration: BoxDecoration(
            color: scheme.surface,
            border: Border(
              bottom: BorderSide(color: scheme.outline.withValues(alpha: 0.2)),
            ),
          ),
          child: AutoAdjustRow(
            spacing: 0,
            children: [
              _Tab('Syscalls', 0, Icons.code),
              _Tab('io_uring', 1, Icons.speed),
              _Tab('Security', 2, Icons.shield),
              _Tab('ProcFS', 3, Icons.folder_open),
              _Tab('Netlink', 4, Icons.network_check),
              _Tab('TEE', 5, Icons.lock),
              _Tab('Perf', 6, Icons.analytics),
              _Tab('Libraries', 7, Icons.library_books),
            ].map((t) => _TabButton(
              label: t.label,
              icon: t.icon,
              isSelected: _tab == t.index,
              onTap: () => setState(() => _tab = t.index),
            )).toList(),
          ),
        ),
        Expanded(child: _buildTabContent()),
      ],
    );
  }

  Widget _buildTabContent() {
    switch (_tab) {
      case 0:
        return _SyscallsTab();
      case 1:
        return _IoUringTab();
      case 2:
        return _SecurityTab();
      case 3:
        return _ProcFsTab();
      case 4:
        return _NetlinkTab();
      case 5:
        return _TeeTab();
      case 6:
        return _PerfTab();
      case 7:
        return _LibrariesTab();
      default:
        return const SizedBox.shrink();
    }
  }
}

class _Tab {
  final String label;
  final int index;
  final IconData icon;
  const _Tab(this.label, this.index, this.icon);
}

class _TabButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;
  const _TabButton({
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              width: 2,
              color: isSelected ? scheme.primary : Colors.transparent,
            ),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: isSelected ? scheme.primary : scheme.onSurfaceVariant),
            const SizedBox(width: 6),
            Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                color: isSelected ? scheme.primary : scheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Tab: Syscalls ────────────────────────────────────────
class _SyscallsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Userspace System Calls',
            body: 'Modern Linux syscall interfaces: unshare, futex2, rseq, '
                'mseal, and more. These provide process isolation, '
                'fast userspace synchronization, and memory sealing.',
          ),
          const SizedBox(height: 16),
          _SyscallCard(name: 'unshare', description: 'Unshare process execution context', status: 'Active', icon: Icons.call_split, color: Colors.blue),
          _SyscallCard(name: 'futex2', description: 'Fast userspace mutex v2', status: 'Active', icon: Icons.lock, color: Colors.green),
          _SyscallCard(name: 'rseq', description: 'Restartable sequences for per-CPU data', status: 'Active', icon: Icons.refresh, color: Colors.orange),
          _SyscallCard(name: 'mseal', description: 'Memory sealing for security', status: 'Active', icon: Icons.security, color: Colors.red),
          _SyscallCard(name: 'io_uring', description: 'Async I/O ring buffer', status: 'Active', icon: Icons.speed, color: Colors.purple),
          _SyscallCard(name: 'seccomp', description: 'Secure computing mode filter', status: 'Active', icon: Icons.filter_alt, color: Colors.teal),
          _SyscallCard(name: 'landlock', description: 'Unprivileged sandboxing', status: 'Active', icon: Icons.security, color: Colors.brown),
        ],
      ),
    );
  }
}

class _SyscallCard extends StatelessWidget {
  final String name;
  final String description;
  final String status;
  final IconData icon;
  final Color color;
  const _SyscallCard({
    required this.name,
    required this.description,
    required this.status,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Icon(icon, color: color, size: 18),
        ),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(description, style: GoogleFonts.inter(fontSize: 12)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: Colors.green.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(status, style: GoogleFonts.inter(fontSize: 10, color: Colors.green, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: io_uring ────────────────────────────────────────
class _IoUringTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'io_uring — Async I/O Ring Buffer',
            body: 'High-performance asynchronous I/O interface. '
                'Supports submission queue (SQ) and completion queue (CQ) '
                'with zero-copy operations.',
          ),
          const SizedBox(height: 16),
          _StatCard(label: 'SQ Entries', value: '256', color: Colors.blue),
          _StatCard(label: 'CQ Entries', value: '512', color: Colors.green),
          _StatCard(label: 'Pending I/O', value: '0', color: Colors.orange),
          _StatCard(label: 'Completed', value: '1,247', color: Colors.purple),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _StatCard({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Icon(Icons.speed, color: color, size: 18),
        ),
        title: Text(label, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Text(value, style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 16, color: color)),
      ),
    );
  }
}

// ── Tab: Security ────────────────────────────────────────
class _SecurityTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Security Subsystems',
            body: 'seccomp (secure computing), landlock (unprivileged sandboxing), '
                'and ntsync (NT synchronization primitives).',
          ),
          const SizedBox(height: 16),
          _SecurityEntry(name: 'seccomp', description: 'BPF-based syscall filtering', status: 'Active', color: Colors.green),
          _SecurityEntry(name: 'landlock', description: 'Filesystem access control (unprivileged)', status: 'Active', color: Colors.green),
          _SecurityEntry(name: 'ntsync', description: 'NT mutex/semaphore emulation', status: 'Active', color: Colors.green),
          _SecurityEntry(name: 'dmabuf', description: 'DMA buffer sharing', status: 'Active', color: Colors.blue),
          _SecurityEntry(name: 'iommufd', description: 'IOMMU file descriptor', status: 'Active', color: Colors.blue),
        ],
      ),
    );
  }
}

class _SecurityEntry extends StatelessWidget {
  final String name;
  final String description;
  final String status;
  final Color color;
  const _SecurityEntry({
    required this.name,
    required this.description,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Icon(Icons.shield, color: color, size: 18),
        ),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(description, style: GoogleFonts.inter(fontSize: 12)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: Colors.green.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(status, style: GoogleFonts.inter(fontSize: 10, color: Colors.green, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: ProcFS ──────────────────────────────────────────
class _ProcFsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'ProcFS & SysFS',
            body: 'Virtual filesystems exposing kernel and process information. '
                '/proc for process info, /sys for device/driver info.',
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'ProcFS Entries'),
          const SizedBox(height: 8),
          _ProcEntry(path: '/proc/cpuinfo', description: 'CPU information', type: 'File'),
          _ProcEntry(path: '/proc/meminfo', description: 'Memory statistics', type: 'File'),
          _ProcEntry(path: '/proc/uptime', description: 'System uptime', type: 'File'),
          _ProcEntry(path: '/proc/loadavg', description: 'Load average', type: 'File'),
          _ProcEntry(path: '/proc/self', description: 'Current process', type: 'Symlink'),
          _ProcEntry(path: '/proc/version', description: 'Kernel version', type: 'File'),
          const SizedBox(height: 16),
          _SectionTitle(title: 'SysFS Entries'),
          const SizedBox(height: 8),
          _ProcEntry(path: '/sys/class', description: 'Device classes', type: 'Dir'),
          _ProcEntry(path: '/sys/devices', description: 'Device tree', type: 'Dir'),
          _ProcEntry(path: '/sys/kernel', description: 'Kernel parameters', type: 'Dir'),
        ],
      ),
    );
  }
}

class _ProcEntry extends StatelessWidget {
  final String path;
  final String description;
  final String type;
  const _ProcEntry({
    required this.path,
    required this.description,
    required this.type,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(
          type == 'Dir' ? Icons.folder : type == 'Symlink' ? Icons.link : Icons.description,
          color: Colors.teal,
          size: 20,
        ),
        title: Text(path, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(description, style: GoogleFonts.inter(fontSize: 11)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: Colors.teal.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(type, style: GoogleFonts.inter(fontSize: 10, color: Colors.teal, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Netlink ─────────────────────────────────────────
class _NetlinkTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Netlink — Kernel-Userspace Communication',
            body: 'Socket-based interface for kernel-userspace communication. '
                'Used for routing, firewall, and network configuration.',
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Netlink Families'),
          const SizedBox(height: 8),
          _NetlinkEntry(family: 'NETLINK_ROUTE', description: 'Routing and link configuration', id: 0),
          _NetlinkEntry(family: 'NETLINK_FIREWALL', description: 'Firewall packet filtering', id: 3),
          _NetlinkEntry(family: 'NETLINK_INET_DIAG', description: 'Socket diagnostics', id: 4),
          _NetlinkEntry(family: 'NETLINK_NFLOG', description: 'Netfilter logging', id: 5),
          _NetlinkEntry(family: 'NETLINK_XFRM', description: 'IPsec transform', id: 6),
          _NetlinkEntry(family: 'NETLINK_SELINUX', description: 'SELinux notifications', id: 7),
        ],
      ),
    );
  }
}

class _NetlinkEntry extends StatelessWidget {
  final String family;
  final String description;
  final int id;
  const _NetlinkEntry({
    required this.family,
    required this.description,
    required this.id,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.network_check, color: Colors.cyan, size: 20),
        title: Text(family, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(description, style: GoogleFonts.inter(fontSize: 11)),
        trailing: Text('ID: $id', style: GoogleFonts.firaCode(fontSize: 11, color: Colors.grey)),
      ),
    );
  }
}

// ── Tab: TEE ─────────────────────────────────────────────
class _TeeTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Trusted Execution Environment (TEE)',
            body: 'Hardware-backed secure execution for sensitive operations. '
                'Supports OP-TEE and AMD SEV-style enclaves.',
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'TEE Status'),
          const SizedBox(height: 8),
          _TeeStatus(name: 'OP-TEE', status: 'Available', color: Colors.green, icon: Icons.verified_user),
          _TeeStatus(name: 'AMD SEV', status: 'Not Available', color: Colors.grey, icon: Icons.block),
          _TeeStatus(name: 'Intel SGX', status: 'Not Available', color: Colors.grey, icon: Icons.block),
          _TeeStatus(name: 'ARM TrustZone', status: 'Simulated', color: Colors.orange, icon: Icons.memory),
        ],
      ),
    );
  }
}

class _TeeStatus extends StatelessWidget {
  final String name;
  final String status;
  final Color color;
  final IconData icon;
  const _TeeStatus({
    required this.name,
    required this.status,
    required this.color,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Icon(icon, color: color, size: 18),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(status, style: GoogleFonts.inter(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Perf ────────────────────────────────────────────
class _PerfTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Performance Monitoring (perf)',
            body: 'Linux perf tool integration for CPU profiling, '
                'hardware counters, and trace analysis.',
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Performance Counters'),
          const SizedBox(height: 8),
          _PerfCounter(name: 'CPU Cycles', value: '2.4 GHz', color: Colors.blue),
          _PerfCounter(name: 'Instructions', value: '1.8 IPC', color: Colors.green),
          _PerfCounter(name: 'Cache Misses', value: '3.2%', color: Colors.orange),
          _PerfCounter(name: 'Branch Misses', value: '1.1%', color: Colors.red),
          _PerfCounter(name: 'Context Switches', value: '1,247/s', color: Colors.purple),
        ],
      ),
    );
  }
}

class _PerfCounter extends StatelessWidget {
  final String name;
  final String value;
  final Color color;
  const _PerfCounter({
    required this.name,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.speed, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Text(value, style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 13, color: color)),
      ),
    );
  }
}

// ── Tab: Libraries ───────────────────────────────────────
class _LibrariesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: '/usr/lib — Shared Libraries',
            body: 'Manages shared libraries, ELF loading, and dynamic linking. '
                'Supports LD_PRELOAD, rpath, and library versioning.',
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Library Status'),
          const SizedBox(height: 8),
          _LibEntry(name: 'libc.so.6', version: '2.38', status: 'Loaded', color: Colors.green),
          _LibEntry(name: 'libm.so.6', version: '2.38', status: 'Loaded', color: Colors.green),
          _LibEntry(name: 'libpthread.so.0', version: '2.38', status: 'Loaded', color: Colors.green),
          _LibEntry(name: 'libdl.so.2', version: '2.38', status: 'Loaded', color: Colors.green),
          _LibEntry(name: 'librt.so.1', version: '2.38', status: 'Loaded', color: Colors.green),
          _LibEntry(name: 'libcrypto.so.3', version: '3.0', status: 'Available', color: Colors.blue),
          _LibEntry(name: 'libssl.so.3', version: '3.0', status: 'Available', color: Colors.blue),
        ],
      ),
    );
  }
}

class _LibEntry extends StatelessWidget {
  final String name;
  final String version;
  final String status;
  final Color color;
  const _LibEntry({
    required this.name,
    required this.version,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.library_books, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Version $version', style: GoogleFonts.inter(fontSize: 11)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(status, style: GoogleFonts.inter(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Shared widgets ───────────────────────────────────────
class _InfoCard extends StatelessWidget {
  final String title;
  final String body;
  const _InfoCard({required this.title, required this.body});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.blue.shade50,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.blue.shade100),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.blue.shade900)),
          const SizedBox(height: 4),
          Text(body, style: GoogleFonts.inter(fontSize: 12, color: Colors.blue.shade800, height: 1.4)),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle({required this.title});

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w600),
    );
  }
}