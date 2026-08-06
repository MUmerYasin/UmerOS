import 'package:flutter/material.dart';
import 'dart:math';

class SecurityApp extends StatefulWidget {
  const SecurityApp({super.key});

  @override
  State<SecurityApp> createState() => _SecurityAppState();
}

class _SecurityAppState extends State<SecurityApp> {
  int _selectedTab = 0;
  final Random _random = Random();

  // Dashboard
  int _threatLevel = 0; // 0=green, 1=yellow, 2=red
  double _scanProgress = 0.0;
  String _lastScanTime = 'Never';
  int _detectedThreats = 0;
  bool _scanning = false;

  // Firewall
  final List<Map<String, String>> _firewallRules = [
    {'source': '192.168.1.0/24', 'dest': '10.0.0.1', 'port': '22', 'action': 'Allow', 'enabled': 'true'},
    {'source': '0.0.0.0/0', 'dest': '10.0.0.5', 'port': '443', 'action': 'Allow', 'enabled': 'true'},
    {'source': '10.0.0.0/8', 'dest': '*', 'port': '3306', 'action': 'Deny', 'enabled': 'true'},
    {'source': '172.16.0.0/12', 'dest': '10.0.0.10', 'port': '8080', 'action': 'Allow', 'enabled': 'false'},
    {'source': '0.0.0.0/0', 'dest': '*', 'port': '23', 'action': 'Deny', 'enabled': 'true'},
  ];
  bool _firewallEnabled = true;

  // Encryption
  String _selectedAlgorithm = 'AES-256';
  final List<String> _algorithms = ['AES-256', 'RSA-2048', 'ChaCha20'];
  String _selectedFile = 'None';
  bool _encrypting = false;

  // Audit Log
  final List<Map<String, String>> _auditLog = [];

  // Sandbox
  final List<Map<String, dynamic>> _sandboxProcesses = [
    {'name': 'untrusted-app-1', 'pid': '4521', 'cpu': '12%', 'mem': '45MB', 'status': 'running'},
    {'name': 'sandbox-browser', 'pid': '4522', 'cpu': '8%', 'mem': '128MB', 'status': 'running'},
    {'name': 'test-executor', 'pid': '4523', 'cpu': '3%', 'mem': '12MB', 'status': 'running'},
  ];

  @override
  void initState() {
    super.initState();
    _generateAuditLog();
  }

  void _generateAuditLog() {
    final events = [
      {'time': '14:32:01', 'type': 'INFO', 'desc': 'System boot completed successfully'},
      {'time': '14:32:05', 'type': 'INFO', 'desc': 'Firewall rules loaded (5 rules)'},
      {'time': '14:33:12', 'type': 'WARN', 'desc': 'Failed login attempt from 192.168.1.50'},
      {'time': '14:35:44', 'type': 'INFO', 'desc': 'Security scan initiated by admin'},
      {'time': '14:36:01', 'type': 'ERROR', 'desc': 'Certificate validation failed for api.example.com'},
      {'time': '14:37:22', 'type': 'INFO', 'desc': 'Firewall rule added: Allow TCP 443 from 0.0.0.0/0'},
      {'time': '14:38:55', 'type': 'WARN', 'desc': 'Unusual outbound traffic detected on port 6667'},
      {'time': '14:40:10', 'type': 'INFO', 'desc': 'Sandbox process started: untrusted-app-1 (PID 4521)'},
      {'time': '14:41:33', 'type': 'ERROR', 'desc': 'Malware signature detected in /tmp/suspicious.bin'},
      {'time': '14:42:01', 'type': 'INFO', 'desc': 'File quarantined: /tmp/suspicious.bin'},
    ];
    _auditLog.addAll(events);
  }

  void _runScan(bool full) async {
    setState(() {
      _scanning = true;
      _scanProgress = 0.0;
    });
    for (int i = 0; i <= 100; i += full ? 2 : 5) {
      await Future.delayed(const Duration(milliseconds: 50));
      if (!mounted) return;
      setState(() => _scanProgress = i.toDouble());
    }
    setState(() {
      _scanning = false;
      _detectedThreats = full ? _random.nextInt(5) : _random.nextInt(2);
      _threatLevel = _detectedThreats == 0 ? 0 : _detectedThreats < 3 ? 1 : 2;
      final now = DateTime.now();
      _lastScanTime = '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}:${now.second.toString().padLeft(2, '0')}';
      _auditLog.insert(0, {
        'time': _lastScanTime,
        'type': _detectedThreats > 0 ? 'WARN' : 'INFO',
        'desc': '${full ? "Full" : "Quick"} scan completed: $_detectedThreats threats found',
      });
    });
  }

