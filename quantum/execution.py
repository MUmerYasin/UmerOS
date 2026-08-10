"""Execution management for quantum circuits.

Provides job management, batching, and session capabilities
for running quantum circuits on various backends.
"""

from __future__ import annotations

import time
import threading
from typing import Any, Union, Optional, Callable
from enum import Enum
import uuid

from .circuit import QuantumCircuit
from .backend import Backend, get_backend


class JobStatus(Enum):
    """Status of a quantum job."""
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    ERROR = "error"


class ExecutionOptions:
    """Options for quantum circuit execution."""

    def __init__(
        self,
        shots: int = 1024,
        seed: Optional[int] = None,
        memory: bool = False,
        max_credits: Optional[int] = None,
        noise_model: Optional[str] = None,
        optimization_level: int = 1,
        **kwargs,
    ):
        self.shots = shots
        self.seed = seed
        self.memory = memory
        self.max_credits = max_credits
        self.noise_model = noise_model
        self.optimization_level = optimization_level
        self.extra_options = kwargs

    def to_dict(self) -> dict:
        """Convert options to dictionary."""
        result = {
            "shots": self.shots,
            "seed": self.seed,
            "memory": self.memory,
            "optimization_level": self.optimization_level,
        }
        if self.max_credits is not None:
            result["max_credits"] = self.max_credits
        if self.noise_model is not None:
            result["noise_model"] = self.noise_model
        result.update(self.extra_options)
        return result


class MeasurementResult:
    """Container for measurement results from a job."""

    def __init__(self, counts: dict[str, int], memory: Optional[list[str]] = None):
        self._counts = counts
        self._memory = memory or []

    @property
    def counts(self) -> dict[str, int]:
        """Get measurement counts."""
        return self._counts

    @property
    def memory(self) -> list[str]:
        """Get individual measurement bitstrings (if memory=True)."""
        return self._memory

    def get_count(self, bitstring: str) -> int:
        """Get count for a specific bitstring."""
        return self._counts.get(bitstring, 0)

    def most_frequent(self) -> str:
        """Get the most frequent measurement outcome."""
        if not self._counts:
            return ""
        return max(self._counts, key=self._counts.get)

    @property
    def shots(self) -> int:
        """Total number of shots."""
        return sum(self._counts.values())

    def __repr__(self):
        return f"MeasurementResult(shots={self.shots}, outcomes={len(self._counts)})"


class QuantumJob:
    """Represents a quantum circuit execution job.

    Manages the lifecycle of a circuit execution including
    status tracking, result retrieval, and cancellation.
    """

    def __init__(
        self,
        circuit: QuantumCircuit,
        backend: Backend,
        options: ExecutionOptions,
        job_id: Optional[str] = None,
    ):
        self._circuit = circuit
        self._backend = backend
        self._options = options
        self._job_id = job_id or str(uuid.uuid4())[:8]
        self._status = JobStatus.QUEUED
        self._result = None
        self._error = None
        self._start_time = None
        self._end_time = None

    @property
    def job_id(self) -> str:
        return self._job_id

    @property
    def status(self) -> JobStatus:
        return self._status

    @property
    def circuit(self) -> QuantumCircuit:
        return self._circuit

    @property
    def backend(self) -> Backend:
        return self._backend

    @property
    def result(self) -> MeasurementResult:
        """Get the job result. Raises error if job failed."""
        if self._status == JobStatus.ERROR:
            raise self._error
        if self._status != JobStatus.DONE:
            raise RuntimeError(f"Job {self._job_id} has not completed (status: {self._status.value})")
        return self._result

    @property
    def done(self) -> bool:
        return self._status == JobStatus.DONE

    @property
    def elapsed_time(self) -> float:
        if self._start_time is None:
            return 0.0
        end = self._end_time or time.time()
        return end - self._start_time

    def run(self) -> MeasurementResult:
        """Execute the job synchronously."""
        self._start_time = time.time()
        self._status = JobStatus.RUNNING

        try:
            result = self._backend.run(
                self._circuit,
                shots=self._options.shots,
                seed=self._options.seed,
            )
            self._result = MeasurementResult(
                counts=result.counts,
                memory=None,
            )
            self._status = JobStatus.DONE
        except Exception as e:
            self._error = e
            self._status = JobStatus.ERROR
            raise
        finally:
            self._end_time = time.time()

        return self._result

    def cancel(self):
        """Cancel the job."""
        if self._status in (JobStatus.DONE, JobStatus.ERROR):
            return
        self._status = JobStatus.CANCELLED

    def __repr__(self):
        return (
            f"QuantumJob(job_id='{self._job_id}', "
            f"status='{self._status.value}', "
            f"backend='{self._backend.name}')"
        )


