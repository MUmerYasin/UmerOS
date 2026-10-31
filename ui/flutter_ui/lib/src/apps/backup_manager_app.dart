/// UmerOS Backup Manager — Backup & Restore
///
/// Desktop control panel for the UmerOS backup subsystem.
/// Covers all backup modules.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class BackupManagerApp extends StatefulWidget {
  const BackupManagerApp({super.key});

  @override
  State<BackupManagerApp> createState() => _BackupManagerAppState();
}

class _BackupManagerAppState extends State<BackupManagerApp> {
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
          child: Row(
            children: [
              _Tab('Snapshots', 0, Icons.camera),
              _Tab('Restore', 1, Icons.restore),
              _Tab('Factory Reset', 2, Icons.restart_alt),
              _Tab('Filters', 3, Icons.filter_list),
              _Tab('CLI', 4, Icons.terminal),
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
        return _SnapshotsTab();
      case 1:
        return _RestoreTab();
      case 2:
        return _FactoryResetTab();
      case 3:
        return _FiltersTab();
      case 4:
        return _CliTab();
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

// ── Tab: Snapshots ───────────────────────────────────────────────
class _SnapshotsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Snapshots',
            body: 'Filesystem snapshots using hardlinks.',
          ),
          const SizedBox(height: 16),
          _SnapshotEntry(name: 'snapshot-2026-10-30', level: 'Full', date: '2026-10-30 14:22:05', size: '2.4 GB', status: 'OK', color: Colors.green),
          _SnapshotEntry(name: 'snapshot-2026-10-29', level: 'Incremental', date: '2026-10-29 02:00:00', size: '128 MB', status: 'OK', color: Colors.green),
          _SnapshotEntry(name: 'snapshot-2026-10-28', level: 'Incremental', date: '2026-10-28 02:00:00', size: '64 MB', status: 'OK', color: Colors.green),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.camera),
            label: const Text('Create Snapshot'),
          ),
        ],
      ),
    );
  }
}

class _SnapshotEntry extends StatelessWidget {
  final String name;
  final String level;
  final String date;
  final String size;
  final String status;
  final Color color;
  const _SnapshotEntry({
    required this.name,
    required this.level,
    required this.date,
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
        leading: Icon(Icons.camera, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$level · $date · $size', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Restore ─────────────────────────────────────────────────
class _RestoreTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Restore',
            body: 'Restore from a previous snapshot.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Available Snapshots', value: '3'),
          _InfoRow(label: 'Last Restore', value: '2026-10-25 10:30:00'),
          _InfoRow(label: 'Restore Status', value: 'Ready'),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.restore),
            label: const Text('Restore from Snapshot'),
          ),
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

// ── Tab: Factory Reset ────────────────────────────────────────────
class _FactoryResetTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Factory Reset',
            body: 'Reset system to factory defaults.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Reset Mode', value: 'Full'),
          _InfoRow(label: 'Preserve User Data', value: 'No'),
          _InfoRow(label: 'Preserve Config', value: 'No'),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.restart_alt),
            label: const Text('Factory Reset'),
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
          ),
        ],
      ),
    );
  }
}

// ── Tab: Filters ─────────────────────────────────────────────────
class _FiltersTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Path Filters',
            body: 'Filters for backup path selection.',
          ),
          const SizedBox(height: 16),
          _FilterEntry(pattern: '/home/*', type: 'Include', status: 'Active', color: Colors.green),
          _FilterEntry(pattern: '/tmp/*', type: 'Exclude', status: 'Active', color: Colors.red),
          _FilterEntry(pattern: '/var/log/*', type: 'Exclude', status: 'Active', color: Colors.red),
          _FilterEntry(pattern: '/etc/*', type: 'Include', status: 'Active', color: Colors.green),
        ],
      ),
    );
  }
}

class _FilterEntry extends StatelessWidget {
  final String pattern;
  final String type;
  final String status;
  final Color color;
  const _FilterEntry({
    required this.pattern,
    required this.type,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.filter_list, color: color, size: 20),
        title: Text(pattern, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Type: $type', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: CLI ─────────────────────────────────────────────────────
class _CliTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Backup CLI',
            body: 'Command-line interface for backup operations.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Commands', value: 'backup, restore, snapshot, reset'),
          _InfoRow(label: 'GRUB CLI', value: 'Available'),
          _InfoRow(label: 'Status', value: 'Ready'),
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