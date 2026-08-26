import 'package:flutter/material.dart';

import '../widgets/auto_adjust_box.dart';

class BootManagerApp extends StatefulWidget {
  const BootManagerApp({super.key});

  @override
  State<BootManagerApp> createState() => _BootManagerAppState();
}

class _BootManagerAppState extends State<BootManagerApp> {
  int _selectedTab = 0;

  // Boot Sequence
  final List<Map<String, dynamic>> _bootStages = [
    {'name': 'BIOS', 'duration': '2.1s', 'status': 'complete', 'icon': Icons.memory},
    {'name': 'Bootloader', 'duration': '0.8s', 'status': 'complete', 'icon': Icons.play_circle},
    {'name': 'Kernel Init', 'duration': '3.4s', 'status': 'complete', 'icon': Icons.code},
    {'name': 'Drivers', 'duration': '1.9s', 'status': 'complete', 'icon': settingsIcon},
    {'name': 'Services', 'duration': '2.7s', 'status': 'complete', 'icon': Icons.apps},
    {'name': 'Desktop', 'duration': '1.2s', 'status': 'complete', 'icon': Icons.desktop_windows},
  ];

  // Services
  final List<Map<String, dynamic>> _services = [
    {'name': 'umerd', 'status': 'running', 'enabled': true, 'desc': 'Core system daemon'},
    {'name': 'quantum-service', 'status': 'running', 'enabled': true, 'desc': 'Quantum computing interface'},
    {'name': 'firewall', 'status': 'running', 'enabled': true, 'desc': 'Network security'},
    {'name': 'network-manager', 'status': 'running', 'enabled': true, 'desc': 'Network configuration'},
    {'name': 'ai-engine', 'status': 'stopped', 'enabled': true, 'desc': 'AI inference engine'},
    {'name': 'package-manager', 'status': 'running', 'enabled': true, 'desc': 'Package installation'},
    {'name': 'security-daemon', 'status': 'running', 'enabled': true, 'desc': 'Security monitoring'},
    {'name': 'display-manager', 'status': 'running', 'enabled': true, 'desc': 'Display configuration'},
    {'name': 'audio-service', 'status': 'stopped', 'enabled': false, 'desc': 'Audio subsystem'},
    {'name': 'bluetooth', 'status': 'stopped', 'enabled': false, 'desc': 'Bluetooth stack'},
  ];

  // Kernel
  final TextEditingController _kernelParamsController = TextEditingController(
    text: 'quiet splash loglevel=3',
  );
  final List<Map<String, dynamic>> _kernelModules = [
    {'name': 'nvidia', 'loaded': true},
    {'name': 'usb_storage', 'loaded': true},
    {'name': 'ext4', 'loaded': true},
    {'name': 'btrfs', 'loaded': false},
    {'name': 'zfs', 'loaded': false},
    {'name': 'vfio_pci', 'loaded': false},
    {'name': 'kvm', 'loaded': true},
    {'name': 'virtio', 'loaded': true},
  ];

  // Recovery
  final List<Map<String, String>> _restorePoints = [
    {'date': '2025-01-15 10:30', 'name': 'Pre-update snapshot', 'size': '2.4 GB'},
    {'date': '2025-01-10 08:15', 'name': 'Clean install baseline', 'size': '1.8 GB'},
    {'date': '2025-01-05 14:45', 'name': 'Post-driver install', 'size': '2.1 GB'},
  ];

  @override
  void initState() {
    super.initState();
  }