class Batch:
    """Batch multiple quantum circuits for execution.

    Groups circuits to be executed together, potentially with
    shared resources or optimization opportunities.

    Usage:
        batch = Batch(backend=local_backend)
        batch.add(circuit1)
        batch.add(circuit2, shots=2048)
        results = batch.run()
    """

    def __init__(self, backend: Optional[Backend] = None, default_options: Optional[ExecutionOptions] = None):
        self._backend = backend or get_backend("local")
        self._default_options = default_options or ExecutionOptions()
        self._jobs: list[QuantumJob] = []
        self._results: list[MeasurementResult] = []

    @property
    def backend(self) -> Backend:
        return self._backend

    @property
    def size(self) -> int:
        return len(self._jobs)

    @property
    def jobs(self) -> list[QuantumJob]:
        return self._jobs.copy()

    def add(
        self,
        circuit: QuantumCircuit,
        shots: Optional[int] = None,
        **options,
    ) -> QuantumJob:
        """Add a circuit to the batch.

        Args:
            circuit: Circuit to execute.
            shots: Optional shot count override.
            **options: Additional execution options.

        Returns:
            The created QuantumJob.
        """
        exec_options = ExecutionOptions(
            shots=shots or self._default_options.shots,
            seed=self._default_options.seed,
            **options,
        )
        job = QuantumJob(
            circuit=circuit,
            backend=self._backend,
            options=exec_options,
        )
        self._jobs.append(job)
        return job

    def run(self) -> list[MeasurementResult]:
        """Execute all circuits in the batch.

        Returns:
            List of MeasurementResult instances.
        """
        self._results = []
        for job in self._jobs:
            result = job.run()
            self._results.append(result)
        return self._results

    def get_result(self, index: int) -> MeasurementResult:
        """Get result for a specific job index."""
        if index >= len(self._results):
            raise IndexError(f"Result index {index} out of range (batch size: {len(self._results)})")
        return self._results[index]

    def clear(self):
        """Clear all jobs from the batch."""
        self._jobs.clear()
        self._results.clear()

    def __repr__(self):
        return f"Batch(backend='{self._backend.name}', size={self.size})"


class Session:
    """Session for managing multiple quantum executions.

    Provides a context for executing multiple circuits on the same
    backend, potentially enabling optimizations across executions.

    Usage:
        with Session(backend=local_backend) as session:
            result1 = session.run(circuit1)
            result2 = session.run(circuit2)
    """

    def __init__(self, backend: Optional[Backend] = None, **options):
        self._backend = backend or get_backend("local")
        self._options = ExecutionOptions(**options)
        self._is_active = False
        self._jobs: list[QuantumJob] = []

    @property
    def backend(self) -> Backend:
        return self._backend

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def jobs(self) -> list[QuantumJob]:
        return self._jobs.copy()

    def __enter__(self):
        self._is_active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._is_active = False
        return False

    def run(
        self,
        circuit: QuantumCircuit,
        shots: Optional[int] = None,
        **options,
    ) -> MeasurementResult:
        """Run a circuit within this session.

        Args:
            circuit: Circuit to execute.
            shots: Optional shot count override.
            **options: Additional execution options.

        Returns:
            MeasurementResult from the execution.
        """
        if not self._is_active:
            raise RuntimeError("Session is not active. Use 'with Session(...) as session:'")

        exec_options = ExecutionOptions(
            shots=shots or self._options.shots,
            seed=self._options.seed,
            **options,
        )

        job = QuantumJob(
            circuit=circuit,
            backend=self._backend,
            options=exec_options,
        )
        self._jobs.append(job)
        return job.run()

    def close(self):
        """Close the session."""
        self._is_active = False


