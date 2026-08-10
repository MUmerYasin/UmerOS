"""Quantum Gate Library — Complete gate set for UmerOS quantum computing.

Implements all standard quantum gates as unitary matrix operators.
Gates are defined as classes with unitary matrices, inverses, and tensor product support.

Gate Categories:
- Single-qubit: I, X, Y, Z, H, S, T, S†, T†, RX, RY, RZ, Phase, U1, U2, U3
- Two-qubit: CNOT/CX, CZ, CY, CH, SWAP, iSWAP, CRX, CRY, CRZ, CPhase, DCX
- Three-qubit: TOFFOLI/CCX, CCZ, CSWAP/FREDKIN
- Multi-qubit: controlled gates, Unitary
- Special: GlobalPhase
"""

from __future__ import annotations

import math
import cmath
from typing import Optional, Sequence, Union, Tuple

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Base gate class
# ---------------------------------------------------------------------------

class Gate:
    """Base class for all quantum gates.

    Every gate stores:
    - name: human-readable label
    - num_qubits: how many qubits it acts on
    - matrix: unitary matrix (2^n x 2^n)
    - params: numeric parameters (angles, etc.)
    """

    def __init__(self, name: str, num_qubits: int, matrix: NDArray[np.complex128],
                 params: Optional[Sequence[float]] = None):
        self.name = name
        self.num_qubits = num_qubits
        self.matrix = np.asarray(matrix, dtype=np.complex128)
        self.params = list(params) if params else []
        assert self.matrix.shape == (2**num_qubits, 2**num_qubits), \
            f"Matrix shape {self.matrix.shape} doesn't match {num_qubits} qubits"
        assert np.allclose(self.matrix @ self.matrix.conj().T,
                           np.eye(2**num_qubits), atol=1e-10), \
            f"Gate {name} is not unitary"

    def __repr__(self) -> str:
        p = f"({', '.join(f'{p:.4f}' for p in self.params)})" if self.params else ""
        return f"{self.name}{p}"

    def inverse(self) -> "Gate":
        """Return the inverse (adjoint) gate."""
        return Gate(
            name=f"{self.name}†",
            num_qubits=self.num_qubits,
            matrix=self.matrix.conj().T,
            params=[-p for p in self.params],
        )

    def tensor(self, other: "Gate") -> "Gate":
        """Tensor product: self ⊗ other."""
        return Gate(
            name=f"{self.name}⊗{other.name}",
            num_qubits=self.num_qubits + other.num_qubits,
            matrix=np.kron(self.matrix, other.matrix),
        )

    def control(self, num_ctrl: int = 1) -> "Gate":
        """Add control qubits."""
        n = self.num_qubits + num_ctrl
        total = 2**n
        mat = np.eye(total, dtype=np.complex128)
        block_size = 2**self.num_qubits
        ctrl_mask = (1 << num_ctrl) - 1
        for i in range(total):
            ctrl_bits = i >> self.num_qubits
            if ctrl_bits == ctrl_mask:
                row_in_block = i - (ctrl_mask << self.num_qubits)
                for j in range(block_size):
                    target_state = j
                    dst = (ctrl_mask << self.num_qubits) | target_state
                    mat[dst, i] = self.matrix[target_state, row_in_block]
        return Gate(
            name=f"C{num_ctrl}({self.name})" if num_ctrl > 1 else f"C({self.name})",
            num_qubits=n,
            matrix=mat,
        )

    def power(self, exp: float) -> "Gate":
        """Matrix power: gate^exp via eigendecomposition."""
        eigenvalues, eigenvectors = np.linalg.eigh(self.matrix)
        powered = eigenvectors @ np.diag(eigenvalues ** exp) @ eigenvectors.conj().T
        return Gate(
            name=f"{self.name}^{exp}",
            num_qubits=self.num_qubits,
            matrix=powered,
        )

    def __call__(self, *qubits: int) -> "Instruction":
        """Apply this gate to the given qubits, returning an Instruction."""
        from .circuit import Instruction
        return Instruction(gate=self, qubits=list(qubits))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Gate):
            return NotImplemented
        return (self.name == other.name and
                self.num_qubits == other.num_qubits and
                np.allclose(self.matrix, other.matrix, atol=1e-10))


# ---------------------------------------------------------------------------
# Single-qubit gates
# ---------------------------------------------------------------------------

