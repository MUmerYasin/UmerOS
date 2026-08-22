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
UMEROS Cloud Job
=================
Job tracking, status polling, and result retrieval for quantum executions.
Integrates with real provider REST APIs (IBM, IonQ, Braket, Rigetti).
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _http_request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Make an HTTP request and return parsed JSON.

    Parameters
    ----------
    method:
        HTTP verb (GET, POST, PUT, DELETE).
    url:
        Full URL.
    headers:
        Optional extra headers (merged with defaults).
    body:
        Optional JSON body (for POST/PUT).
    timeout:
        Network timeout in seconds.

    Returns
    -------
    dict
        Parsed JSON response, or empty dict on 204/empty body.

    Raises
    ------
    RuntimeError
        On non-2xx HTTP status codes.
    ConnectionError
        On network failures.
    """
    default_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        default_headers.update(headers)

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=default_headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw.strip():
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(
            f"HTTP {exc.code} on {method} {url}: {body_text}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"Failed to reach {url}: {exc.reason}"
        ) from exc


# ---------------------------------------------------------------------------
# Status enums and provider maps
# ---------------------------------------------------------------------------


class CloudJobStatus(Enum):
    """Lifecycle states of a cloud quantum job."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


_PROVIDER_STATUS_MAPS: Dict[str, Dict[str, CloudJobStatus]] = {
    "ibm": {
        "QUEUED": CloudJobStatus.QUEUED,
        "RUNNING": CloudJobStatus.RUNNING,
        "COMPLETED": CloudJobStatus.DONE,
        "DONE": CloudJobStatus.DONE,
        "ERROR": CloudJobStatus.ERROR,
        "FAILED": CloudJobStatus.ERROR,
        "CANCELLED": CloudJobStatus.CANCELLED,
        "CANCELED": CloudJobStatus.CANCELLED,
    },
    "ionq": {
        "ready": CloudJobStatus.QUEUED,
        "running": CloudJobStatus.RUNNING,
        "complete": CloudJobStatus.DONE,
        "completed": CloudJobStatus.DONE,
        "failed": CloudJobStatus.ERROR,
        "error": CloudJobStatus.ERROR,
        "cancelled": CloudJobStatus.CANCELLED,
        "canceled": CloudJobStatus.CANCELLED,
    },
    "braket": {
        "QUEUED": CloudJobStatus.QUEUED,
        "IN_QUEUE": CloudJobStatus.QUEUED,
        "RUNNING": CloudJobStatus.RUNNING,
        "COMPLETED": CloudJobStatus.DONE,
        "ERROR": CloudJobStatus.ERROR,
        "CANCELLED": CloudJobStatus.CANCELLED,
    },
    "rigetti": {
        "queued": CloudJobStatus.QUEUED,
        "running": CloudJobStatus.RUNNING,
        "complete": CloudJobStatus.DONE,
        "completed": CloudJobStatus.DONE,
        "failed": CloudJobStatus.ERROR,
        "error": CloudJobStatus.ERROR,
        "cancelled": CloudJobStatus.CANCELLED,
    },
}


def _map_provider_status(provider: str, raw_status: str) -> CloudJobStatus:
    """Map a provider-specific status string to CloudJobStatus."""
    status_map = _PROVIDER_STATUS_MAPS.get(provider.lower(), {})
    normalized = raw_status.strip().upper()
    # Try case-insensitive match first
    for key, val in status_map.items():
        if key.upper() == normalized:
            return val
    logger.warning("Unknown status %r for provider %r, defaulting to QUEUED", raw_status, provider)
    return CloudJobStatus.QUEUED


# ---------------------------------------------------------------------------
# Provider adapters — each implements real REST API polling
# ---------------------------------------------------------------------------