  void _addFirewallRule() {
    showDialog(
      context: context,
      builder: (context) {
        final sourceController = TextEditingController(text: '0.0.0.0/0');
        final destController = TextEditingController(text: '*');
        final portController = TextEditingController(text: '80');
        String action = 'Allow';
        return AlertDialog(
          title: const Text('Add Firewall Rule'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: sourceController, decoration: const InputDecoration(labelText: 'Source')),
              TextField(controller: destController, decoration: const InputDecoration(labelText: 'Destination')),
              TextField(controller: portController, decoration: const InputDecoration(labelText: 'Port')),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: action,
                items: ['Allow', 'Deny'].map((a) => DropdownMenuItem(value: a, child: Text(a))).toList(),
                onChanged: (v) => setState(() => action = v ?? 'Allow'),
                decoration: const InputDecoration(labelText: 'Action'),
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(
              onPressed: () {
                setState(() {
                  _firewallRules.add({
                    'source': sourceController.text,
                    'dest': destController.text,
                    'port': portController.text,
                    'action': action,
                    'enabled': 'true',
                  });
                });
                Navigator.pop(context);
              },
              child: const Text('Add'),
            ),
          ],
        );
      },
    );
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
                  ? _buildFirewallTab()
                  : _selectedTab == 2
                      ? _buildEncryptionTab()
                      : _selectedTab == 3
                          ? _buildAuditLogTab()
                          : _buildSandboxTab(),
        ),
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
      child: Row(
        children: [
          _TabButton(label: 'Dashboard', isSelected: _selectedTab == 0, onTap: () => setState(() => _selectedTab = 0)),
          _TabButton(label: 'Firewall', isSelected: _selectedTab == 1, onTap: () => setState(() => _selectedTab = 1)),
          _TabButton(label: 'Encryption', isSelected: _selectedTab == 2, onTap: () => setState(() => _selectedTab = 2)),
          _TabButton(label: 'Audit Log', isSelected: _selectedTab == 3, onTap: () => setState(() => _selectedTab = 3)),
          _TabButton(label: 'Sandbox', isSelected: _selectedTab == 4, onTap: () => setState(() => _selectedTab = 4)),
        ],
      ),
    );
  }

  // ===================== DASHBOARD TAB =====================
  Widget _buildDashboardTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Security Dashboard',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Theme.of(context).colorScheme.onSurface),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              // Threat Level
              Expanded(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      children: [
                        Text('Threat Level', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Theme.of(context).colorScheme.onSurface)),
                        const SizedBox(height: 16),
                        SizedBox(
                          width: 100,
                          height: 100,
                          child: CustomPaint(
                            painter: _ThreatLevelPainter(
                              level: _threatLevel,
                            ),
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _threatLevel == 0 ? 'SECURE' : _threatLevel == 1 ? 'CAUTION' : 'CRITICAL',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: _threatLevel == 0 ? Colors.green : _threatLevel == 1 ? Colors.amber : Colors.red,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              // Scan Status
              Expanded(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Scan Status', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Theme.of(context).colorScheme.onSurface)),
                        const SizedBox(height: 16),
                        if (_scanning) ...[
                          LinearProgressIndicator(value: _scanProgress / 100),
                          const SizedBox(height: 8),
                          Text('Scanning... ${_scanProgress.toInt()}%', style: const TextStyle(fontSize: 12)),
                        ] else ...[
                          Row(
                            children: [
                              const Icon(Icons.check_circle, color: Colors.green, size: 16),
                              const SizedBox(width: 4),
                              Text('Last scan: $_lastScanTime', style: const TextStyle(fontSize: 12)),
                            ],
                          ),
                        ],
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            const Icon(Icons.warning_amber, color: Colors.amber, size: 16),
                            const SizedBox(width: 4),
                            Text('Threats: $_detectedThreats', style: const TextStyle(fontSize: 12)),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              // Quick Actions
              Expanded(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Quick Actions', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Theme.of(context).colorScheme.onSurface)),
                        const SizedBox(height: 16),
                        FilledButton.icon(
                          onPressed: _scanning ? null : () => _runScan(false),
                          icon: const Icon(Icons.speed, size: 18),
                          label: const Text('Quick Scan'),
                        ),
                        const SizedBox(height: 8),
                        OutlinedButton.icon(
                          onPressed: _scanning ? null : () => _runScan(true),
                          icon: const Icon(Icons.fullscreen, size: 18),
                          label: const Text('Full Scan'),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Scan Progress Bar
          if (_scanning)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Scan Progress', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    LinearProgressIndicator(value: _scanProgress / 100, minHeight: 8),
                    const SizedBox(height: 4),
                    Text('${_scanProgress.toInt()}% complete', style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6))),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  // ===================== FIREWALL TAB =====================
  Widget _buildFirewallTab() {
    return Column(
      children: [
        // Toolbar
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            border: Border(bottom: BorderSide(color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2))),
          ),
          child: Row(
            children: [
              Switch(
                value: _firewallEnabled,
                onChanged: (v) => setState(() => _firewallEnabled = v),
              ),
              const SizedBox(width: 8),
              Text('Firewall ${_firewallEnabled ? "Enabled" : "Disabled"}', style: const TextStyle(fontSize: 13)),
              const Spacer(),
              FilledButton.icon(
                onPressed: _addFirewallRule,
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Add Rule'),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                onPressed: () {
                  setState(() => _firewallRules.removeLast());
                },
                icon: const Icon(Icons.remove, size: 18),
                label: const Text('Remove'),
              ),
            ],
          ),
        ),
        // Rules Table
        Expanded(
          child: SingleChildScrollView(
            child: Table(
              columnWidths: const {
                0: FlexColumnWidth(0.5),
                1: FlexColumnWidth(2),
                2: FlexColumnWidth(2),
                3: FlexColumnWidth(1),
                4: FlexColumnWidth(1),
                5: FlexColumnWidth(1),
              },
              children: [
                _buildFirewallTableHeader(),
                ..._firewallRules.asMap().entries.map((entry) {
                  return _buildFirewallRow(entry.key, entry.value);
                }),
              ],
            ),
          ),
        ),
      ],
    );
  }

  TableRow _buildFirewallTableHeader() {
    return TableRow(
      decoration: BoxDecoration(color: Theme.of(context).colorScheme.surfaceContainerHighest),
      children: ['#', 'Source', 'Destination', 'Port', 'Action', 'Status'].map((h) {
        return Padding(
          padding: const EdgeInsets.all(10),
          child: Text(h, style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7))),
        );
      }).toList(),
    );
  }

  TableRow _buildFirewallRow(int index, Map<String, String> rule) {
    final enabled = rule['enabled'] == 'true';
    return TableRow(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.1))),
      ),
      children: [
        Padding(
          padding: const EdgeInsets.all(10),
          child: Text('${index + 1}', style: const TextStyle(fontSize: 12)),
        ),
        Padding(
          padding: const EdgeInsets.all(10),
          child: Text(rule['source']!, style: const TextStyle(fontSize: 12, fontFamily: 'monospace')),
        ),
        Padding(
          padding: const EdgeInsets.all(10),
          child: Text(rule['dest']!, style: const TextStyle(fontSize: 12, fontFamily: 'monospace')),
        ),
        Padding(
          padding: const EdgeInsets.all(10),
          child: Text(rule['port']!, style: const TextStyle(fontSize: 12)),
        ),
        Padding(
          padding: const EdgeInsets.all(10),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: rule['action'] == 'Allow' ? Colors.green.withValues(alpha: 0.2) : Colors.red.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              rule['action']!,
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: rule['action'] == 'Allow' ? Colors.green : Colors.red),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(10),
          child: Switch(
            value: enabled,
            onChanged: (v) {
              setState(() => rule['enabled'] = v ? 'true' : 'false');
            },
          ),
        ),
      ],
    );
  }

  // ===================== ENCRYPTION TAB =====================
  Widget _buildEncryptionTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('File Encryption', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Theme.of(context).colorScheme.onSurface)),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Encrypt / Decrypt File', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 12),
                        Text('Selected File:', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6))),
                        const SizedBox(height: 4),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Theme.of(context).colorScheme.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(_selectedFile, style: const TextStyle(fontSize: 13, fontFamily: 'monospace')),
                        ),
                        const SizedBox(height: 12),
                        FilledButton.tonalIcon(
                          onPressed: () {
                            setState(() => _selectedFile = '/home/user/documents/secret.txt');
                          },
                          icon: const Icon(Icons.folder_open, size: 18),
                          label: const Text('Select File'),
                        ),
                        const SizedBox(height: 16),
                        DropdownButtonFormField<String>(
                          initialValue: _selectedAlgorithm,
                          items: _algorithms.map((a) => DropdownMenuItem(value: a, child: Text(a))).toList(),
                          onChanged: (v) => setState(() => _selectedAlgorithm = v ?? 'AES-256'),
                          decoration: InputDecoration(
                            labelText: 'Algorithm',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                          ),
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            FilledButton.icon(
                              onPressed: _encrypting ? null : () {
                                setState(() => _encrypting = true);
                                Future.delayed(const Duration(seconds: 2), () {
                                  if (mounted) setState(() => _encrypting = false);
                                });
                              },
                              icon: _encrypting
                                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                                  : const Icon(Icons.lock, size: 18),
                              label: const Text('Encrypt'),
                            ),
                            const SizedBox(width: 8),
                            OutlinedButton.icon(
                              onPressed: () {},
                              icon: const Icon(Icons.lock_open, size: 18),
                              label: const Text('Decrypt'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Key Management', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 12),
                        _buildKeyItem('Primary Key', 'AES-256', '2025-01-15'),
                        _buildKeyItem('Backup Key', 'RSA-2048', '2025-01-15'),
                        _buildKeyItem('Recovery Key', 'ChaCha20', '2024-12-01'),
                        const SizedBox(height: 12),
                        FilledButton.tonal(
                          onPressed: () {},
                          child: const Text('Generate New Key', style: TextStyle(fontSize: 12)),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildKeyItem(String name, String algo, String date) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        children: [
          Icon(Icons.vpn_key, size: 16, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 8),
          Expanded(child: Text(name, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500))),
          Text(algo, style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6))),
          const SizedBox(width: 12),
          Text(date, style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4))),
        ],
      ),
    );
  }

  // ===================== AUDIT LOG TAB =====================
  Widget _buildAuditLogTab() {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            border: Border(bottom: BorderSide(color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2))),
          ),
          child: Row(
            children: [
              Icon(Icons.history, size: 16, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              Text('Audit Log (${_auditLog.length} entries)', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              const Spacer(),
              OutlinedButton.icon(
                onPressed: () => setState(() => _auditLog.clear()),
                icon: const Icon(Icons.delete_outline, size: 16),
                label: const Text('Clear', style: TextStyle(fontSize: 12)),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(8),
            itemCount: _auditLog.length,
            itemBuilder: (context, index) {
              final entry = _auditLog[index];
              final type = entry['type']!;
              final color = type == 'ERROR' ? Colors.red : type == 'WARN' ? Colors.amber : Colors.green;
              final icon = type == 'ERROR' ? Icons.error : type == 'WARN' ? Icons.warning : Icons.info;
              return Card(
                margin: const EdgeInsets.symmetric(vertical: 2),
                child: ListTile(
                  leading: Icon(icon, color: color, size: 18),
                  title: Text(entry['desc']!, style: const TextStyle(fontSize: 12)),
                  subtitle: Text(entry['time']!, style: TextStyle(fontSize: 10, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5))),
                  dense: true,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  // ===================== SANDBOX TAB =====================
  Widget _buildSandboxTab() {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            border: Border(bottom: BorderSide(color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2))),
          ),
          child: Row(
            children: [
              Icon(Icons.security, size: 16, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              Text('Sandboxed Processes (${_sandboxProcesses.length})', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              const Spacer(),
              FilledButton.icon(
                onPressed: () {
                  setState(() {
                    _sandboxProcesses.add({
                      'name': 'sandbox-${_random.nextInt(9999)}',
                      'pid': '${4600 + _random.nextInt(400)}',
                      'cpu': '${_random.nextInt(20)}%',
                      'mem': '${_random.nextInt(200)}MB',
                      'status': 'running',
                    });
                  });
                },
                icon: const Icon(Icons.play_arrow, size: 18),
                label: const Text('Launch'),
              ),
            ],
          ),
        ),
        Expanded(
          child: SingleChildScrollView(
            child: Table(
              columnWidths: const {
                0: FlexColumnWidth(2),
                1: FlexColumnWidth(1),
                2: FlexColumnWidth(1),
                3: FlexColumnWidth(1),
                4: FlexColumnWidth(1.5),
                5: FlexColumnWidth(1),
              },
              children: [
                _buildSandboxTableHeader(),
                ..._sandboxProcesses.asMap().entries.map((entry) {
                  return _buildSandboxRow(entry.key, entry.value);
                }),
              ],
            ),
          ),
        ),
      ],
    );
  }

  TableRow _buildSandboxTableHeader() {
    return TableRow(
      decoration: BoxDecoration(color: Theme.of(context).colorScheme.surfaceContainerHighest),
      children: ['Process', 'PID', 'CPU', 'Memory', 'Resource Limit', 'Action'].map((h) {
        return Padding(
          padding: const EdgeInsets.all(10),
          child: Text(h, style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7))),
        );
      }).toList(),
    );
  }

  TableRow _buildSandboxRow(int index, Map<String, dynamic> proc) {
    return TableRow(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.1))),
      ),
      children: [
        Padding(
          padding: const EdgeInsets.all(10),
          child: Text(proc['name'], style: const TextStyle(fontSize: 12, fontFamily: 'monospace')),
        ),
        Padding(padding: const EdgeInsets.all(10), child: Text(proc['pid'], style: const TextStyle(fontSize: 12))),
        Padding(padding: const EdgeInsets.all(10), child: Text(proc['cpu'], style: const TextStyle(fontSize: 12))),
        Padding(padding: const EdgeInsets.all(10), child: Text(proc['mem'], style: const TextStyle(fontSize: 12))),
        Padding(
          padding: const EdgeInsets.all(10),
          child: Text('500MB / 2 CPU', style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6))),
        ),
        Padding(
          padding: const EdgeInsets.all(10),
          child: IconButton(
            icon: const Icon(Icons.stop_circle, color: Colors.red, size: 18),
            onPressed: () {
              setState(() => _sandboxProcesses.removeAt(index));
            },
          ),
        ),
      ],
    );
  }
}

