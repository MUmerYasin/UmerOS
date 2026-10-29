/// UmerOS /var Manager — Variable State, Logs, Cache, Spool & Mail
///
/// Desktop control panel for the UmerOS /var subsystem.
/// Manages logs, spool, cache, mail, and FHS /var directories.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class VarManagerApp extends StatefulWidget {
  const VarManagerApp({super.key});

  @override
  State<VarManagerApp> createState() => _VarManagerAppState();
}

class _VarManagerAppState extends State<VarManagerApp> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      children: [
        // Tab bar
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
              _Tab('Logs', 0, Icons.article),
              _Tab('Cache', 1, Icons.cached),
              _Tab('Spool', 2, Icons.print),
              _Tab('Mail', 3, Icons.mail),
              _Tab('Directories', 4, Icons.folder),
              _Tab('Lib', 5, Icons.library_books),
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
        return _LogsTab();
      case 1:
        return _CacheTab();
      case 2:
        return _SpoolTab();
      case 3:
        return _MailTab();
      case 4:
        return _DirectoriesTab();
      case 5:
        return _LibTab();
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

// ── Tab: Logs ────────────────────────────────────────────
class _LogsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final logs = [
      _LogEntry('syslog', 'System log — kernel messages and service events', Icons.article, Colors.blue),
      _LogEntry('auth.log', 'Authentication log — login attempts and sudo', Icons.security, Colors.orange),
      _LogEntry('dmesg', 'Kernel ring buffer — hardware and driver messages', Icons.memory, Colors.purple),
      _LogEntry('kern.log', 'Kernel log — detailed kernel diagnostics', Icons.terminal, Colors.teal),
      _LogEntry('daemon.log', 'Daemon log — background service output', Icons.settings, Colors.grey),
      _LogEntry('mail.log', 'Mail transfer log — SMTP/IMAP activity', Icons.mail, Colors.indigo),
    ];

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: logs.length,
      separatorBuilder: (_, _) => const SizedBox(height: 8),
      itemBuilder: (context, i) {
        final log = logs[i];
        return Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: log.color.withValues(alpha: 0.15),
              child: Icon(log.icon, color: log.color, size: 18),
            ),
            title: Text(log.name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
            subtitle: Text(log.description, style: GoogleFonts.inter(fontSize: 12)),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  icon: const Icon(Icons.visibility, size: 18),
                  tooltip: 'View',
                  onPressed: () {},
                ),
                IconButton(
                  icon: const Icon(Icons.compress, size: 18),
                  tooltip: 'Rotate/Compress',
                  onPressed: () {},
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline, size: 18),
                  tooltip: 'Clear',
                  onPressed: () {},
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _LogEntry {
  final String name;
  final String description;
  final IconData icon;
  final Color color;
  const _LogEntry(this.name, this.description, this.icon, this.color);
}

// ── Tab: Cache ───────────────────────────────────────────
class _CacheTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Cache Management',
            body: 'Application cache data is purely derived (regenerable). '
                'May be deleted at any time without data loss. '
                'LRU eviction with size budget and TTL-based expiry.',
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Cache Entries'),
          const SizedBox(height: 8),
          _CacheEntry(name: 'apt', size: '42 MB', entries: 128, ttl: '7 days'),
          _CacheEntry(name: 'pip', size: '128 MB', entries: 342, ttl: '30 days'),
          _CacheEntry(name: 'flutter', size: '256 MB', entries: 89, ttl: '14 days'),
          _CacheEntry(name: 'browser', size: '64 MB', entries: 256, ttl: '3 days'),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.cleaning_services, size: 16),
                label: const Text('Clear All Caches'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Refresh'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _CacheEntry extends StatelessWidget {
  final String name;
  final String size;
  final int entries;
  final String ttl;
  const _CacheEntry({
    required this.name,
    required this.size,
    required this.entries,
    required this.ttl,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Colors.blue.withValues(alpha: 0.15),
          child: const Icon(Icons.cached, color: Colors.blue, size: 18),
        ),
        title: Text('$name cache', style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$entries entries · TTL: $ttl'),
        trailing: Text(size, style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 13)),
      ),
    );
  }
}

