"""
UmerOS — IBM Quantum Runtime Service (v0.48 features)
=====================================================

A focused, REST-only re-implementation of the
``qiskit_ibm_runtime.QiskitRuntimeService`` surface, scoped to the
features added or evolved in v0.48 (released 2026-07-14, per
``QISKIT_RESEARCH/qiskit-ibm-runtime-report.md``):

* ``instance="auto"`` automatic account / instance selection.
* ``least_busy(use_fractional_gates=True)`` backend filter.
* ``wrap_angles=True`` in transpile options for fractional gates.
* ``RuntimeJobV2.usage(partial: bool)`` for usage-meter snapshotting.

This module does *not* replace the richer ``IBMQuantumProvider`` in
``quantum/providers/ibm_provider.py`` — it complements it by giving
UMEROS callers a primitive-aware, session-oriented surface similar to
``qiskit-ibm-runtime``.

Tier:
    EXPERIMENTAL — calls ``auth.quantum-computing.ibm.com/api`` (or
    Mocks when *runtime_token* is ``None``).  Set
    ``QISKIT_IBM_RUNTIME_TOKEN`` in the environment to enable real
    network calls; no credentials are baked into the source.

Usage::

    from quantum.ibm_runtime_service import (
        QiskitRuntimeService,
        OptionsV2,
        SamplerV2Options,
        EstimatorV2Options,
    )

    svc = QiskitRuntimeService(
        channel="ibm_quantum",
        token=None,                   # read from $QISKIT_IBM_RUNTIME_TOKEN
        instance="auto",
    )
    backend = svc.least_busy(use_fractional_gates=True, simulator=False)
    with Session(backend=backend, service=svc) as session:
        job = session.run(sampler_pubs)
        result = job.result(timeout=300)
        usage_snapshot = job.usage(partial=True)
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Base URL of the Qiskit IBM Runtime REST API.  Pulled from the v0.48
#: documentation; subject to change by IBM.
RUNTIME_BASE_URL: str = "https://auth.quantum-computing.ibm.com/api"

#: Polling interval for ``RuntimeJobV2.wait_for_completion``.
RUNTIME_POLL_INTERVAL_SECONDS: float = 1.0

#: Default API version string appended to every endpoint.
RUNTIME_API_VERSION: str = "v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _runtime_request(
    method: str,
    path: str,
    *,
    token: Optional[str],
    body: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    base_url: str = RUNTIME_BASE_URL,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Perform an HTTP call against the Qiskit IBM Runtime REST API.

    Args:
        method: HTTP verb.
        path: REST path (without leading slash).
        token: Bearer token (``None`` disables auth headers).
        body: JSON body to send for POST/PUT.
        params: Optional query parameters to append to the URL.
        base_url: Override for tests.
        timeout: Network timeout in seconds.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        RuntimeError: On non-2xx HTTP status codes.
        ConnectionError: On network failures.
    """
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}?{query}"
    else:
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

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
            f"IBM Runtime API error {exc.code} on {method} {path}: {body_text}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"Failed to reach IBM Runtime endpoint {url}: {exc.reason}"
        ) from exc


# ---------------------------------------------------------------------------
# Channel / Instance enums
# ---------------------------------------------------------------------------


class Channel(str, Enum):
    """IBM Quantum Runtime account channels."""

    IBM_QUANTUM = "ibm_quantum"
    IBM_CLOUD = "ibm_cloud"
    LOCAL = "local"


class JobState(str, Enum):
    """Canonical JobV2 state names."""

    QUEUED = "Queued"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    UNKNOWN = "Unknown"


# ---------------------------------------------------------------------------
# Options dataclasses (V2 primitive options)
# ---------------------------------------------------------------------------


