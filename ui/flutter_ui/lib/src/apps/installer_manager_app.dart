/// UmerOS Installer Manager — Deployment & Installation
///
/// Desktop control panel for the UmerOS installer.
/// Manages installation, EULA, partitioning, and rollback.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class InstallerManagerApp extends StatefulWidget {
  const InstallerManagerApp({super.key});

  @override
  State<InstallerManagerApp> createState() => _InstallerManagerAppState();
}

class _InstallerManagerAppState extends State<InstallerManagerApp> {
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
              _Tab('Overview', 0, Icons.install_desktop),
              _Tab('EULA', 1, Icons.description),
              _Tab('Partitions', 2, Icons.storage),
              _Tab('Progress', 3, Icons.downloading),
              _Tab('Rollback', 4, Icons.restore),
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
        return _OverviewTab();
      case 1:
        return _EulaTab();
      case 2:
        return _PartitionsTab();
      case 3:
        return _ProgressTab();
      case 4:
        return _RollbackTab();
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

// ── Tab: Overview ────────────────────────────────────────────────
class _OverviewTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'UmerOS Installer',
            body: 'System installation and deployment manager.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Version', value: '2.1.0-quantum'),
          _InfoRow(label: 'Architecture', value: 'x86_64'),
          _InfoRow(label: 'Install Mode', value: 'Full'),
          _InfoRow(label: 'Target Disk', value: '/dev/sda'),
          _InfoRow(label: 'Bootloader', value: 'GRUB2'),
          _InfoRow(label: 'Filesystem', value: 'ext4'),
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

// ── Tab: EULA ────────────────────────────────────────────────────
class _EulaTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'End User License Agreement',
            body: 'You must accept the EULA to proceed with installation.',
          ),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            height: 200,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: SingleChildScrollView(
              child: Text(
                'UmerOS End User License Agreement\n\n'
                'This software is licensed under the GNU General Public License v3.\n'
                'By installing UmerOS, you agree to the terms and conditions.\n\n'
                '1. You may use, modify, and distribute this software.\n'
                '2. You must preserve copyright notices.\n'
                '3. You must provide source code when distributing.\n'
                '4. No warranty is provided.\n\n'
                'Type "I AGREE" to accept.',
                style: GoogleFonts.inter(fontSize: 12, height: 1.5),
              ),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: () {},
            icon: const Icon(Icons.check),
            label: const Text('I AGREE'),
          ),
        ],
      ),
    );
  }
}

// ── Tab: Partitions ──────────────────────────────────────────────
class _PartitionsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Disk Partitions',
            body: 'Partition layout for installation.',
          ),
          const SizedBox(height: 16),
          _PartitionEntry(device: '/dev/sda1', mount: '/', fs: 'ext4', size: '50 GB', status: 'OK', color: Colors.green),
          _PartitionEntry(device: '/dev/sda2', mount: '/boot', fs: 'ext4', size: '1 GB', status: 'OK', color: Colors.green),
          _PartitionEntry(device: '/dev/sda3', mount: 'swap', fs: 'swap', size: '8 GB', status: 'OK', color: Colors.blue),
          _PartitionEntry(device: '/dev/sda4', mount: '/home', fs: 'ext4', size: '100 GB', status: 'OK', color: Colors.green),
        ],
      ),
    );
  }
}

class _PartitionEntry extends StatelessWidget {
  final String device;
  final String mount;
  final String fs;
  final String size;
  final String status;
  final Color color;
  const _PartitionEntry({
    required this.device,
    required this.mount,
    required this.fs,
    required this.size,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.storage, color: color, size: 20),
        title: Text(device, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$mount · $fs · $size', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Progress ────────────────────────────────────────────────
class _ProgressTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Installation Progress',
            body: 'Current installation status.',
          ),
          const SizedBox(height: 16),
          _ProgressEntry(step: 'Partitioning', status: 'Done', progress: 1.0, color: Colors.green),
          _ProgressEntry(step: 'Formatting', status: 'Done', progress: 1.0, color: Colors.green),
          _ProgressEntry(step: 'Copying files', status: 'In progress', progress: 0.65, color: Colors.blue),
          _ProgressEntry(step: 'Installing bootloader', status: 'Pending', progress: 0.0, color: Colors.grey),
          _ProgressEntry(step: 'Configuring system', status: 'Pending', progress: 0.0, color: Colors.grey),
        ],
      ),
    );
  }
}

class _ProgressEntry extends StatelessWidget {
  final String step;
  final String status;
  final double progress;
  final Color color;
  const _ProgressEntry({
    required this.step,
    required this.status,
    required this.progress,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(step, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
                const Spacer(),
                Text(status, style: GoogleFonts.inter(fontSize: 11, color: color)),
              ],
            ),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: progress,
              minHeight: 6,
              borderRadius: BorderRadius.circular(3),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Tab: Rollback ────────────────────────────────────────────────
class _RollbackTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Rollback',
            body: 'Rollback to previous installation state on failure.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Snapshot Available', value: 'Yes'),
          _InfoRow(label: 'Snapshot Date', value: '2026-10-30 14:22:05'),
          _InfoRow(label: 'Rollback Status', value: 'Ready'),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.restore),
            label: const Text('Rollback Installation'),
          ),
        ],
      ),
    );
  }
}

// ── Shared widgets ───────────────────────────────────────────────
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