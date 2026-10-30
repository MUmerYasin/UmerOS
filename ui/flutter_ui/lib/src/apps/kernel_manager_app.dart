// UmerOS Kernel & QoS Manager App
// Integrates HarmonyOS-inspired QoS scheduling, O(1) Membox pools,
// Priority Inheritance mutexes, SoftBus mesh networking, and Live Task telemetry.
// Designed with strict adherence to Human-Computer Interaction (HCI) principles.

import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';

/// QoS Tier representation
enum KernelQoSTier {
  userInteractive(label: 'User Interactive', weight: 1.5, boost: 20, color: Colors.cyanAccent),
  userInitiated(label: 'User Initiated', weight: 1.2, boost: 10, color: Colors.blueAccent),
  defaultTier(label: 'Default', weight: 1.0, boost: 0, color: Colors.tealAccent),
  background(label: 'Background', weight: 0.6, boost: -20, color: Colors.amberAccent);

  final String label;
  final double weight;
  final int boost;
  final Color color;

  const KernelQoSTier({
    required this.label,
    required this.weight,
    required this.boost,
    required this.color,
  });
}

/// Process Task Model
class KernelProcessTask {
  final int pid;
  final String name;
  KernelQoSTier qos;
  int basePriority;
  int effectivePriority;
  double cpuPercent;
  String state; // RUNNING, READY, BLOCKED, THROTTLED
  bool isInheritingPriority;
  final String description;

  KernelProcessTask({
    required this.pid,
    required this.name,
    required this.qos,
    required this.basePriority,
    required this.effectivePriority,
    required this.cpuPercent,
    this.state = 'RUNNING',
    this.isInheritingPriority = false,
    this.description = '',
  });
}

/// Membox Pool Model
class MemboxPoolData {
  final String name;
  final int blockSize;
  final int totalBlocks;
  int allocatedBlocks;
  final List<bool> blockMap;
  final String magicHead = '0xAA55AA55';
  final String magicTail = '0x55AA55AA';
  bool isCorrupted;

  MemboxPoolData({
    required this.name,
    required this.blockSize,
    required this.totalBlocks,
    required this.allocatedBlocks,
    required this.blockMap,
    this.isCorrupted = false,
  });
}

/// SoftBus Node Model
class SoftBusNodeData {
  final String nodeId;
  final String name;
  final String ip;
  final String linkType; // WiFi, BLE, P2P
  final int latencyMs;
  final double throughputKBps;
  final bool isSecure;
  final String status;

  SoftBusNodeData({
    required this.nodeId,
    required this.name,
    required this.ip,
    required this.linkType,
    required this.latencyMs,
    required this.throughputKBps,
    this.isSecure = true,
    this.status = 'CONNECTED',
  });
}

/// Live Task Model
class LiveTaskItem {
  final String id;
  final String title;
  final String subsystem;
  double progress;
  String status;
  final IconData icon;

  LiveTaskItem({
    required this.id,
    required this.title,
    required this.subsystem,
    required this.progress,
    required this.status,
    required this.icon,
  });
}

class KernelManagerApp extends StatefulWidget {
  const KernelManagerApp({super.key});

  @override
  State<KernelManagerApp> createState() => _KernelManagerAppState();
}

