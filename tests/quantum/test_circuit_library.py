"""Tests for quantum.circuit_library — all library circuits."""

import math
import pytest
import numpy as np

from quantum.circuit import QuantumCircuit
from quantum.simulator import StatevectorSimulator

# Import all circuit library functions
from quantum.circuit_library import (
    bell_state_circuit,
    ghz_circuit,
    w_state_circuit,
    qft_circuit,
    inverse_qft_circuit,
    grover_circuit,
    quantum_walk_circuit,
    bb84_sender_circuit,
    bb84_receiver_circuit,
    teleportation_circuit,
    superdense_coding_circuit,
    grover_diffusion_circuit,
    qpe_circuit_simple,
    random_circuit,
    hardware_efficient_ansatz,
    bit_flip_encode_circuit,
    phase_flip_encode_circuit,
    create_ghz_state,
    create_bell_state,
    create_w_state,
    create_qft,
    create_random_circuit,
)


sim = StatevectorSimulator()


class TestBellState:
    def test_00(self):
        qc = bell_state_circuit("00")
        sv = sim.run_with_state(qc)
        probs = sv.probabilities_dict()
        assert "00" in probs
        assert "11" in probs
        np.testing.assert_allclose(probs["00"], 0.5, atol=1e-10)

    def test_01(self):
        qc = bell_state_circuit("01")
        sv = sim.run_with_state(qc)
        probs = sv.probabilities_dict()
        assert "01" in probs
        assert "10" in probs

    def test_10(self):
        qc = bell_state_circuit("10")
        sv = sim.run_with_state(qc)
        probs = sv.probabilities_dict()
        assert "01" in probs or "10" in probs

    def test_11(self):
        qc = bell_state_circuit("11")
        sv = sim.run_with_state(qc)
        probs = sv.probabilities_dict()
        assert "11" in probs or "00" in probs


class TestGHZ:
    def test_3_qubits(self):
        qc = ghz_circuit(3)
        sv = sim.run_with_state(qc)
        probs = sv.probabilities_dict()
        assert "000" in probs
        assert "111" in probs
        np.testing.assert_allclose(probs["000"], 0.5, atol=1e-10)
        np.testing.assert_allclose(probs["111"], 0.5, atol=1e-10)

    def test_2_qubits(self):
        qc = ghz_circuit(2)
        sv = sim.run_with_state(qc)
        probs = sv.probabilities_dict()
        assert "00" in probs
        assert "11" in probs


class TestWState:
    def test_3_qubits(self):
        qc = w_state_circuit(3)
        sv = sim.run_with_state(qc)
        probs = sv.probabilities_dict()
        assert "001" in probs
        assert "010" in probs
        assert "100" in probs
        for key in ["001", "010", "100"]:
            np.testing.assert_allclose(probs[key], 1.0 / 3, atol=1e-10)


class TestQFT:
    def test_3_qubits(self):
        qc = qft_circuit(3)
        assert qc.num_qubits == 3
        assert qc.size() > 0

    def test_1_qubit(self):
        qc = qft_circuit(1)
        assert qc.num_qubits == 1


class TestInverseQFT:
    def test_3_qubits(self):
        qc = inverse_qft_circuit(3)
        assert qc.num_qubits == 3


class TestGrover:
    def test_2_qubits(self):
        qc = grover_circuit(2)
        assert qc.num_qubits == 2
        assert qc.size() > 0

    def test_3_qubits(self):
        qc = grover_circuit(3)
        assert qc.num_qubits == 3


class TestQuantumWalk:
    def test_default(self):
        qc = quantum_walk_circuit(num_steps=2, num_qubits=3)
        assert qc.num_qubits == 4  # 3 position + 1 coin


class TestBB84:
    def test_sender(self):
        qc = bb84_sender_circuit([0, 1, 0], [0, 1, 0])
        assert qc.num_qubits == 3

    def test_receiver(self):
        qc = bb84_receiver_circuit([0, 1, 0])
        assert qc.num_qubits == 3


class TestTeleportation:
    def test_circuit(self):
        qc = teleportation_circuit()
        assert qc.num_qubits == 3


class TestSuperdenseCoding:
    def test_00(self):
        qc = superdense_coding_circuit("00")
        assert qc.num_qubits == 2

    def test_11(self):
        qc = superdense_coding_circuit("11")
        assert qc.num_qubits == 2


class TestGroverDiffusion:
    def test_2_qubits(self):
        qc = grover_diffusion_circuit(2)
        assert qc.num_qubits == 2

    def test_3_qubits(self):
        qc = grover_diffusion_circuit(3)
        assert qc.num_qubits == 3


class TestQPE:
    def test_default(self):
        qc = qpe_circuit_simple(3)
        assert qc.num_qubits == 4  # 3 counting + 1 eigen


class TestRandomCircuit:
    def test_seed_reproducibility(self):
        qc1 = random_circuit(3, depth=3, seed=42)
        qc2 = random_circuit(3, depth=3, seed=42)
        assert qc1.size() == qc2.size()

    def test_different_seeds(self):
        qc1 = random_circuit(3, depth=3, seed=42)
        qc2 = random_circuit(3, depth=3, seed=99)
        # They may or may not differ, but both should work
        assert qc1.num_qubits == qc2.num_qubits


class TestHardwareEfficientAnsatz:
    def test_default(self):
        qc = hardware_efficient_ansatz(3, layers=2)
        assert qc.num_qubits == 3
        assert qc.size() > 0

    def test_full_entanglement(self):
        qc = hardware_efficient_ansatz(3, layers=1, entanglement="full")
        assert qc.num_qubits == 3


class TestBitFlipEncode:
    def test_encode(self):
        qc = bit_flip_encode_circuit(3)
        assert qc.num_qubits == 3
        sv = sim.run_with_state(qc)
        probs = sv.probabilities_dict()
        assert "000" in probs or "111" in probs


class TestPhaseFlipEncode:
    def test_encode(self):
        qc = phase_flip_encode_circuit(3)
        assert qc.num_qubits == 3


class TestAliases:
    def test_create_ghz(self):
        qc = create_ghz_state(3)
        assert qc.num_qubits == 3

    def test_create_bell(self):
        qc = create_bell_state("00")
        assert qc.num_qubits == 2

    def test_create_w(self):
        qc = create_w_state(3)
        assert qc.num_qubits == 3

    def test_create_qft(self):
        qc = create_qft(3)
        assert qc.num_qubits == 3

    def test_create_random(self):
        qc = create_random_circuit(3, depth=2, seed=42)
        assert qc.num_qubits == 3
