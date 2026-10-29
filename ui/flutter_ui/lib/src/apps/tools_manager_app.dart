/// UmerOS Tools Manager — System Tools & Diagnostics
///
/// Desktop control panel for the UmerOS /tools subsystem.
/// Manages installation, system info, disk, network, and process tools.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class ToolsManagerApp extends StatefulWidget {
  const ToolsManagerApp({super.key});

  @override
  State<ToolsManagerApp> createState() => _ToolsManagerAppState();
}

class _ToolsManagerAppState extends State<ToolsManagerApp> {
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
              _Tab('System Info', 0, Icons.info),
              _Tab('Disk', 1, Icons.storage),
              _Tab('Network', 2, Icons.network_check),
              _Tab('Processes', 3, Icons.list),
              _Tab('Installer', 4, Icons.install_desktop),
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
        return _SystemInfoTab();
      case 1:
        return _DiskTab();
      case 2:
        return _NetworkTab();
      case 3:
        return _ProcessesTab();
      case 4:
        return _InstallerTab();
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

// ── Tab: System Info ─────────────────────────────────────
class _SystemInfoTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'System Information',
            body: 'Hardware and OS information for diagnostics.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'OS', value: 'UmerOS 1.0.0-pre-alpha'),
          _InfoRow(label: 'Kernel', value: 'Python (userspace simulation)'),
          _InfoRow(label: 'Hostname', value: 'umeros'),
          _InfoRow(label: 'Architecture', value: 'x86_64'),
          _InfoRow(label: 'CPU', value: 'Intel64 (20 cores)'),
          _InfoRow(label: 'Memory', value: '607725 MB'),
          _InfoRow(label: 'Python', value: '3.14.6'),
          _InfoRow(label: 'Platform', value: 'Windows 10'),
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

// ── Tab: Disk ────────────────────────────────────────────
class _DiskTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Disk Management',
            body: 'Disk usage and partition information.',
          ),
          const SizedBox(height: 16),
          _DiskEntry(device: 'C:', mount: '/', fs: 'NTFS', size: '1.8 TB', used: '45%', free: '990 GB'),
          _DiskEntry(device: 'D:', mount: '/data', fs: 'NTFS', size: '2.0 TB', used: '30%', free: '1.4 TB'),
        ],
      ),
    );
  }
}

class _DiskEntry extends StatelessWidget {
  final String device;
  final String mount;
  final String fs;
  final String size;
  final String used;
  final String free;
  const _DiskEntry({
    required this.device,
    required this.mount,
    required this.fs,
    required this.size,
    required this.used,
    required this.free,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Colors.blue.withValues(alpha: 0.15),
          child: const Icon(Icons.storage, color: Colors.blue, size: 18),
        ),
        title: Text('$device ($mount)', style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$fs · $size total · $free free'),
        trailing: Text(used, style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 13)),
      ),
    );
  }
}

// ── Tab: Network ─────────────────────────────────────────
class _NetworkTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Network Diagnostics',
            body: 'Ping, DNS lookup, and port checking tools.',
          ),
          const SizedBox(height: 16),
          _NetworkTool(name: 'Ping', description: 'Test connectivity to a host', icon: Icons.network_ping, color: Colors.green),
          _NetworkTool(name: 'DNS Lookup', description: 'Resolve hostname to IP', icon: Icons.dns, color: Colors.blue),
          _NetworkTool(name: 'Port Check', description: 'Check if a port is open', icon: Icons.lan, color: Colors.orange),
          _NetworkTool(name: 'Traceroute', description: 'Trace network path to host', icon: Icons.route, color: Colors.purple),
        ],
      ),
    );
  }
}

class _NetworkTool extends StatelessWidget {
  final String name;
  final String description;
  final IconData icon;
  final Color color;
  const _NetworkTool({
    required this.name,
    required this.description,
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
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(description, style: GoogleFonts.inter(fontSize: 12)),
        trailing: FilledButton.tonal(
          onPressed: () {},
          child: const Text('Run', style: TextStyle(fontSize: 12)),
        ),
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
            title: 'Process Management',
            body: 'List, monitor, and manage running processes.',
          ),
          const SizedBox(height: 16),
          _ProcessEntry(pid: 1, name: 'init', status: 'running', cpu: '0.1%', mem: '4.2 MB'),
          _ProcessEntry(pid: 100, name: 'python3', status: 'running', cpu: '2.5%', mem: '128 MB'),
          _ProcessEntry(pid: 200, name: 'flutter', status: 'running', cpu: '5.0%', mem: '256 MB'),
          _ProcessEntry(pid: 300, name: 'bash', status: 'sleeping', cpu: '0.0%', mem: '8.0 MB'),
        ],
      ),
    );
  }
}

class _ProcessEntry extends StatelessWidget {
  final int pid;
  final String name;
  final String status;
  final String cpu;
  final String mem;
  const _ProcessEntry({
    required this.pid,
    required this.name,
    required this.status,
    required this.cpu,
    required this.mem,
  });

  @override
  Widget build(BuildContext context) {
    final color = status == 'running' ? Colors.green : Colors.grey;
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Text('$pid', style: GoogleFonts.firaCode(fontSize: 10, color: color, fontWeight: FontWeight.bold)),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('CPU: $cpu · MEM: $mem'),
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

// ── Tab: Installer ───────────────────────────────────────
class _InstallerTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'UmerOS Installer',
            body: 'Install, verify, and manage UmerOS on target directories.',
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.install_desktop, size: 16),
                label: const Text('Install'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.verified, size: 16),
                label: const Text('Verify'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.delete_forever, size: 16),
                label: const Text('Uninstall'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _InfoCard(
            title: 'Installation Status',
            body: 'No installation detected. Use "Install" to begin.',
          ),
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