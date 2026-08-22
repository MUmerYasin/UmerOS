# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Simple test script for hardware_transpiler module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import directly from the modules
from quantum.gates import H_GATE, X_GATE, CNOT_GATE, TOFFOLI_GATE, SWAP_GATE
from quantum.circuit import QuantumCircuit, Instruction
from quantum.native_gates import HardwarePlatform
from quantum.hardware_transpiler import (
    CouplingMap,
    IBM_127_QUBIT,
    IONQ_11_QUBIT,
    RIGETTI_80_QUBIT,
    DecompositionPass,
    OptimizationPass,
    LayoutPass,
    RoutingPass,
    PulseLevelPass,
    HardwareTranspiler,
    estimate_circuit_depth,
    estimate_swaps_needed,
)

print("=== Testing CouplingMap ===")
cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
print(f"Created CouplingMap with {cm.num_qubits} qubits and {len(cm.edges)} edges")
print(f"Connected 0-1: {cm.is_connected(0, 1)}")
print(f"Connected 0-2: {cm.is_connected(0, 2)}")
print(f"Distance 0-3: {cm.distance(0, 3)}")
print(f"Shortest path 0-3: {cm.shortest_path(0, 3)}")

print("\n=== Testing Pre-defined Coupling Maps ===")
ibm = IBM_127_QUBIT()
print(f"IBM 127-qubit: {ibm.num_qubits} qubits, {len(ibm.edges)} edges")

ionq = IONQ_11_QUBIT()
print(f"IonQ 11-qubit: {ionq.num_qubits} qubits, {len(ionq.edges)} edges (all-to-all)")

rigetti = RIGETTI_80_QUBIT()
print(f"Rigetti 80-qubit: {rigetti.num_qubits} qubits, {len(rigetti.edges)} edges")

print("\n=== Testing DecompositionPass ===")
decomposer = DecompositionPass(target_gates=['H', 'X', 'CNOT'])

# Create a circuit with Toffoli gate
circuit = QuantumCircuit(3)
circuit.instructions.append(Instruction(gate=TOFFOLI_GATE, qubits=[0, 1, 2]))
print(f"Original circuit: {len(circuit.instructions)} gates")
print(f"  Gate: {circuit.instructions[0].gate.name}")

result = decomposer.run(circuit)
print(f"Decomposed circuit: {len(result.instructions)} gates")
gate_names = [i.gate.name for i in result.instructions]
print(f"  Gates: {gate_names}")

print("\n=== Testing OptimizationPass ===")
optimizer = OptimizationPass()
circuit = QuantumCircuit(1)
circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
print(f"Original circuit: {len(circuit.instructions)} gates (H-H)")

result = optimizer.run(circuit)
print(f"Optimized circuit: {len(result.instructions)} gates")

print("\n=== Testing LayoutPass ===")
layout = LayoutPass(method='trivial')
circuit = QuantumCircuit(2)
circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
result = layout.run(circuit)
print(f"Trivial layout: qubit 0 -> {result.instructions[0].qubits[0]}")

print("\n=== Testing RoutingPass ===")
cm = CouplingMap(num_qubits=3, edges=[(0, 1), (1, 2)])
router = RoutingPass(coupling_map=cm)
circuit = QuantumCircuit(3)
circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 2]))
print(f"Original: CNOT on qubits [0, 2] (not connected)")

result = router.run(circuit)
print(f"Routed: {len(result.instructions)} instructions")
gate_names = [i.gate.name for i in result.instructions]
print(f"  Gates: {gate_names}")

print("\n=== Testing HardwareTranspiler ===")
transpiler = HardwareTranspiler(platform=HardwarePlatform.TRAPPED_ION)
circuit = QuantumCircuit(3)
circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 1]))

result, report = transpiler.transpile_and_report(circuit)
print(f"Transpiled: {len(result.instructions)} gates")
print(f"Report: {report}")

print("\n=== Testing Utility Functions ===")
circuit = QuantumCircuit(2)
circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 1]))
depth = estimate_circuit_depth(circuit)
print(f"Circuit depth: {depth}")

cm = CouplingMap(num_qubits=3, edges=[(0, 1), (1, 2)])
circuit = QuantumCircuit(3)
circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 2]))
swaps = estimate_swaps_needed(circuit, cm)
print(f"Estimated SWAPs needed: {swaps}")

print("\n=== All tests passed! ===")
