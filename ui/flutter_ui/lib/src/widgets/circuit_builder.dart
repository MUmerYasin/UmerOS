/// Interactive Circuit Builder — Drag-and-Drop Gate Placement
///
/// Provides a palette of quantum gates that can be dragged onto a
/// circuit grid. Supports single, two, and three-qubit gates.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class CircuitBuilder extends StatefulWidget {
  const CircuitBuilder({
    super.key,
    this.numQubits = 3,
    this.onCircuitChanged,
  });

  final int numQubits;
  final ValueChanged<List<List<String?>>>? onCircuitChanged;

  @override
  State<CircuitBuilder> createState() => _CircuitBuilderState();
}

class _CircuitBuilderState extends State<CircuitBuilder> {
  // Grid: qubits x steps, each cell holds a gate name or null
  late List<List<String?>> _grid;
  int _numSteps = 8;

  final List<_GateInfo> _gatePalette = const [
    _GateInfo('H', 'Hadamard', Colors.blue, 1),
    _GateInfo('X', 'Pauli-X', Colors.red, 1),
    _GateInfo('Y', 'Pauli-Y', Colors.green, 1),
    _GateInfo('Z', 'Pauli-Z', Colors.purple, 1),
    _GateInfo('S', 'S gate', Colors.teal, 1),
    _GateInfo('T', 'T gate', Colors.orange, 1),
    _GateInfo('CNOT', 'Controlled-NOT', Colors.deepPurple, 2),
    _GateInfo('CZ', 'Controlled-Z', Colors.indigo, 2),
    _GateInfo('SWAP', 'Swap', Colors.brown, 2),
    _GateInfo('CCX', 'Toffoli', Colors.pink, 3),
  ];

  @override
  void initState() {
    super.initState();
    _grid = List.generate(widget.numQubits, (_) => List.filled(_numSteps, null));
  }

  @override
  void didUpdateWidget(CircuitBuilder oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.numQubits != widget.numQubits) {
      _grid = List.generate(widget.numQubits, (_) => List.filled(_numSteps, null));
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Gate palette
        Container(
          height: 60,
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: _gatePalette.length,
            separatorBuilder: (_, _) => const SizedBox(width: 6),
            itemBuilder: (context, i) {
              final gate = _gatePalette[i];
              return Draggable<String>(
                data: gate.name,
                feedback: Material(
                  color: Colors.transparent,
                  child: Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: gate.color.withValues(alpha: 0.9),
                      borderRadius: BorderRadius.circular(8),
                      boxShadow: [
                        BoxShadow(color: Colors.black.withValues(alpha: 0.3), blurRadius: 8),
                      ],
                    ),
                    child: Center(
                      child: Text(
                        gate.name,
                        style: GoogleFonts.firaCode(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ),
                ),
                childWhenDragging: Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: gate.color.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Center(
                    child: Text(
                      gate.name,
                      style: GoogleFonts.firaCode(
                        color: Colors.white54,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ),
                onDragStarted: () {},
                onDragEnd: (_) {},
                child: Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: gate.color,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Center(
                    child: Text(
                      gate.name,
                      style: GoogleFonts.firaCode(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 8),
        // Circuit grid
        Expanded(
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                // Qubit labels
                Column(
                  children: [
                    const SizedBox(height: 24),
                    for (var q = 0; q < widget.numQubits; q++)
                      Container(
                        height: 48,
                        alignment: Alignment.centerRight,
                        padding: const EdgeInsets.only(right: 8),
                        child: Text(
                          'q$q',
                          style: GoogleFonts.firaCode(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                  ],
                ),
                // Gate grid
                for (var step = 0; step < _numSteps; step++)
                  Column(
                    children: [
                      // Step number
                      SizedBox(
                        height: 24,
                        child: Center(
                          child: Text(
                            '$step',
                            style: GoogleFonts.firaCode(
                              fontSize: 10,
                              color: scheme.onSurfaceVariant.withValues(alpha: 0.5),
                            ),
                          ),
                        ),
                      ),
                      for (var q = 0; q < widget.numQubits; q++)
                        DragTarget<String>(
                          onWillAcceptWithDetails: (details) {
                            final gate = _gatePalette.firstWhere((g) => g.name == details.data);
                            return gate.qubits <= widget.numQubits - q;
                          },
                          onAcceptWithDetails: (details) {
                            setState(() {
                              _grid[q][step] = details.data;
                              widget.onCircuitChanged?.call(_grid);
                            });
                          },
                          builder: (context, candidateData, rejectedData) {
                            final gateName = _grid[q][step];
                            final isHighlighted = candidateData.isNotEmpty;
                            return Container(
                              width: 48,
                              height: 48,
                              margin: const EdgeInsets.all(2),
                              decoration: BoxDecoration(
                                color: isHighlighted
                                    ? scheme.primary.withValues(alpha: 0.2)
                                    : scheme.surfaceContainerHigh,
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(
                                  color: isHighlighted
                                      ? scheme.primary
                                      : scheme.outlineVariant.withValues(alpha: 0.3),
                                ),
                              ),
                              child: gateName != null
                                  ? _GateCell(
                                      gateName: gateName,
                                      gateInfo: _gatePalette.firstWhere((g) => g.name == gateName),
                                      onRemove: () {
                                        setState(() {
                                          _grid[q][step] = null;
                                          widget.onCircuitChanged?.call(_grid);
                                        });
                                      },
                                    )
                                  : null,
                            );
                          },
                        ),
                    ],
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        // Controls
        Row(
          children: [
            FilledButton.tonalIcon(
              onPressed: () {
                setState(() {
                  _numSteps++;
                  for (var q = 0; q < widget.numQubits; q++) {
                    _grid[q].add(null);
                  }
                });
              },
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Add Column'),
            ),
            const SizedBox(width: 8),
            FilledButton.tonalIcon(
              onPressed: () {
                setState(() {
                  if (_numSteps > 1) {
                    _numSteps--;
                    for (var q = 0; q < widget.numQubits; q++) {
                      _grid[q].removeLast();
                    }
                  }
                });
              },
              icon: const Icon(Icons.remove, size: 16),
              label: const Text('Remove Column'),
            ),
            const SizedBox(width: 8),
            FilledButton.tonalIcon(
              onPressed: () {
                setState(() {
                  for (var q = 0; q < widget.numQubits; q++) {
                    for (var s = 0; s < _numSteps; s++) {
                      _grid[q][s] = null;
                    }
                  }
                });
              },
              icon: const Icon(Icons.clear, size: 16),
              label: const Text('Clear'),
            ),
          ],
        ),
      ],
    );
  }
}

class _GateInfo {
  final String name;
  final String description;
  final Color color;
  final int qubits;
  const _GateInfo(this.name, this.description, this.color, this.qubits);
}

class _GateCell extends StatelessWidget {
  final String gateName;
  final _GateInfo gateInfo;
  final VoidCallback onRemove;

  const _GateCell({
    required this.gateName,
    required this.gateInfo,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onRemove,
      child: Container(
        decoration: BoxDecoration(
          color: gateInfo.color,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Center(
          child: Text(
            gateName,
            style: GoogleFonts.firaCode(
              color: Colors.white,
              fontWeight: FontWeight.bold,
              fontSize: 11,
            ),
          ),
        ),
      ),
    );
  }
}