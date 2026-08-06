import 'package:flutter/material.dart';
import 'dart:math';

class QuantumSimApp extends StatefulWidget {
  const QuantumSimApp({super.key});

  @override
  State<QuantumSimApp> createState() => _QuantumSimAppState();
}

class _QuantumSimAppState extends State<QuantumSimApp> {
  int _selectedTab = 0;
  String? _draggedGate;
  final List<Map<String, dynamic>> _circuitGates = [];
  int _gateCount = 0;
  int _circuitDepth = 0;
  double _fidelity = 100.0;
  final Random _random = Random();
  bool _simulationRunning = false;

  // Bloch sphere angles
  double _theta = 0.0;
  double _phi = 0.0;

  // Entanglement
  String _bellState = '|Φ+⟩';
  bool _entanglementCreated = false;
  final List<Map<String, String>> _measurements = [];

  // Probability amplitudes
  final List<double> _amplitudes = [0.5, 0.5, 0.0, 0.0];

  // Gate palette
  final List<String> _gates = ['H', 'X', 'Y', 'Z', 'CNOT', 'Toffoli', 'Phase', 'T'];
  final List<Color> _gateColors = [
    Colors.cyan,
    Colors.red,
    Colors.green,
    Colors.blue,
    Colors.orange,
    Colors.purple,
    Colors.pink,
    Colors.teal,
  ];

  final List<String> _qubitLabels = ['Q0', 'Q1', 'Q2', 'Q3'];
  final int _gridColumns = 12;

  @override
  void initState() {
    super.initState();
    _theta = _random.nextDouble() * pi;
    _phi = _random.nextDouble() * 2 * pi;
    _generateMeasurements();
  }

  void _generateMeasurements() {
    _measurements.clear();
    final states = ['|00⟩', '|01⟩', '|10⟩', '|11⟩'];
    for (final state in states) {
      _measurements.add({
        'state': state,
        'probability': '${(_random.nextDouble() * 100).toStringAsFixed(2)}%',
        'phase': '${(_random.nextDouble() * 360).toStringAsFixed(1)}°',
        'count': '${_random.nextInt(1000)}',
      });
    }
  }

  void _onGateDragStart(String gate) {
    _draggedGate = gate;
  }

  void _onGateDrop(int qubit, int position) {
    if (_draggedGate == null) return;
    setState(() {
      _circuitGates.add({
        'gate': _draggedGate,
        'qubit': qubit,
        'position': position,
      });
      _gateCount++;
      _circuitDepth = (position + 1 > _circuitDepth) ? position + 1 : _circuitDepth;
      _fidelity = max(70.0, 100.0 - _gateCount * 0.5);
      _draggedGate = null;
      _updateAmplitudes();
    });
  }

  void _updateAmplitudes() {
    for (int i = 0; i < 4; i++) {
      _amplitudes[i] = _random.nextDouble() * 0.8;
    }
    final total = _amplitudes.reduce((a, b) => a + b);
    for (int i = 0; i < 4; i++) {
      _amplitudes[i] /= total;
    }
  }

