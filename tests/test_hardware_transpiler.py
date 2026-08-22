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

"""Tests for hardware_transpiler module."""

import unittest
import numpy as np

from quantum.hardware_transpiler import (
    CouplingMap,
    TranspilerPass,
    RoutingPass,
    DecompositionPass,
    OptimizationPass,
    LayoutPass,
    PulseLevelPass,
    HardwareTranspiler,
    IBM_127_QUBIT,
    IONQ_11_QUBIT,
    RIGETTI_80_QUBIT,
    transpile_for_hardware,
    estimate_circuit_depth,
    estimate_swaps_needed,
)
from quantum.native_gates import HardwarePlatform
from quantum.circuit import QuantumCircuit, Instruction
from quantum.gates import H_GATE, X_GATE, CNOT_GATE, TOFFOLI_GATE


class TestCouplingMap(unittest.TestCase):
    def test_initialization(self):
        cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
        self.assertEqual(cm.num_qubits, 4)
        self.assertEqual(len(cm.edges), 3)
        self.assertFalse(cm.directed)

    def test_is_connected(self):
        cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
        self.assertTrue(cm.is_connected(0, 1))
        self.assertTrue(cm.is_connected(1, 0))
        self.assertFalse(cm.is_connected(0, 2))

    def test_is_connected_directed(self):
        cm = CouplingMap(num_qubits=3, edges=[(0, 1)], directed=True)
        self.assertTrue(cm.is_connected(0, 1))
        self.assertFalse(cm.is_connected(1, 0))

    def test_neighbors(self):
        cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
        self.assertEqual(sorted(cm.neighbors(1)), [0, 2])

    def test_distance(self):
        cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
        self.assertEqual(cm.distance(0, 0), 0)
        self.assertEqual(cm.distance(0, 1), 1)
        self.assertEqual(cm.distance(0, 3), 3)

    def test_distance_unreachable(self):
        cm = CouplingMap(num_qubits=4, edges=[(0, 1)])
        self.assertEqual(cm.distance(1, 3), -1)

    def test_shortest_path(self):
        cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
        path = cm.shortest_path(0, 3)
        self.assertEqual(path, [0, 1, 2, 3])

    def test_shortest_path_same_qubit(self):
        cm = CouplingMap(num_qubits=4, edges=[(0, 1)])
        self.assertEqual(cm.shortest_path(0, 0), [0])

    def test_validation_out_of_range(self):
        with self.assertRaises(ValueError):
            CouplingMap(num_qubits=4, edges=[(0, 5)])

    def test_validation_self_loop(self):
        with self.assertRaises(ValueError):
            CouplingMap(num_qubits=4, edges=[(0, 0)])


class TestPredefinedCouplingMaps(unittest.TestCase):
    def test_ibm_127_qubit(self):
        cm = IBM_127_QUBIT()
        self.assertEqual(cm.num_qubits, 127)
        self.assertGreater(len(cm.edges), 0)
        self.assertTrue(cm.is_connected(0, 1))

    def test_ionq_11_qubit(self):
        cm = IONQ_11_QUBIT()
        self.assertEqual(cm.num_qubits, 11)
        for i in range(11):
            for j in range(i + 1, 11):
                self.assertTrue(cm.is_connected(i, j))

    def test_rigetti_80_qubit(self):
        cm = RIGETTI_80_QUBIT()
        self.assertEqual(cm.num_qubits, 80)
        self.assertGreater(len(cm.edges), 0)


class TestDecompositionPass(unittest.TestCase):
    def test_toffoli_decomposition(self):
        decomposer = DecompositionPass(target_gates=['H', 'X', 'CNOT'])
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=TOFFOLI_GATE, qubits=[0, 1, 2]))
        result = decomposer.run(circuit)
        gate_names = [i.gate.name for i in result.instructions]
        self.assertNotIn('TOFFOLI', gate_names)
        self.assertIn('CNOT', gate_names)

    def test_swap_decomposition(self):
        from quantum.gates import SWAP_GATE
        decomposer = DecompositionPass(target_gates=['H', 'X', 'CNOT'])
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=SWAP_GATE, qubits=[0, 1]))
        result = decomposer.run(circuit)
        gate_names = [i.gate.name for i in result.instructions]
        self.assertNotIn('SWAP', gate_names)
        self.assertIn('CNOT', gate_names)


class TestOptimizationPass(unittest.TestCase):
    def test_cancel_inverse_pairs(self):
        optimizer = OptimizationPass()
        circuit = QuantumCircuit(1)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        result = optimizer.run(circuit)
        self.assertEqual(len(result.instructions), 0)

    def test_no_cancellation_different_qubits(self):
        optimizer = OptimizationPass()
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[1]))
        result = optimizer.run(circuit)
        self.assertEqual(len(result.instructions), 2)


