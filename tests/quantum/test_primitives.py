"""Tests for quantum.primitives — SamplerV2, EstimatorV2, PrimitiveJob, wrap_angles."""

import math
import pytest
import numpy as np

from quantum.circuit import QuantumCircuit
from quantum.primitives import (
    SamplerV2, EstimatorV2, PrimitiveJob,
    sampler_run, estimator_run,
    wrap_angles, wrap_angles_to_2pi, wrap_angles_to_pi,
)
from quantum.operators import SparsePauliOp


class TestPrimitiveJob:
    def test_create(self):
        job = PrimitiveJob(lambda: 42)
        assert job is not None

    def test_result(self):
        job = PrimitiveJob(lambda: 42)
        result = job.result()
        assert result == 42

    def test_status(self):
        job = PrimitiveJob(lambda: 42)
        _ = job.result()
        status = job.status()
        assert status == "DONE" or status == "done" or isinstance(status, str)

    def test_error(self):
        def fail():
            raise RuntimeError("test error")
        job = PrimitiveJob(fail)
        with pytest.raises(RuntimeError):
            job.result()


class TestWrapAngles:
    def test_single_float_2pi(self):
        wrapped = wrap_angles(7.0, 0, 2 * np.pi)
        assert 0 <= wrapped < 2 * np.pi

    def test_single_float_pi(self):
        wrapped = wrap_angles(4.0, -np.pi, np.pi)
        assert -np.pi <= wrapped < np.pi

    def test_list_of_angles(self):
        angles = [0.0, 3.5, 7.0, -1.0]
        wrapped = wrap_angles(angles, 0, 2 * np.pi)
        assert isinstance(wrapped, list)
        assert len(wrapped) == 4
        for w in wrapped:
            assert 0 <= w < 2 * np.pi

    def test_numpy_array(self):
        angles = np.array([0.0, 3.5, 7.0])
        wrapped = wrap_angles(angles, 0, 2 * np.pi)
        assert isinstance(wrapped, np.ndarray)
        assert len(wrapped) == 3

    def test_already_in_range(self):
        wrapped = wrap_angles(2.0, 0, 2 * np.pi)
        np.testing.assert_allclose(wrapped, 2.0, atol=1e-10)

    def test_wrap_2pi(self):
        wrapped = wrap_angles_to_2pi(7.0)
        np.testing.assert_allclose(wrapped, 7.0 - 2 * np.pi, atol=1e-10)

    def test_wrap_pi(self):
        wrapped = wrap_angles_to_pi(4.0)
        np.testing.assert_allclose(wrapped, 4.0 - 2 * np.pi, atol=1e-10)

    def test_invalid_range(self):
        with pytest.raises(ValueError):
            wrap_angles(1.0, 5.0, 2.0)


class TestSamplerV2:
    def test_single_circuit(self):
        qc = QuantumCircuit(1, 1)
        qc.h(0)
        qc.measure(0, 0)
        sampler = SamplerV2()
        job = sampler.run(circuits=[qc], shots=100)
        result = job.result()
        assert result is not None
        assert len(result.quasi_dists) == 1

    def test_multiple_circuits(self):
        qc1 = QuantumCircuit(1, 1)
        qc1.x(0)
        qc1.measure(0, 0)
        qc2 = QuantumCircuit(1, 1)
        qc2.h(0)
        qc2.measure(0, 0)
        sampler = SamplerV2()
        job = sampler.run(circuits=[qc1, qc2], shots=100)
        result = job.result()
        assert len(result.quasi_dists) == 2

    def test_bell_state_sampling(self):
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        sampler = SamplerV2()
        job = sampler.run(circuits=[qc], shots=1000)
        result = job.result()
        dist = result.quasi_dists[0]
        assert len(dist) > 0

    def test_sampler_run_convenience(self):
        qc = QuantumCircuit(1, 1)
        qc.x(0)
        qc.measure(0, 0)
        job = sampler_run(circuits=[qc], shots=100)
        result = job.result()
        assert result is not None

    def test_wrap_angles_true(self):
        qc = QuantumCircuit(1, 1)
        qc.h(0)
        qc.measure(0, 0)
        sampler = SamplerV2()
        job = sampler.run(circuits=[qc], shots=100, wrap_angles=True)
        result = job.result()
        assert result is not None

    def test_wrap_angles_dict(self):
        qc = QuantumCircuit(1, 1)
        qc.h(0)
        qc.measure(0, 0)
        sampler = SamplerV2()
        job = sampler.run(circuits=[qc], shots=100, wrap_angles={"min": -np.pi, "max": np.pi})
        result = job.result()
        assert result is not None


class TestEstimatorV2:
    def test_single_circuit(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        obs = SparsePauliOp.from_list([("Z", 1.0)])
        estimator = EstimatorV2()
        job = estimator.run(circuits=[qc], observables=[obs])
        result = job.result()
        assert result is not None
        assert len(result.quasi_dists) == 1

    def test_z_expectation(self):
        qc = QuantumCircuit(1)
        obs = SparsePauliOp.from_list([("Z", 1.0)])
        estimator = EstimatorV2()
        job = estimator.run(circuits=[qc], observables=[obs])
        result = job.result()
        ev = result.quasi_dists[0].value
        np.testing.assert_allclose(ev, 1.0, atol=1e-6)

    def test_x_expectation(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        obs = SparsePauliOp.from_list([("X", 1.0)])
        estimator = EstimatorV2()
        job = estimator.run(circuits=[qc], observables=[obs])
        result = job.result()
        ev = result.quasi_dists[0].value
        np.testing.assert_allclose(ev, 1.0, atol=1e-6)

    def test_multiple_circuits(self):
        qc1 = QuantumCircuit(1)
        qc2 = QuantumCircuit(1)
        qc2.x(0)
        obs = SparsePauliOp.from_list([("Z", 1.0)])
        estimator = EstimatorV2()
        job = estimator.run(circuits=[qc1, qc2], observables=[obs])
        result = job.result()
        assert len(result.quasi_dists) == 2

    def test_estimator_run_convenience(self):
        qc = QuantumCircuit(1)
        obs = SparsePauliOp.from_list([("Z", 1.0)])
        job = estimator_run(circuits=[qc], observables=[obs])
        result = job.result()
        assert result is not None

    def test_wrap_angles(self):
        qc = QuantumCircuit(1)
        obs = SparsePauliOp.from_list([("Z", 1.0)])
        estimator = EstimatorV2()
        job = estimator.run(circuits=[qc], observables=[obs], wrap_angles=True)
        result = job.result()
        assert result is not None
