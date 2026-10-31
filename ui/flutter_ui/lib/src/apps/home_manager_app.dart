/// UmerOS /home Manager — User Home Directory Management
///
/// Desktop control panel for the UmerOS /home subsystem.
/// Manages user profiles, dotfiles, SSH keys, mail, quota, backup.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class HomeManagerApp extends StatefulWidget {
  const HomeManagerApp({super.key});

  @override
  State<HomeManagerApp> createState() => _HomeManagerAppState();
}

class _HomeManagerAppState extends State<HomeManagerApp> {
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
              _Tab('Profile', 0, Icons.person),
              _Tab('Dotfiles', 1, Icons.settings),
              _Tab('SSH Keys', 2, Icons.key),
              _Tab('Mail', 3, Icons.mail),
              _Tab('Quota', 4, Icons.pie_chart),
              _Tab('Backup', 5, Icons.backup),
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
        return _ProfileTab();
      case 1:
        return _DotfilesTab();
      case 2:
        return _SshKeysTab();
      case 3:
        return _MailTab();
      case 4:
        return _QuotaTab();
      case 5:
        return _BackupTab();
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

// ── Tab: Profile ─────────────────────────────────────────────────
class _ProfileTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'User Profile',
            body: 'User account and home directory information.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Username', value: 'umer'),
          _InfoRow(label: 'Home Directory', value: '/home/umer'),
          _InfoRow(label: 'Shell', value: '/bin/bash'),
          _InfoRow(label: 'UID', value: '1000'),
          _InfoRow(label: 'GID', value: '1000'),
          _InfoRow(label: 'Groups', value: 'umer, sudo, docker'),
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

// ── Tab: Dotfiles ────────────────────────────────────────────────
class _DotfilesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Dotfiles',
            body: 'Hidden configuration files in home directory.',
          ),
          const SizedBox(height: 16),
          _DotfileEntry(name: '.bashrc', status: 'Present', size: '4.2 KB', color: Colors.green),
          _DotfileEntry(name: '.bash_profile', status: 'Present', size: '1.1 KB', color: Colors.green),
          _DotfileEntry(name: '.vimrc', status: 'Present', size: '2.3 KB', color: Colors.green),
          _DotfileEntry(name: '.gitconfig', status: 'Present', size: '0.8 KB', color: Colors.green),
          _DotfileEntry(name: '.ssh/config', status: 'Present', size: '0.5 KB', color: Colors.blue),
          _DotfileEntry(name: '.local/bin', status: 'Present', size: '12.4 MB', color: Colors.blue),
        ],
      ),
    );
  }
}

class _DotfileEntry extends StatelessWidget {
  final String name;
  final String status;
  final String size;
  final Color color;
  const _DotfileEntry({
    required this.name,
    required this.status,
    required this.size,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.description, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Size: $size', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: SSH Keys ────────────────────────────────────────────────
class _SshKeysTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'SSH Keys',
            body: 'SSH keys in ~/.ssh directory.',
          ),
          const SizedBox(height: 16),
          _SshKeyEntry(name: 'id_ed25519', type: 'Ed25519', status: 'Valid', color: Colors.green),
          _SshKeyEntry(name: 'id_rsa', type: 'RSA 4096', status: 'Valid', color: Colors.green),
          _SshKeyEntry(name: 'id_ecdsa', type: 'ECDSA', status: 'Valid', color: Colors.blue),
          _SshKeyEntry(name: 'authorized_keys', type: 'Authorized', status: '3 keys', color: Colors.blue),
          _SshKeyEntry(name: 'known_hosts', type: 'Known Hosts', status: '12 entries', color: Colors.grey),
        ],
      ),
    );
  }
}

class _SshKeyEntry extends StatelessWidget {
  final String name;
  final String type;
  final String status;
  final Color color;
  const _SshKeyEntry({
    required this.name,
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
        leading: Icon(Icons.key, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
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

// ── Tab: Mail ────────────────────────────────────────────────────
class _MailTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Mail',
            body: 'User mail in ~/Mail or ~/.mail.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Inbox', value: '12 messages'),
          _InfoRow(label: 'Sent', value: '45 messages'),
          _InfoRow(label: 'Drafts', value: '3 messages'),
          _InfoRow(label: 'Trash', value: '8 messages'),
          _InfoRow(label: 'Total Size', value: '24.5 MB'),
        ],
      ),
    );
  }
}

// ── Tab: Quota ───────────────────────────────────────────────────
class _QuotaTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Disk Quota',
            body: 'User disk quota and usage.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Quota', value: '50 GB'),
          _InfoRow(label: 'Used', value: '12.4 GB'),
          _InfoRow(label: 'Available', value: '37.6 GB'),
          const SizedBox(height: 16),
          LinearProgressIndicator(
            value: 12.4 / 50,
            minHeight: 8,
            borderRadius: BorderRadius.circular(4),
          ),
        ],
      ),
    );
  }
}

// ── Tab: Backup ──────────────────────────────────────────────────
class _BackupTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Home Backup',
            body: 'Backup and restore home directory.',
          ),
          const SizedBox(height: 16),
          _BackupEntry(name: 'backup-2026-10-30.tar.gz', date: '2026-10-30 14:22:05', size: '2.4 GB', status: 'OK', color: Colors.green),
          _BackupEntry(name: 'backup-2026-10-29.tar.gz', date: '2026-10-29 02:00:00', size: '2.3 GB', status: 'OK', color: Colors.green),
          _BackupEntry(name: 'backup-2026-10-28.tar.gz', date: '2026-10-28 02:00:00', size: '2.2 GB', status: 'OK', color: Colors.green),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.backup),
            label: const Text('Create Backup'),
          ),
        ],
      ),
    );
  }
}

class _BackupEntry extends StatelessWidget {
  final String name;
  final String date;
  final String size;
  final String status;
  final Color color;
  const _BackupEntry({
    required this.name,
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
        leading: Icon(Icons.backup, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$date · $size', style: GoogleFonts.inter(fontSize: 11)),
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