/// UmerOS /srv Manager — Site-Specific Service Data
///
/// Desktop control panel for the UmerOS /srv subsystem.
/// Manages WWW, FTP, Git, Rsync, TFTP, Samba/NFS services.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class SrvManagerApp extends StatefulWidget {
  const SrvManagerApp({super.key});

  @override
  State<SrvManagerApp> createState() => _SrvManagerAppState();
}

class _SrvManagerAppState extends State<SrvManagerApp> {
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
              _Tab('Services', 0, Icons.dns),
              _Tab('Protocols', 1, Icons.settings_ethernet),
              _Tab('Permissions', 2, Icons.security),
              _Tab('Backup', 3, Icons.backup),
              _Tab('FHS', 4, Icons.folder),
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
        return _ServicesTab();
      case 1:
        return _ProtocolsTab();
      case 2:
        return _PermissionsTab();
      case 3:
        return _BackupTab();
      case 4:
        return _FhsTab();
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

// ── Tab: Services ────────────────────────────────────────
class _ServicesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Site-Specific Services (/srv)',
            body: 'Manages data served by the system: WWW, FTP, Git, '
                'Rsync, TFTP, Samba, and NFS.',
          ),
          const SizedBox(height: 16),
          _ServiceEntry(name: 'www', protocol: 'HTTP/HTTPS', status: 'Active', port: '80/443', color: Colors.blue),
          _ServiceEntry(name: 'ftp', protocol: 'FTP', status: 'Active', port: '21', color: Colors.green),
          _ServiceEntry(name: 'git', protocol: 'Git (SSH)', status: 'Active', port: '22', color: Colors.orange),
          _ServiceEntry(name: 'rsync', protocol: 'Rsync', status: 'Inactive', port: '873', color: Colors.grey),
          _ServiceEntry(name: 'tftp', protocol: 'TFTP', status: 'Inactive', port: '69', color: Colors.grey),
          _ServiceEntry(name: 'samba', protocol: 'SMB/CIFS', status: 'Active', port: '445', color: Colors.purple),
          _ServiceEntry(name: 'nfs', protocol: 'NFS', status: 'Active', port: '2049', color: Colors.teal),
        ],
      ),
    );
  }
}

class _ServiceEntry extends StatelessWidget {
  final String name;
  final String protocol;
  final String status;
  final String port;
  final Color color;
  const _ServiceEntry({
    required this.name,
    required this.protocol,
    required this.status,
    required this.port,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final isActive = status == 'Active';
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Icon(Icons.dns, color: color, size: 18),
        ),
        title: Text('/srv/$name', style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$protocol · Port $port'),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: (isActive ? Colors.green : Colors.grey).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(status, style: GoogleFonts.inter(fontSize: 10, color: isActive ? Colors.green : Colors.grey, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Protocols ───────────────────────────────────────
class _ProtocolsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Protocol Handlers',
            body: 'Service protocol handlers for WWW, FTP, Git, Rsync, TFTP, Samba/NFS.',
          ),
          const SizedBox(height: 16),
          _ProtocolEntry(name: 'WWWServiceHandler', protocol: 'HTTP/HTTPS', status: 'Running', color: Colors.blue),
          _ProtocolEntry(name: 'FTPServiceHandler', protocol: 'FTP', status: 'Running', color: Colors.green),
          _ProtocolEntry(name: 'GitServiceHandler', protocol: 'Git', status: 'Running', color: Colors.orange),
          _ProtocolEntry(name: 'RsyncServiceHandler', protocol: 'Rsync', status: 'Stopped', color: Colors.grey),
          _ProtocolEntry(name: 'TFTPServiceHandler', protocol: 'TFTP', status: 'Stopped', color: Colors.grey),
          _ProtocolEntry(name: 'SambaNfsServiceHandler', protocol: 'SMB/NFS', status: 'Running', color: Colors.purple),
        ],
      ),
    );
  }
}

