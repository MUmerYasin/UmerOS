/// UmerOS Packages Manager — Package Management (.umerpkg)
///
/// Desktop control panel for the UmerOS package manager.
/// Manages installed packages, registry, search, build, and trust keys.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../widgets/auto_adjust_box.dart';

class PackagesManagerApp extends StatefulWidget {
  const PackagesManagerApp({super.key});

  @override
  State<PackagesManagerApp> createState() => _PackagesManagerAppState();
}

class _PackagesManagerAppState extends State<PackagesManagerApp> {
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
              _Tab('Installed', 0, Icons.inventory_2),
              _Tab('Registry', 1, Icons.store),
              _Tab('Search', 2, Icons.search),
              _Tab('Build', 3, Icons.build),
              _Tab('Trust Keys', 4, Icons.verified_user),
              _Tab('Stats', 5, Icons.bar_chart),
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
        return _InstalledTab();
      case 1:
        return _RegistryTab();
      case 2:
        return _SearchTab();
      case 3:
        return _BuildTab();
      case 4:
        return _TrustKeysTab();
      case 5:
        return _StatsTab();
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

// ── Tab: Installed ───────────────────────────────────────────────
class _InstalledTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Installed Packages',
            body: 'Packages currently installed on this system.',
          ),
          const SizedBox(height: 16),
          _PackageEntry(name: 'umer-core', version: '2.0.0', status: 'Installed', color: Colors.green),
          _PackageEntry(name: 'umer-quantum', version: '1.2.0', status: 'Installed', color: Colors.green),
          _PackageEntry(name: 'umer-ai', version: '1.0.0', status: 'Installed', color: Colors.green),
          _PackageEntry(name: 'python-stdlib', version: '3.12.0', status: 'Installed', color: Colors.green),
          _PackageEntry(name: 'numpy', version: '1.26.4', status: 'Installed', color: Colors.green),
        ],
      ),
    );
  }
}

class _PackageEntry extends StatelessWidget {
  final String name;
  final String version;
  final String status;
  final Color color;
  const _PackageEntry({
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

// ── Tab: Registry ────────────────────────────────────────────────
class _RegistryTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Package Registry',
            body: 'Available packages in the local registry.',
          ),
          const SizedBox(height: 16),
          _RegistryEntry(name: 'umer-core', version: '2.0.0', description: 'Core OS libraries and utilities', size: '2048 KB', deps: []),
          _RegistryEntry(name: 'umer-quantum', version: '1.2.0', description: 'Quantum simulation toolkit', size: '4096 KB', deps: ['umer-core']),
          _RegistryEntry(name: 'umer-ai', version: '1.0.0', description: 'AI assistant and resource predictor', size: '8192 KB', deps: ['umer-core']),
          _RegistryEntry(name: 'umer-crypto', version: '1.1.0', description: 'Post-quantum cryptography engine', size: '1024 KB', deps: ['umer-core']),
          _RegistryEntry(name: 'umer-net', version: '1.0.0', description: 'Networking stack (TCP, DNS, HTTP, VPN)', size: '1536 KB', deps: ['umer-core']),
          _RegistryEntry(name: 'umer-ui', version: '1.0.0', description: 'Fluidic Shell and theme engine', size: '512 KB', deps: ['umer-core']),
          _RegistryEntry(name: 'vim', version: '9.1.0', description: 'Terminal text editor', size: '4096 KB', deps: []),
          _RegistryEntry(name: 'htop', version: '3.3.0', description: 'Interactive process viewer', size: '256 KB', deps: []),
          _RegistryEntry(name: 'git', version: '2.45.0', description: 'Distributed version control', size: '8192 KB', deps: []),
          _RegistryEntry(name: 'gcc', version: '14.1.0', description: 'GNU C/C++ compiler', size: '32768 KB', deps: []),
        ],
      ),
    );
  }
}

class _RegistryEntry extends StatelessWidget {
  final String name;
  final String version;
  final String description;
  final String size;
  final List<String> deps;
  const _RegistryEntry({
    required this.name,
    required this.version,
    required this.description,
    required this.size,
    required this.deps,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.extension, color: Colors.blue, size: 18),
                const SizedBox(width: 8),
                Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: scheme.primaryContainer,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(version, style: GoogleFonts.firaCode(fontSize: 10, color: scheme.onPrimaryContainer)),
                ),
                const Spacer(),
                Text(size, style: GoogleFonts.inter(fontSize: 11, color: Colors.grey.shade600)),
              ],
            ),
            const SizedBox(height: 4),
            Text(description, style: GoogleFonts.inter(fontSize: 11, color: Colors.grey.shade700)),
            if (deps.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Deps: ${deps.join(", ")}', style: GoogleFonts.inter(fontSize: 10, color: Colors.grey.shade500)),
            ],
          ],
        ),
      ),
    );
  }
}

