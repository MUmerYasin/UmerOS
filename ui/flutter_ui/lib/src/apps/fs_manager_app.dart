/// UmerOS /fs Manager — Virtual Filesystem
///
/// Desktop control panel for the UmerOS /fs subsystem.
/// Manages QFS, VFS, DFS, CRDT objects, snapshots.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class FsManagerApp extends StatefulWidget {
  const FsManagerApp({super.key});

  @override
  State<FsManagerApp> createState() => _FsManagerAppState();
}

class _FsManagerAppState extends State<FsManagerApp> {
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
              _Tab('Files', 0, Icons.folder),
              _Tab('Snapshots', 1, Icons.camera),
              _Tab('Distributed', 2, Icons.cloud),
              _Tab('CRDT', 3, Icons.sync),
              _Tab('CAS', 4, Icons.fingerprint),
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
        return _FilesTab();
      case 1:
        return _SnapshotsTab();
      case 2:
        return _DistributedTab();
      case 3:
        return _CrdtTab();
      case 4:
        return _CasTab();
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

// ── Tab: Files ───────────────────────────────────────────────────
class _FilesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Virtual Filesystem',
            body: 'Files stored in quantum content-addressable store.',
          ),
          const SizedBox(height: 16),
          _FileEntry(name: '/home/umer/documents/report.pdf', size: '2.4 MB', hash: 'sha3-256:abc123...', color: Colors.green),
          _FileEntry(name: '/home/umer/code/main.py', size: '12.8 KB', hash: 'sha3-256:def456...', color: Colors.green),
          _FileEntry(name: '/etc/config.json', size: '1.2 KB', hash: 'sha3-256:ghi789...', color: Colors.blue),
          _FileEntry(name: '/tmp/scratchpad.txt', size: '256 B', hash: 'sha3-256:jkl012...', color: Colors.grey),
        ],
      ),
    );
  }
}

class _FileEntry extends StatelessWidget {
  final String name;
  final String size;
  final String hash;
  final Color color;
  const _FileEntry({
    required this.name,
    required this.size,
    required this.hash,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.insert_drive_file, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 11)),
        subtitle: Text('Size: $size · Hash: $hash', style: GoogleFonts.inter(fontSize: 10)),
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
            title: 'Filesystem Snapshots',
            body: 'Point-in-time snapshots of the filesystem.',
          ),
          const SizedBox(height: 16),
          _SnapshotEntry(name: 'snapshot-2026-10-30', date: '2026-10-30 14:22:05', files: '1,247', status: 'OK', color: Colors.green),
          _SnapshotEntry(name: 'snapshot-2026-10-29', date: '2026-10-29 02:00:00', files: '1,230', status: 'OK', color: Colors.green),
          _SnapshotEntry(name: 'snapshot-2026-10-28', date: '2026-10-28 02:00:00', files: '1,215', status: 'OK', color: Colors.green),
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
  final String date;
  final String files;
  final String status;
  final Color color;
  const _SnapshotEntry({
    required this.name,
    required this.date,
    required this.files,
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
        subtitle: Text('$date · $files files', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Distributed ─────────────────────────────────────────────
class _DistributedTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Distributed Filesystem',
            body: 'UmerDFS distributed VFS and CRDT objects.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Nodes', value: '3'),
          _InfoRow(label: 'Sync Status', value: 'In sync'),
          _InfoRow(label: 'Conflict Resolution', value: 'LWW'),
          _InfoRow(label: 'Objects', value: '1,247'),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.sync),
            label: const Text('Sync Now'),
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

// ── Tab: CRDT ────────────────────────────────────────────────────
class _CrdtTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'CRDT Objects',
            body: 'Conflict-free replicated data types.',
          ),
          const SizedBox(height: 16),
          _CrdtEntry(name: 'config.json', type: 'LWWRegister', replicas: '3', status: 'Synced', color: Colors.green),
          _CrdtEntry(name: 'user_prefs', type: 'LWWRegister', replicas: '3', status: 'Synced', color: Colors.green),
          _CrdtEntry(name: 'shared_doc', type: 'LWWRegister', replicas: '2', status: 'Syncing', color: Colors.orange),
        ],
      ),
    );
  }
}

class _CrdtEntry extends StatelessWidget {
  final String name;
  final String type;
  final String replicas;
  final String status;
  final Color color;
  const _CrdtEntry({
    required this.name,
    required this.type,
    required this.replicas,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.sync, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$type · $replicas replicas', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: CAS ─────────────────────────────────────────────────────
class _CasTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Content-Addressable Store',
            body: 'SHA-3 content-addressable storage.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Hash Algorithm', value: 'SHA-3 (Keccak)'),
          _InfoRow(label: 'Total Objects', value: '1,247'),
          _InfoRow(label: 'Total Size', value: '4.2 GB'),
          _InfoRow(label: 'Deduplication', value: 'Enabled'),
          _InfoRow(label: 'Compression', value: 'Quantum'),
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