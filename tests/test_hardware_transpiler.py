"""Tests for hardware_transpiler module."""

import pytest
import numpy as np

from umeros.quantum.hardware_transpiler import (
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
from umeros.quantum.native_gates import HardwarePlatform
from umeros.quantum.circuit import QuantumCircuit
from umeros.quantum.gates import H_GATE, X_GATE, CNOT_GATE, TOFFOLI_GATE


class TestCouplingMap:
    """Tests for CouplingMap class."""

    def test_initialization(self):
        """Test basic CouplingMap creation."""
        cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
        assert cm.num_qubits == 4
        assert len(cm.edges) == 3
        assert cm.directed is False

    def test_is_connected(self):
        """Test connectivity check."""
        cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
        assert cm.is_connected(0, 1) is True
        assert cm.is_connected(1, 0) is True  # Undirected
        assert cm.is_connected(0, 2) is False

    def test_is_connected_directed(self):
        """Test directed connectivity."""
        cm = CouplingMap(num_qubits=3, edges=[(0, 1)], directed=True)
        assert cm.is_connected(0, 1) is True
        assert cm.is_connected(1, 0) is False

    def test_neighbors(self):
        """Test neighbor finding."""
        cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
        assert sorted(cm.neighbors(1)) == [0, 2]

    def test_distance(self):
        """Test shortest path distance."""
        cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
        assert cm.distance(0, 0) == 0
        assert cm.distance(0, 1) == 1
        assert cm.distance(0, 3) == 3

    def test_distance_unreachable(self):
        """Test distance for unreachable qubits."""
        cm = CouplingMap(num_qubits=4, edges=[(0, 1)])
        assert cm.distance(1, 3) == -1

    def test_shortest_path(self):
        """Test shortest path finding."""
        cm = CouplingMap(num_qubits=4, edges=[(0, 1), (1, 2), (2, 3)])
        path = cm.shortest_path(0, 3)
        assert path == [0, 1, 2, 3]

    def test_shortest_path_same_qubit(self):
        """Test shortest path to same qubit."""
        cm = CouplingMap(num_qubits=4, edges=[(0, 1)])
        assert cm.shortest_path(0, 0) == [0]

    def test_validation_out_of_range(self):
        """Test validation for out-of-range qubits."""
        with pytest.raises(ValueError, match="out of range"):
            CouplingMap(num_qubits=4, edges=[(0, 5)])

    def test_validation_self_loop(self):
        """Test validation for self-loops."""
        with pytest.raises(ValueError, match="Self-loop"):
            CouplingMap(num_qubits=4, edges=[(0, 0)])


class TestPredefinedCouplingMaps:
    """Tests for pre-defined coupling maps."""

    def test_ibm_127_qubit(self):
        """Test IBM 127-qubit coupling map."""
        cm = IBM_127_QUBIT()
        assert cm.num_qubits == 127
        assert len(cm.edges) > 0
        assert cm.is_connected(0, 1) is True

    def test_ionq_11_qubit(self):
        """Test IonQ 11-qubit coupling map (all-to-all)."""
        cm = IONQ_11_QUBIT()
        assert cm.num_qubits == 11
        # All-to-all connectivity
        for i in range(11):
            for j in range(i + 1, 11):
                assert cm.is_connected(i, j) is True

    def test_rigetti_80_qubit(self):
        """Test Rigetti 80-qubit coupling map."""
        cm = RIGETTI_80_QUBIT()
        assert cm.num_qubits == 80
        assert len(cm.edges) > 0


class TestDecompositionPass:
    """Tests for DecompositionPass."""

    def test_toffoli_decomposition(self):
        """Test TOFFOLI decomposition."""
        decomposer = DecompositionPass(target_gates=['H', 'X', 'CNOT'])
        circuit = QuantumCircuit(3)
        circuit.instructions.append(
            Instruction(gate=TOFFOLI_GATE, qubits=[0, 1, 2])
        )

        result = decomposer.run(circuit)

        # Should not contain TOFFOLI
        gate_names = [i.gate.name for i in result.instructions]
        assert 'TOFFOLI' not in gate_names
        # Should contain CNOT
        assert 'CNOT' in gate_names

    def test_swap_decomposition(self):
        """Test SWAP decomposition."""
        from umeros.quantum.gates import SWAP_GATE
        decomposer = DecompositionPass(target_gates=['H', 'X', 'CNOT'])
        circuit = QuantumCircuit(2)
        circuit.instructions.append(
            Instruction(gate=SWAP_GATE, qubits=[0, 1])
        )

        result = decomposer.run(circuit)

        gate_names = [i.gate.name for i in result.instructions]
        assert 'SWAP' not in gate_names
        assert 'CNOT' in gate_names


class TestOptimizationPass:
    """Tests for OptimizationPass."""

    def test_cancel_inverse_pairs(self):
        """Test cancellation of adjacent inverse gates."""
        optimizer = OptimizationPass()
        circuit = QuantumCircuit(1)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))

        result = optimizer.run(circuit)

        assert len(result.instructions) == 0

    def test_no_cancellation_different_qubits(self):
        """Test no cancellation when gates are on different qubits."""
        optimizer = OptimizationPass()
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[1]))

        result = optimizer.run(circuit)

        assert len(result.instructions) == 2


