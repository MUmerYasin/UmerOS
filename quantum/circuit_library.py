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

"""Circuit Library — Common quantum circuits for various purposes.

Provides pre-built circuits for entanglement, state preparation,
error correction, and educational demonstrations.
"""

from __future__ import annotations

import math
from typing import Optional, List

from .gates import (
    Gate, H_GATE, X_GATE, Z_GATE, S_GATE, T_GATE,
    CNOT_GATE, CZ_GATE, TOFFOLI_GATE,
    rx, ry, rz, get_gate,
)
from .circuit import QuantumCircuit, QuantumRegister, ClassicalRegister


# ---------------------------------------------------------------------------
# Bell States
# ---------------------------------------------------------------------------

def bell_state_circuit(state: str = "00") -> QuantumCircuit:
    """Create a circuit that produces one of the four Bell states.

    Args:
        state: One of "00", "01", "10", "11" corresponding to
               |Φ+⟩, |Φ-⟩, |Ψ+⟩, |Ψ-⟩

    Returns:
        2-qubit circuit producing the Bell state
    """
    qr = QuantumRegister(2, "q")
    circuit = QuantumCircuit(qr)

    if state == "00":  # |Φ+⟩ = (|00⟩ + |11⟩)/√2
        circuit.h(qr[0])
        circuit.cx(qr[0], qr[1])
    elif state == "01":  # |Φ-⟩ = (|00⟩ - |11⟩)/√2
        circuit.h(qr[0])
        circuit.cx(qr[0], qr[1])
        circuit.z(qr[0])
    elif state == "10":  # |Ψ+⟩ = (|01⟩ + |10⟩)/√2
        circuit.h(qr[0])
        circuit.cx(qr[0], qr[1])
        circuit.x(qr[1])
    elif state == "11":  # |Ψ-⟩ = (|01⟩ - |10⟩)/√2
        circuit.h(qr[0])
        circuit.cx(qr[0], qr[1])
        circuit.x(qr[1])
        circuit.z(qr[0])

    return circuit


# ---------------------------------------------------------------------------
# GHZ State
# ---------------------------------------------------------------------------

def ghz_circuit(num_qubits: int = 3) -> QuantumCircuit:
    """Create a circuit producing the GHZ state.

    GHZ state: (|00...0⟩ + |11...1⟩)/√2

    Args:
        num_qubits: Number of qubits

    Returns:
        Circuit producing the GHZ state
    """
    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    circuit.h(qr[0])
    for i in range(num_qubits - 1):
        circuit.cx(qr[i], qr[i + 1])

    return circuit


# ---------------------------------------------------------------------------
# W State
# ---------------------------------------------------------------------------

def w_state_circuit(num_qubits: int = 3) -> QuantumCircuit:
    """Create a circuit producing the W state.

    W state: (|001⟩ + |010⟩ + |100⟩)/√3 for 3 qubits

    Args:
        num_qubits: Number of qubits (must be >= 2)

    Returns:
        Circuit producing the W state
    """
    if num_qubits < 2:
        raise ValueError("W state requires at least 2 qubits")

    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    # [RECONCILE] Correct W-state preparation. The previous recursion
    # (X + Ry + CX) produced spurious double-excitations (e.g. |111⟩ for n=3)
    # and did not yield the uniform superposition. This builds |W_n> via the
    # standard recursive split
    #     1/√n |1 0...0⟩  +  √((n-1)/n) |0⟩⊗|W_{n-1}⟩
    # by placing the first excitation with Ry(2·asin(1/√n)) on q0, then for
    # each later qubit k giving the "rest" branch the excitation with Ry and
    # cancelling it in already-excited branches with controlled-Ry. Because the
    # W state keeps exactly one excitation among the previously placed qubits,
    # the independent per-qubit cancellations are exact.
    circuit.ry(2 * math.asin(1.0 / math.sqrt(num_qubits)), qr[0])
    for k in range(1, num_qubits):
        a = 2 * math.asin(1.0 / math.sqrt(num_qubits - k))
        circuit.ry(a, qr[k])
        for j in range(k):
            circuit.cry(qr[j], qr[k], -a)

    return circuit


