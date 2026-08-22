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

"""Quantum Information — Density matrices, entanglement, entropy, channels.

Implements density matrix operations, partial trace, von Neumann entropy,
purity, fidelity, quantum channels (Kraus operators), and entanglement measures.
"""

from __future__ import annotations

import math
import cmath
from typing import Optional, Sequence, Union, List, Tuple
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Density matrix operations
# ---------------------------------------------------------------------------

def statevector_to_density(statevector: NDArray) -> NDArray[np.complex128]:
    """Convert a state vector |ψ⟩ to density matrix ρ = |ψ⟩⟨ψ|."""
    sv = np.asarray(statevector, dtype=np.complex128)
    return np.outer(sv, np.conj(sv))


def partial_trace(rho: NDArray, trace_over: Sequence[int],
                  num_qubits: int) -> NDArray[np.complex128]:
    """Trace out specified qubits from a density matrix.

    Args:
        rho: Density matrix of size (2^n x 2^n)
        trace_over: List of qubit indices to trace out
        num_qubits: Total number of qubits
    Returns:
        Reduced density matrix
    """
    trace_over = sorted(trace_over)
    n = num_qubits
    dim = 2**n

    result = rho.reshape([2] * (2 * n))
    # Trace over specified qubits (both row and column dimensions)
    for q in reversed(trace_over):
        result = np.trace(result, axis1=q, axis2=q + n)
        # After trace, dimensions shift
        n -= 1

    return result.reshape(2**n, 2**n)


def partial_transpose(rho: NDArray, system: int, num_qubits: int) -> NDArray[np.complex128]:
    """Partial transpose over a subsystem (for entanglement detection)."""
    n = num_qubits
    dim = 2**n
    rho_mat = rho.reshape([2] * (2 * n))

    # Swap row and column indices for the target system
    axes = list(range(2 * n))
    axes[system] = n + system
    axes[n + system] = system

    return rho_mat.transpose(axes).reshape(dim, dim)


def purity(rho: NDArray) -> float:
    """Compute purity Tr(ρ²). Pure states have purity=1, maximally mixed have purity=1/d."""
    return float(np.real(np.trace(rho @ rho)))


def fidelity(rho: NDArray, sigma: NDArray) -> float:
    """Quantum fidelity F(ρ, σ).

    For pure states |ψ⟩ and |φ⟩: F = |⟨ψ|φ⟩|²
    """
    rho_sqrt = _matrix_sqrt(rho)
    inner = rho_sqrt @ sigma @ rho_sqrt
    inner_sqrt = _matrix_sqrt(inner)
    return float(np.real(np.trace(inner_sqrt)) ** 2)


def _matrix_sqrt(A: NDArray) -> NDArray[np.complex128]:
    """Matrix square root via eigendecomposition."""
    eigenvalues, eigenvectors = np.linalg.eigh(A)
    sqrt_eigenvalues = np.sqrt(np.maximum(eigenvalues, 0))
    return eigenvectors @ np.diag(sqrt_eigenvalues) @ eigenvectors.conj().T


def trace_distance(rho: NDArray, sigma: NDArray) -> float:
    """Trace distance: T(ρ, σ) = (1/2)||ρ - σ||₁"""
    diff = rho - sigma
    eigenvalues = np.linalg.eigvalsh(diff)
    return float(0.5 * np.sum(np.abs(eigenvalues)))


def von_neumann_entropy(rho: NDArray) -> float:
    """Von Neumann entropy: S(ρ) = -Tr(ρ log₂ ρ)"""
    eigenvalues = np.linalg.eigvalsh(rho)
    eigenvalues = eigenvalues[eigenvalues > 1e-15]  # avoid log(0)
    return float(-np.sum(eigenvalues * np.log2(eigenvalues)))


def relative_entropy(rho: NDArray, sigma: NDArray) -> float:
    """Quantum relative entropy: S(ρ||σ) = Tr(ρ(log ρ - log σ))"""
    eigenvalues_rho = np.linalg.eigvalsh(rho)
    eigenvalues_sigma = np.linalg.eigvalsh(sigma)

    # Filter out zero eigenvalues
    mask_rho = eigenvalues_rho > 1e-15
    mask_sigma = eigenvalues_sigma > 1e-15

    result = 0.0
    # This is a simplified version - full implementation requires
    # simultaneous diagonalization
    log_rho = np.zeros_like(rho)
    log_sigma = np.zeros_like(sigma)

    evals_r, evecs_r = np.linalg.eigh(rho)
    evals_s, evecs_s = np.linalg.eigh(sigma)

    for i, ev in enumerate(evals_r):
        if ev > 1e-15:
            log_rho += math.log2(ev) * np.outer(evecs_r[:, i], np.conj(evecs_r[:, i]))

    for i, ev in enumerate(evals_s):
        if ev > 1e-15:
            log_sigma += math.log2(ev) * np.outer(evecs_s[:, i], np.conj(evecs_s[:, i]))

    return float(np.real(np.trace(rho @ (log_rho - log_sigma))))


