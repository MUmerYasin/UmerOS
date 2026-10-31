/// UmerOS Build Manager — Build & Signing
///
/// Desktop control panel for the UmerOS build subsystem.
/// Manages build scripts, signing, and artifacts.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class BuildManagerApp extends StatefulWidget {
  const BuildManagerApp({super.key});

  @override
  State<BuildManagerApp> createState() => _BuildManagerAppState();
}

class _BuildManagerAppState extends State<BuildManagerApp> {
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
          child: Row(
            children: [
              _Tab('Builds', 0, Icons.build),
              _Tab('Signing', 1, Icons.verified_user),
              _Tab('Artifacts', 2, Icons.inventory_2),
              _Tab('Config', 3, Icons.settings),
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
        return _BuildsTab();
      case 1:
        return _SigningTab();
      case 2:
        return _ArtifactsTab();
      case 3:
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

// ── Tab: Builds ──────────────────────────────────────────────────
class _BuildsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Build Scripts',
            body: 'Available build scripts and configurations.',
          ),
          const SizedBox(height: 16),
          _BuildEntry(name: 'build_umeros_gui.py', type: 'PyInstaller', status: 'Ready', color: Colors.green),
          _BuildEntry(name: 'sign_artifact.py', type: 'Signing', status: 'Ready', color: Colors.green),
          _BuildEntry(name: 'UmerOS-GUI.spec', type: 'Spec', status: 'Ready', color: Colors.blue),
        ],
      ),
    );
  }
}

class _BuildEntry extends StatelessWidget {
  final String name;
  final String type;
  final String status;
  final Color color;
  const _BuildEntry({
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
        leading: Icon(Icons.build, color: color, size: 20),
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

// ── Tab: Signing ─────────────────────────────────────────────────
class _SigningTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Artifact Signing',
            body: 'Cryptographic signing of build artifacts.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Signing Algorithm', value: 'Ed25519'),
          _InfoRow(label: 'Key Store', value: 'Trusted Keys'),
          _InfoRow(label: 'Signed Artifacts', value: '3'),
          _InfoRow(label: 'Unsigned Artifacts', value: '0'),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.verified_user),
            label: const Text('Sign All Artifacts'),
          ),
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

// ── Tab: Artifacts ───────────────────────────────────────────────
class _ArtifactsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Build Artifacts',
            body: 'Compiled and signed build artifacts.',
          ),
          const SizedBox(height: 16),
          _ArtifactEntry(name: 'UmerOS-GUI.exe', type: 'Executable', size: '45.2 MB', signed: 'Yes', color: Colors.green),
          _ArtifactEntry(name: 'UmerOS-GUI.spec', type: 'Spec', size: '3.1 KB', signed: 'N/A', color: Colors.blue),
        ],
      ),
    );
  }
}

class _ArtifactEntry extends StatelessWidget {
  final String name;
  final String type;
  final String size;
  final String signed;
  final Color color;
  const _ArtifactEntry({
    required this.name,
    required this.type,
    required this.size,
    required this.signed,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.inventory_2, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$type · $size', style: GoogleFonts.inter(fontSize: 11)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text('Signed: $signed', style: GoogleFonts.inter(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
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
            title: 'Build Configuration',
            body: 'Build settings and parameters.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Entry Point', value: 'ui/launch_gui.py'),
          _InfoRow(label: 'Frontend', value: 'ui/flutter_ui'),
          _InfoRow(label: 'Build Tool', value: 'PyInstaller'),
          _InfoRow(label: 'Output Dir', value: 'build/UmerOS-GUI'),
          _InfoRow(label: 'Platform', value: 'Windows'),
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