/// UmerOS /bin Manager — Essential Command Binaries
///
/// Desktop control panel for the UmerOS /bin subsystem.
/// Covers all 43 bin modules.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class BinManagerApp extends StatefulWidget {
  const BinManagerApp({super.key});

  @override
  State<BinManagerApp> createState() => _BinManagerAppState();
}

class _BinManagerAppState extends State<BinManagerApp> {
  int _tab = 0;
  String _search = '';

  final List<_BinCategory> _categories = [
    _BinCategory('Essential', Icons.terminal, [
      'essential_commands', 'boolean_ops', 'archive',
    ]),
    _BinCategory('Shell', Icons.code, [
      'bash', 'csh', 'shell', 'ed',
    ]),
    _BinCategory('System', Icons.settings, [
      'system_info', 'process', 'permissions', 'device',
      'home', 'network_cmds',
    ]),
    _BinCategory('User', Icons.person, [
      'user_commands',
    ]),
    _BinCategory('Usr', Icons.folder, [
      'usr_cmds', 'usr_commands', 'usr_doc', 'usr_etc', 'usr_games',
      'usr_include', 'usr_lib', 'usr_libexec', 'usr_libqual',
      'usr_local', 'usr_local_libexec', 'usr_man', 'usr_sbin_cmds',
      'usr_share', 'usr_share_color', 'usr_share_dict', 'usr_share_doc',
      'usr_share_games', 'usr_share_info', 'usr_share_locale',
      'usr_share_nls', 'usr_share_ppd', 'usr_share_sgml',
      'usr_share_templates', 'usr_share_xml', 'usr_src', 'usr_tmp',
      'usr_x11r6',
    ]),
    _BinCategory('Registry', Icons.list, [
      'bin_manager',
    ]),
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final filtered = _search.isEmpty
        ? _categories
        : _categories
            .map((c) => _BinCategory(
                  c.name,
                  c.icon,
                  c.commands.where((cmd) => cmd.toLowerCase().contains(_search.toLowerCase())).toList(),
                ))
            .where((c) => c.commands.isNotEmpty)
            .toList();

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            decoration: InputDecoration(
              labelText: 'Search commands',
              hintText: 'e.g. ls, cp, grep',
              prefixIcon: const Icon(Icons.search),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onChanged: (v) => setState(() => _search = v),
          ),
        ),
        Container(
          decoration: BoxDecoration(
            color: scheme.surface,
            border: Border(
              bottom: BorderSide(color: scheme.outline.withValues(alpha: 0.2)),
            ),
          ),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: filtered.map((c) => _CategoryTab(
                label: c.name,
                icon: c.icon,
                isSelected: _tab == filtered.indexOf(c),
                onTap: () => setState(() => _tab = filtered.indexOf(c)),
                count: c.commands.length,
              )).toList(),
            ),
          ),
        ),
        Expanded(
          child: filtered.isEmpty
              ? Center(child: Text('No commands found', style: GoogleFonts.inter(color: Colors.grey)))
              : _buildContent(filtered[_tab.clamp(0, filtered.length - 1)]),
        ),
      ],
    );
  }

  Widget _buildContent(_BinCategory category) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: category.name,
            body: '${category.commands.length} command modules.',
          ),
          const SizedBox(height: 16),
          ...category.commands.map((c) => _CommandEntry(name: c)),
        ],
      ),
    );
  }
}

class _BinCategory {
  final String name;
  final IconData icon;
  final List<String> commands;
  const _BinCategory(this.name, this.icon, this.commands);
}

class _CategoryTab extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;
  final int count;
  const _CategoryTab({
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.onTap,
    required this.count,
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
            const SizedBox(width: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
              decoration: BoxDecoration(
                color: scheme.primaryContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '$count',
                style: GoogleFonts.inter(fontSize: 9, color: scheme.onPrimaryContainer, fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CommandEntry extends StatelessWidget {
  final String name;
  const _CommandEntry({required this.name});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.terminal, color: Colors.green, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('/bin/$name.py', style: GoogleFonts.inter(fontSize: 11)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: Colors.green.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text('Available', style: GoogleFonts.inter(fontSize: 10, color: Colors.green, fontWeight: FontWeight.w600)),
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