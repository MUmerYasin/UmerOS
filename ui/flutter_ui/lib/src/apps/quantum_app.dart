import 'dart:math';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class QuantumSimApp extends StatefulWidget {
  const QuantumSimApp({super.key});
  @override
  State<QuantumSimApp> createState() => _QuantumSimAppState();
}

class _QuantumSimAppState extends State<QuantumSimApp>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  final List<_QubitLine> _qubitLines = [
    _QubitLine(label: 'q\u2080'),
    _QubitLine(label: 'q\u2081'),
    _QubitLine(label: 'q\u2082'),
  ];
  String _selectedGate = 'H';
  final List<_PlacedGate> _placedGates = [];
  final List<_SimResult> _simResults = [];
  bool _simRunning = false;
  int _blochQubit = 0;
  final List<_PulseFrame> _pulseFrames = [
    _PulseFrame(name: 'Drive', frequency: 5.0, amplitude: 0.8, duration: 0.1),
    _PulseFrame(name: 'Drag', frequency: 5.0, amplitude: 0.3, duration: 0.05),
    _PulseFrame(name: 'CR', frequency: 6.2, amplitude: 0.5, duration: 0.25),
  ];
  final List<_QuantumJob> _jobs = [];
  final List<_AlgorithmPreset> _algorithmPresets = _defaultAlgorithms();
  String _transpilerBackend = 'ionq_hardware';
  String _transpilerOptLevel = 'optimized';
  bool _transpileRunning = false;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 8, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Column(children: [
      Material(
        color: cs.surfaceContainerHighest.withValues(alpha: 0.5),
        child: TabBar(
          controller: _tabs,
          isScrollable: true,
          labelColor: cs.primary,
          unselectedLabelColor: cs.onSurfaceVariant,
          indicatorColor: cs.primary,
          labelStyle: GoogleFonts.inter(fontSize: 11, fontWeight: FontWeight.w600),
          unselectedLabelStyle: GoogleFonts.inter(fontSize: 11),
          tabAlignment: TabAlignment.start,
          tabs: const [
            Tab(icon: Icon(Icons.grid_on, size: 15), text: 'Circuit Builder'),
            Tab(icon: Icon(Icons.category, size: 15), text: 'Gates'),
            Tab(icon: Icon(Icons.scatter_plot, size: 15), text: 'States'),
            Tab(icon: Icon(Icons.play_circle, size: 15), text: 'Simulator'),
            Tab(icon: Icon(Icons.compare_arrows, size: 15), text: 'Transpiler'),
            Tab(icon: Icon(Icons.wifi_tethering, size: 15), text: 'Pulse Control'),
            Tab(icon: Icon(Icons.workspaces, size: 15), text: 'Jobs'),
            Tab(icon: Icon(Icons.psychology, size: 15), text: 'Algorithms'),
          ],
        ),
      ),
      Expanded(
        child: TabBarView(
          controller: _tabs,
          children: [
            _buildCircuitBuilderTab(cs),
            _buildGatesTab(cs),
            _buildStatesTab(cs),
            _buildSimulatorTab(cs),
            _buildTranspilerTab(cs),
            _buildPulseControlTab(cs),
            _buildJobsTab(cs),
            _buildAlgorithmsTab(cs),
          ],
        ),
      ),
    ]);
  }

  // --- TAB 1: CIRCUIT BUILDER ---
  Widget _buildCircuitBuilderTab(ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _sectionHeader('GATE PALETTE', Icons.grid_view, cs),
        const SizedBox(height: 6),
        _gatePalette(cs),
        const SizedBox(height: 12),
        Row(children: [
          _pillButton('Add Qubit', Icons.add, cs, () {
            setState(() {
              final n = _qubitLines.length;
              _qubitLines.add(_QubitLine(label: 'q$superScript(n)'));
            });
          }),
          const SizedBox(width: 8),
          _pillButton('Remove Qubit', Icons.remove, cs, () {
            if (_qubitLines.length > 1) setState(() => _qubitLines.removeLast());
          }),
          const SizedBox(width: 8),
          _pillButton('Clear All', Icons.delete_sweep, cs, () {
            setState(() => _placedGates.clear());
          }),
          const SizedBox(width: 8),
          _pillButton('Export QASM', Icons.code, cs, _showQasmDialog),
          const Spacer(),
          _pillButton('Run Circuit', Icons.play_arrow, cs, () {
            setState(() => _tabs.index = 3);
          }),
        ]),
        const SizedBox(height: 12),
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: cs.surfaceContainerHighest.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: cs.outlineVariant.withValues(alpha: 0.25)),
            ),
            child: _circuitGridView(cs),
          ),
        ),
      ]),
    );
  }

  Widget _gatePalette(ColorScheme cs) {
    final gates = <String, Color>{
      'H': Colors.teal, 'X': Colors.red, 'Y': Colors.orange, 'Z': Colors.blue,
      'S': Colors.indigo, 'T': Colors.purple, 'CNOT': Colors.green,
      'SWAP': Colors.brown, 'Toffoli': Colors.deepOrange, 'Rz': Colors.cyan,
      'Ry': Colors.amber, 'Rx': Colors.pink, 'I': Colors.grey,
    };
    return Wrap(
      spacing: 6, runSpacing: 6,
      children: gates.entries.map((e) {
        final sel = _selectedGate == e.key;
        return GestureDetector(
          onTap: () => setState(() => _selectedGate = e.key),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: sel ? e.value.withValues(alpha: 0.22) : cs.surfaceContainerHighest.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: sel ? e.value : cs.outlineVariant.withValues(alpha: 0.2), width: sel ? 2 : 1),
            ),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(_gateIcon(e.key), size: 18, color: e.value),
              const SizedBox(height: 3),
              Text(e.key, style: GoogleFonts.jetBrainsMono(fontSize: 11, fontWeight: sel ? FontWeight.w700 : FontWeight.w500, color: sel ? e.value : cs.onSurface)),
            ]),
          ),
        );
      }).toList(),
    );
  }

  Widget _circuitGridView(ColorScheme cs) {
    const cols = 16;
    return LayoutBuilder(builder: (context, constraints) {
      final rowH = constraints.maxHeight / _qubitLines.length;
      final colW = constraints.maxWidth / cols;
      return GestureDetector(
        onTapDown: (details) {
          final col = (details.localPosition.dx / colW).floor();
          final row = (details.localPosition.dy / rowH).floor();
          if (row >= 0 && row < _qubitLines.length && col >= 0 && col < cols) {
            setState(() => _placedGates.add(_PlacedGate(qubit: row, col: col, type: _selectedGate)));
          }
        },
        child: Stack(children: [
          for (int q = 0; q < _qubitLines.length; q++)
            Positioned(top: rowH * q + rowH / 2 - 1, left: 0, right: 0, child: Container(height: 2, color: cs.outlineVariant.withValues(alpha: 0.25))),
          for (int q = 0; q < _qubitLines.length; q++)
            Positioned(top: rowH * q, left: 6, child: SizedBox(height: rowH, child: Center(child: Text(_qubitLines[q].label, style: GoogleFonts.jetBrainsMono(fontSize: 11, color: cs.onSurfaceVariant))))),
          for (final g in _placedGates)
            Positioned(
              top: rowH * g.qubit + rowH / 2 - 16,
              left: 44.0 + colW * g.col - 14,
              child: GestureDetector(onDoubleTap: () => setState(() => _placedGates.remove(g)), child: _gateChip(g.type, cs, small: true)),
            ),
        ]),
      );
    });
  }

  // --- TAB 2: GATES ---
  Widget _buildGatesTab(ColorScheme cs) {
    final gates = _gateReferenceData();
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: gates.length,
      itemBuilder: (_, i) {
        final g = gates[i];
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          color: cs.surfaceContainerHighest.withValues(alpha: 0.35),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(children: [
              _gateChip(g.name, cs),
              const SizedBox(width: 14),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(g.description, style: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600)),
                const SizedBox(height: 3),
                Text(g.matrix, style: GoogleFonts.jetBrainsMono(fontSize: 10, color: cs.onSurfaceVariant)),
                const SizedBox(height: 3),
                Text('Category: ${g.category}', style: GoogleFonts.inter(fontSize: 10, color: cs.onSurfaceVariant.withValues(alpha: 0.7))),
              ])),
            ]),
          ),
        );
      },
    );
  }

  // --- TAB 3: STATES ---
  Widget _buildStatesTab(ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _sectionHeader('QUANTUM STATES', Icons.scatter_plot, cs),
        const SizedBox(height: 10),
        Row(children: [
          Text('Qubit: ', style: GoogleFonts.inter(fontSize: 12, color: cs.onSurface)),
          for (int i = 0; i < _qubitLines.length; i++)
            Padding(padding: const EdgeInsets.only(right: 6), child: ChoiceChip(label: Text(_qubitLines[i].label), selected: _blochQubit == i, onSelected: (_) => setState(() => _blochQubit = i))),
        ]),
        const SizedBox(height: 14),
        Expanded(child: Row(children: [
          Expanded(flex: 3, child: Card(
            color: cs.surfaceContainerHighest.withValues(alpha: 0.3),
            child: Center(child: CustomPaint(size: const Size(260, 260), painter: _BlochSpherePainter(theta: [0.0, pi / 4, pi / 2, pi][_blochQubit], phi: pi / 4, color: cs.primary))),
          )),
          const SizedBox(width: 14),
          Expanded(flex: 2, child: Card(
            color: cs.surfaceContainerHighest.withValues(alpha: 0.3),
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('State Vector', style: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              _stateVectorRow('|0\u27E9', '0.707 + 0.000i', cs),
              _stateVectorRow('|1\u27E9', '0.707 + 0.000i', cs),
              const Divider(height: 20),
              Text('Probabilities', style: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              _probBar('|0\u27E9', 0.50, Colors.teal, cs),
              _probBar('|1\u27E9', 0.50, Colors.orange, cs),
              const Spacer(),
              Text('Purity: 1.000', style: GoogleFonts.jetBrainsMono(fontSize: 10, color: cs.onSurfaceVariant)),
              Text('Entropy: 1.000', style: GoogleFonts.jetBrainsMono(fontSize: 10, color: cs.onSurfaceVariant)),
            ]),
          )),
        ])),
      ]),
    );
  }

  // --- TAB 4: SIMULATOR ---
  Widget _buildSimulatorTab(ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _sectionHeader('QUANTUM SIMULATOR', Icons.play_circle, cs),
        const SizedBox(height: 10),
        Row(children: [
          _configChip('Backend', 'StatevectorSimulator', cs),
          const SizedBox(width: 8),
          _configChip('Shots', '1024', cs),
          const SizedBox(width: 8),
          _configChip('Noise Model', 'None', cs),
          const Spacer(),
          _pillButton(_simRunning ? 'Running\u2026' : 'Run Simulation', _simRunning ? Icons.hourglass_top : Icons.play_arrow, cs, _simRunning ? null : _runSimulation),
        ]),
        const SizedBox(height: 12),
        Expanded(child: _simResults.isEmpty
            ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.science_outlined, size: 48, color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
                const SizedBox(height: 10),
                Text('No simulation results yet', style: GoogleFonts.inter(fontSize: 12, color: cs.onSurfaceVariant)),
                Text('Build a circuit and click Run', style: GoogleFonts.inter(fontSize: 10, color: cs.onSurfaceVariant.withValues(alpha: 0.6))),
              ]))
            : _buildSimResults(cs)),
      ]),
    );
  }

  Widget _buildSimResults(ColorScheme cs) {
    return ListView.builder(
      itemCount: _simResults.length,
      itemBuilder: (_, i) {
        final r = _simResults[i];
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          color: cs.surfaceContainerHighest.withValues(alpha: 0.3),
          child: Padding(padding: const EdgeInsets.all(12), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Icon(Icons.check_circle, size: 14, color: Colors.green),
              const SizedBox(width: 6),
              Text('Result #${i + 1}', style: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600)),
              const Spacer(),
              Text(r.timestamp, style: GoogleFonts.jetBrainsMono(fontSize: 9, color: cs.onSurfaceVariant)),
            ]),
            const SizedBox(height: 8),
            Wrap(spacing: 14, runSpacing: 6, children: r.counts.entries.map((e) {
              final pct = (e.value / 1024 * 100).toStringAsFixed(1);
              return Column(children: [
                Text(e.key, style: GoogleFonts.jetBrainsMono(fontSize: 12, fontWeight: FontWeight.w700)),
                Text('$pct%', style: GoogleFonts.inter(fontSize: 10, color: cs.onSurfaceVariant)),
                const SizedBox(height: 2),
                SizedBox(width: 60, child: LinearProgressIndicator(value: e.value / 1024, minHeight: 4, backgroundColor: cs.surfaceContainerHighest)),
              ]);
            }).toList()),
          ])),
        );
      },
    );
  }

  // --- TAB 5: TRANSPILER ---
  Widget _buildTranspilerTab(ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _sectionHeader('CIRCUIT TRANSPILER', Icons.compare_arrows, cs),
        const SizedBox(height: 10),
        Row(children: [
          _configChip('Backend', _transpilerBackend, cs),
          const SizedBox(width: 8),
          _configChip('Optimization', _transpilerOptLevel, cs),
          const SizedBox(width: 8),
          _configChip('Gates', '${_placedGates.length} total', cs),
        ]),
        const SizedBox(height: 12),
        Row(children: [
          _pillButton('Transpile', Icons.speed, cs, _transpileRunning ? null : _runTranspile),
          const SizedBox(width: 8),
          _pillButton('Decompose', Icons.unfold_more, cs, () {}),
          const SizedBox(width: 8),
          _pillButton('Optimize', Icons.auto_fix_high, cs, () {}),
        ]),
        const SizedBox(height: 14),
        Expanded(child: Card(
          color: cs.surfaceContainerHighest.withValues(alpha: 0.3),
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Transpiled Output', style: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600)),
            const SizedBox(height: 10),
            if (_transpileRunning)
              const Center(child: CircularProgressIndicator())
            else ...[
              Text('// Transpiled circuit will appear here\n// Native gates: GZ, GP, GK\n// Fidelity estimate: 0.987', style: GoogleFonts.jetBrainsMono(fontSize: 11, color: cs.onSurfaceVariant)),
              const Spacer(),
              Row(children: [
                _metricChip('Depth', '${_placedGates.isNotEmpty ? _placedGates.map((g) => g.col).reduce(max) + 1 : 0}', cs),
                const SizedBox(width: 8),
                _metricChip('Two-Qubit', '${_placedGates.where((g) => ['CNOT', 'SWAP', 'Toffoli'].contains(g.type)).length}', cs),
                const SizedBox(width: 8),
                _metricChip('Fidelity', '98.7%', cs),
              ]),
            ],
          ]),
        )),
      ]),
    );
  }

  // --- TAB 6: PULSE CONTROL ---
  Widget _buildPulseControlTab(ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _sectionHeader('PULSE CONTROL', Icons.wifi_tethering, cs),
        const SizedBox(height: 10),
        Row(children: [
          _pillButton('Add Frame', Icons.add, cs, () {
            setState(() => _pulseFrames.add(_PulseFrame(name: 'New', frequency: 5.0, amplitude: 0.5, duration: 0.1)));
          }),
          const SizedBox(width: 8),
          _pillButton('Run Sequence', Icons.play_arrow, cs, () {}),
          const SizedBox(width: 8),
          _pillButton('Export OPENQASM', Icons.code, cs, () {}),
        ]),
        const SizedBox(height: 12),
        Expanded(child: ListView.builder(
          itemCount: _pulseFrames.length,
          itemBuilder: (_, i) {
            final f = _pulseFrames[i];
            return Card(
              margin: const EdgeInsets.only(bottom: 8),
              color: cs.surfaceContainerHighest.withValues(alpha: 0.35),
              child: Padding(padding: const EdgeInsets.all(12), child: Row(children: [
                Container(
                  width: 40, height: 40,
                  decoration: BoxDecoration(color: cs.primary.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(10)),
                  child: Icon(Icons.wifi_tethering, size: 20, color: cs.primary),
                ),
                const SizedBox(width: 12),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(f.name, style: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  Row(children: [
                    _miniChip('Freq: ${f.frequency.toStringAsFixed(1)} GHz', cs),
                    const SizedBox(width: 6),
                    _miniChip('Amp: ${f.amplitude.toStringAsFixed(2)}', cs),
                    const SizedBox(width: 6),
                    _miniChip('Dur: ${f.duration.toStringAsFixed(3)} \u03BCs', cs),
                  ]),
                ])),
                SizedBox(width: 100, height: 36, child: CustomPaint(painter: _PulseWaveformPainter(amplitude: f.amplitude, color: cs.primary))),
                IconButton(icon: const Icon(Icons.close, size: 16), onPressed: () => setState(() => _pulseFrames.removeAt(i))),
              ])),
            );
          },
        )),
      ]),
    );
  }

  // --- TAB 7: JOBS ---
  Widget _buildJobsTab(ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _sectionHeader('QUANTUM JOBS', Icons.workspaces, cs),
        const SizedBox(height: 10),
        Row(children: [
          _pillButton('Submit Job', Icons.send, cs, _submitJob),
          const SizedBox(width: 8),
          _pillButton('Refresh', Icons.refresh, cs, () {}),
          const Spacer(),
          Text('${_jobs.length} jobs', style: GoogleFonts.inter(fontSize: 11, color: cs.onSurfaceVariant)),
        ]),
        const SizedBox(height: 12),
        Expanded(child: _jobs.isEmpty
            ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.workspaces_outlined, size: 48, color: cs.onSurfaceVariant.withValues(alpha: 0.3)),
                const SizedBox(height: 10),
                Text('No jobs submitted', style: GoogleFonts.inter(fontSize: 12, color: cs.onSurfaceVariant)),
              ]))
            : ListView.builder(
                itemCount: _jobs.length,
                itemBuilder: (_, i) {
                  final j = _jobs[i];
                  return Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    color: cs.surfaceContainerHighest.withValues(alpha: 0.35),
                    child: ListTile(
                      leading: Icon(
                        j.status == 'Completed' ? Icons.check_circle : j.status == 'Running' ? Icons.autorenew : Icons.pending,
                        color: j.status == 'Completed' ? Colors.green : j.status == 'Running' ? cs.primary : Colors.amber,
                        size: 22,
                      ),
                      title: Text(j.name, style: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600)),
                      subtitle: Text('${j.backend}  \u00B7  ${j.shots} shots  \u00B7  ${j.status}', style: GoogleFonts.jetBrainsMono(fontSize: 10, color: cs.onSurfaceVariant)),
                      trailing: Text(j.time, style: GoogleFonts.jetBrainsMono(fontSize: 9, color: cs.onSurfaceVariant)),
                    ),
                  );
                },
              )),
      ]),
    );
  }

  // --- TAB 8: ALGORITHMS ---
  Widget _buildAlgorithmsTab(ColorScheme cs) {
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _algorithmPresets.length,
      itemBuilder: (_, i) {
        final a = _algorithmPresets[i];
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          color: cs.surfaceContainerHighest.withValues(alpha: 0.35),
          child: Padding(padding: const EdgeInsets.all(14), child: Row(children: [
            Container(
              width: 48, height: 48,
              decoration: BoxDecoration(color: a.color.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(12)),
              child: Icon(a.icon, color: a.color, size: 26),
            ),
            const SizedBox(width: 14),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(a.name, style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600)),
              const SizedBox(height: 3),
              Text(a.description, style: GoogleFonts.inter(fontSize: 10, color: cs.onSurfaceVariant.withValues(alpha: 0.8))),
              const SizedBox(height: 4),
              Wrap(spacing: 6, children: a.tags.map((t) => _miniChip(t, cs)).toList()),
            ])),
            _pillButton('Run', Icons.play_arrow, cs, () {
              setState(() {
                _jobs.add(_QuantumJob(name: a.name, backend: 'ionq_hardware', shots: 1024, status: 'Completed', time: '1.2s'));
                _tabs.index = 6;
              });
            }),
          ])),
        );
      },
    );
  }

  // --- SHARED WIDGETS ---
  Widget _sectionHeader(String text, IconData icon, ColorScheme cs) {
    return Row(children: [
      Icon(icon, size: 16, color: cs.primary),
      const SizedBox(width: 6),
      Text(text, style: GoogleFonts.inter(fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.2, color: cs.onSurfaceVariant)),
    ]);
  }

  Widget _pillButton(String label, IconData icon, ColorScheme cs, VoidCallback? onTap) {
    final enabled = onTap != null;
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: enabled ? cs.primaryContainer.withValues(alpha: 0.6) : cs.surfaceContainerHighest.withValues(alpha: 0.3),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: enabled ? cs.primary.withValues(alpha: 0.4) : cs.outlineVariant.withValues(alpha: 0.15)),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 14, color: enabled ? cs.primary : cs.onSurfaceVariant.withValues(alpha: 0.4)),
          const SizedBox(width: 5),
          Text(label, style: GoogleFonts.inter(fontSize: 11, fontWeight: FontWeight.w600, color: enabled ? cs.onPrimaryContainer : cs.onSurfaceVariant.withValues(alpha: 0.4))),
        ]),
      ),
    );
  }

  Widget _gateChip(String name, ColorScheme cs, {bool small = false}) {
    final color = _gateColor(name);
    return Container(
      padding: EdgeInsets.symmetric(horizontal: small ? 6 : 10, vertical: small ? 3 : 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(small ? 6 : 8),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(name, style: GoogleFonts.jetBrainsMono(fontSize: small ? 9 : 11, fontWeight: FontWeight.w700, color: color)),
    );
  }

  Widget _configChip(String label, String value, ColorScheme cs) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(color: cs.surfaceContainerHighest.withValues(alpha: 0.4), borderRadius: BorderRadius.circular(8)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text('$label: ', style: GoogleFonts.inter(fontSize: 10, color: cs.onSurfaceVariant)),
        Text(value, style: GoogleFonts.jetBrainsMono(fontSize: 10, fontWeight: FontWeight.w600)),
      ]),
    );
  }

  Widget _metricChip(String label, String value, ColorScheme cs) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(color: cs.primaryContainer.withValues(alpha: 0.3), borderRadius: BorderRadius.circular(8)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text('$label: ', style: GoogleFonts.inter(fontSize: 10, color: cs.onSurfaceVariant)),
        Text(value, style: GoogleFonts.jetBrainsMono(fontSize: 11, fontWeight: FontWeight.w700)),
      ]),
    );
  }

  Widget _miniChip(String text, ColorScheme cs) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(color: cs.surfaceContainerHighest.withValues(alpha: 0.5), borderRadius: BorderRadius.circular(5)),
      child: Text(text, style: GoogleFonts.jetBrainsMono(fontSize: 9, color: cs.onSurfaceVariant)),
    );
  }

  Widget _stateVectorRow(String ket, String amp, ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(children: [
        Text(ket, style: GoogleFonts.jetBrainsMono(fontSize: 12, fontWeight: FontWeight.w700, color: Colors.teal)),
        const SizedBox(width: 10),
        Text(amp, style: GoogleFonts.jetBrainsMono(fontSize: 11, color: cs.onSurface)),
      ]),
    );
  }

  Widget _probBar(String ket, double prob, Color color, ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(children: [
        SizedBox(width: 30, child: Text(ket, style: GoogleFonts.jetBrainsMono(fontSize: 10, fontWeight: FontWeight.w600))),
        Expanded(child: ClipRRect(borderRadius: BorderRadius.circular(3), child: LinearProgressIndicator(value: prob, minHeight: 8, backgroundColor: cs.surfaceContainerHighest, valueColor: AlwaysStoppedAnimation(color)))),
        const SizedBox(width: 8),
        SizedBox(width: 36, child: Text('${(prob * 100).toStringAsFixed(0)}%', style: GoogleFonts.jetBrainsMono(fontSize: 9))),
      ]),
    );
  }

  IconData _gateIcon(String gate) {
    switch (gate) {
      case 'H': return Icons.horizontal_rule;
      case 'X': return Icons.close;
      case 'Y': return Icons.swap_vert;
      case 'Z': return Icons.swap_horiz;
      case 'S': return Icons.square;
      case 'T': return Icons.square_foot;
      case 'CNOT': return Icons.link;
      case 'SWAP': return Icons.swap_horiz_circle;
      case 'Toffoli': return Icons.control_point;
      case 'Rz': return Icons.rotate_right;
      case 'Ry': return Icons.rotate_left;
      case 'Rx': return Icons.sync;
      default: return Icons.blur_circular;
    }
  }

  Color _gateColor(String gate) {
    switch (gate) {
      case 'H': return Colors.teal;
      case 'X': return Colors.red;
      case 'Y': return Colors.orange;
      case 'Z': return Colors.blue;
      case 'S': return Colors.indigo;
      case 'T': return Colors.purple;
      case 'CNOT': return Colors.green;
      case 'SWAP': return Colors.brown;
      case 'Toffoli': return Colors.deepOrange;
      case 'Rz': return Colors.cyan;
      case 'Ry': return Colors.amber;
      case 'Rx': return Colors.pink;
      default: return Colors.grey;
    }
  }

  String superScript(int n) {
    const sup = ['\u2070', '\u00B9', '\u00B2', '\u00B3', '\u2074', '\u2075', '\u2076', '\u2077', '\u2078', '\u2079'];
    return n.toString().split('').map((d) => sup[int.parse(d)]).join();
  }

  // --- ACTIONS ---
  void _runSimulation() {
    setState(() => _simRunning = true);
    Future.delayed(const Duration(seconds: 2), () {
      if (!mounted) return;
      final rng = Random();
      final counts = <String, int>{};
      for (final g in _placedGates) {
        final key = List.generate(_qubitLines.length, (i) => i == g.qubit ? '1' : '0').join();
        counts[key] = (counts[key] ?? 0) + rng.nextInt(200);
      }
      if (counts.isEmpty) { counts['000'] = 512; counts['001'] = 512; }
      final total = counts.values.fold<int>(0, (a, b) => a + b);
      final normalized = <String, int>{};
      counts.forEach((k, v) { normalized[k] = (v / total * 1024).round(); });
      setState(() {
        _simRunning = false;
        _simResults.add(_SimResult(counts: normalized, timestamp: DateTime.now().toString().substring(11, 19)));
      });
    });
  }

  void _runTranspile() {
    setState(() => _transpileRunning = true);
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _transpileRunning = false);
    });
  }

  void _submitJob() {
    final rng = Random();
    setState(() {
      _jobs.add(_QuantumJob(name: 'Circuit Job #${_jobs.length + 1}', backend: 'ionq_hardware', shots: 1024, status: 'Running', time: '\u2014'));
    });
    Future.delayed(Duration(seconds: 2 + rng.nextInt(3)), () {
      if (!mounted) return;
      setState(() {
        final idx = _jobs.length - 1;
        _jobs[idx] = _QuantumJob(name: _jobs[idx].name, backend: _jobs[idx].backend, shots: _jobs[idx].shots, status: 'Completed', time: '${(1 + rng.nextDouble() * 3).toStringAsFixed(1)}s');
      });
    });
  }

  void _showQasmDialog() {
    final gates = _placedGates.map((g) {
      if (g.type == 'CNOT') return 'cx q[${g.qubit}], q[${(g.qubit + 1) % _qubitLines.length}];';
      if (g.type == 'SWAP') return 'swap q[${g.qubit}], q[${(g.qubit + 1) % _qubitLines.length}];';
      if (g.type.startsWith('R')) return '${g.type.toLowerCase()}(0.5) q[${g.qubit}];';
      return '${g.type.toLowerCase()} q[${g.qubit}];';
    }).join('\n');
    showDialog(context: context, builder: (_) => AlertDialog(
      title: const Text('OpenQASM 3.0'),
      content: SingleChildScrollView(child: Text('OPENQASM 3.0;\ninclude "stdgates.inc";\n\nqubit[${_qubitLines.length}] q;\nbit[${_qubitLines.length}] c;\n\n$gates', style: GoogleFonts.jetBrainsMono(fontSize: 11))),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
    ));
  }

  static List<_AlgorithmPreset> _defaultAlgorithms() {
    return [
      _AlgorithmPreset(name: "Grover's Search", description: 'Quadratic speedup for unstructured search', icon: Icons.search, color: Colors.teal, tags: ['Oracle', 'Diffusion', 'O(\u221AN)']),
      _AlgorithmPreset(name: "Shor's Factoring", description: 'Exponential speedup for integer factorization', icon: Icons.key, color: Colors.red, tags: ['Period Finding', 'QFT', 'RSA-2048']),
      _AlgorithmPreset(name: 'Quantum Phase Estimation', description: 'Estimate eigenvalues of unitary operators', icon: Icons.architecture, color: Colors.blue, tags: ['QFT', 'Controlled-U', 'Phase']),
      _AlgorithmPreset(name: 'Variational Quantum Eigensolver', description: 'Find ground state energy of molecular Hamiltonians', icon: Icons.science, color: Colors.purple, tags: ['VQE', 'Ansatz', 'Optimizer']),
      _AlgorithmPreset(name: 'QAOA', description: 'Combinatorial optimization via parameterized circuits', icon: Icons.tune, color: Colors.orange, tags: ['QAOA', 'MaxCut', 'Parameterized']),
      _AlgorithmPreset(name: 'Quantum Random Number Generator', description: 'True randomness from quantum superposition', icon: Icons.casino, color: Colors.green, tags: ['QRNG', 'Hadamard', 'Uniform']),
      _AlgorithmPreset(name: 'Quantum Key Distribution', description: 'Provably secure key exchange protocol (BB84)', icon: Icons.vpn_key, color: Colors.indigo, tags: ['BB84', 'BBM92', 'E91']),
      _AlgorithmPreset(name: 'Bernstein-Vazirani', description: 'Find hidden string via single query', icon: Icons.fingerprint, color: Colors.brown, tags: ['Oracle', 'O(1)', 'Promise']),
    ];
  }

  static List<_GateReference> _gateReferenceData() {
    return [
      _GateReference('H', 'Hadamard Gate', '1/\u221A2 [1 1; 1 -1]', 'Single-Qubit'),
      _GateReference('X', 'Pauli-X (NOT)', '[0 1; 1 0]', 'Single-Qubit'),
      _GateReference('Y', 'Pauli-Y', '[0 -i; i 0]', 'Single-Qubit'),
      _GateReference('Z', 'Pauli-Z', '[1 0; 0 -1]', 'Single-Qubit'),
      _GateReference('S', 'S Gate (\u221AZ)', '[1 0; 0 i]', 'Single-Qubit'),
      _GateReference('T', 'T Gate (\u221AS)', '[1 0; 0 e^(i\u03C0/4)]', 'Single-Qubit'),
      _GateReference('CNOT', 'Controlled-NOT', '4\u00D74 matrix', 'Two-Qubit'),
      _GateReference('SWAP', 'SWAP Gate', 'Permutation matrix', 'Two-Qubit'),
      _GateReference('Toffoli', 'Toffoli (CCX)', '8\u00D78 matrix', 'Three-Qubit'),
      _GateReference('Rx', 'Rotation-X', 'cos(\u03B8/2)I - i\u00B7sin(\u03B8/2)X', 'Parametric'),
      _GateReference('Ry', 'Rotation-Y', 'cos(\u03B8/2)I - i\u00B7sin(\u03B8/2)Y', 'Parametric'),
      _GateReference('Rz', 'Rotation-Z', 'e^(-i\u03B8/2Z)', 'Parametric'),
      _GateReference('I', 'Identity', '[1 0; 0 1]', 'Single-Qubit'),
    ];
  }
}

