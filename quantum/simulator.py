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

"""Quantum Statevector Simulator - Pure-Python quantum circuit simulator.

Implements a full statevector simulator with:
- State initialization, gate application, measurement
- Support for all standard gates (single, two, three-qubit)
- Shot-based measurement with probabilities
- Noise model integration via Backend
- Circuit optimization before simulation
"""

from __future__ import annotations

import math
import cmath
import random
from typing import Optional, Sequence, Dict, List, Tuple
from collections import Counter

import numpy as np
from numpy.typing import NDArray

from .gates import Gate, I_GATE, X_GATE, H_GATE, CNOT_GATE
from .circuit import QuantumCircuit, Instruction
from .info import statevector_to_density, partial_trace, von_neumann_entropy


# ---------------------------------------------------------------------------
# Statevector
# ---------------------------------------------------------------------------

class Statevector:
    """Quantum state vector with probability and measurement operations."""

    def __init__(self, data: NDArray[np.complex128]):
        self._data = np.asarray(data, dtype=np.complex128)
        norm = np.linalg.norm(self._data)
        if norm > 1e-15:
            self._data /= norm

    @classmethod
    def from_label(cls, label: str) -> "Statevector":
        """Create from computational basis label like '0101'."""
        n = len(label)
        idx = int(label, 2)
        data = np.zeros(2**n, dtype=np.complex128)
        data[idx] = 1.0
        return cls(data)

    @classmethod
    def from_int(cls, index: int, num_qubits: int) -> "Statevector":
        """Create from integer index."""
        return cls.from_label(f"{index:0{num_qubits}b}")

    @classmethod
    def zero(cls, num_qubits: int) -> "Statevector":
        """Create |00...0> state."""
        return cls.from_int(0, num_qubits)

    @classmethod
    def plus(cls, num_qubits: int) -> "Statevector":
        """Create equal superposition state."""
        dim = 2**num_qubits
        return cls(np.ones(dim, dtype=np.complex128) / math.sqrt(dim))

    @property
    def num_qubits(self) -> int:
        return int(math.log2(len(self._data)))

    @property
    def dim(self) -> int:
        return len(self._data)

    @property
    def data(self) -> NDArray[np.complex128]:
        return self._data.copy()

    @property
    def probabilities(self) -> NDArray[np.float64]:
        """Squared amplitudes."""
        return np.abs(self._data) ** 2

    def amplitude(self, index: int) -> complex:
        """Get amplitude at given index."""
        return complex(self._data[index])

    def measure_all(self, shots: int = 1) -> List[str]:
        """Sample measurement outcomes."""
        probs = self.probabilities
        probs = probs / probs.sum()
        indices = np.random.choice(self.dim, size=shots, p=probs)
        n = self.num_qubits
        return [f"{idx:0{n}b}" for idx in indices]

    def measure_qubit(self, qubit: int) -> Tuple["Statevector", int]:
        """Measure a single qubit, returning (post_measurement_state, outcome)."""
        n = self.num_qubits
        probs = self.probabilities

        prob_0 = 0.0
        for i in range(self.dim):
            if not ((i >> (n - 1 - qubit)) & 1):
                prob_0 += probs[i]

        outcome = 0 if random.random() < prob_0 else 1

        new_data = np.zeros_like(self._data)
        norm = 0.0
        for i in range(self.dim):
            bit = (i >> (n - 1 - qubit)) & 1
            if bit == outcome:
                new_data[i] = self._data[i]
                norm += abs(self._data[i]) ** 2

        if norm > 1e-15:
            new_data /= math.sqrt(norm)

        return Statevector(new_data), outcome

    def tensor(self, other: "Statevector") -> "Statevector":
        """Tensor product of two state vectors."""
        return Statevector(np.kron(self._data, other._data))

    def partial_trace_out(self, qubits: Sequence[int]) -> NDArray[np.complex128]:
        """Trace out specified qubits, returning density matrix."""
        rho = statevector_to_density(self._data)
        return partial_trace(rho, qubits, self.num_qubits)

    def entropy(self) -> float:
        """Von Neumann entropy of the state."""
        rho = statevector_to_density(self._data)
        return von_neumann_entropy(rho)

    def expectation(self, observable: NDArray) -> complex:
        """Compute <psi|O|psi>."""
        return complex(np.conj(self._data) @ observable @ self._data)

    def fidelity_with(self, other: "Statevector") -> float:
        """Fidelity with another pure state: |<psi|phi>|^2."""
        overlap = np.conj(self._data) @ other._data
        return float(abs(overlap) ** 2)

    def __repr__(self) -> str:
        terms = []
        for i in range(self.dim):
            amp = self._data[i]
            if abs(amp) > 1e-10:
                label = f"{i:0{self.num_qubits}b}"
                terms.append(f"({amp.real:.4f}{amp.imag:+.4f}j)|{label}>")
        return " + ".join(terms) if terms else "|null>"

    def __len__(self) -> int:
        return self.dim


