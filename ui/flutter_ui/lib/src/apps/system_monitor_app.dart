import 'package:flutter/material.dart';
import 'dart:math';
import '../widgets/auto_adjust_box.dart';

class SystemMonitorApp extends StatefulWidget {
  const SystemMonitorApp({super.key});

  @override
  State<SystemMonitorApp> createState() => _SystemMonitorAppState();
}

class _SystemMonitorAppState extends State<SystemMonitorApp> {
  final Random _random = Random();
  double _cpuUsage = 0;
  double _memoryUsage = 0;
  double _diskUsage = 0;
  double _networkIn = 0;
  double _networkOut = 0;
  final List<double> _cpuHistory = [];
  final List<double> _memoryHistory = [];
  int _selectedTab = 0;

  @override
  void initState() {
    super.initState();
    _updateStats();
    Future.doWhile(() async {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted) return false;
      _updateStats();
      return true;
    });
  }

  void _updateStats() {
    setState(() {
      _cpuUsage = 20 + _random.nextDouble() * 60;
      _memoryUsage = 40 + _random.nextDouble() * 30;
      _diskUsage = 55 + _random.nextDouble() * 10;
      _networkIn = _random.nextDouble() * 100;
      _networkOut = _random.nextDouble() * 50;

      _cpuHistory.add(_cpuUsage);
      _memoryHistory.add(_memoryUsage);

      if (_cpuHistory.length > 60) _cpuHistory.removeAt(0);
      if (_memoryHistory.length > 60) _memoryHistory.removeAt(0);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Tab Bar
        Container(
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
              _TabButton(
                label: 'Overview',
                isSelected: _selectedTab == 0,
                onTap: () => setState(() => _selectedTab = 0),
              ),
              _TabButton(
                label: 'Processes',
                isSelected: _selectedTab == 1,
                onTap: () => setState(() => _selectedTab = 1),
              ),
              _TabButton(
                label: 'Resources',
                isSelected: _selectedTab == 2,
                onTap: () => setState(() => _selectedTab = 2),
              ),
            ],
          ),
        ),

        // Content
        Expanded(
          child: _selectedTab == 0
              ? _buildOverview()
              : _selectedTab == 1
                  ? _buildProcesses()
                  : _buildResources(),
        ),
      ],
    );
  }

  Widget _buildOverview() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: _MetricCard(
                title: 'CPU',
                value: '${_cpuUsage.toStringAsFixed(1)}%',
                icon: Icons.speed,
                color: Colors.blue,
                history: _cpuHistory,
              )),
              const SizedBox(width: 16),
              Expanded(child: _MetricCard(
                title: 'Memory',
                value: '${_memoryUsage.toStringAsFixed(1)}%',
                icon: Icons.memory,
                color: Colors.green,
                history: _memoryHistory,
              )),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(child: _StatCard(
                title: 'Disk Usage',
                value: '${_diskUsage.toStringAsFixed(1)}%',
                icon: Icons.storage,
                color: Colors.orange,
              )),
              const SizedBox(width: 16),
              Expanded(child: _StatCard(
                title: 'Network In',
                value: '${_networkIn.toStringAsFixed(1)} MB/s',
                icon: Icons.arrow_downward,
                color: Colors.cyan,
              )),
              const SizedBox(width: 16),
              Expanded(child: _StatCard(
                title: 'Network Out',
                value: '${_networkOut.toStringAsFixed(1)} MB/s',
                icon: Icons.arrow_upward,
                color: Colors.purple,
              )),
            ],
          ),
          const SizedBox(height: 16),
          _SystemInfoCard(),
        ],
      ),
    );
  }

  Widget _buildProcesses() {
    final processes = [
      {'pid': '1', 'name': 'init', 'cpu': '0.1', 'mem': '0.2', 'status': 'Running'},
      {'pid': '2', 'name': 'kernel', 'cpu': '0.3', 'mem': '1.5', 'status': 'Running'},
      {'pid': '3', 'name': 'ai_engine', 'cpu': '2.1', 'mem': '5.2', 'status': 'Running'},
      {'pid': '4', 'name': 'quantum_daemon', 'cpu': '1.8', 'mem': '3.1', 'status': 'Running'},
      {'pid': '5', 'name': 'shell', 'cpu': '0.5', 'mem': '0.8', 'status': 'Running'},
      {'pid': '6', 'name': 'file_manager', 'cpu': '0.2', 'mem': '1.2', 'status': 'Sleeping'},
      {'pid': '7', 'name': 'network_manager', 'cpu': '0.4', 'mem': '0.9', 'status': 'Running'},
      {'pid': '8', 'name': 'security_daemon', 'cpu': '0.6', 'mem': '1.1', 'status': 'Running'},
    ];

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
          child: const Row(
            children: [
              SizedBox(width: 80, child: Text('PID', style: TextStyle(fontWeight: FontWeight.bold))),
              Expanded(child: Text('Name', style: TextStyle(fontWeight: FontWeight.bold))),
              SizedBox(width: 80, child: Text('CPU%', style: TextStyle(fontWeight: FontWeight.bold))),
              SizedBox(width: 80, child: Text('Mem%', style: TextStyle(fontWeight: FontWeight.bold))),
              SizedBox(width: 100, child: Text('Status', style: TextStyle(fontWeight: FontWeight.bold))),
            ],
          ),
        ),
        Expanded(
          child: ListView.builder(
            itemCount: processes.length,
            itemBuilder: (context, index) {
              final p = processes[index];
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                      color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.1),
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    SizedBox(width: 80, child: Text(p['pid']!)),
                    Expanded(child: Text(p['name']!)),
                    SizedBox(width: 80, child: Text(p['cpu']!)),
                    SizedBox(width: 80, child: Text(p['mem']!)),
                    SizedBox(
                      width: 100,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: p['status'] == 'Running'
                              ? Colors.green.withValues(alpha: 0.2)
                              : Colors.orange.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          p['status']!,
                          style: TextStyle(
                            fontSize: 12,
                            color: p['status'] == 'Running' ? Colors.green : Colors.orange,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildResources() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          _ResourceBar(label: 'CPU Cores', value: 0.45, color: Colors.blue),
          const SizedBox(height: 16),
          _ResourceBar(label: 'Memory (256 GB)', value: _memoryUsage / 100, color: Colors.green),
          const SizedBox(height: 16),
          _ResourceBar(label: 'Disk (2 TB QFS)', value: _diskUsage / 100, color: Colors.orange),
          const SizedBox(height: 16),
          _ResourceBar(label: 'Swap (16 GB)', value: 0.05, color: Colors.purple),
          const SizedBox(height: 16),
          _ResourceBar(label: 'GPU VRAM (24 GB)', value: 0.32, color: Colors.cyan),
          const SizedBox(height: 16),
          _ResourceBar(label: 'Quantum Qubits (128)', value: 0.75, color: Colors.indigo),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;
  final List<double> history;

  const _MetricCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
    required this.history,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 24),
              const SizedBox(width: 8),
              Expanded(child: Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold))),
              const SizedBox(width: 8),
              Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 60,
            child: CustomPaint(
              painter: _GraphPainter(data: history, color: color),
              size: const Size(double.infinity, 60),
            ),
          ),
        ],
      ),
    );
  }
}

