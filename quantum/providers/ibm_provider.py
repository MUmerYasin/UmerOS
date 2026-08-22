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
IBM Quantum Provider
====================
Provider integration for IBM Quantum Platform real hardware via REST API.

Connects to IBM Quantum (auth.quantum-computing.ibm.com) for backend
discovery, job submission, result retrieval, and account management.

Example::

    from quantum.providers.ibm_provider import IBMQuantumProvider

    provider = IBMQuantumProvider(token="YOUR_IBM_QUANTUM_API_TOKEN")
    provider.authenticate()

    backends = provider.backends()
    backend = provider.get_backend("ibm_brisbane")

    job = provider.submit_job("ibm_brisbane", circuits=[...], shots=2048)
    result = job.result(timeout=300)
"""

from __future__ import annotations

import json
import time
import logging
from typing import Any, Dict, List, Optional

import requests

from .base import (
    BackendJob,
    BackendProperties,
    BackendProvider,
    BackendStatus,
    BackendTarget,
    BackendTargetCoupling,
    GateSet,
    JobResult,
    JobQueueMode,
)

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://auth.quantum-computing.ibm.com/api"
_DEFAULT_HUB = "ibm-q"
_DEFAULT_GROUP = "open"
_DEFAULT_PROJECT = "main"

_TERMINAL_STATES = {"DONE", "ERROR", "CANCELLED"}
_ACTIVE_STATES = {"QUEUED", "RUNNING", "INITIALIZING", "VALIDATING"}

_STATUS_MAP = {
    "online": BackendStatus.ONLINE,
    "offline": BackendStatus.OFFLINE,
    "maintenance": BackendStatus.MAINTENANCE,
    "active": BackendStatus.ONLINE,
    "closed": BackendStatus.OFFLINE,
    "opening": BackendStatus.MAINTENANCE,
}

_JOB_STATUS_MAP = {
    "QUEUED": "QUEUED",
    "RUNNING": "RUNNING",
    "DONE": "DONE",
    "ERROR": "ERROR",
    "CANCELLED": "CANCELLED",
    "INITIALIZING": "QUEUED",
    "VALIDATING": "QUEUED",
}


class IBMQuantumError(Exception):
    """Base exception for IBM Quantum provider errors."""


class IBMAuthenticationError(IBMQuantumError):
    """Raised when authentication fails."""


class IBMRatelimitError(IBMQuantumError):
    """Raised when the API rate limit is exceeded."""


class IBMBackendNotFoundError(IBMQuantumError):
    """Raised when a requested backend does not exist."""


class IBMJobError(IBMQuantumError):
    """Raised when a job operation fails."""

class IBMQuantumJob(BackendJob):
    """Represents a job submitted to IBM Quantum hardware.

    Wraps the IBM Quantum REST API to track job status, retrieve results,
    cancel jobs, and download raw output.
    """

    def __init__(
        self,
        job_id: str,
        backend_name: str,
        provider: "IBMQuantumProvider",
        hub: str = _DEFAULT_HUB,
        group: str = _DEFAULT_GROUP,
        project: str = _DEFAULT_PROJECT,
        **kwargs: Any,
    ) -> None:
        super().__init__(job_id=job_id, backend_name=backend_name)
        self._provider = provider
        self._hub = hub
        self._group = group
        self._project = project
        self._status: str = kwargs.get("status", "QUEUED")
        self._queue_position: Optional[int] = kwargs.get("queue_position")
        self._progress: float = kwargs.get("progress", 0.0)
        self._tags: List[str] = list(kwargs.get("tags", []))
        self._usage: Dict[str, Any] = kwargs.get("usage", {})
        self._session_id: Optional[str] = kwargs.get("session_id")
        self._created_at: Optional[str] = kwargs.get("created_at")
        self._result: Optional[JobResult] = None
        self._raw_response: Optional[Dict[str, Any]] = None

    @property
    def status(self) -> str:
        """Current job status (QUEUED, RUNNING, DONE, ERROR, CANCELLED)."""
        return _JOB_STATUS_MAP.get(self._status, self._status)

    @property
    def queue_position(self) -> Optional[int]:
        """Position in the execution queue, or None."""
        return self._queue_position

    @property
    def progress(self) -> float:
        """Estimated progress between 0.0 and 1.0."""
        return self._progress

    @property
    def tags(self) -> List[str]:
        """User-defined tags attached to this job."""
        return list(self._tags)

    @property
    def usage(self) -> Dict[str, Any]:
        """Resource usage statistics (seconds, credits, etc.)."""
        return dict(self._usage)

    @property
    def session_id(self) -> Optional[str]:
        """IBM Quantum Runtime session identifier, if applicable."""
        return self._session_id

    def refresh_status(self) -> str:
        """Poll the IBM Quantum API for the latest job status.

        Returns:
            Updated status string.
        Raises:
            IBMQuantumError: If the API request fails.
        """
        url = self._job_url()
        try:
            resp = self._provider._api_get(url)
        except requests.RequestException as exc:
            raise IBMQuantumError(f"Failed to refresh job status: {exc}") from exc

        self._raw_response = resp
        self._status = resp.get("status", self._status)
        self._queue_position = resp.get("position")
        self._tags = list(resp.get("tags", []))
        self._session_id = resp.get("session_id")

        if "usage" in resp:
            self._usage = resp["usage"]

        if self._status in _TERMINAL_STATES:
            self._progress = 1.0
        elif self._status == "RUNNING":
            self._progress = max(self._progress, 0.5)
        elif self._status == "QUEUED":
            self._progress = 0.0

        return self.status

    def result(self, timeout: Optional[float] = None) -> JobResult:
        """Wait for job completion and return the result.

        Args:
            timeout: Maximum seconds to wait. None means wait indefinitely.
        Returns:
            The completed JobResult.
        Raises:
            TimeoutError: If the job does not finish within timeout.
            IBMJobError: If the job ended in error or was cancelled.
        """
        self.wait_for_completion(timeout=timeout)

        if self._result is not None:
            return self._result

        if self._status == "ERROR":
            raise IBMJobError(f"Job failed: {self.status_detail()}")

        if self._status == "CANCELLED":
            raise IBMJobError(f"Job {self._job_id} was cancelled.")

        return self._download_and_parse_result()

    def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """Block until the job reaches a terminal state.

        Args:
            timeout: Maximum seconds to wait. None means wait indefinitely.
        Raises:
            TimeoutError: If the job does not finish within timeout.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        poll_interval = 2.0

        while True:
            self.refresh_status()

            if self._status in _TERMINAL_STATES:
                return

            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {self._job_id} did not complete within {timeout}s "
                    f"(last status: {self._status})"
                )

            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 30.0)

    def cancel(self) -> None:
        """Cancel a queued or running job.

        Raises:
            IBMJobError: If cancellation fails.
        """
        url = self._job_url()
        try:
            self._provider._api_delete(url)
            self._status = "CANCELLED"
        except requests.RequestException as exc:
            raise IBMJobError(f"Failed to cancel job {self._job_id}: {exc}") from exc

    def download_result(self) -> Dict[str, Any]:
        """Download the raw result payload from IBM Quantum.

        Returns:
            Parsed JSON result dictionary.
        Raises:
            IBMJobError: If the download fails.
        """
        return self._download_and_parse_result()

    def share(self) -> str:
        """Make the job result publicly accessible.

        Returns:
            A public URL for the result.
        Raises:
            IBMJobError: If sharing fails.
        """
        url = f"{self._job_url()}/share"
        try:
            resp = self._provider._api_post(url, body={})
            public_url = resp.get("share_url", "") or resp.get("url", "")
            return public_url
        except requests.RequestException as exc:
            raise IBMJobError(f"Failed to share job {self._job_id}: {exc}") from exc

    def status_detail(self) -> str:
        """Return a human-readable detailed status string."""
        parts = [
            f"Job {self._job_id}",
            f"backend={self._backend_name}",
            f"status={self._status}",
        ]
        if self._queue_position is not None:
            parts.append(f"queue_pos={self._queue_position}")
        if self._session_id:
            parts.append(f"session={self._session_id}")
        if self._usage:
            parts.append(f"usage={self._usage}")
        return " | ".join(parts)

    def _base_url(self) -> str:
        return (
            f"{self._provider._api_url}/Network/{self._hub}"
            f"/Groups/{self._group}/Projects/{self._project}"
        )

    def _job_url(self) -> str:
        return f"{self._base_url()}/jobs/{self._job_id}"

    def _download_and_parse_result(self) -> JobResult:
        """Fetch the result download URL, retrieve, and parse the result."""
        result_url_endpoint = f"{self._job_url()}/resultDownloadUrl"
        try:
            dl_resp = self._provider._api_get(result_url_endpoint)
            download_url = dl_resp.get("url", "")

            if not download_url:
                raise IBMJobError(f"No download URL for job {self._job_id}")

            dl_session = requests.Session()
            file_resp = dl_session.get(download_url, timeout=60)
            file_resp.raise_for_status()

            result_data = file_resp.json()
            return JobResult(
                job_id=self._job_id,
                backend_name=self._backend_name,
                data=result_data.get("data", {}),
                counts=result_data.get("counts", {}),
                metadata=result_data.get("metadata", {}),
                success=result_data.get("success", True),
            )
        except requests.RequestException as exc:
            raise IBMJobError(f"Failed to download result: {exc}") from exc


