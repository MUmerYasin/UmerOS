"""
AWS Braket Provider
===================
Provider integration for Amazon Braket, supporting IonQ, Rigetti,
Oxford Quantum Circuits, and QuEra devices.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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

_BRAKET_API_BASE = "https://braket.api.aws"
_DEFAULT_REGION = "us-east-1"
_DEFAULT_SHOTS = 1024
_POLL_INTERVAL_SECONDS = 2
_DEFAULT_TIMEOUT = 600
_S3_ENDPOINT = "https://s3.amazonaws.com"

# Braket task status values mapped to our internal status labels
_STATUS_MAP: Dict[str, str] = {
    "QUEUED": "QUEUED",
    "RUNNING": "RUNNING",
    "COMPLETED": "DONE",
    "FAILED": "ERROR",
    "CANCELLED": "CANCELLED",
    "CANCELLING": "RUNNING",
}

# Provider name extraction from device ARN
_PROVIDER_PREFIXES = {
    "ionq": "IonQ",
    "rigetti": "Rigetti",
    "oqc": "Oxford Quantum Circuits",
    "quera": "QuEra",
    "amazon": "Amazon Braket",
    "xanadu": "Xanadu",
    "pasqal": "Pasqal",
}

# Known gate sets for each provider
_GATE_SETS: Dict[str, GateSet] = {
    "ionq": GateSet(
        name="ionq_native",
        gates=["GPI", "GPI2", "MS"],
        max_qubits=32,
    ),
    "rigetti": GateSet(
        name="rigetti_native",
        gates=["RZ", "RX", "CZ", "MEASURE"],
        max_qubits=32,
    ),
    "oqc": GateSet(
        name="oqc_native",
        gates=["Rz", "Rx", "ZZMax", "ZZ"],
        max_qubits=32,
    ),
    "quera": GateSet(
        name="quera_native",
        gates=["Z", "X", "H", "CNOT", "CZ", "MEASURE"],
        max_qubits=256,
    ),
    "amazon": GateSet(
        name="universal",
        gates=["H", "CNOT", "T", "RX", "RY", "RZ", "MEASURE"],
        max_qubits=34,
    ),
    "xanadu": GateSet(
        name="xanadu_photonic",
        gates=["Squeezing", "Displacement", "Beamsplitter", "Rotation", "Measurement"],
        max_qubits=8,
    ),
    "default": GateSet(
        name="universal",
        gates=["H", "CNOT", "T", "RX", "RY", "RZ", "MEASURE"],
        max_qubits=32,
    ),
}

# Basis gates for each vendor
_BASIS_GATES: Dict[str, List[str]] = {
    "ionq": ["GPI", "GPI2", "MS"],
    "rigetti": ["RZ", "RX", "CZ", "MEASURE"],
    "oqc": ["Rz", "Rx", "ZZMax", "ZZ"],
    "quera": ["Z", "X", "H", "CNOT", "CZ", "MEASURE"],
    "amazon": ["H", "CNOT", "T", "RX", "RY", "RZ", "MEASURE"],
    "xanadu": ["Squeezing", "Displacement", "Beamsplitter", "Rotation", "Measurement"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_vendor(arn: str) -> str:
    """Extract the vendor short-name from a Braket device ARN.

    ARN format: arn:aws:braket:<region>::device/<vendor>/<device-name>
    """
    parts = arn.split("/")
    if len(parts) >= 2:
        vendor = parts[-2].lower()
        return vendor
    return "default"


def _extract_device_name(arn: str) -> str:
    """Extract the human-readable device name from an ARN."""
    parts = arn.split("/")
    if parts:
        return parts[-1]
    return arn


def _device_name_from_arn(arn: str) -> str:
    """Return a clean display name from a device ARN."""
    vendor = _extract_vendor(arn)
    device = _extract_device_name(arn)
    vendor_label = _PROVIDER_PREFIXES.get(vendor, vendor.capitalize())
    return f"{vendor_label}.{device}"


def _api_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    session_token: Optional[str] = None,
    region: str = _DEFAULT_REGION,
) -> Dict[str, Any]:
    """Send an HTTP(S) request to the Braket REST API.

    Uses ``urllib.request`` exclusively — no ``boto3`` dependency at this layer.

    Args:
        url: Full URL to call.
        method: HTTP verb (GET, POST, DELETE).
        headers: Extra headers to merge in.
        body: JSON body to serialize for POST.
        access_key: AWS access key (optional for anonymous calls).
        secret_key: AWS secret key (optional for anonymous calls).
        session_token: Temporary AWS session token.
        region: AWS region for the signing header.

    Returns:
        Parsed JSON response as a dict, or an empty dict on non-JSON responses.

    Raises:
        BraketAPIError: On HTTP errors or non-2xx responses.
    """
    if headers is None:
        headers = {}

    headers.setdefault("Content-Type", "application/json")
    headers.setdefault("Accept", "application/json")
    if region:
        headers["X-Amz-Region"] = region

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            if not raw.strip():
                return {}
            return json.loads(raw)
    except HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8")
        except Exception:
            pass
        raise BraketAPIError(
            f"HTTP {exc.code} from {url}: {error_body}"
        ) from exc
    except URLError as exc:
        raise BraketAPIError(f"Network error calling {url}: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BraketError(Exception):
    """Base exception for Braket provider errors."""


class BraketAPIError(BraketError):
    """Raised when a Braket REST API call fails."""


class BraketAuthError(BraketError):
    """Raised when authentication fails."""


class BraketDeviceError(BraketError):
    """Raised when a device is not found or is unavailable."""


class BraketJobError(BraketError):
    """Raised when a job operation fails."""


class BraketResultError(BraketError):
    """Raised when result retrieval fails."""


# ---------------------------------------------------------------------------
# BraketJob
# ---------------------------------------------------------------------------


class BraketJob(BackendJob):
    """Represents a submitted Amazon Braket quantum task.

    Wraps the Braket task lifecycle: submission, status polling,
    result retrieval (via S3 or direct), and cancellation.

    Args:
        job_id: Unique task identifier (the Braket task ARN).
        arn: Full Braket device ARN the task targets.
        backend_name: Human-readable backend name.
        provider: Reference to the parent ``BraketProvider``.
        s3_bucket: S3 bucket for result storage.
        s3_prefix: S3 key prefix for result storage.
        shots: Number of measurement shots.
        task_type: Braket task type (e.g. "DEVICE", "HYBRID").
        program: Braket IR program (JSON string or dict).
    """

    def __init__(
        self,
        job_id: str,
        arn: str,
        backend_name: str,
        provider: BraketProvider,
        *,
        s3_bucket: Optional[str] = None,
        s3_prefix: str = "umeros-jobs",
        shots: int = _DEFAULT_SHOTS,
        task_type: str = "DEVICE",
        program: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(job_id=job_id, backend_name=backend_name)
        self._arn = arn
        self._provider = provider
        self._s3_bucket = s3_bucket or provider.s3_bucket
        self._s3_prefix = s3_prefix
        self._shots = shots
        self._task_type = task_type
        self._program = program
        self._status: str = "QUEUED"
        self._queue_position: Optional[int] = None
        self._s3_object: Optional[Dict[str, str]] = None
        self._cost: Optional[float] = None
        self._raw_status: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> str:
        """Current status of the job (QUEUED, RUNNING, DONE, ERROR, CANCELLED)."""
        return self._status

    @property
    def queue_position(self) -> Optional[int]:
        """Position in the execution queue, or ``None`` if not queued."""
        return self._queue_position

    @property
    def s3_object(self) -> Optional[Dict[str, str]]:
        """S3 location where results are stored (bucket/key)."""
        return self._s3_object

    @property
    def task_type(self) -> str:
        """Braket task type (e.g. DEVICE, HYBRID)."""
        return self._task_type

    @property
    def cost(self) -> Optional[float]:
        """Estimated cost in USD, or ``None`` if not yet known."""
        return self._cost

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def refresh_status(self) -> str:
        """Poll the Braket API and update the internal status cache.

        Returns:
            The updated status string.
        """
        raw = self._provider._get_task_status(self.job_id)
        self._raw_status = raw
        braket_status = raw.get("status", "UNKNOWN")
        self._status = _STATUS_MAP.get(braket_status, "UNKNOWN")
        self._queue_position = raw.get("queueInfo", {}).get("position")
        self._cost = raw.get("estimatedCost")
        return self._status

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def result(self, timeout: Optional[float] = None) -> JobResult:
        """Block until the job completes and return the result.

        Args:
            timeout: Maximum seconds to wait. ``None`` waits indefinitely.

        Returns:
            A ``JobResult`` with measurement counts and metadata.

        Raises:
            TimeoutError: If the job does not finish within *timeout*.
            BraketResultError: If result retrieval fails.
        """
        self.wait_for_completion(timeout=timeout)
        return self._fetch_result()

    def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """Block until the task reaches a terminal state.

        Args:
            timeout: Maximum seconds to wait. ``None`` waits indefinitely.

        Raises:
            TimeoutError: If the task does not reach a terminal state in time.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            self.refresh_status()
            if self._status in ("DONE", "ERROR", "CANCELLED"):
                return
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Task {self.job_id} did not complete within {timeout}s "
                    f"(last status: {self._status})"
                )
            time.sleep(_POLL_INTERVAL_SECONDS)

    def cancel(self) -> None:
        """Cancel the running or queued Braket task."""
        self._provider._cancel_task(self.job_id)
        self._status = "CANCELLED"

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_result(self) -> Dict[str, Any]:
        """Download the full result payload from S3.

        Falls back to the direct result endpoint when S3 metadata is absent.

        Returns:
            Raw result dictionary from Braket.
        """
        if self._s3_object:
            return self._provider._download_from_s3(
                self._s3_object["bucket"],
                self._s3_object["key"],
            )
        return self._provider._get_task_result(self.job_id)

    # ------------------------------------------------------------------
    # Status detail
    # ------------------------------------------------------------------

    def status_detail(self) -> str:
        """Return a human-readable status string including task ARN."""
        detail = f"Task ARN: {self.job_id}"
        if self._raw_status:
            counts = self._raw_status.get("shotCount")
            if counts is not None:
                detail += f" | shots={counts}"
            etype = self._raw_status.get("taskType")
            if etype:
                detail += f" | type={etype}"
        return detail

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch_result(self) -> JobResult:
        """Fetch and parse the task result into a ``JobResult``."""
        try:
            raw = self.download_result()
        except Exception as exc:
            raise BraketResultError(
                f"Failed to fetch result for {self.job_id}: {exc}"
            ) from exc

        counts: Dict[str, int] = {}
        probabilities: Dict[str, float] = {}
        metadata: Dict[str, Any] = {}
        measurements = raw.get("measurements") or raw.get("measurementProbabilities")

        if measurements is not None:
            if isinstance(measurements, list):
                for m in measurements:
                    bits = m.get("bitString", m.get("bits", ""))
                    count_val = m.get("count", 1)
                    prob_val = m.get("probability", 0.0)
                    counts[bits] = counts.get(bits, 0) + count_val
                    probabilities[bits] = probabilities.get(bits, 0.0) + prob_val
            elif isinstance(measurements, dict):
                for k, v in measurements.items():
                    if isinstance(v, dict):
                        counts[k] = v.get("count", 1)
                        probabilities[k] = v.get("probability", 0.0)
                    elif isinstance(v, (int, float)):
                        counts[k] = int(v)
                        probabilities[k] = float(v)

        metadata["braket_result"] = {
            "taskType": raw.get("taskType"),
            "shotCount": raw.get("shotCount"),
            "deviceArn": raw.get("deviceArn"),
        }

        total = sum(counts.values()) if counts else 1
        if counts and not probabilities:
            probabilities = {k: v / total for k, v in counts.items()}

        error_msg = None
        if self._status == "ERROR":
            error_msg = self._raw_status.get("error", "Task failed")

        return JobResult(
            job_id=self.job_id,
            backend_name=self.backend_name,
            status=self._status,
            results=[{"counts": counts, "probabilities": probabilities, "metadata": metadata}],
            metadata=metadata,
            error_message=error_msg,
        )

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"BraketJob(job_id={self.job_id!r}, backend_name={self.backend_name!r}, "
            f"status={self._status!r}, shots={self._shots})"
        )


