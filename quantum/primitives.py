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


# ---------------------------------------------------------------------------
# Angle Wrapping Utilities
# ---------------------------------------------------------------------------

def wrap_angles(
    angles: Union[float, list[float], np.ndarray],
    min_val: float = 0.0,
    max_val: float = 2 * np.pi,
) -> Union[float, list[float], np.ndarray]:
    """Wrap rotation angles into a specified range.

    Useful for variational circuits where parameterized angles should stay
    within a valid range (e.g., [0, 2π] or [-π, π]).

    Args:
        angles: Angle value(s) in radians.
        min_val: Minimum of the target range (inclusive).
        max_val: Maximum of the target range (exclusive).

    Returns:
        Wrapped angle(s) within [min_val, max_val).

    Example:
        >>> wrap_angles(5.0, 0, 2 * 3.14159)
        5.0
        >>> wrap_angles(7.0, 0, 2 * 3.14159)
        0.7168... (7.0 - 2π)
        >>> wrap_angles([0, 3.5, 7.0], 0, 2 * 3.14159)
        [0.0, 3.5, 0.7168...]
    """
    range_width = max_val - min_val
    if range_width <= 0:
        raise ValueError(f"Invalid range: [{min_val}, {max_val})")

    if isinstance(angles, (float, int)):
        wrapped = (angles - min_val) % range_width + min_val
        return float(wrapped)
    else:
        arr = np.asarray(angles, dtype=float)
        wrapped = (arr - min_val) % range_width + min_val
        return wrapped.tolist() if isinstance(angles, list) else wrapped


def wrap_angles_to_2pi(angles: Union[float, list[float], np.ndarray]) -> Union[float, list[float], np.ndarray]:
    """Wrap angles to [0, 2π).

    Args:
        angles: Angle value(s) in radians.

    Returns:
        Wrapped angle(s) within [0, 2π).

    Example:
        >>> wrap_angles_to_2pi(7.0)
        0.7168...
    """
    return wrap_angles(angles, min_val=0.0, max_val=2 * np.pi)


def wrap_angles_to_pi(angles: Union[float, list[float], np.ndarray]) -> Union[float, list[float], np.ndarray]:
    """Wrap angles to [-π, π).

    Args:
        angles: Angle value(s) in radians.

    Returns:
        Wrapped angle(s) within [-π, π).

    Example:
        >>> wrap_angles_to_pi(4.0)
        0.8584...
    """
    return wrap_angles(angles, min_val=-np.pi, max_val=np.pi)


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
        wrap_angles: Optional[dict] = None,
        **options,
    ) -> PrimitiveJob:
        """Run one or more circuits and sample measurements.

        Args:
            circuits: A single circuit or list of circuits to sample.
            shots: Number of measurement shots per circuit.
            wrap_angles: Optional angle wrapping configuration.
                If provided, applies angle wrapping to parameterized gates.
                Format: {"min": float, "max": float} or True for [0, 2π).
            **options: Additional backend options.

        Returns:
            PrimitiveJob containing SamplerPubResult instances.
        """
        if not isinstance(circuits, list):
            circuits = [circuits]

        # Apply angle wrapping if requested
        if wrap_angles is not None:
            circuits = self._apply_wrap_angles(circuits, wrap_angles)

        def _sample():
            return self._execute_sampler(circuits, shots, **options)

        return PrimitiveJob(_sample)

    def _apply_wrap_angles(self, circuits, wrap_config):
        """Apply angle wrapping to parameterized circuits."""
        wrapped_circuits = []
        for circuit in circuits:
            if hasattr(circuit, '_param_table') and circuit._param_table:
                # Has parameterized gates — wrap their angles
                if wrap_config is True:
                    min_val, max_val = 0.0, 2 * np.pi
                elif isinstance(wrap_config, dict):
                    min_val = wrap_config.get("min", 0.0)
                    max_val = wrap_config.get("max", 2 * np.pi)
                else:
                    min_val, max_val = 0.0, 2 * np.pi

                wrapped = QuantumCircuit(circuit.num_qubits)
                for inst in circuit.data:
                    if hasattr(inst, '_params') and inst._params:
                        new_params = wrap_angles(inst._params, min_val, max_val)
                        wrapped.append(inst._gate, list(range(inst._gate.num_qubits)), new_params)
                    else:
                        wrapped.append(inst._gate, list(range(inst._gate.num_qubits)))
                wrapped_circuits.append(wrapped)
            else:
                wrapped_circuits.append(circuit)
        return wrapped_circuits

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
        wrap_angles: Optional[dict] = None,
        **options,
    ) -> PrimitiveJob:
        """Run circuits and estimate expectation values.

        Args:
            circuits: A single circuit or list of circuits.
            observables: Observables to estimate. Can be:
                - A single SparsePauliOp (applied to all circuits)
                - A list of SparsePauliOps (one per circuit)
                - A list of lists of SparsePauliOps (multiple per circuit)
            wrap_angles: Optional angle wrapping configuration.
                If provided, applies angle wrapping to parameterized gates.
                Format: {"min": float, "max": float} or True for [0, 2π).
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

        # Apply angle wrapping if requested
        if wrap_angles is not None:
            circuits = self._apply_wrap_angles(circuits, wrap_angles)

        def _estimate():
            return self._execute_estimator(circuits, observables, **options)

        return PrimitiveJob(_estimate)

    def _apply_wrap_angles(self, circuits, wrap_config):
        """Apply angle wrapping to parameterized circuits."""
        wrapped_circuits = []
        for circuit in circuits:
            if hasattr(circuit, '_param_table') and circuit._param_table:
                if wrap_config is True:
                    min_val, max_val = 0.0, 2 * np.pi
                elif isinstance(wrap_config, dict):
                    min_val = wrap_config.get("min", 0.0)
                    max_val = wrap_config.get("max", 2 * np.pi)
                else:
                    min_val, max_val = 0.0, 2 * np.pi

                wrapped = QuantumCircuit(circuit.num_qubits)
                for inst in circuit.data:
                    if hasattr(inst, '_params') and inst._params:
                        new_params = wrap_angles(inst._params, min_val, max_val)
                        wrapped.append(inst._gate, list(range(inst._gate.num_qubits)), new_params)
                    else:
                        wrapped.append(inst._gate, list(range(inst._gate.num_qubits)))
                wrapped_circuits.append(wrapped)
            else:
                wrapped_circuits.append(circuit)
        return wrapped_circuits

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
    wrap_angles: Optional[dict] = None,
    **options,
) -> PrimitiveJob:
    """Convenience function to run a sampler.

    Args:
        circuits: Circuit(s) to sample.
        shots: Number of shots.
        backend: Optional backend to use.
        wrap_angles: Optional angle wrapping configuration.

    Returns:
        PrimitiveJob with sampling results.
    """
    sampler = SamplerV2(backend=backend)
    return sampler.run(circuits=circuits, shots=shots, wrap_angles=wrap_angles, **options)


def estimator_run(
    circuits: Union[QuantumCircuit, list[QuantumCircuit]],
    observables: Union[SparsePauliOp, list[SparsePauliOp]],
    backend=None,
    wrap_angles: Optional[dict] = None,
    **options,
) -> PrimitiveJob:
    """Convenience function to run an estimator.

    Args:
        circuits: Circuit(s) to use for state preparation.
        observables: Observable(s) to estimate.
        backend: Optional backend to use.
        wrap_angles: Optional angle wrapping configuration.

    Returns:
        PrimitiveJob with estimation results.
    """
    estimator = EstimatorV2(backend=backend)
    return estimator.run(circuits=circuits, observables=observables, wrap_angles=wrap_angles, **options)
