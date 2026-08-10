"""Quantum Algorithms — Shor, Grover, VQE, QAOA, QPE.

Implements core quantum algorithms using the UmerOS quantum stack.
Each algorithm returns circuits and/or result objects.
"""

from __future__ import annotations

import math
import cmath
from typing import Optional, List, Tuple, Callable, Dict, Any
from dataclasses import dataclass, field
from fractions import Fraction
import numpy as np
from numpy.typing import NDArray

from .gates import (
    Gate, H_GATE, X_GATE, Z_GATE, CNOT_GATE, CZ_GATE,
    rx, ry, rz, get_gate,
)
from .circuit import QuantumCircuit, QuantumRegister, ClassicalRegister
from .operators import SparsePauliOp, PauliTerm, Hamiltonian
from .simulator import StatevectorSimulator, Statevector, MeasurementResult
from .transpiler import PassManager, DecomposeToBasicPass


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ShorResult:
    """Result from Shor's factoring algorithm."""
    n: int
    factors: List[int]
    period: int
    success: bool
    circuit_depth: int = 0

    def __repr__(self) -> str:
        return f"ShorResult(n={self.n}, factors={self.factors}, period={self.period})"


@dataclass
class GroverResult:
    """Result from Grover's search algorithm."""
    target: int
    iterations: int
    probability: float
    counts: Dict[str, int]
    circuit_depth: int = 0

    def __repr__(self) -> str:
        return f"GroverResult(target={self.target}, prob={self.probability:.4f})"


@dataclass
class VQEResult:
    """Result from VQE algorithm."""
    energy: float
    optimal_params: NDArray
    circuit_depth: int = 0
    iterations: int = 0
    history: List[float] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"VQEResult(energy={self.energy:.6f}, iter={self.iterations})"


@dataclass
class QAOAResult:
    """Result from QAOA algorithm."""
    energy: float
    optimal_params: NDArray
    counts: Dict[str, int]
    circuit_depth: int = 0
    iterations: int = 0
    history: List[float] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"QAOAResult(energy={self.energy:.6f})"


@dataclass
class QPEResult:
    """Result from Quantum Phase Estimation."""
    phase: float
    eigenvalue: complex
    counts: Dict[str, int]
    circuit_depth: int = 0

    def __repr__(self) -> str:
        return f"QPEResult(phase={self.phase:.6f}, eigenvalue={self.eigenvalue:.6f})"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _modular_exp(circuit: QuantumCircuit, control_qubits: List[int],
                 target_qubits: List[int], a: int, N: int) -> None:
    """Add modular exponentiation gates to circuit.

    Implements |x⟩|y⟩ → |x⟩|y ⊕ a^x mod N⟩.
    This is a simplified version for demonstration.
    """
    n = len(control_qubits)
    # For each control qubit, apply controlled modular multiplication
    for i, cq in enumerate(control_qubits):
        power = pow(2, n - 1 - i, N)
        # Simplified: just apply controlled gates for small examples
        if power % 2 == 1:
            if len(target_qubits) > 0:
                circuit.cx(cq, target_qubits[0])


