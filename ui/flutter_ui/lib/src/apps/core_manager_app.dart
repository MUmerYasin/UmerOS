/// UmerOS Core Manager — Core Primitives
///
/// Desktop control panel for the UmerOS core subsystem.
/// Manages capability gates, commands, live tasks, path guard, UDMF.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class CoreManagerApp extends StatefulWidget {
  const CoreManagerApp({super.key});

  @override
  State<CoreManagerApp> createState() => _CoreManagerAppState();
}

class _CoreManagerAppState extends State<CoreManagerApp> {
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
              _Tab('Capabilities', 0, Icons.security),
              _Tab('Commands', 1, Icons.terminal),
              _Tab('Live Tasks', 2, Icons.task),
              _Tab('Path Guard', 3, Icons.shield),
              _Tab('UDMF', 4, Icons.data_object),
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
        return _CapabilitiesTab();
      case 1:
        return _CommandsTab();
      case 2:
        return _LiveTasksTab();
      case 3:
        return _PathGuardTab();
      case 4:
        return _UdmfTab();
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

// ── Tab: Capabilities ────────────────────────────────────────────
class _CapabilitiesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Capability Gate',
            body: 'Zero-trust capability-based access control.',
          ),
          const SizedBox(height: 16),
          _CapEntry(cap: 'CAP_SYS_ADMIN', status: 'Granted', color: Colors.green),
          _CapEntry(cap: 'CAP_NET_SEND', status: 'Granted', color: Colors.green),
          _CapEntry(cap: 'CAP_FS_ADMIN', status: 'Granted', color: Colors.green),
          _CapEntry(cap: 'CAP_IPC_SEND', status: 'Granted', color: Colors.green),
          _CapEntry(cap: 'CAP_DEVICE_USB', status: 'Denied', color: Colors.red),
          _CapEntry(cap: 'CAP_AI_INFERENCE', status: 'Granted', color: Colors.green),
        ],
      ),
    );
  }
}

class _CapEntry extends StatelessWidget {
  final String cap;
  final String status;
  final Color color;
  const _CapEntry({required this.cap, required this.status, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.security, color: color, size: 20),
        title: Text(cap, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
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

// ── Tab: Commands ────────────────────────────────────────────────
class _CommandsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Commands',
            body: 'Base command class for FHS programs.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Command Base', value: 'Command'),
          _InfoRow(label: 'Base Command', value: 'BaseCommand'),
          _InfoRow(label: 'Execute', value: 'execute(args) -> int'),
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

// ── Tab: Live Tasks ──────────────────────────────────────────────
class _LiveTasksTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Live Task Manager',
            body: 'Real-time task management and monitoring.',
          ),
          const SizedBox(height: 16),
          _TaskEntry(name: 'task-1', status: 'Running', pid: '1001', color: Colors.green),
          _TaskEntry(name: 'task-2', status: 'Ready', pid: '1002', color: Colors.blue),
          _TaskEntry(name: 'task-3', status: 'Blocked', pid: '1003', color: Colors.orange),
        ],
      ),
    );
  }
}

class _TaskEntry extends StatelessWidget {
  final String name;
  final String status;
  final String pid;
  final Color color;
  const _TaskEntry({
    required this.name,
    required this.status,
    required this.pid,
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
          child: Text(pid, style: GoogleFonts.firaCode(fontSize: 9, color: color, fontWeight: FontWeight.bold)),
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

// ── Tab: Path Guard ──────────────────────────────────────────────
class _PathGuardTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Path Guard',
            body: 'Path traversal protection and validation.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Status', value: 'Active'),
          _InfoRow(label: 'Mode', value: 'Strict'),
          _InfoRow(label: 'Protected Paths', value: '/etc, /lib, /bin'),
          _InfoRow(label: 'Violations', value: '0'),
        ],
      ),
    );
  }
}

// ── Tab: UDMF ────────────────────────────────────────────────────
class _UdmfTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'UDMF',
            body: 'Unified Data Management Framework.',
          ),
          const SizedBox(height: 16),
          _UdmfEntry(name: 'UTDRegistry', type: 'Registry', status: 'Active', color: Colors.green),
          _UdmfEntry(name: 'UniformTypeDescriptor', type: 'Descriptor', status: 'Active', color: Colors.green),
          _UdmfEntry(name: 'UnifiedData', type: 'Data', status: 'Active', color: Colors.green),
          _UdmfEntry(name: 'DataRepresentation', type: 'Representation', status: 'Active', color: Colors.green),
        ],
      ),
    );
  }
}

class _UdmfEntry extends StatelessWidget {
  final String name;
  final String type;
  final String status;
  final Color color;
  const _UdmfEntry({
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
        leading: Icon(Icons.data_object, color: color, size: 20),
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