// ── Tab: Spool ───────────────────────────────────────────
class _SpoolTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Spool Management',
            body: 'Manages print jobs, mail queue, and cron spool. '
                'Jobs are queued for processing by the appropriate daemon.',
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Active Spool Jobs'),
          const SizedBox(height: 8),
          _SpoolJob(name: 'print_job_001', type: 'Print', status: 'Queued', color: Colors.blue),
          _SpoolJob(name: 'mail_queue_003', type: 'Mail', status: 'Processing', color: Colors.orange),
          _SpoolJob(name: 'cron_daily', type: 'Cron', status: 'Scheduled', color: Colors.green),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.delete_sweep, size: 16),
                label: const Text('Clear Spool'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Refresh'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SpoolJob extends StatelessWidget {
  final String name;
  final String type;
  final String status;
  final Color color;
  const _SpoolJob({
    required this.name,
    required this.type,
    required this.status,
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
          child: Icon(
            type == 'Print' ? Icons.print : type == 'Mail' ? Icons.mail : Icons.schedule,
            color: color,
            size: 18,
          ),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$type · $status'),
        trailing: IconButton(
          icon: const Icon(Icons.cancel, size: 18),
          tooltip: 'Cancel job',
          onPressed: () {},
        ),
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
            title: 'Mail Management',
            body: 'Manages local mailboxes in /var/mail and /var/spool/mail. '
                'Supports MBOX and Maildir formats.',
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Mailboxes'),
          const SizedBox(height: 8),
          _MailboxEntry(name: 'root', messages: 12, unread: 3, size: '2.4 MB'),
          _MailboxEntry(name: 'umer', messages: 45, unread: 8, size: '12.8 MB'),
          _MailboxEntry(name: 'system', messages: 3, unread: 0, size: '0.5 MB'),
        ],
      ),
    );
  }
}

class _MailboxEntry extends StatelessWidget {
  final String name;
  final int messages;
  final int unread;
  final String size;
  const _MailboxEntry({
    required this.name,
    required this.messages,
    required this.unread,
    required this.size,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Colors.indigo.withValues(alpha: 0.15),
          child: const Icon(Icons.mail, color: Colors.indigo, size: 18),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$messages messages · $unread unread'),
        trailing: Text(size, style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 13)),
      ),
    );
  }
}

// ── Tab: Directories ─────────────────────────────────────
class _DirectoriesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'FHS /var Directory Structure',
            body: '/var contains variable data files: logs, caches, spool, '
                'mail, and runtime state. Managed per FHS 3.0 specification.',
          ),
          const SizedBox(height: 16),
          _DirEntry(path: '/var/log', description: 'Log files', status: 'Active', color: Colors.blue),
          _DirEntry(path: '/var/cache', description: 'Application cache data', status: 'Active', color: Colors.green),
          _DirEntry(path: '/var/spool', description: 'Spool for print, mail, cron', status: 'Active', color: Colors.orange),
          _DirEntry(path: '/var/mail', description: 'User mailboxes', status: 'Active', color: Colors.indigo),
          _DirEntry(path: '/var/lib', description: 'Variable state information', status: 'Active', color: Colors.purple),
          _DirEntry(path: '/var/local', description: 'Variable data for /usr/local', status: 'Active', color: Colors.teal),
          _DirEntry(path: '/var/lock', description: 'Lock files (→ /run/lock)', status: 'Symlink', color: Colors.grey),
          _DirEntry(path: '/var/opt', description: 'Variable data for /opt', status: 'Active', color: Colors.amber),
          _DirEntry(path: '/var/run', description: 'Runtime data (→ /run)', status: 'Symlink', color: Colors.grey),
          _DirEntry(path: '/var/tmp', description: 'Temporary files (preserved)', status: 'Active', color: Colors.cyan),
        ],
      ),
    );
  }
}

class _DirEntry extends StatelessWidget {
  final String path;
  final String description;
  final String status;
  final Color color;
  const _DirEntry({
    required this.path,
    required this.description,
    required this.status,
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

// ── Tab: Lib ─────────────────────────────────────────────
class _LibTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: '/var/lib — Variable State Information',
            body: 'State information for programs: dpkg, apt, systemd, etc. '
                'Managed via AlternativesManager and VarLibManager.',
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'State Entries'),
          const SizedBox(height: 8),
          _StateEntry(name: 'dpkg', path: '/var/lib/dpkg', status: 'Healthy', color: Colors.green),
          _StateEntry(name: 'apt', path: '/var/lib/apt', status: 'Healthy', color: Colors.green),
          _StateEntry(name: 'systemd', path: '/var/lib/systemd', status: 'Healthy', color: Colors.green),
          _StateEntry(name: 'snapd', path: '/var/lib/snapd', status: 'Active', color: Colors.blue),
          _StateEntry(name: 'NetworkManager', path: '/var/lib/NetworkManager', status: 'Active', color: Colors.blue),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Refresh State'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.cleaning_services, size: 16),
                label: const Text('Clean Stale State'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StateEntry extends StatelessWidget {
  final String name;
  final String path;
  final String status;
  final Color color;
  const _StateEntry({
    required this.name,
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
        leading: Icon(Icons.storage, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(path, style: GoogleFonts.firaCode(fontSize: 11)),
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

class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle({required this.title});

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w600),
    );
  }
}