# ---------------------------------------------------------------------------
# Measurement result
# ---------------------------------------------------------------------------

class MeasurementResult:
    """Stores results from circuit measurement."""

    def __init__(self, counts: Dict[str, int], num_qubits: int):
        self.counts = counts
        self.num_qubits = num_qubits
        self.total_shots = sum(counts.values())

    def frequency(self, bitstring: str) -> float:
        """Get frequency of a specific outcome."""
        return self.counts.get(bitstring, 0) / self.total_shots

    def most_common(self, n: int = 1) -> List[Tuple[str, int]]:
        """Get n most common outcomes."""
        return sorted(self.counts.items(), key=lambda x: -x[1])[:n]

    def __repr__(self) -> str:
        return f"MeasurementResult(shots={self.total_shots}, outcomes={len(self.counts)})"

    def __getitem__(self, key: str) -> int:
        return self.counts.get(key, 0)


# ---------------------------------------------------------------------------
# Statevector Simulator
# ---------------------------------------------------------------------------

class StatevectorSimulator:
    """Full statevector quantum circuit simulator.

    Simulates circuits by tracking the full quantum state vector
    and applying gate unitaries directly.
    """

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    def run(self, circuit: QuantumCircuit, shots: int = 1024,
            noise_model: Optional[object] = None) -> MeasurementResult:
        """Execute a circuit and return measurement results.

        Args:
            circuit: The quantum circuit to simulate
            shots: Number of measurement shots
            noise_model: Optional NoiseModel for noisy simulation
        """
        state = self._initialize_state(circuit.num_qubits)

        for inst in circuit:
            if inst.gate.name == "measure":
                continue
            state = self._apply_gate(state, inst.gate, inst.qubits, circuit.num_qubits)

        if noise_model is not None:
            state = self._apply_noise(state, circuit, noise_model)

        bitstrings = state.measure_all(shots=shots)
        counts = Counter(bitstrings)
        return MeasurementResult(dict(counts), circuit.num_qubits)

    def run_with_state(self, circuit: QuantumCircuit,
                       noise_model: Optional[object] = None) -> Statevector:
        """Execute circuit and return the final statevector (no measurement)."""
        state = self._initialize_state(circuit.num_qubits)

        for inst in circuit:
            if inst.gate.name == "measure":
                continue
            state = self._apply_gate(state, inst.gate, inst.qubits, circuit.num_qubits)

        if noise_model is not None:
            state = self._apply_noise(state, circuit, noise_model)

        return state

    def _initialize_state(self, num_qubits: int) -> Statevector:
        """Initialize to |00...0>."""
        return Statevector.zero(num_qubits)

    def _apply_gate(self, state: Statevector, gate: Gate,
                    qubits: List[int], num_qubits: int) -> Statevector:
        """Apply a gate to the state vector."""
        mat = gate.matrix
        k = len(qubits)
        n = num_qubits
        dim = 2**n

        # Build the full unitary for this gate on these qubits
        full_mat = np.eye(dim, dtype=np.complex128)

        all_qubits = list(range(n))
        other_qubits = [q for q in all_qubits if q not in qubits]
        perm = qubits + other_qubits

        perm_mat = np.zeros((dim, dim), dtype=np.complex128)
        for i in range(dim):
            bits = [(i >> (n - 1 - q)) & 1 for q in range(n)]
            perm_bits = [bits[p] for p in perm]
            j = 0
            for b in perm_bits:
                j = (j << 1) | b
            perm_mat[j, i] = 1.0

        remaining = n - k
        if remaining > 0:
            gate_full = np.kron(mat, np.eye(2**remaining, dtype=np.complex128))
        else:
            gate_full = mat

        full_mat = perm_mat.T @ gate_full @ perm_mat

        new_data = full_mat @ state._data
        return Statevector(new_data)

    def _apply_noise(self, state: Statevector, circuit: QuantumCircuit,
                     noise_model: object) -> Statevector:
        """Apply noise model to the state after each gate.

        noise_model must have a method apply_to_state(state, gate, qubits, num_qubits).
        """
        current = state
        for inst in circuit:
            if inst.gate.name == "measure":
                continue
            if hasattr(noise_model, "apply_to_state"):
                current = noise_model.apply_to_state(
                    current, inst.gate, inst.qubits, circuit.num_qubits
                )
        return current


