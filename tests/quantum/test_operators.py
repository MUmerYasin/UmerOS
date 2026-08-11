"""Tests for quantum.operators — SparsePauliOp, PauliTerm, Hamiltonian."""

import math
import pytest
import numpy as np

from quantum.operators import SparsePauliOp, PauliTerm, Hamiltonian


class TestSparsePauliOp:
    def test_from_single_string(self):
        op = SparsePauliOp.from_list([("Z", 1.0)])
        assert op.num_qubits == 1
        assert len(op) == 1

    def test_from_two_qubit(self):
        op = SparsePauliOp.from_list([("ZZ", 1.0)])
        assert op.num_qubits == 2

    def test_from_multiple_terms(self):
        op = SparsePauliOp.from_list([("Z", 1.0), ("X", 0.5)])
        assert len(op) == 2

    def test_matrix_z(self):
        op = SparsePauliOp.from_list([("Z", 1.0)])
        m = op.matrix
        expected = np.array([[1, 0], [0, -1]], dtype=complex)
        np.testing.assert_allclose(m, expected, atol=1e-10)

    def test_matrix_x(self):
        op = SparsePauliOp.from_list([("X", 1.0)])
        m = op.matrix
        expected = np.array([[0, 1], [1, 0]], dtype=complex)
        np.testing.assert_allclose(m, expected, atol=1e-10)

    def test_matrix_identity(self):
        op = SparsePauliOp.from_list([("I", 1.0)])
        m = op.matrix
        np.testing.assert_allclose(m, np.eye(2), atol=1e-10)

    def test_zz_operator(self):
        op = SparsePauliOp.from_list([("ZZ", 1.0)])
        m = op.matrix
        assert m.shape == (4, 4)
        expected = np.diag([1, -1, -1, 1])
        np.testing.assert_allclose(m, expected, atol=1e-10)

    def test_addition(self):
        op1 = SparsePauliOp.from_list([("Z", 1.0)])
        op2 = SparsePauliOp.from_list([("X", 0.5)])
        op3 = op1 + op2
        assert len(op3) == 2

    def test_scalar_mul(self):
        op = SparsePauliOp.from_list([("Z", 1.0)])
        op2 = op * 2.0
        assert len(op2) == 1

    def test_repr(self):
        op = SparsePauliOp.from_list([("Z", 1.0)])
        r = repr(op)
        assert "SparsePauliOp" in r or "Z" in r

    def test_hermitian(self):
        op = SparsePauliOp.from_list([("Z", 1.0)])
        m = op.matrix
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
        op = SparsePauliOp.from_list([("Z", 1.0)])
        ham = Hamiltonian(op)
        assert ham.num_qubits == 1

    def test_expectation_value(self):
        """<0|Z|0> = 1"""
        op = SparsePauliOp.from_list([("Z", 1.0)])
        ham = Hamiltonian(op)
        # |0⟩ state
        state = np.array([1, 0], dtype=complex)
        ev = ham.expectation(state)
        np.testing.assert_allclose(ev, 1.0, atol=1e-10)

    def test_expectation_x(self):
        """<+|X|+> = 1, where |+> = (|0>+|1>)/sqrt(2)"""
        op = SparsePauliOp.from_list([("X", 1.0)])
        ham = Hamiltonian(op)
        state = np.array([1 / np.sqrt(2), 1 / np.sqrt(2)], dtype=complex)
        ev = ham.expectation(state)
        np.testing.assert_allclose(ev, 1.0, atol=1e-10)
