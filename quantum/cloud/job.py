"""
UMEROS Cloud Job
=================
Job tracking, status polling, and result retrieval for quantum executions.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class CloudJobStatus(Enum):
    """Lifecycle states of a cloud quantum job."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class CloudJobResult:
    """Aggregated result of a completed quantum job.

    Attributes
    ----------
    counts:
        Measurement counts per bitstring (e.g. ``{"00": 512, "11": 512}``).
    probabilities:
        Normalised probabilities for each bitstring.
    metadata:
        Provider-specific metadata (timing, backend version, etc.).
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
        Initial status (defaults to :attr:`CloudJobStatus.QUEUED`).
    **kwargs:
        Optional fields: ``shots``, ``circuit_dict``, ``options``,
        ``queue_position``.
    """

    def __init__(
        self,
        job_id: str,
        provider: str,
        backend_name: str,
        status: CloudJobStatus = CloudJobStatus.QUEUED,
        **kwargs: Any,
    ) -> None:
        self._job_id = job_id
        self._provider = provider
        self._backend_name = backend_name
        self._status = status
        self._created_at = datetime.now(timezone.utc)
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._queue_position: Optional[int] = kwargs.get("queue_position")
        self._error_message: Optional[str] = None
        self._result_data: Optional[CloudJobResult] = None
        self._shots: int = kwargs.get("shots", 1024)
        self._circuit_dict: Dict[str, Any] = kwargs.get("circuit_dict", {})
        self._options: Dict[str, Any] = kwargs.get("options", {})
        self._history: List[Dict[str, Any]] = [
            {
                "status": status.value,
                "timestamp": self._created_at.isoformat(),
            }
        ]

    # -- Properties --------------------------------------------------------

    @property
    def job_id(self) -> str:
        """Unique job identifier."""
        return self._job_id

    @property
    def provider(self) -> str:
        """Cloud provider name."""
        return self._provider

    @property
    def backend_name(self) -> str:
        """Target backend identifier."""
        return self._backend_name

    @property
    def status(self) -> CloudJobStatus:
        """Current job status."""
        return self._status

    @property
    def created_at(self) -> datetime:
        """Timestamp when the job was created."""
        return self._created_at

    @property
    def started_at(self) -> Optional[datetime]:
        """Timestamp when the job started running."""
        return self._started_at

    @property
    def completed_at(self) -> Optional[datetime]:
        """Timestamp when the job finished (success or error)."""
        return self._completed_at

    @property
    def queue_position(self) -> Optional[int]:
        """Position in the provider's queue, or None if unknown."""
        return self._queue_position

    @property
    def error_message(self) -> Optional[str]:
        """Error description if the job failed."""
        return self._error_message

    @property
    def result_data(self) -> Optional[CloudJobResult]:
        """Result payload, available only after the job is done."""
        return self._result_data

    # -- Status transitions ------------------------------------------------

    def _set_status(self, new_status: CloudJobStatus) -> None:
        """Transition to *new_status* and record the change."""
        now = datetime.now(timezone.utc)
        self._status = new_status
        if new_status == CloudJobStatus.RUNNING and self._started_at is None:
            self._started_at = now
        elif new_status in (CloudJobStatus.DONE, CloudJobStatus.ERROR, CloudJobStatus.CANCELLED):
            self._completed_at = now
        self._history.append(
            {"status": new_status.value, "timestamp": now.isoformat()}
        )

    def refresh_status(self) -> None:
        """Poll the provider API for the latest status.

        This is a stub — override or monkey-patch with real API calls.
        """
        pass

    def wait(self, timeout: float = 300) -> None:
        """Block until the job reaches a terminal state.

        Parameters
        ----------
        timeout:
            Maximum seconds to wait before raising :class:`TimeoutError`.

        Raises
        ------
        TimeoutError
            If the job does not finish within *timeout* seconds.
        """
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
            time.sleep(2)

    def cancel(self) -> bool:
        """Request cancellation of this job.

        Returns True if the status was changed to CANCELLED, False if the
        job was already in a terminal state.
        """
        if self._status in (
            CloudJobStatus.DONE,
            CloudJobStatus.ERROR,
            CloudJobStatus.CANCELLED,
        ):
            return False
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
            return CloudJobResult(
                success=False,
                error_message="Job was cancelled",
            )
        if self._status == CloudJobStatus.ERROR:
            return CloudJobResult(
                success=False,
                error_message=self._error_message or "Unknown error",
            )
        # Return cached result or build a default one.
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
        """Return measurement counts for the given circuit index.

        Raises RuntimeError if the job has not completed successfully.
        """
        if self._status != CloudJobStatus.DONE:
            raise RuntimeError(
                f"Job {self._job_id} has not completed (status={self._status.value})"
            )
        result = self.result(timeout=0) if self._result_data is None else self._result_data
        return result.counts

    def get_probabilities(self, circuit_index: int = 0) -> Dict[str, float]:
        """Return normalised probabilities for the given circuit index.

        Raises RuntimeError if the job has not completed successfully.
        """
        if self._status != CloudJobStatus.DONE:
            raise RuntimeError(
                f"Job {self._job_id} has not completed (status={self._status.value})"
            )
        result = self.result(timeout=0) if self._result_data is None else self._result_data
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
