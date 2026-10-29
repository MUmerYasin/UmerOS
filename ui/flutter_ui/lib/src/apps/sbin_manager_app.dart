/// UmerOS /sbin Manager — System Administration Binaries
///
/// Desktop control panel for the UmerOS /sbin subsystem.
/// Manages boot, filesystem, modules, network, system, mount, and maintenance.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class SbinManagerApp extends StatefulWidget {
  const SbinManagerApp({super.key});

  @override
  State<SbinManagerApp> createState() => _SbinManagerAppState();
}

class _SbinManagerAppState extends State<SbinManagerApp> {
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
              _Tab('Boot', 0, Icons.power_settings_new),
              _Tab('Filesystem', 1, Icons.storage),
              _Tab('Modules', 2, Icons.extension),
              _Tab('Network', 3, Icons.network_check),
              _Tab('System', 4, Icons.settings),
              _Tab('Mount', 5, Icons.storage),
              _Tab('Maintenance', 6, Icons.build),
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
        return _BootTab();
      case 1:
        return _FilesystemTab();
      case 2:
        return _ModulesTab();
      case 3:
        return _NetworkTab();
      case 4:
        return _SystemTab();
      case 5:
        return _MountTab();
      case 6:
        return _MaintenanceTab();
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

// ── Tab: Boot ────────────────────────────────────────────
class _BootTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Boot Commands',
            body: 'System boot, shutdown, and power management commands.',
          ),
          const SizedBox(height: 16),
          _CmdEntry(name: 'reboot', description: 'Reboot the system', icon: Icons.restart_alt, color: Colors.orange),
          _CmdEntry(name: 'shutdown', description: 'Shutdown the system', icon: Icons.power_settings_new, color: Colors.red),
          _CmdEntry(name: 'halt', description: 'Halt the system', icon: Icons.stop, color: Colors.red),
          _CmdEntry(name: 'poweroff', description: 'Power off the system', icon: Icons.power_off, color: Colors.red),
          _CmdEntry(name: 'init', description: 'Initialize system (runlevel)', icon: Icons.play_arrow, color: Colors.green),
          _CmdEntry(name: 'fastboot', description: 'Fast boot (skip fsck)', icon: Icons.speed, color: Colors.blue),
          _CmdEntry(name: 'update', description: 'Update system packages', icon: Icons.system_update, color: Colors.purple),
        ],
      ),
    );
  }
}

// ── Tab: Filesystem ──────────────────────────────────────
class _FilesystemTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Filesystem Commands',
            body: 'Disk partitioning, filesystem creation, and repair.',
          ),
          const SizedBox(height: 16),
          _CmdEntry(name: 'fdisk', description: 'Partition table manipulator', icon: Icons.storage, color: Colors.blue),
          _CmdEntry(name: 'fsck', description: 'Filesystem consistency check', icon: Icons.check_circle, color: Colors.green),
          _CmdEntry(name: 'mkfs', description: 'Create a filesystem', icon: Icons.add_circle, color: Colors.teal),
          _CmdEntry(name: 'mkswap', description: 'Set up swap area', icon: Icons.swap_vert, color: Colors.orange),
          _CmdEntry(name: 'swapon', description: 'Enable swap', icon: Icons.toggle_on, color: Colors.green),
          _CmdEntry(name: 'swapoff', description: 'Disable swap', icon: Icons.toggle_off, color: Colors.red),
          _CmdEntry(name: 'chroot', description: 'Change root directory', icon: Icons.folder, color: Colors.purple),
        ],
      ),
    );
  }
}

// ── Tab: Modules ─────────────────────────────────────────
class _ModulesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Kernel Module Management',
            body: 'Load, unload, and manage kernel modules.',
          ),
          const SizedBox(height: 16),
          _CmdEntry(name: 'insmod', description: 'Insert a kernel module', icon: Icons.add, color: Colors.green),
          _CmdEntry(name: 'rmmod', description: 'Remove a kernel module', icon: Icons.remove, color: Colors.red),
          _CmdEntry(name: 'modprobe', description: 'Add/remove modules with dependencies', icon: Icons.extension, color: Colors.blue),
          _CmdEntry(name: 'lsmod', description: 'List loaded modules', icon: Icons.list, color: Colors.teal),
          _CmdEntry(name: 'depmod', description: 'Generate module dependency list', icon: Icons.account_tree, color: Colors.purple),
        ],
      ),
    );
  }
}

