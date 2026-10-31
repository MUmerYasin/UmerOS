/// UmerOS Drivers Manager — Kernel Driver Management
///
/// Desktop control panel for the UmerOS driver subsystem.
/// Covers all 75 driver modules.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class DriversManagerApp extends StatefulWidget {
  const DriversManagerApp({super.key});

  @override
  State<DriversManagerApp> createState() => _DriversManagerAppState();
}

class _DriversManagerAppState extends State<DriversManagerApp> {
  int _tab = 0;
  String _search = '';

  final List<_DriverCategory> _categories = [
    _DriverCategory('Core', Icons.settings, [
      'bus', 'char_device_base', 'component', 'device', 'device_io',
      'device_link', 'device_registry', 'device_tree', 'devres',
      'platform_driver', 'resource_manager', 'driver_service',
    ]),
    _DriverCategory('Storage', Icons.storage, [
      'ata', 'nvme', 'scsi', 'mtd', 'nvmem', 'dmabuf',
    ]),
    _DriverCategory('Network', Icons.lan, [
      'pci', 'pci_endpoint', 'usb', 'virtio', 'rpmsg', 'remoteproc',
    ]),
    _DriverCategory('Input', Icons.keyboard, [
      'input', 'gpio', 'pinctrl', 'led', 'backlight', 'rfkill',
    ]),
    _DriverCategory('Display', Icons.display_settings, [
      'framebuffer', 'console', 'tty', 'wmi',
    ]),
    _DriverCategory('Power', Icons.battery_charging_full, [
      'acpi', 'clock', 'cpuidle', 'cpuidle_driver_advanced',
      'cpuidle_governor', 'cpuidle_governor_advanced',
      'devfreq', 'power_manager', 'pwrseq', 'regulator', 'thermal',
    ]),
    _DriverCategory('I/O', Icons.cable, [
      'i2c', 'spi', 'hsi', 'interconnect', 'ntb', 'soundwire',
      'pwm', 'counter', 'ptp', 'dmaengine', 'irq', 'reset',
    ]),
    _DriverCategory('Sensors', Icons.sensors, [
      'iio', 'extcon', 'phy', 'rtc', 'edac', 'ipmi', 'tee',
    ]),
    _DriverCategory('Media', Icons.perm_media, [
      'media', 'soundwire', 'fpga', 'nfc',
    ]),
    _DriverCategory('Crypto', Icons.lock, [
      'crypto', 'tee',
    ]),
    _DriverCategory('Firmware', Icons.memory, [
      'firmware', 'mailbox',
    ]),
    _DriverCategory('Examples', Icons.code, [
      'example_driver', 'example_cpuidle_driver', 'example_ioctl_driver',
      'gpu_platform_driver', 'hello_char_driver', 'platform_driver',
    ]),
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final filtered = _search.isEmpty
        ? _categories
        : _categories
            .map((c) => _DriverCategory(
                  c.name,
                  c.icon,
                  c.drivers.where((d) => d.toLowerCase().contains(_search.toLowerCase())).toList(),
                ))
            .where((c) => c.drivers.isNotEmpty)
            .toList();

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            decoration: InputDecoration(
              labelText: 'Search drivers',
              hintText: 'e.g. usb, nvme, gpio',
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
                count: c.drivers.length,
              )).toList(),
            ),
          ),
        ),
        Expanded(
          child: filtered.isEmpty
              ? Center(child: Text('No drivers found', style: GoogleFonts.inter(color: Colors.grey)))
              : _buildContent(filtered[_tab.clamp(0, filtered.length - 1)]),
        ),
      ],
    );
  }

  Widget _buildContent(_DriverCategory category) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: category.name,
            body: '${category.drivers.length} driver modules.',
          ),
          const SizedBox(height: 16),
          ...category.drivers.map((d) => _DriverEntry(name: d)),
        ],
      ),
    );
  }
}

class _DriverCategory {
  final String name;
  final IconData icon;
  final List<String> drivers;
  const _DriverCategory(this.name, this.icon, this.drivers);
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

class _DriverEntry extends StatelessWidget {
  final String name;
  const _DriverEntry({required this.name});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.extension, color: Colors.blue, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('/drivers/$name.py', style: GoogleFonts.inter(fontSize: 11)),
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