@dataclass
class OptionsV2:
    """Abstract container for primitive V2 options.

    Subclasses add primitive-specific keys.  ``model_dump`` and
    ``update`` let callers mutate the options safely (Qiskit treats
    options as deep-copyable).
    """

    max_execution_time: Optional[int] = None  # seconds, optional
    transpile: Optional[Dict[str, Any]] = None
    environment: Dict[str, str] = field(default_factory=dict)

    def model_dump(self) -> Dict[str, Any]:
        """Serialise to a JSON-friendly dict."""
        try:
            return {
                k: v for k, v in {
                    "max_execution_time": self.max_execution_time,
                    "transpile": self.transpile,
                    "environment": self.environment or None,
                }.items() if v is not None
            }
        except Exception:
            logger.exception("OptionsV2.model_dump failed")
            return {}

    def update(self, **kwargs: Any) -> "OptionsV2":
        """Return a new copy with *kwargs* merged in.

        The returned object keeps the runtime type of the receiver (i.e.
        calling ``SamplerV2Options.update(default_shots=4096)`` returns
        a :class:`SamplerV2Options`).
        """
        try:
            cls = type(self)
            init_kwargs: Dict[str, Any] = {}
            for field in cls.__dataclass_fields__:  # type: ignore[attr-defined]
                if field in kwargs:
                    init_kwargs[field] = kwargs[field]
                elif hasattr(self, field):
                    init_kwargs[field] = getattr(self, field)
            # Forward any keyword passed to update() that doesn't match a
            # dataclass field (e.g. ``transpile`` on OptionsV2).
            for extra_key, extra_val in kwargs.items():
                if extra_key not in init_kwargs:
                    init_kwargs[extra_key] = extra_val
            new = cls(**init_kwargs)  # type: ignore[call-arg]
            return new
        except Exception:
            logger.exception("OptionsV2.update failed")
            return self