def concurrence(rho: NDArray) -> float:
    """Concurrence for a two-qubit density matrix.

    Returns 0 for separable states, 1 for maximally entangled states.
    """
    if rho.shape != (4, 4):
        raise ValueError("Concurrence requires a 4x4 (2-qubit) density matrix")

    # Spin-flip matrix
    sigma_y = np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
    sigma_y_y = np.kron(sigma_y, sigma_y)

    rho_tilde = sigma_y_y @ np.conj(rho) @ sigma_y_y
    R = rho @ rho_tilde

    eigenvalues = np.sqrt(np.maximum(np.real(np.linalg.eigvalsh(R)), 0))
    eigenvalues = np.sort(eigenvalues)[::-1]  # descending

    C = max(0, eigenvalues[0] - eigenvalues[1] - eigenvalues[2] - eigenvalues[3])
    return float(C)


def entanglement_of_formation(rho: NDArray) -> float:
    """Entanglement of formation for a two-qubit state."""
    C = concurrence(rho)
    if C < 1e-15:
        return 0.0
    x = 0.5 * (1 + math.sqrt(1 - C**2))
    return float(-x * math.log2(x) - (1 - x) * math.log2(1 - x))


def negativity(rho: NDArray, num_qubits: int) -> float:
    """Negativity: (||ρ^T_A||₁ - 1) / 2"""
    rho_pt = partial_transpose(rho, 0, num_qubits)
    eigenvalues = np.linalg.eigvalsh(rho_pt)
    return float(max(0, -np.sum(np.minimum(eigenvalues, 0))))


# ---------------------------------------------------------------------------
# Maximally entangled states
# ---------------------------------------------------------------------------

def bell_state(kind: str = "phi_plus") -> NDArray[np.complex128]:
    """Bell states: |Φ+⟩, |Φ-⟩, |Ψ+⟩, |Ψ-⟩."""
    states = {
        "phi_plus":  np.array([1, 0, 0, 1], dtype=np.complex128) / math.sqrt(2),
        "phi_minus": np.array([1, 0, 0, -1], dtype=np.complex128) / math.sqrt(2),
        "psi_plus":  np.array([0, 1, 1, 0], dtype=np.complex128) / math.sqrt(2),
        "psi_minus": np.array([0, 1, -1, 0], dtype=np.complex128) / math.sqrt(2),
    }
    return states[kind]


def ghz_state(num_qubits: int) -> NDArray[np.complex128]:
    """GHZ state: (|00...0⟩ + |11...1⟩) / √2"""
    dim = 2**num_qubits
    state = np.zeros(dim, dtype=np.complex128)
    state[0] = 1 / math.sqrt(2)
    state[-1] = 1 / math.sqrt(2)
    return state


def w_state(num_qubits: int) -> NDArray[np.complex128]:
    """W state: equal superposition of single-excitation states."""
    dim = 2**num_qubits
    state = np.zeros(dim, dtype=np.complex128)
    for i in range(num_qubits):
        index = 1 << (num_qubits - 1 - i)
        state[index] = 1 / math.sqrt(num_qubits)
    return state


# ---------------------------------------------------------------------------
# Quantum channels (Kraus representation)
# ---------------------------------------------------------------------------

@dataclass
class KrausChannel:
    """Quantum channel defined by Kraus operators: ρ → Σ_k A_k ρ A_k†"""
    kraus_ops: List[NDArray[np.complex128]]

    def apply(self, rho: NDArray) -> NDArray[np.complex128]:
        """Apply channel to density matrix."""
        result = np.zeros_like(rho)
        for A in self.kraus_ops:
            result += A @ rho @ A.conj().T
        return result

    def is_valid(self) -> bool:
        """Check trace-preserving condition: Σ_k A_k† A_k = I"""
        dim = self.kraus_ops[0].shape[0]
        total = np.zeros((dim, dim), dtype=np.complex128)
        for A in self.kraus_ops:
            total += A.conj().T @ A
        return np.allclose(total, np.eye(dim), atol=1e-10)


