/// UmerOS /etc Manager — System Configuration
///
/// Desktop control panel for the UmerOS /etc subsystem.
/// Manages system configuration files, services, and settings.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class EtcManagerApp extends StatefulWidget {
  const EtcManagerApp({super.key});

  @override
  State<EtcManagerApp> createState() => _EtcManagerAppState();
}

class _EtcManagerAppState extends State<EtcManagerApp> {
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
              _Tab('Config', 0, Icons.settings),
              _Tab('Users', 1, Icons.people),
              _Tab('Network', 2, Icons.lan),
              _Tab('Services', 3, Icons.miscellaneous_services),
              _Tab('Security', 4, Icons.security),
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
        return _ConfigTab();
      case 1:
        return _UsersTab();
      case 2:
        return _NetworkTab();
      case 3:
        return _ServicesTab();
      case 4:
        return _SecurityTab();
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

// ── Tab: Config ──────────────────────────────────────────────────
class _ConfigTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'System Configuration',
            body: 'Configuration files in /etc.',
          ),
          const SizedBox(height: 16),
          _ConfigEntry(file: 'fstab', path: '/etc/fstab', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'hosts', path: '/etc/hosts', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'hostname', path: '/etc/hostname', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'resolv.conf', path: '/etc/resolv.conf', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'passwd', path: '/etc/passwd', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'group', path: '/etc/group', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'sudoers', path: '/etc/sudoers', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'os-release', path: '/etc/os-release', status: 'OK', color: Colors.green),
        ],
      ),
    );
  }
}

class _ConfigEntry extends StatelessWidget {
  final String file;
  final String path;
  final String status;
  final Color color;
  const _ConfigEntry({
    required this.file,
    required this.path,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.description, color: color, size: 20),
        title: Text(file, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(path, style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Users ───────────────────────────────────────────────────
class _UsersTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'User Accounts',
            body: 'User accounts and groups from /etc/passwd and /etc/group.',
          ),
          const SizedBox(height: 16),
          _UserEntry(name: 'root', uid: '0', gid: '0', shell: '/bin/bash', color: Colors.red),
          _UserEntry(name: 'umer', uid: '1000', gid: '1000', shell: '/bin/bash', color: Colors.blue),
          _UserEntry(name: 'nobody', uid: '65534', gid: '65534', shell: '/usr/sbin/nologin', color: Colors.grey),
        ],
      ),
    );
  }
}

class _UserEntry extends StatelessWidget {
  final String name;
  final String uid;
  final String gid;
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
        subtitle: Text('UID: $uid · GID: $gid · Shell: $shell', style: GoogleFonts.inter(fontSize: 11)),
      ),
    );
  }
}

// ── Tab: Network ─────────────────────────────────────────────────
class _NetworkTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Network Configuration',
            body: 'Network configuration files in /etc.',
          ),
          const SizedBox(height: 16),
          _ConfigEntry(file: 'networks', path: '/etc/networks', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'hosts', path: '/etc/hosts', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'resolv.conf', path: '/etc/resolv.conf', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'nsswitch.conf', path: '/etc/nsswitch.conf', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'hosts.allow', path: '/etc/hosts.allow', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'hosts.deny', path: '/etc/hosts.deny', status: 'OK', color: Colors.green),
        ],
      ),
    );
  }
}

// ── Tab: Services ────────────────────────────────────────────────
class _ServicesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Services',
            body: 'System services and init scripts.',
          ),
          const SizedBox(height: 16),
          _ServiceEntry(name: 'ssh', status: 'Running', color: Colors.green),
          _ServiceEntry(name: 'nginx', status: 'Running', color: Colors.green),
          _ServiceEntry(name: 'mysql', status: 'Stopped', color: Colors.grey),
          _ServiceEntry(name: 'cron', status: 'Running', color: Colors.green),
          _ServiceEntry(name: 'rsyslog', status: 'Running', color: Colors.green),
        ],
      ),
    );
  }
}

class _ServiceEntry extends StatelessWidget {
  final String name;
  final String status;
  final Color color;
  const _ServiceEntry({required this.name, required this.status, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.miscellaneous_services, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
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

// ── Tab: Security ────────────────────────────────────────────────
class _SecurityTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Security Configuration',
            body: 'Security-related configuration files.',
          ),
          const SizedBox(height: 16),
          _ConfigEntry(file: 'sudoers', path: '/etc/sudoers', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'pam.d', path: '/etc/pam.d', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'ssh/sshd_config', path: '/etc/ssh/sshd_config', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'security', path: '/etc/security', status: 'OK', color: Colors.green),
          _ConfigEntry(file: 'selinux', path: '/etc/selinux', status: 'OK', color: Colors.green),
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