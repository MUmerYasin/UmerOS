/// UmerOS /root Manager — Root Home & User Management
///
/// Desktop control panel for the UmerOS /root subsystem.
/// Manages root home, dotfiles, passwd, mail, safety, and shell.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class RootManagerApp extends StatefulWidget {
  const RootManagerApp({super.key});

  @override
  State<RootManagerApp> createState() => _RootManagerAppState();
}

class _RootManagerAppState extends State<RootManagerApp> {
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
              _Tab('Home', 0, Icons.home),
              _Tab('Dotfiles', 1, Icons.settings),
              _Tab('Passwd', 2, Icons.person),
              _Tab('Mail', 3, Icons.mail),
              _Tab('Safety', 4, Icons.security),
              _Tab('Shell', 5, Icons.terminal),
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
        return _HomeTab();
      case 1:
        return _DotfilesTab();
      case 2:
        return _PasswdTab();
      case 3:
        return _MailTab();
      case 4:
        return _SafetyTab();
      case 5:
        return _ShellTab();
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

// ── Tab: Home ────────────────────────────────────────────
class _HomeTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Root Home Directory',
            body: 'Manages root user home, dotfiles, mail, and safety settings.',
          ),
          const SizedBox(height: 16),
          _HomeEntry(name: '.bashrc', type: 'Config', size: '2.4 KB', color: Colors.blue),
          _HomeEntry(name: '.profile', type: 'Config', size: '1.1 KB', color: Colors.green),
          _HomeEntry(name: '.ssh/', type: 'Directory', size: '4.0 KB', color: Colors.orange),
          _HomeEntry(name: '.config/', type: 'Directory', size: '12.0 KB', color: Colors.purple),
          _HomeEntry(name: 'mail/', type: 'Directory', size: '8.5 MB', color: Colors.indigo),
        ],
      ),
    );
  }
}

class _HomeEntry extends StatelessWidget {
  final String name;
  final String type;
  final String size;
  final Color color;
  const _HomeEntry({
    required this.name,
    required this.type,
    required this.size,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(name.endsWith('/') ? Icons.folder : Icons.insert_drive_file, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(type),
        trailing: Text(size, style: GoogleFonts.inter(fontSize: 11, color: Colors.grey)),
      ),
    );
  }
}

// ── Tab: Dotfiles ────────────────────────────────────────
class _DotfilesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Dotfile Management',
            body: 'Manage hidden configuration files in /root.',
          ),
          const SizedBox(height: 16),
          _DotfileEntry(name: '.bashrc', status: 'Modified', color: Colors.orange),
          _DotfileEntry(name: '.profile', status: 'Unchanged', color: Colors.green),
          _DotfileEntry(name: '.vimrc', status: 'Unchanged', color: Colors.green),
          _DotfileEntry(name: '.gitconfig', status: 'Unchanged', color: Colors.green),
          _DotfileEntry(name: '.ssh/config', status: 'Modified', color: Colors.orange),
        ],
      ),
    );
  }
}

class _DotfileEntry extends StatelessWidget {
  final String name;
  final String status;
  final Color color;
  const _DotfileEntry({
    required this.name,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final isActive = status == 'Unchanged';
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.settings, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: (isActive ? Colors.green : Colors.orange).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(status, style: GoogleFonts.inter(fontSize: 10, color: isActive ? Colors.green : Colors.orange, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Passwd ──────────────────────────────────────────
class _PasswdTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'User Account Management',
            body: 'Manage /etc/passwd entries, passwords, and user shells.',
          ),
          const SizedBox(height: 16),
          _UserEntry(name: 'root', uid: 0, gid: 0, shell: '/bin/bash', color: Colors.red),
          _UserEntry(name: 'umer', uid: 1000, gid: 1000, shell: '/bin/bash', color: Colors.blue),
          _UserEntry(name: 'nobody', uid: 65534, gid: 65534, shell: '/usr/sbin/nologin', color: Colors.grey),
          _UserEntry(name: 'www-data', uid: 33, gid: 33, shell: '/usr/sbin/nologin', color: Colors.green),
        ],
      ),
    );
  }
}

class _UserEntry extends StatelessWidget {
  final String name;
  final int uid;
  final int gid;
  final String shell;
  final Color color;
  const _UserEntry({
    required this.name,
    required this.uid,
    required this.gid,
    required this.shell,
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
          child: Text(name[0].toUpperCase(), style: GoogleFonts.inter(fontSize: 12, color: color, fontWeight: FontWeight.bold)),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('UID: $uid · GID: $gid · Shell: $shell'),
      ),
    );
  }
}

// ── Tab: Mail ────────────────────────────────────────────
class _MailTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Root Mail',
            body: 'Manage root user mail in /var/mail/root.',
          ),
          const SizedBox(height: 16),
          _MailEntry(subject: 'System Alert: Disk Usage', from: 'system', date: '2026-10-29', unread: true),
          _MailEntry(subject: 'Cron Job Report', from: 'cron', date: '2026-10-28', unread: false),
          _MailEntry(subject: 'Security Update Available', from: 'apt', date: '2026-10-27', unread: true),
        ],
      ),
    );
  }
}

class _MailEntry extends StatelessWidget {
  final String subject;
  final String from;
  final String date;
  final bool unread;
  const _MailEntry({
    required this.subject,
    required this.from,
    required this.date,
    required this.unread,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(unread ? Icons.mail : Icons.mail_outline, color: unread ? Colors.blue : Colors.grey, size: 20),
        title: Text(subject, style: GoogleFonts.inter(fontWeight: unread ? FontWeight.w600 : FontWeight.normal, fontSize: 13)),
        subtitle: Text('From: $from · $date'),
        trailing: unread ? Container(
          width: 8,
          height: 8,
          decoration: const BoxDecoration(color: Colors.blue, shape: BoxShape.circle),
        ) : null,
      ),
    );
  }
}

// ── Tab: Safety ──────────────────────────────────────────
class _SafetyTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Root Safety & Security',
            body: 'Safety checks, permission auditing, and security status for root.',
          ),
          const SizedBox(height: 16),
          _SafetyEntry(name: 'Root Password', status: 'Set', color: Colors.green),
          _SafetyEntry(name: 'SSH Key', status: 'Configured', color: Colors.green),
          _SafetyEntry(name: 'Sudo Access', status: 'Enabled', color: Colors.blue),
          _SafetyEntry(name: 'Root Login', status: 'Disabled (SSH)', color: Colors.orange),
          _SafetyEntry(name: '2FA', status: 'Not Configured', color: Colors.grey),
        ],
      ),
    );
  }
}

class _SafetyEntry extends StatelessWidget {
  final String name;
  final String status;
  final Color color;
  const _SafetyEntry({
    required this.name,
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

// ── Tab: Shell ───────────────────────────────────────────
class _ShellTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Root Shell',
            body: 'Root shell configuration and environment.',
          ),
          const SizedBox(height: 16),
          _ShellEntry(name: 'Default Shell', value: '/bin/bash', color: Colors.blue),
          _ShellEntry(name: 'PATH', value: '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', color: Colors.green),
          _ShellEntry(name: 'EDITOR', value: 'vim', color: Colors.orange),
          _ShellEntry(name: 'LANG', value: 'en_US.UTF-8', color: Colors.purple),
          _ShellEntry(name: 'TERM', value: 'xterm-256color', color: Colors.teal),
        ],
      ),
    );
  }
}

class _ShellEntry extends StatelessWidget {
  final String name;
  final String value;
  final Color color;
  const _ShellEntry({
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
        leading: Icon(Icons.terminal, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(value, style: GoogleFonts.firaCode(fontSize: 11)),
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