I_GATE = Gate("I", 1, np.eye(2))
X_GATE = Gate("X", 1, np.array([[0, 1], [1, 0]], dtype=np.complex128))
Y_GATE = Gate("Y", 1, np.array([[0, -1j], [1j, 0]], dtype=np.complex128))
Z_GATE = Gate("Z", 1, np.array([[1, 0], [0, -1]], dtype=np.complex128))
H_GATE = Gate("H", 1, np.array([[1, 1], [1, -1]], dtype=np.complex128) / math.sqrt(2))
S_GATE = Gate("S", 1, np.array([[1, 0], [0, 1j]], dtype=np.complex128))
T_GATE = Gate("T", 1, np.array([[1, 0], [0, cmath.exp(1j * math.pi / 4)]], dtype=np.complex128))
SDG_GATE = Gate("S†", 1, np.array([[1, 0], [0, -1j]], dtype=np.complex128))
TDG_GATE = Gate("T†", 1, np.array([[1, 0], [0, cmath.exp(-1j * math.pi / 4)]], dtype=np.complex128))


# ---------------------------------------------------------------------------
# Parametric single-qubit gates
# ---------------------------------------------------------------------------

def rx(theta: float) -> Gate:
    """Rotation around X-axis: RX(theta) = exp(-i*theta*X/2)"""
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return Gate("RX", 1, np.array([[c, -1j*s], [-1j*s, c]], dtype=np.complex128), [theta])


def ry(theta: float) -> Gate:
    """Rotation around Y-axis: RY(theta) = exp(-i*theta*Y/2)"""
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return Gate("RY", 1, np.array([[c, -s], [s, c]], dtype=np.complex128), [theta])


def rz(theta: float) -> Gate:
    """Rotation around Z-axis: RZ(theta) = exp(-i*theta*Z/2)"""
    return Gate("RZ", 1, np.array(
        [[cmath.exp(-1j*theta/2), 0],
         [0, cmath.exp(1j*theta/2)]], dtype=np.complex128), [theta])


def phase_gate(phi: float) -> Gate:
    """Phase gate: P(phi) = diag(1, e^{i*phi})"""
    return Gate("Phase", 1, np.array([[1, 0], [0, cmath.exp(1j*phi)]], dtype=np.complex128), [phi])


def u1(lam: float) -> Gate:
    """U1 gate: diag(1, e^{i*lam})"""
    return phase_gate(lam)


def u2(phi: float, lam: float) -> Gate:
    """U2 gate: (1/sqrt(2))[[1, -e^{i*lam}], [e^{i*phi}, e^{i*(phi+lam)}]]"""
    e_il = cmath.exp(1j * lam)
    e_ip = cmath.exp(1j * phi)
    e_ipl = cmath.exp(1j * (phi + lam))
    return Gate("U2", 1, np.array(
        [[1, -e_il], [e_ip, e_ipl]], dtype=np.complex128) / math.sqrt(2), [phi, lam])


def u3(theta: float, phi: float, lam: float) -> Gate:
    """U3 gate: general single-qubit unitary."""
    c, s = math.cos(theta/2), math.sin(theta/2)
    return Gate("U3", 1, np.array([
        [c, -cmath.exp(1j*lam)*s],
        [cmath.exp(1j*phi)*s, cmath.exp(1j*(phi+lam))*c]
    ], dtype=np.complex128), [theta, phi, lam])


# ---------------------------------------------------------------------------
# Two-qubit gates
# ---------------------------------------------------------------------------

CNOT_GATE = Gate("CNOT", 2, np.array([
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 0, 1],
    [0, 0, 1, 0],
], dtype=np.complex128))

CX_GATE = CNOT_GATE

CZ_GATE = Gate("CZ", 2, np.array([
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, -1],
], dtype=np.complex128))

CY_GATE = Gate("CY", 2, np.array([
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 0, -1j],
    [0, 0, 1j, 0],
], dtype=np.complex128))

CH_GATE = H_GATE.control(1)

SWAP_GATE = Gate("SWAP", 2, np.array([
    [1, 0, 0, 0],
    [0, 0, 1, 0],
    [0, 1, 0, 0],
    [0, 0, 0, 1],
], dtype=np.complex128))

ISWAP_GATE = Gate("iSWAP", 2, np.array([
    [1, 0, 0, 0],
    [0, 0, 1j, 0],
    [0, 1j, 0, 0],
    [0, 0, 0, 1],
], dtype=np.complex128))


