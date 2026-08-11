"""Cloud and local quantum job management."""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Sequence

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job status
# ---------------------------------------------------------------------------

class JobStatus(Enum):
    PENDING = auto()
    QUEUED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    TIMEOUT = auto()

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMEOUT)


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------

class JobPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

@dataclass
class Job:
    """Single quantum computation job."""

    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: Optional[str] = None
    circuits: List[Any] = field(default_factory=list)
    backend: Optional[str] = None
    shots: int = 1024
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)

    # runtime bookkeeping
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    provider_job_id: Optional[str] = None

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.started_at

    def mark_running(self) -> None:
        self.status = JobStatus.RUNNING
        self.started_at = time.time()

    def mark_completed(self, result: Any = None) -> None:
        self.status = JobStatus.COMPLETED
        self.result = result
        self.completed_at = time.time()

    def mark_failed(self, error: str) -> None:
        self.status = JobStatus.FAILED
        self.error = error
        self.completed_at = time.time()

    def mark_cancelled(self) -> None:
        self.status = JobStatus.CANCELLED
        self.completed_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "backend": self.backend,
            "shots": self.shots,
            "priority": self.priority.value,
            "status": self.status.name,
            "elapsed": self.elapsed,
            "error": self.error,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Abstract manager
# ---------------------------------------------------------------------------

class BaseJobManager(ABC):
    """Interface every job manager must implement."""

    @abstractmethod
    def submit(self, job: Job) -> str:
        """Submit *job* and return a provider-level ID."""

    @abstractmethod
    def status(self, job_id: str) -> JobStatus:
        """Return current status for *job_id*."""

    @abstractmethod
    def result(self, job_id: str) -> Any:
        """Return result payload for a completed job."""

    @abstractmethod
    def cancel(self, job_id: str) -> bool:
        """Cancel a running or queued job."""


# ---------------------------------------------------------------------------
# Local queue manager
# ---------------------------------------------------------------------------

