/// UmerOS /tmp Manager — Temporary Filesystem & Runtime State
///
/// Desktop control panel for the UmerOS /tmp subsystem.
/// Manages temp files, socket dirs, locks, reaper, tmpfs, permissions.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class TmpManagerApp extends StatefulWidget {
  const TmpManagerApp({super.key});

  @override
  State<TmpManagerApp> createState() => _TmpManagerAppState();
}

class _TmpManagerAppState extends State<TmpManagerApp> {
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
              _Tab('Overview', 0, Icons.folder_open),
              _Tab('Temp Files', 1, Icons.insert_drive_file),
              _Tab('Socket Dirs', 2, Icons.link),
              _Tab('Locks', 3, Icons.lock),
              _Tab('Reaper', 4, Icons.cleaning_services),
              _Tab('TmpFS', 5, Icons.memory),
              _Tab('Permissions', 6, Icons.security),
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
        return _TempFilesTab();
      case 2:
        return _SocketDirsTab();
      case 3:
        return _LocksTab();
      case 4:
        return _ReaperTab();
      case 5:
        return _TmpFsTab();
      case 6:
        return _PermissionsTab();
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

// ── Tab: Overview ────────────────────────────────────────
class _OverviewTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Temporary Filesystem (/tmp)',
            body: 'Manages transient files, UNIX socket directories, process locks, '
                'tmpwatch/systemd-tmpfiles reaper policies, and high-performance TmpFS.',
          ),
          const SizedBox(height: 16),
          _StatRow(label: 'Temp Files', value: '24', color: Colors.blue),
          _StatRow(label: 'Socket Dirs', value: '7', color: Colors.green),
          _StatRow(label: 'Active Locks', value: '3', color: Colors.orange),
          _StatRow(label: 'TmpFS Usage', value: '12.4 MB / 256 MB', color: Colors.purple),
          _StatRow(label: 'Reaped (24h)', value: '142', color: Colors.teal),
        ],
      ),
    );
  }
}

class _StatRow extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _StatRow({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        title: Text(label, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Text(value, style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 13, color: color)),
      ),
    );
  }
}

// ── Tab: Temp Files ──────────────────────────────────────
class _TempFilesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Secure Temporary Files',
            body: 'Race-free mktemp with SecureIO. Files are created with '
                'O_EXCL and proper permissions (0600).',
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.add, size: 16),
                label: const Text('Create Temp File'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.folder, size: 16),
                label: const Text('Create Temp Dir'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.cleaning_services, size: 16),
                label: const Text('Clean All'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _TempFileEntry(name: 'tmp_abc123.txt', size: '1.2 KB', age: '2 min', color: Colors.blue),
          _TempFileEntry(name: 'tmp_def456.log', size: '4.5 KB', age: '15 min', color: Colors.orange),
          _TempFileEntry(name: 'tmp_ghi789.json', size: '0.8 KB', age: '1 hour', color: Colors.green),
        ],
      ),
    );
  }
}

class _TempFileEntry extends StatelessWidget {
  final String name;
  final String size;
  final String age;
  final Color color;
  const _TempFileEntry({
    required this.name,
    required this.size,
    required this.age,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.insert_drive_file, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Age: $age'),
        trailing: Text(size, style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 12)),
      ),
    );
  }
}

// ── Tab: Socket Dirs ─────────────────────────────────────
class _SocketDirsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'UNIX Socket Directories',
            body: 'FHS-compliant socket directories: .X11-unix, .ICE-unix, '
                '.font-unix, .Test-unix, and per-user runtime directories.',
          ),
          const SizedBox(height: 16),
          _SocketDirEntry(name: '.X11-unix', sockets: 2, status: 'Active', color: Colors.blue),
          _SocketDirEntry(name: '.ICE-unix', sockets: 1, status: 'Active', color: Colors.green),
          _SocketDirEntry(name: '.font-unix', sockets: 0, status: 'Empty', color: Colors.grey),
          _SocketDirEntry(name: '.Test-unix', sockets: 0, status: 'Empty', color: Colors.grey),
          _SocketDirEntry(name: 'user/', sockets: 3, status: 'Active', color: Colors.orange),
        ],
      ),
    );
  }
}