class _GraphPainter extends CustomPainter {
  final List<double> data;
  final Color color;

  _GraphPainter({required this.data, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (data.isEmpty) return;

    final paint = Paint()
      ..color = color
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;

    final fillPaint = Paint()
      ..color = color.withValues(alpha: 0.2)
      ..style = PaintingStyle.fill;

    final path = Path();
    final fillPath = Path();

    final width = size.width;
    final height = size.height;
    final step = width / (data.length - 1);

    path.moveTo(0, height - (data[0] / 100 * height));
    fillPath.moveTo(0, height);
    fillPath.lineTo(0, height - (data[0] / 100 * height));

    for (int i = 1; i < data.length; i++) {
      final x = i * step;
      final y = height - (data[i] / 100 * height);
      path.lineTo(x, y);
      fillPath.lineTo(x, y);
    }

    fillPath.lineTo(width, height);
    fillPath.close();

    canvas.drawPath(fillPath, fillPaint);
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}

class _StatCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;

  const _StatCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 20),
              const SizedBox(width: 8),
              Expanded(child: Text(title, style: TextStyle(fontSize: 14, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7)))),
            ],
          ),
          const SizedBox(height: 8),
          Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color)),
        ],
      ),
    );
  }
}

class _SystemInfoCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('System Information', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          _InfoRow(label: 'OS', value: 'UmerOS 2.0'),
          _InfoRow(label: 'Kernel', value: 'Quantum Kernel 1.0'),
          _InfoRow(label: 'CPU', value: 'Quantum Core (128 qubits)'),
          _InfoRow(label: 'Memory', value: '256 GB QRAM'),
          _InfoRow(label: 'GPU', value: 'UmerGPU RTX 5090'),
          _InfoRow(label: 'AI Engine', value: 'Neural Engine v3'),
          _InfoRow(label: 'Filesystem', value: 'QFS (Quantum File System)'),
          _InfoRow(label: 'Uptime', value: '12h 34m'),
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
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
          ),
          Expanded(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w500))),
        ],
      ),
    );
  }
}

class _ResourceBar extends StatelessWidget {
  final String label;
  final double value;
  final Color color;

  const _ResourceBar({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(child: Text(label)),
            Text('${(value * 100).toStringAsFixed(1)}%', style: TextStyle(color: color)),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: value,
            backgroundColor: color.withValues(alpha: 0.2),
            valueColor: AlwaysStoppedAnimation<Color>(color),
            minHeight: 8,
          ),
        ),
      ],
    );
  }
}

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
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: isSelected
                  ? Theme.of(context).colorScheme.primary
                  : Colors.transparent,
              width: 2,
            ),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
            color: isSelected
                ? Theme.of(context).colorScheme.primary
                : Theme.of(context).colorScheme.onSurface,
          ),
        ),
      ),
    );
  }
}
