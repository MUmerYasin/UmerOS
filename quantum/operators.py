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

"""Quantum Operators — Pauli strings, observables, and operator algebra.

Implements Pauli operators, SparsePauliOp for efficient multi-qubit operator
representations, and observable measurement preparation.
"""

from __future__ import annotations

import math
import cmath
from typing import Optional, Sequence, Union, List, Tuple, Dict
from dataclasses import dataclass, field
from collections import defaultdict

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Pauli operators
# ---------------------------------------------------------------------------

PAULI_I = np.eye(2, dtype=np.complex128)
PAULI_X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
PAULI_Y = np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
PAULI_Z = np.array([[1, 0], [0, -1]], dtype=np.complex128)

PAULI_MAP = {"I": PAULI_I, "X": PAULI_X, "Y": PAULI_Y, "Z": PAULI_Z}
PAULI_LABELS = ["I", "X", "Y", "Z"]


# ---------------------------------------------------------------------------
# SparsePauliOp
# ---------------------------------------------------------------------------

@dataclass
class PauliTerm:
    """A single term in a Pauli operator: coeff * (P_0 ⊗ P_1 ⊗ ... ⊗ P_{n-1})."""
    label: str  # e.g. "IXYZ"
    coeff: complex

    def __post_init__(self):
        self.label = self.label.upper()
        for c in self.label:
            if c not in "IXYZ":
                raise ValueError(f"Invalid Pauli label character: {c}")


class SparsePauliOp:
    """Efficient representation of multi-qubit Pauli operators.

    Stores operator as sum of tensor products of Pauli matrices with coefficients.
    Uses string labels for compact representation (e.g., "XYZI" for X⊗Y⊗Z⊗I).
    """

    def __init__(self, terms: Optional[List[PauliTerm]] = None,
                 labels: Optional[List[str]] = None,
                 coeffs: Optional[List[complex]] = None):
        self.terms: List[PauliTerm] = []

        if terms:
            self.terms = terms
        elif labels and coeffs:
            if len(labels) != len(coeffs):
                raise ValueError("labels and coeffs must have same length")
            self.terms = [PauliTerm(l, c) for l, c in zip(labels, coeffs)]
        elif labels:
            self.terms = [PauliTerm(l, 1.0) for l in labels]
        else:
            self.terms = []

    @property
    def num_qubits(self) -> int:
        """Number of qubits in the operator."""
        if not self.terms:
            return 0
        return len(self.terms[0].label)

    @property
    def size(self) -> int:
        """Number of non-zero terms."""
        return sum(1 for t in self.terms if t.coeff != 0)

    def __repr__(self) -> str:
        if not self.terms:
            return "SparsePauliOp(0)"
        return " + ".join(
            f"({t.coeff.real:+.4f}{t.coeff.imag:+.4f}j)*{t.label}"
            for t in self.terms if t.coeff != 0
        )

    def __add__(self, other: "SparsePauliOp") -> "SparsePauliOp":
        """Add two Pauli operators."""
        combined = defaultdict(complex)
        for t in self.terms:
            combined[t.label] += t.coeff
        for t in other.terms:
            combined[t.label] += t.coeff
        terms = [PauliTerm(l, c) for l, c in combined.items() if abs(c) > 1e-15]
        return SparsePauliOp(terms=terms)

    def __sub__(self, other: "SparsePauliOp") -> "SparsePauliOp":
        """Subtract two Pauli operators."""
        neg_other = SparsePauliOp(terms=[PauliTerm(t.label, -t.coeff) for t in other.terms])
        return self + neg_other

    def __mul__(self, scalar: complex) -> "SparsePauliOp":
        """Scalar multiplication."""
        return SparsePauliOp(terms=[PauliTerm(t.label, t.coeff * scalar) for t in self.terms])

    def __rmul__(self, scalar: complex) -> "SparsePauliOp":
        return self.__mul__(scalar)

    def __neg__(self) -> "SparsePauliOp":
        return self * (-1)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SparsePauliOp):
            return NotImplemented
        d1 = {t.label: t.coeff for t in self.terms if abs(t.coeff) > 1e-15}
        d2 = {t.label: t.coeff for t in other.terms if abs(t.coeff) > 1e-15}
        return d1 == d2

    def to_matrix(self) -> NDArray[np.complex128]:
        """Convert to full unitary matrix."""
        if not self.terms:
            raise ValueError("Cannot convert empty SparsePauliOp to matrix")

        n = self.num_qubits
        total = 2**n
        result = np.zeros((total, total), dtype=np.complex128)

        for term in self.terms:
            if abs(term.coeff) < 1e-15:
                continue
            mat = np.array([[1]], dtype=np.complex128)
            for char in term.label:
                mat = np.kron(mat, PAULI_MAP[char])
            result += term.coeff * mat

        return result

    def tensor(self, other: "SparsePauliOp") -> "SparsePauliOp":
        """Tensor product: self ⊗ other."""
        new_terms = []
        for t1 in self.terms:
            for t2 in other.terms:
                new_terms.append(PauliTerm(
                    label=t1.label + t2.label,
                    coeff=t1.coeff * t2.coeff,
                ))
        return SparsePauliOp(terms=new_terms)

    def compose(self, other: "SparsePauliOp") -> "SparsePauliOp":
        """Operator multiplication (composition)."""
        result = SparsePauliOp()
        for t1 in self.terms:
            for t2 in other.terms:
                # Multiply Pauli labels term-by-term
                new_label = ""
                new_coeff = t1.coeff * t2.coeff
                for c1, c2 in zip(t1.label, t2.label):
                    new_label += _pauli_multiply(c1, c2, coeff_accumulator=new_coeff)
                    # new_coeff is updated by _pauli_multiply
                # Actually, we need the phase separately
                new_label = ""
                phase = 1
                for c1, c2 in zip(t1.label, t2.label):
                    label, p = _pauli_product(c1, c2)
                    new_label += label
                    phase *= p
                new_coeff = t1.coeff * t2.coeff * phase
                result = result + SparsePauliOp(terms=[PauliTerm(new_label, new_coeff)])
        return result

    def expectation_value(self, statevector: NDArray) -> complex:
        """Compute <ψ|O|ψ> for a state vector."""
        mat = self.to_matrix()
        return np.conj(statevector) @ mat @ statevector

    def simplify(self) -> "SparsePauliOp":
        """Combine duplicate labels."""
        combined = defaultdict(complex)
        for t in self.terms:
            combined[t.label] += t.coeff
        terms = [PauliTerm(l, c) for l, c in combined.items() if abs(c) > 1e-15]
        return SparsePauliOp(terms=terms)


