"""
UMEROS Provider Base Module
===========================
Core abstractions for quantum hardware providers, backends, jobs, and results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class JobQueueMode(Enum):
    """Mode of execution for submitted jobs."""

    QUEUE = "queue"
    EMULATE = "emulate"
    HYBRID = "hybrid"


class BackendStatus(Enum):
    """Operational status of a quantum backend."""

    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    QUEUE_PAUSED = "queue_paused"
    ERROR = "error"


@dataclass
class GateSet:
    """Represents a named gate set supported by a backend.

    Attributes:
        name: Human-readable name for the gate set (e.g. "universal", "surface_code").
        gates: List of gate names included in the set (e.g. ["H", "CNOT", "T"]).
        max_qubits: Maximum number of qubits this gate set can operate on.
    """

    name: str
    gates: List[str]
    max_qubits: int

    def __repr__(self) -> str:
        return f"GateSet(name={self.name!r}, gates={self.gates!r}, max_qubits={self.max_qubits})"


@dataclass
class BackendTargetCoupling:
    """Defines a coupling constraint between two qubits.

    Attributes:
        q1: First qubit index.
        q2: Second qubit index.
        gate: The gate allowed between these qubits (default "CNOT").
    """

    q1: int
    q2: int
    gate: str = "CNOT"

    def __repr__(self) -> str:
        return f"BackendTargetCoupling(q1={self.q1}, q2={self.q2}, gate={self.gate!r})"


@dataclass
class BackendTarget:
    """Full description of a quantum backend target.

    Attributes:
        name: Unique backend identifier.
        num_qubits: Number of qubits available.
        status: Current operational status.
        provider_name: Name of the owning provider.
        gate_set: Supported gate set.
        coupling_map: Qubit coupling constraints.
        max_shots: Maximum measurement shots per job.
        max_circuits: Maximum circuits per job.
        basis_gates: Minimum gate set required for compilation.
        native_gates: Gates natively supported by hardware.
        simulator: Whether this is a simulator backend.
        dynamic_circuits: Whether dynamic circuits are supported.
        description: Human-readable description.
        operational: Whether the backend is currently operational.
        pending_jobs: Number of jobs currently in the queue.
        tags: User-defined tags for filtering.
    """

    name: str
    num_qubits: int
    status: BackendStatus
    provider_name: str
    gate_set: GateSet
    coupling_map: List[BackendTargetCoupling]
    max_shots: int = 4000
    max_circuits: int = 100
    basis_gates: List[str] = field(default_factory=list)
    native_gates: List[str] = field(default_factory=list)
    simulator: bool = False
    dynamic_circuits: bool = True
    description: str = ""
    operational: bool = True
    pending_jobs: int = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all fields to a dictionary."""
        return {
            "name": self.name,
            "num_qubits": self.num_qubits,
            "status": self.status.value,
            "provider_name": self.provider_name,
            "gate_set": {
                "name": self.gate_set.name,
                "gates": self.gate_set.gates,
                "max_qubits": self.gate_set.max_qubits,
            },
            "coupling_map": [
                {"q1": c.q1, "q2": c.q2, "gate": c.gate}
                for c in self.coupling_map
            ],
            "max_shots": self.max_shots,
            "max_circuits": self.max_circuits,
            "basis_gates": list(self.basis_gates),
            "native_gates": list(self.native_gates),
            "simulator": self.simulator,
            "dynamic_circuits": self.dynamic_circuits,
            "description": self.description,
            "operational": self.operational,
            "pending_jobs": self.pending_jobs,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BackendTarget":
        """Construct a BackendTarget from a dictionary.

        Args:
            d: Dictionary with keys matching ``to_dict()`` output.

        Returns:
            A fully initialized BackendTarget instance.
        """
        gate_set = GateSet(
            name=d["gate_set"]["name"],
            gates=d["gate_set"]["gates"],
            max_qubits=d["gate_set"]["max_qubits"],
        )
        coupling_map = [
            BackendTargetCoupling(q1=c["q1"], q2=c["q2"], gate=c.get("gate", "CNOT"))
            for c in d.get("coupling_map", [])
        ]
        return cls(
            name=d["name"],
            num_qubits=d["num_qubits"],
            status=BackendStatus(d["status"]),
            provider_name=d["provider_name"],
            gate_set=gate_set,
            coupling_map=coupling_map,
            max_shots=d.get("max_shots", 4000),
            max_circuits=d.get("max_circuits", 100),
            basis_gates=d.get("basis_gates", []),
            native_gates=d.get("native_gates", []),
            simulator=d.get("simulator", False),
            dynamic_circuits=d.get("dynamic_circuits", True),
            description=d.get("description", ""),
            operational=d.get("operational", True),
            pending_jobs=d.get("pending_jobs", 0),
            tags=d.get("tags", []),
        )

    def __repr__(self) -> str:
        return (
            f"BackendTarget(name={self.name!r}, num_qubits={self.num_qubits}, "
            f"status={self.status.value!r}, provider_name={self.provider_name!r})"
        )


@dataclass
class BackendProperties:
    """Calibration and error data for a quantum backend.

    Attributes:
        backend_name: Name of the backend these properties describe.
        backend_version: Version string for the properties data.
        qubits: Per-qubit metrics (T1, T2, frequency, readout_error, etc.).
        gates: Per-gate error rates grouped by gate name and qubit indices.
        general: General backend calibration data.
        last_update: ISO timestamp of the last properties update.
    """

    backend_name: str
    backend_version: str
    qubits: List[Dict[str, Any]]
    gates: List[Dict[str, Any]]
    general: List[Dict[str, Any]]
    last_update: str

    def gate_error(self, gate_name: str, qubit_indices: List[int]) -> float:
        """Return the error rate for a specific gate on given qubits.

        Args:
            gate_name: Name of the gate (e.g. "cx", "u3").
            qubit_indices: List of qubit indices the gate operates on.

        Returns:
            The error rate as a float between 0 and 1.

        Raises:
            KeyError: If no matching gate entry is found.
        """
        for g in self.gates:
            if g.get("gate") == gate_name and g.get("qubits") == qubit_indices:
                return float(g.get("error", 0.0))
        raise KeyError(
            f"No gate_error found for {gate_name} on qubits {qubit_indices}"
        )

    def t1(self, qubit: int) -> float:
        """Return the T1 relaxation time for a qubit (seconds).

        Args:
            qubit: Qubit index.

        Returns:
            T1 value in seconds.

        Raises:
            IndexError: If the qubit index is out of range.
        """
        if qubit < 0 or qubit >= len(self.qubits):
            raise IndexError(
                f"Qubit index {qubit} out of range (0..{len(self.qubits) - 1})"
            )
        return float(self.qubits[qubit].get("T1", 0.0))

    def t2(self, qubit: int) -> float:
        """Return the T2 dephasing time for a qubit (seconds).

        Args:
            qubit: Qubit index.

        Returns:
            T2 value in seconds.

        Raises:
            IndexError: If the qubit index is out of range.
        """
        if qubit < 0 or qubit >= len(self.qubits):
            raise IndexError(
                f"Qubit index {qubit} out of range (0..{len(self.qubits) - 1})"
            )
        return float(self.qubits[qubit].get("T2", 0.0))

    def readout_error(self, qubit: int) -> float:
        """Return the readout error probability for a qubit.

        Args:
            qubit: Qubit index.

        Returns:
            Readout error as a float between 0 and 1.

        Raises:
            IndexError: If the qubit index is out of range.
        """
        if qubit < 0 or qubit >= len(self.qubits):
            raise IndexError(
                f"Qubit index {qubit} out of range (0..{len(self.qubits) - 1})"
            )
        return float(self.qubits[qubit].get("readout_error", 0.0))

    def __repr__(self) -> str:
        return (
            f"BackendProperties(backend_name={self.backend_name!r}, "
            f"backend_version={self.backend_version!r}, "
            f"num_qubits={len(self.qubits)}, "
            f"last_update={self.last_update!r})"
        )


@dataclass
class JobResult:
    """Result container for a completed quantum job.

    Attributes:
        job_id: Unique job identifier.
        backend_name: Name of the backend that executed the job.
        status: Job status (QUEUED, RUNNING, DONE, ERROR, CANCELLED).
        results: List of per-circuit result dicts with counts, probabilities, metadata.
        metadata: Top-level job metadata.
        error_message: Error details if the job failed (optional).
        start_time: ISO timestamp when the job started (optional).
        end_time: ISO timestamp when the job finished (optional).
    """

    job_id: str
    backend_name: str
    status: str
    results: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    error_message: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    def get_counts(self, circuit_index: int = 0) -> Dict[str, int]:
        """Return measurement counts for a specific circuit.

        Args:
            circuit_index: Index into the results list.

        Returns:
            Dictionary mapping bitstring to count.

        Raises:
            IndexError: If circuit_index is out of range.
            KeyError: If the result dict has no "counts" key.
        """
        if circuit_index < 0 or circuit_index >= len(self.results):
            raise IndexError(
                f"circuit_index {circuit_index} out of range (0..{len(self.results) - 1})"
            )
        return dict(self.results[circuit_index]["counts"])

    def get_probabilities(self, circuit_index: int = 0) -> Dict[str, float]:
        """Return outcome probabilities for a specific circuit.

        Args:
            circuit_index: Index into the results list.

        Returns:
            Dictionary mapping bitstring to probability.

        Raises:
            IndexError: If circuit_index is out of range.
            KeyError: If the result dict has no "probabilities" key.
        """
        if circuit_index < 0 or circuit_index >= len(self.results):
            raise IndexError(
                f"circuit_index {circuit_index} out of range (0..{len(self.results) - 1})"
            )
        return dict(self.results[circuit_index]["probabilities"])

    def get_metadata(self, circuit_index: int = 0) -> Dict[str, Any]:
        """Return metadata for a specific circuit result.

        Args:
            circuit_index: Index into the results list.

        Returns:
            Metadata dictionary for the circuit.

        Raises:
            IndexError: If circuit_index is out of range.
        """
        if circuit_index < 0 or circuit_index >= len(self.results):
            raise IndexError(
                f"circuit_index {circuit_index} out of range (0..{len(self.results) - 1})"
            )
        return dict(self.results[circuit_index].get("metadata", {}))

    def success(self) -> bool:
        """Return True if the job completed without error."""
        return self.status == "DONE" and self.error_message is None

    def __repr__(self) -> str:
        return (
            f"JobResult(job_id={self.job_id!r}, backend_name={self.backend_name!r}, "
            f"status={self.status!r}, num_results={len(self.results)})"
        )


class BackendJob(ABC):
    """Abstract base class representing a submitted quantum job.

    Args:
        job_id: Unique identifier for this job.
        backend_name: Name of the backend executing the job.
    """

    def __init__(self, job_id: str, backend_name: str) -> None:
        self._job_id = job_id
        self._backend_name = backend_name

    @property
    def job_id(self) -> str:
        """Unique job identifier."""
        return self._job_id

    @property
    def backend_name(self) -> str:
        """Name of the backend executing this job."""
        return self._backend_name

    @property
    @abstractmethod
    def status(self) -> str:
        """Current status of the job (QUEUED, RUNNING, DONE, ERROR, CANCELLED)."""
        ...

    @property
    @abstractmethod
    def queue_position(self) -> Optional[int]:
        """Position in the queue, or None if not queued."""
        ...

    @abstractmethod
    def cancel(self) -> None:
        """Cancel the running or queued job."""
        ...

    @abstractmethod
    def result(self, timeout: Optional[float] = None) -> JobResult:
        """Block until the job completes and return the result.

        Args:
            timeout: Maximum seconds to wait. None means wait indefinitely.

        Returns:
            The completed JobResult.

        Raises:
            TimeoutError: If the job does not complete within timeout.
        """
        ...

    @abstractmethod
    def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """Block until the job reaches a terminal state.

        Args:
            timeout: Maximum seconds to wait. None means wait indefinitely.

        Raises:
            TimeoutError: If the job does not complete within timeout.
        """
        ...

    def status_detail(self) -> str:
        """Return a human-readable status detail string."""
        return f"Job {self.job_id} on {self.backend_name} - status: {self.status}"

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(job_id={self.job_id!r}, "
            f"backend_name={self.backend_name!r}, status={self.status!r})"
        )


class BackendSession(ABC):
    """Abstract base class for a session with a quantum backend.

    Sessions manage authentication, connection pooling, and lifecycle for
    multiple job submissions to the same backend.

    Args:
        backend: The BackendTarget this session connects to.
        token: Optional authentication token.
        **kwargs: Additional provider-specific session options.
    """

    def __init__(
        self, backend: BackendTarget, token: Optional[str] = None, **kwargs: Any
    ) -> None:
        self._backend = backend
        self._token = token
        self._kwargs = kwargs

    @property
    def backend(self) -> BackendTarget:
        """The backend target for this session."""
        return self._backend

    @property
    def token(self) -> Optional[str]:
        """Authentication token, or None."""
        return self._token

    @abstractmethod
    def close(self) -> None:
        """Close the session and release resources."""
        ...

    @abstractmethod
    def submit_circuits(
        self, circuits: Any, shots: int = 1024, **options: Any
    ) -> BackendJob:
        """Submit one or more circuits for execution.

        Args:
            circuits: Circuits to execute (format depends on the provider).
            shots: Number of measurement shots per circuit.
            **options: Additional execution options.

        Returns:
            A BackendJob tracking the submitted work.
        """
        ...

    def __enter__(self) -> "BackendSession":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(backend={self.backend.name!r}, "
            f"token={'***' if self.token else None})"
        )


class BackendProvider(ABC):
    """Abstract base class for quantum hardware providers.

    A provider manages authentication, backend discovery, job submission,
    and account operations for a quantum computing platform.

    Args:
        token: Optional authentication token.
        **kwargs: Additional provider-specific configuration.
    """

    def __init__(self, token: Optional[str] = None, **kwargs: Any) -> None:
        self._token = token
        self._kwargs = kwargs

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical name of the provider (e.g. 'ibm', 'ionq')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Version string of the provider SDK."""
        ...

    @abstractmethod
    def backends(
        self, name: Optional[str] = None, **kwargs: Any
    ) -> List[BackendTarget]:
        """List available backends, optionally filtered by name or attributes.

        Args:
            name: Optional name filter (exact match or substring).
            **kwargs: Additional filters (e.g. simulator=True).

        Returns:
            List of matching BackendTarget instances.
        """
        ...

    @abstractmethod
    def get_backend(self, name: str) -> BackendTarget:
        """Retrieve a specific backend by name.

        Args:
            name: Exact backend name.

        Returns:
            The BackendTarget instance.

        Raises:
            KeyError: If no backend with the given name exists.
        """
        ...

    @abstractmethod
    def refresh_backends(self) -> None:
        """Refresh the local cache of available backends."""
        ...

    @abstractmethod
    def backend_status(self, name: str) -> BackendStatus:
        """Return the current status of a backend.

        Args:
            name: Backend name.

        Returns:
            Current BackendStatus enum value.
        """
        ...

    @abstractmethod
    def backend_properties(self, name: str) -> BackendProperties:
        """Return calibration and error properties for a backend.

        Args:
            name: Backend name.

        Returns:
            BackendProperties with current calibration data.
        """
        ...

    @abstractmethod
    def submit_job(
        self,
        backend_name: str,
        circuits: Any,
        shots: int = 1024,
        **options: Any,
    ) -> BackendJob:
        """Submit a job for execution on a specific backend.

        Args:
            backend_name: Target backend name.
            circuits: Circuits to execute.
            shots: Number of measurement shots.
            **options: Additional provider-specific options.

        Returns:
            A BackendJob tracking the submission.
        """
        ...

    @abstractmethod
    def get_job(self, job_id: str) -> BackendJob:
        """Retrieve an existing job by its ID.

        Args:
            job_id: Unique job identifier.

        Returns:
            The BackendJob instance.

        Raises:
            KeyError: If no job with the given ID exists.
        """
        ...

    @abstractmethod
    def cancel_job(self, job_id: str) -> None:
        """Cancel a queued or running job.

        Args:
            job_id: Unique job identifier.
        """
        ...

    @abstractmethod
    def my_reservations(self) -> List[Dict[str, Any]]:
        """Return a list of backend reservations for the current account.

        Returns:
            List of reservation dicts with details like backend, start, end, status.
        """
        ...

    @abstractmethod
    def account_usage(self) -> Dict[str, Any]:
        """Return current account usage statistics.

        Returns:
            Dictionary with usage metrics (seconds used, jobs run, quota, etc.).
        """
        ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, version={self.version!r})"