class IBMJobAdapter:
    """IBM Quantum job operations via REST API.

    Endpoints:
        GET  /jobs/{job_id}
        GET  /jobs/{job_id}/result
        POST /jobs/{job_id}/cancel
    """

    def get_job_status(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        data = _http_request(
            "GET",
            f"{base}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return {
            "status": data.get("status", data.get("state", "UNKNOWN")),
            "queue_position": (data.get("queue_info") or {}).get("position"),
            "raw": data,
        }

    def get_job_result(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        return _http_request(
            "GET",
            f"{base}/jobs/{job_id}/result",
            headers={"Authorization": f"Bearer {token}"},
        )

    def cancel_job(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        return _http_request(
            "POST",
            f"{base}/jobs/{job_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
            body={},
        )


class IonQJobAdapter:
    """IonQ job operations via REST API v0.3.

    Endpoints:
        GET  /jobs/{job_id}
        DELETE /jobs/{job_id}
    """

    def get_job_status(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        data = _http_request(
            "GET",
            f"{base}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return {
            "status": data.get("status", "UNKNOWN"),
            "queue_position": data.get("queue_position"),
            "raw": data,
        }

    def get_job_result(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        data = _http_request(
            "GET",
            f"{base}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return data.get("result", data)

    def cancel_job(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        return _http_request(
            "DELETE",
            f"{base}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )


class BraketJobAdapter:
    """AWS Braket task operations via REST API.

    Endpoints:
        GET  /tasks/{task_arn}
        POST /tasks/{task_arn}/cancel
    """

    def get_job_status(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        data = _http_request(
            "GET",
            f"{base}/tasks/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return {
            "status": data.get("status", "UNKNOWN"),
            "queue_position": None,
            "raw": data,
        }

    def get_job_result(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        return _http_request(
            "GET",
            f"{base}/tasks/{job_id}/result",
            headers={"Authorization": f"Bearer {token}"},
        )

    def cancel_job(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        return _http_request(
            "POST",
            f"{base}/tasks/{job_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
            body={},
        )


class RigettiJobAdapter:
    """Rigetti QCS job operations via REST API.

    Endpoints:
        GET  /jobs/{job_id}
        POST /jobs/{job_id}/cancel
    """

    def get_job_status(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        data = _http_request(
            "GET",
            f"{base}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return {
            "status": data.get("status", "UNKNOWN"),
            "queue_position": None,
            "raw": data,
        }

    def get_job_result(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        return _http_request(
            "GET",
            f"{base}/jobs/{job_id}/result",
            headers={"Authorization": f"Bearer {token}"},
        )

    def cancel_job(self, job_id: str, token: str, endpoint: str) -> Dict[str, Any]:
        base = endpoint.rstrip("/")
        return _http_request(
            "POST",
            f"{base}/jobs/{job_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
            body={},
        )


# Provider adapter registry
_JOB_ADAPTERS: Dict[str, Any] = {
    "ibm": IBMJobAdapter(),
    "ionq": IonQJobAdapter(),
    "braket": BraketJobAdapter(),
    "rigetti": RigettiJobAdapter(),
}


def get_job_adapter(provider: str):
    """Return the provider-specific job adapter, or None."""
    return _JOB_ADAPTERS.get(provider.lower())


# ---------------------------------------------------------------------------
# Result data
# ---------------------------------------------------------------------------


@dataclass
class CloudJobResult:
    """Aggregated result of a completed quantum job.

    Attributes
    ----------
    counts:
        Measurement counts per bitstring.
    probabilities:
        Normalised probabilities for each bitstring.
    metadata:
        Provider-specific metadata.
    raw_data:
        Raw payload returned by the provider API.
    success:
        Whether the job completed without error.
    error_message:
        Description of the error, if *success* is False.
    """

    counts: Dict[str, int] = field(default_factory=dict)
    probabilities: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_data: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        """Auto-compute probabilities from counts if missing."""
        if self.counts and not self.probabilities:
            total = sum(self.counts.values())
            if total > 0:
                self.probabilities = {k: v / total for k, v in self.counts.items()}

    @classmethod
    def from_provider_response(cls, data: Dict[str, Any], provider: str) -> "CloudJobResult":
        """Parse a provider-specific result response into CloudJobResult.

        Parameters
        ----------
        data:
            Raw JSON response from the provider's result endpoint.
        provider:
            Provider name for format-specific parsing.
        """
        counts: Dict[str, int] = {}
        metadata: Dict[str, Any] = {}
        raw = data

        if provider == "ibm":
            counts = data.get("counts", {})
            metadata = {
                "backend": data.get("backend_name", ""),
                "job_id": data.get("job_id", ""),
                "qobj_id": data.get("qobj_id", ""),
            }
        elif provider == "ionq":
            counts_dict = data.get("counts", data.get("result", {}))
            if isinstance(counts_dict, dict):
                counts = {k: int(v) for k, v in counts_dict.items()}
            metadata = {"probabilities": data.get("probabilities", {})}
        elif provider == "braket":
            measurements = data.get("measurements", data.get("measurementSets", []))
            if isinstance(measurements, list):
                for mset in measurements:
                    bits = mset.get("measurementResults", [])
                    for b in bits:
                        bitstring = "".join(str(x) for x in b) if isinstance(b, list) else str(b)
                        counts[bitstring] = counts.get(bitstring, 0) + 1
            metadata = {"type": data.get("type", "")}
        elif provider == "rigetti":
            counts_raw = data.get("readout", data.get("counts", {}))
            if isinstance(counts_raw, dict):
                counts = {k: int(v) for k, v in counts_raw.items()}
            metadata = {"metadata": data.get("metadata", {})}

        return cls(counts=counts, metadata=metadata, raw_data=raw)


# ---------------------------------------------------------------------------
# CloudJob
# ---------------------------------------------------------------------------


class CloudJob:
    """Represents a single quantum job submitted to a cloud backend.

    Parameters
    ----------
    job_id:
        Unique identifier assigned by the provider.
    provider:
        Cloud provider name.
    backend_name:
        Target quantum backend.
    status:
        Initial status.
    token:
        Authentication token for API polling.
    endpoint:
        API base URL for this provider.
    **kwargs:
        Optional: shots, circuit_dict, options, queue_position.
    """

    def __init__(
        self,
        job_id: str,
        provider: str,
        backend_name: str,
        status: CloudJobStatus = CloudJobStatus.QUEUED,
        token: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self._job_id = job_id
        self._provider = provider
        self._backend_name = backend_name
        self._status = status
        self._token = token
        self._endpoint = endpoint
        self._created_at = datetime.now(timezone.utc)
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._queue_position: Optional[int] = kwargs.get("queue_position")
        self._error_message: Optional[str] = None
        self._result_data: Optional[CloudJobResult] = None
        self._shots: int = kwargs.get("shots", 1024)
        self._circuit_dict: Dict[str, Any] = kwargs.get("circuit_dict", {})
        self._options: Dict[str, Any] = kwargs.get("options", {})
        self._adapter = get_job_adapter(provider)
        self._history: List[Dict[str, Any]] = [
            {
                "status": status.value,
                "timestamp": self._created_at.isoformat(),
            }
        ]

    # -- Properties --------------------------------------------------------

    @property
    def job_id(self) -> str:
        return self._job_id

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def status(self) -> CloudJobStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def started_at(self) -> Optional[datetime]:
        return self._started_at

    @property
    def completed_at(self) -> Optional[datetime]:
        return self._completed_at

    @property
    def queue_position(self) -> Optional[int]:
        return self._queue_position

    @property
    def error_message(self) -> Optional[str]:
        return self._error_message

    @property
    def result_data(self) -> Optional[CloudJobResult]:
        return self._result_data

    @property
    def token(self) -> Optional[str]:
        return self._token

    @token.setter
    def token(self, value: Optional[str]) -> None:
        self._token = value

    @property
    def endpoint(self) -> Optional[str]:
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value: Optional[str]) -> None:
        self._endpoint = value

    # -- Status transitions ------------------------------------------------

    def _set_status(self, new_status: CloudJobStatus) -> None:
        """Transition to *new_status* and record the change."""
        now = datetime.now(timezone.utc)
        self._status = new_status
        if new_status == CloudJobStatus.RUNNING and self._started_at is None:
            self._started_at = now
        elif new_status in (
            CloudJobStatus.DONE,
            CloudJobStatus.ERROR,
            CloudJobStatus.CANCELLED,
        ):
            self._completed_at = now
        self._history.append(
            {"status": new_status.value, "timestamp": now.isoformat()}
        )

    def refresh_status(self) -> None:
        """Poll the provider API for the latest status.

        Uses the provider-specific adapter to make a real REST call.
        Falls back gracefully if no adapter is configured or on network errors.
        """
        if self._adapter is None or self._token is None or self._endpoint is None:
            logger.debug(
                "refresh_status skipped for %s: no adapter/token/endpoint", self._job_id
            )
            return

        try:
            response = self._adapter.get_job_status(
                self._job_id, self._token, self._endpoint
            )
        except (RuntimeError, ConnectionError) as exc:
            logger.warning("refresh_status network error for %s: %s", self._job_id, exc)
            return

        raw_status = response.get("status", "")
        new_status = _map_provider_status(self._provider, raw_status)
        self._queue_position = response.get("queue_position")

        if new_status != self._status:
            self._set_status(new_status)

        if new_status == CloudJobStatus.ERROR:
            self._error_message = (
                response.get("raw", {}).get("error", {})
                .get("message", "Job failed on provider")
            )

        if new_status == CloudJobStatus.DONE:
            self._fetch_result()

    def _fetch_result(self) -> None:
        """Fetch the result payload from the provider after completion."""
        if self._adapter is None or self._token is None or self._endpoint is None:
            return
        try:
            raw_result = self._adapter.get_job_result(
                self._job_id, self._token, self._endpoint
            )
            self._result_data = CloudJobResult.from_provider_response(
                raw_result, self._provider
            )
        except (RuntimeError, ConnectionError) as exc:
            logger.warning("Failed to fetch result for %s: %s", self._job_id, exc)

    def wait(self, timeout: float = 300, poll_interval: float = 2.0) -> None:
        """Block until the job reaches a terminal state.

        Parameters
        ----------
        timeout:
            Maximum seconds to wait before raising TimeoutError.
        poll_interval:
            Seconds between status polls (minimum 0.5s).

        Raises
        ------
        TimeoutError
            If the job does not finish within *timeout* seconds.
        """
        poll_interval = max(0.5, poll_interval)
        deadline = time.monotonic() + timeout
        while self._status not in (
            CloudJobStatus.DONE,
            CloudJobStatus.ERROR,
            CloudJobStatus.CANCELLED,
        ):
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {self._job_id} did not complete within {timeout}s"
                )
            self.refresh_status()
            time.sleep(poll_interval)

    def cancel(self) -> bool:
        """Request cancellation via the provider API.

        Returns True if the cancel request was sent.
        """
        if self._status in (
            CloudJobStatus.DONE,
            CloudJobStatus.ERROR,
            CloudJobStatus.CANCELLED,
        ):
            return False

        if self._adapter and self._token and self._endpoint:
            try:
                self._adapter.cancel_job(self._job_id, self._token, self._endpoint)
            except (RuntimeError, ConnectionError) as exc:
                logger.warning("cancel() network error for %s: %s", self._job_id, exc)

        self._error_message = "Cancelled by user"
        self._set_status(CloudJobStatus.CANCELLED)
        return True

    def result(self, timeout: float = 600) -> CloudJobResult:
        """Wait for completion and return the aggregated result.

        Parameters
        ----------
        timeout:
            Maximum seconds to wait for the result.

        Returns
        -------
        CloudJobResult

        Raises
        ------
        RuntimeError
            If the job ended in an error or was cancelled.
        TimeoutError
            If the job does not finish within *timeout* seconds.
        """
        self.wait(timeout=timeout)
        if self._status == CloudJobStatus.CANCELLED:
            return CloudJobResult(success=False, error_message="Job was cancelled")
        if self._status == CloudJobStatus.ERROR:
            return CloudJobResult(
                success=False, error_message=self._error_message or "Unknown error"
            )
        if self._result_data is not None:
            return self._result_data
        self._result_data = CloudJobResult(
            counts={},
            probabilities={},
            metadata={"backend": self._backend_name, "shots": self._shots},
        )
        return self._result_data

    # -- Result helpers ----------------------------------------------------

    def get_counts(self, circuit_index: int = 0) -> Dict[str, int]:
        """Return measurement counts for the given circuit index."""
        if self._status != CloudJobStatus.DONE:
            raise RuntimeError(
                f"Job {self._job_id} has not completed (status={self._status.value})"
            )
        result = (
            self.result(timeout=0) if self._result_data is None else self._result_data
        )
        return result.counts

    def get_probabilities(self, circuit_index: int = 0) -> Dict[str, float]:
        """Return normalised probabilities for the given circuit index."""
        if self._status != CloudJobStatus.DONE:
            raise RuntimeError(
                f"Job {self._job_id} has not completed (status={self._status.value})"
            )
        result = (
            self.result(timeout=0) if self._result_data is None else self._result_data
        )
        return result.probabilities

    def history(self) -> List[Dict[str, Any]]:
        """Return the full status-change history for this job."""
        return list(self._history)

    # -- Dunder ------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"CloudJob(id={self._job_id!r}, provider={self._provider!r}, "
            f"backend={self._backend_name!r}, status={self._status.value!r})"
        )
