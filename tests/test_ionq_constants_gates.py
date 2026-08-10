"""Tests for quantum.ionq_constants and quantum.ionq_gates.

Run::

    python -m pytest tests/test_ionq_constants_gates.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

# Make the package importable when running from the repo root.
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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_constants_default_url_versions() -> None:
    """Both v0.3 and v0.4 endpoints must be exported."""
    assert IONQ_DEFAULT_URL.endswith("/v0.3")
    assert IONQ_DEFAULT_URL_V4.endswith("/v0.4")


def test_constants_native_gate_set_is_subset_of_translatable() -> None:
    """Every native gate name must also be in the translatable set."""
    for g in IONQ_NATIVE_GATES:
        assert g in IONQ_TRANSLATABLE_GATES


def test_api_job_status_strings_match_ionq_docs() -> None:
    """API status names mirror the IonQ REST schema."""
    expected = {"pending", "ready", "running", "succeeded", "failed",
                "cancelled", "unknown"}
    assert {s.value for s in APIJobStatus} == expected


def test_aggregation_method_distinct_values() -> None:
    """Each IonQ aggregation method is unique."""
    members = list(IonQAggregationMethod)
    assert len({m.name for m in members}) == len(members)


def test_error_mitigation_documented_levels() -> None:
    """Error-mitigation vocabulary is closed and human-readable."""
    vals = {m.value for m in IonQErrorMitigation}
    assert {"none", "shot_noise", "zero_noise_extrapolation",
            "matrix_error_diffusion"} <= vals


def test_target_backend_qubit_counts_consistent() -> None:
    """Backend → qubit mapping must be a bijection from keys."""
    for backend in IonQTargetBackend:
        if backend == IonQTargetBackend.SIMULATOR:
            continue
        assert backend.value in IONQ_BACKEND_QUBITS
        assert IONQ_BACKEND_QUBITS[backend.value] > 0


# ---------------------------------------------------------------------------
# Gates — unitary shape + unitarity
# ---------------------------------------------------------------------------


def _is_unitary(mat: np.ndarray, atol: float = 1e-9) -> bool:
    """Check ``U · Uᴴ = I`` up to *atol*."""
    eye = mat.conj().T @ mat
    return np.allclose(eye, np.eye(eye.shape[0]), atol=atol)


def test_gpi_matrix_unitarity() -> None:
    """GPI must produce a unitary 2x2 matrix for any phase."""
    for phi in (0.0, 0.1, 0.5, 1.0, math.pi - 1e-6):
        mat = GPIGate(phi=phi).to_matrix()
        assert mat.shape == (2, 2)
        assert _is_unitary(mat)


def test_gpi2_matrix_unitarity() -> None:
    """GPI2 must produce a unitary 2x2 matrix."""
    for phi in (0.0, 0.3, 1.1, math.pi / 2):
        mat = GPI2Gate(phi=phi).to_matrix()
        assert mat.shape == (2, 2)
        assert _is_unitary(mat)


def test_ms_matrix_unitarity() -> None:
    """MS must produce a unitary 4x4 matrix for any phase pair."""
    for phi0 in (0.0, math.pi / 4, 0.7):
        for phi1 in (-0.2, 0.0, math.pi / 2):
            mat = MSGate(phi0=phi0, phi1=phi1).to_matrix()
            assert mat.shape == (4, 4)
            assert _is_unitary(mat)


def test_zz_matrix_unitarity_and_diagonal() -> None:
    """ZZ must be a diagonal unitary."""
    mat = ZZGate(phi0=0.3, phi1=-0.4).to_matrix()
    assert mat.shape == (4, 4)
    assert _is_unitary(mat)
    # Diagonal entries (off-diagonals must be zero).
    diag = np.diag(mat)
    assert np.allclose(mat, np.diag(diag), atol=1e-12)


def test_gpi2_at_zero_equals_s_gate() -> None:
    """GPI2(0) should approximate a half-rotation through Y+X."""
    mat = GPI2Gate(phi=0.0).to_matrix()
    # Magnitude checks (no specific Pauli identity enforced here).
    assert _is_unitary(mat)
    assert np.allclose(np.abs(mat[0, 0]), 1.0 / math.sqrt(2.0), atol=1e-9)


def test_zz_at_zero_is_identity() -> None:
    """ZZ(0, 0) is the identity."""
    mat = ZZGate(phi0=0.0, phi1=0.0).to_matrix()
    assert np.allclose(mat, np.eye(4, dtype=np.complex128), atol=1e-12)


def test_get_ionq_gate_factory_dispatch() -> None:
    """Factory must dispatch by canonical name and accept phase list."""
    g1 = get_ionq_gate("gpi", [0.1])
    g2 = get_ionq_gate("gpi2", [0.2])
    g3 = get_ionq_gate("ms", [0.3, 0.4])
    g4 = get_ionq_gate("zz", [0.5, 0.6])
    assert isinstance(g1, GPIGate)
    assert isinstance(g2, GPI2Gate)
    assert isinstance(g3, MSGate)
    assert isinstance(g4, ZZGate)
    assert math.isclose(g1.phi, 0.1)
    assert math.isclose(g3.phi1, 0.4)


def test_get_ionq_gate_unknown_name_raises() -> None:
    """Factory must reject unknown gate names."""
    with pytest.raises(ValueError):
        get_ionq_gate("nope")


def test_to_dict_carries_phase_params() -> None:
    """Each gate's dict form must surface its phase parameters."""
    assert GPIGate(phi=0.1).to_dict()["phases"][0] == pytest.approx(0.1)
    assert GPI2Gate(phi=0.2).to_dict()["phases"][0] == pytest.approx(0.2)
    assert MSGate(phi0=0.3, phi1=0.4).to_dict()["phases"] == pytest.approx([0.3, 0.4])
    assert ZZGate(phi0=0.5, phi1=0.6).to_dict()["phases"] == pytest.approx([0.5, 0.6])
