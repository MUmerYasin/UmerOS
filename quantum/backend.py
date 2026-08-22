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

"""Quantum Backend Abstraction - Unified interface for local simulator and IBM Quantum.

Provides a common Backend interface that wraps:
- LocalStatevectorSimulator (pure Python, no dependencies)
- IBMBackend (IBM Quantum runtime, optional dependency)

    from quantum.backend import Backend, LocalBackend, IBMBackend

    backend = LocalBackend()
    result = backend.run(circuit, shots=1024)

    # Or with IBM Quantum
    backend = IBMBackend(token="...", instance="ibm-q/open/main")
    result = backend.run(circuit, shots=1024)

Backend objects are compatible with noise models and can be composed.
"""

from __future__ import annotations

import math
import time
from typing import Optional, Dict, Any, List, Sequence
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from collections import Counter

import numpy as np
from numpy.typing import NDArray

from .circuit import QuantumCircuit
from .gates import Gate
from .simulator import StatevectorSimulator, DensityMatrixSimulator, Statevector, MeasurementResult
from .noise import NoiseModel


# ---------------------------------------------------------------------------
# Backend status and options
# ---------------------------------------------------------------------------

class BackendStatus(Enum):
    """Backend operational status."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


@dataclass
class BackendOptions:
    """Options for backend execution."""
    shots: int = 1024
    seed: Optional[int] = None
    noise_model: Optional[NoiseModel] = None
    optimization_level: int = 1
    max_shots: int = 8192
    memory: bool = False
    memory_slots: int = 0

    def validate(self):
        if self.shots < 1:
            raise ValueError("shots must be >= 1")
        if self.shots > self.max_shots:
            raise ValueError(f"shots {self.shots} exceeds max {self.max_shots}")
        if self.optimization_level < 0 or self.optimization_level > 3:
            raise ValueError("optimization_level must be 0-3")


@dataclass
class JobResult:
    """Result from a backend job execution."""
    job_id: str
    status: str
    counts: Dict[str, int]
    num_qubits: int
    shots: int
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def most_common(self) -> List[tuple]:
        return sorted(self.counts.items(), key=lambda x: -x[1])

    def frequency(self, bitstring: str) -> float:
        return self.counts.get(bitstring, 0) / self.shots

    def __repr__(self) -> str:
        return f"JobResult(job_id={self.job_id}, shots={self.shots}, status={self.status})"


# ---------------------------------------------------------------------------
# Abstract Backend
# ---------------------------------------------------------------------------

class Backend(ABC):
    """Abstract quantum backend interface.

    All backends must implement run() and status().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name."""
        ...

    @property
    @abstractmethod
    def num_qubits(self) -> int:
        """Maximum number of qubits supported."""
        ...

    @property
    @abstractmethod
    def max_shots(self) -> int:
        """Maximum number of shots."""
        ...

    @abstractmethod
    def status(self) -> BackendStatus:
        """Get backend status."""
        ...

    @abstractmethod
    def run(self, circuit: QuantumCircuit, **kwargs) -> JobResult:
        """Execute a circuit on the backend."""
        ...

    def run_batch(self, circuits: List[QuantumCircuit], **kwargs) -> List[JobResult]:
        """Execute multiple circuits (batch mode)."""
        return [self.run(c, **kwargs) for c in circuits]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"


# ---------------------------------------------------------------------------
# Local Simulator Backend
# ---------------------------------------------------------------------------

class LocalBackend(Backend):
    """Pure-Python local simulator backend.

    Uses statevector simulation with optional noise model.
    Suitable for circuits up to ~20 qubits.
    """

    def __init__(self, num_qubits: int = 20, seed: Optional[int] = None,
                 use_density_matrix: bool = False):
        self._num_qubits = num_qubits
        self._seed = seed
        self._use_density_matrix = use_density_matrix
        self._sv_sim = StatevectorSimulator(seed=seed)
        self._dm_sim = DensityMatrixSimulator(seed=seed) if use_density_matrix else None

    @property
    def name(self) -> str:
        return "local_statevector"

    @property
    def num_qubits(self) -> int:
        return self._num_qubits

    @property
    def max_shots(self) -> int:
        return 100000

    def status(self) -> BackendStatus:
        return BackendStatus.ONLINE

    def run(self, circuit: QuantumCircuit, **kwargs) -> JobResult:
        """Run circuit on local simulator.

        Args:
            circuit: Quantum circuit to execute
            shots: Number of shots (default 1024)
            noise_model: Optional NoiseModel
            seed: Random seed
        """
        shots = kwargs.get("shots", 1024)
        noise = kwargs.get("noise_model", None)
        seed = kwargs.get("seed", self._seed)

        if seed is not None:
            np.random.seed(seed)

        start_time = time.time()

        if self._use_density_matrix and self._dm_sim:
            result = self._dm_sim.run(circuit, shots=shots, noise_model=noise)
        else:
            result = self._sv_sim.run(circuit, shots=shots, noise_model=noise)

        exec_time = time.time() - start_time

        if noise is not None and hasattr(noise, "apply_readout_error"):
            result.counts = noise.apply_readout_error(result.counts, circuit.num_qubits)

        return JobResult(
            job_id=f"local-{id(circuit)}",
            status="completed",
            counts=result.counts,
            num_qubits=circuit.num_qubits,
            shots=shots,
            execution_time=exec_time,
            metadata={"backend": self.name, "noise": str(noise) if noise else None}
        )

    def run_with_statevector(self, circuit: QuantumCircuit, **kwargs) -> Statevector:
        """Run circuit and return final statevector (no measurement)."""
        noise = kwargs.get("noise_model", None)
        return self._sv_sim.run_with_state(circuit, noise_model=noise)


class LocalDensityMatrixBackend(LocalBackend):
    """Local backend using density matrix simulation."""

    def __init__(self, num_qubits: int = 15, seed: Optional[int] = None):
        super().__init__(num_qubits=num_qubits, seed=seed, use_density_matrix=True)

    @property
    def name(self) -> str:
        return "local_density_matrix"


# ---------------------------------------------------------------------------
# Aer-compatible Backend (uses local sim with Aer-like API)
# ---------------------------------------------------------------------------

class AerBackend(Backend):
    """Backend compatible with Qiskit Aer API.

    Wraps the local simulator with an interface matching AerSimulator.
    """

    def __init__(self, backend_options: Optional[Dict] = None):
        opts = backend_options or {}
        self._local = LocalBackend(
            num_qubits=opts.get("max_qubits", 20),
            seed=opts.get("seed_simulator"),
            use_density_matrix=opts.get("method") == "density_matrix"
        )

    @property
    def name(self) -> str:
        return "aer_simulator"

    @property
    def num_qubits(self) -> int:
        return self._local.num_qubits

    @property
    def max_shots(self) -> int:
        return self._local.max_shots

    def status(self) -> BackendStatus:
        return BackendStatus.ONLINE

    def run(self, circuit: QuantumCircuit, **kwargs) -> JobResult:
        return self._local.run(circuit, **kwargs)


# ---------------------------------------------------------------------------
# IBM Quantum Backend (stub - requires qiskit-ibm-runtime)
# ---------------------------------------------------------------------------

class IBMBackend(Backend):
    """IBM Quantum backend via qiskit-ibm-runtime.

    Requires: pip install qiskit-ibm-runtime
    """

    def __init__(self, token: Optional[str] = None, instance: Optional[str] = None,
                 backend_name: str = "ibm_brisbane", **kwargs):
        self._token = token
        self._instance = instance
        self._backend_name = backend_name
        self._service = None
        self._backend = None

        try:
            from qiskit_ibm_runtime import QiskitRuntimeService
            self._service = QiskitRuntimeService(
                token=token, instance=instance
            )
            self._backend = self._service.backend(backend_name)
        except ImportError:
            pass
        except Exception as e:
            print(f"IBM Backend init warning: {e}")

    @property
    def name(self) -> str:
        return self._backend_name

    @property
    def num_qubits(self) -> int:
        if self._backend:
            return self._backend.num_qubits
        return 127

    @property
    def max_shots(self) -> int:
        if self._backend:
            return self._backend.max_shots
        return 4000

    def status(self) -> BackendStatus:
        if self._backend is None:
            return BackendStatus.OFFLINE
        try:
            status = self._backend.status()
            if status.operational:
                return BackendStatus.ONLINE
            return BackendStatus.OFFLINE
        except Exception:
            return BackendStatus.ERROR

    def run(self, circuit: QuantumCircuit, **kwargs) -> JobResult:
        """Run circuit on IBM Quantum.

        Args:
            circuit: Quantum circuit to execute
            shots: Number of shots
            optimization_level: Transpilation optimization level (0-3)
            resilience_level: Error mitigation level (0-2)
        """
        if self._backend is None:
            raise RuntimeError(
                "IBM Backend not initialized. Install qiskit-ibm-runtime "
                "and provide a valid token."
            )

        shots = kwargs.get("shots", 1024)
        optimization_level = kwargs.get("optimization_level", 1)
        resilience_level = kwargs.get("resilience_level", 1)

        start_time = time.time()

        try:
            from qiskit_ibm_runtime import EstimatorV2 as Estimator, SamplerV2 as Sampler
            from qiskit import transpile

            transpiled = transpile(
                circuit, self._backend,
                optimization_level=optimization_level
            )

            sampler = Sampler(self._backend)
            job = sampler.run([transpiled], shots=shots)
            result = job.result()

            counts = {}
            if hasattr(result, "quasi_dists"):
                for dist in result.quasi_dists:
                    for k, v in dist.items():
                        counts[f"{k:0{circuit.num_qubits}b}"] = int(v * shots)

            exec_time = time.time() - start_time

            return JobResult(
                job_id=job.job_id() if hasattr(job, "job_id") else "ibm-unknown",
                status="completed",
                counts=counts,
                num_qubits=circuit.num_qubits,
                shots=shots,
                execution_time=exec_time,
                metadata={"backend": self._backend_name, "provider": "ibm"}
            )
        except ImportError:
            raise RuntimeError(
                "qiskit-ibm-runtime not installed. "
                "Install with: pip install qiskit-ibm-runtime"
            )


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------

def get_backend(name: str = "local", **kwargs) -> Backend:
    """Get a backend by name.

    Supported backends:
    - "local" / "local_statevector": Local statevector simulator
    - "local_density": Local density matrix simulator
    - "aer": Aer-compatible simulator
    - "ibm": IBM Quantum (requires token)
    """
    backends = {
        "local": lambda: LocalBackend(**kwargs),
        "local_statevector": lambda: LocalBackend(**kwargs),
        "local_density": lambda: LocalDensityMatrixBackend(**kwargs),
        "aer": lambda: AerBackend(**kwargs),
        "ibm": lambda: IBMBackend(**kwargs),
    }

    if name not in backends:
        raise ValueError(f"Unknown backend '{name}'. Available: {list(backends.keys())}")

    return backends[name]()


# ---------------------------------------------------------------------------
# Backend monitoring
# ---------------------------------------------------------------------------

class BackendMonitor:
    """Monitor backend performance and status."""

    def __init__(self, backend: Backend):
        self._backend = backend
        self._history: List[Dict] = []

    def run_and_monitor(self, circuit: QuantumCircuit, **kwargs) -> JobResult:
        """Run a circuit and record performance metrics."""
        result = self._backend.run(circuit, **kwargs)

        self._history.append({
            "job_id": result.job_id,
            "num_qubits": circuit.num_qubits,
            "depth": circuit.depth,
            "shots": result.shots,
            "execution_time": result.execution_time,
            "num_outcomes": len(result.counts),
        })

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated performance statistics."""
        if not self._history:
            return {"runs": 0}

        times = [h["execution_time"] for h in self._history]
        return {
            "runs": len(self._history),
            "avg_time": sum(times) / len(times),
            "total_time": sum(times),
            "min_time": min(times),
            "max_time": max(times),
            "avg_qubits": sum(h["num_qubits"] for h in self._history) / len(self._history),
            "avg_depth": sum(h["depth"] for h in self._history) / len(self._history),
        }
