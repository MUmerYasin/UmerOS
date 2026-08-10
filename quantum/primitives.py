"""Primitives API for quantum computing - V2 interface.

Provides SamplerV2 and EstimatorV2 primitives that work with
QuantumCircuit and operator objects for sampling and expectation
value calculations.
"""

from __future__ import annotations

import time
import threading
from typing import Any, Union, Optional, Sequence
from enum import Enum
import uuid

import numpy as np

from .circuit import QuantumCircuit
from .operators import SparsePauliOp
from .simulator import StatevectorSimulator, Statevector


class PrimitiveJobStatus(Enum):
    """Status of a primitive job."""
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    ERROR = "error"


class PrimitiveJob:
    """Represents a job submitted to a primitive.

    A PrimitiveJob wraps the result of a primitive execution,
    providing status tracking and result retrieval.
    """

    def __init__(self, func, *args, **kwargs):
        self._job_id = str(uuid.uuid4())[:8]
        self._status = PrimitiveJobStatus.QUEUED
        self._result = None
        self._error = None
        self._start_time = None
        self._end_time = None

        # Execute immediately for local backends
        self._execute(func, *args, **kwargs)

    def _execute(self, func, *args, **kwargs):
        """Execute the job function."""
        self._start_time = time.time()
        self._status = PrimitiveJobStatus.RUNNING
        try:
            self._result = func(*args, **kwargs)
            self._status = PrimitiveJobStatus.DONE
        except Exception as e:
            self._error = e
            self._status = PrimitiveJobStatus.ERROR
        finally:
            self._end_time = time.time()

    @property
    def job_id(self) -> str:
        return self._job_id

    @property
    def status(self) -> PrimitiveJobStatus:
        return self._status

    @property
    def result(self):
        if self._status == PrimitiveJobStatus.ERROR:
            raise self._error
        return self._result

    @property
    def done(self) -> bool:
        return self._status == PrimitiveJobStatus.DONE

    @property
    def elapsed_time(self) -> float:
        if self._start_time is None:
            return 0.0
        end = self._end_time or time.time()
        return end - self._start_time

    def cancel(self):
        self._status = PrimitiveJobStatus.CANCELLED

    def __repr__(self):
        return f"PrimitiveJob(job_id='{self._job_id}', status='{self._status.value}')"


class PrimitiveV2Result:
    """Result container for V2 primitives."""

    def __init__(self, quasi_dists=None, metadata=None):
        self._quasi_dists = quasi_dists or []
        self._metadata = metadata or []

    @property
    def quasi_dists(self):
        return self._quasi_dists

    @property
    def metadata(self):
        return self._metadata

    def __getitem__(self, index):
        return self._quasi_dists[index]

    def __len__(self):
        return len(self._quasi_dists)

    def __repr__(self):
        return f"PrimitiveV2Result(quasi_dists={len(self._quasi_dists)} items)"


class SamplerPubResult:
    """Result of a single Sampler PUB (Primitive Unified Block)."""

    def __init__(self, measurements: dict[int, int], metadata: dict = None):
        self._measurements = measurements
        self._metadata = metadata or {}

    @property
    def data(self) -> dict[int, int]:
        return self._measurements

    @property
    def metadata(self) -> dict:
        return self._metadata

    def __repr__(self):
        return f"SamplerPubResult(data={self._measurements})"


class EstimatorPubResult:
    """Result of a single Estimator PUB."""

    def __init__(self, value: float, variance: float = 0.0, metadata: dict = None):
        self._value = value
        self._variance = variance
        self._metadata = metadata or {}

    @property
    def data(self) -> dict:
        return {"evs": self._value, "variances": self._variance}

    @property
    def metadata(self) -> dict:
        return self._metadata

    def __repr__(self):
        return f"EstimatorPubResult(value={self._value:.6f}, variance={self._variance:.6f})"


class BasePrimitiveV2:
    """Base class for V2 primitives."""

    def __init__(self, backend=None):
        if backend is None:
            self._backend = StatevectorSimulator()
        else:
            self._backend = backend

    @property
    def backend(self):
        return self._backend