def depolarizing_channel(p: float) -> KrausChannel:
    """Depolarizing channel: with probability p, replaces state with I/2."""
    return KrausChannel([
        math.sqrt(1 - 3*p/4) * np.eye(2, dtype=np.complex128),
        math.sqrt(p/4) * np.array([[0, 1], [1, 0]], dtype=np.complex128),
        math.sqrt(p/4) * np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
        math.sqrt(p/4) * np.array([[1, 0], [0, -1]], dtype=np.complex128),
    ])


def amplitude_damping(gamma: float) -> KrausChannel:
    """Amplitude damping channel (models T1 relaxation)."""
    return KrausChannel([
        np.array([[1, 0], [0, math.sqrt(1 - gamma)]], dtype=np.complex128),
        np.array([[0, math.sqrt(gamma)], [0, 0]], dtype=np.complex128),
    ])


def phase_damping(gamma: float) -> KrausChannel:
    """Phase damping channel (models T2 dephasing)."""
    return KrausChannel([
        np.array([[1, 0], [0, math.sqrt(1 - gamma)]], dtype=np.complex128),
        np.array([[0, 0], [0, math.sqrt(gamma)]], dtype=np.complex128),
    ])


def bit_flip_channel(p: float) -> KrausChannel:
    """Bit flip channel: X with probability p."""
    return KrausChannel([
        math.sqrt(1 - p) * np.eye(2, dtype=np.complex128),
        math.sqrt(p) * np.array([[0, 1], [1, 0]], dtype=np.complex128),
    ])


def phase_flip_channel(p: float) -> KrausChannel:
    """Phase flip channel: Z with probability p."""
    return KrausChannel([
        math.sqrt(1 - p) * np.eye(2, dtype=np.complex128),
        math.sqrt(p) * np.array([[1, 0], [0, -1]], dtype=np.complex128),
    ])


def thermal_relaxation(t1: float, t2: float, time: float) -> KrausChannel:
    """Thermal relaxation channel (combined T1 and T2).

    Args:
        t1: T1 relaxation time
        t2: T2 dephasing time (must be <= 2*T1)
        time: elapsed time
    """
    if t2 > 2 * t1:
        raise ValueError("T2 must be <= 2*T1")

    exp_t1 = math.exp(-time / t1) if t1 > 0 else 0
    exp_t2 = math.exp(-time / t2) if t2 > 0 else 0

    p_reset = 0.5 * (1 - exp_t1)
    gamma_z = 0.5 * (1 - exp_t2 / (1 - p_reset + 1e-15))

    return KrausChannel([
        math.sqrt(1 - p_reset) * np.array([[1, 0], [0, math.sqrt(1 - 2*gamma_z)]], dtype=np.complex128),
        math.sqrt(p_reset) * np.array([[0, 1], [0, 0]], dtype=np.complex128),
        math.sqrt(p_reset) * np.array([[0, 0], [1, 0]], dtype=np.complex128),
        math.sqrt(1 - p_reset) * np.array([[0, 0], [0, math.sqrt(2*gamma_z)]], dtype=np.complex128),
    ])


# ---------------------------------------------------------------------------
# Superoperator representation
# ---------------------------------------------------------------------------

def kraus_to_superoperator(channel: KrausChannel) -> NDArray[np.complex128]:
    """Convert Kraus operators to superoperator matrix.

    The superoperator S satisfies: vec(ρ') = S vec(ρ)
    where vec(ρ) stacks columns of ρ.
    """
    dim = channel.kraus_ops[0].shape[0]
    total = dim * dim
    S = np.zeros((total, total), dtype=np.complex128)

    for A in channel.kraus_ops:
        S += np.kron(A, np.conj(A))

    return S


# ---------------------------------------------------------------------------
# Channel fidelity and properties
# ---------------------------------------------------------------------------

def channel_fidelity(channel: KrausChannel, num_qubits: int = 1) -> float:
    """Average fidelity of a quantum channel with the identity."""
    dim = 2**num_qubits
    total = 0.0
    count = 0

    # Average over random states
    for i in range(dim):
        psi = np.zeros(dim, dtype=np.complex128)
        psi[i] = 1.0
        rho_in = np.outer(psi, np.conj(psi))
        rho_out = channel.apply(rho_in)
        total += float(np.real(np.trace(rho_out @ rho_in)))
        count += 1

    return total / count if count > 0 else 0.0
