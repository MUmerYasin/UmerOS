# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Optimized Quantum Statevector Simulator using NumPy BLAS.

Uses tensor contraction (einsum/tensordot) instead of building full
permutation matrices, achieving O(2^n * 2^k) per gate instead of O(2^(2n)).
Supports up to 20+ qubits on standard hardware.
"""
from __future__ import annotations

import math
import random
from typing import Optional, Sequence, Dict, List, Tuple
from collections import Counter

import numpy as np
from numpy.typing import NDArray

from .gates import Gate
from .circuit import QuantumCircuit, Instruction
from .simulator import Statevector, MeasurementResult


class OptimizedStatevector:
    """State vector stored as a multi-dimensional tensor for fast gate application."""

    def __init__(self, data: NDArray[np.complex128], num_qubits: int):
        self._num_qubits = num_qubits
        self._data = np.asarray(data, dtype=np.complex128).reshape([2] * num_qubits)
        norm = np.linalg.norm(self._data)
        if norm > 1e-15:
            self._data /= norm

    @property
    def num_qubits(self) -> int:
        return self._num_qubits

    @property
    def dim(self) -> int:
        return 2 ** self._num_qubits

    def to_flat(self) -> NDArray[np.complex128]:
        return self._data.reshape(-1).copy()

    def to_statevector(self) -> Statevector:
        return Statevector(self._data.reshape(-1))

    @classmethod
    def zero(cls, num_qubits: int) -> "OptimizedStatevector":
        data = np.zeros([2] * num_qubits, dtype=np.complex128)
        data[(0,) * num_qubits] = 1.0
        return cls(data, num_qubits)

    @classmethod
    def plus(cls, num_qubits: int) -> "OptimizedStatevector":
        data = np.ones([2] * num_qubits, dtype=np.complex128) / math.sqrt(2 ** num_qubits)
        return cls(data, num_qubits)

    def measure_all(self, shots: int = 1) -> List[str]:
        flat = self._data.reshape(-1)
        probs = np.abs(flat) ** 2
        probs = probs / probs.sum()
        indices = np.random.choice(len(flat), size=shots, p=probs)
        return [f"{idx:0{self._num_qubits}b}" for idx in indices]

    def probabilities(self) -> NDArray[np.float64]:
        return (np.abs(self._data.reshape(-1)) ** 2)


class OptimizedSimulator:
    """Optimized simulator using tensor contraction for gate application."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        if seed is not None:
            np.random.seed(seed)

    def run(self, circuit, shots: int = 1024, noise_model=None) -> MeasurementResult:
        state = self._initialize_state(circuit.num_qubits)
        for inst in circuit:
            if inst.gate.name == "measure":
                continue
            state = self._apply_gate(state, inst.gate, inst.qubits)
        bitstrings = state.measure_all(shots=shots)
        counts = Counter(bitstrings)
        return MeasurementResult(dict(counts), circuit.num_qubits)

    def run_with_state(self, circuit, noise_model=None) -> Statevector:
        state = self._initialize_state(circuit.num_qubits)
        for inst in circuit:
            if inst.gate.name == "measure":
                continue
            state = self._apply_gate(state, inst.gate, inst.qubits)
        return state.to_statevector()

    def _initialize_state(self, num_qubits: int) -> OptimizedStatevector:
        return OptimizedStatevector.zero(num_qubits)

    def _apply_gate(self, state: OptimizedStatevector, gate: Gate, qubits: List[int]) -> OptimizedStatevector:
        """Apply gate using tensor contraction (einsum)."""
        mat = np.asarray(gate.matrix, dtype=np.complex128)
        n = state.num_qubits
        k = len(qubits)

        # For single-qubit gates, use einsum for efficiency
        if k == 1:
            q = qubits[0]
            # Build einsum string: apply 2x2 matrix to axis q
            # Input tensor has axes 0..n-1, output same shape
            # We contract: new_data[..., q, ...] = sum_j mat[i,j] * data[..., j, ...]
            axes = list(range(n))
            # Move target qubit to last axis for contraction, then move back
            # Use np.tensordot approach
            data = state._data
            # Reshape to isolate the qubit axis
            # Move qubit axis to position 0
            data_moved = np.moveaxis(data, q, 0)  # shape: (2, 2, ..., 2) with q first
            orig_shape = data_moved.shape
            # Reshape: (2, -1) -> apply mat -> (2, -1) -> reshape back
            flat = data_moved.reshape(2, -1)
            new_flat = mat @ flat
            new_data = new_flat.reshape(orig_shape)
            new_data = np.moveaxis(new_data, 0, q)
            return OptimizedStatevector(new_data, n)

        elif k == 2:
            # Two-qubit gate
            q0, q1 = qubits[0], qubits[1]
            data = state._data
            # Apply using reshape and matrix multiplication
            # Move both qubit axes to front
            data_moved = np.moveaxis(data, [q0, q1], [0, 1])
            orig_shape = data_moved.shape
            # Reshape to (4, -1)
            flat = data_moved.reshape(4, -1)
            new_flat = mat @ flat
            new_data = new_flat.reshape(orig_shape)
            # Move axes back
            new_data = np.moveaxis(new_data, [0, 1], [q0, q1])
            return OptimizedStatevector(new_data, n)

        else:
            # Multi-qubit: fall back to full matrix approach for correctness
            # but use optimized permutation
            data = state._data.reshape(-1)
            dim = 2 ** n
            # Build permutation
            all_qubits = list(range(n))
            other_qubits = [q for q in all_qubits if q not in qubits]
            perm = qubits + other_qubits
            # Use np.einsum for permutation
            # This is complex; fall back to standard approach for k>2
            from .simulator import StatevectorSimulator
            sv = Statevector(state.to_flat())
            std_sim = StatevectorSimulator()
            result_sv = std_sim._apply_gate(sv, gate, qubits, n)
            return OptimizedStatevector(result_sv._data.reshape([2] * n), n)

    def get_performance_info(self) -> dict:
        """Return performance characteristics."""
        return {
            "method": "tensor_contraction",
            "blas_backend": np.__config__.show() if hasattr(np.__config__, "show") else "unknown",
            "max_recommended_qubits": 20,
            "memory_per_qubit_mb": 16,  # 2^20 * 16 bytes for 20 qubits
        }