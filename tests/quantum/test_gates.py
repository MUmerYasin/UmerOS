"""Tests for quantum.gates — gate classes, parametric gates, gate algebra."""

import math
import pytest
import numpy as np

from quantum.gates import (
    Gate,
    I, X, Y, Z, H, S, T, CX, CZ, CCX, SWAP,
    RX, RY, RZ, PhaseGate,
    get_gate,
)


class TestGateBase:
    def test_gate_name(self):
        assert H.name == "H"

    def test_gate_matrix(self):
        m = H.matrix
        assert m.shape == (2, 2)

    def test_gate_unitary(self):
        m = H.matrix
        product = m @ m.conj().T
        np.testing.assert_allclose(product, np.eye(2), atol=1e-10)


class TestStandardGates:
    def test_x_matrix(self):
        expected = np.array([[0, 1], [1, 0]])
        np.testing.assert_allclose(X.matrix, expected, atol=1e-10)

    def test_z_matrix(self):
        expected = np.array([[1, 0], [0, -1]])
        np.testing.assert_allclose(Z.matrix, expected, atol=1e-10)

    def test_h_matrix(self):
        inv = math.sqrt(2) / 2
        expected = np.array([[inv, inv], [inv, -inv]])
        np.testing.assert_allclose(H.matrix, expected, atol=1e-10)

    def test_s_matrix(self):
        expected = np.array([[1, 0], [0, 1j]])
        np.testing.assert_allclose(S.matrix, expected, atol=1e-10)

    def test_cnot_matrix(self):
        m = CX.matrix
        assert m.shape == (4, 4)
        expected = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 0],
        ])
        np.testing.assert_allclose(m, expected, atol=1e-10)

    def test_swap_matrix(self):
        m = SWAP.matrix
        assert m.shape == (4, 4)

    def test_ccx_matrix(self):
        m = CCX.matrix
        assert m.shape == (8, 8)


class TestParametricGates:
    def test_rx_zero(self):
        m = RX(0).matrix
        np.testing.assert_allclose(m, np.eye(2), atol=1e-10)

    def test_ry_pi(self):
        m = RY(math.pi).matrix
        expected = np.array([[0, -1], [1, 0]])
        np.testing.assert_allclose(m, expected, atol=1e-10)

    def test_rz_unitary(self):
        m = RZ(math.pi / 4).matrix
        product = m @ m.conj().T
        np.testing.assert_allclose(product, np.eye(2), atol=1e-10)

    def test_rx_pi_equality(self):
        """RX(pi) = -iX"""
        m = RX(math.pi).matrix
        expected = -1j * np.array([[0, 1], [1, 0]])
        np.testing.assert_allclose(m, expected, atol=1e-10)


class TestGateAlgebra:
    def test_h_h_is_identity(self):
        product = H.matrix @ H.matrix
        np.testing.assert_allclose(product, np.eye(2), atol=1e-10)

    def test_x_x_is_identity(self):
        product = X.matrix @ X.matrix
        np.testing.assert_allclose(product, np.eye(2), atol=1e-10)

    def test_z_z_is_identity(self):
        product = Z.matrix @ Z.matrix
        np.testing.assert_allclose(product, np.eye(2), atol=1e-10)

    def test_s_s_is_z(self):
        product = S.matrix @ S.matrix
        np.testing.assert_allclose(product, Z.matrix, atol=1e-10)


class TestGetGate:
    def test_get_h(self):
        gate = get_gate("H")
        np.testing.assert_allclose(gate.matrix, H.matrix, atol=1e-10)

    def test_get_x(self):
        gate = get_gate("X")
        np.testing.assert_allclose(gate.matrix, X.matrix, atol=1e-10)

    def test_get_cx(self):
        gate = get_gate("CNOT")
        np.testing.assert_allclose(gate.matrix, CX.matrix, atol=1e-10)

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError):
            get_gate("UNKNOWN_GATE")
