/// UmerOS /dev Manager — Device File Management
///
/// Desktop control panel for the UmerOS /dev subsystem.
/// Covers all device modules.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class DevManagerApp extends StatefulWidget {
  const DevManagerApp({super.key});

  @override
  State<DevManagerApp> createState() => _DevManagerAppState();
}

class _DevManagerAppState extends State<DevManagerApp> {
  int _tab = 0;
  String _search = '';

  final List<_DevCategory> _categories = [
    _DevCategory('Core', Icons.settings, [
      'core', 'devtmpfs', 'makedev', 'mknod_virtual', 'udevadm',
      'udev_modern', 'ioctl_codec', 'io_subsystems', 'kmsg_rtc',
    ]),
    _DevCategory('Char Devices', Icons.description, [
      'null_device', 'zero_device', 'random_device', 'full_device',
      'tty_device', 'ptmx_device', 'fd_device', 'pts_device',
      'shm_device', 'log_device', 'mqueue_device', 'hugepages_device',
      'char_devices', 'fuse_device', 'i2c_devices',
    ]),
    _DevCategory('Block Devices', Icons.storage, [
      'block_devices', 'disk_device', 'loop_control', 'losetup',
      'mapper_device', 'media_device', 'nvme_devices', 'scsi_devices',
      'virtual_devices', 'virtualization_devices',
    ]),
    _DevCategory('Input', Icons.keyboard, [
      'input_device', 'hidraw_device', 'uinput_device',
    ]),
    _DevCategory('Display', Icons.display_settings, [
      'dri_device', 'framebuffer_device', 'console',
    ]),
    _DevCategory('Network', Icons.lan, [
      'net_device', 'ptp',
    ]),
    _DevCategory('USB', Icons.usb, [
      'usb_device', 'usb_serial_device',
    ]),
    _DevCategory('Audio', Icons.volume_up, [
      'snd_device',
    ]),
    _DevCategory('Memory', Icons.memory, [
      'memory_devices',
    ]),
    _DevCategory('Misc', Icons.miscellaneous_services, [
      'misc_char_devices', 'misc_system_devices', 'modern_devices',
      'virtualization_devices', 'parallel_device', 'media_device',
    ]),
    _DevCategory('System', Icons.computer, [
      'block_devices', 'char_devices', 'devtmpfs', 'makedev',
      'udevadm', 'udev_modern', 'modern_devices', 'io_subsystems',
      'kmsg_rtc', 'mknod_virtual', 'ioctl_codec',
    ]),
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final filtered = _search.isEmpty
        ? _categories
        : _categories
            .map((c) => _DevCategory(
                  c.name,
                  c.icon,
                  c.devices.where((d) => d.toLowerCase().contains(_search.toLowerCase())).toList(),
                ))
            .where((c) => c.devices.isNotEmpty)
            .toList();

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            decoration: InputDecoration(
              labelText: 'Search devices',
              hintText: 'e.g. usb, nvme, tty',
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
                count: c.devices.length,
              )).toList(),
            ),
          ),
        ),
        Expanded(
          child: filtered.isEmpty
              ? Center(child: Text('No devices found', style: GoogleFonts.inter(color: Colors.grey)))
              : _buildContent(filtered[_tab.clamp(0, filtered.length - 1)]),
        ),
      ],
    );
  }

  Widget _buildContent(_DevCategory category) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: category.name,
            body: '${category.devices.length} device modules.',
          ),
          const SizedBox(height: 16),
          ...category.devices.map((d) => _DeviceEntry(name: d)),
        ],
      ),
    );
  }
}

class _DevCategory {
  final String name;
  final IconData icon;
  final List<String> devices;
  const _DevCategory(this.name, this.icon, this.devices);
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

class _DeviceEntry extends StatelessWidget {
  final String name;
  const _DeviceEntry({required this.name});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.devices, color: Colors.blue, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('/dev/$name', style: GoogleFonts.inter(fontSize: 11)),
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