// ===================== TAB BUTTON =====================
class _TabButton extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _TabButton({required this.label, required this.isSelected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: isSelected ? Theme.of(context).colorScheme.primary : Colors.transparent, width: 2),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
            color: isSelected ? Theme.of(context).colorScheme.primary : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
          ),
        ),
      ),
    );
  }
}

// ===================== THREAT LEVEL PAINTER =====================
class _ThreatLevelPainter extends CustomPainter {
  final int level;

  _ThreatLevelPainter({required this.level});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = min(size.width, size.height) / 2 - 8;

    // Outer ring
    final ringPaint = Paint()
      ..color = _getColor().withValues(alpha: 0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 8;
    canvas.drawCircle(center, radius, ringPaint);

    // Inner fill
    final fillPaint = Paint()
      ..color = _getColor().withValues(alpha: 0.15)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(center, radius - 8, fillPaint);

    // Pulse effect
    final pulsePaint = Paint()
      ..color = _getColor().withValues(alpha: 0.1)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(center, radius + 4, pulsePaint);

    // Icon in center
    final icon = level == 0 ? Icons.shield : level == 1 ? Icons.warning : Icons.dangerous;
    final iconPainter = TextPainter(
      text: TextSpan(
        text: String.fromCharCode(icon.codePoint),
        style: TextStyle(
          fontSize: 32,
          color: _getColor(),
          fontFamily: icon.fontFamily,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    iconPainter.paint(
      canvas,
      Offset(center.dx - iconPainter.width / 2, center.dy - iconPainter.height / 2),
    );
  }

  Color _getColor() {
    switch (level) {
      case 0: return Colors.green;
      case 1: return Colors.amber;
      case 2: return Colors.red;
      default: return Colors.green;
    }
  }

  @override
  bool shouldRepaint(covariant _ThreatLevelPainter oldDelegate) => level != oldDelegate.level;
}
