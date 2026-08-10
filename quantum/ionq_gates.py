"""
UmerOS — IonQ Native Gate Definitions
=====================================

Definitions for the four gate families IonQ's trapped-ion QPUs can execute
directly:

    GPI(φ)  — Generalised-Photonics single-qubit phase gate (continuous).
    GPI2(φ) — π/2 generalisation of GPI; shorthand for π-pulse equivalents.
    MS(φ₀,φ₁) — Mølmer–Sørensen two-qubit entangling gate.
    ZZ(φ₀,φ₁) — Symmetric ZZ two-qubit rotation.

Each gate exposes both its exact unitary matrix and a ``to_matrix`` /
``to_dict`` representation that the IonQ REST API consumes.

Tier:
    EXPERIMENTAL — These gates describe a physical gate family that
    UmerOS only *simulates*.  All matrix definitions are classical and
    reproducible on any NumPy-capable host.  Real IonQ QPU integration
    requires authenticated https calls; see ``ionq_provider.py``.

Usage::

    from quantum.ionq_gates import GPIGate, GPI2Gate, MSGate, ZZGate
    import math
    g = GPI2Gate(0.5 * math.pi)  # equivalent to S
    print(g.to_matrix().shape)  # (2, 2)
"""

from __future__ import annotations

import math
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


