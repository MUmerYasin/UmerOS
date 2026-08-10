"""
UMEROS IonQ Provider Module
============================
Provider integration for IonQ quantum computers via their REST API (v0.3).

IonQ uses a trapped-ion architecture with all-to-all qubit connectivity,
native gates including GPI, GPI2, and MS (Molmer-Sorensen), and supports
both simulator and real hardware targets.

Reference: https://docs.ionq.com/
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import (
    BackendJob,
    BackendProperties,
    BackendProvider,
    BackendStatus,
    BackendTarget,
    BackendTargetCoupling,
    GateSet,
    JobResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IonQ API constants
# ---------------------------------------------------------------------------

IONQ_DEFAULT_URL = "https://api.ionq.co/v0.3"
IONQ_DEFAULT_SHOTS = 1024
IONQ_MAX_SHOTS = 1_000_000

# IonQ native gates (trapped-ion architecture)
IONQ_NATIVE_GATES = ["GPI", "GPI2", "MS"]
IONQ_BASIS_GATES = ["GPI", "GPI2", "MS", "I", "Z", "X", "H", "CNOT", "CZ"]

# Map IonQ API status strings to our BackendStatus enum
_IONQ_BACKEND_STATUS_MAP: Dict[str, BackendStatus] = {
    "online": BackendStatus.ONLINE,
    "available": BackendStatus.ONLINE,
    "offline": BackendStatus.OFFLINE,
    "unavailable": BackendStatus.OFFLINE,
    "maintenance": BackendStatus.MAINTENANCE,
    "paused": BackendStatus.QUEUE_PAUSED,
    "error": BackendStatus.ERROR,
}

# Map IonQ API job status to canonical status strings
_IONQ_JOB_STATUS_MAP: Dict[str, str] = {
    "pending": "QUEUED",
    "queued": "QUEUED",
    "running": "RUNNING",
    "completed": "DONE",
    "canceled": "CANCELLED",
    "cancelled": "CANCELLED",
    "failed": "ERROR",
    "error": "ERROR",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class IonQError(Exception):
    """Base exception for IonQ provider errors."""


class IonQAuthenticationError(IonQError):
    """Raised when API key is invalid or missing."""


class IonQAPIError(IonQError):
    """Raised when the IonQ API returns an error response."""

    def __init__(self, status_code: int, message: str, response_body: Any = None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"IonQ API error {status_code}: {message}")


class IonQJobError(IonQError):
    """Raised when a job fails or cannot be retrieved."""


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only, no ``requests`` dependency)
# ---------------------------------------------------------------------------


def _http_request(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[bytes] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Perform an HTTP request and return parsed JSON.

    Args:
        url: Full URL to request.
        method: HTTP method (GET, POST, DELETE, etc.).
        headers: Optional request headers.
        body: Optional request body (bytes).
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response body.

    Raises:
        IonQAuthenticationError: On 401/403 responses.
        IonQAPIError: On any non-2xx response.
    """
    if headers is None:
        headers = {}

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8") if exc.fp else ""
        try:
            parsed = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw_body}

        message = parsed.get("error", parsed.get("message", raw_body or str(exc)))
        status = exc.code

        if status in (401, 403):
            raise IonQAuthenticationError(
                f"Authentication failed (HTTP {status}): {message}"
            ) from exc

        raise IonQAPIError(status, str(message), response_body=parsed) from exc
    except urllib.error.URLError as exc:
        raise IonQError(f"Network error reaching IonQ API: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# IonQJob
# ---------------------------------------------------------------------------


class IonQJob(BackendJob):
    """Represents a job submitted to IonQ hardware or simulator.

    Wraps the IonQ Jobs API to provide status polling, result retrieval,
    cost tracking, and cancellation.

    Args:
        job_id: IonQ-assigned job identifier.
        backend_name: Name of the backend the job was submitted to.
        provider: The IonQProvider instance used for API calls.
        api_url: IonQ API base URL.
        api_key: IonQ API key.
    """

    def __init__(
        self,
        job_id: str,
        backend_name: str,
        provider: "IonQProvider",
        *,
        api_url: str = IONQ_DEFAULT_URL,
        api_key: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(job_id, backend_name)
        self._provider = provider
        self._api_url = api_url
        self._api_key = api_key
        self._status: str = kwargs.get("status", "QUEUED")
        self._queue_position: Optional[int] = kwargs.get("queue_position")
        self._probabilities: Optional[Dict[str, float]] = kwargs.get("probabilities")
        self._raw_data: Optional[Dict[str, Any]] = kwargs.get("raw_data")
        self._cost: Optional[float] = kwargs.get("cost")
        self._execution_time: Optional[float] = kwargs.get("execution_time")
        self._result_cache: Optional[JobResult] = None

    # -- Properties --------------------------------------------------------

    @property
    def status(self) -> str:
        """Current job status (QUEUED, RUNNING, DONE, ERROR, CANCELLED)."""
        return self._status

    @property
    def queue_position(self) -> Optional[int]:
        """Position in the execution queue, or None if not queued."""
        return self._queue_position

    @property
    def probabilities(self) -> Optional[Dict[str, float]]:
        """Measurement outcome probabilities (populated after completion)."""
        return self._probabilities

    @property
    def raw_data(self) -> Optional[Dict[str, Any]]:
        """Raw JSON response from the IonQ API."""
        return self._raw_data

    @property
    def cost(self) -> Optional[float]:
        """Estimated or actual cost of this job in USD."""
        return self._cost

    @property
    def execution_time(self) -> Optional[float]:
        """Actual execution time in seconds, or None if not yet completed."""
        return self._execution_time

    # -- API interaction ---------------------------------------------------

    def _api_headers(self) -> Dict[str, str]:
        """Return standard headers for IonQ API requests."""
        return {
            "Authorization": f"apiKey {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def refresh_status(self) -> str:
        """Poll the IonQ API for the latest job status.

        Updates internal state and returns the current status string.

        Returns:
            Updated status string (QUEUED, RUNNING, DONE, ERROR, CANCELLED).
        """
        url = f"{self._api_url}/jobs/{self._job_id}"
        data = _http_request(url, headers=self._api_headers())

        self._raw_data = data
        self._status = _IONQ_JOB_STATUS_MAP.get(
            data.get("status", "").lower(), data.get("status", "UNKNOWN")
        )
        self._queue_position = data.get("queue_position")

        # Extract cost and timing when available
        if "cost" in data:
            self._cost = float(data["cost"])
        if "execution_time" in data:
            self._execution_time = float(data["execution_time"])

        # Extract probabilities from results
        if self._status == "DONE" and "result" in data:
            result_data = data["result"]
            if isinstance(result_data, dict):
                self._probabilities = result_data.get("probabilities")
                self._execution_time = result_data.get(
                    "execution_time", self._execution_time
                )

        return self._status

    def result(self, timeout: Optional[float] = None) -> JobResult:
        """Block until the job completes and return the result.

        Args:
            timeout: Maximum seconds to wait. None means wait indefinitely.

        Returns:
            A JobResult containing counts, probabilities, and metadata.

        Raises:
            TimeoutError: If the job does not complete within timeout.
            IonQJobError: If the job failed or was cancelled.
        """
        if self._result_cache is not None and self._status == "DONE":
            return self._result_cache

        self.wait_for_completion(timeout=timeout)

        if self._status == "CANCELLED":
            raise IonQJobError(f"Job {self._job_id} was cancelled")
        if self._status == "ERROR":
            error_msg = ""
            if self._raw_data and "error" in self._raw_data:
                error_msg = str(self._raw_data["error"])
            raise IonQJobError(
                f"Job {self._job_id} failed: {error_msg or 'unknown error'}"
            )

        # Fetch full result from API
        url = f"{self._api_url}/jobs/{self._job_id}"
        data = _http_request(url, headers=self._api_headers())

        result_data = data.get("result", {})
        probabilities = result_data.get("probabilities", {})

        # Convert probabilities to counts based on shots
        shots = data.get("shots", IONQ_DEFAULT_SHOTS)
        counts: Dict[str, int] = {}
        for bitstring, prob in probabilities.items():
            counts[bitstring] = round(prob * shots)

        results_list = [
            {
                "counts": counts,
                "probabilities": probabilities,
                "metadata": {
                    "shots": shots,
                    "backend": self._backend_name,
                    "execution_time": result_data.get("execution_time"),
                    "queue_time": result_data.get("queue_time"),
                },
            }
        ]

        metadata = {
            "job_id": self._job_id,
            "backend": self._backend_name,
            "shots": shots,
            "cost": self._cost,
            "execution_time": self._execution_time,
        }

        job_result = JobResult(
            job_id=self._job_id,
            backend_name=self._backend_name,
            status=self._status,
            results=results_list,
            metadata=metadata,
            error_message=data.get("error"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
        )

        self._result_cache = job_result
        return job_result

    def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """Block until the job reaches a terminal state.

        Args:
            timeout: Maximum seconds to wait. None means wait indefinitely.

        Raises:
            TimeoutError: If the job does not complete within timeout.
        """
        terminal_states = {"DONE", "ERROR", "CANCELLED"}
        start = time.monotonic()

        while True:
            self.refresh_status()
            if self._status in terminal_states:
                return

            if timeout is not None:
                elapsed = time.monotonic() - start
                if elapsed >= timeout:
                    raise TimeoutError(
                        f"Job {self._job_id} did not complete within {timeout}s "
                        f"(current status: {self._status})"
                    )

            # Poll interval: 1s for first 60s, then 5s to be polite
            elapsed = time.monotonic() - start
            sleep_time = 1.0 if elapsed < 60 else 5.0
            time.sleep(sleep_time)

    def cancel(self) -> None:
        """Cancel the running or queued job.

        Raises:
            IonQAPIError: If the API rejects the cancellation request.
        """
        url = f"{self._api_url}/jobs/{self._job_id}"
        req = urllib.request.Request(
            url, headers=self._api_headers(), method="DELETE"
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                # Success — 200 or 204
                self._status = "CANCELLED"
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8") if exc.fp else ""
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {}
            message = parsed.get("error", parsed.get("message", raw or str(exc)))
            raise IonQAPIError(exc.code, str(message), response_body=parsed) from exc

    def download_result(self) -> Dict[str, Any]:
        """Download the raw JSON result from the IonQ API.

        Returns:
            Raw JSON response dict.

        Raises:
            IonQAPIError: If the API request fails.
        """
        url = f"{self._api_url}/jobs/{self._job_id}"
        data = _http_request(url, headers=self._api_headers())
        self._raw_data = data
        return data

    def status_detail(self) -> str:
        """Return a human-readable status detail string."""
        detail = (
            f"IonQ Job {self._job_id} | backend={self._backend_name} | "
            f"status={self._status}"
        )
        if self._queue_position is not None:
            detail += f" | queue_position={self._queue_position}"
        if self._cost is not None:
            detail += f" | cost=${self._cost:.4f}"
        if self._execution_time is not None:
            detail += f" | execution_time={self._execution_time:.2f}s"
        return detail

    def __repr__(self) -> str:
        return (
            f"IonQJob(job_id={self._job_id!r}, "
            f"backend_name={self._backend_name!r}, "
            f"status={self._status!r})"
        )


# ---------------------------------------------------------------------------
# IonQProvider
# ---------------------------------------------------------------------------


class IonQProvider(BackendProvider):
    """Provider for IonQ trapped-ion quantum computers.

    Manages authentication, backend discovery, job submission, and account
    operations through the IonQ REST API (v0.3).

    Args:
        api_key: IonQ API key. If not provided, falls back to ``token`` kwarg
            or the ``IONQ_API_KEY`` environment variable.
        api_url: Base URL for the IonQ API.
        **kwargs: Additional provider-specific configuration passed to the
            ``BackendProvider`` base class.

    Example::

        provider = IonQProvider(api_key="your-api-key")
        backend = provider.get_backend("simulator")
        job = provider.submit_job("simulator", circuits, shots=1024)
        result = job.result()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = IONQ_DEFAULT_URL,
        **kwargs: Any,
    ) -> None:
        import os

        resolved_key = api_key or kwargs.pop("token", None) or os.environ.get("IONQ_API_KEY", "")
        super().__init__(token=resolved_key, **kwargs)
        self._api_key = resolved_key
        self._api_url = api_url.rstrip("/")
        self._backends_cache: Dict[str, BackendTarget] = {}

    # -- Properties --------------------------------------------------------

    @property
    def name(self) -> str:
        """Canonical provider name."""
        return "ionq"

    @property
    def version(self) -> str:
        """API version string."""
        return "0.3"

    # -- Internal helpers --------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        """Return standard headers for IonQ API requests."""
        return {
            "Authorization": f"apiKey {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _parse_backend(data: Dict[str, Any]) -> BackendTarget:
        """Convert an IonQ API backend response into a BackendTarget.

        Args:
            data: Raw JSON from ``GET /backends/{name}``.

        Returns:
            A fully populated BackendTarget.
        """
        name = data.get("backend", data.get("name", "unknown"))
        qubits = data.get("qubits", data.get("num_qubits", 1))
        status_str = data.get("status", "online").lower()
        status = _IONQ_BACKEND_STATUS_MAP.get(status_str, BackendStatus.ONLINE)
        simulator = "simulator" in name.lower() or data.get("simulator", False)

        # IonQ has all-to-all connectivity — build a linear coupling map
        # representative of the native connectivity (all pairs are valid)
        coupling_map = [
            BackendTargetCoupling(q1=i, q2=j, gate="MS")
            for i in range(min(qubits, 20))  # cap for very large backends
            for j in range(i + 1, min(qubits, 20))
        ]

        max_shots = data.get("max_shots", IONQ_MAX_SHOTS)
        description = data.get(
            "description",
            f"IonQ {'simulator' if simulator else 'trapped-ion'} backend with {qubits} qubits",
        )

        gate_set = GateSet(
            name="ionq_native",
            gates=list(IONQ_NATIVE_GATES),
            max_qubits=qubits,
        )

        pending = 0
        if "queue_length" in data:
            pending = int(data["queue_length"])

        tags: List[str] = []
        if simulator:
            tags.append("simulator")
        if status == BackendStatus.ONLINE:
            tags.append("available")

        return BackendTarget(
            name=name,
            num_qubits=qubits,
            status=status,
            provider_name="ionq",
            gate_set=gate_set,
            coupling_map=coupling_map,
            max_shots=max_shots,
            max_circuits=data.get("max_circuits", 100),
            basis_gates=list(IONQ_BASIS_GATES),
            native_gates=list(IONQ_NATIVE_GATES),
            simulator=simulator,
            dynamic_circuits=data.get("dynamic_circuits", True),
            description=description,
            operational=status == BackendStatus.ONLINE,
            pending_jobs=pending,
            tags=tags,
        )

    # -- Authentication ----------------------------------------------------

    def authenticate(self) -> bool:
        """Verify the API key against the IonQ API.

        Returns:
            True if authentication succeeds.

        Raises:
            IonQAuthenticationError: If the API key is invalid.
        """
        if not self._api_key:
            raise IonQAuthenticationError(
                "No API key provided. Pass api_key= or set the IONQ_API_KEY "
                "environment variable."
            )

        url = f"{self._api_url}/backends"
        try:
            _http_request(url, headers=self._headers())
            return True
        except IonQAuthenticationError:
            raise
        except IonQError:
            # If we get a non-auth error the key is probably valid but
            # something else went wrong — treat as authenticated.
            return True

    # -- Backend discovery -------------------------------------------------

    def backends(
        self, name: Optional[str] = None, **kwargs: Any
    ) -> List[BackendTarget]:
        """List available IonQ backends.

        Args:
            name: Optional name filter (exact match or substring).
            **kwargs: Additional filters (e.g. ``simulator=True``).

        Returns:
            List of BackendTarget instances.
        """
        if not self._backends_cache:
            self.refresh_backends()

        results = list(self._backends_cache.values())

        if name is not None:
            name_lower = name.lower()
            results = [b for b in results if name_lower in b.name.lower()]

        simulator_filter = kwargs.get("simulator")
        if simulator_filter is not None:
            results = [b for b in results if b.simulator == simulator_filter]

        return results

    def get_backend(self, name: str) -> BackendTarget:
        """Retrieve a specific IonQ backend by name.

        Args:
            name: Exact backend name (e.g. ``"simulator"`` or ``"harmony"``).

        Returns:
            The BackendTarget instance.

        Raises:
            KeyError: If no backend with the given name exists.
        """
        if not self._backends_cache:
            self.refresh_backends()

        if name in self._backends_cache:
            return self._backends_cache[name]

        # Try fetching directly from the API
        try:
            url = f"{self._api_url}/backends/{name}"
            data = _http_request(url, headers=self._headers())
            target = self._parse_backend(data)
            self._backends_cache[name] = target
            return target
        except IonQAPIError as exc:
            if exc.status_code == 404:
                raise KeyError(
                    f"No IonQ backend named '{name}'. "
                    f"Available: {list(self._backends_cache.keys())}"
                ) from exc
            raise

    def refresh_backends(self) -> None:
        """Refresh the local cache of available IonQ backends."""
        url = f"{self._api_url}/backends"
        data = _http_request(url, headers=self._headers())

        # The API returns a list of backend summaries or a dict with a "backends" key
        if isinstance(data, list):
            backend_list = data
        elif isinstance(data, dict):
            backend_list = data.get("backends", data.get("data", []))
        else:
            backend_list = []

        self._backends_cache.clear()
        for entry in backend_list:
            target = self._parse_backend(entry)
            self._backends_cache[target.name] = target

        logger.info("Refreshed IonQ backends: %s", list(self._backends_cache.keys()))

    def backend_status(self, name: str) -> BackendStatus:
        """Return the current status of an IonQ backend.

        Args:
            name: Backend name.

        Returns:
            Current BackendStatus enum value.
        """
        backend = self.get_backend(name)
        return backend.status

    def backend_properties(self, name: str) -> BackendProperties:
        """Return calibration and error properties for an IonQ backend.

        IonQ provides limited public calibration data compared to superconducting
        providers. This constructs a BackendProperties from available fields.

        Args:
            name: Backend name.

        Returns:
            BackendProperties with current calibration data.
        """
        url = f"{self._api_url}/backends/{name}"
        data = _http_request(url, headers=self._headers())

        qubits_raw = data.get("qubits", data.get("num_qubits", 1))
        num_qubits = int(qubits_raw) if isinstance(qubits_raw, (int, float)) else len(qubits_raw)

        # Build per-qubit properties (IonQ exposes limited calibration)
        qubit_props: List[Dict[str, Any]] = []
        raw_qubits = data.get("qubit_properties", data.get("calibration", []))

        if isinstance(raw_qubits, list):
            for qp in raw_qubits:
                qubit_props.append({
                    "T1": qp.get("T1", qp.get("t1", 0.0)),
                    "T2": qp.get("T2", qp.get("t2", 0.0)),
                    "frequency": qp.get("frequency", qp.get("freq", 0.0)),
                    "readout_error": qp.get("readout_error", qp.get("readout_error_rate", 0.0)),
                })
        else:
            # No per-qubit calibration available — populate with defaults
            for i in range(num_qubits):
                qubit_props.append({
                    "T1": data.get("T1", 0.0),
                    "T2": data.get("T2", 0.0),
                    "frequency": 0.0,
                    "readout_error": 0.0,
                })

        # Gate error properties
        gates_raw = data.get("gate_errors", data.get("gate_error", []))
        gate_props: List[Dict[str, Any]] = []
        if isinstance(gates_raw, list):
            for g in gates_raw:
                gate_props.append({
                    "gate": g.get("gate", "unknown"),
                    "qubits": g.get("qubits", []),
                    "error": g.get("error", g.get("error_rate", 0.0)),
                })
        else:
            # Default single-qubit and two-qubit error rates
            default_1q = data.get("single_qubit_error", 0.001)
            default_2q = data.get("two_qubit_error", 0.01)
            for i in range(num_qubits):
                gate_props.append({"gate": "GPI", "qubits": [i], "error": default_1q})
                gate_props.append({"gate": "GPI2", "qubits": [i], "error": default_1q})
            if num_qubits >= 2:
                for i in range(num_qubits):
                    for j in range(i + 1, num_qubits):
                        gate_props.append({"gate": "MS", "qubits": [i, j], "error": default_2q})

        general: List[Dict[str, Any]] = [
            {"name": "backend", "value": name},
            {"name": "max_shots", "value": data.get("max_shots", IONQ_MAX_SHOTS)},
        ]

        return BackendProperties(
            backend_name=name,
            backend_version=data.get("version", data.get("backend_version", "0.3")),
            qubits=qubit_props,
            gates=gate_props,
            general=general,
            last_update=data.get("last_updated", data.get("last_update", "")),
        )

    # -- Job submission and management -------------------------------------

    def submit_job(
        self,
        backend_name: str,
        circuits: Any,
        shots: int = IONQ_DEFAULT_SHOTS,
        **options: Any,
    ) -> IonQJob:
        """Submit a job to an IonQ backend.

        The ``circuits`` argument should be in IonQ JSON format — either a
        single circuit dict or a list of circuit dicts as documented at
        https://docs.ionq.com/#tag/Jobs.

        Args:
            backend_name: Target backend name (e.g. ``"simulator"``).
            circuits: IonQ-format circuit(s) to execute.
            shots: Number of measurement shots (1 – 1,000,000).
            **options: Additional IonQ job options:
                - ``name`` (str): User-defined job name.
                - ``tags`` (list[str]): User-defined tags.
                - ``shot_noise`` (bool): Enable shot noise simulation on simulators.
                - ``noise_model`` (str): Noise model for simulation.
                - ``packet_id`` (str): External packet identifier.
                - ``priority`` (str): Job priority ("normal" or "high").

        Returns:
            An IonQJob tracking the submission.

        Raises:
            IonQAPIError: If the API rejects the submission.
            ValueError: If shots is out of range.
        """
        if shots < 1 or shots > IONQ_MAX_SHOTS:
            raise ValueError(
                f"shots must be between 1 and {IONQ_MAX_SHOTS}, got {shots}"
            )

        payload: Dict[str, Any] = {
            "target": backend_name,
            "shots": shots,
            "circuit": circuits,
        }

        # Merge optional fields
        for key in ("name", "tags", "shot_noise", "noise_model", "packet_id", "priority"):
            if key in options:
                payload[key] = options[key]

        url = f"{self._api_url}/jobs"
        data = _http_request(
            url,
            method="POST",
            headers=self._headers(),
            body=json.dumps(payload).encode("utf-8"),
        )

        job_id = data.get("id", data.get("job_id", ""))
        if not job_id:
            raise IonQJobError(
                f"No job ID returned from IonQ API. Response: {data}"
            )

        return IonQJob(
            job_id=job_id,
            backend_name=backend_name,
            provider=self,
            api_url=self._api_url,
            api_key=self._api_key,
            status=_IONQ_JOB_STATUS_MAP.get(
                data.get("status", "pending").lower(), "QUEUED"
            ),
            queue_position=data.get("queue_position"),
            cost=data.get("cost"),
        )

    def get_job(self, job_id: str) -> IonQJob:
        """Retrieve an existing IonQ job by its ID.

        Args:
            job_id: IonQ-assigned job identifier.

        Returns:
            The IonQJob instance.

        Raises:
            KeyError: If no job with the given ID exists.
        """
        url = f"{self._api_url}/jobs/{job_id}"
        data = _http_request(url, headers=self._headers())

        backend_name = data.get("target", data.get("backend", "unknown"))

        return IonQJob(
            job_id=job_id,
            backend_name=backend_name,
            provider=self,
            api_url=self._api_url,
            api_key=self._api_key,
            status=_IONQ_JOB_STATUS_MAP.get(
                data.get("status", "pending").lower(), "QUEUED"
            ),
            queue_position=data.get("queue_position"),
            cost=data.get("cost"),
            raw_data=data,
        )

    def cancel_job(self, job_id: str) -> None:
        """Cancel a queued or running IonQ job.

        Args:
            job_id: IonQ-assigned job identifier.

        Raises:
            IonQAPIError: If the API rejects the cancellation.
        """
        job = self.get_job(job_id)
        job.cancel()

    # -- Account operations ------------------------------------------------

    def my_reservations(self) -> List[Dict[str, Any]]:
        """Return a list of backend reservations for the current account.

        IonQ reservations allow reserving dedicated hardware time.

        Returns:
            List of reservation dicts with details.
        """
        url = f"{self._api_url}/reservations"
        try:
            data = _http_request(url, headers=self._headers())
        except IonQAPIError as exc:
            if exc.status_code == 404:
                logger.debug("Reservations endpoint not available for this account")
                return []
            raise

        if isinstance(data, list):
            return data
        return data.get("reservations", data.get("data", []))

    def account_usage(self) -> Dict[str, Any]:
        """Return current account usage statistics.

        Returns:
            Dictionary with usage metrics such as seconds used,
            jobs run, and quota information.
        """
        url = f"{self._api_url}/account"
        try:
            data = _http_request(url, headers=self._headers())
        except IonQAPIError as exc:
            if exc.status_code == 404:
                logger.debug("Account endpoint not available")
                return {}
            raise

        return {
            "seconds_used": data.get("seconds_used", 0),
            "jobs_run": data.get("jobs_run", 0),
            "quota_seconds": data.get("quota_seconds", 0),
            "quota_remaining": data.get("quota_remaining", 0),
            "plan": data.get("plan", "unknown"),
            "raw": data,
        }

    def get_cost_estimate(
        self, shots: int, backend: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Estimate the cost of a job before submission.

        IonQ pricing is based on shots and backend type. Simulator backends
        are typically free or very low cost.

        Args:
            shots: Number of measurement shots.
            backend: Backend name to estimate for.
            **kwargs: Additional estimation parameters (reserved for future use).

        Returns:
            Dictionary with cost estimate details including per-shot price,
            total estimated cost, and currency.
        """
        # IonQ approximate pricing (USD)
        # Real hardware: ~$0.01 per shot for 11-qubit, scales with qubits
        # Simulator: typically $0.00 or negligible
        pricing_table: Dict[str, float] = {
            "simulator": 0.0,
            "simulator_atlantic": 0.0,
            "simulator_fusion": 0.0,
            "harmony": 0.01,
            "aria-1": 0.03,
            "aria-2": 0.03,
            "forte-1": 0.03,
            "forte-enterprise-1": 0.03,
        }

        per_shot = pricing_table.get(backend.lower(), 0.01)
        total = shots * per_shot

        return {
            "backend": backend,
            "shots": shots,
            "per_shot_usd": per_shot,
            "total_usd": total,
            "currency": "USD",
            "estimated": True,
            "note": "Estimate based on published pricing; actual cost may vary",
        }

    def queue_status(self) -> Dict[str, Any]:
        """Return the current IonQ queue status.

        Returns:
            Dictionary with queue length, estimated wait time, etc.
        """
        url = f"{self._api_url}/queue"
        data = _http_request(url, headers=self._headers())
        return data


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def IonQBackend(backend_name: str, provider: IonQProvider) -> BackendTarget:
    """Factory function to retrieve an IonQ backend target.

    This is a convenience wrapper around ``provider.get_backend()`` that
    provides a functional interface for backend retrieval.

    Args:
        backend_name: Name of the IonQ backend (e.g. ``"simulator"``).
        provider: An IonQProvider instance.

    Returns:
        The BackendTarget for the requested backend.

    Raises:
        KeyError: If the backend does not exist.
    """
    return provider.get_backend(backend_name)