class _KernelManagerAppState extends State<KernelManagerApp>
    with SingleTickerProviderStateMixin {
  int _selectedTab = 0;
  Timer? _telemetryTimer;
  final Random _rand = Random();

  // Metrics
  double _lastFrameMs = 14.2;
  bool _isBackgroundThrottled = false;
  final int _quantumMs = 10;
  int _totalContextSwitches = 14208;
  double _overallCpuUsage = 24.5;

  // Process list
  late List<KernelProcessTask> _processes;
  String _processFilter = '';

  // Membox pools
  late List<MemboxPoolData> _memboxPools;

  // SoftBus Nodes
  late List<SoftBusNodeData> _softbusNodes;

  // Live Tasks
  late List<LiveTaskItem> _liveTasks;

  @override
  void initState() {
    super.initState();
    _initData();
    _startTelemetry();
  }

  @override
  void dispose() {
    _telemetryTimer?.cancel();
    super.dispose();
  }

  void _initData() {
    _processes = [
      KernelProcessTask(
        pid: 1,
        name: 'umer_kernel',
        qos: KernelQoSTier.userInteractive,
        basePriority: 100,
        effectivePriority: 120,
        cpuPercent: 4.8,
        description: 'Core Hybrid Microkernel',
      ),
      KernelProcessTask(
        pid: 2,
        name: 'flutter_desktop_ui',
        qos: KernelQoSTier.userInteractive,
        basePriority: 90,
        effectivePriority: 110,
        cpuPercent: 12.4,
        description: 'Fluidic Glassmorphism Desktop Shell',
      ),
      KernelProcessTask(
        pid: 3,
        name: 'quantum_sim_engine',
        qos: KernelQoSTier.background,
        basePriority: 30,
        effectivePriority: 10,
        cpuPercent: 8.5,
        description: 'Trapped-Ion & Quantum Circuit Simulator',
      ),
      KernelProcessTask(
        pid: 4,
        name: 'softbus_daemon',
        qos: KernelQoSTier.userInitiated,
        basePriority: 70,
        effectivePriority: 80,
        cpuPercent: 1.8,
        description: 'Distributed SoftBus Discovery & Mesh Bus',
      ),
      KernelProcessTask(
        pid: 5,
        name: 'pqc_kyber_signer',
        qos: KernelQoSTier.defaultTier,
        basePriority: 50,
        effectivePriority: 50,
        cpuPercent: 2.1,
        description: 'Post-Quantum Crypto Signature Worker',
      ),
      KernelProcessTask(
        pid: 6,
        name: 'background_ota_syncer',
        qos: KernelQoSTier.background,
        basePriority: 25,
        effectivePriority: 5,
        cpuPercent: 0.6,
        state: 'READY',
        description: 'Atomic Differential Update Worker',
      ),
      KernelProcessTask(
        pid: 7,
        name: 'ipc_fastpath_broker',
        qos: KernelQoSTier.userInteractive,
        basePriority: 95,
        effectivePriority: 115,
        cpuPercent: 3.2,
        isInheritingPriority: true,
        description: 'Zero-Copy Shared Memory IPC Broker',
      ),
    ];

    _memboxPools = [
      MemboxPoolData(
        name: 'fast_packets',
        blockSize: 64,
        totalBlocks: 16,
        allocatedBlocks: 7,
        blockMap: [true, true, false, true, false, false, true, true, false, true, true, false, false, false, false, false],
      ),
      MemboxPoolData(
        name: 'ipc_buffers',
        blockSize: 256,
        totalBlocks: 12,
        allocatedBlocks: 4,
        blockMap: [true, false, true, false, false, true, true, false, false, false, false, false],
      ),
      MemboxPoolData(
        name: 'quantum_events',
        blockSize: 128,
        totalBlocks: 8,
        allocatedBlocks: 2,
        blockMap: [true, true, false, false, false, false, false, false],
      ),
    ];

    _softbusNodes = [
      SoftBusNodeData(
        nodeId: 'node-01',
        name: 'umer-workstation-local',
        ip: '127.0.0.1:48899',
        linkType: 'P2P Loopback',
        latencyMs: 1,
        throughputKBps: 2450.0,
      ),
      SoftBusNodeData(
        nodeId: 'node-02',
        name: 'umer-quantum-rig-alpha',
        ip: '192.168.1.140:48899',
        linkType: 'WiFi Mesh 6E',
        latencyMs: 4,
        throughputKBps: 1820.0,
      ),
      SoftBusNodeData(
        nodeId: 'node-03',
        name: 'umer-mobile-mate60',
        ip: '192.168.1.185:48899',
        linkType: 'BLE 5.4 / P2P',
        latencyMs: 12,
        throughputKBps: 640.0,
      ),
    ];

    _liveTasks = [
      LiveTaskItem(
        id: 'task-quantum-opt',
        title: 'Trapped-Ion Circuit Transpilation',
        subsystem: 'quantum',
        progress: 0.68,
        status: 'Optimizing 12 CNOT gates...',
        icon: Icons.memory,
      ),
      LiveTaskItem(
        id: 'task-pqc-keys',
        title: 'ML-KEM-768 Ephemeral Keypair Gen',
        subsystem: 'crypto',
        progress: 0.92,
        status: 'Validating lattice constraints',
        icon: Icons.lock_outline,
      ),
      LiveTaskItem(
        id: 'task-softbus-sync',
        title: 'Distributed State Synchronization',
        subsystem: 'softbus',
        progress: 0.45,
        status: 'Syncing with umer-quantum-rig-alpha',
        icon: Icons.sync,
      ),
    ];
  }

  void _startTelemetry() {
    _telemetryTimer = Timer.periodic(const Duration(milliseconds: 1400), (_) {
      if (!mounted) return;
      setState(() {
        _overallCpuUsage = max(10.0, min(85.0, _overallCpuUsage + (_rand.nextDouble() * 6 - 3)));
        _totalContextSwitches += _rand.nextInt(45) + 15;

        _lastFrameMs = max(8.0, min(24.0, 13.5 + (_rand.nextDouble() * 5.0 - 2.0)));
        _isBackgroundThrottled = _lastFrameMs > 16.67;

        for (var task in _liveTasks) {
          if (task.progress < 1.0) {
            task.progress = min(1.0, task.progress + 0.04);
            if (task.progress >= 1.0) {
              task.status = 'Completed';
            }
          }
        }
      });
    });
  }

  void _simulateFrameDrop() {
    setState(() {
      _lastFrameMs = 28.5;
      _isBackgroundThrottled = true;
    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Colors.amberAccent),
            SizedBox(width: 8),
            Text('Simulated Frame Drop: 28.5ms. Background tasks throttled automatically!'),
          ],
        ),
        backgroundColor: Colors.grey.shade900,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _toggleMemboxBlock(MemboxPoolData pool, int index) {
    setState(() {
      if (pool.blockMap[index]) {
        pool.blockMap[index] = false;
        pool.allocatedBlocks = max(0, pool.allocatedBlocks - 1);
      } else {
        pool.blockMap[index] = true;
        pool.allocatedBlocks = min(pool.totalBlocks, pool.allocatedBlocks + 1);
      }
    });
  }

  void _corruptMemboxPool(MemboxPoolData pool) {
    setState(() {
      pool.isCorrupted = !pool.isCorrupted;
    });

    final message = pool.isCorrupted
        ? 'Sentinel Canary corrupted! Magic 0xDEADBEEF detected by Kernel Membox Guard.'
        : 'Sentinel restored. Canary guards 0xAA55AA55 / 0x55AA55AA verified.';

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: pool.isCorrupted ? Colors.red.shade900 : Colors.teal.shade900,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _changeTaskQoS(KernelProcessTask task, KernelQoSTier newQoS) {
    setState(() {
      task.qos = newQoS;
      task.effectivePriority = task.basePriority + newQoS.boost;
    });
  }

  void _elevateTaskPriority(KernelProcessTask task) {
    setState(() {
      task.isInheritingPriority = !task.isInheritingPriority;
      if (task.isInheritingPriority) {
        task.effectivePriority += 25;
      } else {
        task.effectivePriority = task.basePriority + task.qos.boost;
      }
    });
  }

  void _showKillConfirmation(KernelProcessTask task) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Row(
          children: [
            const Icon(Icons.warning_amber_rounded, color: Colors.redAccent),
            const SizedBox(width: 8),
            Text('Terminate Process PID ${task.pid}?'),
          ],
        ),
        content: Text(
          'Are you sure you want to send SIGKILL to "${task.name}"?\n'
          'Subsystem: ${task.description}\n'
          'Current State: ${task.state}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () {
              Navigator.pop(ctx);
              setState(() {
                _processes.removeWhere((p) => p.pid == task.pid);
              });
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Process ${task.name} (PID ${task.pid}) killed with SIGKILL.'),
                  backgroundColor: Colors.red.shade900,
                ),
              );
            },
            child: const Text('Kill Process'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Container(
        decoration: BoxDecoration(
          color: colorScheme.surface.withValues(alpha: 0.95),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          children: [
            _buildHeader(colorScheme),
            Expanded(
              child: IndexedStack(
                index: _selectedTab,
                children: [
                  _buildQoSSchedulerTab(colorScheme),
                  _buildMemboxPoolsTab(colorScheme),
                  _buildProcessControllerTab(colorScheme),
                  _buildSoftBusTab(colorScheme),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(ColorScheme colorScheme) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isNarrow = constraints.maxWidth < 650;

        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.6),
            border: Border(
              bottom: BorderSide(
                color: colorScheme.outlineVariant.withValues(alpha: 0.3),
              ),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: Colors.cyan.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.cyan.withValues(alpha: 0.3)),
                    ),
                    child: const Icon(Icons.developer_board, color: Colors.cyanAccent, size: 18),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Kernel & QoS Manager',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: colorScheme.onSurface,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                        if (!isNarrow)
                          Text(
                            'HarmonyOS QoS Tiers • Membox O(1) • PI Mutex • SoftBus Mesh',
                            style: TextStyle(
                              fontSize: 10,
                              color: colorScheme.onSurfaceVariant,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _buildNavTabButton(0, 'QoS Scheduler', Icons.speed),
                    const SizedBox(width: 6),
                    _buildNavTabButton(1, 'Membox Pools', Icons.layers),
                    const SizedBox(width: 6),
                    _buildNavTabButton(2, 'Process Controller', Icons.list_alt),
                    const SizedBox(width: 6),
                    _buildNavTabButton(3, 'SoftBus & Tasks', Icons.hub),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildNavTabButton(int index, String label, IconData icon) {
    final isSelected = _selectedTab == index;
    final colorScheme = Theme.of(context).colorScheme;

    return InkWell(
      onTap: () => setState(() => _selectedTab = index),
      borderRadius: BorderRadius.circular(8),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: isSelected ? colorScheme.primary : colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 14,
              color: isSelected ? colorScheme.onPrimary : colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: 5),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                color: isSelected ? colorScheme.onPrimary : colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ==========================================
  // TAB 0: QoS Scheduler & Latency Telemetry
  // ==========================================
  Widget _buildQoSSchedulerTab(ColorScheme colorScheme) {
    final frameStatusColor = _lastFrameMs > 16.67 ? Colors.amberAccent : Colors.greenAccent;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section Title & Simulation Button
          Row(
            children: [
              Text(
                'Performance & Frame Latency Telemetry',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
              ),
              const Spacer(),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  side: BorderSide(color: Colors.amberAccent.withValues(alpha: 0.5)),
                ),
                icon: const Icon(Icons.bolt, size: 14, color: Colors.amberAccent),
                label: const Text('Simulate Drop', style: TextStyle(fontSize: 10, color: Colors.amberAccent)),
                onPressed: _simulateFrameDrop,
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Responsive KPI Metric Cards
          LayoutBuilder(
            builder: (context, constraints) {
              final cardWidth = constraints.maxWidth > 650
                  ? (constraints.maxWidth - 36) / 4
                  : (constraints.maxWidth - 12) / 2;

              return Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  SizedBox(
                    width: cardWidth,
                    child: _buildMetricCard(
                      title: 'Frame Latency Telemetry',
                      value: '${_lastFrameMs.toStringAsFixed(1)} ms',
                      subtitle: _lastFrameMs > 16.67 ? 'Frame Drop! Throttling' : 'Optimal 60 FPS Target',
                      icon: Icons.timer,
                      color: frameStatusColor,
                    ),
                  ),
                  SizedBox(
                    width: cardWidth,
                    child: _buildMetricCard(
                      title: 'QoS Background Throttle',
                      value: _isBackgroundThrottled ? 'ACTIVE' : 'IDLE',
                      subtitle: _isBackgroundThrottled ? 'Quantum: 2ms for BG' : 'Quantum: ${_quantumMs}ms baseline',
                      icon: Icons.tune,
                      color: _isBackgroundThrottled ? Colors.amberAccent : Colors.cyanAccent,
                    ),
                  ),
                  SizedBox(
                    width: cardWidth,
                    child: _buildMetricCard(
                      title: 'Context Switches',
                      value: '$_totalContextSwitches',
                      subtitle: 'Fastpath IPC enabled',
                      icon: Icons.sync_alt,
                      color: Colors.purpleAccent,
                    ),
                  ),
                  SizedBox(
                    width: cardWidth,
                    child: _buildMetricCard(
                      title: 'Overall CPU Usage',
                      value: '${_overallCpuUsage.toStringAsFixed(1)}%',
                      subtitle: '${_processes.length} Active Tasks',
                      icon: Icons.memory,
                      color: Colors.tealAccent,
                    ),
                  ),
                ],
              );
            },
          ),

          const SizedBox(height: 18),

          // QoS Hierarchy Cards
          Text(
            'HarmonyOS 4-Tier QoS Hierarchy Engine',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.bold,
              color: colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 8),

          LayoutBuilder(
            builder: (context, constraints) {
              final tierWidth = constraints.maxWidth > 650
                  ? (constraints.maxWidth - 30) / 4
                  : (constraints.maxWidth - 10) / 2;

              return Wrap(
                spacing: 10,
                runSpacing: 10,
                children: KernelQoSTier.values.map((tier) {
                  final count = _processes.where((p) => p.qos == tier).length;
                  return SizedBox(
                    width: tierWidth,
                    child: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: tier.color.withValues(alpha: 0.3),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Container(
                                width: 8,
                                height: 8,
                                decoration: BoxDecoration(
                                  color: tier.color,
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  tier.label,
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                    color: tier.color,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Weight: ${tier.weight}x • Boost: ${tier.boost > 0 ? "+${tier.boost}" : tier.boost}',
                            style: TextStyle(fontSize: 10, color: colorScheme.onSurfaceVariant),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '$count tasks assigned',
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                              color: colorScheme.onSurface,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              );
            },
          ),

          const SizedBox(height: 18),

          // Priority Inheritance & Mutex Monitor
          Text(
            'Priority Inheritance (PI) Mutex & Inversion Shield',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.bold,
              color: colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 8),

          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: colorScheme.outlineVariant.withValues(alpha: 0.3)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.shield, color: Colors.greenAccent, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Active Protection: Priority Inversion Prevention Active',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: colorScheme.onSurface,
                        ),
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.greenAccent.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        'PI Mutex Protected',
                        style: TextStyle(fontSize: 9, color: Colors.greenAccent, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  'When an interactive UI thread requests a lock held by a background batch task, '
                  'the kernel scheduler automatically elevates the batch task\'s effective priority '
                  'to match the waiter, preventing intermediate priority starvation.',
                  style: TextStyle(fontSize: 10, color: colorScheme.onSurfaceVariant),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricCard({
    required String title,
    required String value,
    required String subtitle,
    required IconData icon,
    required Color color,
  }) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 14, color: color),
              const SizedBox(width: 5),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(fontSize: 10, color: colorScheme.onSurfaceVariant),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            style: TextStyle(fontSize: 9, color: colorScheme.onSurfaceVariant),
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  // ==========================================
  // TAB 1: Membox Pools & Sentinel Canaries
  // ==========================================
  Widget _buildMemboxPoolsTab(ColorScheme colorScheme) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'HarmonyOS / LiteOS Membox Block Allocator Pools',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                        color: colorScheme.onSurface,
                      ),
                    ),
                    Text(
                      'Deterministic O(1) allocation with magic boundary guards',
                      style: TextStyle(fontSize: 10, color: colorScheme.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.cyanAccent.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: Colors.cyanAccent.withValues(alpha: 0.3)),
                ),
                child: const Text(
                  '0xAA55AA55 / 0x55AA55AA',
                  style: TextStyle(
                    fontSize: 10,
                    fontFamily: 'monospace',
                    fontWeight: FontWeight.bold,
                    color: Colors.cyanAccent,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),

          ..._memboxPools.map((pool) => _buildMemboxPoolCard(pool, colorScheme)),
        ],
      ),
    );
  }

  Widget _buildMemboxPoolCard(MemboxPoolData pool, ColorScheme colorScheme) {
    final usageRatio = pool.allocatedBlocks / pool.totalBlocks;
    final statusColor = pool.isCorrupted
        ? Colors.redAccent
        : usageRatio > 0.8
            ? Colors.amberAccent
            : Colors.cyanAccent;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: statusColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.inventory_2_outlined, color: statusColor, size: 16),
              const SizedBox(width: 6),
              Text(
                'Pool: ${pool.name}',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '${pool.blockSize}B Block Size',
                  style: TextStyle(fontSize: 9, color: colorScheme.onSurfaceVariant),
                ),
              ),
              const Spacer(),
              TextButton.icon(
                style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
                onPressed: () => _corruptMemboxPool(pool),
                icon: Icon(
                  pool.isCorrupted ? Icons.build : Icons.bug_report,
                  size: 13,
                  color: pool.isCorrupted ? Colors.greenAccent : Colors.redAccent,
                ),
                label: Text(
                  pool.isCorrupted ? 'Heal Canary' : 'Test Corruption',
                  style: TextStyle(
                    fontSize: 10,
                    color: pool.isCorrupted ? Colors.greenAccent : Colors.redAccent,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),

          Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(3),
                  child: LinearProgressIndicator(
                    value: usageRatio,
                    backgroundColor: colorScheme.surfaceContainerHigh,
                    color: statusColor,
                    minHeight: 5,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '${pool.allocatedBlocks}/${pool.totalBlocks} (${(usageRatio * 100).toInt()}%)',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  color: statusColor,
                ),
              ),
            ],
          ),

          const SizedBox(height: 10),

          Text(
            'Direct Block Allocation Map (Click block to toggle allocate/free):',
            style: TextStyle(fontSize: 9, color: colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 5),
          Wrap(
            spacing: 5,
            runSpacing: 5,
            children: List.generate(pool.totalBlocks, (i) {
              final isAllocated = pool.blockMap[i];
              return InkWell(
                onTap: () => _toggleMemboxBlock(pool, i),
                borderRadius: BorderRadius.circular(4),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  width: 32,
                  height: 24,
                  decoration: BoxDecoration(
                    color: pool.isCorrupted
                        ? Colors.redAccent.withValues(alpha: 0.3)
                        : isAllocated
                            ? Colors.cyanAccent.withValues(alpha: 0.35)
                            : colorScheme.surfaceContainerHighest.withValues(alpha: 0.6),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(
                      color: pool.isCorrupted
                          ? Colors.redAccent
                          : isAllocated
                              ? Colors.cyanAccent
                              : colorScheme.outlineVariant.withValues(alpha: 0.3),
                      width: 1,
                    ),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    '#$i',
                    style: TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.bold,
                      color: isAllocated ? Colors.cyanAccent : colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }

  // ==========================================
  // TAB 2: Process Controller & QoS Hierarchy
  // ==========================================
  Widget _buildProcessControllerTab(ColorScheme colorScheme) {
    final filteredProcesses = _processes.where((p) {
      if (_processFilter.isEmpty) return true;
      return p.name.toLowerCase().contains(_processFilter.toLowerCase()) ||
          p.pid.toString().contains(_processFilter) ||
          p.description.toLowerCase().contains(_processFilter.toLowerCase());
    }).toList();

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  decoration: InputDecoration(
                    hintText: 'Filter processes by PID, Name or Description...',
                    hintStyle: TextStyle(fontSize: 11, color: colorScheme.onSurfaceVariant),
                    prefixIcon: const Icon(Icons.search, size: 15),
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(vertical: 6),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(6),
                      borderSide: BorderSide(color: colorScheme.outlineVariant.withValues(alpha: 0.3)),
                    ),
                  ),
                  onChanged: (val) => setState(() => _processFilter = val),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                '${filteredProcesses.length} Tasks',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: colorScheme.onSurface),
              ),
            ],
          ),
        ),

        Expanded(
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SingleChildScrollView(
              child: DataTable(
                columnSpacing: 16,
                horizontalMargin: 12,
                headingRowHeight: 34,
                dataRowMinHeight: 40,
                dataRowMaxHeight: 46,
                columns: const [
                  DataColumn(label: Text('PID', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 10))),
                  DataColumn(label: Text('Process Name', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 10))),
                  DataColumn(label: Text('QoS Tier', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 10))),
                  DataColumn(label: Text('Priority', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 10))),
                  DataColumn(label: Text('CPU %', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 10))),
                  DataColumn(label: Text('State', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 10))),
                  DataColumn(label: Text('Actions', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 10))),
                ],
                rows: filteredProcesses.map((proc) {
                  return DataRow(
                    cells: [
                      DataCell(Text('${proc.pid}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 10))),
                      DataCell(
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(proc.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 11)),
                            Text(proc.description, style: TextStyle(fontSize: 8, color: colorScheme.onSurfaceVariant)),
                          ],
                        ),
                      ),
                      DataCell(
                        DropdownButton<KernelQoSTier>(
                          value: proc.qos,
                          isDense: true,
                          underline: const SizedBox.shrink(),
                          icon: const Icon(Icons.arrow_drop_down, size: 14),
                          items: KernelQoSTier.values.map((tier) {
                            return DropdownMenuItem(
                              value: tier,
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Container(width: 5, height: 5, decoration: BoxDecoration(color: tier.color, shape: BoxShape.circle)),
                                  const SizedBox(width: 5),
                                  Text(tier.label, style: TextStyle(fontSize: 10, color: tier.color)),
                                ],
                              ),
                            );
                          }).toList(),
                          onChanged: (newQoS) {
                            if (newQoS != null) _changeTaskQoS(proc, newQoS);
                          },
                        ),
                      ),
                      DataCell(
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text('${proc.basePriority}/${proc.effectivePriority}', style: const TextStyle(fontSize: 10)),
                            if (proc.isInheritingPriority) ...[
                              const SizedBox(width: 3),
                              const Icon(Icons.arrow_upward, size: 11, color: Colors.greenAccent),
                            ],
                          ],
                        ),
                      ),
                      DataCell(Text('${proc.cpuPercent.toStringAsFixed(1)}%', style: const TextStyle(fontSize: 10))),
                      DataCell(
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                          decoration: BoxDecoration(
                            color: proc.state == 'RUNNING' ? Colors.green.withValues(alpha: 0.2) : Colors.amber.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            proc.state,
                            style: TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.bold,
                              color: proc.state == 'RUNNING' ? Colors.greenAccent : Colors.amberAccent,
                            ),
                          ),
                        ),
                      ),
                      DataCell(
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              icon: Icon(
                                proc.isInheritingPriority ? Icons.priority_high : Icons.upgrade,
                                size: 14,
                                color: proc.isInheritingPriority ? Colors.greenAccent : Colors.cyanAccent,
                              ),
                              tooltip: 'Toggle Priority Inheritance Elevation',
                              onPressed: () => _elevateTaskPriority(proc),
                            ),
                            IconButton(
                              icon: const Icon(Icons.close, size: 14, color: Colors.redAccent),
                              tooltip: 'Send SIGKILL to Process',
                              onPressed: () => _showKillConfirmation(proc),
                            ),
                          ],
                        ),
                      ),
                    ],
                  );
                }).toList(),
              ),
            ),
          ),
        ),
      ],
    );
  }

  // ==========================================
  // TAB 3: SoftBus Mesh & Background Live Tasks
  // ==========================================
  Widget _buildSoftBusTab(ColorScheme colorScheme) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.hub, color: Colors.blueAccent, size: 16),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'Distributed SoftBus Discovery & Mesh Nodes',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.greenAccent.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  '56-byte Binary • HMAC Signed',
                  style: TextStyle(fontSize: 9, color: Colors.greenAccent, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          LayoutBuilder(
            builder: (context, constraints) {
              final nodeWidth = constraints.maxWidth > 650
                  ? (constraints.maxWidth - 24) / 3
                  : constraints.maxWidth;

              return Wrap(
                spacing: 12,
                runSpacing: 10,
                children: _softbusNodes.map((node) {
                  return SizedBox(
                    width: nodeWidth,
                    child: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: Colors.blueAccent.withValues(alpha: 0.3)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Icon(Icons.devices, size: 14, color: Colors.blueAccent),
                              const SizedBox(width: 5),
                              Expanded(
                                child: Text(
                                  node.name,
                                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              Container(
                                width: 5,
                                height: 5,
                                decoration: const BoxDecoration(color: Colors.greenAccent, shape: BoxShape.circle),
                              ),
                            ],
                          ),
                          const SizedBox(height: 5),
                          Text('IP: ${node.ip}', style: TextStyle(fontSize: 9, color: colorScheme.onSurfaceVariant)),
                          Text('Link: ${node.linkType}', style: TextStyle(fontSize: 9, color: colorScheme.onSurfaceVariant)),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Text('Latency: ${node.latencyMs}ms', style: const TextStyle(fontSize: 9, color: Colors.greenAccent)),
                              const Spacer(),
                              Text('${node.throughputKBps.toInt()} KB/s', style: TextStyle(fontSize: 9, color: colorScheme.onSurfaceVariant)),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              );
            },
          ),

          const SizedBox(height: 20),

          Row(
            children: [
              const Icon(Icons.hourglass_top, color: Colors.cyanAccent, size: 16),
              const SizedBox(width: 6),
              Text(
                'Live Window Background Tasks (实况窗 Engine)',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          ..._liveTasks.map((task) {
            final isDone = task.progress >= 1.0;
            final progressColor = isDone ? Colors.greenAccent : Colors.cyanAccent;

            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: progressColor.withValues(alpha: 0.3)),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: progressColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Icon(task.icon, color: progressColor, size: 16),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                task.title,
                                style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            Text(
                              '${(task.progress * 100).toInt()}%',
                              style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: progressColor),
                            ),
                          ],
                        ),
                        const SizedBox(height: 3),
                        Text(
                          task.status,
                          style: TextStyle(fontSize: 9, color: colorScheme.onSurfaceVariant),
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 5),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(2),
                          child: LinearProgressIndicator(
                            value: task.progress,
                            minHeight: 3,
                            backgroundColor: colorScheme.surfaceContainerHigh,
                            color: progressColor,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  IconButton(
                    visualDensity: VisualDensity.compact,
                    icon: Icon(
                      isDone ? Icons.check_circle : Icons.cancel_outlined,
                      size: 16,
                      color: isDone ? Colors.greenAccent : colorScheme.onSurfaceVariant,
                    ),
                    tooltip: isDone ? 'Done' : 'Cancel Task',
                    onPressed: isDone
                        ? null
                        : () {
                            setState(() {
                              task.progress = 1.0;
                              task.status = 'Cancelled by User';
                            });
                          },
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}