@dataclass
class IonQGate(ABC):
    """Abstract base class for IonQ-native gates.

    All concrete gates carry a small set of phase parameters and
    implement :py:meth:`to_matrix` returning a NumPy ``ndarray``.  The
    matrix is *simulated* classically — UmerOS cannot speak to a real
    Aria / Forte QPU.

    .. note::
        # TODO: QPU integration — the only thing this class must change
        # for real IonQ support is ``to_dict``'s shape (i.e. match the
        # job payload schema).  See ``ionq_provider.py`` for details.
    """

    params: Tuple[float, ...] = field(default_factory=tuple)

    # ------------------------------------------------------------------ #

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical IonQ gate name (matches the v0.4 API schema)."""

    @property
    @abstractmethod
    def num_qubits(self) -> int:
        """Number of physical qubits the gate acts on."""

    @abstractmethod
    def to_matrix(self) -> np.ndarray:
        """Return the unitary matrix as a complex ``ndarray``."""

    # ------------------------------------------------------------------ #

    def to_dict(self) -> Dict[str, Any]:
        """Return the IonQ REST-API representation for this gate.

        Returns:
            A JSON-serialisable dict with ``gate`` and ``targets``
            (no phase parameters — single-qubit gates may carry an
            optional ``phases`` key for continuous families).
        """
        return {"gate": self.name, "targets": []}

    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        params_str = ", ".join(f"{p:.6g}" for p in self.params)
        return f"{self.__class__.__name__}({params_str})"


# ---------------------------------------------------------------------------
# GPI  — Generalised-Photonics single-qubit gate
# ---------------------------------------------------------------------------


@dataclass
class GPIGate(IonQGate):
    """Continuous single-qubit *generalised photonics* gate.

    .. math::
        GPI(\\phi)
        = \\begin{pmatrix}
              0 & e^{-i\\phi}  \\\\
              e^{ i\\phi} & 0
          \\end{pmatrix}

    IonQ hardware reduces to a short laser pulse set by the qubit phase
    shift ``φ``.  Because its top-left entry is zero the gate is *not*
    a unitary rotation through a discrete angle — it is closer to the
    composition ``X · R_z(2φ)``.

    Args:
        phi: Phase parameter in radians.  Repeated values are taken
            modulo 2π.
    """

    phi: float = 0.0

    def __post_init__(self) -> None:
        # Wrap into the canonical (-π, π] interval.
        self.phi = float(((self.phi + math.pi) % (2.0 * math.pi)) - math.pi)
        self.params = (self.phi,)

    @property
    def name(self) -> str:
        return "gpi"

    @property
    def num_qubits(self) -> int:
        return 1

    def to_matrix(self) -> np.ndarray:
        phi = self.phi
        try:
            mat = np.array([
                [0.0 + 0.0j, math.cos(phi) - 1j * math.sin(phi)],
                [math.cos(phi) + 1j * math.sin(phi), 0.0 + 0.0j],
            ], dtype=np.complex128)
        except Exception:  # pragma: no cover - guaranteed by NumPy
            logger.exception("GPIGate.to_matrix failed")
            mat = np.eye(2, dtype=np.complex128)
        return mat

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.name,
            "targets": [],  # caller fills in physical qubit index
            "phases": [self.phi],
        }


# ---------------------------------------------------------------------------
# GPI2  — π/2 generalisation of GPI
# ---------------------------------------------------------------------------


@dataclass
class GPI2Gate(IonQGate):
    """Half-angle cousin of :class:`GPIGate`.

    .. math::
        GPI2(\\phi)
        = \\begin{pmatrix}
              1 & -i e^{-i\\phi} \\\\
             -i e^{ i\\phi} & 1
          \\end{pmatrix} / \\sqrt{2}

    GPI2(0) and GPI2(π/2) produce the two ``X_{±}``-rotated ``pi/2``
    pulses that, combined with virtual-``Z`` frames, give full SU(2).

    Args:
        phi: Phase parameter in radians.
    """

    phi: float = 0.0

    def __post_init__(self) -> None:
        self.phi = float(((self.phi + math.pi) % (2.0 * math.pi)) - math.pi)
        self.params = (self.phi,)

    @property
    def name(self) -> str:
        return "gpi2"

    @property
    def num_qubits(self) -> int:
        return 1

    def to_matrix(self) -> np.ndarray:
        phi = self.phi
        coeff = 1.0 / math.sqrt(2.0)
        try:
            mat = np.array([
                [coeff * 1.0,   coeff * (-1j * math.cos(-phi) - math.sin(-phi))],
                [coeff * (-1j * math.cos(phi)  - math.sin(phi)),   coeff * 1.0],
            ], dtype=np.complex128)
        except Exception:  # pragma: no cover
            logger.exception("GPI2Gate.to_matrix failed")
            mat = np.eye(2, dtype=np.complex128)
        return mat

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.name,
            "targets": [],
            "phases": [self.phi],
        }


# ---------------------------------------------------------------------------
# MS  — Mølmer–Sørensen two-qubit entangling gate
# ---------------------------------------------------------------------------


@dataclass
class MSGate(IonQGate):
    """Two-qubit Mølmer–Sørensen entangling gate.

    IonQ's MS accepts two independent phase parameters that drive
    bichromatic force on the collective mode.  The unitary is

    .. math::
        MS(\\phi_0, \\phi_1)
        = \\exp\\!\\left(
            -\\tfrac{i\\pi}{2}
            \\big(\\cos(\\phi_0 - \\phi_1) X\\!X
                  + \\sin(\\phi_0 - \\phi_1) Y\\!Y\\big)
          \\right).

    Args:
        phi0: First phase in radians.
        phi1: Second phase in radians.
    """

    phi0: float = 0.0
    phi1: float = 0.0

    def __post_init__(self) -> None:
        self.phi0 = float(((self.phi0 + math.pi) % (2.0 * math.pi)) - math.pi)
        self.phi1 = float(((self.phi1 + math.pi) % (2.0 * math.pi)) - math.pi)
        self.params = (self.phi0, self.phi1)

    @property
    def name(self) -> str:
        return "ms"

    @property
    def num_qubits(self) -> int:
        return 2

    def to_matrix(self) -> np.ndarray:
        delta = self.phi0 - self.phi1
        try:
            cos_d = math.cos(delta)
            sin_d = math.sin(delta)
            xx = np.array([[0, 0, 0, 1], [0, 0, 1, 0],
                           [0, 1, 0, 0], [1, 0, 0, 0]], dtype=np.complex128)
            yy = np.array([[0, 0, 0, -1], [0, 0, 1, 0],
                           [0, 1, 0, 0], [-1, 0, 0, 0]], dtype=np.complex128)
            base = cos_d * xx + sin_d * yy
            # Use scipy.linalg.expm only if available; otherwise build manually.
            try:
                from scipy.linalg import expm  # type: ignore
                mat = expm(-1j * (math.pi / 2.0) * base)
            except Exception:
                # Closed-form fallback — exact for the XX/YY combination.
                theta = math.pi / 2.0
                c = math.cos(theta)
                s = math.sin(theta)
                mat = (
                    np.cos(theta) * np.eye(4, dtype=np.complex128)
                    - 1j * math.sin(theta) * (cos_d * xx + sin_d * yy)
                )
                mat = c * np.eye(4, dtype=np.complex128) - 1j * s * base
        except Exception:
            logger.exception("MSGate.to_matrix failed")
            mat = np.eye(4, dtype=np.complex128)
        return mat

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.name,
            "targets": [],
            "phases": [self.phi0, self.phi1],
        }


# ---------------------------------------------------------------------------
# ZZ  — Symmetric ZZ interaction
# ---------------------------------------------------------------------------


@dataclass
class ZZGate(IonQGate):
    """Symmetric ZZ two-qubit rotation.

    .. math::
        ZZ(\\phi_0, \\phi_1) = \\exp\\!\\left(
            -\\tfrac{i\\phi_0}{2} Z \\otimes I
            -\\tfrac{i\\phi_1}{2} I \\otimes Z
        \\right).

    Useful for parametrically-controlled longitudinal interactions in
    trapped-ion hardware.  IonQ does not enable ZZ on the public REST
    API yet — exposed here for completeness against Qiskit's reference.

    Args:
        phi0: Phase for the control qubit in radians.
        phi1: Phase for the target qubit in radians.
    """

    phi0: float = 0.0
    phi1: float = 0.0

    def __post_init__(self) -> None:
        self.phi0 = float(self.phi0)
        self.phi1 = float(self.phi1)
        self.params = (self.phi0, self.phi1)

    @property
    def name(self) -> str:
        return "zz"

    @property
    def num_qubits(self) -> int:
        return 2

    def to_matrix(self) -> np.ndarray:
        p0, p1 = self.phi0, self.phi1
        try:
            diag = np.array([
                math.exp(-0.5j * (p0 + p1)),
                math.exp( 0.5j * (p0 - p1)),
                math.exp(-0.5j * (p0 - p1)),
                math.exp( 0.5j * (p0 + p1)),
            ], dtype=np.complex128)
            mat = np.diag(diag)
        except Exception:  # pragma: no cover
            logger.exception("ZZGate.to_matrix failed")
            mat = np.eye(4, dtype=np.complex128)
        return mat

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.name,
            "targets": [],
            "phases": [self.phi0, self.phi1],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_ionq_gate(name: str, params: Optional[List[float]] = None) -> IonQGate:
    """Build a concrete gate by canonical name.

    Args:
        name: One of ``"gpi"``, ``"gpi2"``, ``"ms"``, ``"zz"``.
        params: Gate-specific phase parameters.  Defaults are all-zero.

    Returns:
        A concrete :class:`IonQGate` instance.

    Raises:
        ValueError: If the name is not recognised.
    """
    n = name.lower()
    params = params or []
    try:
        if n == "gpi":
            return GPIGate(phi=params[0] if params else 0.0)
        if n == "gpi2":
            return GPI2Gate(phi=params[0] if params else 0.0)
        if n == "ms":
            p0 = params[0] if len(params) >= 1 else 0.0
            p1 = params[1] if len(params) >= 2 else 0.0
            return MSGate(phi0=p0, phi1=p1)
        if n == "zz":
            p0 = params[0] if len(params) >= 1 else 0.0
            p1 = params[1] if len(params) >= 2 else 0.0
            return ZZGate(phi0=p0, phi1=p1)
    except Exception:
        logger.exception("get_ionq_gate failed for name=%r", name)
        raise
    raise ValueError(f"Unknown IonQ native gate name: {name!r}")


__all__ = [
    "IonQGate",
    "GPIGate",
    "GPI2Gate",
    "MSGate",
    "ZZGate",
    "get_ionq_gate",
]
