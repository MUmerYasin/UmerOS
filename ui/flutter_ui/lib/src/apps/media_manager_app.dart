/// UmerOS /media Manager — Removable Media Management
///
/// Desktop control panel for the UmerOS /media subsystem.
/// Manages removable media, mount points, network shares, auto-mount.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class MediaManagerApp extends StatefulWidget {
  const MediaManagerApp({super.key});

  @override
  State<MediaManagerApp> createState() => _MediaManagerAppState();
}

class _MediaManagerAppState extends State<MediaManagerApp> {
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
              _Tab('Devices', 0, Icons.usb),
              _Tab('Mounts', 1, Icons.storage),
              _Tab('Network', 2, Icons.cloud),
              _Tab('Auto-Mount', 3, Icons.autorenew),
              _Tab('Permissions', 4, Icons.lock),
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
        return _DevicesTab();
      case 1:
        return _MountsTab();
      case 2:
        return _NetworkTab();
      case 3:
        return _AutoMountTab();
      case 4:
        return _PermissionsTab();
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

// ── Tab: Devices ─────────────────────────────────────────────────
class _DevicesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Removable Devices',
            body: 'Detected removable media devices.',
          ),
          const SizedBox(height: 16),
          _DeviceEntry(name: 'USB Drive', device: '/dev/sdb1', fs: 'vfat', size: '32 GB', status: 'Connected', color: Colors.green),
          _DeviceEntry(name: 'SD Card', device: '/dev/mmcblk0p1', fs: 'ext4', size: '64 GB', status: 'Connected', color: Colors.green),
          _DeviceEntry(name: 'CD-ROM', device: '/dev/sr0', fs: 'iso9660', size: '4.7 GB', status: 'Ejected', color: Colors.grey),
          _DeviceEntry(name: 'USB Stick', device: '/dev/sdc1', fs: 'ntfs', size: '16 GB', status: 'Connected', color: Colors.green),
        ],
      ),
    );
  }
}

class _DeviceEntry extends StatelessWidget {
  final String name;
  final String device;
  final String fs;
  final String size;
  final String status;
  final Color color;
  const _DeviceEntry({
    required this.name,
    required this.device,
    required this.fs,
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
        leading: Icon(Icons.usb, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$device · $fs · $size', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Mounts ──────────────────────────────────────────────────
class _MountsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Mounted Media',
            body: 'Currently mounted removable media.',
          ),
          const SizedBox(height: 16),
          _MediaMountEntry(name: 'USB Drive', mount: '/media/usb', fs: 'vfat', status: 'Mounted', color: Colors.green),
          _MediaMountEntry(name: 'SD Card', mount: '/media/sdcard', fs: 'ext4', status: 'Mounted', color: Colors.green),
          _MediaMountEntry(name: 'USB Stick', mount: '/media/usb1', fs: 'ntfs', status: 'Mounted', color: Colors.green),
        ],
      ),
    );
  }
}

class _MediaMountEntry extends StatelessWidget {
  final String name;
  final String mount;
  final String fs;
  final String status;
  final Color color;
  const _MediaMountEntry({
    required this.name,
    required this.mount,
    required this.fs,
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
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$mount · $fs', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Network ─────────────────────────────────────────────────
class _NetworkTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Network Shares',
            body: 'Mounted network shares (SMB, NFS, SSHFS).',
          ),
          const SizedBox(height: 16),
          _NetworkShareEntry(name: 'office_docs', protocol: 'SMB', host: '192.168.1.10', mount: '/media/network/office_docs', status: 'Mounted', color: Colors.green),
          _NetworkShareEntry(name: 'home_nfs', protocol: 'NFS', host: '192.168.1.20', mount: '/media/network/home_nfs', status: 'Mounted', color: Colors.green),
          _NetworkShareEntry(name: 'remote_ssh', protocol: 'SSHFS', host: 'remote.example.com', mount: '/media/network/remote_ssh', status: 'Disconnected', color: Colors.grey),
        ],
      ),
    );
  }
}

class _NetworkShareEntry extends StatelessWidget {
  final String name;
  final String protocol;
  final String host;
  final String mount;
  final String status;
  final Color color;
  const _NetworkShareEntry({
    required this.name,
    required this.protocol,
    required this.host,
    required this.mount,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.cloud, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('$protocol · $host · $mount', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Auto-Mount ──────────────────────────────────────────────
class _AutoMountTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Auto-Mount Daemon',
            body: 'Automatic mounting of removable media on insertion.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Daemon Status', value: 'Running'),
          _InfoRow(label: 'Policy', value: 'Mount on insert'),
          _InfoRow(label: 'Mount Point', value: '/media/<label>'),
          _InfoRow(label: 'Unmount on eject', value: 'Yes'),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.refresh),
            label: const Text('Restart Daemon'),
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

// ── Tab: Permissions ─────────────────────────────────────────────
class _PermissionsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Mount Permissions',
            body: 'User/group access control for removable media.',
          ),
          const SizedBox(height: 16),
          _PermissionEntry(group: 'plugdev', access: 'Read/Write', color: Colors.green),
          _PermissionEntry(group: 'storage', access: 'Read/Write', color: Colors.green),
          _PermissionEntry(group: 'users', access: 'Read Only', color: Colors.blue),
          _PermissionEntry(group: 'others', access: 'No Access', color: Colors.grey),
        ],
      ),
    );
  }
}

class _PermissionEntry extends StatelessWidget {
  final String group;
  final String access;
  final Color color;
  const _PermissionEntry({required this.group, required this.access, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.group, color: color, size: 20),
        title: Text(group, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(access, style: GoogleFonts.inter(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
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