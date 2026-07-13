"""Tests for Umer OS Quantum Simulation Layer."""
from __future__ import annotations

import math
import unittest

import numpy as np

from quantum.quantum_sim import (
    QuantumCircuitSimulator,
    SuperpositionSchedulerAdapter,
    EntanglementIPCAdapter,
    QuantumDevice,
)
from kernel.scheduler import Task


class TestQuantumCircuitSimulator(unittest.TestCase):

    def setUp(self):
        self.sim = QuantumCircuitSimulator(n_qubits=2)

    def test_initial_state_is_ground(self):
        """State vector should start at |00⟩."""
        self.assertAlmostEqual(self.sim.state[0], 1.0 + 0j)
        self.assertAlmostEqual(np.sum(np.abs(self.sim.state) ** 2), 1.0, places=6)

    def test_reset_returns_to_ground(self):
        self.sim.apply_h(0)
        self.sim.reset()
        self.assertAlmostEqual(self.sim.state[0], 1.0 + 0j)

    def test_hadamard_creates_superposition(self):
        self.sim.apply_h(0)
        probs = self.sim.probabilities()
        # Both |00⟩ and |10⟩ should have equal probability
        self.assertAlmostEqual(probs[0], 0.5, places=5)
        self.assertAlmostEqual(probs[2], 0.5, places=5)

    def test_probabilities_sum_to_one(self):
        self.sim.apply_h(0)
        self.sim.apply_h(1)
        total = np.sum(self.sim.probabilities())
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_x_gate_flips_qubit(self):
        self.sim.apply_x(0)
        probs = self.sim.probabilities()
        # |00⟩ → |10⟩  (qubit 0 is MSB)
        self.assertAlmostEqual(probs[2], 1.0, places=5)

    def test_z_gate_on_ground_state_unchanged(self):
        """Z gate on |0⟩ adds no phase shift to |0⟩ — probability unchanged."""
        self.sim.apply_z(0)
        probs = self.sim.probabilities()
        self.assertAlmostEqual(probs[0], 1.0, places=5)

    def test_cnot_creates_bell_state(self):
        """H on qubit 0 + CNOT → Bell state |Φ+⟩."""
        self.sim.apply_h(0)
        self.sim.apply_cnot(0, 1)
        probs = self.sim.probabilities()
        # Should be 50% |00⟩ and 50% |11⟩
        self.assertAlmostEqual(probs[0], 0.5, places=5)
        self.assertAlmostEqual(probs[3], 0.5, places=5)
        self.assertAlmostEqual(probs[1], 0.0, places=5)
        self.assertAlmostEqual(probs[2], 0.0, places=5)

    def test_measure_returns_valid_index(self):
        self.sim.apply_h(0)
        outcome = self.sim.measure()
        self.assertIn(outcome, range(4))

    def test_measure_collapses_state(self):
        """After measurement, state should be a basis vector."""
        self.sim.apply_h(0)
        self.sim.apply_h(1)
        self.sim.measure()
        probs = self.sim.probabilities()
        # Exactly one probability should be ~1.0
        ones = [p for p in probs if abs(p - 1.0) < 1e-5]
        zeros = [p for p in probs if abs(p) < 1e-5]
        self.assertEqual(len(ones), 1)
        self.assertEqual(len(zeros), 3)

    def test_measure_qubit_returns_zero_or_one(self):
        self.sim.apply_h(0)
        bit = self.sim.measure_qubit(0)
        self.assertIn(bit, (0, 1))

    def test_expectation_z_ground_state(self):
        """⟨Z⟩ of |0⟩ = +1."""
        sim = QuantumCircuitSimulator(n_qubits=1)
        ev = sim.expectation_z(0)
        self.assertAlmostEqual(ev, 1.0, places=5)

    def test_expectation_z_excited_state(self):
        """⟨Z⟩ of |1⟩ = -1."""
        sim = QuantumCircuitSimulator(n_qubits=1)
        sim.apply_x(0)
        ev = sim.expectation_z(0)
        self.assertAlmostEqual(ev, -1.0, places=5)

    def test_state_vector_returns_copy(self):
        sv = self.sim.state_vector()
        sv[0] = 99  # modifying the copy should not affect internal state
        self.assertAlmostEqual(self.sim.state[0], 1.0 + 0j)

    def test_invalid_qubit_index_raises(self):
        with self.assertRaises(ValueError):
            self.sim.apply_h(5)  # only 2 qubits (0 and 1)

    def test_cnot_same_qubit_raises(self):
        with self.assertRaises(ValueError):
            self.sim.apply_cnot(0, 0)

    def test_invalid_n_qubits_raises(self):
        with self.assertRaises(ValueError):
            QuantumCircuitSimulator(n_qubits=0)
        with self.assertRaises(ValueError):
            QuantumCircuitSimulator(n_qubits=21)

    def test_method_chaining(self):
        """Fluent API: apply_h().apply_x().apply_z() should work."""
        self.sim.apply_h(0).apply_x(1).apply_z(0)
        probs = self.sim.probabilities()
        self.assertAlmostEqual(np.sum(probs), 1.0, places=6)

    def test_single_qubit_simulator(self):
        sim = QuantumCircuitSimulator(n_qubits=1)
        sim.apply_h(0)
        probs = sim.probabilities()
        self.assertAlmostEqual(probs[0], 0.5, places=5)
        self.assertAlmostEqual(probs[1], 0.5, places=5)


class TestSuperpositionSchedulerAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = SuperpositionSchedulerAdapter()

    def test_evaluate_returns_dict_keyed_by_pid(self):
        tasks = [
            Task(pid=1, name="a", priority=0.3),
            Task(pid=2, name="b", priority=0.7),
        ]
        result = self.adapter.evaluate_task_paths(tasks)
        self.assertIn(1, result)
        self.assertIn(2, result)

    def test_scores_in_valid_range(self):
        tasks = [Task(pid=i, name=f"t{i}", priority=0.5) for i in range(1, 6)]
        result = self.adapter.evaluate_task_paths(tasks)
        for pid, score in result.items():
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_empty_task_list(self):
        result = self.adapter.evaluate_task_paths([])
        self.assertEqual(result, {})

    def test_higher_priority_tends_to_higher_score(self):
        """Over many samples the high-priority task should average higher."""
        scores_low  = []
        scores_high = []
        for _ in range(50):
            t_low  = Task(pid=1, name="low",  priority=0.1)
            t_high = Task(pid=2, name="high", priority=0.9)
            r = self.adapter.evaluate_task_paths([t_low, t_high])
            scores_low.append(r[1])
            scores_high.append(r[2])
        avg_low  = sum(scores_low)  / len(scores_low)
        avg_high = sum(scores_high) / len(scores_high)
        self.assertGreater(avg_high, avg_low)


class TestEntanglementIPCAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = EntanglementIPCAdapter()

    def test_subscribe_and_publish(self):
        self.adapter.subscribe(pid=1, channel="sync")
        self.adapter.subscribe(pid=2, channel="sync")
        bit, msg = self.adapter.publish(channel="sync", message={"data": 42})
        self.assertIn(bit, (0, 1))
        self.assertEqual(msg["data"], 42)
        self.assertIn("_quantum", msg)

    def test_quantum_metadata_in_message(self):
        self.adapter.subscribe(1, "ch")
        _, msg = self.adapter.publish("ch", {"x": 1})
        q = msg["_quantum"]
        self.assertIn("pub_bit", q)
        self.assertIn("sub_bit", q)
        self.assertIn(q["pub_bit"], (0, 1))
        self.assertIn(q["sub_bit"], (0, 1))

    def test_sync_state_returns_probabilities(self):
        state = self.adapter.sync_state()
        self.assertIn("probabilities", state)
        probs = state["probabilities"]
        self.assertAlmostEqual(sum(probs), 1.0, places=5)


class TestQuantumDeviceAbstract(unittest.TestCase):

    def test_all_methods_raise_not_implemented(self):
        dev = QuantumDevice()
        with self.assertRaises(NotImplementedError):
            dev.allocate_qubits(2)
        with self.assertRaises(NotImplementedError):
            dev.run_circuit([])
        with self.assertRaises(NotImplementedError):
            dev.get_fidelity()
        with self.assertRaises(NotImplementedError):
            dev.deallocate([0, 1])


if __name__ == "__main__":
    unittest.main()
