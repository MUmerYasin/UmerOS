/// UmerOS Dist Manager — Distribution
///
/// Desktop control panel for UmerOS distribution.
/// Manages build artifacts, releases, and packages.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class DistManagerApp extends StatefulWidget {
  const DistManagerApp({super.key});

  @override
  State<DistManagerApp> createState() => _DistManagerAppState();
}

class _DistManagerAppState extends State<DistManagerApp> {
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
              _Tab('Releases', 1, Icons.new_releases),
              _Tab('Artifacts', 2, Icons.inventory_2),
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
        return _ReleasesTab();
      case 2:
        return _ArtifactsTab();
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
            title: 'Build Artifacts',
            body: 'Compiled build artifacts and packages.',
          ),
          const SizedBox(height: 16),
          _BuildEntry(name: 'umeros-2.1.0-quantum.iso', type: 'ISO', size: '2.4 GB', status: 'Ready', color: Colors.green),
          _BuildEntry(name: 'umeros-2.1.0-quantum.img', type: 'Disk Image', size: '4.8 GB', status: 'Ready', color: Colors.green),
          _BuildEntry(name: 'umeros-2.1.0-quantum.tar.gz', type: 'Tarball', size: '1.2 GB', status: 'Ready', color: Colors.blue),
        ],
      ),
    );
  }
}

class _BuildEntry extends StatelessWidget {
  final String name;
  final String type;
  final String size;
  final String status;
  final Color color;
  const _BuildEntry({
    required this.name,
    required this.type,
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
        leading: Icon(Icons.build, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$type · $size', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Releases ────────────────────────────────────────────────
class _ReleasesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Releases',
            body: 'Published UmerOS releases.',
          ),
          const SizedBox(height: 16),
          _ReleaseEntry(version: '2.1.0-quantum', date: '2026-10-30', status: 'Latest', color: Colors.green),
          _ReleaseEntry(version: '2.0.0-quantum', date: '2026-09-15', status: 'Stable', color: Colors.blue),
          _ReleaseEntry(version: '1.9.0', date: '2026-08-01', status: 'Legacy', color: Colors.grey),
        ],
      ),
    );
  }
}

class _ReleaseEntry extends StatelessWidget {
  final String version;
  final String date;
  final String status;
  final Color color;
  const _ReleaseEntry({
    required this.version,
    required this.date,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.new_releases, color: color, size: 20),
        title: Text(version, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Released: $date', style: GoogleFonts.inter(fontSize: 11)),
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
            body: 'Distribution artifacts and packages.',
          ),
          const SizedBox(height: 16),
          _ArtifactEntry(name: 'kernel.img', type: 'Kernel', size: '12.4 MB', status: 'OK', color: Colors.green),
          _ArtifactEntry(name: 'initrd.img', type: 'Initrd', size: '45.2 MB', status: 'OK', color: Colors.green),
          _ArtifactEntry(name: 'rootfs.tar.gz', type: 'Root FS', size: '1.2 GB', status: 'OK', color: Colors.green),
          _ArtifactEntry(name: 'modules.tar.gz', type: 'Modules', size: '256 MB', status: 'OK', color: Colors.blue),
        ],
      ),
    );
  }
}

class _ArtifactEntry extends StatelessWidget {
  final String name;
  final String type;
  final String size;
  final String status;
  final Color color;
  const _ArtifactEntry({
    required this.name,
    required this.type,
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
        leading: Icon(Icons.inventory_2, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$type · $size', style: GoogleFonts.inter(fontSize: 11)),
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