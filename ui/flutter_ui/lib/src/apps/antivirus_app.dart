import 'package:flutter/material.dart';
import 'dart:math';

import '../widgets/auto_adjust_box.dart';

class AntivirusApp extends StatefulWidget {
  const AntivirusApp({super.key});

  @override
  State<AntivirusApp> createState() => _AntivirusAppState();
}

class _AntivirusAppState extends State<AntivirusApp> {
  int _selectedTab = 0;
  final Random _random = Random();

  // Dashboard
  int _threatLevel = 0; // 0=green, 1=yellow, 2=red
  double _scanProgress = 0.0;
  String _lastScanTime = 'Never';
  int _detectedThreats = 0;
  bool _scanning = false;
  int _filesScanned = 0;
  final int _totalSignatures = 1247;

  // Scan results
  final List<Map<String, dynamic>> _scanResults = [];
  String _selectedScanPath = 'C:\\Users\\Public';
  bool _realtimeProtection = true;

  // Quarantine
  final List<Map<String, dynamic>> _quarantine = [];

  // Real-time monitor
  final List<Map<String, dynamic>> _monitorEvents = [];
  final List<String> _watchedDirs = [
    'C:\\Users\\Public\\Downloads',
    'C:\\Windows\\Temp',
  ];

  void _runScan(bool full) async {
    setState(() {
      _scanning = true;
      _scanProgress = 0.0;
      _scanResults.clear();
      _filesScanned = 0;
    });

    final paths = full
        ? [
            'C:\\Windows\\System32',
            'C:\\Program Files',
            'C:\\Users\\Public',
            _selectedScanPath,
          ]
        : [_selectedScanPath];

    for (final path in paths) {
      final fileCount = full ? 200 + _random.nextInt(300) : 50 + _random.nextInt(100);
      for (int i = 0; i < fileCount; i++) {
        await Future.delayed(const Duration(milliseconds: 5));
        if (!mounted) return;
        setState(() {
          _filesScanned++;
          _scanProgress = min(100, (_filesScanned / (full ? 800 : 150)) * 100);
        });

        // Simulate threat detection
        if (_random.nextDouble() < 0.008) {
          final threatNames = [
            'Trojan.GenericKD.48291',
            'Worm.Win32.AutoRun',
            'Adware.BrowserModifier',
            'RiskTool.Injector',
            'Backdoor.Agent',
            'Rootkit.TDSS',
            'Cryptor.XOR',
          ];
          final levels = ['low', 'medium', 'high', 'critical'];
          final result = {
            'file': '$path\\file${_random.nextInt(9999)}.exe',
            'threat': threatNames[_random.nextInt(threatNames.length)],
            'level': levels[_random.nextInt(levels.length)],
            'method': _random.nextBool() ? 'signature' : 'heuristic',
            'action': 'detected',
          };
          _scanResults.add(result);
        }
      }
    }

    setState(() {
      _scanning = false;
      _detectedThreats = _scanResults.length;
      _threatLevel = _detectedThreats == 0 ? 0 : _detectedThreats < 3 ? 1 : 2;
      final now = DateTime.now();
      _lastScanTime =
          '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';
    });
  }

  void _quarantineFile(Map<String, dynamic> result) {
    setState(() {
      _quarantine.add({
        ...result,
        'quarantined_at': _lastScanTime,
        'status': 'quarantined',
      });
      _scanResults.remove(result);
      _detectedThreats = _scanResults.length;
      _threatLevel = _detectedThreats == 0 ? 0 : _detectedThreats < 3 ? 1 : 2;
    });
  }

  void _quarantineAll() {
    setState(() {
      for (final r in List.from(_scanResults)) {
        _quarantine.add({
          ...r,
          'quarantined_at': _lastScanTime,
          'status': 'quarantined',
        });
      }
      _scanResults.clear();
      _detectedThreats = 0;
      _threatLevel = 0;
    });
  }

  void _deleteFromQuarantine(int index) {
    setState(() => _quarantine.removeAt(index));
  }

  void _restoreFromQuarantine(int index) {
    setState(() => _quarantine.removeAt(index));
  }

