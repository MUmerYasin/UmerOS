/// UmerOS SDK Manager — Application Development Kit
///
/// Desktop control panel for the UmerOS SDK.
/// Manages app templates, build tools, validation, and project scaffolding.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class SdkManagerApp extends StatefulWidget {
  const SdkManagerApp({super.key});

  @override
  State<SdkManagerApp> createState() => _SdkManagerAppState();
}

class _SdkManagerAppState extends State<SdkManagerApp> {
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
              _Tab('Templates', 0, Icons.code),
              _Tab('Build', 1, Icons.build),
              _Tab('Validate', 2, Icons.verified),
              _Tab('Projects', 3, Icons.folder),
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
        return _TemplatesTab();
      case 1:
        return _BuildTab();
      case 2:
        return _ValidateTab();
      case 3:
        return _ProjectsTab();
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

// ── Tab: Templates ───────────────────────────────────────
class _TemplatesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'App Templates',
            body: 'Base classes and templates for building UmerOS applications. '
                'Subclass UmerApp and implement lifecycle hooks.',
          ),
          const SizedBox(height: 16),
          _TemplateEntry(name: 'UmerApp', description: 'Base class for all UmerOS apps', type: 'Class', color: Colors.blue),
          _TemplateEntry(name: 'HelloWorldApp', description: 'Minimal example application', type: 'Example', color: Colors.green),
          _TemplateEntry(name: 'BuildTool', description: 'Scaffold and package apps', type: 'Tool', color: Colors.orange),
          _TemplateEntry(name: 'AppValidator', description: 'Validate app structure and manifest', type: 'Tool', color: Colors.purple),
        ],
      ),
    );
  }
}

class _TemplateEntry extends StatelessWidget {
  final String name;
  final String description;
  final String type;
  final Color color;
  const _TemplateEntry({
    required this.name,
    required this.description,
    required this.type,
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
          child: Icon(Icons.code, color: color, size: 18),
        ),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(description, style: GoogleFonts.inter(fontSize: 12)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(type, style: GoogleFonts.inter(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }
}

// ── Tab: Build ───────────────────────────────────────────
class _BuildTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Build Tool',
            body: 'Scaffold new app projects, package for distribution, '
                'and manage dependencies.',
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.create_new_folder, size: 16),
                label: const Text('Scaffold App'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.inventory_2, size: 16),
                label: const Text('Package App'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.play_arrow, size: 16),
                label: const Text('Build'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _InfoCard(
            title: 'Build Status',
            body: 'No active builds. Use "Scaffold App" to create a new project.',
          ),
        ],
      ),
    );
  }
}

// ── Tab: Validate ────────────────────────────────────────
class _ValidateTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'App Validator',
            body: 'Validate app structure, manifest, and code. '
                'Checks required fields, version format, and lifecycle hooks.',
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.folder_open, size: 16),
                label: const Text('Select App Dir'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () {},
                icon: const Icon(Icons.verified, size: 16),
                label: const Text('Validate'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _InfoCard(
            title: 'Validation Result',
            body: 'No validation performed yet. Select an app directory and click "Validate".',
          ),
        ],
      ),
    );
  }
}

// ── Tab: Projects ────────────────────────────────────────
class _ProjectsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'SDK Projects',
            body: 'Manage scaffolded app projects in /sdk/projects/.',
          ),
          const SizedBox(height: 16),
          _ProjectEntry(name: 'HelloWorld', version: '1.0.0', status: 'Ready', color: Colors.green),
          _ProjectEntry(name: 'MyApp', version: '0.1.0', status: 'Draft', color: Colors.orange),
          _ProjectEntry(name: 'TestApp', version: '1.0.0', status: 'Validated', color: Colors.blue),
        ],
      ),
    );
  }
}

class _ProjectEntry extends StatelessWidget {
  final String name;
  final String version;
  final String status;
  final Color color;
  const _ProjectEntry({
    required this.name,
    required this.version,
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
          child: const Icon(Icons.code, color: Colors.deepPurple, size: 18),
        ),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('Version $version'),
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