/// UmerOS /etc Manager — System Configuration
///
/// Desktop control panel for the UmerOS /etc subsystem.
/// Manages 81 system configuration files and services.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class EtcManagerApp extends StatefulWidget {
  const EtcManagerApp({super.key});

  @override
  State<EtcManagerApp> createState() => _EtcManagerAppState();
}

class _EtcManagerAppState extends State<EtcManagerApp> {
  int _tab = 0;
  String _search = '';

  final List<_ConfigCategory> _categories = [
    _ConfigCategory('System', Icons.settings, [
      'ConfigManager', 'PasswdGroupManager', 'HostnameManager', 'OSReleaseManager',
      'SkeletonManager', 'EnvironmentManager', 'DefaultConfigManager',
      'InputRCManager', 'ProfileDManager', 'ShellProfileManager',
      'ShellsManager', 'VConsoleManager', 'ManpathConfigManager',
      'AdduserConfigManager', 'ShellConfigManager', 'SysconfigManager',
      'get_config_manager', 'CshZshConfigManager', 'SysctlDManager',
    ]),
    _ConfigCategory('Network', Icons.lan, [
      'NetworkConfigManager', 'NetworksManager', 'NetworkManagerConfigManager',
      'HostsManager', 'HostsAccessManager', 'HostConfManager',
      'DHCPConfigManager', 'NFSExportsManager', 'SambaConfigManager',
      'OpenVPNConfigManager', 'WPASupplicantManager', 'PPPConfigManager',
      'InetServicesManager',
    ]),
    _ConfigCategory('Security', Icons.security, [
      'SecurityConfigManager', 'SudoersManager', 'PAMConfigManager',
      'SSLConfigManager', 'SSLDirsManager', 'SecureTTYManager',
      'HostsAccessManager', 'GSSConfigManager',
    ]),
    _ConfigCategory('Services', Icons.miscellaneous_services, [
      'CronScheduleManager', 'CronDManager', 'CronAccessManager',
      'InitScriptsManager', 'InitSystemManager', 'SyslogConfigManager',
      'LogrotateConfigManager', 'DBusConfigManager',
    ]),
    _ConfigCategory('Hardware', Icons.memory, [
      'HardwareConfigManager', 'LVMConfigManager', 'FontsConfigManager',
      'USBConfigManager', 'ModprobeDManager', 'ModulesLoadManager',
      'ModuleConfigManager', 'KernelConfigManager',
    ]),
    _ConfigCategory('Filesystem', Icons.storage, [
      'FstabManager', 'TmpfilesManager', 'UdevRulesManager',
      'E2fsckConfigManager', 'BinFmtManager',
    ]),
    _ConfigCategory('Desktop', Icons.desktop_windows, [
      'XDGConfigManager', 'X11ExtraManager', 'KDEConfigManager',
    ]),
    _ConfigCategory('Mail & Misc', Icons.mail, [
      'MailConfigManager', 'MailAliasesManager', 'MimeConfigManager',
      'CUPSConfigManager', 'SANEConfigManager', 'ChronyConfigManager',
      'HotplugConfigManager', 'UpdatedbConfigManager', 'GAIConfManager',
      'ConfDManager', 'AlternativesManager', 'CriticalFilesManager',
      'IssueMotdManager', 'LocaleTimezoneManager', 'LoginConfigManager',
      'LoginEnvironmentManager', 'AptConfigManager', 'DpkgConfigManager',
    ]),
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final filtered = _search.isEmpty
        ? _categories
        : _categories
            .map((c) => _ConfigCategory(
                  c.name,
                  c.icon,
                  c.managers.where((m) => m.toLowerCase().contains(_search.toLowerCase())).toList(),
                ))
            .where((c) => c.managers.isNotEmpty)
            .toList();

    return Column(
      children: [
        // Search bar
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            decoration: InputDecoration(
              labelText: 'Search configurations',
              hintText: 'e.g. hostname, ssh, cron',
              prefixIcon: const Icon(Icons.search),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onChanged: (v) => setState(() => _search = v),
          ),
        ),
        // Category tabs
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
                count: c.managers.length,
              )).toList(),
            ),
          ),
        ),
        // Content
        Expanded(
          child: filtered.isEmpty
              ? Center(child: Text('No configurations found', style: GoogleFonts.inter(color: Colors.grey)))
              : _buildContent(filtered[_tab.clamp(0, filtered.length - 1)]),
        ),
      ],
    );
  }

  Widget _buildContent(_ConfigCategory category) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _InfoCard(
            title: category.name,
            body: '${category.managers.length} configuration managers.',
          ),
          const SizedBox(height: 16),
          ...category.managers.map((m) => _ConfigManagerEntry(name: m)),
        ],
      ),
    );
  }
}

class _ConfigCategory {
  final String name;
  final IconData icon;
  final List<String> managers;
  const _ConfigCategory(this.name, this.icon, this.managers);
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

class _ConfigManagerEntry extends StatelessWidget {
  final String name;
  const _ConfigManagerEntry({required this.name});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(Icons.settings, color: Colors.blue, size: 20),
        title: Text(name, style: GoogleFonts.firaCode(fontWeight: FontWeight.w600, fontSize: 12)),
        subtitle: Text('/etc configuration manager', style: GoogleFonts.inter(fontSize: 11)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: Colors.green.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text('Active', style: GoogleFonts.inter(fontSize: 10, color: Colors.green, fontWeight: FontWeight.w600)),
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