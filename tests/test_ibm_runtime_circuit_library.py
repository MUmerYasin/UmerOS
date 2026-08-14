"""Tests for quantum.ibm_runtime_service and quantum.circuit_library_extensions."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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


class TestOptions(unittest.TestCase):
    def test_options_v2_model_dump_empty(self):
        opts = OptionsV2()
        self.assertEqual(opts.model_dump(), {})

    def test_sampler_options_default_shots(self):
        opts = SamplerV2Options()
        self.assertEqual(opts.default_shots, 4096)

    def test_estimator_options_precision(self):
        opts = EstimatorV2Options()
        self.assertEqual(opts.precision, 0.01)
        self.assertEqual(opts.default_precision, 0.01)

    def test_options_update_returns_new(self):
        a = SamplerV2Options(default_shots=1024)
        b = a.update(default_shots=2048)
        self.assertIsNot(a, b)
        self.assertEqual(a.default_shots, 1024)
        self.assertEqual(b.default_shots, 2048)


class TestService(unittest.TestCase):
    def test_auto_instance(self):
        svc = QiskitRuntimeService(token="x", instance="auto")
        self.assertEqual(svc.instance, "ibm-q/open/main")

    def test_explicit_instance(self):
        svc = QiskitRuntimeService(token="x", instance="hub/grp/proj")
        self.assertEqual(svc.instance, "hub/grp/proj")

    def test_version(self):
        svc = QiskitRuntimeService(token="x", instance="auto")
        self.assertTrue(svc.version.startswith("0.48"))

    def test_least_busy_no_token(self):
        svc = QiskitRuntimeService(token=None, instance="auto")
        self.assertIsNone(svc.least_busy())

    def test_least_busy_fractional(self):
        svc = QiskitRuntimeService(token="x", instance="auto")
        with patch.object(svc, "backends", return_value=["fake_brisbane", "ibmq_qasm_simulator"]):
            backend = svc.least_busy(use_fractional_gates=True)
        self.assertEqual(backend, "fake_brisbane")

    def test_get_runtime_service_factory(self):
        svc = get_runtime_service(token="x")
        self.assertIsInstance(svc, QiskitRuntimeService)
        self.assertEqual(svc.channel, Channel.IBM_QUANTUM)

    def test_channel_enum_values(self):
        self.assertEqual({c.value for c in Channel}, {"ibm_quantum", "ibm_cloud", "local"})


class TestRuntimeJobV2(unittest.TestCase):
    def test_initial_state(self):
        svc = QiskitRuntimeService(token="x", instance="auto")
        job = RuntimeJobV2(job_id="abc", service=svc, program_id="sampler",
                           backend_name="fake_brisbane")
        self.assertEqual(job.state, JobState.QUEUED.value)
        self.assertIsNone(job.session_id)

    def test_usage_partial_cached(self):
        svc = QiskitRuntimeService(token="x", instance="auto")
        job = RuntimeJobV2(job_id="abc", service=svc, program_id="sampler",
                           backend_name="fake_brisbane")
        snap = UsageData(instance="ibm-q/open/main", job_id="abc")
        job._usage_data = snap
        out = job.usage(partial=True)
        self.assertIs(out, snap)

    def test_usage_partial_uncached(self):
        svc = QiskitRuntimeService(token="x", instance="auto")
        job = RuntimeJobV2(job_id="abc", service=svc, program_id="sampler",
                           backend_name="fake_brisbane")
        snap = job.usage(partial=True)
        self.assertEqual(snap.job_id, "abc")


class TestSession(unittest.TestCase):
    def test_run_outside_context(self):
        svc = QiskitRuntimeService(token="x", instance="auto")
        sess = Session(backend="fake_brisbane", service=svc)
        with self.assertRaises(RuntimeError):
            sess.run([("pubs",)])

    def test_context_yields_handle(self):
        svc = QiskitRuntimeService(token="x", instance="auto")
        with Session(backend="fake_brisbane", service=svc) as sess:
            self.assertTrue(sess.session_id)
            self.assertTrue(sess._active)


class TestCircuitLibrary(unittest.TestCase):
    def test_real_amplitudes_params(self):
        ansatz = RealAmplitudes(num_qubits=3, reps=2, entanglement="linear")
        self.assertIsNotNone(ansatz.circuit)
        self.assertEqual(len(ansatz.parameters), 3 * 3)

    def test_efficient_su2_params(self):
        ansatz = EfficientSU2(num_qubits=2, reps=1, entanglement="linear")
        self.assertIsNotNone(ansatz.circuit)
        self.assertEqual(len(ansatz.parameters), 8)

    def test_two_local(self):
        ansatz = TwoLocal(num_qubits=2, reps=1, entanglement="linear",
                          rotation_blocks=("ry",), entanglement_blocks=("cx",))
        self.assertIsNotNone(ansatz.circuit)

    def test_pauli_feature_map(self):
        fm = PauliFeatureMap(feature_dimension=4, reps=1)
        self.assertIsNotNone(fm.circuit)
        self.assertEqual(fm.circuit.num_qubits, 4)
        self.assertGreater(len(fm.parameters), 0)

    def test_iqp(self):
        iqp = IQP(feature_dimension=3, reps=1)
        self.assertIsNotNone(iqp.circuit)
        self.assertEqual(iqp.circuit.num_qubits, 3)

    def test_nlocal_unknown_entanglement(self):
        ansatz = RealAmplitudes(num_qubits=2, reps=1, entanglement="definitely-not-a-strategy")
        self.assertIsNotNone(ansatz.circuit)

    def test_bind_parameters_noop(self):
        ansatz = RealAmplitudes(num_qubits=2, reps=1, entanglement="linear")
        out = bind_parameters(ansatz.circuit, [0.1, 0.2, 0.3, 0.4])
        self.assertIs(out, ansatz.circuit)


if __name__ == "__main__":
    unittest.main()
