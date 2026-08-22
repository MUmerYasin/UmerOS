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

"""
UMEROS Cloud Session
=====================
Session management for interacting with quantum cloud backends.
Wires to real provider REST APIs (IBM, IonQ, Braket, Rigetti).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .job import CloudJob, CloudJobStatus, _http_request

if TYPE_CHECKING:
    from .auth import AuthManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider-specific backend schemas
# ---------------------------------------------------------------------------


@dataclass
class ProviderBackend:
    """Standardised backend descriptor returned by every provider adapter."""

    name: str
    n_qubits: int
    status: str
    provider: str
    description: str = ""
    basis_gates: Optional[List[str]] = None
    max_shots: int = 4096
    avg_t1_us: Optional[float] = None
    avg_t2_us: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "n_qubits": self.n_qubits,
            "status": self.status,
            "provider": self.provider,
            "description": self.description,
            "max_shots": self.max_shots,
        }
        if self.basis_gates is not None:
            d["basis_gates"] = self.basis_gates
        if self.avg_t1_us is not None:
            d["avg_t1_us"] = self.avg_t1_us
        if self.avg_t2_us is not None:
            d["avg_t2_us"] = self.avg_t2_us
        return d


# ---------------------------------------------------------------------------
# Provider backend adapters — each calls real APIs
# ---------------------------------------------------------------------------


class IBMBackendAdapter:
    """IBM Quantum backends via REST API.

    GET /Network/{hub}/Groups/{group}/Projects/{project}/devices
    GET /devices/{device_name}
    """

    def list_backends(
        self, token: str, endpoint: str, status_filter: Optional[str] = None
    ) -> List[ProviderBackend]:
        base = endpoint.rstrip("/")
        # IBM uses v2 devices endpoint
        url = f"{base}/devices?pending_jobs=0"
        try:
            data = _http_request(
                "GET", url, headers={"Authorization": f"Bearer {token}"}
            )
        except (RuntimeError, ConnectionError):
            return []

        backends: List[ProviderBackend] = []
        items = data if isinstance(data, list) else data.get("devices", [])
        for dev in items:
            name = dev.get("name", "")
            n_qubits = dev.get("n_qubits", dev.get("num_qubits", 0))
            raw_status = dev.get("status", "offline")
            if status_filter and raw_status.lower() != status_filter.lower():
                continue
            backends.append(
                ProviderBackend(
                    name=name,
                    n_qubits=n_qubits,
                    status=raw_status,
                    provider="ibm",
                    description=dev.get("description", ""),
                    basis_gates=dev.get("basis_gates"),
                    max_shots=dev.get("max_shots", 8192),
                )
            )
        return backends

    def get_backend_properties(
        self, backend_name: str, token: str, endpoint: str
    ) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        data = _http_request(
            "GET",
            f"{base}/devices/{backend_name}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return data


class IonQBackendAdapter:
    """IonQ backends via REST API v0.3.

    GET /targets
    """

    def list_backends(
        self, token: str, endpoint: str, status_filter: Optional[str] = None
    ) -> List[ProviderBackend]:
        base = endpoint.rstrip("/")
        data = _http_request(
            "GET",
            f"{base}/targets",
            headers={"Authorization": f"Bearer {token}"},
        )
        backends: List[ProviderBackend] = []
        targets = data if isinstance(data, list) else data.get("targets", [])
        for tgt in targets:
            name = tgt.get("name", tgt.get("target", ""))
            n_qubits = tgt.get("n_qubits", tgt.get("qubits", 11))
            raw_status = tgt.get("status", "online")
            if status_filter and raw_status.lower() != status_filter.lower():
                continue
            backends.append(
                ProviderBackend(
                    name=name,
                    n_qubits=n_qubits,
                    status=raw_status,
                    provider="ionq",
                    description=tgt.get("description", ""),
                    basis_gates=tgt.get("basis_gates"),
                    max_shots=tgt.get("max_shots", 10000),
                )
            )
        return backends

    def get_backend_properties(
        self, backend_name: str, token: str, endpoint: str
    ) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        return _http_request(
            "GET",
            f"{base}/targets/{backend_name}",
            headers={"Authorization": f"Bearer {token}"},
        )


class BraketBackendAdapter:
    """AWS Braket backends via REST API.

    GET /providers
    GET /devices
    """

    def list_backends(
        self, token: str, endpoint: str, status_filter: Optional[str] = None
    ) -> List[ProviderBackend]:
        base = endpoint.rstrip("/")
        data = _http_request(
            "GET",
            f"{base}/devices",
            headers={"Authorization": f"Bearer {token}"},
        )
        backends: List[ProviderBackend] = []
        devices = data if isinstance(data, list) else data.get("devices", [])
        for dev in devices:
            name = dev.get("name", dev.get("deviceArn", "").split("/")[-1])
            n_qubits = dev.get("number_of_qubits", 0)
            if isinstance(n_qubits, str):
                try:
                    n_qubits = int(n_qubits)
                except ValueError:
                    n_qubits = 0
            raw_status = dev.get("deviceStatus", dev.get("status", "OFFLINE"))
            if status_filter and raw_status.lower() != status_filter.lower():
                continue
            backends.append(
                ProviderBackend(
                    name=name,
                    n_qubits=n_qubits,
                    status=raw_status,
                    provider="braket",
                    description=dev.get("provider_name", ""),
                    basis_gates=dev.get("supported_actions"),
                    max_shots=dev.get("shots_max", 10000),
                )
            )
        return backends

    def get_backend_properties(
        self, backend_name: str, token: str, endpoint: str
    ) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        return _http_request(
            "GET",
            f"{base}/devices/{backend_name}",
            headers={"Authorization": f"Bearer {token}"},
        )


class RigettiBackendAdapter:
    """Rigetti QCS backends via REST API.

    GET /qpus
    GET /qpus/{qpu_name}
    """

    def list_backends(
        self, token: str, endpoint: str, status_filter: Optional[str] = None
    ) -> List[ProviderBackend]:
        base = endpoint.rstrip("/")
        data = _http_request(
            "GET",
            f"{base}/qpus",
            headers={"Authorization": f"Bearer {token}"},
        )
        backends: List[ProviderBackend] = []
        qpus = data if isinstance(data, list) else data.get("qpus", [])
        for qpu in qpus:
            name = qpu.get("name", "")
            n_qubits = qpu.get("n_qubits", qpu.get("num_qubits", 0))
            raw_status = qpu.get("status", "offline")
            if status_filter and raw_status.lower() != status_filter.lower():
                continue
            backends.append(
                ProviderBackend(
                    name=name,
                    n_qubits=n_qubits,
                    status=raw_status,
                    provider="rigetti",
                    description=qpu.get("description", ""),
                    max_shots=qpu.get("max_shots", 4000),
                )
            )
        return backends

    def get_backend_properties(
        self, backend_name: str, token: str, endpoint: str
    ) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        return _http_request(
            "GET",
            f"{base}/qpus/{backend_name}",
            headers={"Authorization": f"Bearer {token}"},
        )


# Adapter registry
_BACKEND_ADAPTERS: Dict[str, Any] = {
    "ibm": IBMBackendAdapter(),
    "ionq": IonQBackendAdapter(),
    "braket": BraketBackendAdapter(),
    "rigetti": RigettiBackendAdapter(),
}


# ---------------------------------------------------------------------------
# Provider-specific submit helpers
# ---------------------------------------------------------------------------


def _submit_ibm(
    circuit_dict: Dict[str, Any],
    backend_name: str,
    shots: int,
    token: str,
    endpoint: str,
    **options: Any,
) -> CloudJob:
    """Submit a circuit to IBM Quantum via REST API.

    POST /Network/{hub}/Groups/{group}/Projects/{project}/jobs
    """
    base = endpoint.rstrip("/")
    payload = {
        "backend": {"name": backend_name},
        "circuits": [circuit_dict],
        "shots": shots,
    }
    if options:
        payload.update(options)
    data = _http_request(
        "POST",
        f"{base}/jobs",
        headers={"Authorization": f"Bearer {token}"},
        body=payload,
    )
    job_id = data.get("id", data.get("job_id", f"ibm-{uuid.uuid4().hex[:12]}"))
    return CloudJob(
        job_id=job_id,
        provider="ibm",
        backend_name=backend_name,
        status=CloudJobStatus.QUEUED,
        token=token,
        endpoint=endpoint,
        shots=shots,
        circuit_dict=circuit_dict,
        options=options,
    )


def _submit_ionq(
    circuit_dict: Dict[str, Any],
    backend_name: str,
    shots: int,
    token: str,
    endpoint: str,
    **options: Any,
) -> CloudJob:
    """Submit a circuit to IonQ via REST API v0.3.

    POST /jobs
    """
    base = endpoint.rstrip("/")
    # IonQ uses JSON circuit format
    payload: Dict[str, Any] = {
        "target": backend_name,
        "shots": shots,
        "input": {
            "qasm": circuit_dict.get("qasm", ""),
        },
    }
    # IonQ also accepts their native JSON format
    if "json_circuit" in circuit_dict:
        payload["input"]["json_circuit"] = circuit_dict["json_circuit"]
    if options:
        payload.update(options)
    data = _http_request(
        "POST",
        f"{base}/jobs",
        headers={"Authorization": f"Bearer {token}"},
        body=payload,
    )
    job_id = data.get("id", data.get("job_id", f"ionq-{uuid.uuid4().hex[:12]}"))
    return CloudJob(
        job_id=job_id,
        provider="ionq",
        backend_name=backend_name,
        status=CloudJobStatus.QUEUED,
        token=token,
        endpoint=endpoint,
        shots=shots,
        circuit_dict=circuit_dict,
        options=options,
    )


def _submit_braket(
    circuit_dict: Dict[str, Any],
    backend_name: str,
    shots: int,
    token: str,
    endpoint: str,
    **options: Any,
) -> CloudJob:
    """Submit a circuit to AWS Braket via REST API.

    POST /tasks
    """
    base = endpoint.rstrip("/")
    # Braket expects OpenQASM or IR JSON
    payload: Dict[str, Any] = {
        "action": {
            "type": "circuit",
            "circuit": circuit_dict,
        },
        "device": backend_name,
        "shots": shots,
    }
    if options:
        payload.update(options)
    data = _http_request(
        "POST",
        f"{base}/tasks",
        headers={"Authorization": f"Bearer {token}"},
        body=payload,
    )
    job_id = data.get("taskArn", data.get("id", f"braket-{uuid.uuid4().hex[:12]}"))
    return CloudJob(
        job_id=job_id,
        provider="braket",
        backend_name=backend_name,
        status=CloudJobStatus.QUEUED,
        token=token,
        endpoint=endpoint,
        shots=shots,
        circuit_dict=circuit_dict,
        options=options,
    )


def _submit_rigetti(
    circuit_dict: Dict[str, Any],
    backend_name: str,
    shots: int,
    token: str,
    endpoint: str,
    **options: Any,
) -> CloudJob:
    """Submit a circuit to Rigetti QCS via REST API.

    POST /jobs
    """
    base = endpoint.rstrip("/")
    payload: Dict[str, Any] = {
        "target": backend_name,
        "shots": shots,
        "program": circuit_dict,
    }
    if options:
        payload.update(options)
    data = _http_request(
        "POST",
        f"{base}/jobs",
        headers={"Authorization": f"Bearer {token}"},
        body=payload,
    )
    job_id = data.get("id", f"rigetti-{uuid.uuid4().hex[:12]}")
    return CloudJob(
        job_id=job_id,
        provider="rigetti",
        backend_name=backend_name,
        status=CloudJobStatus.QUEUED,
        token=token,
        endpoint=endpoint,
        shots=shots,
        circuit_dict=circuit_dict,
        options=options,
    )


_SUBMIT_FUNCS: Dict[str, Callable[..., CloudJob]] = {
    "ibm": _submit_ibm,
    "ionq": _submit_ionq,
    "braket": _submit_braket,
    "rigetti": _submit_rigetti,
}


# ---------------------------------------------------------------------------
# CloudSession
# ---------------------------------------------------------------------------


class CloudSession:
    """Represents an active connection to a quantum cloud provider.

    Wraps real provider REST APIs for backend discovery, job submission,
    and job listing.

    Parameters
    ----------
    provider:
        Cloud provider identifier (e.g. ``"ibm"``, ``"ionq"``).
    token:
        Authentication token.  If *None* the session will attempt to
        obtain credentials from the linked :class:`AuthManager`.
    endpoint:
        API base URL.  Providers usually supply a sensible default.
    auth_manager:
        Optional :class:`AuthManager` used to resolve credentials.
    **kwargs:
        Extra provider-specific options stored on the session.
    """

    _DEFAULT_ENDPOINTS: Dict[str, str] = {
        "ibm": "https://auth.quantum-computing.ibm.com/api",
        "ionq": "https://api.ionq.co/v0.3",
        "braket": "https://braket.us-east-1.amazonaws.com",
        "rigetti": "https://qpu.rigetti.com/v1",
    }

    def __init__(
        self,
        provider: str,
        token: Optional[str] = None,
        endpoint: Optional[str] = None,
        auth_manager: Optional[AuthManager] = None,
        **kwargs: Any,
    ) -> None:
        self._provider = provider.lower()
        self._token = token
        self._endpoint = endpoint or self._DEFAULT_ENDPOINTS.get(self._provider, "")
        self._auth_manager = auth_manager
        self._session_id = uuid.uuid4().hex
        self._active = False
        self._created_at: Optional[datetime] = None
        self._extra = kwargs
        self._jobs: Dict[str, CloudJob] = {}
        self._backend_adapter = _BACKEND_ADAPTERS.get(self._provider)
        self._submit_fn = _SUBMIT_FUNCS.get(self._provider)

    # -- Properties --------------------------------------------------------

    @property
    def provider(self) -> str:
        """Cloud provider name."""
        return self._provider

    @property
    def token(self) -> Optional[str]:
        """Current authentication token."""
        if self._token is None and self._auth_manager is not None:
            creds = self._auth_manager.get_credentials(self._provider)
            if creds is not None:
                self._token = creds.token or creds.api_key or creds.access_token
        return self._token

    @property
    def endpoint(self) -> str:
        """API base URL for this session."""
        return self._endpoint

    @property
    def is_active(self) -> bool:
        """Whether the session is currently open."""
        return self._active

    @property
    def session_id(self) -> str:
        """Unique identifier for this session."""
        return self._session_id

    # -- Lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Initialize the session with the provider.

        Raises RuntimeError if the session is already active.
        """
        if self._active:
            raise RuntimeError(
                f"Session {self._session_id} is already active for {self._provider!r}"
            )
        if self._token is None and self._auth_manager is not None:
            creds = self._auth_manager.get_credentials(self._provider)
            if creds is None:
                raise ValueError(
                    f"No credentials found for provider {self._provider!r}. "
                    "Call AuthManager.set_credentials() or load_from_env() first."
                )
            self._token = creds.token or creds.api_key or creds.access_token
        if not self._token:
            raise ValueError(
                f"No token provided and no credentials available for {self._provider!r}"
            )
        self._active = True
        self._created_at = datetime.now(timezone.utc)

    def stop(self) -> None:
        """Close the session.

        Raises RuntimeError if the session is not active.
        """
        if not self._active:
            raise RuntimeError(
                f"Session {self._session_id} is not active for {self._provider!r}"
            )
        self._active = False

    # -- Context manager ---------------------------------------------------

    def __enter__(self) -> CloudSession:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._active:
            self.stop()

    # -- Job operations ----------------------------------------------------

    def submit(
        self,
        circuit_dict: Dict[str, Any],
        backend_name: str,
        shots: int = 1024,
        **options: Any,
    ) -> CloudJob:
        """Submit a circuit for execution on a real quantum backend.

        Parameters
        ----------
        circuit_dict:
            JSON-serializable circuit description (gates, qubits, etc.).
        backend_name:
            Target backend identifier.
        shots:
            Number of measurement repetitions.
        **options:
            Additional provider-specific options.

        Returns
        -------
        CloudJob
            A job handle that can be polled for status and results.

        Raises
        ------
        RuntimeError
            If the session is not active or the provider is unsupported.
        """
        if not self._active:
            raise RuntimeError(
                "Session is not active. Call start() or use a context manager."
            )
        if self._submit_fn is None:
            raise RuntimeError(
                f"Unsupported provider for submit: {self._provider!r}"
            )
        if not self._token:
            raise ValueError("No token available — cannot submit job.")

        try:
            job = self._submit_fn(
                circuit_dict,
                backend_name,
                shots,
                self._token,
                self._endpoint,
                **options,
            )
        except (RuntimeError, ConnectionError) as exc:
            raise RuntimeError(
                f"Failed to submit job to {self._provider!r}: {exc}"
            ) from exc

        self._jobs[job.job_id] = job
        logger.info(
            "Submitted job %s to %s/%s", job.job_id, self._provider, backend_name
        )
        return job

    def list_jobs(
        self, status: Optional[CloudJobStatus] = None, limit: int = 20
    ) -> List[CloudJob]:
        """Return jobs submitted through this session.

        Parameters
        ----------
        status:
            If given, only jobs matching this status are returned.
        limit:
            Maximum number of jobs to return.
        """
        jobs = list(self._jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return jobs[:limit]

    def get_job(self, job_id: str) -> CloudJob:
        """Retrieve a job by its identifier.

        Raises KeyError if the job is not known.
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"No job with id {job_id!r} in session {self._session_id}")
        return job

    def cancel_job(self, job_id: str) -> None:
        """Cancel a queued or running job.

        Raises KeyError if the job is not known.
        """
        job = self.get_job(job_id)
        job.cancel()

    def refresh_job(self, job_id: str) -> None:
        """Force-refresh the status of a job from the provider API.

        Raises KeyError if the job is not known.
        """
        job = self.get_job(job_id)
        job.refresh_status()

    def wait_for_job(
        self, job_id: str, timeout: float = 300, poll_interval: float = 2.0
    ) -> CloudJobResult:
        """Wait for a job to complete and return its result.

        Parameters
        ----------
        job_id:
            Job identifier.
        timeout:
            Maximum seconds to wait.
        poll_interval:
            Seconds between status polls.

        Returns
        -------
        CloudJobResult
        """
        job = self.get_job(job_id)
        return job.result(timeout=timeout)

    # -- Backend queries ---------------------------------------------------

    def list_backends(self, status_filter: Optional[str] = None) -> List[dict]:
        """Return available backends for this provider.

        Makes a real API call to the provider to discover available backends.

        Parameters
        ----------
        status_filter:
            Optional filter such as ``"online"`` or ``"available"``.

        Returns
        -------
        list[dict]
            List of backend descriptors as dictionaries.
        """
        if self._backend_adapter is None or not self._token:
            return []
        try:
            backends = self._backend_adapter.list_backends(
                self._token, self._endpoint, status_filter
            )
            return [b.to_dict() for b in backends]
        except (RuntimeError, ConnectionError) as exc:
            logger.warning(
                "Failed to list backends for %s: %s", self._provider, exc
            )
            return []

    def get_backend_properties(self, backend_name: str) -> dict:
        """Return calibration / properties for a specific backend.

        Makes a real API call to the provider for detailed backend info.

        Raises KeyError if the backend is not found.
        """
        if self._backend_adapter is None or not self._token:
            raise KeyError(
                f"Backend {backend_name!r} not found for provider {self._provider!r}"
            )
        try:
            data = self._backend_adapter.get_backend_properties(
                backend_name, self._token, self._endpoint
            )
            data.setdefault("name", backend_name)
            data.setdefault("provider", self._provider)
            return data
        except (RuntimeError, ConnectionError) as exc:
            raise KeyError(
                f"Backend {backend_name!r} not found for provider {self._provider!r}"
            ) from exc

    # -- Dunder ------------------------------------------------------------

    def __repr__(self) -> str:
        state = "active" if self._active else "inactive"
        n_jobs = len(self._jobs)
        return (
            f"CloudSession(provider={self._provider!r}, state={state}, "
            f"jobs={n_jobs}, id={self._session_id!r})"
        )