// ── Tab: Network ─────────────────────────────────────────
class _NetworkTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Network Configuration',
            body: 'Network interface and routing management.',
          ),
          const SizedBox(height: 16),
          _CmdEntry(name: 'ifconfig', description: 'Configure network interfaces', icon: Icons.settings_ethernet, color: Colors.blue),
          _CmdEntry(name: 'ip', description: 'Show/manipulate routing, devices', icon: Icons.route, color: Colors.green),
          _CmdEntry(name: 'route', description: 'Show/manipulate IP routing table', icon: Icons.alt_route, color: Colors.orange),
        ],
      ),
    );
  }
}

// ── Tab: System ──────────────────────────────────────────
class _SystemTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'System Administration',
            body: 'System configuration and hardware clock management.',
          ),
          const SizedBox(height: 16),
          _CmdEntry(name: 'sysctl', description: 'Configure kernel parameters at runtime', icon: Icons.tune, color: Colors.blue),
          _CmdEntry(name: 'hwclock', description: 'Query/set hardware clock', icon: Icons.access_time, color: Colors.green),
          _CmdEntry(name: 'ldconfig', description: 'Configure dynamic linker', icon: Icons.link, color: Colors.orange),
        ],
      ),
    );
  }
}

// ── Tab: Mount ───────────────────────────────────────────
class _MountTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Mount & Device Management',
            body: 'Filesystem mounting and device node management.',
          ),
          const SizedBox(height: 16),
          _CmdEntry(name: 'mount', description: 'Mount a filesystem', icon: Icons.storage, color: Colors.green),
          _CmdEntry(name: 'umount', description: 'Unmount a filesystem', icon: Icons.eject, color: Colors.red),
          _CmdEntry(name: 'mknod', description: 'Create device node', icon: Icons.add_circle, color: Colors.blue),
          _CmdEntry(name: 'losetup', description: 'Set up loop device', icon: Icons.loop, color: Colors.orange),
          _CmdEntry(name: 'pivot_root', description: 'Change root filesystem', icon: Icons.swap_horiz, color: Colors.purple),
        ],
      ),
    );
  }
}

// ── Tab: Maintenance ─────────────────────────────────────
class _MaintenanceTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'System Maintenance',
            body: 'Filesystem repair, backup/restore, and system tools.',
          ),
          const SizedBox(height: 16),
          _CmdEntry(name: 'tune2fs', description: 'Adjust ext filesystem parameters', icon: Icons.tune, color: Colors.blue),
          _CmdEntry(name: 'e2fsck', description: 'Check ext filesystem', icon: Icons.check_circle, color: Colors.green),
          _CmdEntry(name: 'mke2fs', description: 'Create ext filesystem', icon: Icons.add_circle, color: Colors.teal),
          _CmdEntry(name: 'ctrlaltdel', description: 'Set Ctrl+Alt+Del behavior', icon: Icons.keyboard, color: Colors.orange),
          _CmdEntry(name: 'kbdrate', description: 'Set keyboard repeat rate', icon: Icons.speed, color: Colors.purple),
          _CmdEntry(name: 'loadkeys', description: 'Load keyboard translation tables', icon: Icons.keyboard, color: Colors.brown),
          _CmdEntry(name: 'dump', description: 'Backup filesystem', icon: Icons.backup, color: Colors.indigo),
          _CmdEntry(name: 'restore', description: 'Restore filesystem', icon: Icons.restore, color: Colors.indigo),
          _CmdEntry(name: 'sln', description: 'Create symbolic link', icon: Icons.link, color: Colors.teal),
          _CmdEntry(name: 'mktemp', description: 'Create temporary file', icon: Icons.insert_drive_file, color: Colors.amber),
          _CmdEntry(name: 'rdev', description: 'Query/set device info', icon: Icons.info, color: Colors.grey),
        ],
      ),
    );
  }
}

// ── Shared widgets ───────────────────────────────────────
class _CmdEntry extends StatelessWidget {
  final String name;
  final String description;
  final IconData icon;
  final Color color;
  const _CmdEntry({
    required this.name,
    required this.description,
    required this.icon,
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
          child: Icon(icon, color: color, size: 18),
        ),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text(description, style: GoogleFonts.inter(fontSize: 12)),
        trailing: FilledButton.tonal(
          onPressed: () {},
          child: const Text('Run', style: TextStyle(fontSize: 12)),
        ),
      ),
    );
  }
}

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