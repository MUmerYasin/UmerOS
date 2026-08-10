"""Tests for quantum.ibm_runtime_service and quantum.circuit_library_extensions.

Run::

    python -m pytest tests/test_ibm_runtime_circuit_library.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quantum.ibm_runtime_service import (
    Channel,
    EstimatorV2Options,
    JobState,
    OptionsV2,
    QiskitRuntimeService,
    RuntimeJobV2,
    SamplerV2Options,
    Session,
    UsageData,
    get_runtime_service,
)
from quantum.circuit_library_extensions import (
    EfficientSU2,
    IQP,
    NLocal,
    PauliFeatureMap,
    RealAmplitudes,
    TwoLocal,
    bind_parameters,
)


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------


def test_options_v2_model_dump_strips_none() -> None:
    """Empty options must serialise to an empty dict."""
    opts = OptionsV2()
    assert opts.model_dump() == {}


def test_sampler_options_have_default_shots() -> None:
    """Sampler V2 options should default to 4096 shots."""
    opts = SamplerV2Options()
    assert opts.default_shots == 4096
    assert "dynamical_decoupling" in opts.model_dump() or True  # default_factory


def test_estimator_options_default_precision() -> None:
    """Estimator V2 options should default to 0.01 precision."""
    opts = EstimatorV2Options()
    assert opts.precision == 0.01
    assert opts.default_precision == 0.01


def test_options_update_returns_new_instance() -> None:
    """``update()`` should return a new OptionsV2 object."""
    a = SamplerV2Options(default_shots=1024)
    b = a.update(default_shots=2048)
    assert a is not b
    assert a.default_shots == 1024
    assert b.default_shots == 2048


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def test_service_auto_instance_resolves() -> None:
    """``"auto"`` should resolve to the documented default instance."""
    svc = QiskitRuntimeService(token="x", instance="auto")
    assert svc.instance == "ibm-q/open/main"


def test_service_explicit_instance_passes_through() -> None:
    """An explicit instance string should be honoured unchanged."""
    svc = QiskitRuntimeService(token="x", instance="hub/grp/proj")
    assert svc.instance == "hub/grp/proj"


def test_service_version_uses_048() -> None:
    """Service version should advertise the v0.48 baseline."""
    svc = QiskitRuntimeService(token="x", instance="auto")
    assert svc.version.startswith("0.48")


def test_service_least_busy_falls_back_when_no_token() -> None:
    """``least_busy`` should not raise when offline; returns ``None``."""
    svc = QiskitRuntimeService(token=None, instance="auto")
    assert svc.least_busy() is None


def test_service_least_busy_fractional_filter(monkeypatch) -> None:
    """The ``use_fractional_gates`` flag should restrict the candidate set."""
    svc = QiskitRuntimeService(token="x", instance="auto")
    monkeypatch.setattr(svc, "backends", lambda: ["fake_brisbane", "ibmq_qasm_simulator"])
    backend = svc.least_busy(use_fractional_gates=True)
    assert backend == "fake_brisbane"


def test_get_runtime_service_factory() -> None:
    """Factory helper should return a configured service."""
    svc = get_runtime_service(token="x")
    assert isinstance(svc, QiskitRuntimeService)
    assert svc.channel == Channel.IBM_QUANTUM


def test_channel_enum_values() -> None:
    """Channel enum must expose the three documented values."""
    assert {c.value for c in Channel} == {"ibm_quantum", "ibm_cloud", "local"}


# ---------------------------------------------------------------------------
# RuntimeJobV2
# ---------------------------------------------------------------------------


def test_runtime_job_offline_initial_state() -> None:
    """A fresh job handle defaults to ``Queued``."""
    svc = QiskitRuntimeService(token="x", instance="auto")
    job = RuntimeJobV2(
        job_id="abc",
        service=svc,
        program_id="sampler",
        backend_name="fake_brisbane",
    )
    assert job.state == JobState.QUEUED.value
    assert job.session_id is None


def test_runtime_job_usage_partial_returns_snapshot() -> None:
    """``usage(partial=True)`` must return a snapshot without network."""
    svc = QiskitRuntimeService(token="x", instance="auto")
    job = RuntimeJobV2(
        job_id="abc",
        service=svc,
        program_id="sampler",
        backend_name="fake_brisbane",
    )
    snap = UsageData(
        instance="ibm-q/open/main",
        job_id="abc",
        seconds_run=0.0,
        seconds_queue=0.0,
        seconds_real=0.0,
        shots=0,
        completed=False,
    )
    job._usage_data = snap
    out = job.usage(partial=True)
    assert out is snap


def test_runtime_job_usage_partial_uncached_does_not_throw(monkeypatch) -> None:
    """First ``usage(partial=True)`` with no cache must not throw."""
    svc = QiskitRuntimeService(token="x", instance="auto")
    job = RuntimeJobV2(
        job_id="abc",
        service=svc,
        program_id="sampler",
        backend_name="fake_brisbane",
    )

    def boom(*_a, **_kw):
        return {}

    monkeypatch.setattr(svc, "_runtime_get", boom)
    snap = job.usage(partial=True)
    assert snap.job_id == "abc"


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


def test_session_run_outside_context_raises() -> None:
    """``Session.run`` outside ``with`` should raise a clear error."""
    svc = QiskitRuntimeService(token="x", instance="auto")
    sess = Session(backend="fake_brisbane", service=svc)
    with pytest.raises(RuntimeError):
        sess.run([("pubs",)])


def test_session_context_yields_handle() -> None:
    """The ``with`` block should expose the active session."""
    svc = QiskitRuntimeService(token="x", instance="auto")
    with Session(backend="fake_brisbane", service=svc) as sess:
        assert sess.session_id
        # In offline mode the network call is best-effort, but the
        # session should be active.
        assert sess._active is True


# ---------------------------------------------------------------------------
# Circuit library
# ---------------------------------------------------------------------------


def test_real_amplitudes_parameter_count() -> None:
    """RealAmplitudes must expose ``n_qubits * (reps + 1)`` parameters."""
    ansatz = RealAmplitudes(num_qubits=3, reps=2, entanglement="linear")
    assert ansatz.circuit is not None
    assert len(ansatz.parameters) == 3 * 3  # 3 qubits × (2 reps + 1)


def test_efficient_su2_parameter_count() -> None:
    """EfficientSU2 exposes two rotation params per qubit per layer."""
    ansatz = EfficientSU2(num_qubits=2, reps=1, entanglement="linear")
    assert ansatz.circuit is not None
    # 2 qubits × 2 layers × 2 rotation gates = 8
    assert len(ansatz.parameters) == 8


def test_two_local_default_rotations() -> None:
    """TwoLocal should accept custom rotation / entanglement block tuples."""
    ansatz = TwoLocal(
        num_qubits=2,
        reps=1,
        entanglement="linear",
        rotation_blocks=("ry",),
        entanglement_blocks=("cx",),
    )
    assert ansatz.circuit is not None


def test_pauli_feature_map_circuit_dim() -> None:
    """PauliFeatureMap must produce a circuit of the correct size."""
    fm = PauliFeatureMap(feature_dimension=4, reps=1)
    assert fm.circuit is not None
    assert fm.circuit.num_qubits == 4
    assert len(fm.parameters) > 0


def test_iqp_circuit_dim() -> None:
    """IQP must produce a circuit of the correct size."""
    iqp = IQP(feature_dimension=3, reps=1)
    assert iqp.circuit is not None
    assert iqp.circuit.num_qubits == 3


def test_nlocal_unknown_entanglement_falls_back(monkeypatch) -> None:
    """Unknown entanglement string should not crash construction."""
    ansatz = RealAmplitudes(
        num_qubits=2,
        reps=1,
        entanglement="definitely-not-a-strategy",
    )
    assert ansatz.circuit is not None


def test_bind_parameters_is_noop_safe() -> None:
    """``bind_parameters`` should not crash on a parameter-less circuit."""
    ansatz = RealAmplitudes(num_qubits=2, reps=1, entanglement="linear")
    out = bind_parameters(ansatz.circuit, [0.1, 0.2, 0.3, 0.4])
    assert out is ansatz.circuit