class SamplerV2(BasePrimitiveV2):
    """Sampler V2 primitive.

    Samples quantum circuits and returns quasi-probability distributions
    over classical register outcomes.

    Usage:
        sampler = SamplerV2()
        job = sampler.run(circuits=[circuit], shots=1024)
        result = job.result()
        quasi_dist = result.quasi_dists[0]
    """

    def run(
        self,
        circuits: Union[QuantumCircuit, list[QuantumCircuit]],
        shots: int = 1024,
        **options,
    ) -> PrimitiveJob:
        """Run one or more circuits and sample measurements.

        Args:
            circuits: A single circuit or list of circuits to sample.
            shots: Number of measurement shots per circuit.
            **options: Additional backend options.

        Returns:
            PrimitiveJob containing SamplerPubResult instances.
        """
        if not isinstance(circuits, list):
            circuits = [circuits]

        def _sample():
            return self._execute_sampler(circuits, shots, **options)

        return PrimitiveJob(_sample)

    def _execute_sampler(self, circuits, shots, **options):
        """Execute sampling for circuits."""
        quasi_dists = []
        metadata_list = []

        for circuit in circuits:
            quasi_dist, meta = self._sample_single(circuit, shots, **options)
            quasi_dists.append(quasi_dist)
            metadata_list.append(meta)

        return PrimitiveV2Result(quasi_dists=quasi_dists, metadata=metadata_list)

    def _sample_single(self, circuit, shots, **options):
        """Sample a single circuit."""
        # Use StatevectorSimulator to get statevector, then sample from it
        sv_sim = StatevectorSimulator()
        statevector = sv_sim.run_with_state(circuit)

        # Get the classical register size
        if hasattr(circuit, '_classical_registers') and circuit._classical_registers:
            total_bits = sum(reg.size for reg in circuit._classical_registers)
        else:
            total_bits = circuit.num_clbits

        if total_bits == 0:
            return {0: 1.0}, {"shots": shots}

        # Sample from the statevector probabilities
        probabilities = np.abs(statevector.data) ** 2

        # Map statevector indices to measurement outcomes
        counts = {}
        for _ in range(shots):
            outcome = np.random.choice(len(probabilities), p=probabilities)
            # Convert to bitstring and then to integer
            bitstring = format(outcome, f'0{total_bits}b')
            # Reverse bit ordering (Qiskit convention: LSB first)
            reversed_bits = bitstring[::-1]
            measured_value = int(reversed_bits, 2)
            counts[measured_value] = counts.get(measured_value, 0) + 1

        # Normalize to quasi-distribution
        quasi_dist = {k: v / shots for k, v in counts.items()}

        metadata = {"shots": shots, "num_clbits": total_bits}
        return quasi_dist, metadata


class EstimatorV2(BasePrimitiveV2):
    """Estimator V2 primitive.

    Estimates expectation values of operators given quantum states.

    Usage:
        estimator = EstimatorV2()
        job = estimator.run(
            circuits=[circuit],
            observables=[observable]
        )
        result = job.result()
        expectation = result[0].data["evs"]
    """

    def run(
        self,
        circuits: Union[QuantumCircuit, list[QuantumCircuit]],
        observables: Union[SparsePauliOp, list[SparsePauliOp], list[list[SparsePauliOp]]],
        **options,
    ) -> PrimitiveJob:
        """Run circuits and estimate expectation values.

        Args:
            circuits: A single circuit or list of circuits.
            observables: Observables to estimate. Can be:
                - A single SparsePauliOp (applied to all circuits)
                - A list of SparsePauliOps (one per circuit)
                - A list of lists of SparsePauliOps (multiple per circuit)
            **options: Additional backend options.

        Returns:
            PrimitiveJob containing EstimatorPubResult instances.
        """
        if not isinstance(circuits, list):
            circuits = [circuits]

        # Normalize observables
        if isinstance(observables, SparsePauliOp):
            observables = [observables] * len(circuits)
        elif isinstance(observables, list):
            if len(observables) == 1:
                observables = observables * len(circuits)

        def _estimate():
            return self._execute_estimator(circuits, observables, **options)

        return PrimitiveJob(_estimate)

    def _execute_estimator(self, circuits, observables, **options):
        """Execute estimation for circuits and observables."""
        results = []
        metadata_list = []

        for circuit, observable in zip(circuits, observables):
            result, meta = self._estimate_single(circuit, observable, **options)
            results.append(result)
            metadata_list.append(meta)

        return PrimitiveV2Result(
            quasi_dists=results,
            metadata=metadata_list
        )

    def _estimate_single(self, circuit, observable, **options):
        """Estimate expectation value for a single circuit-observable pair."""
        # Get statevector
        sv_sim = StatevectorSimulator()
        statevector = sv_sim.run_with_state(circuit)

        # Calculate expectation value: <ψ|O|ψ>
        state_array = statevector.data
        observable_matrix = observable.matrix

        expectation_value = np.real(np.conj(state_array) @ observable_matrix @ state_array)

        # Calculate variance
        # Var(O) = <ψ|O²|ψ> - <ψ|O|ψ>²
        O_squared = observable_matrix @ observable_matrix
        exp_O_squared = np.real(np.conj(state_array) @ O_squared @ state_array)
        variance = exp_O_squared - expectation_value ** 2

        pub_result = EstimatorPubResult(
            value=expectation_value,
            variance=variance,
            metadata={"observable_num_qubits": observable.num_qubits}
        )

        metadata = {"num_circuits": 1}
        return pub_result, metadata


# Convenience functions

def sampler_run(
    circuits: Union[QuantumCircuit, list[QuantumCircuit]],
    shots: int = 1024,
    backend=None,
    **options,
) -> PrimitiveJob:
    """Convenience function to run a sampler.

    Args:
        circuits: Circuit(s) to sample.
        shots: Number of shots.
        backend: Optional backend to use.

    Returns:
        PrimitiveJob with sampling results.
    """
    sampler = SamplerV2(backend=backend)
    return sampler.run(circuits=circuits, shots=shots, **options)


def estimator_run(
    circuits: Union[QuantumCircuit, list[QuantumCircuit]],
    observables: Union[SparsePauliOp, list[SparsePauliOp]],
    backend=None,
    **options,
) -> PrimitiveJob:
    """Convenience function to run an estimator.

    Args:
        circuits: Circuit(s) to use for state preparation.
        observables: Observable(s) to estimate.
        backend: Optional backend to use.

    Returns:
        PrimitiveJob with estimation results.
    """
    estimator = EstimatorV2(backend=backend)
    return estimator.run(circuits=circuits, observables=observables, **options)