  void _runSimulation() {
    setState(() => _simulationRunning = true);
    _theta = _random.nextDouble() * pi;
    _phi = _random.nextDouble() * 2 * pi;
    _updateAmplitudes();
    _generateMeasurements();
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _simulationRunning = false);
    });
  }

  void _createBellState() {
    setState(() {
      _entanglementCreated = true;
      final states = ['|Φ+⟩', '|Φ-⟩', '|Ψ+⟩', '|Ψ-⟩'];
      _bellState = states[_random.nextInt(states.length)];
      _generateMeasurements();
    });
  }

  void _clearCircuit() {
    setState(() {
      _circuitGates.clear();
      _gateCount = 0;
      _circuitDepth = 0;
      _fidelity = 100.0;
      _entanglementCreated = false;
      for (int i = 0; i < 4; i++) {
        _amplitudes[i] = (i < 2) ? 0.5 : 0.0;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildTabBar(),
        Expanded(
          child: _selectedTab == 0
              ? _buildCircuitTab()
              : _selectedTab == 1
                  ? _buildStatesTab()
                  : _buildEntanglementTab(),
        ),
        _buildStatusBar(),
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
          _TabButton(
            label: 'Circuit',
            isSelected: _selectedTab == 0,
            onTap: () => setState(() => _selectedTab = 0),
          ),
          _TabButton(
            label: 'States',
            isSelected: _selectedTab == 1,
            onTap: () => setState(() => _selectedTab = 1),
          ),
          _TabButton(
            label: 'Entanglement',
            isSelected: _selectedTab == 2,
            onTap: () => setState(() => _selectedTab = 2),
          ),
          const Spacer(),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: FilledButton.icon(
              onPressed: _simulationRunning ? null : _runSimulation,
              icon: _simulationRunning
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.play_arrow, size: 18),
              label: Text(_simulationRunning ? 'Running...' : 'Run'),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 8.0),
            child: OutlinedButton.icon(
              onPressed: _clearCircuit,
              icon: const Icon(Icons.delete_outline, size: 18),
              label: const Text('Clear'),
            ),
          ),
        ],
      ),
    );
  }

  // ===================== CIRCUIT TAB =====================
  Widget _buildCircuitTab() {
    return Row(
      children: [
        // Gate Palette
        Container(
          width: 140,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            border: Border(
              right: BorderSide(
                color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
              ),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  'GATES',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                    letterSpacing: 1.2,
                  ),
                ),
              ),
              Expanded(
                child: ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  itemCount: _gates.length,
                  itemBuilder: (context, index) {
                    final gate = _gates[index];
                    final color = _gateColors[index];
                    return Draggable<String>(
                      data: gate,
                      onDragStarted: () => _onGateDragStart(gate),
                      feedback: Material(
                        color: Colors.transparent,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: color.withValues(alpha: 0.9),
                            borderRadius: BorderRadius.circular(6),
                            boxShadow: [
                              BoxShadow(
                                color: color.withValues(alpha: 0.4),
                                blurRadius: 8,
                              ),
                            ],
                          ),
                          child: Text(
                            gate,
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 13,
                            ),
                          ),
                        ),
                      ),
                      childWhenDragging: Opacity(
                        opacity: 0.3,
                        child: _buildGateChip(gate, color),
                      ),
                      child: _buildGateChip(gate, color),
                    );
                  },
                ),
              ),
            ],
          ),
        ),

        // Circuit Grid
        Expanded(
          child: Column(
            children: [
              // Timeline header
              Container(
                height: 32,
                padding: const EdgeInsets.only(left: 60),
                child: Row(
                  children: List.generate(_gridColumns, (i) {
                    return Container(
                      width: 64,
                      alignment: Alignment.center,
                      child: Text(
                        't$i',
                        style: TextStyle(
                          fontSize: 11,
                          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4),
                        ),
                      ),
                    );
                  }),
                ),
              ),
              // Qubit rows
              Expanded(
                child: ListView.builder(
                  itemCount: 4,
                  itemBuilder: (context, qubitIndex) {
                    return _buildQubitRow(qubitIndex);
                  },
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildGateChip(String gate, Color color) {
    return Container(
      width: 124,
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(4),
            ),
            alignment: Alignment.center,
            child: Text(
              gate.substring(0, 1),
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.bold,
                fontSize: 12,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            gate,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurface,
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQubitRow(int qubitIndex) {
    return Container(
      height: 48,
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.1),
          ),
        ),
      ),
      child: Row(
        children: [
          // Qubit label
          Container(
            width: 60,
            alignment: Alignment.center,
            child: Text(
              _qubitLabels[qubitIndex],
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
          ),
          // Grid cells
          Expanded(
            child: Row(
              children: List.generate(_gridColumns, (colIndex) {
                final gateOnCell = _circuitGates.where(
                  (g) => g['qubit'] == qubitIndex && g['position'] == colIndex,
                ).toList();
                return DragTarget<String>(
                  onWillAcceptWithDetails: (details) => true,
                  onAcceptWithDetails: (details) {
                    _onGateDrop(qubitIndex, colIndex);
                  },
                  builder: (context, candidateData, rejectedData) {
                    final isHovering = candidateData.isNotEmpty;
                    return Container(
                      width: 64,
                      height: 48,
                      decoration: BoxDecoration(
                        color: isHovering
                            ? Theme.of(context).colorScheme.primary.withValues(alpha: 0.15)
                            : Colors.transparent,
                        border: Border(
                          right: BorderSide(
                            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.1),
                          ),
                        ),
                      ),
                      alignment: Alignment.center,
                      child: gateOnCell.isNotEmpty
                          ? Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: _getGateColor(gateOnCell.first['gate']),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                gateOnCell.first['gate'],
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            )
                          : null,
                    );
                  },
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  Color _getGateColor(String? gate) {
    if (gate == null) return Colors.grey;
    final index = _gates.indexOf(gate);
    return index >= 0 ? _gateColors[index] : Colors.grey;
  }

  // ===================== STATES TAB =====================
  Widget _buildStatesTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Quantum States',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Bloch Sphere
              Expanded(
                child: _buildBlochSphere(),
              ),
              const SizedBox(width: 16),
              // Probability Amplitudes
              Expanded(
                child: _buildProbabilityChart(),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBlochSphere() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Text(
              'Bloch Sphere',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: 220,
              height: 220,
              child: CustomPaint(
                painter: _BlochSpherePainter(
                  theta: _theta,
                  phi: _phi,
                  primaryColor: Theme.of(context).colorScheme.primary,
                  outlineColor: Theme.of(context).colorScheme.outline,
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Column(
                  children: [
                    Text('θ = ${(_theta * 180 / pi).toStringAsFixed(1)}°',
                        style: const TextStyle(fontSize: 12)),
                    const SizedBox(height: 4),
                    Text('φ = ${(_phi * 180 / pi).toStringAsFixed(1)}°',
                        style: const TextStyle(fontSize: 12)),
                  ],
                ),
                const SizedBox(width: 16),
                FilledButton.tonal(
                  onPressed: () {
                    setState(() {
                      _theta = _random.nextDouble() * pi;
                      _phi = _random.nextDouble() * 2 * pi;
                    });
                  },
                  child: const Text('Randomize', style: TextStyle(fontSize: 12)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProbabilityChart() {
    final labels = ['|00⟩', '|01⟩', '|10⟩', '|11⟩'];
    final maxAmp = _amplitudes.reduce(max);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Probability Amplitudes',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 16),
            ...List.generate(4, (i) {
              final fraction = maxAmp > 0 ? _amplitudes[i] / maxAmp : 0.0;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  children: [
                    SizedBox(
                      width: 40,
                      child: Text(
                        labels[i],
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: fraction,
                          minHeight: 20,
                          backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            _amplitudeBarColor(i),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(
                      width: 50,
                      child: Text(
                        '${(_amplitudes[i] * 100).toStringAsFixed(1)}%',
                        style: const TextStyle(fontSize: 11),
                        textAlign: TextAlign.right,
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Color _amplitudeBarColor(int index) {
    const colors = [Colors.cyan, Colors.cyanAccent, Colors.lightBlue, Colors.lightBlueAccent];
    return colors[index];
  }

  // ===================== ENTANGLEMENT TAB =====================
  Widget _buildEntanglementTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Quantum Entanglement',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Bell State & Visualization
              Expanded(
                child: Column(
                  children: [
                    _buildBellStateCard(),
                    const SizedBox(height: 16),
                    _buildEntanglementVisualization(),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              // Measurements Table
              Expanded(
                child: _buildMeasurementsTable(),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBellStateCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.link, size: 18, color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Bell State',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _bellState,
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.onPrimaryContainer,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Center(
              child: FilledButton.icon(
                onPressed: _createBellState,
                icon: const Icon(Icons.add_link, size: 18),
                label: const Text('Create Bell State'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEntanglementVisualization() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Entanglement Map',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 180,
              child: CustomPaint(
                size: const Size(double.infinity, 180),
                painter: _EntanglementPainter(
                  created: _entanglementCreated,
                  primaryColor: Theme.of(context).colorScheme.primary,
                  outlineColor: Theme.of(context).colorScheme.outline,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMeasurementsTable() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Measurements',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 12),
            Table(
              columnWidths: const {
                0: FlexColumnWidth(1.2),
                1: FlexColumnWidth(1.5),
                2: FlexColumnWidth(1),
                3: FlexColumnWidth(1),
              },
              children: [
                _buildTableHeader(['State', 'Probability', 'Phase', 'Count']),
                ..._measurements.map((m) => TableRow(
                  children: [
                    _buildTableCell(m['state']!, bold: true),
                    _buildTableCell(m['probability']!),
                    _buildTableCell(m['phase']!),
                    _buildTableCell(m['count']!),
                  ],
                )),
              ],
            ),
          ],
        ),
      ),
    );
  }

  TableRow _buildTableHeader(List<String> headers) {
    return TableRow(
      children: headers.map((h) {
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text(
            h,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildTableCell(String text, {bool bold = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 12,
          fontWeight: bold ? FontWeight.w600 : FontWeight.normal,
        ),
      ),
    );
  }

  // ===================== STATUS BAR =====================
  Widget _buildStatusBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          top: BorderSide(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
          ),
        ),
      ),
      child: Row(
        children: [
          _statusChip('Qubits', '4', Colors.cyan),
          const SizedBox(width: 12),
          _statusChip('Gates', '$_gateCount', Colors.orange),
          const SizedBox(width: 12),
          _statusChip('Depth', '$_circuitDepth', Colors.green),
          const SizedBox(width: 12),
          _statusChip('Fidelity', '${_fidelity.toStringAsFixed(1)}%', Colors.purple),
          const Spacer(),
          if (_simulationRunning)
            const SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
        ],
      ),
    );
  }

  Widget _statusChip(String label, String value, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(
          '$label: $value',
          style: TextStyle(
            fontSize: 11,
            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
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

// ===================== BLOCH SPHERE PAINTER =====================
class _BlochSpherePainter extends CustomPainter {
  final double theta;
  final double phi;
  final Color primaryColor;
  final Color outlineColor;

  _BlochSpherePainter({
    required this.theta,
    required this.phi,
    required this.primaryColor,
    required this.outlineColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = min(size.width, size.height) / 2 - 20;

    // Draw sphere circle
    final circlePaint = Paint()
      ..color = outlineColor.withValues(alpha: 0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    canvas.drawCircle(center, radius, circlePaint);

    // Draw axes
    final axisPaint = Paint()
      ..color = outlineColor.withValues(alpha: 0.2)
      ..strokeWidth = 1;

    // X axis
    canvas.drawLine(
      Offset(center.dx - radius, center.dy),
      Offset(center.dx + radius, center.dy),
      axisPaint,
    );
    // Y axis (drawn as shorter for 3D effect)
    canvas.drawLine(
      Offset(center.dx, center.dy - radius),
      Offset(center.dx, center.dy + radius),
      axisPaint,
    );

    // Draw axis labels
    final labelStyle = TextStyle(
      color: outlineColor.withValues(alpha: 0.5),
      fontSize: 12,
      fontWeight: FontWeight.w500,
    );
    final tp0 = TextPainter(
      text: TextSpan(text: '|0⟩', style: labelStyle),
      textDirection: TextDirection.ltr,
    )..layout();
    tp0.paint(canvas, Offset(center.dx - 12, center.dy - radius - 18));

    final tp1 = TextPainter(
      text: TextSpan(text: '|1⟩', style: labelStyle),
      textDirection: TextDirection.ltr,
    )..layout();
    tp1.paint(canvas, Offset(center.dx - 12, center.dy + radius + 6));

    // Draw state vector arrow
    final arrowEnd = Offset(
      center.dx + radius * 0.8 * sin(theta) * cos(phi),
      center.dy - radius * 0.8 * cos(theta),
    );

    final arrowPaint = Paint()
      ..color = primaryColor
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(center, arrowEnd, arrowPaint);

    // Arrowhead
    final arrowHeadPaint = Paint()
      ..color = primaryColor
      ..style = PaintingStyle.fill;
    final angle = atan2(arrowEnd.dy - center.dy, arrowEnd.dx - center.dx);
    final headSize = 8.0;
    final path = Path()
      ..moveTo(arrowEnd.dx, arrowEnd.dy)
      ..lineTo(
        arrowEnd.dx - headSize * cos(angle - 0.4),
        arrowEnd.dy - headSize * sin(angle - 0.4),
      )
      ..lineTo(
        arrowEnd.dx - headSize * cos(angle + 0.4),
        arrowEnd.dy - headSize * sin(angle + 0.4),
      )
      ..close();
    canvas.drawPath(path, arrowHeadPaint);

    // State dot
    canvas.drawCircle(
      arrowEnd,
      5,
      Paint()..color = primaryColor,
    );
  }

  @override
  bool shouldRepaint(covariant _BlochSpherePainter oldDelegate) =>
      theta != oldDelegate.theta || phi != oldDelegate.phi;
}

// ===================== ENTANGLEMENT PAINTER =====================
class _EntanglementPainter extends CustomPainter {
  final bool created;
  final Color primaryColor;
  final Color outlineColor;

  _EntanglementPainter({
    required this.created,
    required this.primaryColor,
    required this.outlineColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final qubitRadius = 24.0;

    // Draw 4 qubit circles
    final positions = [
      Offset(center.dx - 100, center.dy),
      Offset(center.dx - 33, center.dy),
      Offset(center.dx + 33, center.dy),
      Offset(center.dx + 100, center.dy),
    ];

    final labels = ['Q0', 'Q1', 'Q2', 'Q3'];

    // Entanglement lines
    if (created) {
      final linePaint = Paint()
        ..color = primaryColor.withValues(alpha: 0.6)
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke;

      // Wavy line between Q0 and Q1
      final path01 = Path()..moveTo(positions[0].dx + qubitRadius, positions[0].dy);
      for (double i = 0; i <= 1; i += 0.05) {
        final x = positions[0].dx + qubitRadius + i * (positions[1].dx - positions[0].dx - 2 * qubitRadius);
        final y = positions[0].dy + sin(i * pi * 4) * 8;
        path01.lineTo(x, y);
      }
      canvas.drawPath(path01, linePaint);

      // Wavy line between Q2 and Q3
      final path23 = Path()..moveTo(positions[2].dx + qubitRadius, positions[2].dy);
      for (double i = 0; i <= 1; i += 0.05) {
        final x = positions[2].dx + qubitRadius + i * (positions[3].dx - positions[2].dx - 2 * qubitRadius);
        final y = positions[2].dy + sin(i * pi * 4) * 8;
        path23.lineTo(x, y);
      }
      canvas.drawPath(path23, linePaint);

      // Glow effects
      for (final pos in [positions[0], positions[3]]) {
        canvas.drawCircle(
          pos,
          qubitRadius + 8,
          Paint()
            ..color = primaryColor.withValues(alpha: 0.1)
            ..style = PaintingStyle.fill,
        );
      }
    }

    // Draw qubit circles
    for (int i = 0; i < 4; i++) {
      final paint = Paint()
        ..color = created && (i == 0 || i == 3)
            ? primaryColor.withValues(alpha: 0.3)
            : outlineColor.withValues(alpha: 0.2)
        ..style = PaintingStyle.fill;
      canvas.drawCircle(positions[i], qubitRadius, paint);

      final strokePaint = Paint()
        ..color = created && (i == 0 || i == 3)
            ? primaryColor
            : outlineColor.withValues(alpha: 0.5)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5;
      canvas.drawCircle(positions[i], qubitRadius, strokePaint);

      // Label
      final labelPainter = TextPainter(
        text: TextSpan(
          text: labels[i],
          style: TextStyle(
            color: created && (i == 0 || i == 3)
                ? primaryColor
                : outlineColor,
            fontSize: 13,
            fontWeight: FontWeight.bold,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      labelPainter.paint(
        canvas,
        Offset(
          positions[i].dx - labelPainter.width / 2,
          positions[i].dy - labelPainter.height / 2,
        ),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _EntanglementPainter oldDelegate) =>
      created != oldDelegate.created;
}
