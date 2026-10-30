/// UmerOS /opt Manager — Add-on Software Package Management
///
/// Desktop control panel for the UmerOS /opt subsystem.
/// Manages installed packages, FHS validation, environment, services.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class OptManagerApp extends StatefulWidget {
  const OptManagerApp({super.key});

  @override
  State<OptManagerApp> createState() => _OptManagerAppState();
}

class _OptManagerAppState extends State<OptManagerApp> {
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
              _Tab('Packages', 0, Icons.inventory_2),
              _Tab('FHS', 1, Icons.folder_special),
              _Tab('Environment', 2, Icons.terminal),
              _Tab('Config', 3, Icons.settings),
              _Tab('Services', 4, Icons.miscellaneous_services),
              _Tab('Var Data', 5, Icons.storage),
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
        return _PackagesTab();
      case 1:
        return _FhsTab();
      case 2:
        return _EnvironmentTab();
      case 3:
        return _ConfigTab();
      case 4:
        return _ServicesTab();
      case 5:
        return _VarDataTab();
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

// ── Tab: Packages ────────────────────────────────────────────────
class _PackagesTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Installed /opt Packages',
            body: 'Add-on software packages installed under /opt.',
          ),
          const SizedBox(height: 16),
          _OptPackageEntry(name: 'vim', provider: 'vim', version: '9.1.0', status: 'Installed', color: Colors.green),
          _OptPackageEntry(name: 'htop', provider: 'htop', version: '3.3.0', status: 'Installed', color: Colors.green),
          _OptPackageEntry(name: 'git', provider: 'git', version: '2.45.0', status: 'Installed', color: Colors.green),
          _OptPackageEntry(name: 'sample-app', provider: 'umer', version: '1.0.0', status: 'Installed', color: Colors.blue),
        ],
      ),
    );
  }
}

class _OptPackageEntry extends StatelessWidget {
  final String name;
  final String provider;
  final String version;
  final String status;
  final Color color;
  const _OptPackageEntry({
    required this.name,
    required this.provider,
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
        subtitle: Text('Provider: $provider · Version: $version', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: FHS ─────────────────────────────────────────────────────
class _FhsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'FHS Validation',
            body: 'Filesystem Hierarchy Standard compliance check for /opt.',
          ),
          const SizedBox(height: 16),
          _FhsEntry(path: '/opt', status: 'OK', color: Colors.green),
          _FhsEntry(path: '/opt/bin', status: 'OK', color: Colors.green),
          _FhsEntry(path: '/opt/lib', status: 'OK', color: Colors.green),
          _FhsEntry(path: '/opt/include', status: 'OK', color: Colors.green),
          _FhsEntry(path: '/opt/share', status: 'OK', color: Colors.green),
          _FhsEntry(path: '/etc/opt', status: 'OK', color: Colors.green),
          _FhsEntry(path: '/var/opt', status: 'OK', color: Colors.green),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.check_circle),
            label: const Text('Run FHS Check'),
          ),
        ],
      ),
    );
  }
}

class _FhsEntry extends StatelessWidget {
  final String path;
  final String status;
  final Color color;
  const _FhsEntry({required this.path, required this.status, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.folder, color: color, size: 20),
        title: Text(path, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
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

// ── Tab: Environment ─────────────────────────────────────────────
class _EnvironmentTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Environment Variables',
            body: 'PATH, MANPATH, LD_LIBRARY_PATH exports from /opt.',
          ),
          const SizedBox(height: 16),
          _EnvEntry(varName: 'PATH', value: '/opt/bin:/opt/vim/bin:/opt/git/bin'),
          _EnvEntry(varName: 'MANPATH', value: '/opt/share/man:/opt/vim/share/man'),
          _EnvEntry(varName: 'LD_LIBRARY_PATH', value: '/opt/lib:/opt/vim/lib'),
          _EnvEntry(varName: 'INCLUDE_DIRS', value: '/opt/include:/opt/vim/include'),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.refresh),
            label: const Text('Regenerate Exports'),
          ),
        ],
      ),
    );
  }
}

class _EnvEntry extends StatelessWidget {
  final String varName;
  final String value;
  const _EnvEntry({required this.varName, required this.value});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        title: Text(varName, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(value, style: GoogleFonts.inter(fontSize: 11)),
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
            title: 'Package Configuration',
            body: 'Host-specific configuration files in /etc/opt.',
          ),
          const SizedBox(height: 16),
          _ConfigEntry(pkg: 'vim', config: 'vimrc', path: '/etc/opt/vim/vimrc'),
          _ConfigEntry(pkg: 'git', config: 'gitconfig', path: '/etc/opt/git/gitconfig'),
          _ConfigEntry(pkg: 'sample-app', config: 'app.conf', path: '/etc/opt/umer/sample-app/app.conf'),
        ],
      ),
    );
  }
}

class _ConfigEntry extends StatelessWidget {
  final String pkg;
  final String config;
  final String path;
  const _ConfigEntry({required this.pkg, required this.config, required this.path});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.settings, color: Colors.blue, size: 20),
        title: Text('$pkg / $config', style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(path, style: GoogleFonts.inter(fontSize: 11)),
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
            title: 'Service Management',
            body: 'Registered services from /opt packages.',
          ),
          const SizedBox(height: 16),
          _ServiceEntry(name: 'sample-app', status: 'Running', color: Colors.green),
          _ServiceEntry(name: 'vim-server', status: 'Stopped', color: Colors.grey),
        ],
      ),
    );
  }
}

class _ServiceEntry extends StatelessWidget {
  final String name;
  final String status;
  final Color color;
  const _ServiceEntry({required this.name, required this.status, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.miscellaneous_services, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
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

// ── Tab: Var Data ────────────────────────────────────────────────
class _VarDataTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Variable Data (/var/opt)',
            body: 'Per-package variable data storage.',
          ),
          const SizedBox(height: 16),
          _VarDataEntry(pkg: 'vim', path: '/var/opt/vim', size: '2.4 MB'),
          _VarDataEntry(pkg: 'git', path: '/var/opt/git', size: '1.2 MB'),
          _VarDataEntry(pkg: 'sample-app', path: '/var/opt/umer/sample-app', size: '0.5 MB'),
        ],
      ),
    );
  }
}

class _VarDataEntry extends StatelessWidget {
  final String pkg;
  final String path;
  final String size;
  const _VarDataEntry({required this.pkg, required this.path, required this.size});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.folder, color: Colors.teal, size: 20),
        title: Text(pkg, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text(path, style: GoogleFonts.inter(fontSize: 11)),
        trailing: Text(size, style: GoogleFonts.inter(fontSize: 11, color: Colors.grey.shade600)),
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