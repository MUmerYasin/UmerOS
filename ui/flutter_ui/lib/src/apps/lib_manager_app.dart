/// UmerOS /lib Manager — Shared Libraries & Kernel Modules
///
/// Desktop control panel for the UmerOS /lib subsystem.
/// Manages shared libraries, kernel modules, dynamic linker, SSL, etc.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class LibManagerApp extends StatefulWidget {
  const LibManagerApp({super.key});

  @override
  State<LibManagerApp> createState() => _LibManagerAppState();
}

class _LibManagerAppState extends State<LibManagerApp> {
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
              _Tab('Libraries', 0, Icons.library_books),
              _Tab('Modules', 1, Icons.extension),
              _Tab('Linker', 2, Icons.link),
              _Tab('SSL/TLS', 3, Icons.lock),
              _Tab('Firmware', 4, Icons.memory),
              _Tab('Summary', 5, Icons.bar_chart),
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
        return _LibrariesTab();
      case 1:
        return _ModulesTab();
      case 2:
        return _LinkerTab();
      case 3:
        return _SslTab();
      case 4:
        return _FirmwareTab();
      case 5:
        return _SummaryTab();
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

// ── Tab: Libraries ───────────────────────────────────────────────
class _LibrariesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Shared Libraries',
            body: 'Essential shared libraries in /lib.',
          ),
          const SizedBox(height: 16),
          _LibEntry(name: 'libc.so.6', version: '2.38', status: 'OK', color: Colors.green),
          _LibEntry(name: 'libm.so.6', version: '2.38', status: 'OK', color: Colors.green),
          _LibEntry(name: 'libdl.so.2', version: '2.38', status: 'OK', color: Colors.green),
          _LibEntry(name: 'libpthread.so.0', version: '2.38', status: 'OK', color: Colors.green),
          _LibEntry(name: 'librt.so.1', version: '2.38', status: 'OK', color: Colors.green),
          _LibEntry(name: 'ld-linux-x86-64.so.2', version: '2.38', status: 'OK', color: Colors.green),
          _LibEntry(name: 'libssl.so.3', version: '3.0.13', status: 'OK', color: Colors.blue),
          _LibEntry(name: 'libcrypto.so.3', version: '3.0.13', status: 'OK', color: Colors.blue),
        ],
      ),
    );
  }
}

class _LibEntry extends StatelessWidget {
  final String name;
  final String version;
  final String status;
  final Color color;
  const _LibEntry({
    required this.name,
    required this.version,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.library_books, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Version: $version', style: GoogleFonts.inter(fontSize: 11)),
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
            title: 'Kernel Modules',
            body: 'Loaded kernel modules in /lib/modules.',
          ),
          const SizedBox(height: 16),
          _ModuleEntry(name: 'ext4', version: '6.8.0', status: 'Loaded', color: Colors.green),
          _ModuleEntry(name: 'xfs', version: '6.8.0', status: 'Loaded', color: Colors.green),
          _ModuleEntry(name: 'nvidia', version: '550.54', status: 'Loaded', color: Colors.green),
          _ModuleEntry(name: 'bluetooth', version: '6.8.0', status: 'Loaded', color: Colors.blue),
          _ModuleEntry(name: 'usb_storage', version: '6.8.0', status: 'Loaded', color: Colors.blue),
          _ModuleEntry(name: 'nvidia_drm', version: '550.54', status: 'Loaded', color: Colors.green),
        ],
      ),
    );
  }
}

class _ModuleEntry extends StatelessWidget {
  final String name;
  final String version;
  final String status;
  final Color color;
  const _ModuleEntry({
    required this.name,
    required this.version,
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
        subtitle: Text('Kernel: $version', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Linker ──────────────────────────────────────────────────
class _LinkerTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Dynamic Linker',
            body: 'ldconfig, ld.so.conf and ld.so.cache management.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'ld.so.conf', value: '/etc/ld.so.conf'),
          _InfoRow(label: 'ld.so.cache', value: '/etc/ld.so.cache'),
          _InfoRow(label: 'Cache Entries', value: '1,247'),
          _InfoRow(label: 'Library Paths', value: '12'),
          _InfoRow(label: 'Multiarch', value: 'x86_64-linux-gnu'),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.refresh),
            label: const Text('Run ldconfig'),
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

// ── Tab: SSL/TLS ─────────────────────────────────────────────────
class _SslTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'SSL/TLS Certificates',
            body: 'Certificate store and CA bundle management.',
          ),
          const SizedBox(height: 16),
          _SslEntry(name: 'ca-certificates.crt', type: 'CA Bundle', count: '138', status: 'OK', color: Colors.green),
          _SslEntry(name: 'server.crt', type: 'Server Cert', count: '1', status: 'Valid', color: Colors.green),
          _SslEntry(name: 'server.key', type: 'Private Key', count: '1', status: 'OK', color: Colors.blue),
          _SslEntry(name: 'client.crt', type: 'Client Cert', count: '1', status: 'Valid', color: Colors.green),
        ],
      ),
    );
  }
}

class _SslEntry extends StatelessWidget {
  final String name;
  final String type;
  final String count;
  final String status;
  final Color color;
  const _SslEntry({
    required this.name,
    required this.type,
    required this.count,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.lock, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$type · Count: $count', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Firmware ────────────────────────────────────────────────
class _FirmwareTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Firmware Blobs',
            body: 'Firmware files in /lib/firmware.',
          ),
          const SizedBox(height: 16),
          _FirmwareEntry(name: 'iwlwifi-cc-a0-77.ucode', subsystem: 'WiFi', size: '1.2 MB', status: 'Loaded', color: Colors.green),
          _FirmwareEntry(name: 'nvidia/ga102.bin', subsystem: 'GPU', size: '4.5 MB', status: 'Loaded', color: Colors.green),
          _FirmwareEntry(name: 'amd/amdgpu/navi10.bin', subsystem: 'GPU', size: '2.1 MB', status: 'Loaded', color: Colors.green),
          _FirmwareEntry(name: 'intel/ibt-0041-0041.sfi', subsystem: 'Bluetooth', size: '0.8 MB', status: 'Loaded', color: Colors.blue),
        ],
      ),
    );
  }
}

class _FirmwareEntry extends StatelessWidget {
  final String name;
  final String subsystem;
  final String size;
  final String status;
  final Color color;
  const _FirmwareEntry({
    required this.name,
    required this.subsystem,
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
        leading: Icon(Icons.memory, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$subsystem · $size', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Summary ─────────────────────────────────────────────────
class _SummaryTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Library Summary',
            body: 'Overview of /lib subsystem state.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Total Libraries', value: '1,247'),
          _InfoRow(label: 'Kernel Modules', value: '6'),
          _InfoRow(label: 'SSL Certificates', value: '140'),
          _InfoRow(label: 'Firmware Blobs', value: '4'),
          _InfoRow(label: 'Library Paths', value: '12'),
          _InfoRow(label: 'Architecture', value: 'x86_64'),
          _InfoRow(label: 'Multiarch', value: 'x86_64-linux-gnu'),
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