// --- DATA MODELS ---
class _QubitLine { final String label; _QubitLine({required this.label}); }
class _PlacedGate { final int qubit; final int col; final String type; _PlacedGate({required this.qubit, required this.col, required this.type}); }
class _SimResult { final Map<String, int> counts; final String timestamp; _SimResult({required this.counts, required this.timestamp}); }
class _PulseFrame { final String name; final double frequency; final double amplitude; final double duration; _PulseFrame({required this.name, required this.frequency, required this.amplitude, required this.duration}); }
class _QuantumJob { final String name; final String backend; final int shots; final String status; final String time; _QuantumJob({required this.name, required this.backend, required this.shots, required this.status, required this.time}); }
class _AlgorithmPreset { final String name; final String description; final IconData icon; final Color color; final List<String> tags; _AlgorithmPreset({required this.name, required this.description, required this.icon, required this.color, required this.tags}); }
class _GateReference { final String name; final String description; final String matrix; final String category; _GateReference(this.name, this.description, this.matrix, this.category); }

// --- CUSTOM PAINTERS ---
class _BlochSpherePainter extends CustomPainter {
  final double theta; final double phi; final Color color;
  _BlochSpherePainter({required this.theta, required this.phi, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2, cy = size.height / 2;
    final r = size.width / 2 - 20;
    final outlinePaint = Paint()..color = color.withValues(alpha: 0.2)..style = PaintingStyle.stroke..strokeWidth = 1.5;
    canvas.drawCircle(Offset(cx, cy), r, outlinePaint);
    final equatorPaint = Paint()..color = color.withValues(alpha: 0.12)..style = PaintingStyle.stroke..strokeWidth = 1;
    canvas.drawOval(Rect.fromCenter(center: Offset(cx, cy), width: r * 2, height: r * 0.6), equatorPaint);
    final axisPaint = Paint()..color = color.withValues(alpha: 0.15)..strokeWidth = 1;
    canvas.drawLine(Offset(cx, cy - r), Offset(cx, cy + r), axisPaint);
    canvas.drawLine(Offset(cx - r, cy), Offset(cx + r, cy), axisPaint);
    final vecX = r * sin(theta) * cos(phi);
    final vecY = -r * cos(theta);
    final vecEnd = Offset(cx + vecX, cy + vecY);
    final vecPaint = Paint()..color = color..strokeWidth = 2.5..strokeCap = StrokeCap.round;
    canvas.drawLine(Offset(cx, cy), vecEnd, vecPaint);
    canvas.drawCircle(vecEnd, 5, Paint()..color = color);
  }

  @override
  bool shouldRepaint(_BlochSpherePainter o) => o.theta != theta || o.phi != phi;
}

class _PulseWaveformPainter extends CustomPainter {
  final double amplitude; final Color color;
  _PulseWaveformPainter({required this.amplitude, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color..style = PaintingStyle.stroke..strokeWidth = 2;
    final path = Path();
    for (double x = 0; x <= size.width; x++) {
      final y = size.height / 2 - sin(x / size.width * 4 * pi) * size.height / 2 * amplitude;
      if (x == 0) path.moveTo(x, y); else path.lineTo(x, y);
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_PulseWaveformPainter o) => o.amplitude != amplitude;
}