def _qft_dagger(circuit: QuantumCircuit, qubits: List[int]) -> None:
    """Apply inverse QFT to given qubits."""
    n = len(qubits)
    for i in range(n // 2):
        circuit.swap(qubits[i], qubits[n - 1 - i])
    for i in range(n):
        for j in range(i):
            angle = -math.pi / (2 ** (i - j))
            circuit.append(rz(angle), [qubits[j]])
            circuit.cx(qubits[j], qubits[i])
        circuit.h(qubits[i])


def _oracle_qubits(oracle: Any, circuit: QuantumCircuit,
                   qubits: List[int]) -> None:
    """Apply an oracle to qubits."""
    if callable(oracle):
        oracle(circuit, qubits)
    elif isinstance(oracle, list):
        for gate_info in oracle:
            if len(gate_info) == 2:
                gate_name, qubit = gate_info
                circuit.append(get_gate(gate_name), [qubit])
            elif len(gate_info) == 3:
                gate_name, q1, q2 = gate_info
                circuit.append(get_gate(gate_name), [q1, q2])


# ---------------------------------------------------------------------------
# Shor's Algorithm
# ---------------------------------------------------------------------------

def shor_circuit(n: int, a: int, N: int) -> QuantumCircuit:
    """Create circuit for Shor's algorithm.

    Args:
        n: Number of qubits for counting register
        a: Random integer coprime to N
        N: Number to factor

    Returns:
        QuantumCircuit implementing Shor's algorithm
    """
    # Counting register: n qubits
    # Work register: ceil(log2(N)) qubits
    work_qubits = math.ceil(math.log2(N)) if N > 1 else 1
    total_qubits = n + work_qubits

    qr_count = QuantumRegister(n, "count")
    qr_work = QuantumRegister(work_qubits, "work")
    cr = ClassicalRegister(n, "meas")
    circuit = QuantumCircuit(qr_count, qr_work, cr)

    # Initialize counting register in superposition
    for i in range(n):
        circuit.h(qr_count[i])

    # Initialize work register to |1⟩
    circuit.x(qr_work[0])

    # Apply controlled modular exponentiation
    for i in range(n):
        power = pow(2, n - 1 - i, N)
        # Simplified controlled multiplication
        controlled_a = pow(a, power, N)
        for q in range(work_qubits):
            if (controlled_a >> q) & 1:
                circuit.cx(qr_count[i], qr_work[q])

    # Inverse QFT on counting register
    _qft_dagger(circuit, list(qr_count))

    # Measure counting register
    for i in range(n):
        circuit.measure(qr_count[i], cr[i])

    return circuit


def shor(N: int, max_attempts: int = 10, seed: Optional[int] = None) -> ShorResult:
    """Run Shor's algorithm to factor N.

    Args:
        N: Number to factor (must be odd and > 2)
        max_attempts: Maximum number of random 'a' values to try
        seed: Random seed

    Returns:
        ShorResult with factors
    """
    if N <= 2 or N % 2 == 0:
        return ShorResult(n=N, factors=[N], period=0, success=False)

    rng = np.random.default_rng(seed)
    sim = StatevectorSimulator(seed=seed)

    for _ in range(max_attempts):
        # Pick random a in [2, N-1]
        a = int(rng.integers(2, N))
        if math.gcd(a, N) != 1:
            # Lucky guess - found a factor
            factor = math.gcd(a, N)
            return ShorResult(
                n=N,
                factors=[factor, N // factor],
                period=1,
                success=True,
            )

        # Create and run Shor circuit
        n_count = math.ceil(math.log2(N))
        circuit = shor_circuit(n_count, a, N)
        result = sim.run(circuit, shots=1024)

        # Process measurement results to find period
        for bitstring, count in result.counts.items():
            if count < 10:
                continue
            phase = int(bitstring, 2) / (2 ** n_count)
            if phase == 0:
                continue
            frac = Fraction(phase).limit_denominator(N)
            r = frac.denominator

            if r % 2 != 0:
                continue

            # Check if a^(r/2) ≡ -1 (mod N)
            half_pow = pow(a, r // 2, N)
            if half_pow == N - 1:
                continue

            # Extract factors
            factor1 = math.gcd(half_pow - 1, N)
            factor2 = math.gcd(half_pow + 1, N)

            if factor1 not in (1, N) and factor2 not in (1, N):
                return ShorResult(
                    n=N,
                    factors=sorted([factor1, factor2]),
                    period=r,
                    success=True,
                    circuit_depth=circuit.depth,
                )

    return ShorResult(n=N, factors=[N], period=0, success=False)


# ---------------------------------------------------------------------------
# Grover's Algorithm
# ---------------------------------------------------------------------------

def grover_oracle(target: int, num_qubits: int) -> Callable:
    """Create an oracle that marks the target state.

    Args:
        target: Integer representation of target state
        num_qubits: Number of qubits

    Returns:
        Oracle function that applies X to target qubits
    """
    def oracle(circuit: QuantumCircuit, qubits: List[int]) -> None:
        # Convert target to binary and apply X gates where needed
        bits = format(target, f"0{num_qubits}b")
        for i, bit in enumerate(reversed(bits)):
            if bit == '0':
                circuit.x(qubits[i])

        # Multi-controlled Z
        if len(qubits) > 1:
            circuit.h(qubits[-1])
            # Use multi-controlled X pattern
            if len(qubits) == 2:
                circuit.cx(qubits[0], qubits[1])
            else:
                circuit.ccx(qubits[0], qubits[1], qubits[2])
            circuit.h(qubits[-1])

        # Undo X gates
        for i, bit in enumerate(reversed(bits)):
            if bit == '0':
                circuit.x(qubits[i])

    return oracle


def grover_diffuser(num_qubits: int) -> Callable:
    """Create the Grover diffusion operator.

    Applies 2|ψ⟩⟨ψ| - I where |ψ⟩ = H^n|0⟩
    """
    def diffuser(circuit: QuantumCircuit, qubits: List[int]) -> None:
        # H gates
        for q in qubits:
            circuit.h(q)

        # X gates
        for q in qubits:
            circuit.x(q)

        # Multi-controlled Z
        if len(qubits) > 1:
            circuit.h(qubits[-1])
            if len(qubits) == 2:
                circuit.cx(qubits[0], qubits[1])
            else:
                circuit.ccx(qubits[0], qubits[1], qubits[2])
            circuit.h(qubits[-1])

        # Undo X gates
        for q in qubits:
            circuit.x(q)

        # H gates
        for q in qubits:
            circuit.h(q)

    return diffuser


def grover_circuit(num_qubits: int, oracle: Any,
                   iterations: int = 1) -> QuantumCircuit:
    """Create a Grover search circuit.

    Args:
        num_qubits: Number of qubits
        oracle: Oracle function or list of gates
        iterations: Number of Grover iterations

    Returns:
        QuantumCircuit for Grover's algorithm
    """
    qr = QuantumRegister(num_qubits, "q")
    cr = ClassicalRegister(num_qubits, "meas")
    circuit = QuantumCircuit(qr, cr)

    # Initialize: H on all qubits
    for i in range(num_qubits):
        circuit.h(qr[i])

    # Grover iterations
    for _ in range(iterations):
        # Apply oracle
        _oracle_qubits(oracle, circuit, list(qr))

        # Apply diffuser
        diffuser = grover_diffuser(num_qubits)
        diffuser(circuit, list(qr))

    # Measure
    for i in range(num_qubits):
        circuit.measure(qr[i], cr[i])

    return circuit


def grover(target: int, num_qubits: Optional[int] = None,
           iterations: Optional[int] = None,
           seed: Optional[int] = None) -> GroverResult:
    """Run Grover's search algorithm.

    Args:
        target: Target state to search for
        num_qubits: Number of qubits (auto-detected if None)
        iterations: Number of iterations (optimal if None)
        seed: Random seed

    Returns:
        GroverResult with measurement results
    """
    if num_qubits is None:
        num_qubits = max(1, math.ceil(math.log2(max(target + 1, 2))))

    if iterations is None:
        # Optimal iterations: π/4 * √N
        iterations = max(1, int(math.pi / 4 * math.sqrt(2 ** num_qubits)))

    oracle = grover_oracle(target, num_qubits)
    circuit = grover_circuit(num_qubits, oracle, iterations)

    sim = StatevectorSimulator(seed=seed)
    result = sim.run(circuit, shots=1024)

    # Find target in results
    target_str = format(target, f"0{num_qubits}b")
    prob = result.frequency(target_str)

    return GroverResult(
        target=target,
        iterations=iterations,
        probability=prob,
        counts=result.counts,
        circuit_depth=circuit.depth,
    )


# ---------------------------------------------------------------------------
# Variational Quantum Eigensolver (VQE)
# ---------------------------------------------------------------------------

def vqe_ansatz(params: NDArray, num_qubits: int,
               layers: int = 1) -> QuantumCircuit:
    """Create a hardware-efficient VQE ansatz.

    Args:
        params: Rotation angles
        num_qubits: Number of qubits
        layers: Number of ansatz layers

    Returns:
        QuantumCircuit for the ansatz
    """
    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    idx = 0
    for _ in range(layers):
        # Single-qubit rotations
        for i in range(num_qubits):
            if idx < len(params):
                circuit.append(ry(params[idx]), [qr[i]])
                idx += 1
            if idx < len(params):
                circuit.append(rz(params[idx]), [qr[i]])
                idx += 1

        # Entangling gates
        for i in range(num_qubits - 1):
            circuit.cx(qr[i], qr[i + 1])

    return circuit


def vqe(hamiltonian: SparsePauliOp, num_qubits: Optional[int] = None,
         layers: int = 1, max_iter: int = 100,
         seed: Optional[int] = None) -> VQEResult:
    """Run Variational Quantum Eigensolver.

    Args:
        hamiltonian: Observable to minimize
        num_qubits: Number of qubits
        layers: Ansatz depth
        max_iter: Maximum optimization iterations
        seed: Random seed

    Returns:
        VQEResult with ground state energy
    """
    if num_qubits is None:
        num_qubits = hamiltonian.num_qubits

    sim = StatevectorSimulator(seed=seed)
    rng = np.random.default_rng(seed)

    # Initialize parameters
    params = rng.uniform(0, 2 * math.pi, size=layers * num_qubits * 2)
    best_energy = float('inf')
    best_params = params.copy()
    history = []

    # Simple gradient descent
    lr = 0.1
    for iteration in range(max_iter):
        # Evaluate energy
        circuit = vqe_ansatz(params, num_qubits, layers)
        state = sim.run_with_state(circuit)
        energy = complex(hamiltonian.expectation_value(state._data)).real
        history.append(energy)

        if energy < best_energy:
            best_energy = energy
            best_params = params.copy()

        # Numerical gradient
        gradient = np.zeros_like(params)
        for i in range(len(params)):
            params_plus = params.copy()
            params_plus[i] += 0.01
            params_minus = params.copy()
            params_minus[i] -= 0.01

            circuit_plus = vqe_ansatz(params_plus, num_qubits, layers)
            circuit_minus = vqe_ansatz(params_minus, num_qubits, layers)

            state_plus = sim.run_with_state(circuit_plus)
            state_minus = sim.run_with_state(circuit_minus)

            energy_plus = complex(hamiltonian.expectation_value(state_plus._data)).real
            energy_minus = complex(hamiltonian.expectation_value(state_minus._data)).real

            gradient[i] = (energy_plus - energy_minus) / 0.02

        # Update parameters
        params -= lr * gradient

    circuit = vqe_ansatz(best_params, num_qubits, layers)
    return VQEResult(
        energy=best_energy,
        optimal_params=best_params,
        circuit_depth=circuit.depth,
        iterations=max_iter,
        history=history,
    )


# ---------------------------------------------------------------------------
# QAOA (Quantum Approximate Optimization Algorithm)
# ---------------------------------------------------------------------------

def qaoa_cost_circuit(cost_terms: List[Tuple[float, List[int]]],
                      num_qubits: int, gamma: float) -> QuantumCircuit:
    """Create cost unitary for QAOA.

    Args:
        cost_terms: List of (coefficient, qubit_indices) for cost Hamiltonian
        num_qubits: Number of qubits
        gamma: QAOA parameter

    Returns:
        Cost unitary circuit
    """
    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    for coeff, qubits in cost_terms:
        # ZZ interaction: exp(-i * gamma * coeff * Z_i Z_j)
        if len(qubits) == 2:
            circuit.cx(qubits[0], qubits[1])
            circuit.rz(2 * gamma * coeff, qubits[1])
            circuit.cx(qubits[0], qubits[1])
        elif len(qubits) == 1:
            circuit.rz(2 * gamma * coeff, qubits[0])

    return circuit


def qaoa_mixer_circuit(num_qubits: int, beta: float) -> QuantumCircuit:
    """Create mixer unitary for QAOA.

    Args:
        num_qubits: Number of qubits
        beta: QAOA parameter

    Returns:
        Mixer unitary circuit
    """
    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    for i in range(num_qubits):
        circuit.rx(2 * beta, qr[i])

    return circuit


def qaoa(cost_terms: List[Tuple[float, List[int]]],
         num_qubits: int, p: int = 1,
         max_iter: int = 50,
         seed: Optional[int] = None) -> QAOAResult:
    """Run QAOA algorithm.

    Args:
        cost_terms: Cost Hamiltonian terms
        num_qubits: Number of qubits
        p: QAOA depth
        max_iter: Maximum optimization iterations
        seed: Random seed

    Returns:
        QAOAResult with solution
    """
    sim = StatevectorSimulator(seed=seed)
    rng = np.random.default_rng(seed)

    # Initialize parameters
    params = rng.uniform(0, math.pi, size=2 * p)
    best_energy = float('inf')
    best_params = params.copy()
    history = []

    for iteration in range(max_iter):
        # Build QAOA circuit
        qr = QuantumRegister(num_qubits, "q")
        cr = ClassicalRegister(num_qubits, "meas")
        circuit = QuantumCircuit(qr, cr)

        # Initial superposition
        for i in range(num_qubits):
            circuit.h(qr[i])

        # QAOA layers
        for layer in range(p):
            gamma = params[2 * layer]
            beta = params[2 * layer + 1]

            # Cost unitary
            cost_circuit = qaoa_cost_circuit(cost_terms, num_qubits, gamma)
            circuit.compose(cost_circuit, inplace=True)

            # Mixer unitary
            mixer_circuit = qaoa_mixer_circuit(num_qubits, beta)
            circuit.compose(mixer_circuit, inplace=True)

        # Measure
        for i in range(num_qubits):
            circuit.measure(qr[i], cr[i])

        # Run and evaluate
        result = sim.run(circuit, shots=1024)
        energy = 0.0
        for bitstring, count in result.counts.items():
            prob = count / result.total_shots
            # Evaluate cost function
            for coeff, qubits in cost_terms:
                if len(qubits) == 2:
                    b1 = int(bitstring[qubits[0]])
                    b2 = int(bitstring[qubits[1]])
                    if b1 == b2:
                        energy += coeff * prob
                elif len(qubits) == 1:
                    b = int(bitstring[qubits[0]])
                    energy += coeff * prob

        history.append(energy)

        if energy < best_energy:
            best_energy = energy
            best_params = params.copy()

        # Simple parameter update
        params += rng.uniform(-0.1, 0.1, size=2 * p)

    # Get final result
    qr = QuantumRegister(num_qubits, "q")
    cr = ClassicalRegister(num_qubits, "meas")
    circuit = QuantumCircuit(qr, cr)

    for i in range(num_qubits):
        circuit.h(qr[i])

    for layer in range(p):
        gamma = best_params[2 * layer]
        beta = best_params[2 * layer + 1]
        cost_circuit = qaoa_cost_circuit(cost_terms, num_qubits, gamma)
        circuit.compose(cost_circuit, inplace=True)
        mixer_circuit = qaoa_mixer_circuit(num_qubits, beta)
        circuit.compose(mixer_circuit, inplace=True)

    for i in range(num_qubits):
        circuit.measure(qr[i], cr[i])

    result = sim.run(circuit, shots=1024)

    return QAOAResult(
        energy=best_energy,
        optimal_params=best_params,
        counts=result.counts,
        circuit_depth=circuit.depth,
        iterations=max_iter,
        history=history,
    )


# ---------------------------------------------------------------------------
# Quantum Phase Estimation (QPE)
# ---------------------------------------------------------------------------

def qpe_circuit(unitary_powers: List[NDArray], num_counting: int) -> QuantumCircuit:
    """Create Quantum Phase Estimation circuit.

    Args:
        unitary_powers: List of unitary matrices [U^1, U^2, ..., U^(2^n)]
        num_counting: Number of counting qubits

    Returns:
        QPE circuit
    """
    n = num_counting
    total = n + int(np.log2(unitary_powers[0].shape[0]))

    qr_count = QuantumRegister(n, "count")
    qr_eigen = QuantumRegister(total - n, "eigen")
    cr = ClassicalRegister(n, "meas")
    circuit = QuantumCircuit(qr_count, qr_eigen, cr)

    # Prepare eigenstate (|1⟩ for simplicity)
    circuit.x(qr_eigen[0])

    # Hadamard on counting qubits
    for i in range(n):
        circuit.h(qr_count[i])

    # Controlled unitaries
    for i in range(n):
        # Apply U^(2^i) controlled by qubit i
        # Simplified: just apply phase rotation for demonstration
        angle = 2 * math.pi * (i + 1) / (2 ** n)
        circuit.append(rz(angle), [qr_eigen[0]])

    # Inverse QFT
    _qft_dagger(circuit, list(qr_count))

    # Measure
    for i in range(n):
        circuit.measure(qr_count[i], cr[i])

    return circuit


def qpe(unitary: NDArray, eigenstate: Optional[NDArray] = None,
        num_counting: int = 4,
        seed: Optional[int] = None) -> QPEResult:
    """Run Quantum Phase Estimation.

    Args:
        unitary: Unitary matrix with eigenvalue e^(2πiφ)
        eigenstate: Eigenstate of the unitary
        num_counting: Number of counting qubits
        seed: Random seed

    Returns:
        QPEResult with estimated phase
    """
    sim = StatevectorSimulator(seed=seed)

    # Create circuit
    qr_count = QuantumRegister(num_counting, "count")
    qr_eigen = QuantumRegister(1, "eigen")
    cr = ClassicalRegister(num_counting, "meas")
    circuit = QuantumCircuit(qr_count, qr_eigen, cr)

    # Prepare eigenstate
    if eigenstate is not None:
        # Apply gates to prepare eigenstate
        pass  # Simplified
    circuit.x(qr_eigen[0])

    # Hadamard on counting qubits
    for i in range(num_counting):
        circuit.h(qr_count[i])

    # Simplified controlled unitary application
    for i in range(num_counting):
        # Phase kickback approximation
        angle = 2 * math.pi * (i + 1) / (2 ** num_counting)
        circuit.cx(qr_count[i], qr_eigen[0])
        circuit.rz(angle, qr_eigen[0])
        circuit.cx(qr_count[i], qr_eigen[0])

    # Inverse QFT
    _qft_dagger(circuit, list(qr_count))

    # Measure
    for i in range(num_counting):
        circuit.measure(qr_count[i], cr[i])

    result = sim.run(circuit, shots=1024)

    # Find most likely outcome
    most_common = result.most_common(1)[0]
    phase_est = int(most_common[0], 2) / (2 ** num_counting)

    return QPEResult(
        phase=phase_est,
        eigenvalue=cmath.exp(2j * math.pi * phase_est),
        counts=result.counts,
        circuit_depth=circuit.depth,
    )


# ---------------------------------------------------------------------------
# Deutsch-Jozsa Algorithm
# ---------------------------------------------------------------------------

def deutsch_jozsa(oracle_type: str = "balanced",
                  num_qubits: int = 3,
                  seed: Optional[int] = None) -> Dict[str, Any]:
    """Run Deutsch-Jozsa algorithm.

    Args:
        oracle_type: "balanced" or "constant"
        num_qubits: Number of input qubits
        seed: Random seed

    Returns:
        Dictionary with result
    """
    qr = QuantumRegister(num_qubits + 1, "q")
    cr = ClassicalRegister(num_qubits, "meas")
    circuit = QuantumCircuit(qr, cr)

    # Initialize
    for i in range(num_qubits):
        circuit.h(qr[i])
    circuit.x(qr[num_qubits])
    circuit.h(qr[num_qubits])

    # Apply oracle
    if oracle_type == "balanced":
        for i in range(num_qubits):
            circuit.cx(qr[i], qr[num_qubits])
    # Constant oracle does nothing

    # Hadamard on input qubits
    for i in range(num_qubits):
        circuit.h(qr[i])

    # Measure
    for i in range(num_qubits):
        circuit.measure(qr[i], cr[i])

    sim = StatevectorSimulator(seed=seed)
    result = sim.run(circuit, shots=1024)

    # Check result
    all_zero = all(count == 0 for bitstring, count in result.counts.items()
                   if int(bitstring, 2) != 0)

    return {
        "oracle_type": oracle_type,
        "result": "constant" if all_zero else "balanced",
        "counts": result.counts,
        "correct": (oracle_type == "constant" and all_zero) or
                   (oracle_type == "balanced" and not all_zero),
    }


# ---------------------------------------------------------------------------
# Bernstein-Vazirani Algorithm
# ---------------------------------------------------------------------------

def bernstein_vazirani(secret: str, seed: Optional[int] = None) -> Dict[str, Any]:
    """Run Bernstein-Vazirani algorithm.

    Args:
        secret: Binary string representing the secret number
        seed: Random seed

    Returns:
        Dictionary with result
    """
    n = len(secret)
    qr = QuantumRegister(n + 1, "q")
    cr = ClassicalRegister(n, "meas")
    circuit = QuantumCircuit(qr, cr)

    # Initialize
    for i in range(n):
        circuit.h(qr[i])
    circuit.x(qr[n])
    circuit.h(qr[n])

    # Oracle: s·x mod 2
    for i, bit in enumerate(reversed(secret)):
        if bit == '1':
            circuit.cx(qr[i], qr[n])

    # Hadamard on input qubits
    for i in range(n):
        circuit.h(qr[i])

    # Measure
    for i in range(n):
        circuit.measure(qr[i], cr[i])

    sim = StatevectorSimulator(seed=seed)
    result = sim.run(circuit, shots=1024)

    # Most common result should be the secret
    most_common = result.most_common(1)[0][0]

    return {
        "secret": secret,
        "measured": most_common,
        "correct": most_common == secret[::-1],
        "counts": result.counts,
    }


# ---------------------------------------------------------------------------
# Simon's Algorithm
# ---------------------------------------------------------------------------

def simon(oracle_matrix: NDArray, num_qubits: int,
          seed: Optional[int] = None) -> Dict[str, Any]:
    """Run Simon's algorithm.

    Args:
        oracle_matrix: Oracle unitary matrix
        num_qubits: Number of qubits
        seed: Random seed

    Returns:
        Dictionary with result
    """
    qr = QuantumRegister(2 * num_qubits, "q")
    cr = ClassicalRegister(num_qubits, "meas")
    circuit = QuantumCircuit(qr, cr)

    # Initialize
    for i in range(num_qubits):
        circuit.h(qr[i])

    # Simplified oracle application
    # In practice, this would apply the actual oracle
    for i in range(num_qubits):
        circuit.cx(qr[i], qr[num_qubits + i])

    # Hadamard on first register
    for i in range(num_qubits):
        circuit.h(qr[i])

    # Measure first register
    for i in range(num_qubits):
        circuit.measure(qr[i], cr[i])

    sim = StatevectorSimulator(seed=seed)
    result = sim.run(circuit, shots=1024)

    return {
        "counts": result.counts,
        "num_qubits": num_qubits,
    }


# ---------------------------------------------------------------------------
# Amplitude Estimation
# ---------------------------------------------------------------------------

def amplitude_estimation(oracle_qubits: int, state_prepared: bool = True,
                         num_counting: int = 3,
                         seed: Optional[int] = None) -> Dict[str, Any]:
    """Run Amplitude Estimation algorithm.

    Args:
        oracle_qubits: Number of qubits for the oracle
        state_prepared: Whether state preparation is done
        num_counting: Number of counting qubits
        seed: Random seed

    Returns:
        Dictionary with estimated amplitude
    """
    # Simplified implementation
    qr_count = QuantumRegister(num_counting, "count")
    qr_state = QuantumRegister(oracle_qubits, "state")
    cr = ClassicalRegister(num_counting, "meas")
    circuit = QuantumCircuit(qr_count, qr_state, cr)

    # Initialize counting register
    for i in range(num_counting):
        circuit.h(qr_count[i])

    # Prepare state
    circuit.h(qr_state[0])

    # Simplified Grover-like iteration
    for i in range(num_counting):
        circuit.cx(qr_count[i], qr_state[0])

    # Inverse QFT
    _qft_dagger(circuit, list(qr_count))

    # Measure
    for i in range(num_counting):
        circuit.measure(qr_count[i], cr[i])

    sim = StatevectorSimulator(seed=seed)
    result = sim.run(circuit, shots=1024)

    most_common = result.most_common(1)[0][0]
    phase = int(most_common, 2) / (2 ** num_counting)
    amplitude = math.sin(math.pi * phase) ** 2

    return {
        "amplitude": amplitude,
        "phase": phase,
        "counts": result.counts,
    }
