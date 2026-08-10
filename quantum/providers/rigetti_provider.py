"""
Rigetti Quantum Cloud Services (QCS) Provider
==============================================
Provider integration for Rigetti Aspen and Ankaa quantum processors
via the QCS REST API.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RIGETTI_NATIVE_GATES = ["RX", "RZ", "CZ"]
_RIGETTI_BASIS_GATES = ["RX", "RZ", "CZ", "MEASURE"]
_RIGETTI_MAX_SHOTS = 4000
_RIGETTI_MAX_CIRCUITS = 100
_RIGETTI_POLL_INTERVAL = 2.0

_QPU_MAP: Dict[str, Dict[str, Any]] = {
    "Ankaa-3": {"num_qubits": 44, "family": "Ankaa"},
    "Ankaa-2": {"num_qubits": 44, "family": "Ankaa"},
    "Aspen-M-3": {"num_qubits": 80, "family": "Aspen"},
    "Aspen-M-2": {"num_qubits": 80, "family": "Aspen"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_cz_coupling_map(num_qubits: int) -> List[BackendTargetCoupling]:
    """Build a heavy-hex-style nearest-neighbour CZ coupling map."""
    couplings: List[BackendTargetCoupling] = []
    for q in range(num_qubits - 1):
        couplings.append(BackendTargetCoupling(q1=q, q2=q + 1, gate="CZ"))
    return couplings


def _http_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Execute an HTTP request and return the parsed JSON response.

    Args:
        method: HTTP method (GET, POST, DELETE).
        url: Full request URL.
        headers: Optional extra headers merged with defaults.
        body: Optional JSON-serialisable request body.
        timeout: Socket timeout in seconds.

    Returns:
        Parsed JSON response body as a dict (empty dict on 204).

    Raises:
        ConnectionError: On network-level failures.
        RuntimeError: On non-2xx HTTP status codes.
    """
    default_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        default_headers.update(headers)

    data = json.dumps(body).encode("utf-8") if body is not None else None

    req = urllib.request.Request(
        url,
        data=data,
        headers=default_headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if raw:
                return json.loads(raw)
            return {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(
            f"QCS API error {exc.code}: {exc.reason}\n{detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"Failed to reach QCS endpoint {url}: {exc.reason}"
        ) from exc


# ---------------------------------------------------------------------------
# RigettiJob
# ---------------------------------------------------------------------------


class RigettiJob(BackendJob):
    """Represents a job submitted to a Rigetti QPU via QCS.

    Args:
        job_id: QCS job identifier.
        backend_name: Name of the target QPU.
        provider: Parent ``RigettiProvider`` instance.
        initial_status: Optional pre-fetched status string.
        **kwargs: Extra metadata from the submit response.
    """

    _STATUS_MAP: Dict[str, str] = {
        "queued": "QUEUED",
        "running": "RUNNING",
        "completed": "DONE",
        "completedWithSuccess": "DONE",
        "completedWithFailure": "ERROR",
        "cancelled": "CANCELLED",
        "error": "ERROR",
    }

    def __init__(
        self,
        job_id: str,
        backend_name: str,
        provider: RigettiProvider,
        *,
        initial_status: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(job_id, backend_name)
        self._provider = provider
        self._status = self._STATUS_MAP.get(
            (initial_status or "queued").lower(), "QUEUED"
        )
        self._queue_position: Optional[int] = kwargs.get("queue_position")
        self._execution_time: Optional[float] = kwargs.get("execution_time")
        self._compiler_stats: Dict[str, Any] = kwargs.get("compiler_stats", {})
        self._meta: Dict[str, Any] = kwargs

    # -- properties ---------------------------------------------------------

    @property
    def status(self) -> str:
        """Current job status string (QUEUED | RUNNING | DONE | ERROR | CANCELLED)."""
        return self._status

    @property
    def queue_position(self) -> Optional[int]:
        """Position in the execution queue, or None if not queued."""
        return self._queue_position

    @property
    def execution_time(self) -> Optional[float]:
        """Elapsed wall-clock execution time in seconds, or None if unavailable."""
        return self._execution_time

    @property
    def compiler_stats(self) -> Dict[str, Any]:
        """Rigetti compiler statistics returned alongside the job."""
        return self._compiler_stats

    # -- mutations ----------------------------------------------------------

    def refresh_status(self) -> None:
        """Poll the QCS API and update internal status fields."""
        data = self._provider._api_get(f"/v1/jobs/{self._job_id}")
        self._status = self._STATUS_MAP.get(
            data.get("status", "").lower(), "QUEUED"
        )
        self._queue_position = data.get("queue_position")
        self._execution_time = data.get("execution_time_seconds")
        self._compiler_stats = data.get("compiler_stats", {})
        self._meta.update(data)

    def result(self, timeout: Optional[float] = None) -> JobResult:
        """Block until the job finishes and return the result.

        Args:
            timeout: Maximum seconds to wait. ``None`` waits indefinitely.

        Returns:
            A ``JobResult`` containing measurement outcomes.

        Raises:
            TimeoutError: If the job does not reach a terminal state.
            RuntimeError: If the job ended in an error state.
        """
        self.wait_for_completion(timeout=timeout)

        if self._status in ("ERROR", "CANCELLED"):
            err = self._meta.get("error_message", "Job failed or was cancelled.")
            return JobResult(
                job_id=self._job_id,
                backend_name=self._backend_name,
                status=self._status,
                results=[],
                metadata=self._meta,
                error_message=str(err),
            )

        raw = self._provider._api_get(f"/v1/jobs/{self._job_id}/result")
        return _parse_qcs_result(raw, self._job_id, self._backend_name)

    def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """Block until the job reaches a terminal state.

        Args:
            timeout: Maximum seconds to wait. ``None`` waits indefinitely.

        Raises:
            TimeoutError: If the timeout expires before the job finishes.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while self._status in ("QUEUED", "RUNNING"):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {self._job_id} did not complete within {timeout}s"
                )
            time.sleep(_RIGETTI_POLL_INTERVAL)
            self.refresh_status()

    def cancel(self) -> None:
        """Cancel a queued or running job.

        Raises:
            RuntimeError: If the QCS API rejects the cancellation request.
        """
        self._provider._api_delete(f"/v1/jobs/{self._job_id}")
        self._status = "CANCELLED"

    def download_result(self) -> Dict[str, Any]:
        """Download the raw result payload without parsing into ``JobResult``.

        Returns:
            Raw JSON dict from the QCS results endpoint.
        """
        return self._provider._api_get(f"/v1/jobs/{self._job_id}/result")

    def status_detail(self) -> str:
        """Human-readable summary including queue position and compile stats."""
        parts = [f"Job {self._job_id} on {self._backend_name}"]
        parts.append(f"status={self._status}")
        if self._queue_position is not None:
            parts.append(f"queue_pos={self._queue_position}")
        if self._execution_time is not None:
            parts.append(f"exec_time={self._execution_time:.3f}s")
        if self._compiler_stats:
            parts.append(f"compile={self._compiler_stats}")
        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"RigettiJob(job_id={self._job_id!r}, "
            f"backend_name={self._backend_name!r}, status={self._status!r})"
        )


# ---------------------------------------------------------------------------
# Result parser
# ---------------------------------------------------------------------------


def _parse_qcs_result(
    raw: Dict[str, Any],
    job_id: str,
    backend_name: str,
) -> JobResult:
    """Convert a raw QCS result payload into the SDK's ``JobResult``."""
    results: List[Dict[str, Any]] = []
    for circuit_data in raw.get("results", []):
        counts_raw = circuit_data.get("measurements", {})
        total_shots = sum(counts_raw.values()) if counts_raw else 0
        probs = (
            {k: v / total_shots for k, v in counts_raw.items()}
            if total_shots
            else {}
        )
        results.append(
            {
                "counts": counts_raw,
                "probabilities": probs,
                "metadata": circuit_data.get("metadata", {}),
            }
        )

    status_done = "DONE" if raw.get("status", "").lower() in (
        "completed", "completedwithsuccess"
    ) else raw.get("status", "DONE").upper()

    return JobResult(
        job_id=job_id,
        backend_name=backend_name,
        status=status_done,
        results=results,
        metadata={
            "compiler_stats": raw.get("compiler_stats", {}),
            "execution_time_seconds": raw.get("execution_time_seconds"),
        },
        start_time=raw.get("start_time"),
        end_time=raw.get("end_time"),
    )


# ---------------------------------------------------------------------------
# RigettiProvider
# ---------------------------------------------------------------------------


class RigettiProvider(BackendProvider):
    """Provider for Rigetti Quantum Cloud Services (QCS).

    Supports listing and querying Aspen / Ankaa QPUs, submitting circuits,
    and retrieving measurement results through the QCS REST API.

    Args:
        api_key: QCS API key. Falls back to the ``RIGETTI_API_KEY``
            environment variable when ``None``.
        api_url: Base URL for the QCS REST API.
        **kwargs: Passed to the ``BackendProvider`` base class.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = "https://qcs.rigetti.com",
        **kwargs: Any,
    ) -> None:
        import os

        resolved_key = api_key or os.environ.get("RIGETTI_API_KEY")
        super().__init__(token=resolved_key, **kwargs)
        self._api_url = api_url.rstrip("/")
        self._backends_cache: Optional[List[BackendTarget]] = None
        self._authenticated = False

    # -- abstract properties ------------------------------------------------

    @property
    def name(self) -> str:
        """Canonical provider name."""
        return "rigetti"

    @property
    def version(self) -> str:
        """Provider SDK version."""
        return "1.0"

    # -- authentication -----------------------------------------------------

    def authenticate(self) -> bool:
        """Verify the API key against QCS.

        Returns:
            ``True`` if the key is valid and the account is reachable.

        Raises:
            RuntimeError: If no API key has been provided.
            ConnectionError: If the QCS endpoint cannot be reached.
        """
        if not self._token:
            raise RuntimeError(
                "No API key provided. Pass api_key or set the "
                "RIGETTI_API_KEY environment variable."
            )
        self._api_get("/v1/qpus")
        self._authenticated = True
        return True

    # -- backend management -------------------------------------------------

    def backends(
        self, name: Optional[str] = None, **kwargs: Any
    ) -> List[BackendTarget]:
        """List available QPU backends, optionally filtered by name.

        Args:
            name: Substring or exact name filter.
            **kwargs: Reserved for future filters.

        Returns:
            Matching ``BackendTarget`` instances.
        """
        if self._backends_cache is None:
            self.refresh_backends()
        targets = self._backends_cache or []
        if name is not None:
            name_lower = name.lower()
            targets = [t for t in targets if name_lower in t.name.lower()]
        return list(targets)

    def get_backend(self, name: str) -> BackendTarget:
        """Retrieve a specific backend by exact name.

        Args:
            name: Exact backend name (case-insensitive).

        Returns:
            The matching ``BackendTarget``.

        Raises:
            KeyError: If no backend matches.
        """
        for backend in self.backends():
            if backend.name.lower() == name.lower():
                return backend
        raise KeyError(f"No Rigetti backend found with name {name!r}")

    def refresh_backends(self) -> None:
        """Refresh the cached list of QPU backends from QCS."""
        try:
            data = self._api_get("/v1/qpus")
            qpu_list = data.get("qpus", data) if isinstance(data, dict) else data
        except Exception:
            qpu_list = _QPU_MAP.keys()

        targets: List[BackendTarget] = []
        for qpu_info in qpu_list:
            if isinstance(qpu_info, str):
                qpu_name = qpu_info
                qpu_meta: Dict[str, Any] = _QPU_MAP.get(qpu_name, {})
            elif isinstance(qpu_info, dict):
                qpu_name = qpu_info.get("name", qpu_info.get("id", "unknown"))
                qpu_meta = qpu_info
            else:
                continue

            num_qubits = qpu_meta.get(
                "num_qubits", _QPU_MAP.get(qpu_name, {}).get("num_qubits", 80)
            )

            try:
                status_str = self.backend_status_raw(qpu_name)
            except Exception:
                status_str = "unknown"

            status = {
                "online": BackendStatus.ONLINE,
                "offline": BackendStatus.OFFLINE,
                "maintenance": BackendStatus.MAINTENANCE,
            }.get(status_str.lower(), BackendStatus.OFFLINE)

            targets.append(
                RigettiBackend(qpu_name, provider=self, num_qubits=num_qubits)
            )
            targets[-1].status = status

        self._backends_cache = targets

    # -- status & properties ------------------------------------------------

    def backend_status(self, name: str) -> BackendStatus:
        """Return the operational status for a QPU.

        Args:
            name: QPU name (e.g. ``"Ankaa-3"``).

        Returns:
            A ``BackendStatus`` enum value.
        """
        raw = self.backend_status_raw(name)
        return {
            "online": BackendStatus.ONLINE,
            "offline": BackendStatus.OFFLINE,
            "maintenance": BackendStatus.MAINTENANCE,
            "queue_paused": BackendStatus.QUEUE_PAUSED,
        }.get(raw.lower(), BackendStatus.OFFLINE)

    def backend_status_raw(self, name: str) -> str:
        """Return the raw status string for a QPU.

        Args:
            name: QPU name.

        Returns:
            Status string from QCS (e.g. ``"online"``).
        """
        data = self._api_get(f"/v1/qpus/{name}/status")
        return data.get("status", "unknown")

    def backend_properties(self, name: str) -> BackendProperties:
        """Fetch calibration and error data for a QPU.

        Args:
            name: QPU name.

        Returns:
            A ``BackendProperties`` with per-qubit and per-gate metrics.
        """
        data = self._api_get(f"/v1/qpus/{name}/calibration")
        return _parse_qcs_calibration(name, data)

    # -- job submission -----------------------------------------------------

    def submit_job(
        self,
        backend_name: str,
        circuits: Any,
        shots: int = 1024,
        **options: Any,
    ) -> RigettiJob:
        """Submit one or more circuits for execution on a Rigetti QPU.

        Args:
            backend_name: Target QPU name.
            circuits: Circuits in quil, JSON dict, or list-of-dict form.
            shots: Number of measurement shots (max 4000).
            **options: Optional ``priority`` (int) and ``param`` (dict).

        Returns:
            A ``RigettiJob`` tracking the submission.
        """
        if shots < 1 or shots > _RIGETTI_MAX_SHOTS:
            raise ValueError(
                f"shots must be between 1 and {_RIGETTI_MAX_SHOTS}, got {shots}"
            )

        normalized = _normalise_circuits(circuits)
        payload: Dict[str, Any] = {
            "type": "standard",
            "device_id": backend_name,
            "shots": shots,
            "program": normalized,
        }
        priority = options.get("priority")
        if priority is not None:
            payload["priority"] = int(priority)
        params = options.get("param")
        if params is not None:
            payload["param"] = params

        resp = self._api_post("/v1/jobs", payload)
        job_id = resp.get("job_id") or resp.get("id", "unknown")

        return RigettiJob(
            job_id=job_id,
            backend_name=backend_name,
            provider=self,
            initial_status=resp.get("status", "queued"),
            queue_position=resp.get("queue_position"),
            execution_time=resp.get("execution_time_seconds"),
            compiler_stats=resp.get("compiler_stats", {}),
        )

    def get_job(self, job_id: str) -> RigettiJob:
        """Retrieve an existing job by its identifier.

        Args:
            job_id: QCS job ID.

        Returns:
            A ``RigettiJob`` instance.

        Raises:
            KeyError: If the job does not exist.
        """
        data = self._api_get(f"/v1/jobs/{job_id}")
        return RigettiJob(
            job_id=job_id,
            backend_name=data.get("device_id", data.get("backend_name", "unknown")),
            provider=self,
            initial_status=data.get("status", "unknown"),
            queue_position=data.get("queue_position"),
            execution_time=data.get("execution_time_seconds"),
            compiler_stats=data.get("compiler_stats", {}),
        )

    def cancel_job(self, job_id: str) -> None:
        """Cancel a queued or running job.

        Args:
            job_id: QCS job ID.
        """
        self._api_delete(f"/v1/jobs/{job_id}")

    # -- account operations -------------------------------------------------

    def my_reservations(self) -> List[Dict[str, Any]]:
        """Return reservations for the authenticated account.

        Returns:
            List of reservation dicts with backend, start/end times, and status.
        """
        data = self._api_get("/v1/reservations")
        return data.get("reservations", data) if isinstance(data, dict) else data

    def account_usage(self) -> Dict[str, Any]:
        """Return current account usage statistics.

        Returns:
            Dict with metrics like ``seconds_used``, ``jobs_run``, ``quota``.
        """
        return self._api_get("/v1/account/usage")

    # -- Rigetti-specific helpers -------------------------------------------

    def list_quantum_processors(self) -> List[Dict[str, Any]]:
        """List all quantum processors with metadata.

        Returns:
            List of dicts containing processor name, qubit count, and family.
        """
        data = self._api_get("/v1/qpus")
        qpu_list = data.get("qpus", data) if isinstance(data, dict) else data
        processors: List[Dict[str, Any]] = []
        for qpu in qpu_list:
            if isinstance(qpu, str):
                name = qpu
                info: Dict[str, Any] = _QPU_MAP.get(name, {})
            elif isinstance(qpu, dict):
                name = qpu.get("name", qpu.get("id", "unknown"))
                info = qpu
            else:
                continue
            processors.append({
                "name": name,
                "num_qubits": info.get(
                    "num_qubits", _QPU_MAP.get(name, {}).get("num_qubits", 80)
                ),
                "family": info.get(
                    "family", _QPU_MAP.get(name, {}).get("family", "unknown")
                ),
            })
        return processors

    def get_qpu_calibration(self, processor: str) -> Dict[str, Any]:
        """Return the full calibration payload for a processor.

        Args:
            processor: QPU name (e.g. ``"Ankaa-3"``).

        Returns:
            Raw calibration dict from QCS.
        """
        return self._api_get(f"/v1/qpus/{processor}/calibration")

    # -- low-level HTTP wrappers -------------------------------------------

    def _api_get(self, path: str) -> Dict[str, Any]:
        """Perform an authenticated GET request."""
        url = f"{self._api_url}{path}"
        headers = _auth_header(self._token)
        return _http_request("GET", url, headers=headers)

    def _api_post(
        self, path: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform an authenticated POST request."""
        url = f"{self._api_url}{path}"
        headers = _auth_header(self._token)
        return _http_request("POST", url, headers=headers, body=body)

    def _api_delete(self, path: str) -> Dict[str, Any]:
        """Perform an authenticated DELETE request."""
        url = f"{self._api_url}{path}"
        headers = _auth_header(self._token)
        return _http_request("DELETE", url, headers=headers)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _auth_header(token: Optional[str]) -> Dict[str, str]:
    """Return authorization headers for QCS API calls."""
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _normalise_circuits(circuits: Any) -> Any:
    """Ensure circuits are in a JSON-serialisable format for the QCS payload."""
    if isinstance(circuits, str):
        return circuits
    if isinstance(circuits, (list, tuple, dict)):
        return circuits
    return str(circuits)


def _parse_qcs_calibration(
    backend_name: str, data: Dict[str, Any]
) -> BackendProperties:
    """Convert a QCS calibration dict into ``BackendProperties``."""
    qubits_raw = data.get("qubits", data.get("perQubitMetrics", {}))
    qubits: List[Dict[str, Any]] = []
    if isinstance(qubits_raw, dict):
        for idx in sorted(qubits_raw.keys(), key=lambda k: int(k)):
            entry = qubits_raw[idx]
            qubits.append({
                "T1": entry.get("T1", entry.get("t1", 0.0)),
                "T2": entry.get("T2", entry.get("t2", 0.0)),
                "frequency": entry.get("frequency", entry.get("freq", 0.0)),
                "readout_error": entry.get(
                    "readout_error", entry.get("fidelity", 0.0)
                ),
            })
    elif isinstance(qubits_raw, list):
        for entry in qubits_raw:
            qubits.append({
                "T1": entry.get("T1", 0.0),
                "T2": entry.get("T2", 0.0),
                "frequency": entry.get("frequency", 0.0),
                "readout_error": entry.get("readout_error", 0.0),
            })

    gates_raw = data.get("gates", data.get("twoQubitGateCalibrations", []))
    gates: List[Dict[str, Any]] = []
    if isinstance(gates_raw, dict):
        for gate_name, qubit_pairs in gates_raw.items():
            if isinstance(qubit_pairs, dict):
                for pair_key, metrics in qubit_pairs.items():
                    if isinstance(pair_key, str) and "-" in pair_key:
                        qubit_indices = [
                            int(q) for q in pair_key.split("-") if q.isdigit()
                        ]
                    else:
                        qubit_indices = []
                    gates.append({
                        "gate": gate_name,
                        "qubits": qubit_indices,
                        "error": metrics.get("error", metrics.get("fidelity", 0.0)),
                    })
    elif isinstance(gates_raw, list):
        for entry in gates_raw:
            gates.append({
                "gate": entry.get("gate", entry.get("name", "unknown")),
                "qubits": entry.get("qubits", []),
                "error": entry.get("error", entry.get("fidelity", 0.0)),
            })

    ts = data.get("timestamp", data.get("lastUpdated", ""))
    if ts and isinstance(ts, (int, float)):
        ts = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    last_update = str(ts) if ts else datetime.now(tz=timezone.utc).isoformat()

    return BackendProperties(
        backend_name=backend_name,
        backend_version=data.get("version", "1.0"),
        qubits=qubits,
        gates=gates,
        general=data.get("general", []),
        last_update=last_update,
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def RigettiBackend(
    backend_name: str,
    provider: RigettiProvider,
    *,
    num_qubits: Optional[int] = None,
) -> BackendTarget:
    """Create a ``BackendTarget`` for a Rigetti QPU.

    This is a convenience factory that builds the full ``BackendTarget``
    dataclass with Rigetti-native defaults.

    Args:
        backend_name: QPU identifier (e.g. ``"Ankaa-3"``).
        provider: The ``RigettiProvider`` that owns this backend.
        num_qubits: Override qubit count (auto-detected when omitted).

    Returns:
        A fully populated ``BackendTarget``.
    """
    meta = _QPU_MAP.get(backend_name, {})
    qubits = num_qubits or meta.get("num_qubits", 80)

    try:
        status = provider.backend_status(backend_name)
    except Exception:
        status = BackendStatus.OFFLINE

    gate_set = GateSet(
        name="rigetti_native",
        gates=list(_RIGETTI_BASIS_GATES),
        max_qubits=qubits,
    )

    return BackendTarget(
        name=backend_name,
        num_qubits=qubits,
        status=status,
        provider_name="rigetti",
        gate_set=gate_set,
        coupling_map=_build_cz_coupling_map(qubits),
        max_shots=_RIGETTI_MAX_SHOTS,
        max_circuits=_RIGETTI_MAX_CIRCUITS,
        basis_gates=list(_RIGETTI_BASIS_GATES),
        native_gates=list(_RIGETTI_NATIVE_GATES),
        simulator=False,
        dynamic_circuits=False,
        description=(
            f"Rigetti {meta.get('family', 'QPU')} quantum processor "
            f"({qubits} qubits) via QCS"
        ),
        operational=status == BackendStatus.ONLINE,
        pending_jobs=0,
        tags=["rigetti", "qcs", meta.get("family", "").lower()],
    )
