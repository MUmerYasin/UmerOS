/// UmerOS Compatibility Manager — Windows Compatibility Layer
///
/// Desktop control panel for the UmerOS compatibility subsystem.
/// Covers all 54 compatibility modules.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class CompatibilityManagerApp extends StatefulWidget {
  const CompatibilityManagerApp({super.key});

  @override
  State<CompatibilityManagerApp> createState() => _CompatibilityManagerAppState();
}

class _CompatibilityManagerAppState extends State<CompatibilityManagerApp> {
  int _tab = 0;
  String _search = '';

  final List<_CompatCategory> _categories = [
    _CompatCategory('Core', Icons.settings, [
      'container', 'container_engine', 'com_support', 'delay_imports',
      'forwarded', 'manifest', 'memory_map', 'sync', 'syscall_shim',
      'tokens', 'version_info', 'dll_loader', 'dll_search', 'ntstatus',
    ]),
    _CompatCategory('PE/EXE', Icons.insert_drive_file, [
      'pe_loader', 'pe_exports', 'pe_imports', 'pe_relocations',
      'pe_resources', 'pe_tls', 'mz_loader', 'ne_loader', 'signed_pe',
    ]),
    _CompatCategory('Registry', Icons.storage, [
      'registry_hive', 'registry_paths', 'registry_view',
    ]),
    _CompatCategory('Environment', Icons.terminal, [
      'environment', 'env_dialog', 'env_registry', 'installer_env',
      'long_path', 'timezone',
    ]),
    _CompatCategory('Win32 API', Icons.window, [
      'win_kernel32', 'win_ntdll', 'win_user32', 'win_gdi32',
      'win_advapi32', 'win_shell32', 'win_sid', 'win_strings',
      'win_guid', 'win_path', 'winerror',
    ]),
    _CompatCategory('Winsock', Icons.lan, [
      'winsock', 'api_set',
    ]),
    _CompatCategory('Shell', Icons.code, [
      'shell_links', 'file_attrs',
    ]),
    _CompatCategory('Service', Icons.miscellaneous_services, [
      'service_manager', 'msi_runtime',
    ]),
    _CompatCategory('Runner', Icons.play_arrow, [
      'win32_runner', 'x86_runner', 'wine_shim',
    ]),
    _CompatCategory('Known Folders', Icons.folder, [
      'knownfolders',
    ]),
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final filtered = _search.isEmpty
        ? _categories
        : _categories
            .map((c) => _CompatCategory(
                  c.name,
                  c.icon,
                  c.modules.where((m) => m.toLowerCase().contains(_search.toLowerCase())).toList(),
                ))
            .where((c) => c.modules.isNotEmpty)
            .toList();

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            decoration: InputDecoration(
              labelText: 'Search modules',
              hintText: 'e.g. pe, win, registry',
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
                count: c.modules.length,
              )).toList(),
            ),
          ),
        ),
        Expanded(
          child: filtered.isEmpty
              ? Center(child: Text('No modules found', style: GoogleFonts.inter(color: Colors.grey)))
              : _buildContent(filtered[_tab.clamp(0, filtered.length - 1)]),
        ),
      ],
    );
  }

  Widget _buildContent(_CompatCategory category) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: category.name,
            body: '${category.modules.length} compatibility modules.',
          ),
          const SizedBox(height: 16),
          ...category.modules.map((m) => _ModuleEntry(name: m)),
        ],
      ),
    );
  }
}

class _CompatCategory {
  final String name;
  final IconData icon;
  final List<String> modules;
  const _CompatCategory(this.name, this.icon, this.modules);
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

class _ModuleEntry extends StatelessWidget {
  final String name;
  const _ModuleEntry({required this.name});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.extension, color: Colors.blue, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('/compatibility/$name.py', style: GoogleFonts.inter(fontSize: 11)),
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