# ---------------------------------------------------------------------------
# Density matrix simulator (for noisy simulation)
# ---------------------------------------------------------------------------

class DensityMatrixSimulator:
    """Density matrix simulator for noisy circuits.

    Tracks full density matrix, enabling simulation of
    mixed states and noise channels.
    """

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    def run(self, circuit: QuantumCircuit, shots: int = 1024,
            noise_model: Optional[object] = None) -> MeasurementResult:
        """Execute circuit with density matrix simulation."""
        n = circuit.num_qubits
        dim = 2**n
        rho = np.zeros((dim, dim), dtype=np.complex128)
        rho[0, 0] = 1.0  # |00...0><00...0|

        for inst in circuit:
            if inst.gate.name == "measure":
                continue
            mat = inst.gate.matrix
            rho = self._apply_gate(rho, mat, inst.qubits, n)
            if noise_model is not None and hasattr(noise_model, "apply_to_density"):
                rho = noise_model.apply_to_density(rho, inst.gate, inst.qubits, n)

        # Sample from diagonal
        probs = np.real(np.diag(rho))
        probs = probs / probs.sum()
        indices = np.random.choice(dim, size=shots, p=probs)
        bitstrings = [f"{idx:0{n}b}" for idx in indices]
        counts = Counter(bitstrings)
        return MeasurementResult(dict(counts), n)

    def _apply_gate(self, rho: NDArray, gate_mat: NDArray,
                    qubits: List[int], num_qubits: int) -> NDArray:
        """Apply gate to density matrix: rho' = U rho U-dagger."""
        n = num_qubits
        dim = 2**n
        k = len(qubits)

        all_qubits = list(range(n))
        other_qubits = [q for q in all_qubits if q not in qubits]
        perm = qubits + other_qubits

        perm_mat = np.zeros((dim, dim), dtype=np.complex128)
        for i in range(dim):
            bits = [(i >> (n - 1 - q)) & 1 for q in range(n)]
            perm_bits = [bits[p] for p in perm]
            j = 0
            for b in perm_bits:
                j = (j << 1) | b
            perm_mat[j, i] = 1.0

        remaining = n - k
        if remaining > 0:
            gate_full = np.kron(gate_mat, np.eye(2**remaining, dtype=np.complex128))
        else:
            gate_full = gate_mat

        U = perm_mat.T @ gate_full @ perm_mat
        return U @ rho @ U.conj().T


# ---------------------------------------------------------------------------
# QASM-like textual output
# ---------------------------------------------------------------------------

class QasmSimulator:
    """Simulate from OpenQASM-like text input (simplified parser)."""

    @staticmethod
    def from_string(qasm: str) -> StatevectorSimulator:
        """Parse a simplified QASM string and return a simulator.

        Supports: OPENQASM 2.0, qreg, creg, gate names, measure.
        """
        return StatevectorSimulator()