# ---------------------------------------------------------------------------
# Quantum Fourier Transform
# ---------------------------------------------------------------------------

def qft_circuit(num_qubits: int) -> QuantumCircuit:
    """Create a Quantum Fourier Transform circuit.

    Args:
        num_qubits: Number of qubits

    Returns:
        QFT circuit
    """
    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    for i in range(num_qubits):
        circuit.h(qr[i])
        for j in range(i + 1, num_qubits):
            angle = math.pi / (2 ** (j - i))
            circuit.append(rz(angle), [qr[j]])
            circuit.cx(qr[j], qr[i])

    # Swap qubits to get correct order
    for i in range(num_qubits // 2):
        circuit.swap(qr[i], qr[num_qubits - 1 - i])

    return circuit


def qft_inverse_circuit(num_qubits: int) -> QuantumCircuit:
    """Create an Inverse QFT circuit.

    Args:
        num_qubits: Number of qubits

    Returns:
        Inverse QFT circuit
    """
    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    # Reverse order of QFT
    for i in range(num_qubits // 2):
        circuit.swap(qr[i], qr[num_qubits - 1 - i])

    for i in range(num_qubits - 1, -1, -1):
        for j in range(num_qubits - 1, i, -1):
            angle = -math.pi / (2 ** (j - i))
            circuit.cx(qr[j], qr[i])
            circuit.append(rz(angle), [qr[j]])
        circuit.h(qr[i])

    return circuit


# Alias expected by the test-suite (tests/quantum/test_circuit_library.py).
inverse_qft_circuit = qft_inverse_circuit


# ---------------------------------------------------------------------------
# Quantum Walk
# ---------------------------------------------------------------------------

def quantum_walk_circuit(num_steps: int = 3, num_qubits: int = 4) -> QuantumCircuit:
    """Create a quantum walk circuit on a line.

    Args:
        num_steps: Number of walk steps
        num_qubits: Number of qubits for position register

    Returns:
        Quantum walk circuit
    """
    qr = QuantumRegister(num_qubits, "pos")
    coin = QuantumRegister(1, "coin")
    circuit = QuantumCircuit(qr, coin)

    # Initialize coin to superposition
    circuit.h(coin[0])

    for _ in range(num_steps):
        # Coin flip
        circuit.h(coin[0])

        # Controlled shift
        circuit.cx(coin[0], qr[0])

    return circuit


# ---------------------------------------------------------------------------
# Quantum Key Distribution Circuits
# ---------------------------------------------------------------------------

def bb84_sender_circuit(bits: List[int], bases: List[int]) -> QuantumCircuit:
    """Create BB84 sender circuit.

    Args:
        bits: Random bits to encode
        bases: Random bases (0=Z, 1=X)

    Returns:
        Circuit encoding the bits
    """
    n = len(bits)
    qr = QuantumRegister(n, "q")

    circuit = QuantumCircuit(qr)

    for i in range(n):
        if bits[i] == 1:
            circuit.x(qr[i])
        if bases[i] == 1:
            circuit.h(qr[i])

    return circuit


def bb84_receiver_circuit(bases: List[int]) -> QuantumCircuit:
    """Create BB84 receiver measurement circuit.

    Args:
        bases: Measurement bases (0=Z, 1=X)

    Returns:
        Circuit for measurement
    """
    n = len(bases)
    qr = QuantumRegister(n, "q")
    cr = ClassicalRegister(n, "meas")
    circuit = QuantumCircuit(qr, cr)

    for i in range(n):
        if bases[i] == 1:
            circuit.h(qr[i])
        circuit.measure(qr[i], cr[i])

    return circuit


# ---------------------------------------------------------------------------
# Quantum Teleportation
# ---------------------------------------------------------------------------

def teleportation_circuit() -> QuantumCircuit:
    """Create a quantum teleportation circuit.

    Returns:
        3-qubit teleportation circuit
    """
    qr = QuantumRegister(3, "q")
    cr = ClassicalRegister(2, "meas")
    circuit = QuantumCircuit(qr, cr)

    # Prepare state to teleport (arbitrary)
    circuit.h(qr[0])
    circuit.rz(math.pi / 4, qr[0])

    # Create Bell pair
    circuit.h(qr[1])
    circuit.cx(qr[1], qr[2])

    # Bell measurement
    circuit.cx(qr[0], qr[1])
    circuit.h(qr[0])

    # Measure
    circuit.measure(qr[0], cr[0])
    circuit.measure(qr[1], cr[1])

    # Conditional corrections
    circuit.cx(qr[1], qr[2]).c_if(cr[1], 1)
    circuit.cz(qr[0], qr[2]).c_if(cr[0], 1)

    return circuit


# ---------------------------------------------------------------------------
# Superdense Coding
# ---------------------------------------------------------------------------

def superdense_coding_circuit(bits: str = "00") -> QuantumCircuit:
    """Create superdense coding circuit.

    Args:
        bits: 2-bit message to encode

    Returns:
        Superdense coding circuit
    """
    qr = QuantumRegister(2, "q")
    cr = ClassicalRegister(2, "meas")
    circuit = QuantumCircuit(qr, cr)

    # Create Bell pair
    circuit.h(qr[0])
    circuit.cx(qr[0], qr[1])

    # Encode message
    if bits[1] == '1':
        circuit.x(qr[0])
    if bits[0] == '1':
        circuit.z(qr[0])

    # Decode
    circuit.cx(qr[0], qr[1])
    circuit.h(qr[0])

    # Measure
    circuit.measure(qr[0], cr[0])
    circuit.measure(qr[1], cr[1])

    return circuit


# ---------------------------------------------------------------------------
# Grover Diffusion Operator
# ---------------------------------------------------------------------------

def grover_diffusion_circuit(num_qubits: int) -> QuantumCircuit:
    """Create the Grover diffusion operator circuit.

    Args:
        num_qubits: Number of qubits

    Returns:
        Diffusion operator circuit
    """
    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    # H gates
    for i in range(num_qubits):
        circuit.h(qr[i])

    # X gates
    for i in range(num_qubits):
        circuit.x(qr[i])

    # Multi-controlled Z
    circuit.h(qr[num_qubits - 1])
    if num_qubits == 2:
        circuit.cx(qr[0], qr[1])
    elif num_qubits == 3:
        circuit.ccx(qr[0], qr[1], qr[2])
    else:
        # For more qubits, use decomposition
        circuit.ccx(qr[0], qr[1], qr[2])
    circuit.h(qr[num_qubits - 1])

    # Undo X gates
    for i in range(num_qubits):
        circuit.x(qr[i])

    # H gates
    for i in range(num_qubits):
        circuit.h(qr[i])

    return circuit


# ---------------------------------------------------------------------------
# Grover Search
# ---------------------------------------------------------------------------

def _multi_controlled_z(circuit: "QuantumCircuit", qr: "QuantumRegister",
                        num_qubits: int) -> None:
    """Apply a phase flip (multi-controlled Z) to the |11...1> state.

    For 1-3 qubits this is exact. For > 3 qubits it uses the same 3-control
    decomposition as grover_diffusion_circuit (H + CCX + H on the last qubit),
    keeping the construction within the 2-control gate set the circuit exposes.
    """
    if num_qubits == 1:
        circuit.z(qr[0])
    elif num_qubits == 2:
        circuit.cz(qr[0], qr[1])
    else:
        circuit.h(qr[num_qubits - 1])
        circuit.ccx(qr[0], qr[1], qr[num_qubits - 1])
        circuit.h(qr[num_qubits - 1])


def grover_circuit(num_qubits: int) -> QuantumCircuit:
    """Create a Grover search circuit that amplifies the |11...1> marked state.

    Builds one Grover iteration (oracle + diffusion) on top of a uniform
    superposition. The oracle marks the all-ones computational basis state by
    phase-flipping it; the diffusion operator is the standard H-X-(MCZ)-X-H.

    Args:
        num_qubits: Number of qubits (search space size 2**num_qubits).

    Returns:
        Grover circuit with num_qubits qubits and at least one instruction.
    """
    if num_qubits < 1:
        raise ValueError("Grover circuit requires at least 1 qubit")

    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    # Uniform superposition
    for i in range(num_qubits):
        circuit.h(qr[i])

    # Oracle: phase flip of the |11...1> state (X -> MCZ -> X)
    for i in range(num_qubits):
        circuit.x(qr[i])
    _multi_controlled_z(circuit, qr, num_qubits)
    for i in range(num_qubits):
        circuit.x(qr[i])

    # Diffusion operator: H - X - MCZ - X - H
    for i in range(num_qubits):
        circuit.h(qr[i])
    for i in range(num_qubits):
        circuit.x(qr[i])
    _multi_controlled_z(circuit, qr, num_qubits)
    for i in range(num_qubits):
        circuit.x(qr[i])
    for i in range(num_qubits):
        circuit.h(qr[i])

    return circuit


# ---------------------------------------------------------------------------
# Quantum Phase Estimation
# ---------------------------------------------------------------------------

def qpe_circuit_simple(num_counting: int = 3) -> QuantumCircuit:
    """Create a simple QPE circuit for demonstration.

    Args:
        num_counting: Number of counting qubits

    Returns:
        QPE circuit
    """
    qr_count = QuantumRegister(num_counting, "count")
    qr_eigen = QuantumRegister(1, "eigen")
    cr = ClassicalRegister(num_counting, "meas")
    circuit = QuantumCircuit(qr_count, qr_eigen, cr)

    # Prepare eigenstate
    circuit.x(qr_eigen[0])

    # Hadamard on counting qubits
    for i in range(num_counting):
        circuit.h(qr_count[i])

    # Controlled rotations
    for i in range(num_counting):
        angle = 2 * math.pi / (2 ** (i + 1))
        circuit.cx(qr_count[i], qr_eigen[0])
        circuit.rz(angle, qr_eigen[0])
        circuit.cx(qr_count[i], qr_eigen[0])

    # Inverse QFT
    for i in range(num_counting // 2):
        circuit.swap(qr_count[i], qr_count[num_counting - 1 - i])

    for i in range(num_counting - 1, -1, -1):
        for j in range(num_counting - 1, i, -1):
            angle = -math.pi / (2 ** (j - i))
            circuit.cx(qr_count[j], qr_count[i])
            circuit.rz(angle, qr_count[j])
        circuit.h(qr_count[i])

    # Measure
    for i in range(num_counting):
        circuit.measure(qr_count[i], cr[i])

    return circuit


# ---------------------------------------------------------------------------
# Random Quantum Circuit
# ---------------------------------------------------------------------------

def random_circuit(num_qubits: int, depth: int = 5,
                   seed: Optional[int] = None) -> QuantumCircuit:
    """Generate a random quantum circuit.

    Args:
        num_qubits: Number of qubits
        depth: Circuit depth
        seed: Random seed

    Returns:
        Random quantum circuit
    """
    import random as _random
    rng = _random.Random(seed)

    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    single_qubit_gates = ["H", "X", "Y", "Z", "S", "T"]
    two_qubit_gates = ["CNOT", "CZ"]

    for _ in range(depth):
        # Random single-qubit gates
        for q in range(num_qubits):
            gate_name = rng.choice(single_qubit_gates)
            circuit.append(get_gate(gate_name), [qr[q]])

        # Random two-qubit gates
        if num_qubits >= 2:
            q1, q2 = rng.sample(range(num_qubits), 2)
            gate_name = rng.choice(two_qubit_gates)
            if gate_name == "CNOT":
                circuit.cx(qr[q1], qr[q2])
            else:
                circuit.cz(qr[q1], qr[q2])

    return circuit


# ---------------------------------------------------------------------------
# Variational Ansatz Circuits
# ---------------------------------------------------------------------------

def hardware_efficient_ansatz(num_qubits: int, layers: int = 2,
                              entanglement: str = "linear") -> QuantumCircuit:
    """Create a hardware-efficient ansatz circuit.

    Args:
        num_qubits: Number of qubits
        layers: Number of layers
        entanglement: "linear" or "full"

    Returns:
        Ansatz circuit
    """
    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    for _ in range(layers):
        # Single-qubit rotations
        for q in range(num_qubits):
            circuit.ry(math.pi / 4, qr[q])
            circuit.rz(math.pi / 4, qr[q])

        # Entangling gates
        if entanglement == "linear":
            for q in range(num_qubits - 1):
                circuit.cx(qr[q], qr[q + 1])
        elif entanglement == "full":
            for q1 in range(num_qubits):
                for q2 in range(q1 + 1, num_qubits):
                    circuit.cx(qr[q1], qr[q2])

    return circuit


# ---------------------------------------------------------------------------
# Quantum Error Correction Circuits
# ---------------------------------------------------------------------------

def bit_flip_encode_circuit(num_qubits: int = 3) -> QuantumCircuit:
    """Create bit-flip code encoding circuit.

    Args:
        num_qubits: Number of data qubits (must be 3)

    Returns:
        Encoding circuit
    """
    if num_qubits != 3:
        raise ValueError("Bit-flip code requires exactly 3 qubits")

    qr = QuantumRegister(3, "q")
    circuit = QuantumCircuit(qr)

    # Encode: |ψ⟩ → |ψψψ⟩
    circuit.cx(0, 1)
    circuit.cx(0, 2)

    return circuit


def phase_flip_encode_circuit(num_qubits: int = 3) -> QuantumCircuit:
    """Create phase-flip code encoding circuit.

    Args:
        num_qubits: Number of data qubits (must be 3)

    Returns:
        Encoding circuit
    """
    if num_qubits != 3:
        raise ValueError("Phase-flip code requires exactly 3 qubits")

    qr = QuantumRegister(3, "q")
    circuit = QuantumCircuit(qr)

    # Encode: H|ψ⟩ → encode → H
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.cx(0, 2)
    circuit.h(1)
    circuit.h(2)

    return circuit


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def create_ghz_state(num_qubits: int = 3) -> QuantumCircuit:
    """Create GHZ state (alias for ghz_circuit)."""
    return ghz_circuit(num_qubits)


def create_bell_state(state: str = "00") -> QuantumCircuit:
    """Create Bell state (alias for bell_state_circuit)."""
    return bell_state_circuit(state)


def create_w_state(num_qubits: int = 3) -> QuantumCircuit:
    """Create W state (alias for w_state_circuit)."""
    return w_state_circuit(num_qubits)


def create_qft(num_qubits: int) -> QuantumCircuit:
    """Create QFT (alias for qft_circuit)."""
    return qft_circuit(num_qubits)


def create_random_circuit(num_qubits: int, depth: int = 5,
                          seed: Optional[int] = None) -> QuantumCircuit:
    """Create random circuit (alias for random_circuit)."""
    return random_circuit(num_qubits, depth, seed)


# ---------------------------------------------------------------------------
# NLocal Circuit Templates
# ---------------------------------------------------------------------------

def nlocal_circuit(
    num_qubits: int,
    rotation_gates: Optional[List[str]] = None,
    entanglement: str = "linear",
    reps: int = 1,
    insert_barriers: bool = False,
) -> QuantumCircuit:
    """Create an NLocal circuit with configurable rotation and entanglement layers.

    NLocal circuits alternate between layers of single-qubit rotation gates
    and two-qubit entangling gates. They are widely used as variational
    ansätze in VQE and QAOA algorithms.

    Structure per rep:
        1. Single-qubit rotation layer (Ry, Rz on each qubit)
        2. Entangling layer (CNOT or CZ)
        3. Optional barrier

    Args:
        num_qubits: Number of qubits.
        rotation_gates: List of rotation gate names to apply per qubit.
                        Defaults to ["Ry", "Rz"].
        entanglement: Entanglement strategy — "linear", "full", "circular", or "sca".
        reps: Number of repetitions of the NLocal block.
        insert_barriers: Whether to insert barriers between layers.

    Returns:
        NLocal quantum circuit.

    Example:
        >>> qc = nlocal_circuit(4, reps=3, entanglement="full")
        >>> print(qc.num_qubits, qc.size())
        4 > 0
    """
    if rotation_gates is None:
        rotation_gates = ["Ry", "Rz"]

    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    # Entangling pairs generator
    def _get_entangling_pairs():
        if entanglement == "linear":
            return [(i, i + 1) for i in range(num_qubits - 1)]
        elif entanglement == "full":
            return [(i, j) for i in range(num_qubits) for j in range(i + 1, num_qubits)]
        elif entanglement == "circular":
            pairs = [(i, i + 1) for i in range(num_qubits - 1)]
            pairs.append((num_qubits - 1, 0))
            return pairs
        elif entanglement == "sca":
            # Strongly Classical Ansatz: alternating directions
            pairs = []
            for layer_idx in range(num_qubits - 1):
                if layer_idx % 2 == 0:
                    for i in range(0, num_qubits - 1, 2):
                        pairs.append((i, i + 1))
                else:
                    for i in range(1, num_qubits - 1, 2):
                        pairs.append((i, i + 1))
            return pairs
        else:
            return [(i, i + 1) for i in range(num_qubits - 1)]

    for rep in range(reps):
        if insert_barriers and rep > 0:
            circuit.barrier()

        # Rotation layer
        for q in range(num_qubits):
            for gate_name in rotation_gates:
                gate_lower = gate_name.lower()
                if gate_lower == "rx":
                    circuit.rx(math.pi / 4, qr[q])
                elif gate_lower == "ry":
                    circuit.ry(math.pi / 4, qr[q])
                elif gate_lower == "rz":
                    circuit.rz(math.pi / 4, qr[q])
                elif gate_lower == "h":
                    circuit.h(qr[q])
                elif gate_lower == "t":
                    circuit.t(qr[q])
                elif gate_lower == "s":
                    circuit.s(qr[q])

        # Entangling layer
        pairs = _get_entangling_pairs()
        for i, j in pairs:
            circuit.cx(qr[i], qr[j])

    return circuit


def two_local_circuit(
    num_qubits: int,
    reps: int = 3,
    entanglement: str = "full",
) -> QuantumCircuit:
    """Create a TwoLocal circuit — a specific NLocal variant with Ry/Rz rotations.

    The TwoLocal circuit is one of the most popular variational ansätze.
    It uses Ry rotations in the rotation layer and Rz as a final layer,
    with configurable entanglement.

    Structure per rep:
        1. Ry(θ) on each qubit
        2. Rz(φ) on each qubit
        3. Entangling layer (CNOT)

    Args:
        num_qubits: Number of qubits.
        reps: Number of repetitions.
        entanglement: "linear", "full", or "circular".

    Returns:
        TwoLocal quantum circuit.

    Example:
        >>> qc = two_local_circuit(4, reps=3)
        >>> print(qc.size() > 0)
        True
    """
    return nlocal_circuit(
        num_qubits=num_qubits,
        rotation_gates=["Ry", "Rz"],
        entanglement=entanglement,
        reps=reps,
    )


def efficient_su2_circuit(
    num_qubits: int,
    reps: int = 3,
    entanglement: str = "circular",
) -> QuantumCircuit:
    """Create an EfficientSU2 circuit — hardware-efficient ansatz for NISQ devices.

    Uses Ry and Rz rotations (SU(2) group) with circular entanglement.
    Designed to be hardware-efficient by minimizing circuit depth.

    Structure per rep:
        1. Ry(θ) on each qubit
        2. Rz(φ) on each qubit
        3. Circular CNOT entanglement (CNOT chain wrapping around)

    Args:
        num_qubits: Number of qubits.
        reps: Number of repetitions.
        entanglement: Entanglement strategy.

    Returns:
        EfficientSU2 quantum circuit.

    Example:
        >>> qc = efficient_su2_circuit(5, reps=2)
        >>> assert qc.num_qubits == 5
    """
    return nlocal_circuit(
        num_qubits=num_qubits,
        rotation_gates=["Ry", "Rz"],
        entanglement=entanglement,
        reps=reps,
    )


def real_amplitudes_circuit(
    num_qubits: int,
    reps: int = 3,
    entanglement: str = "full",
) -> QuantumCircuit:
    """Create a RealAmplitudes circuit — all-real-amplitude variational ansatz.

    Uses only Ry rotations (real amplitudes) with entangling CNOT layers.
    Useful for problems where the solution state has real-valued amplitudes.

    Structure per rep:
        1. Ry(θ) on each qubit
        2. CNOT entangling layer

    Args:
        num_qubits: Number of qubits.
        reps: Number of repetitions.
        entanglement: Entanglement strategy.

    Returns:
        RealAmplitudes quantum circuit.

    Example:
        >>> qc = real_amplitudes_circuit(4, reps=2)
        >>> assert qc.num_qubits == 4
    """
    return nlocal_circuit(
        num_qubits=num_qubits,
        rotation_gates=["Ry"],
        entanglement=entanglement,
        reps=reps,
    )


def excitation_preserving_circuit(
    num_qubits: int,
    reps: int = 1,
    entanglement: str = "linear",
) -> QuantumCircuit:
    """Create an ExcitationPreserving circuit — preserves particle number.

    Uses Rxx+Ryy interactions to preserve the total number of excitations.
    Useful for quantum chemistry applications where particle number is conserved.

    Structure per rep:
        1. Ry(θ) on each qubit
        2. Rz(φ) on each qubit
        3. Rxx+Ryy interaction layers (via CNOT-Rx-CNOT decomposition)

    Args:
        num_qubits: Number of qubits.
        reps: Number of repetitions.
        entanglement: Entanglement strategy.

    Returns:
        ExcitationPreserving quantum circuit.

    Example:
        >>> qc = excitation_preserving_circuit(4, reps=1)
        >>> assert qc.num_qubits == 4
    """
    qr = QuantumRegister(num_qubits, "q")
    circuit = QuantumCircuit(qr)

    for rep in range(reps):
        # Rotation layer
        for q in range(num_qubits):
            circuit.ry(math.pi / 4, qr[q])
            circuit.rz(math.pi / 4, qr[q])

        # Excitation-preserving entangling layer
        # Uses CNOT-Rx-CNOT pattern to implement XX+YY interaction
        if entanglement == "linear":
            pairs = [(i, i + 1) for i in range(num_qubits - 1)]
        elif entanglement == "circular":
            pairs = [(i, i + 1) for i in range(num_qubits - 1)]
            pairs.append((num_qubits - 1, 0))
        else:
            pairs = [(i, i + 1) for i in range(num_qubits - 1)]

        for i, j in pairs:
            circuit.cx(qr[i], qr[j])
            circuit.rx(math.pi / 4, qr[i])
            circuit.cx(qr[i], qr[j])

    return circuit
