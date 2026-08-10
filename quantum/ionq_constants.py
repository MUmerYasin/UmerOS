"""
UmerOS — IonQ Provider Constants
=================================

Enumerations and string constants used by the IonQ backend / provider layer.

These mirror the public surface of the upstream ``qiskit-ionq`` provider and
the IonQ REST API v0.3 / v0.4 schemas (see ``QISKIT_RESEARCH/qiskit-ionq-report.md``
for source material).

Tier:
    EXPERIMENTAL — These constants describe a real, paid cloud service
    (api.ionq.co).  UmerOS only emulates the wire shape locally; real
    ``ionq.ionq_access_token`` calls are gated behind a TODO marker.

Usage::

    from quantum.ionq_constants import (
        APIJobStatus, IonQErrorMitigation, IonQAggregationMethod,
        IONQ_DEFAULT_URL, IONQ_NATIVE_GATES, IONQ_DEFAULT_SHOTS,
    )
"""

from __future__ import annotations

from enum import Enum, auto


# ---------------------------------------------------------------------------
# REST endpoint defaults
# ---------------------------------------------------------------------------

#: Base URL of the IonQ REST API.  UmerOS targets the v0.3 endpoint by
#: default for compatibility with historical payloads, but the provider
#: can be reconfigured for v0.4 endpoints below.
IONQ_DEFAULT_URL: str = "https://api.ionq.co/v0.3"

#: v0.4 base URL — newer schema with native-gate matrix fields and richer
#: metadata.  Use ``IonQProvider(url=IONQ_DEFAULT_URL_V4)`` to opt-in.
IONQ_DEFAULT_URL_V4: str = "https://api.ionq.co/v0.4"

#: Default ``shots`` count if the user does not provide one.
IONQ_DEFAULT_SHOTS: int = 1024

#: Hard cap on simultaneous circuits per job — IonQ rejects payloads
#: above this on the wire.
IONQ_MAX_CIRCUITS_PER_JOB: int = 100

#: Highest allowed ``error_mitigation`` value the API accepts.
#: ``debias`` is documented up to ``0.999`` on the v0.4 schema.
IONQ_MAX_DEBIAS: float = 0.999

#: Polling interval when waiting for an async job to terminate.
IONQ_POLL_INTERVAL_SECONDS: float = 1.0


# ---------------------------------------------------------------------------
# Native gate sets (string constants; canonical matrices live in
# ``quantum/ionq_gates.py``)
# ---------------------------------------------------------------------------

#: Canonical IonQ native gate alphabet — gates IonQ hardware can execute
#: directly without synthesis.  Matches the ``ionq_qiskit.gates`` module.
IONQ_NATIVE_GATES: tuple[str, ...] = ("gpi", "gpi2", "ms", "zz")

#: All gate names IonQ will accept after pre-translation.  Differs from
#: ``IONQ_NATIVE_GATES`` by also including classical and measurement ops
#: that the provider injects automatically.
IONQ_TRANSLATABLE_GATES: tuple[str, ...] = (
    "x",
    "y",
    "z",
    "rx",
    "ry",
    "rz",
    "h",
    "s",
    "t",
    "sdg",
    "tdg",
    "sx",
    "sxdg",
    "p",
    "u1",
    "u2",
    "u3",
    "cx",
    "cy",
    "cz",
    "ch",
    "swap",
    "iswap",
    "ccx",
    "ccz",
    "cswap",
    "cp",
    "crx",
    "cry",
    "crz",
    "cu1",
    "cu3",
    "rxx",
    "ryy",
    "rzz",
    "rccx",
    "rc3x",
    "c3x",
    "c3sx",
    "id",
    *IONQ_NATIVE_GATES,
)


# ---------------------------------------------------------------------------
# API job status mapping
# ---------------------------------------------------------------------------


class APIJobStatus(str, Enum):
    """The exact set of ``status`` strings IonQ's REST API returns.

    UmerOS maps these to its internal ``JobStatus``-style canonical
    labels via ``IonQProvider._STATUS_MAP``.
    """

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Aggregation methods
# ---------------------------------------------------------------------------


class IonQAggregationMethod(Enum):
    """Aggregation methods for IonQ estimator-style runs.

    Values mirror ``qiskit_ionq.ionq_gates.AggregationMethod``.  Only
    relevant for ``expectation_value``-style public results.
    """

    #: Argmax of the measurement probability distribution.
    MOST_LIKELY = auto()

    #: Sum of value * probability over all bitstrings.
    EXPECTATION = auto()

    #: Full probability histogram (no aggregation).
    HISTOGRAM = auto()


# ---------------------------------------------------------------------------
# Error-mitigation vocabulary
# ---------------------------------------------------------------------------


class IonQErrorMitigation(Enum):
    """Error-mitigation presets supported by IonQ's REST API.

    These map 1-1 to the ``error_mitigation`` field in the job-creation
    payload (``qiskit-ionq-report.md`` §8).
    """

    #: Disable every mitigation step.
    NONE = "none"

    #: Shot-noise symmetrisation only — does not require additional QPU
    #: runs, but yields larger confidence intervals.
    SHOT_NOISE = "shot_noise"

    #: Zero-noise extrapolation — runs the same circuit at several
    #: noise scale factors and fits an extrapolation.
    ZERO_NOISE_EXTRAPOLATION = "zero_noise_extrapolation"

    #: Probability-matrix error-diffusion (PEC) — currently in IonQ beta
    #: and only enabled on Forte / Aria processors.
    MATRIX_ERROR_DIFFUSION = "matrix_error_diffusion"


# ---------------------------------------------------------------------------
# Target backends
# ---------------------------------------------------------------------------


class IonQTargetBackend(Enum):
    """Catalog of well-known IonQ QPU families."""

    #: 11-qubit Harmony trapped-ion system (legacy / production).
    HARMONY = "harmony"

    #: 25-qubit Aria-1 trapped-ion system.
    ARIA_1 = "aria-1"

    #: 29-qubit Aria-2 trapped-ion system.
    ARIA_2 = "aria-2"

    #: Latest-gen Forte trapped-ion system with high-fidelity gates.
    FORTE = "forte"

    #: Forte Enterprise-class — 32 qubits, low noise.
    FORTE_ENTERPRISE = "forte-enterprise"

    #: IonQ simulator backend (no QPU cost; uses the same REST shape).
    SIMULATOR = "simulator"


#: Mapping from ``IonQTargetBackend`` member to its qubit count.
IONQ_BACKEND_QUBITS: dict[str, int] = {
    IonQTargetBackend.HARMONY.value: 11,
    IonQTargetBackend.ARIA_1.value: 25,
    IonQTargetBackend.ARIA_2.value: 29,
    IonQTargetBackend.FORTE.value: 36,
    IonQTargetBackend.FORTE_ENTERPRISE.value: 32,
    IonQTargetBackend.SIMULATOR.value: 32,
}


__all__ = [
    "IONQ_DEFAULT_URL",
    "IONQ_DEFAULT_URL_V4",
    "IONQ_DEFAULT_SHOTS",
    "IONQ_MAX_CIRCUITS_PER_JOB",
    "IONQ_MAX_DEBIAS",
    "IONQ_POLL_INTERVAL_SECONDS",
    "IONQ_NATIVE_GATES",
    "IONQ_TRANSLATABLE_GATES",
    "APIJobStatus",
    "IonQAggregationMethod",
    "IonQErrorMitigation",
    "IonQTargetBackend",
    "IONQ_BACKEND_QUBITS",
]