def crx(theta: float) -> Gate:
    """Controlled-RX."""
    return rx(theta).control(1)


def cry(theta: float) -> Gate:
    """Controlled-RY."""
    return ry(theta).control(1)


def crz(theta: float) -> Gate:
    """Controlled-RZ."""
    return rz(theta).control(1)


def cphase_gate(phi: float) -> Gate:
    """Controlled-Phase: diag(1,1,1,e^{i*phi})"""
    return Gate("CPhase", 2, np.diag([1, 1, 1, cmath.exp(1j*phi)]).astype(np.complex128), [phi])


# DCX: double CNOT — first CNOT(0,1) then CNOT(1,0)
_cnot_mat = np.array([
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 0, 1],
    [0, 0, 1, 0],
], dtype=np.complex128)
_cnot_rev = np.array([
    [1, 0, 0, 0],
    [0, 0, 0, 1],
    [0, 0, 1, 0],
    [0, 1, 0, 0],
], dtype=np.complex128)
DCX_GATE = Gate("DCX", 2, _cnot_rev @ _cnot_mat)


# ---------------------------------------------------------------------------
# Three-qubit gates
# ---------------------------------------------------------------------------

_toff_mat = np.eye(8, dtype=np.complex128)
_toff_mat[6, 6] = 0; _toff_mat[7, 7] = 0
_toff_mat[6, 7] = 1; _toff_mat[7, 6] = 1
TOFFOLI_GATE = Gate("Toffoli", 3, _toff_mat)
CCX_GATE = TOFFOLI_GATE

CCZ_GATE = Gate("CCZ", 3, np.diag(
    [1, 1, 1, 1, 1, 1, 1, -1]
).astype(np.complex128))

_fredkin = np.eye(8, dtype=np.complex128)
_fredkin[5, 5] = 0; _fredkin[6, 6] = 0
_fredkin[5, 6] = 1; _fredkin[6, 5] = 1
CSWAP_GATE = Gate("CSWAP", 3, _fredkin)
FREDKIN_GATE = CSWAP_GATE


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def unitary(matrix: NDArray, label: str = "U") -> Gate:
    """Wrap an arbitrary unitary matrix as a gate."""
    n = int(math.log2(matrix.shape[0]))
    return Gate(label, n, matrix)


def global_phase(phi: float) -> Gate:
    """Global phase gate."""
    return Gate("GlobalPhase", 1, np.array(
        [[cmath.exp(1j * phi)]], dtype=np.complex128), [phi])


# ---------------------------------------------------------------------------
# Gate registry for name-based lookup
# ---------------------------------------------------------------------------

SINGLE_QUBIT_GATES = {
    "I": I_GATE, "X": X_GATE, "Y": Y_GATE, "Z": Z_GATE,
    "H": H_GATE, "S": S_GATE, "T": T_GATE, "S†": SDG_GATE, "T†": TDG_GATE,
}

TWO_QUBIT_GATES = {
    "CNOT": CNOT_GATE, "CX": CX_GATE, "CZ": CZ_GATE, "CY": CY_GATE,
    "CH": CH_GATE, "SWAP": SWAP_GATE, "iSWAP": ISWAP_GATE, "DCX": DCX_GATE,
}

THREE_QUBIT_GATES = {
    "Toffoli": TOFFOLI_GATE, "CCX": CCX_GATE, "CCZ": CCZ_GATE,
    "CSWAP": CSWAP_GATE, "Fredkin": FREDKIN_GATE,
}

PARAMETRIC_GATES = {
    "RX": rx, "RY": ry, "RZ": rz,
    "CRX": crx, "CRY": cry, "CRZ": crz,
    "Phase": phase_gate, "CPhase": cphase_gate,
    "U1": u1, "U2": u2, "U3": u3,
}


def get_gate(name: str, *params: float) -> Gate:
    """Look up a gate by name, applying params if needed."""
    if name in SINGLE_QUBIT_GATES:
        return SINGLE_QUBIT_GATES[name]
    if name in TWO_QUBIT_GATES:
        return TWO_QUBIT_GATES[name]
    if name in THREE_QUBIT_GATES:
        return THREE_QUBIT_GATES[name]
    if name in PARAMETRIC_GATES:
        return PARAMETRIC_GATES[name](*params)
    raise ValueError(f"Unknown gate: {name}")
