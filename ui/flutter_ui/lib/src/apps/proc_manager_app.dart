/// UmerOS /proc Manager — Process & Kernel Information
///
/// Desktop control panel for the UmerOS /proc subsystem.
/// Manages process info, CPU, memory, mounts, interrupts, modules, etc.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class ProcManagerApp extends StatefulWidget {
  const ProcManagerApp({super.key});

  @override
  State<ProcManagerApp> createState() => _ProcManagerAppState();
}

class _ProcManagerAppState extends State<ProcManagerApp> {
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
              _Tab('CPU', 0, Icons.memory),
              _Tab('Memory', 1, Icons.storage),
              _Tab('Processes', 2, Icons.list),
              _Tab('Mounts', 3, Icons.storage),
              _Tab('Interrupts', 4, Icons.electrical_services),
              _Tab('Modules', 5, Icons.extension),
              _Tab('System', 6, Icons.info),
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
        return _CpuTab();
      case 1:
        return _MemoryTab();
      case 2:
        return _ProcessesTab();
      case 3:
        return _MountsTab();
      case 4:
        return _InterruptsTab();
      case 5:
        return _ModulesTab();
      case 6:
        return _SystemTab();
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

// ── Tab: CPU ─────────────────────────────────────────────
class _CpuTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'CPU Information (/proc/cpuinfo)',
            body: 'Processor details, cores, cache, and features.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Model', value: 'Intel Core i9-13900K'),
          _InfoRow(label: 'Cores', value: '24 (8P + 16E)'),
          _InfoRow(label: 'Threads', value: '32'),
          _InfoRow(label: 'Frequency', value: '3.0 - 5.8 GHz'),
          _InfoRow(label: 'Cache', value: '36 MB L3'),
          _InfoRow(label: 'Architecture', value: 'x86_64'),
          _InfoRow(label: 'Features', value: 'AVX2, AVX-512, VT-x, AES-NI'),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        title: Text(label, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Text(value, style: GoogleFonts.inter(fontSize: 12, color: Colors.grey.shade700)),
      ),
    );
  }
}

// ── Tab: Memory ──────────────────────────────────────────
class _MemoryTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Memory Information (/proc/meminfo)',
            body: 'RAM usage, swap, buffers, and cache statistics.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Total RAM', value: '64 GB'),
          _InfoRow(label: 'Available', value: '48.2 GB'),
          _InfoRow(label: 'Used', value: '15.8 GB'),
          _InfoRow(label: 'Buffers', value: '2.1 GB'),
          _InfoRow(label: 'Cached', value: '12.4 GB'),
          _InfoRow(label: 'Swap Total', value: '8 GB'),
          _InfoRow(label: 'Swap Used', value: '0 GB'),
          const SizedBox(height: 16),
          LinearProgressIndicator(
            value: 15.8 / 64,
            minHeight: 8,
            borderRadius: BorderRadius.circular(4),
          ),
        ],
      ),
    );
  }
}

// ── Tab: Processes ───────────────────────────────────────
class _ProcessesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Process Information (/proc)',
            body: 'Running processes with PID, state, memory, and CPU usage.',
          ),
          const SizedBox(height: 16),
          _ProcessEntry(pid: 1, name: 'systemd', state: 'S', cpu: '0.0%', mem: '12.4 MB'),
          _ProcessEntry(pid: 2, name: 'kthreadd', state: 'S', cpu: '0.0%', mem: '0.0 MB'),
          _ProcessEntry(pid: 100, name: 'python3', state: 'R', cpu: '2.5%', mem: '128 MB'),
          _ProcessEntry(pid: 200, name: 'flutter', state: 'R', cpu: '5.0%', mem: '256 MB'),
          _ProcessEntry(pid: 300, name: 'bash', state: 'S', cpu: '0.0%', mem: '8.0 MB'),
          _ProcessEntry(pid: 400, name: 'nginx', state: 'S', cpu: '0.1%', mem: '16 MB'),
        ],
      ),
    );
  }
}

class _ProcessEntry extends StatelessWidget {
  final int pid;
  final String name;
  final String state;
  final String cpu;
  final String mem;
  const _ProcessEntry({
    required this.pid,
    required this.name,
    required this.state,
    required this.cpu,
    required this.mem,
  });

  @override
  Widget build(BuildContext context) {
    final stateColor = state == 'R' ? Colors.green : state == 'S' ? Colors.blue : Colors.grey;
    final stateLabel = state == 'R' ? 'Running' : state == 'S' ? 'Sleeping' : 'Other';
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: stateColor.withValues(alpha: 0.15),
          child: Text('$pid', style: GoogleFonts.firaCode(fontSize: 10, color: stateColor, fontWeight: FontWeight.bold)),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('State: $stateLabel · CPU: $cpu · MEM: $mem'),
      ),
    );
  }
}