  @override
  void dispose() {
    _kernelParamsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildTabBar(),
        Expanded(
          child: _selectedTab == 0
              ? _buildBootSequenceTab()
              : _selectedTab == 1
                  ? _buildServicesTab()
                  : _selectedTab == 2
                      ? _buildKernelTab()
                      : _buildRecoveryTab(),
        ),
        _buildBottomBar(),
      ],
    );
  }

  Widget _buildTabBar() {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
          ),
        ),
      ),
      child: AutoAdjustRow(
        spacing: 0,
        children: [
          _TabButton(label: 'Boot Sequence', isSelected: _selectedTab == 0, onTap: () => setState(() => _selectedTab = 0)),
          _TabButton(label: 'Services', isSelected: _selectedTab == 1, onTap: () => setState(() => _selectedTab = 1)),
          _TabButton(label: 'Kernel', isSelected: _selectedTab == 2, onTap: () => setState(() => _selectedTab = 2)),
          _TabButton(label: 'Recovery', isSelected: _selectedTab == 3, onTap: () => setState(() => _selectedTab = 3)),
        ],
      ),
    );
  }

  // ===================== BOOT SEQUENCE TAB =====================
  Widget _buildBootSequenceTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Boot Sequence',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Total boot time: 12.1s',
            style: TextStyle(
              fontSize: 12,
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
            ),
          ),
          const SizedBox(height: 20),
          // Timeline
          ...List.generate(_bootStages.length, (index) {
            final stage = _bootStages[index];
            final isLast = index == _bootStages.length - 1;
            return _buildBootStage(stage, isLast);
          }),
        ],
      ),
    );
  }

  Widget _buildBootStage(Map<String, dynamic> stage, bool isLast) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Timeline column
          SizedBox(
            width: 40,
            child: Column(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.primaryContainer,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.check,
                    size: 16,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(
                      width: 2,
                      color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.3),
                    ),
                  ),
              ],
            ),
          ),
          // Content
          Expanded(
            child: Container(
              margin: const EdgeInsets.only(left: 8, bottom: 20),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.15),
                ),
              ),
              child: Row(
                children: [
                  Icon(stage['icon'] as IconData, size: 20, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          stage['name'],
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          stage['status'] == 'complete' ? 'Completed' : 'Pending',
                          style: TextStyle(
                            fontSize: 11,
                            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      stage['duration'],
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ===================== SERVICES TAB =====================
  Widget _buildServicesTab() {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2)),
            ),
          ),
          child: Row(
            children: [
              Icon(Icons.apps, size: 16, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              Text(
                'Startup Services (${_services.where((s) => s['status'] == 'running').length}/${_services.length} running)',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
              ),
              const Spacer(),
              FilledButton.tonal(
                onPressed: () {
                  for (final s in _services) {
                    if (s['enabled'] && s['status'] == 'stopped') {
                      setState(() => s['status'] = 'running');
                    }
                  }
                },
                child: const Text('Start All Enabled', style: TextStyle(fontSize: 12)),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(8),
            itemCount: _services.length,
            itemBuilder: (context, index) {
              return _buildServiceTile(_services[index]);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildServiceTile(Map<String, dynamic> service) {
    final isRunning = service['status'] == 'running';
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 3),
      child: ListTile(
        leading: Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: isRunning ? Colors.green : Colors.red.withValues(alpha: 0.7),
            shape: BoxShape.circle,
          ),
        ),
        title: Text(
          service['name'],
          style: const TextStyle(fontSize: 13, fontFamily: 'monospace', fontWeight: FontWeight.w500),
        ),
        subtitle: Text(
          service['desc'],
          style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5)),
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Enable/Disable toggle
            Switch(
              value: service['enabled'],
              onChanged: (v) => setState(() => service['enabled'] = v),
            ),
            const SizedBox(width: 8),
            // Start/Stop
            IconButton(
              icon: Icon(
                isRunning ? Icons.stop_circle : Icons.play_circle,
                color: isRunning ? Colors.red : Colors.green,
                size: 20,
              ),
              onPressed: () {
                setState(() {
                  service['status'] = isRunning ? 'stopped' : 'running';
                });
              },
              tooltip: isRunning ? 'Stop' : 'Start',
            ),
            // Restart
            IconButton(
              icon: Icon(Icons.refresh, size: 18, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5)),
              onPressed: () {
                setState(() => service['status'] = 'running');
              },
              tooltip: 'Restart',
            ),
          ],
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      ),
    );
  }

  // ===================== KERNEL TAB =====================
  Widget _buildKernelTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Kernel Configuration',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 16),
          // Boot Arguments
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.terminal, size: 18, color: Theme.of(context).colorScheme.primary),
                      const SizedBox(width: 8),
                      Text(
                        'Boot Arguments',
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _kernelParamsController,
                    style: const TextStyle(fontSize: 13, fontFamily: 'monospace'),
                    decoration: InputDecoration(
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                      hintText: 'Enter kernel parameters...',
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      FilledButton.tonal(
                        onPressed: () {},
                        child: const Text('Apply', style: TextStyle(fontSize: 12)),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        onPressed: () {
                          setState(() => _kernelParamsController.text = 'quiet splash loglevel=3');
                        },
                        child: const Text('Reset Default', style: TextStyle(fontSize: 12)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          // Kernel Modules
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.extension, size: 18, color: Theme.of(context).colorScheme.primary),
                      const SizedBox(width: 8),
                      Text(
                        'Kernel Modules',
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  ...List.generate(_kernelModules.length, (index) {
                    final mod = _kernelModules[index];
                    return CheckboxListTile(
                      value: mod['loaded'],
                      onChanged: (v) {
                        setState(() => mod['loaded'] = v ?? false);
                      },
                      title: Text(
                        mod['name'],
                        style: const TextStyle(fontSize: 13, fontFamily: 'monospace'),
                      ),
                      subtitle: Text(
                        mod['loaded'] ? 'Loaded' : 'Not loaded',
                        style: TextStyle(
                          fontSize: 11,
                          color: mod['loaded'] ? Colors.green : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                        ),
                      ),
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                    );
                  }),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ===================== RECOVERY TAB =====================
  Widget _buildRecoveryTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Recovery Mode',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 16),
          // Recovery Options
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.build, size: 18, color: Theme.of(context).colorScheme.primary),
                      const SizedBox(width: 8),
                      Text('Recovery Options', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildRecoveryOption(
                          icon: Icons.restart_alt,
                          title: 'Boot Recovery Mode',
                          desc: 'Restart into recovery shell',
                          color: Colors.orange,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _buildRecoveryOption(
                          icon: Icons.restore,
                          title: 'System Restore',
                          desc: 'Restore to previous state',
                          color: Colors.blue,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _buildRecoveryOption(
                          icon: Icons.delete_sweep,
                          title: 'Factory Reset',
                          desc: 'Reset all settings',
                          color: Colors.red,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          // Restore Points
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.history, size: 18, color: Theme.of(context).colorScheme.primary),
                      const SizedBox(width: 8),
                      Text('Restore Points', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Table(
                    columnWidths: const {
                      0: FlexColumnWidth(2),
                      1: FlexColumnWidth(3),
                      2: FlexColumnWidth(1.5),
                      3: FlexColumnWidth(1.5),
                    },
                    children: [
                      TableRow(
                        decoration: BoxDecoration(color: Theme.of(context).colorScheme.surfaceContainerHighest),
                        children: ['Date', 'Description', 'Size', 'Action'].map((h) {
                          return Padding(
                            padding: const EdgeInsets.all(10),
                            child: Text(h, style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7))),
                          );
                        }).toList(),
                      ),
                      ..._restorePoints.map((rp) {
                        return TableRow(
                          decoration: BoxDecoration(
                            border: Border(bottom: BorderSide(color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.1))),
                          ),
                          children: [
                            Padding(padding: const EdgeInsets.all(10), child: Text(rp['date']!, style: const TextStyle(fontSize: 12))),
                            Padding(padding: const EdgeInsets.all(10), child: Text(rp['name']!, style: const TextStyle(fontSize: 12))),
                            Padding(padding: const EdgeInsets.all(10), child: Text(rp['size']!, style: const TextStyle(fontSize: 12))),
                            Padding(
                              padding: const EdgeInsets.all(6),
                              child: FilledButton.tonal(
                                onPressed: () {},
                                child: const Text('Restore', style: TextStyle(fontSize: 11)),
                              ),
                            ),
                          ],
                        );
                      }),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      FilledButton.icon(
                        onPressed: () {},
                        icon: const Icon(Icons.backup, size: 18),
                        label: const Text('Create Backup'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed: () {},
                        icon: const Icon(Icons.restore, size: 18),
                        label: const Text('Restore from File'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecoveryOption({
    required IconData icon,
    required String title,
    required String desc,
    required Color color,
  }) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () {},
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            children: [
              Icon(icon, size: 28, color: color),
              const SizedBox(height: 8),
              Text(title, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600), textAlign: TextAlign.center),
              const SizedBox(height: 2),
              Text(desc, style: TextStyle(fontSize: 10, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5)), textAlign: TextAlign.center),
            ],
          ),
        ),
      ),
    );
  }

  // ===================== BOTTOM BAR =====================
  Widget _buildBottomBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          top: BorderSide(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
          ),
        ),
      ),
      child: AutoAdjustRow(
        spacing: 0,
        alignment: WrapAlignment.center,
        children: [
          OutlinedButton.icon(
            onPressed: () => _showPowerDialog('Shutdown'),
            icon: const Icon(Icons.power_settings_new, size: 18, color: Colors.red),
            label: const Text('Shutdown', style: TextStyle(color: Colors.red)),
          ),
          const SizedBox(width: 12),
          FilledButton.icon(
            onPressed: () => _showPowerDialog('Reboot'),
            icon: const Icon(Icons.refresh, size: 18),
            label: const Text('Reboot'),
          ),
          const SizedBox(width: 12),
          OutlinedButton.icon(
            onPressed: () => _showPowerDialog('Suspend'),
            icon: const Icon(Icons.pause_circle_outline, size: 18),
            label: const Text('Suspend'),
          ),
        ],
      ),
    );
  }

  void _showPowerDialog(String action) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Confirm $action'),
        content: Text('Are you sure you want to $action the system?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context),
            child: Text(action),
          ),
        ],
      ),
    );
  }
}

// ===================== TAB BUTTON =====================
class _TabButton extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _TabButton({
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: isSelected ? Theme.of(context).colorScheme.primary : Colors.transparent,
              width: 2,
            ),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
            color: isSelected
                ? Theme.of(context).colorScheme.primary
                : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
          ),
        ),
      ),
    );
  }
}

// ===================== SETTINGS ICON (Placeholder) =====================
const IconData settingsIcon = IconData(0xe8b8, fontFamily: 'MaterialIcons');