class _SocketDirEntry extends StatelessWidget {
  final String name;
  final int sockets;
  final String status;
  final Color color;
  const _SocketDirEntry({
    required this.name,
    required this.sockets,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.link, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$sockets socket(s)'),
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

// ── Tab: Locks ───────────────────────────────────────────
class _LocksTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Process Locks',
            body: 'PID-based file locks with stale lock detection. '
                'Locks are stored as JSON metadata files.',
          ),
          const SizedBox(height: 16),
          _LockEntry(name: 'app.lock', pid: 1234, status: 'Active', color: Colors.green),
          _LockEntry(name: 'db.lock', pid: 5678, status: 'Active', color: Colors.green),
          _LockEntry(name: 'cache.lock', pid: 9999, status: 'Stale', color: Colors.red),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.cleaning_services, size: 16),
            label: const Text('Clean Stale Locks'),
          ),
        ],
      ),
    );
  }
}

class _LockEntry extends StatelessWidget {
  final String name;
  final int pid;
  final String status;
  final Color color;
  const _LockEntry({
    required this.name,
    required this.pid,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.lock, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('PID: $pid'),
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

// ── Tab: Reaper ──────────────────────────────────────────
class _ReaperTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Tmp Reaper (tmpwatch/systemd-tmpfiles)',
            body: 'Age-based and quota-based pruning of temporary files. '
                'Configurable max age and size quotas.',
          ),
          const SizedBox(height: 16),
          _ReaperStat(label: 'Max Age', value: '10 days', color: Colors.blue),
          _ReaperStat(label: 'Max Size', value: '2 GB', color: Colors.green),
          _ReaperStat(label: 'Files Reaped (24h)', value: '142', color: Colors.orange),
          _ReaperStat(label: 'Space Freed', value: '84 MB', color: Colors.purple),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.play_arrow, size: 16),
                label: const Text('Run Reaper Now'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.settings, size: 16),
                label: const Text('Configure'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ReaperStat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _ReaperStat({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        title: Text(label, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        trailing: Text(value, style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 13, color: color)),
      ),
    );
  }
}

// ── Tab: TmpFS ───────────────────────────────────────────
class _TmpFsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'TmpFS — In-Memory RAM Filesystem',
            body: 'High-performance in-memory virtual filesystem. '
                'Supports quotas, size limits, and node-based storage.',
          ),
          const SizedBox(height: 16),
          _StatRow(label: 'Capacity', value: '256 MB', color: Colors.blue),
          _StatRow(label: 'Used', value: '12.4 MB', color: Colors.orange),
          _StatRow(label: 'Free', value: '243.6 MB', color: Colors.green),
          _StatRow(label: 'Files', value: '47', color: Colors.purple),
          _StatRow(label: 'Directories', value: '8', color: Colors.teal),
          const SizedBox(height: 16),
          LinearProgressIndicator(
            value: 12.4 / 256,
            minHeight: 8,
            borderRadius: BorderRadius.circular(4),
          ),
        ],
      ),
    );
  }
}

// ── Tab: Permissions ─────────────────────────────────────
class _PermissionsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Tmp Permissions & Security Audit',
            body: 'Sticky-bit validation, permission auditing, and '
                'security checks for /tmp directories.',
          ),
          const SizedBox(height: 16),
          _PermEntry(path: '/tmp', mode: '1777', sticky: true, status: 'Secure', color: Colors.green),
          _PermEntry(path: '/tmp/.X11-unix', mode: '1777', sticky: true, status: 'Secure', color: Colors.green),
          _PermEntry(path: '/var/tmp', mode: '1777', sticky: true, status: 'Secure', color: Colors.green),
          _PermEntry(path: '/tmp/insecure_dir', mode: '0777', sticky: false, status: 'Warning', color: Colors.orange),
        ],
      ),
    );
  }
}

class _PermEntry extends StatelessWidget {
  final String path;
  final String mode;
  final bool sticky;
  final String status;
  final Color color;
  const _PermEntry({
    required this.path,
    required this.mode,
    required this.sticky,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(sticky ? Icons.lock : Icons.lock_open, color: color, size: 20),
        title: Text(path, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Mode: $mode · Sticky: ${sticky ? "yes" : "no"}'),
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