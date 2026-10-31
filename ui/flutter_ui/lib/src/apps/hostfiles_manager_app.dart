/// UmerOS HostFiles Manager — Host Configuration Files
///
/// Desktop control panel for UmerOS host files.
/// Manages welcome messages, chat logs, and host configuration.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class HostFilesManagerApp extends StatefulWidget {
  const HostFilesManagerApp({super.key});

  @override
  State<HostFilesManagerApp> createState() => _HostFilesManagerAppState();
}

class _HostFilesManagerAppState extends State<HostFilesManagerApp> {
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
              _Tab('Welcome', 0, Icons.waving_hand),
              _Tab('Chat Log', 1, Icons.chat),
              _Tab('Config', 2, Icons.settings),
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
        return _WelcomeTab();
      case 1:
        return _ChatLogTab();
      case 2:
        return _ConfigTab();
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

// ── Tab: Welcome ─────────────────────────────────────────────────
class _WelcomeTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Welcome Message',
            body: 'Host welcome message displayed on boot.',
          ),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.green.shade50,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.green.shade100),
            ),
            child: Text(
              'Welcome to Umer OS v2.0.0-Quantum',
              style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.green.shade900),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.edit),
            label: const Text('Edit Welcome Message'),
          ),
        ],
      ),
    );
  }
}

// ── Tab: Chat Log ────────────────────────────────────────────────
class _ChatLogTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Chat Log',
            body: 'Host chat log and communication history.',
          ),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: Text(
              'The core philosophy of Umer OS revolves around zero-trust security, '
              'efficient resource management through AI, and the integration of quantum '
              'computing principles to enhance performance and reliability. It aims to '
              'provide a secure, adaptable, and user-centric operating environment.',
              style: GoogleFonts.inter(fontSize: 12, height: 1.5),
            ),
          ),
        ],
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
            title: 'Host Configuration',
            body: 'Host-specific configuration files.',
          ),
          const SizedBox(height: 16),
          _ConfigEntry(file: 'welcome.txt', path: '/HostFiles/welcome.txt', size: '33 bytes'),
          _ConfigEntry(file: 'welcome_copy.txt', path: '/HostFiles/welcome_copy.txt', size: '33 bytes'),
          _ConfigEntry(file: 'chat_log.txt', path: '/HostFiles/chat_log.txt', size: '281 bytes'),
        ],
      ),
    );
  }
}

class _ConfigEntry extends StatelessWidget {
  final String file;
  final String path;
  final String size;
  const _ConfigEntry({required this.file, required this.path, required this.size});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.description, color: Colors.blue, size: 20),
        title: Text(file, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(path, style: GoogleFonts.inter(fontSize: 11)),
        trailing: Text(size, style: GoogleFonts.inter(fontSize: 11, color: Colors.grey.shade600)),
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