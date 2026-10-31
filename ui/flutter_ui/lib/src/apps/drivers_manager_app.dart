/// UmerOS Drivers Manager — Kernel Driver Management
///
/// Desktop control panel for the UmerOS driver subsystem.
/// Manages hardware drivers, devices, buses, and driver services.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class DriversManagerApp extends StatefulWidget {
  const DriversManagerApp({super.key});

  @override
  State<DriversManagerApp> createState() => _DriversManagerAppState();
}

class _DriversManagerAppState extends State<DriversManagerApp> {
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
              _Tab('Devices', 0, Icons.devices),
              _Tab('Drivers', 1, Icons.extension),
              _Tab('Buses', 2, Icons.cable),
              _Tab('Services', 3, Icons.miscellaneous_services),
              _Tab('Status', 4, Icons.info),
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
        return _DriversTab();
      case 2:
        return _BusesTab();
      case 3:
        return _ServicesTab();
      case 4:
        return _StatusTab();
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
            title: 'Hardware Devices',
            body: 'Detected hardware devices and their drivers.',
          ),
          const SizedBox(height: 16),
          _DeviceEntry(name: 'Intel Wi-Fi 6 AX200', type: 'Network', driver: 'iwlwifi', status: 'Active', color: Colors.green),
          _DeviceEntry(name: 'NVIDIA RTX 4090', type: 'GPU', driver: 'nvidia', status: 'Active', color: Colors.green),
          _DeviceEntry(name: 'Samsung 990 Pro NVMe', type: 'Storage', driver: 'nvme', status: 'Active', color: Colors.green),
          _DeviceEntry(name: 'Realtek Audio', type: 'Audio', driver: 'snd_hda_intel', status: 'Active', color: Colors.green),
          _DeviceEntry(name: 'Logitech Webcam', type: 'USB', driver: 'uvcvideo', status: 'Active', color: Colors.blue),
          _DeviceEntry(name: 'Bluetooth Adapter', type: 'Bluetooth', driver: 'btusb', status: 'Active', color: Colors.blue),
        ],
      ),
    );
  }
}

class _DeviceEntry extends StatelessWidget {
  final String name;
  final String type;
  final String driver;
  final String status;
  final Color color;
  const _DeviceEntry({
    required this.name,
    required this.type,
    required this.driver,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.devices, color: color, size: 20),
        title: Text(name, style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$type · Driver: $driver', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Drivers ─────────────────────────────────────────────────
class _DriversTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Loaded Drivers',
            body: 'Kernel drivers currently loaded.',
          ),
          const SizedBox(height: 16),
          _DriverEntry(name: 'iwlwifi', type: 'Network', version: '6.8.0', status: 'Loaded', color: Colors.green),
          _DriverEntry(name: 'nvidia', type: 'GPU', version: '550.54', status: 'Loaded', color: Colors.green),
          _DriverEntry(name: 'nvme', type: 'Storage', version: '6.8.0', status: 'Loaded', color: Colors.green),
          _DriverEntry(name: 'snd_hda_intel', type: 'Audio', version: '6.8.0', status: 'Loaded', color: Colors.green),
          _DriverEntry(name: 'uvcvideo', type: 'USB', version: '6.8.0', status: 'Loaded', color: Colors.blue),
          _DriverEntry(name: 'btusb', type: 'Bluetooth', version: '6.8.0', status: 'Loaded', color: Colors.blue),
          _DriverEntry(name: 'i2c_hid', type: 'Input', version: '6.8.0', status: 'Loaded', color: Colors.blue),
        ],
      ),
    );
  }
}

class _DriverEntry extends StatelessWidget {
  final String name;
  final String type;
  final String version;
  final String status;
  final Color color;
  const _DriverEntry({
    required this.name,
    required this.type,
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
        subtitle: Text('$type · v$version', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Buses ───────────────────────────────────────────────────
class _BusesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'System Buses',
            body: 'Hardware buses and their devices.',
          ),
          const SizedBox(height: 16),
          _BusEntry(name: 'PCI', devices: '24', status: 'Active', color: Colors.green),
          _BusEntry(name: 'USB', devices: '8', status: 'Active', color: Colors.green),
          _BusEntry(name: 'I2C', devices: '6', status: 'Active', color: Colors.green),
          _BusEntry(name: 'SPI', devices: '4', status: 'Active', color: Colors.green),
          _BusEntry(name: 'GPIO', devices: '32', status: 'Active', color: Colors.blue),
          _BusEntry(name: 'ACPI', devices: '12', status: 'Active', color: Colors.blue),
        ],
      ),
    );
  }
}

class _BusEntry extends StatelessWidget {
  final String name;
  final String devices;
  final String status;
  final Color color;
  const _BusEntry({
    required this.name,
    required this.devices,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.cable, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Devices: $devices', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Services ────────────────────────────────────────────────
class _ServicesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Driver Services',
            body: 'Driver service status and management.',
          ),
          const SizedBox(height: 16),
          _ServiceEntry(name: 'driver_service', status: 'Running', port: '8080', color: Colors.green),
          _ServiceEntry(name: 'hotplug', status: 'Running', port: 'N/A', color: Colors.green),
          _ServiceEntry(name: 'udev', status: 'Running', port: 'N/A', color: Colors.green),
        ],
      ),
    );
  }
}

class _ServiceEntry extends StatelessWidget {
  final String name;
  final String status;
  final String port;
  final Color color;
  const _ServiceEntry({
    required this.name,
    required this.status,
    required this.port,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.miscellaneous_services, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Port: $port', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Status ──────────────────────────────────────────────────
class _StatusTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Driver Status',
            body: 'Overall driver subsystem status.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Total Drivers', value: '82'),
          _InfoRow(label: 'Loaded', value: '7'),
          _InfoRow(label: 'Available', value: '75'),
          _InfoRow(label: 'Failed', value: '0'),
          _InfoRow(label: 'Buses', value: '6'),
          _InfoRow(label: 'Devices', value: '6'),
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