# ---------------------------------------------------------------------------
# Pauli algebra helpers
# ---------------------------------------------------------------------------

_PAULI_PRODUCTS = {
    ("I", "I"): ("I", 1), ("I", "X"): ("X", 1), ("I", "Y"): ("Y", 1), ("I", "Z"): ("Z", 1),
    ("X", "I"): ("X", 1), ("Y", "I"): ("Y", 1), ("Z", "I"): ("Z", 1),
    ("X", "X"): ("I", 1), ("Y", "Y"): ("I", 1), ("Z", "Z"): ("I", 1),
    ("X", "Y"): ("Z", 1j), ("Y", "X"): ("Z", -1j),
    ("Y", "Z"): ("X", 1j), ("Z", "Y"): ("X", -1j),
    ("Z", "X"): ("Y", 1j), ("X", "Z"): ("Y", -1j),
}


def _pauli_product(a: str, b: str) -> Tuple[str, complex]:
    """Multiply two Pauli labels, returning (result_label, phase)."""
    return _PAULI_PRODUCTS[(a, b)]


def _pauli_multiply(a: str, b: str, coeff_accumulator: complex) -> str:
    """Not used directly but kept for reference."""
    label, phase = _PAULI_PRODUCT[(a, b)]
    return label


# ---------------------------------------------------------------------------
# Observable helpers
# ---------------------------------------------------------------------------

def pauli_string(label: str, coeff: complex = 1.0) -> SparsePauliOp:
    """Create a SparsePauliOp from a single Pauli string label."""
    return SparsePauliOp(labels=[label], coeffs=[coeff])


def identity(num_qubits: int) -> SparsePauliOp:
    """Identity operator on n qubits."""
    return SparsePauliOp(labels=["I" * num_qubits], coeffs=[1.0])


def zero_operator(num_qubits: int) -> SparsePauliOp:
    """Zero operator on n qubits."""
    return SparsePauliOp()


def Hamiltonian(terms: Dict[str, complex]) -> SparsePauliOp:
    """Create a Hamiltonian from a dict of {pauli_label: coefficient}."""
    return SparsePauliOp(labels=list(terms.keys()), coeffs=list(terms.values()))


# ---------------------------------------------------------------------------
# Operator basis decomposition
# ---------------------------------------------------------------------------

def decompose_single_qubit(statevector: NDArray) -> Dict[str, float]:
    """Decompose a single-qubit state into Pauli basis.

    Returns {I: a, X: b, Y: c, Z: d} such that ρ = aI + bX + cY + dZ.
    """
    rho = np.outer(statevector, np.conj(statevector))
    return {
        "I": 0.5 * np.real(np.trace(rho @ PAULI_I)),
        "X": 0.5 * np.real(np.trace(rho @ PAULI_X)),
        "Y": 0.5 * np.real(np.trace(rho @ PAULI_Y)),
        "Z": 0.5 * np.real(np.trace(rho @ PAULI_Z)),
    }


def expectation_value_single_qubit(statevector: NDArray, observable: str) -> float:
    """Compute expectation value of a single-qubit Pauli observable."""
    pauli = PAULI_MAP[observable.upper()]
    rho = np.outer(statevector, np.conj(statevector))
    return float(np.real(np.trace(rho @ pauli)))


# ---------------------------------------------------------------------------
# Commutation relations
# ---------------------------------------------------------------------------

def commutator(A: SparsePauliOp, B: SparsePauliOp) -> SparsePauliOp:
    """Compute [A, B] = AB - BA."""
    return A.compose(B) - B.compose(A)


def anticommutor(A: SparsePauliOp, B: SparsePauliOp) -> SparsePauliOp:
    """Compute {A, B} = AB + BA."""
    return A.compose(B) + B.compose(A)


def are_commuting(A: SparsePauliOp, B: SparsePauliOp) -> bool:
    """Check if two operators commute."""
    comm = commutator(A, B)
    return comm.size == 0
