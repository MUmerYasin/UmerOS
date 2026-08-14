"""Tests for quantum.ionq_constants and quantum.ionq_gates."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quantum.ionq_constants import (
    APIJobStatus,
    IONQ_BACKEND_QUBITS,
    IONQ_DEFAULT_URL,
    IONQ_DEFAULT_URL_V4,
    IONQ_NATIVE_GATES,
    IONQ_TRANSLATABLE_GATES,
    IonQAggregationMethod,
    IonQErrorMitigation,
    IonQTargetBackend,
)
from quantum.ionq_gates import (
    GPIGate,
    GPI2Gate,
    MSGate,
    ZZGate,
    get_ionq_gate,
)


def _is_unitary(mat: np.ndarray, atol: float = 1e-9) -> bool:
    eye = mat.conj().T @ mat
    return np.allclose(eye, np.eye(eye.shape[0]), atol=atol)


class TestConstants(unittest.TestCase):
    def test_default_url_versions(self):
        self.assertTrue(IONQ_DEFAULT_URL.endswith("/v0.3"))
        self.assertTrue(IONQ_DEFAULT_URL_V4.endswith("/v0.4"))

    def test_native_gate_subset_of_translatable(self):
        for g in IONQ_NATIVE_GATES:
            self.assertIn(g, IONQ_TRANSLATABLE_GATES)

    def test_api_job_status_values(self):
        expected = {"pending", "ready", "running", "succeeded", "failed",
                    "cancelled", "unknown"}
        self.assertEqual({s.value for s in APIJobStatus}, expected)

    def test_aggregation_method_distinct(self):
        members = list(IonQAggregationMethod)
        self.assertEqual(len({m.name for m in members}), len(members))

    def test_error_mitigation_levels(self):
        vals = {m.value for m in IonQErrorMitigation}
        self.assertTrue({"none", "shot_noise", "zero_noise_extrapolation",
                         "matrix_error_diffusion"} <= vals)

    def test_target_backend_qubit_counts(self):
        for backend in IonQTargetBackend:
            if backend == IonQTargetBackend.SIMULATOR:
                continue
            self.assertIn(backend.value, IONQ_BACKEND_QUBITS)
            self.assertGreater(IONQ_BACKEND_QUBITS[backend.value], 0)


class TestGates(unittest.TestCase):
    def test_gpi_matrix_unitarity(self):
        for phi in (0.0, 0.1, 0.5, 1.0, math.pi - 1e-6):
            mat = GPIGate(phi=phi).to_matrix()
            self.assertEqual(mat.shape, (2, 2))
            self.assertTrue(_is_unitary(mat))

    def test_gpi2_matrix_unitarity(self):
        for phi in (0.0, 0.3, 1.1, math.pi / 2):
            mat = GPI2Gate(phi=phi).to_matrix()
            self.assertEqual(mat.shape, (2, 2))
            self.assertTrue(_is_unitary(mat))

    def test_ms_matrix_unitarity(self):
        for phi0 in (0.0, math.pi / 4, 0.7):
            for phi1 in (-0.2, 0.0, math.pi / 2):
                mat = MSGate(phi0=phi0, phi1=phi1).to_matrix()
                self.assertEqual(mat.shape, (4, 4))
                self.assertTrue(_is_unitary(mat))

    def test_zz_matrix_unitarity_and_diagonal(self):
        mat = ZZGate(phi0=0.3, phi1=-0.4).to_matrix()
        self.assertEqual(mat.shape, (4, 4))
        self.assertTrue(_is_unitary(mat))
        diag = np.diag(mat)
        self.assertTrue(np.allclose(mat, np.diag(diag), atol=1e-12))

    def test_gpi2_at_zero(self):
        mat = GPI2Gate(phi=0.0).to_matrix()
        self.assertTrue(_is_unitary(mat))
        self.assertTrue(np.allclose(np.abs(mat[0, 0]), 1.0 / math.sqrt(2.0), atol=1e-9))

    def test_zz_at_zero_is_identity(self):
        mat = ZZGate(phi0=0.0, phi1=0.0).to_matrix()
        self.assertTrue(np.allclose(mat, np.eye(4, dtype=np.complex128), atol=1e-12))

    def test_get_ionq_gate_dispatch(self):
        g1 = get_ionq_gate("gpi", [0.1])
        g2 = get_ionq_gate("gpi2", [0.2])
        g3 = get_ionq_gate("ms", [0.3, 0.4])
        g4 = get_ionq_gate("zz", [0.5, 0.6])
        self.assertIsInstance(g1, GPIGate)
        self.assertIsInstance(g2, GPI2Gate)
        self.assertIsInstance(g3, MSGate)
        self.assertIsInstance(g4, ZZGate)
        self.assertTrue(math.isclose(g1.phi, 0.1))
        self.assertTrue(math.isclose(g3.phi1, 0.4))

    def test_get_ionq_gate_unknown_raises(self):
        with self.assertRaises(ValueError):
            get_ionq_gate("nope")

    def test_to_dict_phases(self):
        self.assertAlmostEqual(GPIGate(phi=0.1).to_dict()["phases"][0], 0.1)
        self.assertAlmostEqual(GPI2Gate(phi=0.2).to_dict()["phases"][0], 0.2)
        self.assertEqual(MSGate(phi0=0.3, phi1=0.4).to_dict()["phases"], [0.3, 0.4])
        self.assertEqual(ZZGate(phi0=0.5, phi1=0.6).to_dict()["phases"], [0.5, 0.6])


if __name__ == "__main__":
    unittest.main()
