"""
UMEROS Cloud Session
=====================
Session management for interacting with quantum cloud backends.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .job import CloudJob, CloudJobStatus

if TYPE_CHECKING:
    from .auth import AuthManager


class CloudSession:
    """Represents an active connection to a quantum cloud provider.

    A session encapsulates authentication state, the target endpoint,
    and convenience methods for submitting jobs and querying backends.

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

    # Default endpoints per provider (can be overridden via *endpoint*).
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
        # Resolve token from auth manager if not provided directly.
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
        """
        if not self._active:
            raise RuntimeError(
                "Session is not active. Call start() or use a context manager."
            )
        job_id = f"{self._provider}-{uuid.uuid4().hex[:12]}"
        job = CloudJob(
            job_id=job_id,
            provider=self._provider,
            backend_name=backend_name,
            status=CloudJobStatus.QUEUED,
            shots=shots,
            circuit_dict=circuit_dict,
            options=options,
        )
        self._jobs[job_id] = job
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

    # -- Backend queries ---------------------------------------------------

    def list_backends(self, status_filter: Optional[str] = None) -> List[dict]:
        """Return available backends for this provider.

        Parameters
        ----------
        status_filter:
            Optional filter such as ``"online"`` or ``"available"``.
        """
        # Stub — real implementation would call the provider API.
        backends: List[dict] = []
        default_backends = {
            "ibm": [
                {"name": "ibmq_manila", "n_qubits": 5, "status": "online"},
                {"name": "ibmq_quito", "n_qubits": 5, "status": "online"},
                {"name": "ibm_lagos", "n_qubits": 7, "status": "online"},
            ],
            "ionq": [
                {"name": "ionq_harmony", "n_qubits": 11, "status": "online"},
                {"name": "ionq_aria-1", "n_qubits": 25, "status": "online"},
            ],
            "braket": [
                {"name": "IonQ_Harmony", "n_qubits": 11, "status": "online"},
                {"name": "Rigetti_Ankaa-3", "n_qubits": 30, "status": "online"},
                {"name": "SV1", "n_qubits": 32, "status": "online"},
            ],
            "rigetti": [
                {"name": "Ankaa-3", "n_qubits": 30, "status": "online"},
            ],
        }
        backends = default_backends.get(self._provider, [])
        if status_filter is not None:
            backends = [b for b in backends if b.get("status") == status_filter]
        return backends

    def get_backend_properties(self, backend_name: str) -> dict:
        """Return calibration / properties for a specific backend.

        Raises KeyError if the backend is not found.
        """
        for backend in self.list_backends():
            if backend["name"] == backend_name:
                return {
                    "name": backend_name,
                    "provider": self._provider,
                    "n_qubits": backend.get("n_qubits"),
                    "status": backend.get("status"),
                    "gate_error_rates": {},
                    "readout_error_rates": {},
                    "t1_times_us": {},
                    "t2_times_us": {},
                }
        raise KeyError(
            f"Backend {backend_name!r} not found for provider {self._provider!r}"
        )

    # -- Dunder ------------------------------------------------------------

    def __repr__(self) -> str:
        state = "active" if self._active else "inactive"
        n_jobs = len(self._jobs)
        return (
            f"CloudSession(provider={self._provider!r}, state={state}, "
            f"jobs={n_jobs}, id={self._session_id!r})"
        )
