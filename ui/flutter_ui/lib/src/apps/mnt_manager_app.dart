/// UmerOS /mnt Manager — Temporary Mount Management
///
/// Desktop control panel for the UmerOS /mnt subsystem.
/// Manages mount points, fstab, user mounts, audit trail, validation.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class MntManagerApp extends StatefulWidget {
  const MntManagerApp({super.key});

  @override
  State<MntManagerApp> createState() => _MntManagerAppState();
}

class _MntManagerAppState extends State<MntManagerApp> {
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
              _Tab('Mounts', 0, Icons.storage),
              _Tab('Fstab', 1, Icons.list_alt),
              _Tab('User Mounts', 2, Icons.person),
              _Tab('Audit', 3, Icons.history),
              _Tab('Validation', 4, Icons.verified),
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
        return _MountsTab();
      case 1:
        return _FstabTab();
      case 2:
        return _UserMountsTab();
      case 3:
        return _AuditTab();
      case 4:
        return _ValidationTab();
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

// ── Tab: Mounts ──────────────────────────────────────────────────
class _MountsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Active Mounts',
            body: 'Currently mounted filesystems under /mnt.',
          ),
          const SizedBox(height: 16),
          _MountEntry(device: '/dev/sdb1', mount: '/mnt/usb', fs: 'vfat', status: 'Mounted', color: Colors.green),
          _MountEntry(device: '/dev/sdc1', mount: '/mnt/backup', fs: 'ext4', status: 'Mounted', color: Colors.green),
          _MountEntry(device: '//server/share', mount: '/mnt/nfs', fs: 'nfs', status: 'Mounted', color: Colors.blue),
        ],
      ),
    );
  }
}

class _MountEntry extends StatelessWidget {
  final String device;
  final String mount;
  final String fs;
  final String status;
  final Color color;
  const _MountEntry({
    required this.device,
    required this.mount,
    required this.fs,
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
        title: Text('$device → $mount', style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Filesystem: $fs', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Fstab ───────────────────────────────────────────────────
class _FstabTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'fstab Entries',
            body: 'Entries from /etc/fstab configuration.',
          ),
          const SizedBox(height: 16),
          _FstabEntry(device: '/dev/sda1', mount: '/', fs: 'ext4', options: 'defaults', dump: 0, pass: 1),
          _FstabEntry(device: '/dev/sdb1', mount: '/mnt/usb', fs: 'vfat', options: 'rw,user,noauto', dump: 0, pass: 0),
          _FstabEntry(device: '//server/share', mount: '/mnt/nfs', fs: 'nfs', options: 'defaults', dump: 0, pass: 0),
          _FstabEntry(device: 'tmpfs', mount: '/tmp', fs: 'tmpfs', options: 'defaults', dump: 0, pass: 0),
        ],
      ),
    );
  }
}

class _FstabEntry extends StatelessWidget {
  final String device;
  final String mount;
  final String fs;
  final String options;
  final int dump;
  final int pass;
  const _FstabEntry({
    required this.device,
    required this.mount,
    required this.fs,
    required this.options,
    required this.dump,
    required this.pass,
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
                Icon(Icons.storage, color: Colors.blue, size: 18),
                const SizedBox(width: 8),
                Text(device, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade200,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(fs, style: GoogleFonts.firaCode(fontSize: 10, color: Colors.grey.shade700)),
                ),
                const Spacer(),
                Text(mount, style: GoogleFonts.inter(fontSize: 11, color: Colors.grey.shade600)),
              ],
            ),
            const SizedBox(height: 4),
            Text('Options: $options · Dump: $dump · Pass: $pass', style: GoogleFonts.inter(fontSize: 10, color: Colors.grey.shade500)),
          ],
        ),
      ),
    );
  }
}

// ── Tab: User Mounts ─────────────────────────────────────────────
class _UserMountsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'User Mounts',
            body: 'Filesystems mounted by non-root users (user option in fstab).',
          ),
          const SizedBox(height: 16),
          _UserMountEntry(user: 'umer', device: '/dev/sdb1', mount: '/mnt/usb', fs: 'vfat'),
          _UserMountEntry(user: 'umer', device: '/dev/sdc1', mount: '/mnt/backup', fs: 'ext4'),
        ],
      ),
    );
  }
}

class _UserMountEntry extends StatelessWidget {
  final String user;
  final String device;
  final String mount;
  final String fs;
  const _UserMountEntry({
    required this.user,
    required this.device,
    required this.mount,
    required this.fs,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Colors.blue.withValues(alpha: 0.15),
          child: Text(user[0].toUpperCase(), style: GoogleFonts.inter(fontSize: 12, color: Colors.blue, fontWeight: FontWeight.bold)),
        ),
        title: Text('$device → $mount', style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Filesystem: $fs · User: $user', style: GoogleFonts.inter(fontSize: 11)),
      ),
    );
  }
}

// ── Tab: Audit ───────────────────────────────────────────────────
class _AuditTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Mount Audit Trail',
            body: 'History of mount/unmount operations (JSONL append-only).',
          ),
          const SizedBox(height: 16),
          _AuditEntry(time: '2026-10-30 14:22:05', action: 'mount', device: '/dev/sdb1', mount: '/mnt/usb', user: 'root'),
          _AuditEntry(time: '2026-10-30 14:20:00', action: 'unmount', device: '/dev/sdc1', mount: '/mnt/backup', user: 'umer'),
          _AuditEntry(time: '2026-10-30 13:55:30', action: 'mount', device: '//server/share', mount: '/mnt/nfs', user: 'root'),
        ],
      ),
    );
  }
}

class _AuditEntry extends StatelessWidget {
  final String time;
  final String action;
  final String device;
  final String mount;
  final String user;
  const _AuditEntry({
    required this.time,
    required this.action,
    required this.device,
    required this.mount,
    required this.user,
  });

  @override
  Widget build(BuildContext context) {
    final color = action == 'mount' ? Colors.green : Colors.orange;
    final icon = action == 'mount' ? Icons.add_circle : Icons.remove_circle;
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(icon, color: color, size: 20),
        title: Text('$action $device → $mount', style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$time · by $user', style: GoogleFonts.inter(fontSize: 11)),
      ),
    );
  }
}

// ── Tab: Validation ──────────────────────────────────────────────
class _ValidationTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'FHS Validation',
            body: 'Filesystem Hierarchy Standard compliance check for /mnt.',
          ),
          const SizedBox(height: 16),
          _ValidationEntry(path: '/mnt', status: 'OK', color: Colors.green),
          _ValidationEntry(path: '/mnt/usb', status: 'OK', color: Colors.green),
          _ValidationEntry(path: '/mnt/backup', status: 'OK', color: Colors.green),
          _ValidationEntry(path: '/mnt/nfs', status: 'OK', color: Colors.green),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.verified),
            label: const Text('Run Validation'),
          ),
        ],
      ),
    );
  }
}

class _ValidationEntry extends StatelessWidget {
  final String path;
  final String status;
  final Color color;
  const _ValidationEntry({required this.path, required this.status, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.folder, color: color, size: 20),
        title: Text(path, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
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