// ── Tab: Search ──────────────────────────────────────────────────
class _SearchTab extends StatefulWidget {
  @override
  State<_SearchTab> createState() => _SearchTabState();
}

class _SearchTabState extends State<_SearchTab> {
  final _controller = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Search Packages',
            body: 'Search for packages by name or description.',
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _controller,
            decoration: InputDecoration(
              labelText: 'Search query',
              hintText: 'e.g. quantum, vim, network',
              prefixIcon: const Icon(Icons.search),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onChanged: (v) => setState(() => _query = v),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: _query.isEmpty
                ? Center(child: Text('Enter a search term', style: GoogleFonts.inter(color: Colors.grey)))
                : ListView(
                    children: [
                      if (_query.toLowerCase().contains('quantum'))
                        _RegistryEntry(name: 'umer-quantum', version: '1.2.0', description: 'Quantum simulation toolkit', size: '4096 KB', deps: ['umer-core']),
                      if (_query.toLowerCase().contains('vim'))
                        _RegistryEntry(name: 'vim', version: '9.1.0', description: 'Terminal text editor', size: '4096 KB', deps: []),
                      if (_query.toLowerCase().contains('git'))
                        _RegistryEntry(name: 'git', version: '2.45.0', description: 'Distributed version control', size: '8192 KB', deps: []),
                      if (_query.toLowerCase().contains('net'))
                        _RegistryEntry(name: 'umer-net', version: '1.0.0', description: 'Networking stack (TCP, DNS, HTTP, VPN)', size: '1536 KB', deps: ['umer-core']),
                      if (_query.toLowerCase().contains('core'))
                        _RegistryEntry(name: 'umer-core', version: '2.0.0', description: 'Core OS libraries and utilities', size: '2048 KB', deps: []),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

// ── Tab: Build ───────────────────────────────────────────────────
class _BuildTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Build Package',
            body: 'Create a new .umerpkg archive from a source directory.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Source Directory', value: '/home/umer/myapp'),
          _InfoRow(label: 'Output', value: '/tmp/myapp-1.0.0.umerpkg'),
          _InfoRow(label: 'Manifest', value: 'manifest.json'),
          _InfoRow(label: 'Format', value: '.umerpkg (tar.gz)'),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: () {},
            icon: const Icon(Icons.build),
            label: const Text('Build Package'),
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

// ── Tab: Trust Keys ──────────────────────────────────────────────
class _TrustKeysTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Trusted Signing Keys',
            body: 'Ed25519 public keys trusted for package signing.',
          ),
          const SizedBox(height: 16),
          _TrustKeyEntry(name: 'umer-release', algo: 'Ed25519', status: 'Trusted', color: Colors.green),
          _TrustKeyEntry(name: 'umer-test-dev', algo: 'Ed25519', status: 'Trusted', color: Colors.green),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.add),
            label: const Text('Pin New Key'),
          ),
        ],
      ),
    );
  }
}

class _TrustKeyEntry extends StatelessWidget {
  final String name;
  final String algo;
  final String status;
  final Color color;
  const _TrustKeyEntry({
    required this.name,
    required this.algo,
    required this.status,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.key, color: color, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('Algorithm: $algo', style: GoogleFonts.inter(fontSize: 11)),
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

// ── Tab: Stats ───────────────────────────────────────────────────
class _StatsTab extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: 'Package Statistics',
            body: 'Overview of package management state.',
          ),
          const SizedBox(height: 16),
          _InfoRow(label: 'Installed Packages', value: '5'),
          _InfoRow(label: 'Registry Packages', value: '16'),
          _InfoRow(label: 'Trust Keys', value: '2'),
          _InfoRow(label: 'Install Dir', value: '~/.umer/packages'),
          _InfoRow(label: 'Registry Dir', value: '~/.umer/registry'),
          _InfoRow(label: 'Cache Dir', value: '~/.umer/cache'),
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