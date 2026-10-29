/// KVM Manager — Virtual Machine Management App for UmerOS
///
/// Provides a GUI for managing KVM virtual machines, vCPUs,
/// memory slots, IRQ routing, and device passthrough.
library;

import 'package:flutter/material.dart';

class KvmManagerApp extends StatefulWidget {
  const KvmManagerApp({super.key});

  @override
  State<KvmManagerApp> createState() => _KvmManagerAppState();
}

class _KvmManagerAppState extends State<KvmManagerApp> {
  int _selectedTab = 0;
  final List<_VmInstance> _vms = [];
  int _nextVmId = 1;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Column(
        children: [
          // Tab bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                _buildTab('VMs', 0, Icons.computer),
                const SizedBox(width: 8),
                _buildTab('vCPUs', 1, Icons.memory),
                const SizedBox(width: 8),
                _buildTab('Memory', 2, Icons.storage),
                const SizedBox(width: 8),
                _buildTab('IRQ', 3, Icons.electrical_services),
                const SizedBox(width: 8),
                _buildTab('Devices', 4, Icons.devices),
                const Spacer(),
                FilledButton.icon(
                  onPressed: _createVm,
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('New VM'),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: _buildTabContent(colorScheme),
          ),
        ],
      ),
    );
  }

  Widget _buildTab(String label, int index, IconData icon) {
    final isSelected = _selectedTab == index;
    final colorScheme = Theme.of(context).colorScheme;
    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: () => setState(() => _selectedTab = index),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? colorScheme.primaryContainer : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: isSelected ? colorScheme.onPrimaryContainer : colorScheme.onSurfaceVariant),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                color: isSelected ? colorScheme.onPrimaryContainer : colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTabContent(ColorScheme colorScheme) {
    switch (_selectedTab) {
      case 0:
        return _buildVmList(colorScheme);
      case 1:
        return _buildVcpuList(colorScheme);
      case 2:
        return _buildMemorySlots(colorScheme);
      case 3:
        return _buildIrqRouting(colorScheme);
      case 4:
        return _buildDevices(colorScheme);
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildVmList(ColorScheme colorScheme) {
    if (_vms.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.computer, size: 64, color: colorScheme.onSurfaceVariant.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text(
              'No Virtual Machines',
              style: TextStyle(fontSize: 18, color: colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 8),
            Text(
              'Click "New VM" to create one',
              style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant.withValues(alpha: 0.6)),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _vms.length,
      itemBuilder: (context, index) {
        final vm = _vms[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: colorScheme.primaryContainer,
              child: Icon(Icons.computer, color: colorScheme.onPrimaryContainer),
            ),
            title: Text('VM-${vm.id}'),
            subtitle: Text('${vm.vcpuCount} vCPUs, ${vm.memoryMB} MB RAM'),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  icon: Icon(vm.running ? Icons.stop : Icons.play_arrow),
                  onPressed: () => setState(() => vm.running = !vm.running),
                  tooltip: vm.running ? 'Stop' : 'Start',
                ),
                IconButton(
                  icon: const Icon(Icons.delete),
                  onPressed: () => _deleteVm(index),
                  tooltip: 'Delete',
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildVcpuList(ColorScheme colorScheme) {
    return Center(
      child: Text(
        'vCPU management coming soon',
        style: TextStyle(color: colorScheme.onSurfaceVariant),
      ),
    );
  }

  Widget _buildMemorySlots(ColorScheme colorScheme) {
    return Center(
      child: Text(
        'Memory slot visualization coming soon',
        style: TextStyle(color: colorScheme.onSurfaceVariant),
      ),
    );
  }

  Widget _buildIrqRouting(ColorScheme colorScheme) {
    return Center(
      child: Text(
        'IRQ routing table coming soon',
        style: TextStyle(color: colorScheme.onSurfaceVariant),
      ),
    );
  }

  Widget _buildDevices(ColorScheme colorScheme) {
    return Center(
      child: Text(
        'VFIO device passthrough coming soon',
        style: TextStyle(color: colorScheme.onSurfaceVariant),
      ),
    );
  }

  void _createVm() {
    setState(() {
      _vms.add(_VmInstance(
        id: _nextVmId++,
        vcpuCount: 2,
        memoryMB: 512,
        running: false,
      ));
    });
  }

  void _deleteVm(int index) {
    setState(() {
      _vms.removeAt(index);
    });
  }
}

class _VmInstance {
  final int id;
  int vcpuCount;
  int memoryMB;
  bool running;

  _VmInstance({
    required this.id,
    required this.vcpuCount,
    required this.memoryMB,
    required this.running,
  });
}