class IBMQuantumProvider(BackendProvider):
    """Provider for IBM Quantum Platform real hardware.

    Manages authentication, backend discovery, job submission, and account
    operations against the IBM Quantum REST API.

    Args:
        token: IBM Quantum API token. Falls back to UMEROS_IBM_TOKEN env var.
        api_url: Base URL for the IBM Quantum API.
        hub: IBM Quantum hub name.
        group: IBM Quantum group name.
        project: IBM Quantum project name.
        **kwargs: Additional configuration (e.g. timeout, max_retries).
    """

    def __init__(
        self,
        token: Optional[str] = None,
        api_url: str = _DEFAULT_API_URL,
        hub: str = _DEFAULT_HUB,
        group: str = _DEFAULT_GROUP,
        project: str = _DEFAULT_PROJECT,
        **kwargs: Any,
    ) -> None:
        import os

        self._token = token or os.environ.get("UMEROS_IBM_TOKEN")
        self._api_url = api_url.rstrip("/")
        self._hub = hub
        self._group = group
        self._project = project
        self._timeout = kwargs.get("timeout", 30)
        self._max_retries = kwargs.get("max_retries", 3)
        self._authenticated = False
        self._session: Optional[requests.Session] = None
        self._backends_cache: List[BackendTarget] = []
        self._backends_cache_ts: float = 0.0

    # -- BackendProvider interface --------------------------------------------

    def authenticate(self) -> None:
        """Authenticate with IBM Quantum using the API token.

        Validates the token and populates an internal session with auth headers.

        Raises:
            IBMAuthenticationError: If authentication fails.
        """
        if not self._token:
            raise IBMAuthenticationError(
                "No IBM Quantum API token provided. Pass token= or set "
                "the UMEROS_IBM_TOKEN environment variable."
            )

        self._session = requests.Session()
        self._session.headers.update({
            "X-Access-Token": self._token,
            "Content-Type": "application/json",
        })

        url = f"{self._api_url}/users/loginWithToken"
        try:
            resp = self._session.post(
                url,
                json={"apiToken": self._token},
                timeout=self._timeout,
            )
            self._handle_response(resp)
            data = resp.json()
            self._session.headers["Access-Token"] = data.get("id", "")
            self._authenticated = True
            logger.info("IBM Quantum authentication successful.")
        except requests.RequestException as exc:
            raise IBMAuthenticationError(
                f"IBM Quantum authentication failed: {exc}"
            ) from exc

    def is_authenticated(self) -> bool:
        """Return True if the provider has a valid active session."""
        return self._authenticated and self._session is not None

    def backends(self, refresh: bool = False) -> List[BackendTarget]:
        """Return a list of available IBM Quantum backends.

        Args:
            refresh: Force a fresh API call even if cache is still valid.

        Returns:
            List of BackendTarget objects.
        """
        now = time.time()
        if (
            not refresh
            and self._backends_cache
            and (now - self._backends_cache_ts) < 300
        ):
            return list(self._backends_cache)

        url = f"{self._api_url}/Network/{self._hub}/Groups/{self._group}/Projects/{self._project}/devices/v2"
        try:
            resp = self._api_get(url)
        except requests.RequestException as exc:
            raise IBMQuantumError(f"Failed to list backends: {exc}") from exc

        backends = []
        for dev in resp.get("devices", resp.get("backends", [])):
            name = dev.get("name", "")
            if not name:
                continue

            backend_status_str = dev.get("status", "offline")
            backend_status = _STATUS_MAP.get(backend_status_str, BackendStatus.OFFLINE)

            n_qubits = dev.get("n_qubits", dev.get("num_qubits", 0))
            coupling_map = self._parse_coupling_map(dev.get("coupling_map", []))
            gate_set = self._parse_gate_set(dev.get("gate_set", []))

            props = BackendProperties(
                backend_name=name,
                backend_version=dev.get("backend_version", "unknown"),
                n_qubits=n_qubits,
                operational=backend_status == BackendStatus.ONLINE,
                pending_jobs=dev.get("pending_jobs", 0),
                status_msg=dev.get("status_msg", ""),
            )

            target = BackendTarget(
                backend_name=name,
                backend_type="simulator" if "simulator" in name else "hardware",
                n_qubits=n_qubits,
                status=backend_status,
                properties=props,
                coupling_map=coupling_map,
                gate_set=gate_set,
                provider=self,
                provider_metadata={
                    "hub": self._hub,
                    "group": self._group,
                    "project": self._project,
                    "max_shots": dev.get("max_shots", 8192),
                    "max_experiments": dev.get("max_experiments", 75),
                },
            )
            backends.append(target)

        self._backends_cache = backends
        self._backends_cache_ts = time.time()
        logger.info("Discovered %d IBM Quantum backends.", len(backends))
        return list(backends)

    def get_backend(self, backend_name: str) -> BackendTarget:
        """Return a specific backend by name.

        Args:
            backend_name: Name of the backend (e.g. 'ibm_brisbane').

        Returns:
            The matching BackendTarget.

        Raises:
            IBMBackendNotFoundError: If no backend matches.
        """
        for backend in self.backends():
            if backend.backend_name == backend_name:
                return backend
        raise IBMBackendNotFoundError(
            f"Backend '{backend_name}' not found. "
            f"Available: {[b.backend_name for b in self.backends()]}"
        )

    def get_backend_properties(self, backend_name: str) -> BackendProperties:
        """Fetch detailed properties for a specific backend.

        Args:
            backend_name: Name of the backend.

        Returns:
            BackendProperties with detailed hardware info.
        """
        url = (
            f"{self._api_url}/Network/{self._hub}/Groups/{self._group}"
            f"/Projects/{self._project}/devices/v2/{backend_name}/properties"
        )
        try:
            data = self._api_get(url)
        except requests.RequestException as exc:
            raise IBMQuantumError(
                f"Failed to get properties for {backend_name}: {exc}"
            ) from exc

        return BackendProperties(
            backend_name=backend_name,
            backend_version=data.get("backend_version", "unknown"),
            n_qubits=data.get("n_qubits", 0),
            operational=data.get("operational", False),
            pending_jobs=data.get("pending_jobs", 0),
            status_msg=data.get("status_msg", ""),
            extra=data.get("general", {}),
        )

    def get_backend_status(self, backend_name: str) -> BackendStatus:
        """Fetch the current status of a specific backend.

        Args:
            backend_name: Name of the backend.

        Returns:
            BackendStatus enum value.
        """
        url = (
            f"{self._api_url}/Network/{self._hub}/Groups/{self._group}"
            f"/Projects/{self._project}/devices/v2/{backend_name}/status"
        )
        try:
            data = self._api_get(url)
        except requests.RequestException as exc:
            raise IBMQuantumError(
                f"Failed to get status for {backend_name}: {exc}"
            ) from exc

        raw_status = data.get("status", "offline")
        return _STATUS_MAP.get(raw_status, BackendStatus.OFFLINE)

    def submit_job(
        self,
        backend_name: str,
        circuits: List[Dict[str, Any]],
        shots: int = 2048,
        tags: Optional[List[str]] = None,
        **options: Any,
    ) -> IBMQuantumJob:
        """Submit a job to an IBM Quantum backend.

        Args:
            backend_name: Target backend name.
            circuits: List of circuit dictionaries (QASM JSON format).
            shots: Number of measurement shots per circuit.
            tags: Optional list of user-defined tags.
            **options: Additional options (hpcs, memory, optimization_level, etc.).

        Returns:
            IBMQuantumJob instance for tracking.

        Raises:
            IBMJobError: If the job submission fails.
        """
        url = (
            f"{self._api_url}/Network/{self._hub}/Groups/{self._group}"
            f"/Projects/{self._project}/Jobs"
        )

        payload: Dict[str, Any] = {
            "backend": backend_name,
            "circuits": circuits,
            "shots": shots,
        }

        if tags:
            payload["tags"] = tags

        if "hpcs" in options:
            payload["hpcs"] = options["hpcs"]
        if "memory" in options:
            payload["memory"] = options["memory"]
        if "optimization_level" in options:
            payload["optimization_level"] = options["optimization_level"]
        if "seed_simulator" in options:
            payload["seed_simulator"] = options["seed_simulator"]
        if "qobj_id" in options:
            payload["qobj_id"] = options["qobj_id"]
        if "init_qubits" in options:
            payload["init_qubits"] = options["init_qubits"]
        if "rep_delay" in options:
            payload["rep_delay"] = options["rep_delay"]
        if "job_tags" in options:
            payload["tags"] = options["job_tags"]
        if "scheduling_mode" in options:
            payload["scheduling_mode"] = options["scheduling_mode"]

        try:
            resp = self._api_post(url, body=payload)
        except requests.RequestException as exc:
            raise IBMJobError(f"Failed to submit job: {exc}") from exc

        job_id = resp.get("id", resp.get("job_id", ""))
        status = resp.get("status", "QUEUED")

        logger.info("Job %s submitted to %s (status: %s)", job_id, backend_name, status)

        return IBMQuantumJob(
            job_id=job_id,
            backend_name=backend_name,
            provider=self,
            hub=self._hub,
            group=self._group,
            project=self._project,
            status=status,
            queue_position=resp.get("position"),
            tags=list(resp.get("tags", [])),
            usage=resp.get("usage", {}),
            session_id=resp.get("session_id"),
            created_at=resp.get("created_at"),
        )

    def get_job(self, job_id: str, backend_name: str = "") -> IBMQuantumJob:
        """Retrieve an existing job by ID.

        Args:
            job_id: IBM Quantum job identifier.
            backend_name: Optional backend name for context.

        Returns:
            IBMQuantumJob with current state.
        """
        url = (
            f"{self._api_url}/Network/{self._hub}/Groups/{self._group}"
            f"/Projects/{self._project}/jobs/{job_id}"
        )
        try:
            resp = self._api_get(url)
        except requests.RequestException as exc:
            raise IBMJobError(f"Failed to get job {job_id}: {exc}") from exc

        resolved_backend = backend_name or resp.get("backend", {}).get("name", "unknown")

        return IBMQuantumJob(
            job_id=job_id,
            backend_name=resolved_backend,
            provider=self,
            hub=self._hub,
            group=self._group,
            project=self._project,
            status=resp.get("status", "UNKNOWN"),
            queue_position=resp.get("position"),
            tags=list(resp.get("tags", [])),
            usage=resp.get("usage", {}),
            session_id=resp.get("session_id"),
            created_at=resp.get("created_at"),
        )

    def my_reservations(self) -> List[Dict[str, Any]]:
        """Fetch the list of active device reservations for this account.

        Returns:
            List of reservation dictionaries with id, backend, start, end, status.
        """
        url = (
            f"{self._api_url}/Network/{self._hub}/Groups/{self._group}"
            f"/Projects/{self._project}/reservations"
        )
        try:
            data = self._api_get(url)
        except requests.RequestException as exc:
            raise IBMQuantumError(f"Failed to fetch reservations: {exc}") from exc

        if isinstance(data, dict):
            return data.get("reservations", data.get("data", []))
        return data if isinstance(data, list) else []

    def account_usage(self) -> Dict[str, Any]:
        """Fetch current account usage and quota information.

        Returns:
            Dictionary with usage stats (seconds, jobs, credits, etc.).
        """
        url = (
            f"{self._api_url}/Network/{self._hub}/Groups/{self._group}"
            f"/Projects/{self._project}/usage"
        )
        try:
            data = self._api_get(url)
        except requests.RequestException as exc:
            raise IBMQuantumError(f"Failed to fetch account usage: {exc}") from exc

        return data

    def program_run(
        self,
        program_id: str,
        backend_name: str,
        inputs: Dict[str, Any],
        **options: Any,
    ) -> IBMQuantumJob:
        """Run an IBM Quantum Runtime program.

        Args:
            program_id: Runtime program identifier (e.g. 'circuit-runner').
            backend_name: Target backend name.
            inputs: Program input parameters.
            **options: Runtime options (iterations, callback, etc.).

        Returns:
            IBMQuantumJob for tracking.
        """
        url = (
            f"{self._api_url}/Network/{self._hub}/Groups/{self._group}"
            f"/Projects/{self._project}/programs/{program_id}/jobs"
        )

        payload: Dict[str, Any] = {
            "backend": backend_name,
            "params": inputs,
        }

        if "iterations" in options:
            payload["iterations"] = options["iterations"]
        if "callback" in options:
            payload["callback"] = options["callback"]

        try:
            resp = self._api_post(url, body=payload)
        except requests.RequestException as exc:
            raise IBMJobError(f"Failed to run program {program_id}: {exc}") from exc

        job_id = resp.get("id", resp.get("job_id", ""))

        logger.info("Runtime program %s job %s submitted.", program_id, job_id)

        return IBMQuantumJob(
            job_id=job_id,
            backend_name=backend_name,
            provider=self,
            hub=self._hub,
            group=self._group,
            project=self._project,
            status=resp.get("status", "QUEUED"),
            tags=list(resp.get("tags", [])),
            session_id=resp.get("session_id"),
        )

    # -- HTTP helpers --------------------------------------------------------

    def _api_get(self, url: str) -> Dict[str, Any]:
        """Send an authenticated GET request with retry logic."""
        return self._api_request("GET", url)

    def _api_post(self, url: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Send an authenticated POST request with retry logic."""
        return self._api_request("POST", url, json_body=body)

    def _api_delete(self, url: str) -> Dict[str, Any]:
        """Send an authenticated DELETE request with retry logic."""
        return self._api_request("DELETE", url)

    def _api_request(
        self,
        method: str,
        url: str,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute an HTTP request with retry and error handling.

        Retries on transient failures (502, 503, 504) up to max_retries times.

        Returns:
            Parsed JSON response body.
        Raises:
            IBMAuthenticationError: On 401/403 responses.
            IBMRatelimitError: On 429 responses.
            IBMQuantumError: On other HTTP errors or retries exhausted.
        """
        if not self._session:
            self._session = requests.Session()
            if self._token:
                self._session.headers["X-Access-Token"] = self._token
                self._session.headers["Content-Type"] = "application/json"

        last_exc: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                if method == "GET":
                    resp = self._session.get(url, timeout=self._timeout)
                elif method == "POST":
                    resp = self._session.post(url, json=json_body, timeout=self._timeout)
                elif method == "DELETE":
                    resp = self._session.delete(url, timeout=self._timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                if resp.status_code in (401, 403):
                    raise IBMAuthenticationError(
                        f"Authentication failed ({resp.status_code}): "
                        f"{resp.text[:200]}"
                    )

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "5")
                    try:
                        wait = int(retry_after)
                    except (ValueError, TypeError):
                        wait = 5
                    logger.warning("Rate limited, waiting %ds (attempt %d).", wait, attempt)
                    time.sleep(wait)
                    continue

                if resp.status_code in (502, 503, 504):
                    logger.warning(
                        "Transient error %d on attempt %d, retrying...",
                        resp.status_code,
                        attempt,
                    )
                    time.sleep(min(2 ** attempt, 30))
                    continue

                resp.raise_for_status()

                if resp.status_code == 204 or not resp.content:
                    return {}

                return resp.json()

            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                logger.warning("Request failed (attempt %d): %s", attempt, exc)
                time.sleep(min(2 ** attempt, 30))
                continue

        raise IBMQuantumError(
            f"Request failed after {self._max_retries} attempts: {last_exc}"
        )

    def _handle_response(self, resp: requests.Response) -> None:
        """Check a response object for auth or server errors."""
        if resp.status_code in (401, 403):
            raise IBMAuthenticationError(
                f"Authentication failed ({resp.status_code}): {resp.text[:200]}"
            )
        if resp.status_code == 429:
            raise IBMRatelimitError(
                f"Rate limit exceeded: {resp.text[:200]}"
            )
        resp.raise_for_status()

    @staticmethod
    def _parse_coupling_map(raw: Any) -> List[BackendTargetCoupling]:
        """Convert raw coupling data into BackendTargetCoupling objects."""
        if not raw:
            return []

        if isinstance(raw, list) and raw and isinstance(raw[0], list):
            couplings = []
            for pair in raw:
                if len(pair) >= 2:
                    couplings.append(
                        BackendTargetCoupling(
                            qubit_from=int(pair[0]),
                            qubit_to=int(pair[1]),
                        )
                    )
            return couplings

        if isinstance(raw, dict):
            couplings = []
            for qubit_str, neighbors in raw.items():
                qubit_from = int(qubit_str)
                for neighbor in neighbors:
                    couplings.append(
                        BackendTargetCoupling(
                            qubit_from=qubit_from,
                            qubit_to=int(neighbor),
                        )
                    )
            return couplings

        return []

    @staticmethod
    def _parse_gate_set(raw: Any) -> GateSet:
        """Convert raw gate set data into a GateSet object."""
        if not raw:
            return GateSet()

        gate_names: List[str] = []
        if isinstance(raw, list):
            gate_names = [str(g) for g in raw]
        elif isinstance(raw, dict):
            gate_names = list(raw.keys())

        return GateSet(
            gates=gate_names,
            measure=any("measure" in g.lower() for g in gate_names),
            barrier=any("barrier" in g.lower() for g in gate_names),
        )


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def IBMQuantumBackend(
    backend_name: str,
    provider: IBMQuantumProvider,
) -> BackendTarget:
    """Factory function to get a configured BackendTarget for the given backend.

    This is a convenience wrapper around provider.get_backend().

    Args:
        backend_name: Name of the IBM Quantum backend.
        provider: An authenticated IBMQuantumProvider instance.

    Returns:
        Configured BackendTarget.

    Raises:
        IBMBackendNotFoundError: If the backend does not exist.
    """
    return provider.get_backend(backend_name)