def execute(
    circuits: Union[QuantumCircuit, list[QuantumCircuit]],
    backend: Optional[Backend] = None,
    shots: int = 1024,
    seed: Optional[int] = None,
    **options,
) -> Union[MeasurementResult, list[MeasurementResult]]:
    """Execute quantum circuits on a backend.

    This is the primary entry point for running quantum circuits.

    Args:
        circuits: A single circuit or list of circuits to execute.
        backend: Backend to use. Defaults to local statevector simulator.
        shots: Number of measurement shots.
        seed: Random seed for reproducibility.
        **options: Additional execution options.

    Returns:
        MeasurementResult for a single circuit, or list of MeasurementResult
        for multiple circuits.

    Examples:
        # Single circuit
        result = execute(circuit, shots=1024)
        print(result.most_frequent())

        # Multiple circuits
        results = execute([circuit1, circuit2], shots=512)
        for r in results:
            print(r.most_frequent())
    """
    if backend is None:
        backend = get_backend("local")

    # Handle single circuit case
    single = not isinstance(circuits, list)
    if single:
        circuits = [circuits]

    exec_options = ExecutionOptions(shots=shots, seed=seed, **options)

    results = []
    for circuit in circuits:
        job = QuantumJob(
            circuit=circuit,
            backend=backend,
            options=exec_options,
        )
        result = job.run()
        results.append(result)

    return results[0] if single else results


class ExecutionManager:
    """Manages execution of multiple quantum jobs.

    Provides centralized management of job execution, including
    tracking, prioritization, and resource management.
    """

    def __init__(self, backend: Optional[Backend] = None):
        self._backend = backend or get_backend("local")
        self._jobs: dict[str, QuantumJob] = {}
        self._history: list[QuantumJob] = []

    @property
    def backend(self) -> Backend:
        return self._backend

    @property
    def active_jobs(self) -> list[QuantumJob]:
        return [j for j in self._jobs.values() if not j.done]

    @property
    def completed_jobs(self) -> list[QuantumJob]:
        return [j for j in self._jobs.values() if j.done]

    def submit(
        self,
        circuit: QuantumCircuit,
        shots: int = 1024,
        **options,
    ) -> QuantumJob:
        """Submit a circuit for execution.

        Args:
            circuit: Circuit to execute.
            shots: Number of shots.
            **options: Additional options.

        Returns:
            The created QuantumJob.
        """
        exec_options = ExecutionOptions(shots=shots, **options)
        job = QuantumJob(
            circuit=circuit,
            backend=self._backend,
            options=exec_options,
        )
        self._jobs[job.job_id] = job
        return job

    def run_all(self) -> dict[str, MeasurementResult]:
        """Run all submitted jobs.

        Returns:
            Dictionary mapping job IDs to results.
        """
        results = {}
        for job_id, job in self._jobs.items():
            if not job.done:
                result = job.run()
                results[job_id] = result
                self._history.append(job)
        return results

    def get_job(self, job_id: str) -> QuantumJob:
        """Get a job by its ID."""
        if job_id not in self._jobs:
            raise KeyError(f"Job {job_id} not found")
        return self._jobs[job_id]

    def cancel_job(self, job_id: str):
        """Cancel a specific job."""
        job = self.get_job(job_id)
        job.cancel()

    def clear(self):
        """Clear all jobs."""
        self._jobs.clear()

    def __repr__(self):
        return (
            f"ExecutionManager(backend='{self._backend.name}', "
            f"active={len(self.active_jobs)}, "
            f"completed={len(self.completed_jobs)})"
        )
