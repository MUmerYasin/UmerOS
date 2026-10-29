"""Tests for UmerOS Optimized Quantum Simulator."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantum.optimized_simulator import OptimizedSimulator, OptimizedStatevector
from quantum.simulator import StatevectorSimulator
from quantum.circuit_library import bell_state_circuit
from quantum.gates import H_GATE, X_GATE, CNOT_GATE, Z_GATE
from quantum.circuit import QuantumCircuit, Instruction


class TestOptimizedStatevector(unittest.TestCase):
    def test_zero_state(self):
        sv = OptimizedStatevector.zero(2)
        self.assertEqual(sv.num_qubits, 2)
        self.assertEqual(sv.dim, 4)
        flat = sv.to_flat()
        self.assertAlmostEqual(abs(flat[0]), 1.0, places=10)

    def test_plus_state(self):
        sv = OptimizedStatevector.plus(2)
        flat = sv.to_flat()
        for amp in flat:
            self.assertAlmostEqual(abs(amp), 0.5, places=10)

    def test_to_statevector(self):
        sv = OptimizedStatevector.zero(2)
        std_sv = sv.to_statevector()
        self.assertEqual(std_sv.num_qubits, 2)

    def test_measure_all(self):
        sv = OptimizedStatevector.zero(2)
        results = sv.measure_all(shots=100)
        self.assertEqual(len(results), 100)
        self.assertTrue(all(r == "00" for r in results))

    def test_probabilities(self):
        sv = OptimizedStatevector.plus(2)
        probs = sv.probabilities()
        self.assertEqual(len(probs), 4)
        for p in probs:
            self.assertAlmostEqual(p, 0.25, places=10)


class TestOptimizedSimulator(unittest.TestCase):
    def test_bell_state(self):
        circuit = bell_state_circuit("00")
        sim = OptimizedSimulator(seed=42)
        result = sim.run(circuit, shots=1024)
        self.assertEqual(result.total_shots, 1024)
        # Bell state should produce 00 and 11
        self.assertTrue("00" in result.counts or "11" in result.counts)

    def test_multi_qubit_state(self):
        circuit = bell_state_circuit("00")
        sim = OptimizedSimulator(seed=42)
        result = sim.run(circuit, shots=1024)
        self.assertEqual(result.total_shots, 1024)

    def test_run_with_state(self):
        circuit = bell_state_circuit("00")
        sim = OptimizedSimulator(seed=42)
        state = sim.run_with_state(circuit)
        self.assertEqual(state.num_qubits, 2)

    def test_single_qubit_gates(self):
        circuit = QuantumCircuit(1)
        circuit.h(0)
        sim = OptimizedSimulator(seed=42)
        result = sim.run(circuit, shots=100)
        # H on |0> gives |+>, 50/50
        self.assertTrue("0" in result.counts or "1" in result.counts)

    def test_consistency_with_standard(self):
        """Verify optimized simulator matches standard simulator."""
        circuit = bell_state_circuit("00")
        std_sim = StatevectorSimulator(seed=42)
        opt_sim = OptimizedSimulator(seed=42)
        std_result = std_sim.run(circuit, shots=100)
        opt_result = opt_sim.run(circuit, shots=100)
        # Both should have same keys
        self.assertEqual(set(std_result.counts.keys()), set(opt_result.counts.keys()))

    def test_performance_info(self):
        sim = OptimizedSimulator()
        info = sim.get_performance_info()
        self.assertIn("method", info)
        self.assertIn("max_recommended_qubits", info)


if __name__ == "__main__":
    unittest.main()