class JobQueueManager(BaseJobManager):
    """In-process FIFO job queue with optional priority sorting."""

    def __init__(self, max_concurrent: int = 1, poll_interval: float = 0.5):
        self.max_concurrent = max_concurrent
        self.poll_interval = poll_interval
        self._jobs: Dict[str, Job] = {}
        self._queue: List[str] = []  # job_ids in execution order
        self._running: int = 0

    # ---- public API -----------------------------------------------------

    def submit(self, job: Job) -> str:
        self._jobs[job.job_id] = job
        job.status = JobStatus.QUEUED
        self._queue.append(job.job_id)
        self._sort_queue()
        log.info("Job %s queued (%s)", job.job_id, job.name or "unnamed")
        return job.job_id

    def status(self, job_id: str) -> JobStatus:
        return self._get_job(job_id).status

    def result(self, job_id: str) -> Any:
        job = self._get_job(job_id)
        if not job.status.is_terminal:
            raise RuntimeError(f"Job {job_id} is not terminal (status={job.status.name})")
        return job.result

    def cancel(self, job_id: str) -> bool:
        job = self._get_job(job_id)
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False
        job.mark_cancelled()
        if job_id in self._queue:
            self._queue.remove(job_id)
        log.info("Job %s cancelled", job_id)
        return True

    def tick(self) -> None:
        """Advance the queue: start next jobs if slots available."""
        while self._running < self.max_concurrent and self._queue:
            next_id = self._queue.pop(0)
            job = self._jobs[next_id]
            if job.status == JobStatus.QUEUED:
                job.mark_running()
                self._running += 1
                log.info("Job %s started", next_id)

    def complete(self, job_id: str, result: Any = None) -> None:
        """Mark a running job as completed."""
        job = self._get_job(job_id)
        job.mark_completed(result)
        self._running = max(0, self._running - 1)
        log.info("Job %s completed", job_id)

    def fail(self, job_id: str, error: str) -> None:
        """Mark a running job as failed."""
        job = self._get_job(job_id)
        job.mark_failed(error)
        self._running = max(0, self._running - 1)
        log.error("Job %s failed: %s", job_id, error)

    def queue_length(self) -> int:
        return len(self._queue)

    def list_jobs(self, status: Optional[JobStatus] = None) -> List[Job]:
        jobs = list(self._jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return jobs

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    # ---- internal -------------------------------------------------------

    def _get_job(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job_id: {job_id}")
        return job

    def _sort_queue(self) -> None:
        self._queue.sort(key=lambda jid: self._jobs[jid].priority.value, reverse=True)


# ---------------------------------------------------------------------------
# Cloud job manager (wraps provider.submit_job)
# ---------------------------------------------------------------------------

class CloudJobManager(BaseJobManager):
    """Manages jobs dispatched to remote quantum providers."""

    def __init__(self, provider: Any, queue_manager: Optional[JobQueueManager] = None):
        self.provider = provider
        self.queue = queue_manager or JobQueueManager()
        self._provider_map: Dict[str, str] = {}  # local_id -> provider_id

    def submit(self, job: Job) -> str:
        local_id = self.queue.submit(job)
        job = self.queue.get_job(local_id)  # type: ignore[assignment]
        assert job is not None
        try:
            provider_id = self.provider.submit_job(
                circuits=job.circuits,
                backend=job.backend,
                shots=job.shots,
                name=job.name,
            )
            self._provider_map[local_id] = provider_id
            job.provider_job_id = provider_id
            log.info("Job %s dispatched to provider as %s", local_id, provider_id)
        except Exception as exc:
            job.mark_failed(str(exc))
            log.error("Job %s dispatch failed: %s", local_id, exc)
        return local_id

    def status(self, job_id: str) -> JobStatus:
        provider_id = self._provider_map.get(job_id)
        if provider_id is None:
            return self.queue.status(job_id)
        try:
            remote = self.provider.get_job_status(provider_id)
            # map remote status to local enum
            status_map: Dict[str, JobStatus] = {
                "pending": JobStatus.PENDING,
                "queued": JobStatus.QUEUED,
                "running": JobStatus.RUNNING,
                "completed": JobStatus.COMPLETED,
                "failed": JobStatus.FAILED,
                "cancelled": JobStatus.CANCELLED,
            }
            mapped = status_map.get(str(remote).lower(), JobStatus.PENDING)
            job = self.queue.get_job(job_id)
            if job is not None:
                job.status = mapped
            return mapped
        except Exception:
            return self.queue.status(job_id)

    def result(self, job_id: str) -> Any:
        provider_id = self._provider_map.get(job_id)
        if provider_id is None:
            return self.queue.result(job_id)
        return self.provider.get_job_result(provider_id)

    def cancel(self, job_id: str) -> bool:
        provider_id = self._provider_map.get(job_id)
        if provider_id is not None:
            try:
                self.provider.cancel_job(provider_id)
            except Exception as exc:
                log.warning("Provider cancel failed for %s: %s", job_id, exc)
        return self.queue.cancel(job_id)

    def poll_all(self, interval: Optional[float] = None) -> None:
        """Poll every active job until terminal."""
        interval = interval or self.queue.poll_interval
        active = [
            j for j in self.queue.list_jobs()
            if not j.status.is_terminal
        ]
        for job in active:
            if job.provider_job_id:
                self.status(job.job_id)


# ---------------------------------------------------------------------------
# Hybrid (local + cloud) job manager
# ---------------------------------------------------------------------------

class HybridJobManager(BaseJobManager):
    """Coordinates local simulation and cloud execution in a single workflow."""

    def __init__(
        self,
        local_manager: Optional[JobQueueManager] = None,
        cloud_manager: Optional[CloudJobManager] = None,
        auto_route: bool = True,
    ):
        self.local = local_manager or JobQueueManager()
        self.cloud = cloud_manager
        self.auto_route = auto_route
        self._routing: Dict[str, str] = {}  # job_id -> "local" | "cloud"

    def submit(self, job: Job, target: Optional[str] = None) -> str:
        """Submit with optional forced routing (``"local"`` or ``"cloud"``)."""
        if target is None and self.auto_route:
            target = self._infer_target(job)
        elif target is None:
            target = "local"

        if target == "cloud" and self.cloud is not None:
            job_id = self.cloud.submit(job)
            self._routing[job_id] = "cloud"
        else:
            job_id = self.local.submit(job)
            self._routing[job_id] = "local"
        return job_id

    def status(self, job_id: str) -> JobStatus:
        r = self._routing.get(job_id, "local")
        if r == "cloud" and self.cloud is not None:
            return self.cloud.status(job_id)
        return self.local.status(job_id)

    def result(self, job_id: str) -> Any:
        r = self._routing.get(job_id, "local")
        if r == "cloud" and self.cloud is not None:
            return self.cloud.result(job_id)
        return self.local.result(job_id)

    def cancel(self, job_id: str) -> bool:
        r = self._routing.get(job_id, "local")
        if r == "cloud" and self.cloud is not None:
            return self.cloud.cancel(job_id)
        return self.local.cancel(job_id)

    def submit_chain(self, jobs: List[Job]) -> List[str]:
        """Submit a chain where each job's result feeds the next.

        Local jobs complete synchronously; cloud jobs are submitted
        sequentially but results are awaited only when needed.
        """
        ids: List[str] = []
        prev_result: Any = None
        for job in jobs:
            if prev_result is not None:
                job.metadata["input_result"] = prev_result
            jid = self.submit(job)
            ids.append(jid)
            # try to get immediate result for chaining
            if self.status(jid).is_terminal:
                prev_result = self.result(jid)
            else:
                prev_result = None  # can't chain across async cloud jobs
        return ids

    # ---- internal -------------------------------------------------------

    def _infer_target(self, job: Job) -> str:
        if self.cloud is None:
            return "local"
        if len(job.circuits) > 10:
            return "cloud"
        if job.metadata.get("force_local"):
            return "local"
        if job.metadata.get("force_cloud"):
            return "cloud"
        return "local"