class TestLayoutPass:
    """Tests for LayoutPass."""

    def test_trivial_layout(self):
        """Test trivial layout (identity mapping)."""
        layout = LayoutPass(method='trivial')
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))

        result = layout.run(circuit)

        # Qubit mapping should be identity
        assert result.instructions[0].qubits == [0]

    def test_noise_aware_layout(self):
        """Test noise-aware layout with qubit weights."""
        layout = LayoutPass(method='noise_aware')
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))

        # Lower error rate = better qubit
        qubit_weights = {0: 0.01, 1: 0.1, 2: 0.005}
        result = layout.run(circuit, qubit_weights=qubit_weights)

        # Should prefer qubit 2 (lowest error)
        assert result.instructions[0].qubits[0] == 2


class TestRoutingPass:
    """Tests for RoutingPass."""

    def test_no_routing_needed(self):
        """Test when routing is not needed (already connected)."""
        cm = CouplingMap(num_qubits=3, edges=[(0, 1), (1, 2)])
        router = RoutingPass(coupling_map=cm)

        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 1]))

        result = router.run(circuit)

        # No SWAPs needed
        gate_names = [i.gate.name for i in result.instructions]
        assert 'SWAP' not in gate_names

    def test_routing_needed(self):
        """Test when routing is needed (not connected)."""
        cm = CouplingMap(num_qubits=3, edges=[(0, 1), (1, 2)])
        router = RoutingPass(coupling_map=cm)

        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 2]))

        result = router.run(circuit)

        # Should have SWAP gates
        gate_names = [i.gate.name for i in result.instructions]
        assert 'SWAP' in gate_names


class TestPulseLevelPass:
    """Tests for PulseLevelPass."""

    def test_pulse_level_trapped_ion(self):
        """Test pulse-level pass for trapped ion."""
        pulse_pass = PulseLevelPass(HardwarePlatform.TRAPPED_ION)
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=X_GATE, qubits=[0]))

        result = pulse_pass.run(circuit)

        assert len(result.instructions) > 0

    def test_pulse_level_superconducting(self):
        """Test pulse-level pass for superconducting."""
        pulse_pass = PulseLevelPass(HardwarePlatform.SUPERCONDUCTING)
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=X_GATE, qubits=[0]))

        result = pulse_pass.run(circuit)

        assert len(result.instructions) > 0


class TestHardwareTranspiler:
    """Tests for HardwareTranspiler."""

    def test_transpile_trapped_ion(self):
        """Test full transpilation for trapped ion."""
        transpiler = HardwareTranspiler(platform=HardwarePlatform.TRAPPED_ION)
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 1]))

        result = transpiler.transpile(circuit, optimization_level=1)

        assert result.num_qubits == 3
        assert len(result.instructions) > 0

    def test_transpile_with_initial_layout(self):
        """Test transpilation with custom initial layout."""
        transpiler = HardwareTranspiler(platform=HardwarePlatform.TRAPPED_ION)
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))

        result = transpiler.transpile(
            circuit,
            initial_layout={0: 5, 1: 6}
        )

        assert result.instructions[0].qubits[0] == 5

    def test_transpile_and_report(self):
        """Test transpilation with detailed report."""
        transpiler = HardwareTranspiler(platform=HardwarePlatform.TRAPPED_ION)
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 1]))

        result, report = transpiler.transpile_and_report(circuit)

        assert "platform" in report
        assert "initial_gate_count" in report
        assert "final_gate_count" in report

    def test_transpile_too_many_qubits(self):
        """Test error when circuit has too many qubits."""
        transpiler = HardwareTranspiler(platform=HardwarePlatform.TRAPPED_ION)
        circuit = QuantumCircuit(20)  # IonQ only has 11 qubits

        with pytest.raises(ValueError, match="too many qubits"):
            transpiler.transpile(circuit)


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_transpile_for_hardware(self):
        """Test transpile_for_hardware convenience function."""
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))

        result = transpile_for_hardware(circuit, HardwarePlatform.TRAPPED_ION)

        assert result.num_qubits == 3

    def test_estimate_circuit_depth(self):
        """Test circuit depth estimation."""
        circuit = QuantumCircuit(2)
        circuit.instructions.append(Instruction(gate=H_GATE, qubits=[0]))
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 1]))

        depth = estimate_circuit_depth(circuit)

        assert depth == 2

    def test_estimate_circuit_depth_empty(self):
        """Test depth estimation for empty circuit."""
        circuit = QuantumCircuit(2)

        depth = estimate_circuit_depth(circuit)

        assert depth == 0

    def test_estimate_swaps_needed(self):
        """Test SWAP estimation."""
        cm = CouplingMap(num_qubits=3, edges=[(0, 1), (1, 2)])
        circuit = QuantumCircuit(3)
        circuit.instructions.append(Instruction(gate=CNOT_GATE, qubits=[0, 2]))

        swaps = estimate_swaps_needed(circuit, cm)

        assert swaps > 0


class TestModuleExports:
    """Tests for module exports."""

    def test_all_exports(self):
        """Test that all expected classes are exported."""
        from umeros.quantum.hardware_transpiler import __all__

        expected = [
            "CouplingMap",
            "TranspilerPass",
            "RoutingPass",
            "DecompositionPass",
            "OptimizationPass",
            "LayoutPass",
            "PulseLevelPass",
            "HardwareTranspiler",
            "IBM_127_QUBIT",
            "IONQ_11_QUBIT",
            "RIGETTI_80_QUBIT",
            "transpile_for_hardware",
            "estimate_circuit_depth",
            "estimate_swaps_needed",
        ]

        for name in expected:
            assert name in __all__


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
