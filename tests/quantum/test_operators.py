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

"""Tests for quantum.operators — SparsePauliOp, PauliTerm, Hamiltonian.

[RECONCILE] These tests were originally written against a Qiskit-shaped API
(`SparsePauliOp.from_list(...)`, `.matrix`, `Hamiltonian(op).expectation(state)`).
The shipped UmerOS quantum library uses a bespoke API, so the tests below were
rewritten to exercise the SHIPPED surface rather than changing the library:
  * `SparsePauliOp.from_list([("Z", 1.0)])`  ->  `pauli_string("Z", 1.0)`
        (single Pauli string) or
        `SparsePauliOp(labels=["Z", "X"], coeffs=[1.0, 0.5])` (multiple terms).
  * `op.matrix`                              ->  `op.to_matrix()`
  * `len(op)`                                ->  `len(op.terms)` (term list)
  * `Hamiltonian(op)`                        ->  `Hamiltonian({"Z": 1.0})`
        (the lib constructor takes a {label: coeff} dict)
  * `ham.expectation(state)`                 ->  `ham.expectation_value(state)`
"""

import math  # noqa: F401  (kept for parity with other quantum test modules)
import pytest
import numpy as np

from quantum.operators import (
    SparsePauliOp,
    PauliTerm,
    Hamiltonian,
    pauli_string,
)


class TestSparsePauliOp:
    def test_from_single_string(self):
        # [RECONCILE] shipped helper for a single Pauli string is pauli_string()
        op = pauli_string("Z", 1.0)
        assert op.num_qubits == 1
        # [RECONCILE] lib has no __len__; term count is len(op.terms)
        assert len(op.terms) == 1

    def test_from_two_qubit(self):
        # [RECONCILE] pauli_string handles multi-character labels too
        op = pauli_string("ZZ", 1.0)
        assert op.num_qubits == 2

    def test_from_multiple_terms(self):
        # [RECONCILE] multi-term construction uses labels= / coeffs=
        op = SparsePauliOp(labels=["Z", "X"], coeffs=[1.0, 0.5])
        assert len(op.terms) == 2

    def test_matrix_z(self):
        # [RECONCILE] matrix access is to_matrix(), not .matrix
        op = pauli_string("Z", 1.0)
        m = op.to_matrix()
        expected = np.array([[1, 0], [0, -1]], dtype=complex)
        np.testing.assert_allclose(m, expected, atol=1e-10)

    def test_matrix_x(self):
        op = pauli_string("X", 1.0)
        m = op.to_matrix()
        expected = np.array([[0, 1], [1, 0]], dtype=complex)
        np.testing.assert_allclose(m, expected, atol=1e-10)

    def test_matrix_identity(self):
        op = pauli_string("I", 1.0)
        m = op.to_matrix()
        np.testing.assert_allclose(m, np.eye(2), atol=1e-10)

    def test_zz_operator(self):
        op = pauli_string("ZZ", 1.0)
        m = op.to_matrix()
        assert m.shape == (4, 4)
        expected = np.diag([1, -1, -1, 1])
        np.testing.assert_allclose(m, expected, atol=1e-10)

    def test_addition(self):
        op1 = pauli_string("Z", 1.0)
        op2 = pauli_string("X", 0.5)
        op3 = op1 + op2
        assert len(op3.terms) == 2

    def test_scalar_mul(self):
        op = pauli_string("Z", 1.0)
        op2 = op * 2.0
        assert len(op2.terms) == 1

    def test_repr(self):
        op = pauli_string("Z", 1.0)
        r = repr(op)
        assert "SparsePauliOp" in r or "Z" in r

    def test_hermitian(self):
        op = pauli_string("Z", 1.0)
        m = op.to_matrix()
        np.testing.assert_allclose(m, m.conj().T, atol=1e-10)


class TestPauliTerm:
    def test_create(self):
        pt = PauliTerm("Z", 1.0)
        assert pt.label == "Z"
        assert pt.coeff == 1.0

    def test_repr(self):
        pt = PauliTerm("X", 2.0)
        r = repr(pt)
        assert "X" in r


class TestHamiltonian:
    def test_from_operator(self):
        # [RECONCILE] Hamiltonian takes a {label: coeff} dict, returns a
        # SparsePauliOp (which exposes num_qubits)
        ham = Hamiltonian({"Z": 1.0})
        assert ham.num_qubits == 1

    def test_expectation_value(self):
        """<0|Z|0> = 1"""
        # [RECONCILE] Hamiltonian(dict) -> SparsePauliOp; expectation is
        # expectation_value(state), not expectation(state)
        ham = Hamiltonian({"Z": 1.0})
        # |0⟩ state
        state = np.array([1, 0], dtype=complex)
        ev = ham.expectation_value(state)
        np.testing.assert_allclose(ev, 1.0, atol=1e-10)

    def test_expectation_x(self):
        """<+|X|+> = 1, where |+> = (|0>+|1>)/sqrt(2)"""
        ham = Hamiltonian({"X": 1.0})
        state = np.array([1 / np.sqrt(2), 1 / np.sqrt(2)], dtype=complex)
        ev = ham.expectation_value(state)
        np.testing.assert_allclose(ev, 1.0, atol=1e-10)