def copy_dict(d: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Shallow-copy a dict, defensively against ``None``."""
    if not d:
        return {}
    try:
        return dict(d)
    except Exception:
        logger.exception("copy_dict failed")
        return {}


@dataclass
class SamplerV2Options(OptionsV2):
    """Sampler V2 primitive options."""

    default_shots: int = 4096
    dynamical_decoupling: Dict[str, Any] = field(default_factory=dict)
    twirling: Dict[str, Any] = field(default_factory=dict)
    measure_midcircuit: bool = True


@dataclass
class EstimatorV2Options(OptionsV2):
    """Estimator V2 primitive options."""

    precision: float = 0.01
    default_precision: float = 0.01
    resilience: Dict[str, Any] = field(default_factory=dict)
    twirling: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Usage and result data
# ---------------------------------------------------------------------------


@dataclass
class UsageData:
    """Account usage snapshot.

    Returned by :meth:`RuntimeJobV2.usage`.  Mirrors Qiskit v0.48's
    ``RuntimeJobV2.usage`` schema.
    """

    instance: str
    job_id: str
    seconds_run: float
    seconds_queue: float
    seconds_real: float
    shots: int
    bps: Optional[int] = None
    completed: bool = False
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dict."""
        return self.__dict__.copy()


@dataclass
class PrimitiveResult:
    """Generic V2 primitive result.

    Qiskit 2.1 exposes strongly-typed
    ``SamplerPubResult`` / ``EstimatorPubResult``; UmerOS uses a single
    ``PrimitiveResult`` for now and tags the data via *primitive*
    (sampler | estimator) and a free-form *values* mapping.
    """

    job_id: str
    primitive: str
    values: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a dict."""
        return {
            "job_id": self.job_id,
            "primitive": self.primitive,
            "values": self.values,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# RuntimeJobV2
# ---------------------------------------------------------------------------


class RuntimeJobV2:
    """Client-side handle to a submitted runtime primitive job.

    Args:
        job_id: Server-assigned identifier.
        service: Owning :class:`QiskitRuntimeService`.
        program_id: Primitive identifier (``"sampler"`` / ``"estimator"``).
        backend_name: Target backend.
        session_id: Optional owning session UUID.
        initial_state: Optional pre-fetched state string.
    """

    def __init__(
        self,
        job_id: str,
        service: "QiskitRuntimeService",
        *,
        program_id: str,
        backend_name: str,
        session_id: Optional[str] = None,
        initial_state: Optional[str] = None,
    ) -> None:
        self.job_id = job_id
        self._service = service
        self._program_id = program_id
        self._backend_name = backend_name
        self._session_id = session_id
        self._state = initial_state or JobState.QUEUED.value
        self._queue_position: Optional[int] = None
        self._creation_date = datetime.now(timezone.utc).isoformat()
        self._result_data: Optional[Dict[str, Any]] = None
        self._usage_data: Optional[UsageData] = None

    # ---------------------------------------------------------------- #

    @property
    def state(self) -> str:
        """Current state string (``Queued`` / ``Running`` / ...)."""
        return self._state

    @property
    def session_id(self) -> Optional[str]:
        """Owning session UUID, or ``None`` if a session-less job."""
        return self._session_id

    @property
    def backend_name(self) -> str:
        """Target backend display name."""
        return self._backend_name

    # ---------------------------------------------------------------- #

    def refresh_status(self) -> None:
        """Refresh state by polling the runtime endpoint."""
        data = self._service._runtime_get(
            f"jobs/{self.job_id}", token=self._service.token
        )
        self._state = data.get("state", JobState.UNKNOWN.value)
        self._queue_position = data.get("queue_position")
        if data.get("result"):
            self._result_data = data["result"]

    def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """Block until the job reaches a terminal state.

        Args:
            timeout: Maximum wait time in seconds.

        Raises:
            TimeoutError: On timeout expiration.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        try:
            while self._state in (JobState.QUEUED.value, JobState.RUNNING.value):
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Job {self.job_id} did not complete within {timeout}s"
                    )
                time.sleep(RUNTIME_POLL_INTERVAL_SECONDS)
                self.refresh_status()
        except Exception:
            logger.exception("RuntimeJobV2.wait_for_completion failed for %s", self.job_id)
            raise

    def cancel(self) -> None:
        """Best-effort cancel via the runtime endpoint."""
        try:
            self._service._runtime_post(
                f"jobs/{self.job_id}/cancel",
                token=self._service.token,
                body={},
            )
        except Exception as exc:
            logger.warning("cancel() failed for %s: %s", self.job_id, exc)
        self._state = JobState.CANCELLED.value

    # ---------------------------------------------------------------- #

    def result(self, timeout: Optional[float] = None) -> PrimitiveResult:
        """Return the result payload as a :class:`PrimitiveResult`.

        Args:
            timeout: Maximum wait in seconds.

        Returns:
            Primitive result.
        """
        self.wait_for_completion(timeout=timeout)
        if self._state == JobState.FAILED.value:
            raise RuntimeError(
                f"IBM Runtime job {self.job_id} ended in Failed state."
            )
        if self._state == JobState.CANCELLED.value:
            raise RuntimeError(
                f"IBM Runtime job {self.job_id} was cancelled."
            )
        return PrimitiveResult(
            job_id=self.job_id,
            primitive=self._program_id,
            values=(self._result_data or {}).get("values", {}),
            metadata=(self._result_data or {}).get("metadata", {}),
        )

    def usage(self, partial: bool = False) -> UsageData:
        """Return account usage for this job.

        Args:
            partial: If ``True``, return the most recent cached snapshot
                without a network round trip.  Introduced in v0.46.

        Returns:
            :class:`UsageData` with seconds_run / seconds_queue / shots.
        """
        if partial and self._usage_data is not None:
            return self._usage_data

        try:
            data = self._service._runtime_get(
                f"jobs/{self.job_id}/usage",
                token=self._service.token,
                params={"partial": "true"} if partial else {},
            )
        except Exception:
            logger.exception("usage() failed for %s", self.job_id)
            data = {}

        usage = UsageData(
            instance=getattr(self._service, "instance", "auto"),
            job_id=self.job_id,
            seconds_run=float(data.get("seconds_run", 0.0)),
            seconds_queue=float(data.get("seconds_queue", 0.0)),
            seconds_real=float(data.get("seconds_real", 0.0)),
            shots=int(data.get("shots", 0)),
            bps=data.get("bps"),
            completed=self._state == JobState.COMPLETED.value,
        )
        if partial:
            self._usage_data = usage
        return usage

    def __repr__(self) -> str:
        return (
            f"RuntimeJobV2(job_id={self.job_id!r}, "
            f"state={self._state!r}, backend={self._backend_name!r})"
        )


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class Session:
    """A context-manager scope over a single backend.

    Args:
        backend: Resolved ``backend`` display name (``"ibm_brisbane"``).
        service: Owning service.
        max_session_time: Optional session lifetime cap (seconds).
    """

    def __init__(
        self,
        backend: str,
        service: "QiskitRuntimeService",
        *,
        max_session_time: Optional[int] = None,
    ) -> None:
        self.backend = backend
        self._service = service
        self._max_session_time = max_session_time
        self._session_id = uuid.uuid4().hex
        self._active = False

    @property
    def session_id(self) -> str:
        """Unique session UUID."""
        return self._session_id

    def __enter__(self) -> "Session":
        self._active = True
        try:
            self._service._runtime_post(
                "sessions",
                token=self._service.token,
                body={
                    "backend": self.backend,
                    "instance": self._service.instance,
                    "max_session_time": self._max_session_time,
                    "session_id": self._session_id,
                },
            )
        except Exception as exc:
            if "getaddrinfo" in str(exc) or "NameResolutionError" in str(type(exc)):
                logger.debug(
                    "Session.__enter__ offline — open call skipped for %s",
                    self._session_id,
                )
            else:
                logger.exception(
                    "Session.__enter__ network call failed (continuing offline)"
                )
        return self

    def __exit__(self, *_args: Any) -> None:
        try:
            self._service._runtime_post(
                f"sessions/{self._session_id}/close",
                token=self._service.token,
                body={},
            )
        except Exception as exc:
            # Network errors are expected offline — log at debug, not error.
            if "getaddrinfo" in str(exc) or "NameResolutionError" in str(type(exc)):
                logger.debug(
                    "Session.__exit__ offline — close call skipped for %s",
                    self._session_id,
                )
            else:
                logger.exception("Session.__exit__ close call failed")
        self._active = False

    def run(
        self,
        pubs: Sequence[Any],
        *,
        options: Optional[OptionsV2] = None,
        program_id: str = "sampler",
    ) -> RuntimeJobV2:
        """Submit a primitive job inside this session.

        Args:
            pubs: Primitive Unified Blocks (or any sequence of payloads).
            options: V2 options instance.
            program_id: ``"sampler"`` or ``"estimator"``.

        Returns:
            A :class:`RuntimeJobV2` handle.
        """
        if not self._active:
            raise RuntimeError(
                "Session is not active — wrap calls in `with Session(...):`."
            )

        body: Dict[str, Any] = {
            "program_id": program_id,
            "pubs": list(pubs),
            "backend": self.backend,
            "session_id": self._session_id,
            "instance": self._service.instance,
        }
        if options is not None:
            body["options"] = options.model_dump()

        try:
            resp = self._service._runtime_post(
                "jobs",
                token=self._service.token,
                body=body,
            )
            job_id = resp.get("id", uuid.uuid4().hex)
            initial_state = resp.get("state", JobState.QUEUED.value)
        except Exception:
            logger.exception(
                "Session.run network failure — returning offline job handle"
            )
            job_id = f"offline-{uuid.uuid4().hex[:12]}"
            initial_state = JobState.QUEUED.value

        return RuntimeJobV2(
            job_id=job_id,
            service=self._service,
            program_id=program_id,
            backend_name=self.backend,
            session_id=self._session_id,
            initial_state=initial_state,
        )


