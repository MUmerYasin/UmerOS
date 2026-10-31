/// UmerOS Initrd Manager — Initial RAM Disk
///
/// Desktop control panel for the UmerOS initrd subsystem.
/// Manages boot phases, cpio archives, ramdisk, hooks, and scenarios.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class InitrdManagerApp extends StatefulWidget {
  const InitrdManagerApp({super.key});

  @override
  State<InitrdManagerApp> createState() => _InitrdManagerAppState();
}

class _InitrdManagerAppState extends State<InitrdManagerApp> {
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
              _Tab('Phases', 0, Icons.timeline),
              _Tab('Ramdisk', 1, Icons.memory),
              _Tab('Archives', 2, Icons.archive),
              _Tab('Hooks', 3, Icons.code),
              _Tab('Modules', 4, Icons.extension),
              _Tab('Scenarios', 5, Icons.play_circle),
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
        return _PhasesTab();
      case 1:
        return _RamdiskTab();
      case 2:
        return _ArchivesTab();
      case 3:
        return _HooksTab();
      case 4:
        return _ModulesTab();
      case 5:
        return _ScenariosTab();
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

// ── Tab: Phases ──────────────────────────────────────────────────
class _PhasesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Boot Phases',
            body: 'Eight-phase initramfs boot sequence.',
          ),
          const SizedBox(height: 16),
          _PhaseEntry(phase: 1, name: 'Early', status: 'Done', color: Colors.green),
          _PhaseEntry(phase: 2, name: 'Mount Root', status: 'Done', color: Colors.green),
          _PhaseEntry(phase: 3, name: 'Load Modules', status: 'Done', color: Colors.green),
          _PhaseEntry(phase: 4, name: 'Pivot Root', status: 'Done', color: Colors.green),
          _PhaseEntry(phase: 5, name: 'Init', status: 'Done', color: Colors.green),
          _PhaseEntry(phase: 6, name: 'Cleanup', status: 'In progress', color: Colors.blue),
          _PhaseEntry(phase: 7, name: 'Handoff', status: 'Pending', color: Colors.grey),
          _PhaseEntry(phase: 8, name: 'Complete', status: 'Pending', color: Colors.grey),
        ],
      ),
    );
  }
}

class _PhaseEntry extends StatelessWidget {
  final int phase;
  final String name;
  final String status;
  final Color color;
  const _PhaseEntry({
    required this.phase,
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
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Text('$phase', style: GoogleFonts.firaCode(fontSize: 10, color: color, fontWeight: FontWeight.bold)),
        ),
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

// ── Tab: Ramdisk ──────────────────────────────────────────────────
class _RamdiskTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'RAM Disk',
            body: 'In-memory tmpfs stand-in for initramfs.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'State', value: 'Active'),
          _InfoRow(label: 'Size', value: '64 MB'),
          _InfoRow(label: 'Used', value: '12.4 MB'),
          _InfoRow(label: 'Free', value: '51.6 MB'),
          _InfoRow(label: 'Mount Point', value: '/'),
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

// ── Tab: Archives ────────────────────────────────────────────────
class _ArchivesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'CPIO Archives',
            body: 'Initramfs archive management.',
          ),
          const SizedBox(height: 16),
          _ArchiveEntry(name: 'initramfs-6.8.0-umeros.img', format: 'cpio.gz', size: '45.2 MB', status: 'Valid', color: Colors.green),
          _ArchiveEntry(name: 'initramfs-6.8.0-umeros.img.gz', format: 'cpio.gz', size: '12.8 MB', status: 'Valid', color: Colors.green),
          _ArchiveEntry(name: 'initramfs-recovery.img', format: 'cpio', size: '38.5 MB', status: 'Valid', color: Colors.blue),
        ],
      ),
    );
  }
}

class _ArchiveEntry extends StatelessWidget {
  final String name;
  final String format;
  final String size;
  final String status;
  final Color color;
  const _ArchiveEntry({
    required this.name,
    required this.format,
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
        leading: Icon(Icons.archive, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Format: $format · Size: $size', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Hooks ───────────────────────────────────────────────────
class _HooksTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Initramfs Hooks',
            body: 'initramfs-tools style hooks.',
          ),
          const SizedBox(height: 16),
          _HookEntry(name: 'premount', point: 'pre-mount', status: 'Registered', color: Colors.green),
          _HookEntry(name: 'postmount', point: 'post-mount', status: 'Registered', color: Colors.green),
          _HookEntry(name: 'prepivot', point: 'pre-pivot', status: 'Registered', color: Colors.blue),
          _HookEntry(name: 'postpivot', point: 'post-pivot', status: 'Registered', color: Colors.blue),
        ],
      ),
    );
  }
}

class _HookEntry extends StatelessWidget {
  final String name;
  final String point;
  final String status;
  final Color color;
  const _HookEntry({
    required this.name,
    required this.point,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.code, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Point: $point', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Modules ─────────────────────────────────────────────────
class _ModulesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Module Resolution',
            body: 'Kernel modules resolved for initramfs.',
          ),
          const SizedBox(height: 16),
          _ModuleEntry(name: 'ext4', type: 'filesystem', status: 'Included', color: Colors.green),
          _ModuleEntry(name: 'xfs', type: 'filesystem', status: 'Included', color: Colors.green),
          _ModuleEntry(name: 'nvidia', type: 'driver', status: 'Included', color: Colors.green),
          _ModuleEntry(name: 'usb_storage', type: 'driver', status: 'Included', color: Colors.blue),
          _ModuleEntry(name: 'bluetooth', type: 'driver', status: 'Optional', color: Colors.orange),
        ],
      ),
    );
  }
}

class _ModuleEntry extends StatelessWidget {
  final String name;
  final String type;
  final String status;
  final Color color;
  const _ModuleEntry({
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
        leading: Icon(Icons.extension, color: color, size: 20),
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

// ── Tab: Scenarios ───────────────────────────────────────────────
class _ScenariosTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Boot Scenarios',
            body: 'Predefined boot scenarios for different use cases.',
          ),
          const SizedBox(height: 16),
          _ScenarioEntry(name: 'Normal', description: 'Standard boot', status: 'Active', color: Colors.green),
          _ScenarioEntry(name: 'Recovery', description: 'Recovery mode', status: 'Available', color: Colors.blue),
          _ScenarioEntry(name: 'Live', description: 'Live USB boot', status: 'Available', color: Colors.blue),
          _ScenarioEntry(name: 'Install', description: 'Installation mode', status: 'Available', color: Colors.orange),
        ],
      ),
    );
  }
}

class _ScenarioEntry extends StatelessWidget {
  final String name;
  final String description;
  final String status;
  final Color color;
  const _ScenarioEntry({
    required this.name,
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
        leading: Icon(Icons.play_circle, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
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