class _ProtocolEntry extends StatelessWidget {
  final String name;
  final String protocol;
  final String status;
  final Color color;
  const _ProtocolEntry({
    required this.name,
    required this.protocol,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final isActive = status == 'Running';
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Icon(Icons.settings_ethernet, color: color, size: 18),
        ),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(protocol),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: (isActive ? Colors.green : Colors.grey).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(status, style: GoogleFonts.inter(fontSize: 10, color: isActive ? Colors.green : Colors.grey, fontWeight: FontWeight.w600)),
        ),
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
            title: 'Permission & Security Audit',
            body: 'POSIX permission audit and security profiles for /srv data.',
          ),
          const SizedBox(height: 16),
          _PermEntry(path: '/srv/www', mode: '0755', owner: 'www-data', status: 'Secure', color: Colors.green),
          _PermEntry(path: '/srv/ftp', mode: '0755', owner: 'ftp', status: 'Secure', color: Colors.green),
          _PermEntry(path: '/srv/git', mode: '0750', owner: 'git', status: 'Secure', color: Colors.green),
          _PermEntry(path: '/srv/samba', mode: '0770', owner: 'sambashare', status: 'Secure', color: Colors.green),
        ],
      ),
    );
  }
}

class _PermEntry extends StatelessWidget {
  final String path;
  final String mode;
  final String owner;
  final String status;
  final Color color;
  const _PermEntry({
    required this.path,
    required this.mode,
    required this.owner,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.security, color: color, size: 20),
        title: Text(path, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Mode: $mode · Owner: $owner'),
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

// ── Tab: Backup ──────────────────────────────────────────
class _BackupTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Service Data Backup',
            body: 'Snapshot and restore service data in /srv.',
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.backup, size: 16),
                label: const Text('Create Backup'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.restore, size: 16),
                label: const Text('Restore'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.history, size: 16),
                label: const Text('Snapshots'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _BackupEntry(name: 'backup_2026-10-29', size: '2.4 GB', date: '2026-10-29', color: Colors.blue),
          _BackupEntry(name: 'backup_2026-10-28', size: '2.3 GB', date: '2026-10-28', color: Colors.green),
        ],
      ),
    );
  }
}

class _BackupEntry extends StatelessWidget {
  final String name;
  final String size;
  final String date;
  final Color color;
  const _BackupEntry({
    required this.name,
    required this.size,
    required this.date,
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
          child: const Icon(Icons.backup, color: Colors.blue, size: 18),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('Size: $size · Date: $date'),
        trailing: IconButton(
          icon: const Icon(Icons.restore, size: 18),
          tooltip: 'Restore',
          onPressed: () {},
        ),
      ),
    );
  }
}

// ── Tab: FHS ─────────────────────────────────────────────
class _FhsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'FHS /srv Structure',
            body: '/srv contains site-specific data served by the system. '
                'Organized by protocol or by organization.',
          ),
          const SizedBox(height: 16),
          _FhsEntry(path: '/srv/www', description: 'Web server data', color: Colors.blue),
          _FhsEntry(path: '/srv/ftp', description: 'FTP server data', color: Colors.green),
          _FhsEntry(path: '/srv/git', description: 'Git repositories', color: Colors.orange),
          _FhsEntry(path: '/srv/rsync', description: 'Rsync data', color: Colors.purple),
          _FhsEntry(path: '/srv/tftp', description: 'TFTP boot files', color: Colors.teal),
          _FhsEntry(path: '/srv/samba', description: 'Samba shares', color: Colors.indigo),
          _FhsEntry(path: '/srv/nfs', description: 'NFS exports', color: Colors.amber),
        ],
      ),
    );
  }
}

class _FhsEntry extends StatelessWidget {
  final String path;
  final String description;
  final Color color;
  const _FhsEntry({
    required this.path,
    required this.description,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.folder, color: color, size: 20),
        title: Text(path, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(description, style: GoogleFonts.inter(fontSize: 11)),
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