class TestLayoutPass(unittest.TestCase):
    def test_trivial_layout(self):
        layout = LayoutPass(method='trivial')
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        result = layout.run(circuit)
        self.assertEqual(result.instructions[0].qubits, [0])

    def test_noise_aware_layout(self):
        layout = LayoutPass(method='noise_aware')
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        qubit_weights = {0: 0.01, 1: 0.1, 2: 0.005}
        result = layout.run(circuit, qubit_weights=qubit_weights)
        self.assertEqual(result.instructions[0].qubits[0], 2)


class TestRoutingPass(unittest.TestCase):
    def test_no_routing_needed(self):
        cm = CouplingMap(num_qubits=3, edges=[(0, 1), (1, 2)])
        router = RoutingPass(coupling_map=cm)
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 1]))
        result = router.run(circuit)
        gate_names = [i.gate.name for i in result.instructions]
        self.assertNotIn('SWAP', gate_names)

    def test_routing_needed(self):
        cm = CouplingMap(num_qubits=3, edges=[(0, 1), (1, 2)])
        router = RoutingPass(coupling_map=cm)
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 2]))
        result = router.run(circuit)
        gate_names = [i.gate.name for i in result.instructions]
        self.assertIn('SWAP', gate_names)


class TestPulseLevelPass(unittest.TestCase):
    def test_pulse_level_trapped_ion(self):
        pulse_pass = PulseLevelPass(HardwarePlatform.TRAPPED_ION)
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=X_GATE, qubits=[0]))
        result = pulse_pass.run(circuit)
        self.assertGreater(len(result.instructions), 0)

    def test_pulse_level_superconducting(self):
        pulse_pass = PulseLevelPass(HardwarePlatform.SUPERCONDUCTING)
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=X_GATE, qubits=[0]))
        result = pulse_pass.run(circuit)
        self.assertGreater(len(result.instructions), 0)


class TestHardwareTranspiler(unittest.TestCase):
    def test_transpile_trapped_ion(self):
        transpiler = HardwareTranspiler(platform=HardwarePlatform.TRAPPED_ION)
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 1]))
        result = transpiler.transpile(circuit, optimization_level=1)
        self.assertEqual(result.num_qubits, 3)
        self.assertGreater(len(result.instructions), 0)

    def test_transpile_with_initial_layout(self):
        transpiler = HardwareTranspiler(platform=HardwarePlatform.TRAPPED_ION)
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        result = transpiler.transpile(circuit, initial_layout={0: 5, 1: 6})
        self.assertEqual(result.instructions[0].qubits[0], 5)

    def test_transpile_and_report(self):
        transpiler = HardwareTranspiler(platform=HardwarePlatform.TRAPPED_ION)
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 1]))
        result, report = transpiler.transpile_and_report(circuit)
        self.assertIn("platform", report)
        self.assertIn("initial_gate_count", report)
        self.assertIn("final_gate_count", report)

    def test_transpile_too_many_qubits(self):
        transpiler = HardwareTranspiler(platform=HardwarePlatform.TRAPPED_ION)
        circuit = QuantumCircuit(20)
        with self.assertRaises(ValueError):
            transpiler.transpile(circuit)


class TestUtilityFunctions(unittest.TestCase):
    def test_transpile_for_hardware(self):
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        result = transpile_for_hardware(circuit, HardwarePlatform.TRAPPED_ION)
        self.assertEqual(result.num_qubits, 3)

    def test_estimate_circuit_depth(self):
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 1]))
        depth = estimate_circuit_depth(circuit)
        self.assertEqual(depth, 2)

    def test_estimate_circuit_depth_empty(self):
        circuit = QuantumCircuit(2)
        depth = estimate_circuit_depth(circuit)
        self.assertEqual(depth, 0)

    def test_estimate_swaps_needed(self):
        cm = CouplingMap(num_qubits=3, edges=[(0, 1), (1, 2)])
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 2]))
        swaps = estimate_swaps_needed(circuit, cm)
        self.assertGreater(swaps, 0)


class TestModuleExports(unittest.TestCase):
    def test_all_exports(self):
        from quantum.hardware_transpiler import __all__
        expected = [
            "CouplingMap", "TranspilerPass", "RoutingPass",
            "DecompositionPass", "OptimizationPass", "LayoutPass",
            "PulseLevelPass", "HardwareTranspiler",
            "IBM_127_QUBIT", "IONQ_11_QUBIT", "RIGETTI_80_QUBIT",
            "transpile_for_hardware", "estimate_circuit_depth", "estimate_swaps_needed",
        ]
        for name in expected:
            self.assertIn(name, __all__)


if __name__ == "__main__":
    unittest.main()
