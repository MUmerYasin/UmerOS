"""Shared pytest fixtures and configuration for quantum module tests."""

import math
import pytest
import numpy as np

# Ensure quantum module is importable
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# ---------------------------------------------------------------------------
# Circuit fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_circuit():
    """Empty single-qubit circuit."""
    from quantum.circuit import QuantumCircuit
    return QuantumCircuit(1)


@pytest.fixture
def two_qubit_circuit():
    """Two-qubit circuit with no gates."""
    from quantum.circuit import QuantumCircuit
    return QuantumCircuit(2)


@pytest.fixture
def bell_circuit():
    """Bell state |Φ+⟩ circuit."""
    from quantum.circuit import QuantumCircuit, QuantumRegister
    qr = QuantumRegister(2, "q")
    cr = QuantumRegister(2, "c")
    circuit = QuantumCircuit(qr, cr)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])
    return circuit


@pytest.fixture
def ghz3_circuit():
    """3-qubit GHZ circuit with measurements."""
    from quantum.circuit import QuantumCircuit
    circuit = QuantumCircuit(3, 3)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.cx(1, 2)
    circuit.measure([0, 1, 2], [0, 1, 2])
    return circuit


@pytest.fixture
def qft3_circuit():
    """3-qubit QFT circuit (without measurements)."""
    from quantum.circuit_library import qft_circuit
    return qft_circuit(3)


@pytest.fixture
def grover2_circuit():
    """2-qubit Grover search circuit."""
    from quantum.circuit_library import grover_circuit
    return grover_circuit(2)


@pytest.fixture
def hamiltonian_circuit():
    """1-qubit circuit: H then Rz(pi/4)."""
    from quantum.circuit import QuantumCircuit
    circuit = QuantumCircuit(1)
    circuit.h(0)
    circuit.rz(math.pi / 4, 0)
    return circuit


@pytest.fixture
def sampler():
    """SamplerV2 instance with default backend."""
    from quantum.primitives import SamplerV2
    return SamplerV2()


@pytest.fixture
def estimator():
    """EstimatorV2 instance with default backend."""
    from quantum.primitives import EstimatorV2
    return EstimatorV2()


@pytest.fixture
def simulator():
    """StatevectorSimulator instance."""
    from quantum.simulator import StatevectorSimulator
    return StatevectorSimulator()


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

@pytest.fixture
def z_operator():
    """Single-qubit Z Pauli operator."""
    from quantum.operators import SparsePauliOp
    return SparsePauliOp.from_list([("Z", 1.0)])


@pytest.fixture
def x_operator():
    """Single-qubit X Pauli operator."""
    from quantum.operators import SparsePauliOp
    return SparsePauliOp.from_list([("X", 1.0)])


@pytest.fixture
def zz_operator():
    """Two-qubit ZZ operator."""
    from quantum.operators import SparsePauliOp
    return SparsePauliOp.from_list([("ZZ", 1.0)])


@pytest.fixture
def local_hamiltonian():
    """Z + 0.5*X local Hamiltonian on 1 qubit."""
    from quantum.operators import SparsePauliOp
    return SparsePauliOp.from_list([("Z", 1.0), ("X", 0.5)])


# ---------------------------------------------------------------------------
# Transpiler
# ---------------------------------------------------------------------------

@pytest.fixture
def linear_coupling():
    """Linear 3-qubit coupling map."""
    from quantum.transpiler import CouplingMap
    return CouplingMap([[0, 1], [1, 2]])


@pytest.fixture
def pass_manager():
    """Default PassManager."""
    from quantum.transpiler import PassManager
    return PassManager()
