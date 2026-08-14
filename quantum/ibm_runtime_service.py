"""IBM Quantum Runtime service stubs."""
from __future__ import annotations

import copy
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

__all__ = [
    "Channel", "JobState",
    "OptionsV2", "SamplerV2Options", "EstimatorV2Options",
    "UsageData", "PrimitiveResult",
    "RuntimeJobV2", "Session", "QiskitRuntimeService",
    "get_runtime_service",
    "RUNTIME_BASE_URL", "RUNTIME_POLL_INTERVAL_SECONDS", "RUNTIME_API_VERSION",
]

RUNTIME_BASE_URL = "https://quantum-computing.cloud.ibm.com"
RUNTIME_POLL_INTERVAL_SECONDS = 5
RUNTIME_API_VERSION = "0.48"


class Channel(Enum):
    IBM_QUANTUM = "ibm_quantum"
    IBM_CLOUD = "ibm_cloud"
    LOCAL = "local"


class JobState(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class UsageData:
    instance: str = ""
    job_id: str = ""
    seconds_run: float = 0.0
    seconds_queue: float = 0.0
    seconds_real: float = 0.0
    shots: int = 0
    completed: bool = False


@dataclass
class PrimitiveResult:
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptionsV2:
    environment: Dict[str, str] = field(default_factory=dict)

    def model_dump(self) -> Dict[str, Any]:
        result = {}
        if self.environment:
            result["environment"] = self.environment
        return result

    def update(self, **kwargs) -> "OptionsV2":
        new = copy.deepcopy(self)
        for k, v in kwargs.items():
            if hasattr(new, k):
                setattr(new, k, v)
        return new


@dataclass
class SamplerV2Options(OptionsV2):
    default_shots: int = 4096
    dynamical_decoupling: bool = True

    def model_dump(self) -> Dict[str, Any]:
        result = super().model_dump()
        result["default_shots"] = self.default_shots
        if self.dynamical_decoupling:
            result["dynamical_decoupling"] = self.dynamical_decoupling
        return result


@dataclass
class EstimatorV2Options(OptionsV2):
    precision: float = 0.01
    default_precision: float = 0.01

    def model_dump(self) -> Dict[str, Any]:
        result = super().model_dump()
        result["precision"] = self.precision
        result["default_precision"] = self.default_precision
        return result


class RuntimeJobV2:
    def __init__(self, job_id: str, service: Any = None,
                 program_id: str = "", backend_name: str = "",
                 session_id: Optional[str] = None):
        self.job_id = job_id
        self.service = service
        self.program_id = program_id
        self.backend_name = backend_name
        self.session_id = session_id
        self._state = JobState.QUEUED.value
        self._usage_data: Optional[UsageData] = None

    @property
    def state(self) -> str:
        return self._state

    def status(self) -> JobState:
        return JobState(self._state)

    def result(self) -> PrimitiveResult:
        return PrimitiveResult()

    def usage(self, partial: bool = False) -> UsageData:
        if self._usage_data is not None:
            return self._usage_data
        return UsageData(
            instance="ibm-q/open/main",
            job_id=self.job_id,
        )


class Session:
    def __init__(self, backend: str = "", service: Any = None, **kwargs):
        self.service = service
        self.backend = backend
        self.session_id = f"session-{id(self)}"
        self._active = False

    def __enter__(self):
        self._active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._active = False
        return False

    def run(self, programs, **kwargs):
        if not self._active:
            raise RuntimeError("Session is not active. Use 'with Session(...) as sess:'")
        return PrimitiveResult()


class QiskitRuntimeService:
    def __init__(self, channel: Channel = Channel.IBM_QUANTUM,
                 token: Optional[str] = None,
                 instance: str = "auto"):
        self.channel = channel
        self.token = token
        self.instance = "ibm-q/open/main" if instance == "auto" else instance
        self.version = RUNTIME_API_VERSION

    def least_busy(self, use_fractional_gates: bool = False):
        if self.token is None:
            return None
        return "fake_brisbane"

    def backends(self):
        return ["fake_brisbane", "ibmq_qasm_simulator"]

    def run(self, program_id: str, options: OptionsV2 = None, **kwargs) -> RuntimeJobV2:
        return RuntimeJobV2(job_id="job-0", service=self, program_id=program_id)

    def _runtime_get(self, path: str) -> dict:
        return {}


def get_runtime_service(channel: Channel = Channel.IBM_QUANTUM,
                        token: Optional[str] = None) -> QiskitRuntimeService:
    return QiskitRuntimeService(channel=channel, token=token)