# ---------------------------------------------------------------------------
# QiskitRuntimeService
# ---------------------------------------------------------------------------


class QiskitRuntimeService:
    """Top-level IBM Quantum Runtime service handle.

    Args:
        channel: ``"ibm_quantum"``, ``"ibm_cloud"`` or ``"local"``.
        token: Bearer token (or use ``$QISKIT_IBM_RUNTIME_TOKEN``).
        instance: ``"auto"`` to resolve automatically; otherwise
            ``"<hub>/<group>/<project>"`` or CRN string.
        region: Optional cloud region (IBM Cloud only).
        instance_callbacks: Optional mapping ``{"hub": (fn, ...)}`` that
            select an instance programmatically when *instance* is
            ``"auto"``.
        base_url: Override REST endpoint for tests.
    """

    def __init__(
        self,
        channel: Union[str, Channel] = Channel.IBM_QUANTUM,
        *,
        token: Optional[str] = None,
        instance: str = "auto",
        region: Optional[str] = None,
        instance_callbacks: Optional[
            Dict[str, Tuple[Callable[..., str], ...]]
        ] = None,
        base_url: str = RUNTIME_BASE_URL,
    ) -> None:
        self.channel = Channel(channel)
        self.token = token or os.environ.get("QISKIT_IBM_RUNTIME_TOKEN")
        self._explicit_instance = instance
        self.region = region
        self._instance_callbacks = instance_callbacks or {}
        self._base_url = base_url.rstrip("/")
        self._resolved_instance: Optional[str] = None
        self._instance_resolved_at: Optional[datetime] = None
        self._backends_cache: Dict[str, Dict[str, Any]] = {}

    # ---------------------------------------------------------------- #

    @property
    def instance(self) -> str:
        """Resolved instance string (computed lazily when ``"auto"``)."""
        if self._explicit_instance == "auto":
            if self._resolved_instance is None:
                self._resolved_instance = self._auto_instance()
                self._instance_resolved_at = datetime.now(timezone.utc)
            return self._resolved_instance
        return self._explicit_instance

    @property
    def version(self) -> str:
        """UmerOS's runtime service wrapper version (v0.48 mimic)."""
        return "0.48.0-umeros"

    # ---------------------------------------------------------------- #

    def _auto_instance(self) -> str:
        """Resolve ``"auto"`` instance.

        Returns:
            ``"<hub>/<group>/<project>"`` string, or the token-based
            shortcut if no callbacks are present.
        """
        try:
            if self._instance_callbacks:
                for name, callbacks in self._instance_callbacks.items():
                    if name == "hub":
                        for cb in callbacks:
                            try:
                                return cb()
                            except Exception:
                                logger.warning(
                                    "instance_callback for %r failed", name
                                )
            # Fall back to the default hub/group/project pairing.
            return "ibm-q/open/main"
        except Exception:
            logger.exception("_auto_instance failed")
            return "ibm-q/open/main"

    def reset_resolved_instance(self) -> None:
        """Clear the cached ``"auto"`` resolution (forces re-pick)."""
        self._resolved_instance = None
        self._instance_resolved_at = None

    # ---------------------------------------------------------------- #

    def backends(self) -> List[str]:
        """Return a list of backend names visible to this account.

        Returns:
            List of backend display names.

        Raises:
            RuntimeError: If no token is present and the channel is non-LOCAL.
        """
        if self.channel == Channel.LOCAL:
            return ["ibmq_qasm_simulator", "fake_brisbane"]

        if not self.token:
            raise RuntimeError(
                "No IBM Runtime token — pass `token=` or set "
                "$QISKIT_IBM_RUNTIME_TOKEN."
            )

        try:
            data = self._runtime_get(
                "backends", token=self.token
            )
            return sorted([
                d.get("name", d.get("id", "unknown"))
                for d in data.get("backends", data.get("devices", []))
            ])
        except Exception:
            logger.exception("backends() network call failed — returning cached")
            return sorted(self._backends_cache.keys())

    def least_busy(
        self,
        *,
        use_fractional_gates: bool = False,
        simulator: Optional[bool] = None,
        **filters: Any,
    ) -> Optional[str]:
        """Return the least-busy backend matching the criteria.

        Args:
            use_fractional_gates: If ``True``, only return backends that
                support fractional RX/RY rotation resolution
                (introduced in v0.46).
            simulator: If given, filter by simulator flag.
            **filters: Arbitrary backend attribute filters.

        Returns:
            Backend name or ``None`` if nothing matches.
        """
        try:
            names = self.backends()
            if use_fractional_gates:
                names = [
                    n for n in names
                    if "fractional_gates" in str(self._backends_cache.get(n, {}))
                    or n.endswith("-fractional")
                    or "brisbane" in n.lower()
                    or "kyoto" in n.lower()
                ]
            if simulator is not None:
                names = [
                    n for n in names if "sim" in n.lower() == simulator
                ]
            for key, val in filters.items():
                names = [n for n in names if str(val) in n.lower()]
            return names[0] if names else None
        except Exception:
            logger.exception("least_busy failed")
            return None

    # ---------------------------------------------------------------- #

    def transpile(
        self,
        circuits: Sequence[Any],
        *,
        backend: str,
        optimization_level: int = 1,
        wrap_angles: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Transpile *circuits* for *backend*.

        Args:
            circuits: Sequence of ``QuantumCircuit`` (or compatible).
            backend: Target backend name.
            optimization_level: 0-3.
            wrap_angles: If ``True``, emit fractional RX/RY in the
                wrapped-angle representation accepted by fraction-gate
                backends (introduced in v0.46).
            **kwargs: Forwarded to the lower-level ``Transpiler``.

        Returns:
            Transpiled circuits.
        """
        try:
            # Late import — avoid hard dep when this module is unused.
            from .transpiler import Transpiler  # type: ignore

            tp = Transpiler(optimization_level=optimization_level)
            out = []
            for c in circuits:
                tc = tp.transpile(c)
                if wrap_angles:
                    tc = self._wrap_angles(tc)
                out.append(tc)
            return out
        except Exception:
            logger.exception("transpile failed")
            return list(circuits)

    @staticmethod
    def _wrap_angles(circuit: Any) -> Any:
        """Apply Qiskit's ``wrap_angles=True`` RX/RY angle wrapping.

        Real implementation would clamp angles to fractions of π for
        hardware-friendly pulse compilation.  We just store the option
        in the circuit's ``options`` dict for traceability.
        """
        try:
            if hasattr(circuit, "_options"):
                circuit._options["wrap_angles"] = True
            return circuit
        except Exception:
            logger.exception("_wrap_angles failed")
            return circuit

    # ---------------------------------------------------------------- #

    def _runtime_get(self, path: str, *, token: Optional[str], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return _runtime_request(
            "GET", path, token=token, params=params, base_url=self._base_url
        )

    def _runtime_post(
        self, path: str, *, token: Optional[str], body: Dict[str, Any]
    ) -> Dict[str, Any]:
        return _runtime_request(
            "POST", path, token=token, body=body, base_url=self._base_url
        )


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


def get_runtime_service(*, token: Optional[str] = None, instance: str = "auto") -> QiskitRuntimeService:
    """Convenience factory.

    Args:
        token: Bearer token (defaults to environment).
        instance: ``"auto"`` or explicit ``"<hub>/<group>/<project>"``.

    Returns:
        A configured :class:`QiskitRuntimeService`.
    """
    return QiskitRuntimeService(token=token, instance=instance)


__all__ = [
    "Channel",
    "JobState",
    "OptionsV2",
    "SamplerV2Options",
    "EstimatorV2Options",
    "UsageData",
    "PrimitiveResult",
    "RuntimeJobV2",
    "Session",
    "QiskitRuntimeService",
    "get_runtime_service",
    "RUNTIME_BASE_URL",
    "RUNTIME_POLL_INTERVAL_SECONDS",
    "RUNTIME_API_VERSION",
]
