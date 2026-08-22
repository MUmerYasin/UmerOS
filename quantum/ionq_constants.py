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

"""IonQ API constants and enums."""
from __future__ import annotations

from enum import Enum
from typing import Dict

__all__ = [
    "IONQ_DEFAULT_URL", "IONQ_DEFAULT_URL_V4", "IONQ_DEFAULT_SHOTS",
    "IONQ_MAX_CIRCUITS_PER_JOB", "IONQ_MAX_DEBIAS", "IONQ_POLL_INTERVAL_SECONDS",
    "IONQ_NATIVE_GATES", "IONQ_TRANSLATABLE_GATES",
    "APIJobStatus", "IonQAggregationMethod", "IonQErrorMitigation",
    "IonQTargetBackend", "IONQ_BACKEND_QUBITS",
]

IONQ_DEFAULT_URL = "https://api.ionq.co/v0.3"
IONQ_DEFAULT_URL_V4 = "https://api.ionq.co/v0.4"
IONQ_DEFAULT_SHOTS = 1024
IONQ_MAX_CIRCUITS_PER_JOB = 100
IONQ_MAX_DEBIAS = 10
IONQ_POLL_INTERVAL_SECONDS = 2

IONQ_NATIVE_GATES = frozenset({"gpi", "gpi2", "ms"})
IONQ_TRANSLATABLE_GATES = frozenset({
    "gpi", "gpi2", "ms",
    "rz", "ry", "rx", "cnot", "h", "x", "z", "s", "t", "swap",
})


class APIJobStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class IonQAggregationMethod(Enum):
    RAW = "raw"
    TIME_AVERAGE = "time_average"


class IonQErrorMitigation(Enum):
    NONE = "none"
    SHOT_NOISE = "shot_noise"
    ZERO_NOISE_EXTRAPOLATION = "zero_noise_extrapolation"
    MATRIX_ERROR_DIFFUSION = "matrix_error_diffusion"


class IonQTargetBackend(Enum):
    SIMULATOR = "simulator"
    HARMONIC_11 = "harmonic-11-qubit"
    ARIA_1 = "aria-1"
    ARIA_2 = "aria-2"
    FORTIS_1 = "fortis-1"


IONQ_BACKEND_QUBITS: Dict[str, int] = {
    "harmonic-11-qubit": 11,
    "aria-1": 25,
    "aria-2": 25,
    "fortis-1": 36,
}