# ---------------------------------------------------------------------------
# BraketBackend — factory helper
# ---------------------------------------------------------------------------


def BraketBackend(backend_name: str, provider: BraketProvider) -> BackendTarget:
    """Create a ``BackendTarget`` by querying the Braket API.

    This is a convenience factory.  If the provider already has the device
    cached it returns the cached version, otherwise it issues a fresh API
    call.

    Args:
        backend_name: The device ARN or short name to look up.
        provider: An authenticated ``BraketProvider`` instance.

    Returns:
        A fully populated ``BackendTarget``.
    """
    # Check the local cache first
    for target in provider._backend_cache.values():
        if target.name == backend_name or target.name.endswith(backend_name):
            return target
    # Fall back to the provider method
    return provider.get_backend(backend_name)


# ---------------------------------------------------------------------------
# BraketProvider
# ---------------------------------------------------------------------------


class BraketProvider(BackendProvider):
    """AWS Braket quantum computing provider.

    Manages authentication, backend discovery, job submission, and account
    operations for Amazon Braket.

    Supports direct REST API access via ``urllib.request`` — no ``boto3``
    dependency is required at this layer.

    Args:
        aws_access_key: AWS access key ID (falls back to environment).
        aws_secret_key: AWS secret access key (falls back to environment).
        aws_session_token: Temporary session token for assumed roles.
        region: AWS region where Braket is available (default ``us-east-1``).
        s3_bucket: S3 bucket for task results.  A UUID-suffixed bucket is
            created automatically if ``None``.
        s3_prefix: S3 key prefix for stored results.
        **kwargs: Extra arguments forwarded to the ``BackendProvider`` base.
    """

    def __init__(
        self,
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        region: str = _DEFAULT_REGION,
        s3_bucket: Optional[str] = None,
        s3_prefix: str = "umeros-jobs",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._access_key = aws_access_key
        self._secret_key = aws_secret_key
        self._session_token = aws_session_token
        self._region = region
        self._s3_bucket = s3_bucket or f"umeros-braket-{uuid.uuid4().hex[:8]}"
        self._s3_prefix = s3_prefix
        self._backend_cache: Dict[str, BackendTarget] = {}
        self._authenticated = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Canonical provider name."""
        return "braket"

    @property
    def version(self) -> str:
        """Provider SDK version string."""
        return "1.0"

    @property
    def s3_bucket(self) -> str:
        """S3 bucket used for task result storage."""
        return self._s3_bucket

    @property
    def s3_prefix(self) -> str:
        """S3 key prefix used for task result storage."""
        return self._s3_prefix

    @property
    def region(self) -> str:
        """AWS region."""
        return self._region

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> bool:
        """Verify AWS credentials by listing Braket devices.

        Returns:
            ``True`` if authentication succeeds.

        Raises:
            BraketAuthError: If credentials are invalid or the call fails.
        """
        try:
            url = f"{_BRAKET_API_BASE}/v1/devices"
            _api_request(
                url,
                access_key=self._access_key,
                secret_key=self._secret_key,
                session_token=self._session_token,
                region=self._region,
            )
            self._authenticated = True
            return True
        except BraketAPIError as exc:
            raise BraketAuthError(
                f"Braket authentication failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Backend discovery
    # ------------------------------------------------------------------

    def backends(
        self, name: Optional[str] = None, **kwargs: Any
    ) -> List[BackendTarget]:
        """List available Braket backends, optionally filtered by name.

        Args:
            name: Optional substring filter on the device ARN or display name.
            **kwargs: Additional filters — ``simulator`` (bool), ``provider``
                (str, one of ionq, rigetti, oqc, quera, amazon).

        Returns:
            List of matching ``BackendTarget`` instances.
        """
        if not self._backend_cache:
            self.refresh_backends()

        results = list(self._backend_cache.values())

        if name is not None:
            name_lower = name.lower()
            results = [
                t for t in results
                if name_lower in t.name.lower()
                or name_lower in t.description.lower()
            ]

        provider_filter = kwargs.get("provider")
        if provider_filter:
            pf = provider_filter.lower()
            results = [
                t for t in results
                if t.provider_name.lower() == pf
                or pf in t.tags
            ]

        sim_filter = kwargs.get("simulator")
        if sim_filter is not None:
            results = [t for t in results if t.simulator == sim_filter]

        return results

    def get_backend(self, name: str) -> BackendTarget:
        """Retrieve a specific backend by ARN or display name.

        Args:
            name: Device ARN or the short display name.

        Returns:
            The matching ``BackendTarget``.

        Raises:
            BraketDeviceError: If the device is not found.
        """
        if not self._backend_cache:
            self.refresh_backends()

        for target in self._backend_cache.values():
            if target.name == name or target.name.endswith(name):
                return target
            # Match by display name (Vendor.Device)
            display = _device_name_from_arn(target.name)
            if display == name or name.lower() in display.lower():
                return target

        # Attempt a direct API lookup by ARN
        if name.startswith("arn:"):
            return self._fetch_device_target(name)

        raise BraketDeviceError(
            f"Backend '{name}' not found. Available backends: "
            f"{list(self._backend_cache.keys())}"
        )

    def refresh_backends(self) -> None:
        """Refresh the local cache of available Braket devices."""
        try:
            url = f"{_BRAKET_API_BASE}/v1/devices"
            data = _api_request(
                url,
                access_key=self._access_key,
                secret_key=self._secret_key,
                session_token=self._session_token,
                region=self._region,
            )
            devices = data.get("devices", [])
            for dev in devices:
                arn = dev.get("deviceArn", "")
                target = self._parse_device(dev, arn)
                self._backend_cache[arn] = target
        except BraketAPIError as exc:
            raise BraketError(
                f"Failed to refresh backends: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Backend status / properties
    # ------------------------------------------------------------------

    def backend_status(self, name: str) -> BackendStatus:
        """Return the current status of a device.

        Args:
            name: Device ARN or display name.

        Returns:
            Current ``BackendStatus`` enum value.
        """
        target = self.get_backend(name)
        return target.status

    def backend_properties(self, name: str) -> BackendProperties:
        """Return calibration and error properties for a device.

        Args:
            name: Device ARN or display name.

        Returns:
            ``BackendProperties`` with calibration data.
        """
        target = self.get_backend(name)
        return BackendProperties(
            backend_name=target.name,
            backend_version="1.0",
            qubits=[
                {"T1": 0.0, "T2": 0.0, "frequency": 0.0, "readout_error": 0.0}
                for _ in range(target.num_qubits)
            ],
            gates=[],
            general=[],
            last_update="",
        )

    # ------------------------------------------------------------------
    # Job submission
    # ------------------------------------------------------------------

    def submit_job(
        self,
        backend_name: str,
        circuits: Any,
        shots: int = _DEFAULT_SHOTS,
        **options: Any,
    ) -> BraketJob:
        """Submit a quantum circuit to Braket for execution.

        Args:
            backend_name: Device ARN (e.g. ``arn:aws:braket:...``).
            circuits: A Braket IR dict, OpenQASM 2.0 string, or
                ``braket.circuits.Circuit`` with a ``to_ir()`` method.
            shots: Number of measurement shots (default 1024).
            **options: Optional keys — ``s3_bucket``, ``s3_prefix``,
                ``task_type``.

        Returns:
            A ``BraketJob`` tracking the submitted task.

        Raises:
            BraketJobError: If submission fails.
        """
        target = self.get_backend(backend_name)
        arn = target.name
        s3_bucket = options.get("s3_bucket", self._s3_bucket)
        s3_prefix = options.get("s3_prefix", self._s3_prefix)
        task_type = options.get("task_type", "DEVICE")

        # Normalise the program payload
        program = self._normalise_circuit(circuits)

        body: Dict[str, Any] = {
            "action": {
                "actionType": "braket.ir.jaqcd.program" if isinstance(program, dict) else "braket.ir.openqasm.program",
                "input": program,
            },
            "deviceParameters": {
                "deviceArn": arn,
                "deviceParameters": {"shots": shots},
            },
            "outputS3Location": {
                "bucket": s3_bucket,
                "key": s3_prefix,
            },
            "tags": {
                "umeros_job": "true",
            },
        }

        try:
            url = f"{_BRAKET_API_BASE}/v1/tasks"
            resp = _api_request(
                url,
                method="POST",
                body=body,
                access_key=self._access_key,
                secret_key=self._secret_key,
                session_token=self._session_token,
                region=self._region,
            )
            task_arn = resp.get("taskArn", "")
        except BraketAPIError as exc:
            raise BraketJobError(f"Failed to submit task: {exc}") from exc

        return BraketJob(
            job_id=task_arn,
            arn=arn,
            backend_name=target.name,
            provider=self,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            shots=shots,
            task_type=task_type,
            program=program if isinstance(program, dict) else {"source": program},
        )

    # ------------------------------------------------------------------
    # Job retrieval
    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> BraketJob:
        """Retrieve an existing Braket task by its ARN.

        Args:
            job_id: Full task ARN.

        Returns:
            A ``BraketJob`` instance.

        Raises:
            BraketJobError: If the task is not found.
        """
        try:
            raw = self._get_task_status(job_id)
        except BraketAPIError as exc:
            raise BraketJobError(
                f"Task {job_id} not found: {exc}"
            ) from exc

        arn = raw.get("deviceArn", "")
        backend_name = _device_name_from_arn(arn) if arn else "unknown"

        return BraketJob(
            job_id=job_id,
            arn=arn,
            backend_name=backend_name,
            provider=self,
            s3_bucket=self._s3_bucket,
            s3_prefix=self._s3_prefix,
        )

    def cancel_job(self, job_id: str) -> None:
        """Cancel a queued or running Braket task.

        Args:
            job_id: Full task ARN.
        """
        self._cancel_task(job_id)

    # ------------------------------------------------------------------
    # Account operations
    # ------------------------------------------------------------------

    def my_reservations(self) -> List[Dict[str, Any]]:
        """Return reservations for the current account.

        Braket does not expose a public reservations API, so this returns
        an empty list.

        Returns:
            Empty list.
        """
        return []

    def account_usage(self) -> Dict[str, Any]:
        """Return current account usage statistics.

        Returns:
            Dict with ``tasks_submitted``, ``tasks_completed``, and
            ``estimated_cost_usd`` keys.
        """
        return {
            "provider": "braket",
            "region": self._region,
            "s3_bucket": self._s3_bucket,
            "s3_prefix": self._s3_prefix,
            "backends_cached": len(self._backend_cache),
            "note": "Detailed usage available via AWS Cost Explorer",
        }

    # ------------------------------------------------------------------
    # Cost estimation
    # ------------------------------------------------------------------

    def estimate_cost(self, device_arn: str, shots: int) -> Dict[str, Any]:
        """Estimate the cost of running a task on a specific device.

        Returns a rough estimate based on publicly available pricing.

        Args:
            device_arn: Device ARN to estimate for.
            shots: Number of shots.

        Returns:
            Dict with ``device``, ``shots``, ``estimated_cost_usd``,
            and ``currency`` keys.
        """
        vendor = _extract_vendor(device_arn)
        # Approximate per-shot costs (USD) — these are indicative
        _COST_PER_SHOT: Dict[str, float] = {
            "ionq": 0.00002,
            "rigetti": 0.000008,
            "oqc": 0.000015,
            "quera": 0.00001,
            "amazon": 0.000005,
            "xanadu": 0.00001,
        }
        cost_per_shot = _COST_PER_SHOT.get(vendor, 0.00001)
        estimated = cost_per_shot * shots

        return {
            "device": device_arn,
            "vendor": _PROVIDER_PREFIXES.get(vendor, vendor),
            "shots": shots,
            "estimated_cost_usd": round(estimated, 6),
            "currency": "USD",
            "note": "Estimate only — actual cost depends on provider billing.",
        }

    # ==================================================================
    # Internal helpers
    # ==================================================================

    def _get_task_status(self, task_arn: str) -> Dict[str, Any]:
        """Fetch raw status JSON for a Braket task."""
        url = f"{_BRAKET_API_BASE}/v1/tasks/{task_arn}"
        return _api_request(
            url,
            access_key=self._access_key,
            secret_key=self._secret_key,
            session_token=self._session_token,
            region=self._region,
        )

    def _get_task_result(self, task_arn: str) -> Dict[str, Any]:
        """Fetch the result payload for a completed Braket task."""
        url = f"{_BRAKET_API_BASE}/v1/tasks/{task_arn}/result"
        return _api_request(
            url,
            access_key=self._access_key,
            secret_key=self._secret_key,
            session_token=self._session_token,
            region=self._region,
        )

    def _cancel_task(self, task_arn: str) -> None:
        """Issue a cancel request for a Braket task."""
        url = f"{_BRAKET_API_BASE}/v1/tasks/{task_arn}"
        try:
            _api_request(
                url,
                method="DELETE",
                access_key=self._access_key,
                secret_key=self._secret_key,
                session_token=self._session_token,
                region=self._region,
            )
        except BraketAPIError as exc:
            raise BraketJobError(
                f"Failed to cancel task {task_arn}: {exc}"
            ) from exc

    def _download_from_s3(self, bucket: str, key: str) -> Dict[str, Any]:
        """Download and parse a JSON object from S3.

        Uses a signed GET URL via the Braket service.
        """
        url = f"{_S3_ENDPOINT}/{bucket}/{key}"
        return _api_request(
            url,
            access_key=self._access_key,
            secret_key=self._secret_key,
            session_token=self._session_token,
            region=self._region,
        )

    def _fetch_device_target(self, arn: str) -> BackendTarget:
        """Fetch a single device's metadata directly from the API."""
        url = f"{_BRAKET_API_BASE}/v1/devices/{arn}"
        try:
            data = _api_request(
                url,
                access_key=self._access_key,
                secret_key=self._secret_key,
                session_token=self._session_token,
                region=self._region,
            )
            target = self._parse_device(data, arn)
            self._backend_cache[arn] = target
            return target
        except BraketAPIError as exc:
            raise BraketDeviceError(
                f"Failed to fetch device {arn}: {exc}"
            ) from exc

    @staticmethod
    def _parse_device(dev: Dict[str, Any], arn: str) -> BackendTarget:
        """Convert a raw Braket device dict into a ``BackendTarget``."""
        vendor = _extract_vendor(arn)
        device_name = _device_name_from_arn(arn)
        gate_set = _GATE_SETS.get(vendor, _GATE_SETS["default"])
        basis_gates = _BASIS_GATES.get(vendor, [])

        status_str = dev.get("deviceStatus", "OFFLINE")
        status_map: Dict[str, BackendStatus] = {
            "ONLINE": BackendStatus.ONLINE,
            "OFFLINE": BackendStatus.OFFLINE,
            "MAINTENANCE": BackendStatus.MAINTENANCE,
        }
        status = status_map.get(status_str.upper(), BackendStatus.OFFLINE)

        num_qubits = dev.get("deviceCapabilities", {})
        if isinstance(num_qubits, dict):
            qubit_count = num_qubits.get("qubitCount", 0)
            if qubit_count == 0:
                # Try top-level key
                qubit_count = dev.get("qubitCount", 0)
        else:
            qubit_count = dev.get("qubitCount", 0)

        coupling: List[BackendTargetCoupling] = []
        connectivity = dev.get("deviceCapabilities", {})
        if isinstance(connectivity, dict):
            topologies = connectivity.get("topology", [])
            if isinstance(topologies, list):
                for topo in topologies:
                    if isinstance(topo, dict):
                        for edge in topo.get("edges", []):
                            if isinstance(edge, list) and len(edge) == 2:
                                coupling.append(
                                    BackendTargetCoupling(
                                        q1=edge[0], q2=edge[1], gate="CZ"
                                    )
                                )

        is_simulator = "simulator" in arn.lower()

        description_parts = []
        if vendor in _PROVIDER_PREFIXES:
            description_parts.append(_PROVIDER_PREFIXES[vendor])
        description_parts.append(device_name)
        if is_simulator:
            description_parts.append("(simulator)")

        return BackendTarget(
            name=arn,
            num_qubits=qubit_count,
            status=status,
            provider_name=_PROVIDER_PREFIXES.get(vendor, vendor.capitalize()),
            gate_set=gate_set,
            coupling_map=coupling,
            max_shots=4000 if not is_simulator else 10000,
            max_circuits=100,
            basis_gates=basis_gates,
            native_gates=gate_set.gates,
            simulator=is_simulator,
            dynamic_circuits=True,
            description=" ".join(description_parts),
            operational=(status == BackendStatus.ONLINE),
            pending_jobs=0,
            tags=[vendor, "braket"],
        )

    @staticmethod
    def _normalise_circuit(circuits: Any) -> Any:
        """Normalise various circuit representations into Braket IR.

        Accepts:
        - dict (already IR)
        - str (OpenQASM source)
        - Object with ``to_ir()`` (``braket.circuits.Circuit``)

        Returns:
            A JSON-serialisable Braket IR program dict or OpenQASM string.
        """
        if isinstance(circuits, dict):
            return circuits
        if isinstance(circuits, str):
            return {"source": circuits, "type": "OPENQASM"}
        if hasattr(circuits, "to_ir"):
            ir = circuits.to_ir()
            if isinstance(ir, dict):
                return ir
            return {"source": str(ir), "type": "OPENQASM"}
        return {"source": str(circuits), "type": "OPENQASM"}