// ── Tab: Mounts ──────────────────────────────────────────
class _MountsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Mount Information (/proc/mounts)',
            body: 'Currently mounted filesystems and their options.',
          ),
          const SizedBox(height: 16),
          _MountEntry(device: '/dev/sda1', mount: '/', fs: 'ext4', options: 'rw,relatime'),
          _MountEntry(device: '/dev/sda2', mount: '/boot', fs: 'ext4', options: 'rw,relatime'),
          _MountEntry(device: 'tmpfs', mount: '/tmp', fs: 'tmpfs', options: 'rw,nosuid,nodev'),
          _MountEntry(device: 'proc', mount: '/proc', fs: 'proc', options: 'rw,nosuid,nodev,noexec'),
          _MountEntry(device: 'sysfs', mount: '/sys', fs: 'sysfs', options: 'rw,nosuid,nodev,noexec'),
        ],
      ),
    );
  }
}

class _MountEntry extends StatelessWidget {
  final String device;
  final String mount;
  final String fs;
  final String options;
  const _MountEntry({
    required this.device,
    required this.mount,
    required this.fs,
    required this.options,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.storage, color: Colors.teal, size: 20),
        title: Text('$device → $mount', style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$fs · $options', style: GoogleFonts.inter(fontSize: 11)),
      ),
    );
  }
}

// ── Tab: Interrupts ─────────────────────────────────────
class _InterruptsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Interrupts (/proc/interrupts)',
            body: 'Hardware and software interrupt statistics.',
          ),
          const SizedBox(height: 16),
          _InterruptEntry(irq: 0, name: 'timer', count: '1,234,567', color: Colors.blue),
          _InterruptEntry(irq: 1, name: 'keyboard', count: '45,678', color: Colors.green),
          _InterruptEntry(irq: 8, name: 'rtc0', count: '12,345', color: Colors.orange),
          _InterruptEntry(irq: 16, name: 'eth0', count: '987,654', color: Colors.purple),
          _InterruptEntry(irq: 24, name: 'ahci', count: '234,567', color: Colors.teal),
        ],
      ),
    );
  }
}

class _InterruptEntry extends StatelessWidget {
  final int irq;
  final String name;
  final String count;
  final Color color;
  const _InterruptEntry({
    required this.irq,
    required this.name,
    required this.count,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Text('$irq', style: GoogleFonts.firaCode(fontSize: 10, color: color, fontWeight: FontWeight.bold)),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Text(count, style: GoogleFonts.firaCode(fontSize: 12, color: Colors.grey.shade700)),
      ),
    );
  }
}

// ── Tab: Modules ─────────────────────────────────────────
class _ModulesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Loaded Kernel Modules (/proc/modules)',
            body: 'Currently loaded kernel modules and their state.',
          ),
          const SizedBox(height: 16),
          _ModuleEntry(name: 'ext4', size: '1.2 MB', used: 2, state: 'Live', color: Colors.green),
          _ModuleEntry(name: 'xfs', size: '890 KB', used: 0, state: 'Live', color: Colors.green),
          _ModuleEntry(name: 'nvidia', size: '45 MB', used: 1, state: 'Live', color: Colors.green),
          _ModuleEntry(name: 'bluetooth', size: '320 KB', used: 0, state: 'Live', color: Colors.blue),
          _ModuleEntry(name: 'usb_storage', size: '64 KB', used: 1, state: 'Live', color: Colors.blue),
        ],
      ),
    );
  }
}

class _ModuleEntry extends StatelessWidget {
  final String name;
  final String size;
  final int used;
  final String state;
  final Color color;
  const _ModuleEntry({
    required this.name,
    required this.size,
    required this.used,
    required this.state,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.extension, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Size: $size · Used by: $used'),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: Colors.green.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(state, style: GoogleFonts.inter(fontSize: 10, color: Colors.green, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: System ──────────────────────────────────────────
class _SystemTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'System Information',
            body: 'Kernel version, uptime, load average, and system stats.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Kernel Version', value: '6.8.0-umeros'),
          _InfoRow(label: 'Uptime', value: '3 days, 14:22:05'),
          _InfoRow(label: 'Load Average', value: '0.42, 0.38, 0.35'),
          _InfoRow(label: 'Hostname', value: 'umeros-dev'),
          _InfoRow(label: 'Architecture', value: 'x86_64'),
          _InfoRow(label: 'Processes', value: '142'),
          _InfoRow(label: 'Threads', value: '387'),
        ],
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