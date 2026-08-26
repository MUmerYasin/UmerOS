import 'package:flutter/material.dart';

import '../widgets/auto_adjust_box.dart';

class PowerGovernorApp extends StatefulWidget {
  const PowerGovernorApp({super.key});

  @override
  State<PowerGovernorApp> createState() => _PowerGovernorAppState();
}

class _PowerGovernorAppState extends State<PowerGovernorApp> {
  int _selectedGovernorIndex = 0;
  double _latencyBudget = 1000.0; // us
  bool _cpuidleActive = true;
  String _activeState = 'WFI';
  double _powerConsumption = 0.5; // mW
  int _stateTransitions = 1420;

  final List<Map<String, dynamic>> _idleStates = [
    {
      'name': 'WFI (Wait For Interrupt)',
      'latency': 10,
      'power': 0.5,
      'description': 'Low latency ARM/x86 core idle state',
    },
    {
      'name': 'STOP (Deep Sleep)',
      'latency': 200,
      'power': 0.1,
      'description': 'Deep power-down state with clock gating',
    },
  ];

  final List<String> _governors = [
    'SimpleGovernor (Latency Budget)',
    'MenuGovernor (Predictive Idle)',
    'LadderGovernor (Step-down Power)',
    'Performance (Always Active)',
  ];

  final List<Map<String, String>> _deviceLinks = [
    {
      'consumer': 'gpu_accelerator_0',
      'supplier': 'power_bus_cpu0',
      'flags': 'PM_RUNTIME | STATELESS',
    },
    {
      'consumer': 'network_phy_eth0',
      'supplier': 'pci_bridge_0',
      'flags': 'STATELESS',
    },
    {
      'consumer': 'quantum_al_unit',
      'supplier': 'power_bus_cpu0',
      'flags': 'PM_RUNTIME',
    },
  ];

  void _triggerIdleState() {
    setState(() {
      if (_latencyBudget >= 200) {
        _activeState = 'STOP';
        _powerConsumption = 0.1;
      } else {
        _activeState = 'WFI';
        _powerConsumption = 0.5;
      }
      _stateTransitions += 1;
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header Card
            Card(
              color: colorScheme.surfaceContainerHigh,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 24,
                      backgroundColor: colorScheme.primaryContainer,
                      child: Icon(
                        Icons.bolt,
                        color: colorScheme.primary,
                        size: 28,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'CPUIdle & Power Governor Framework',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: colorScheme.onSurface,
                            ),
                          ),
                          Text(
                            'UmerOS Kernel Power Management Driver',
                            style: TextStyle(
                              fontSize: 12,
                              color: colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Switch(
                      value: _cpuidleActive,
                      onChanged: (val) => setState(() => _cpuidleActive = val),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 14),

            // Live Metrics Cards
            Row(
              children: [
                Expanded(
                  child: _MetricCard(
                    title: 'Active Idle State',
                    value: _activeState,
                    icon: Icons.energy_savings_leaf,
                    color: Colors.green,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _MetricCard(
                    title: 'Power Usage',
                    value: '${_powerConsumption.toStringAsFixed(1)} mW',
                    icon: Icons.battery_charging_full,
                    color: Colors.blue,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _MetricCard(
                    title: 'Idle Transitions',
                    value: '$_stateTransitions',
                    icon: Icons.sync,
                    color: Colors.purple,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),

            // Governor Controls
            Card(
              color: colorScheme.surfaceContainerLow,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Power Governor Configuration',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: colorScheme.onSurface,
                      ),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<int>(
                      initialValue: _selectedGovernorIndex,
                      decoration: const InputDecoration(
                        labelText: 'Active Power Governor',
                        border: OutlineInputBorder(),
                      ),
                      items: List.generate(_governors.length, (idx) {
                        return DropdownMenuItem(
                          value: idx,
                          child: Text(_governors[idx]),
                        );
                      }),
                      onChanged: (val) =>
                          setState(() => _selectedGovernorIndex = val!),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      'Max Latency Budget: ${_latencyBudget.round()} µs',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: colorScheme.onSurface,
                      ),
                    ),
                    Slider(
                      value: _latencyBudget,
                      min: 10,
                      max: 1000,
                      divisions: 99,
                      label: '${_latencyBudget.round()} µs',
                      onChanged: (val) {
                        setState(() => _latencyBudget = val);
                        _triggerIdleState();
                      },
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 14),

            // Idle States Table
            Text(
              'Registered CPU Idle States',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 8),
            ..._idleStates.map(
              (st) => Card(
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: colorScheme.primaryContainer,
                    child: Icon(
                      Icons.bedtime,
                      color: colorScheme.primary,
                      size: 18,
                    ),
                  ),
                  title: Text(
                    st['name'],
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                    ),
                  ),
                  subtitle: Text(
                    '${st['description']} • Latency: ${st['latency']} µs',
                  ),
                  trailing: Chip(
                    label: Text('${st['power']} mW'),
                    backgroundColor: Colors.green.withValues(alpha: 0.2),
                  ),
                ),
              ),
            ),

            const SizedBox(height: 14),
            // Device Links Tree
            Text(
              'Device PM Links (Driver Model)',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 8),
            ..._deviceLinks.map(
              (link) => Card(
                child: ListTile(
                  leading: Icon(Icons.account_tree, color: colorScheme.primary),
                  title: Text(
                    '${link['consumer']} ➔ ${link['supplier']}',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                  ),
                  subtitle: Text('Flags: ${link['flags']}'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;

  const _MetricCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Card(
      color: colorScheme.surfaceContainerHigh,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 6),
            Text(
              title,
              style: TextStyle(
                fontSize: 10,
                color: colorScheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 2),
            AutoAdjustBox(
              child: Text(
                value,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