  void _simulateMonitorEvent() {
    final eventTypes = ['created', 'modified', 'accessed'];
    final dirs = _watchedDirs;
    setState(() {
      _monitorEvents.insert(0, {
        'type': eventTypes[_random.nextInt(eventTypes.length)],
        'path':
            '${dirs[_random.nextInt(dirs.length)]}\\file${_random.nextInt(9999)}.dll',
        'time':
            '${DateTime.now().hour.toString().padLeft(2, '0')}:${DateTime.now().minute.toString().padLeft(2, '0')}:${DateTime.now().second.toString().padLeft(2, '0')}',
        'status': _random.nextDouble() < 0.05 ? 'threat' : 'clean',
      });
      if (_monitorEvents.length > 50) _monitorEvents.removeLast();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildTabBar(),
        Expanded(
          child: _selectedTab == 0
              ? _buildDashboardTab()
              : _selectedTab == 1
                  ? _buildScanTab()
                  : _selectedTab == 2
                      ? _buildQuarantineTab()
                      : _buildMonitorTab(),
        ),
      ],
    );
  }

  Widget _buildTabBar() {
    final tabs = ['Dashboard', 'Scan', 'Quarantine', 'Monitor'];
    final icons = [Icons.dashboard, Icons.search, Icons.security, Icons.monitor];
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
          ),
        ),
      ),
      child: Row(
        children: [
          for (int i = 0; i < tabs.length; i++)
            Expanded(
              child: GestureDetector(
                onTap: () => setState(() => _selectedTab = i),
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  decoration: BoxDecoration(
                    border: Border(
                      bottom: BorderSide(
                        color: _selectedTab == i
                            ? Theme.of(context).colorScheme.primary
                            : Colors.transparent,
                        width: 2,
                      ),
                    ),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        icons[i],
                        size: 16,
                        color: _selectedTab == i
                            ? Theme.of(context).colorScheme.primary
                            : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                      const SizedBox(width: 6),
                      Flexible(
                        child: Text(
                          tabs[i],
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: _selectedTab == i ? FontWeight.w600 : FontWeight.normal,
                            color: _selectedTab == i
                                ? Theme.of(context).colorScheme.primary
                                : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildDashboardTab() {
    final colorScheme = Theme.of(context).colorScheme;
    final statusColor = _threatLevel == 0
        ? Colors.green
        : _threatLevel == 1
            ? Colors.orange
            : Colors.red;
    final statusText = _threatLevel == 0
        ? 'System Protected'
        : _threatLevel == 1
            ? 'Threats Detected'
            : 'Critical Threats!';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Status Banner
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  statusColor.withValues(alpha: 0.15),
                  statusColor.withValues(alpha: 0.05),
                ],
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: statusColor.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(
                    _threatLevel == 0
                        ? Icons.shield
                        : _threatLevel == 1
                            ? Icons.warning
                            : Icons.dangerous,
                    size: 32,
                    color: statusColor,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        statusText,
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                          color: statusColor,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Last scan: $_lastScanTime  |  Signatures: $_totalSignatures',
                        style: TextStyle(
                          fontSize: 13,
                          color: colorScheme.onSurface.withValues(alpha: 0.6),
                        ),
                      ),
                    ],
                  ),
                ),
                _buildGlowIndicator(statusColor),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Quick Actions
          Row(
            children: [
              _buildQuickAction(
                Icons.search,
                'Quick Scan',
                Colors.blue,
                () => _runScan(false),
              ),
              const SizedBox(width: 12),
              _buildQuickAction(
                Icons.scanner,
                'Full Scan',
                Colors.purple,
                () => _runScan(true),
              ),
              const SizedBox(width: 12),
              _buildQuickAction(
                _realtimeProtection ? Icons.play_circle : Icons.pause_circle,
                _realtimeProtection ? 'Protection ON' : 'Protection OFF',
                _realtimeProtection ? Colors.green : Colors.grey,
                () => setState(() => _realtimeProtection = !_realtimeProtection),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Stats Grid
          Row(
            children: [
              _buildStatCard('Files Scanned', '$_filesScanned', Icons.folder_open, Colors.blue),
              const SizedBox(width: 12),
              _buildStatCard('Threats Found', '$_detectedThreats', Icons.bug_report, Colors.red),
              const SizedBox(width: 12),
              _buildStatCard(
                  'Quarantined', '${_quarantine.length}', Icons.lock, Colors.orange),
              const SizedBox(width: 12),
              _buildStatCard(
                  'Watched', '${_watchedDirs.length}', Icons.visibility, Colors.cyan),
            ],
          ),

          if (_scanning) ...[
            const SizedBox(height: 20),
            _buildScanProgress(),
          ],
        ],
      ),
    );
  }

  Widget _buildGlowIndicator(Color color) {
    return Container(
      width: 16,
      height: 16,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(color: color.withValues(alpha: 0.6), blurRadius: 12, spreadRadius: 4),
        ],
      ),
    );
  }

  Widget _buildQuickAction(IconData icon, String label, Color color, VoidCallback onTap) {
    return Expanded(
      child: GestureDetector(
        onTap: _scanning ? null : onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 16),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: color.withValues(alpha: 0.3)),
          ),
          child: Column(
            children: [
              Icon(icon, size: 28, color: color),
              const SizedBox(height: 6),
              Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatCard(String label, String value, IconData icon, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          children: [
            Icon(icon, size: 20, color: color),
            const SizedBox(height: 6),
            Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
            const SizedBox(height: 2),
            Text(label,
                style: TextStyle(
                    fontSize: 11, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5))),
          ],
        ),
      ),
    );
  }

  Widget _buildScanProgress() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AutoAdjustRow(
            alignment: WrapAlignment.spaceBetween,
            children: [
              const Text('Scanning...', style: TextStyle(fontWeight: FontWeight.w600)),
              Text('${_scanProgress.toStringAsFixed(0)}%  |  $_filesScanned files',
                  style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6))),
            ],
          ),
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: _scanProgress / 100,
            backgroundColor: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
            valueColor: AlwaysStoppedAnimation<Color>(
              _threatLevel == 0 ? Colors.blue : Colors.orange,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildScanTab() {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Path selector
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                Icon(Icons.folder, size: 18, color: colorScheme.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(_selectedScanPath,
                      style: const TextStyle(fontSize: 13, fontFamily: 'monospace')),
                ),
                FilledButton.tonal(
                  onPressed: () {
                    setState(() => _selectedScanPath = 'C:\\Users\\Public\\Documents');
                  },
                  child: const Text('Change'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Scan buttons
          Row(
            children: [
              FilledButton.icon(
                onPressed: _scanning ? null : () => _runScan(false),
                icon: const Icon(Icons.search, size: 18),
                label: const Text('Quick Scan'),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: _scanning ? null : () => _runScan(true),
                icon: const Icon(Icons.scanner, size: 18),
                label: const Text('Full Scan'),
              ),
              const Spacer(),
              if (_scanResults.isNotEmpty)
                FilledButton.tonal(
                  onPressed: _quarantineAll,
                  child: const Text('Quarantine All'),
                ),
            ],
          ),
          const SizedBox(height: 16),

          if (_scanning) _buildScanProgress(),
          if (_scanResults.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text('Detected Threats (${_scanResults.length})',
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            const SizedBox(height: 8),
            Expanded(
              child: ListView.builder(
                itemCount: _scanResults.length,
                itemBuilder: (context, index) {
                  final r = _scanResults[index];
                  final levelColor = r['level'] == 'critical'
                      ? Colors.red
                      : r['level'] == 'high'
                          ? Colors.orange
                          : r['level'] == 'medium'
                              ? Colors.amber
                              : Colors.grey;
                  return Container(
                    margin: const EdgeInsets.only(bottom: 6),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: levelColor.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: levelColor.withValues(alpha: 0.2)),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.bug_report, size: 18, color: levelColor),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(r['threat'],
                                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12)),
                              Text(r['file'],
                                  style: TextStyle(
                                      fontSize: 11,
                                      color: colorScheme.onSurface.withValues(alpha: 0.5),
                                      fontFamily: 'monospace'),
                                  overflow: TextOverflow.ellipsis),
                            ],
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: levelColor.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(r['level'].toUpperCase(),
                              style: TextStyle(fontSize: 10, color: levelColor, fontWeight: FontWeight.bold)),
                        ),
                        const SizedBox(width: 6),
                        IconButton(
                          icon: const Icon(Icons.lock, size: 16),
                          tooltip: 'Quarantine',
                          onPressed: () => _quarantineFile(r),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ] else if (!_scanning) ...[
            const SizedBox(height: 40),
            Center(
              child: Column(
                children: [
                  Icon(Icons.search_off,
                      size: 48, color: colorScheme.onSurface.withValues(alpha: 0.2)),
                  const SizedBox(height: 8),
                  Text('No threats detected',
                      style: TextStyle(color: colorScheme.onSurface.withValues(alpha: 0.4))),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildQuarantineTab() {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AutoAdjustRow(
            alignment: WrapAlignment.spaceBetween,
            children: [
              Text('Quarantined Files (${_quarantine.length})',
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
              if (_quarantine.isNotEmpty)
                TextButton.icon(
                  onPressed: () {
                    showDialog(
                      context: context,
                      builder: (ctx) => AlertDialog(
                        title: const Text('Clear Quarantine?'),
                        content: Text('Delete all ${_quarantine.length} quarantined files permanently?'),
                        actions: [
                          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                          FilledButton(
                            onPressed: () {
                              setState(() => _quarantine.clear());
                              Navigator.pop(ctx);
                            },
                            child: const Text('Delete All'),
                          ),
                        ],
                      ),
                    );
                  },
                  icon: const Icon(Icons.delete_sweep, size: 18),
                  label: const Text('Clear All'),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: _quarantine.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.lock_open,
                            size: 48, color: colorScheme.onSurface.withValues(alpha: 0.2)),
                        const SizedBox(height: 8),
                        Text('No quarantined files',
                            style: TextStyle(color: colorScheme.onSurface.withValues(alpha: 0.4))),
                      ],
                    ),
                  )
                : ListView.builder(
                    itemCount: _quarantine.length,
                    itemBuilder: (context, index) {
                      final q = _quarantine[index];
                      final levelColor = q['level'] == 'critical'
                          ? Colors.red
                          : q['level'] == 'high'
                              ? Colors.orange
                              : Colors.amber;
                      return Container(
                        margin: const EdgeInsets.only(bottom: 8),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Row(
                          children: [
                            Container(
                              width: 36,
                              height: 36,
                              decoration: BoxDecoration(
                                color: levelColor.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Icon(Icons.lock, size: 18, color: levelColor),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(q['threat'],
                                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12)),
                                  Text('Quarantined: ${q['quarantined_at']}',
                                      style: TextStyle(
                                          fontSize: 11,
                                          color: colorScheme.onSurface.withValues(alpha: 0.5))),
                                ],
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.restore, size: 18),
                              tooltip: 'Restore',
                              onPressed: () => _restoreFromQuarantine(index),
                            ),
                            IconButton(
                              icon: Icon(Icons.delete, size: 18, color: Colors.red.shade300),
                              tooltip: 'Delete',
                              onPressed: () => _deleteFromQuarantine(index),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildMonitorTab() {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Watched directories
          const Text('Watched Directories', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Column(
              children: [
                for (final dir in _watchedDirs)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        Icon(Icons.folder, size: 14, color: colorScheme.primary),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(dir,
                              style: const TextStyle(fontSize: 12, fontFamily: 'monospace')),
                        ),
                        Icon(Icons.circle, size: 8, color: Colors.green),
                      ],
                    ),
                  ),
                const SizedBox(height: 4),
                GestureDetector(
                  onTap: _simulateMonitorEvent,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.add, size: 14, color: colorScheme.primary),
                      const SizedBox(width: 4),
                      Text('Add Directory',
                          style: TextStyle(fontSize: 12, color: colorScheme.primary)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          AutoAdjustRow(
            alignment: WrapAlignment.spaceBetween,
            children: [
              const Text('Recent Events', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
              Row(
                children: [
                  FilledButton.tonal(
                    onPressed: _simulateMonitorEvent,
                    child: const Text('Simulate Event'),
                  ),
                  const SizedBox(width: 6),
                  Switch(
                    value: _realtimeProtection,
                    onChanged: (v) => setState(() => _realtimeProtection = v),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),

          Expanded(
            child: _monitorEvents.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.monitor_heart,
                            size: 48, color: colorScheme.onSurface.withValues(alpha: 0.2)),
                        const SizedBox(height: 8),
                        Text('No events yet',
                            style: TextStyle(color: colorScheme.onSurface.withValues(alpha: 0.4))),
                      ],
                    ),
                  )
                : ListView.builder(
                    itemCount: _monitorEvents.length,
                    itemBuilder: (context, index) {
                      final e = _monitorEvents[index];
                      final isThreat = e['status'] == 'threat';
                      return Container(
                        margin: const EdgeInsets.only(bottom: 4),
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                        decoration: BoxDecoration(
                          color: isThreat
                              ? Colors.red.withValues(alpha: 0.08)
                              : Colors.transparent,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              isThreat ? Icons.dangerous : Icons.check_circle_outline,
                              size: 16,
                              color: isThreat ? Colors.red : Colors.green,
                            ),
                            const SizedBox(width: 8),
                            Text(e['time'],
                                style: const TextStyle(fontSize: 11, fontFamily: 'monospace')),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                              decoration: BoxDecoration(
                                color: (e['type'] == 'created'
                                        ? Colors.blue
                                        : e['type'] == 'modified'
                                            ? Colors.orange
                                            : Colors.grey)
                                    .withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(3),
                              ),
                              child: Text(e['type'],
                                  style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold)),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(e['path'],
                                  style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
                                  overflow: TextOverflow.ellipsis),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
