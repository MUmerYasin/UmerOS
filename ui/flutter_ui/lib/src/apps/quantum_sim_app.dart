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
    Future.delayed(const Duration(seconds: 1), () {
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
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.surface,
      body: Column(
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
      ),
    );
  }

  Widget _buildTabBar() {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHigh,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.3),
          ),
        ),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
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
            const SizedBox(width: 12),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
              child: FilledButton.icon(
                onPressed: _simulationRunning ? null : _runSimulation,
                icon: _simulationRunning
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.play_arrow, size: 16),
                label: Text(_simulationRunning ? 'Running...' : 'Run'),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
              child: OutlinedButton.icon(
                onPressed: _clearCircuit,
                icon: const Icon(Icons.delete_outline, size: 16),
                label: const Text('Clear'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ===================== CIRCUIT TAB =====================
  Widget _buildCircuitTab() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isNarrow = constraints.maxWidth < 600;

        Widget palette = Container(
          width: isNarrow ? double.infinity : 130,
          height: isNarrow ? 70 : null,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerLow,
            border: Border(
              right: BorderSide(
                color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.2),
              ),
              bottom: BorderSide(
                color: isNarrow
                    ? Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.2)
                    : Colors.transparent,
              ),
            ),
          ),
          child: ListView.builder(
            scrollDirection: isNarrow ? Axis.horizontal : Axis.vertical,
            padding: const EdgeInsets.all(6),
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
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.9),
                      borderRadius: BorderRadius.circular(6),
                      boxShadow: [
                        BoxShadow(color: color.withValues(alpha: 0.4), blurRadius: 8),
                      ],
                    ),
                    child: Text(
                      gate,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
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
        );

        Widget grid = Expanded(
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SingleChildScrollView(
              scrollDirection: Axis.vertical,
              child: SizedBox(
                width: 60 + _gridColumns * 60.0,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Timeline header
                    Container(
                      height: 28,
                      padding: const EdgeInsets.only(left: 60),
                      child: Row(
                        children: List.generate(_gridColumns, (i) {
                          return SizedBox(
                            width: 60,
                            child: Center(
                              child: Text(
                                't$i',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                                ),
                              ),
                            ),
                          );
                        }),
                      ),
                    ),
                    // Qubit rows
                    ...List.generate(4, (qubitIndex) => _buildQubitRow(qubitIndex)),
                  ],
                ),
              ),
            ),
          ),
        );

        if (isNarrow) {
          return Column(
            children: [
              palette,
              grid,
            ],
          );
        }

        return Row(
          children: [
            palette,
            grid,
          ],
        );
      },
    );
  }

  Widget _buildGateChip(String gate, Color color) {
    return Container(
      margin: const EdgeInsets.all(3),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 22,
            height: 22,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.25),
              borderRadius: BorderRadius.circular(4),
            ),
            alignment: Alignment.center,
            child: Text(
              gate.substring(0, 1),
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.bold,
                fontSize: 11,
              ),
            ),
          ),
          const SizedBox(width: 6),
          Text(
            gate,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurface,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQubitRow(int qubitIndex) {
    return Container(
      height: 46,
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.15),
          ),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
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
          ...List.generate(_gridColumns, (colIndex) {
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
                  width: 60,
                  height: 46,
                  decoration: BoxDecoration(
                    color: isHovering
                        ? Theme.of(context).colorScheme.primary.withValues(alpha: 0.15)
                        : Colors.transparent,
                    border: Border(
                      right: BorderSide(
                        color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.15),
                      ),
                    ),
                  ),
                  alignment: Alignment.center,
                  child: gateOnCell.isNotEmpty
                      ? Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                          decoration: BoxDecoration(
                            color: _getGateColor(gateOnCell.first['gate']),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            gateOnCell.first['gate'],
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        )
                      : null,
                );
              },
            );
          }),
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
    return LayoutBuilder(
      builder: (context, constraints) {
        final isNarrow = constraints.maxWidth < 650;

        final bloch = _buildBlochSphere();
        final prob = _buildProbabilityChart();

        return SingleChildScrollView(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Quantum State Visualizer',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 12),
              if (isNarrow)
                Column(
                  children: [
                    bloch,
                    const SizedBox(height: 12),
                    prob,
                  ],
                )
              else
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: bloch),
                    const SizedBox(width: 12),
                    Expanded(child: prob),
                  ],
                ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildBlochSphere() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Text(
              'Bloch Sphere',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: 180,
              height: 180,
              child: CustomPaint(
                painter: _BlochSpherePainter(
                  theta: _theta,
                  phi: _phi,
                  primaryColor: Theme.of(context).colorScheme.primary,
                  outlineColor: Theme.of(context).colorScheme.outline,
                ),
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              alignment: WrapAlignment.center,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 12,
              children: [
                Text('θ = ${(_theta * 180 / pi).toStringAsFixed(1)}°', style: const TextStyle(fontSize: 11)),
                Text('φ = ${(_phi * 180 / pi).toStringAsFixed(1)}°', style: const TextStyle(fontSize: 11)),
                FilledButton.tonal(
                  onPressed: () {
                    setState(() {
                      _theta = _random.nextDouble() * pi;
                      _phi = _random.nextDouble() * 2 * pi;
                    });
                  },
                  child: const Text('Randomize', style: TextStyle(fontSize: 11)),
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
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Probability Amplitudes',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 12),
            ...List.generate(4, (i) {
              final fraction = maxAmp > 0 ? _amplitudes[i] / maxAmp : 0.0;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    SizedBox(
                      width: 36,
                      child: Text(
                        labels[i],
                        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: fraction,
                          minHeight: 16,
                          backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
                          valueColor: AlwaysStoppedAnimation<Color>(_amplitudeBarColor(i)),
                        ),
                      ),
                    ),
                    const SizedBox(width: 6),
                    SizedBox(
                      width: 44,
                      child: Text(
                        '${(_amplitudes[i] * 100).toStringAsFixed(1)}%',
                        style: const TextStyle(fontSize: 10),
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
    return LayoutBuilder(
      builder: (context, constraints) {
        final isNarrow = constraints.maxWidth < 650;

        final bell = Column(
          children: [
            _buildBellStateCard(),
            const SizedBox(height: 12),
            _buildEntanglementVisualization(),
          ],
        );
        final meas = _buildMeasurementsTable();

        return SingleChildScrollView(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Quantum Entanglement',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 12),
              if (isNarrow)
                Column(
                  children: [
                    bell,
                    const SizedBox(height: 12),
                    meas,
                  ],
                )
              else
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: bell),
                    const SizedBox(width: 12),
                    Expanded(child: meas),
                  ],
                ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildBellStateCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.link, size: 16, color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 6),
                Text(
                  'Bell State',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _bellState,
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.onPrimaryContainer,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Center(
              child: FilledButton.icon(
                onPressed: _createBellState,
                icon: const Icon(Icons.add_link, size: 16),
                label: const Text('Create Bell State', style: TextStyle(fontSize: 11)),
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
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Entanglement Map',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 8),
            SizedBox(
              height: 140,
              child: CustomPaint(
                size: const Size(double.infinity, 140),
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
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Measurements',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 8),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                columnSpacing: 16,
                dataRowMinHeight: 32,
                dataRowMaxHeight: 36,
                headingRowHeight: 36,
                columns: const [
                  DataColumn(label: Text('State', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold))),
                  DataColumn(label: Text('Prob', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold))),
                  DataColumn(label: Text('Phase', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold))),
                  DataColumn(label: Text('Count', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold))),
                ],
                rows: _measurements.map((m) {
                  return DataRow(cells: [
                    DataCell(Text(m['state']!, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold))),
                    DataCell(Text(m['probability']!, style: const TextStyle(fontSize: 11))),
                    DataCell(Text(m['phase']!, style: const TextStyle(fontSize: 11))),
                    DataCell(Text(m['count']!, style: const TextStyle(fontSize: 11))),
                  ]);
                }).toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusBar() {
    return Container(
      height: 28,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          top: BorderSide(
            color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.3),
          ),
        ),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            Text('Gates: $_gateCount', style: const TextStyle(fontSize: 11)),
            const SizedBox(width: 16),
            Text('Depth: $_circuitDepth', style: const TextStyle(fontSize: 11)),
            const SizedBox(width: 16),
            Text('Fidelity: ${_fidelity.toStringAsFixed(1)}%', style: const TextStyle(fontSize: 11)),
            const SizedBox(width: 16),
            Text(
              _entanglementCreated ? 'Entangled: Yes' : 'Entangled: No',
              style: TextStyle(
                fontSize: 11,
                color: _entanglementCreated ? Colors.green : Colors.orange,
              ),
            ),
          ],
        ),
      ),
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
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
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
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
            color: isSelected
                ? Theme.of(context).colorScheme.primary
                : Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

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
    final radius = min(size.width, size.height) / 2 - 10;

    final paintSphere = Paint()
      ..color = outlineColor.withValues(alpha: 0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    canvas.drawCircle(center, radius, paintSphere);

    // Draw equator
    final equatorRect = Rect.fromCenter(
      center: center,
      width: radius * 2,
      height: radius * 0.6,
    );
    canvas.drawOval(equatorRect, paintSphere);

    // Draw state vector
    final r = radius * 0.85;
    final x = center.dx + r * sin(theta) * cos(phi);
    final y = center.dy - r * cos(theta);

    final vectorPaint = Paint()
      ..color = primaryColor
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round;

    canvas.drawLine(center, Offset(x, y), vectorPaint);
    canvas.drawCircle(Offset(x, y), 5, Paint()..color = primaryColor);
  }

  @override
  bool shouldRepaint(covariant _BlochSpherePainter oldDelegate) =>
      oldDelegate.theta != theta || oldDelegate.phi != phi;
}

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
    final q0 = Offset(size.width * 0.25, size.height * 0.5);
    final q1 = Offset(size.width * 0.75, size.height * 0.5);

    final paintNode = Paint()..color = primaryColor;
    canvas.drawCircle(q0, 16, paintNode);
    canvas.drawCircle(q1, 16, paintNode);

    final textPainter = TextPainter(textDirection: TextDirection.ltr);
    textPainter.text = const TextSpan(text: 'Q0', style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold));
    textPainter.layout();
    textPainter.paint(canvas, q0 - Offset(textPainter.width / 2, textPainter.height / 2));

    textPainter.text = const TextSpan(text: 'Q1', style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold));
    textPainter.layout();
    textPainter.paint(canvas, q1 - Offset(textPainter.width / 2, textPainter.height / 2));

    if (created) {
      final linkPaint = Paint()
        ..color = Colors.cyan
        ..strokeWidth = 3
        ..style = PaintingStyle.stroke;
      canvas.drawLine(q0, q1, linkPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _EntanglementPainter oldDelegate) => oldDelegate.created != created;
}
