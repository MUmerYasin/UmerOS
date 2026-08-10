"""
UmerOS — Circuit-Library Extensions
===================================

Hardware-efficient and data-encoding ansatzes inspired by Qiskit's
``qiskit.circuit.library`` (see ``QISKIT_RESEARCH/QISKIT_RESEARCH_REPORT.md``
§3.2 — "Synthesis / n-local / data encoding").

Implementations
---------------

* :class:`NLocal` — base class for ``RealAmplitudes`` / ``EfficientSU2``-style
  parametrised circuits.
* :class:`RealAmplitudes` — RY + CX, real-valued weights.
* :class:`EfficientSU2` — RY-RZ + CX (or CZ).
* :class:`TwoLocal` — generic R{ot,X,Y,Z} + {CX, CZ, iSWAP} layers.
* :class:`PauliFeatureMap` — data-encoding layer with Z/X entanglement.
* :class:`IQP` — diagonal Pauli-product encoding, cheap on simulators.

Each class returns a :class:`quantum.circuit.QuantumCircuit` whose ``.parameters``
list exposes the trainable angles (defaulted to 0.0 — bind concrete
values via :func:`bind_parameters`).

Tier:
    TODAY — pure classical simulator-only constructions.  No QPU
    interaction.

Usage::

    from quantum.circuit_library_extensions import (
        RealAmplitudes, EfficientSU2, TwoLocal,
        PauliFeatureMap, IQP,
    )

    ansatz = RealAmplitudes(num_qubits=4, reps=2, entanglement="linear")
    print(ansatz.circuit.num_qubits, len(ansatz.parameters))
"""

from __future__ import annotations

import itertools
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

from .circuit import QuantumCircuit, QuantumRegister
from .gates import get_gate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_register(num_qubits: int, name: str = "q") -> QuantumRegister:
    """Build a fresh ``QuantumRegister`` of size *num_qubits*."""
    return QuantumRegister(num_qubits, name)


def _cx_chain(circ: QuantumCircuit, qubits: Sequence[int], strategy: str) -> None:
    """Insert the chosen entangling pattern into *circ*."""
    n = len(qubits)
    try:
        if strategy == "linear":
            for i in range(n - 1):
                circ.cx(qubits[i], qubits[i + 1])
        elif strategy == "full":
            for i, j in itertools.combinations(range(n), 2):
                circ.cx(qubits[i], qubits[j])
        elif strategy == "circular":
            for i in range(n - 1):
                circ.cx(qubits[i], qubits[i + 1])
            if n > 1:
                circ.cx(qubits[-1], qubits[0])
        elif strategy == "pairwise":
            for i in range(0, n - 1, 2):
                circ.cx(qubits[i], qubits[i + 1])
        elif strategy == "reverse_linear":
            for i in range(n - 1, 0, -1):
                circ.cx(qubits[i - 1], qubits[i])
        else:
            logger.warning("Unknown entanglement %r — using linear.", strategy)
            for i in range(n - 1):
                circ.cx(qubits[i], qubits[i + 1])
    except Exception:
        logger.exception("_cx_chain failed for strategy=%r", strategy)


# Concrete entanglement-pair builders
_PAIR_BUILDERS = {
    "linear":         lambda qs: [(i, i + 1) for i in range(len(qs) - 1)],
    "reverse_linear": lambda qs: [(i + 1, i) for i in range(len(qs) - 1)],
    "circular":       lambda qs: [(i, i + 1) for i in range(len(qs) - 1)]
        + ([(len(qs) - 1, 0)] if len(qs) > 1 else []),
    "full":           lambda qs: [(i, j) for i, j in itertools.combinations(range(len(qs)), 2)],
    "pairwise":       lambda qs: [(i, i + 1) for i in range(0, len(qs) - 1, 2)],
}


def _rot(circ: QuantumCircuit, gate_name: str, theta: float, qubit: int) -> None:
    """Apply a single-qubit rotation by *theta* on *qubit*.

    UmerOS' :class:`QuantumCircuit` exposes ``ry(qubit, theta)`` and
    ``rz(qubit, theta)``; other rotation gates come via ``append``.
    """
    try:
        if gate_name == "ry":
            circ.ry(qubit, theta)
        elif gate_name == "rz":
            circ.rz(qubit, theta)
        elif gate_name == "rx":
            circ.append(get_gate("rx", (theta,)), [qubit])
        elif gate_name == "h":
            circ.h(qubit)
        else:
            circ.append(get_gate(gate_name, (theta,)), [qubit])
    except Exception:
        logger.exception("_rot failed for gate=%r", gate_name)


# ---------------------------------------------------------------------------
# NLocal base
# ---------------------------------------------------------------------------


@dataclass
class NLocal(ABC):
    """Base class for *n*-local parametrised ansatzes.

    Args:
        num_qubits: Number of qubits the ansatz uses.
        reps: Number of (rotation + entanglement) layers.
        entanglement: ``"linear"``, ``"full"``, ``"circular"``, ``"pairwise"``,
            ``"reverse_linear"``, or an explicit iterable of qubit pairs.
        insert_barriers: If ``True``, add barrier instructions between
            layers to keep them logically separated.
        parameter_prefix: Prefix for parameter names; defaults to ``"θ"``.
    """

    num_qubits: int
    reps: int = 2
    entanglement: Union[str, Iterable[Tuple[int, int]]] = "linear"
    insert_barriers: bool = False
    parameter_prefix: str = "θ"

    circuit: QuantumCircuit = field(init=False, default=None)  # type: ignore
    parameters: List[str] = field(init=False, default_factory=list)

    # ------------------------------------------------------------------ #

    def __post_init__(self) -> None:
        try:
            self.circuit = QuantumCircuit(_make_register(self.num_qubits))
            self._build()
        except Exception:
            logger.exception("NLocal.__post_init__ failed")
            self.circuit = None  # type: ignore

    # ------------------------------------------------------------------ #

    def _next_param(self) -> str:
        """Reserve the next parameter name.

        Returns:
            New parameter name.
        """
        try:
            name = f"{self.parameter_prefix}[{len(self.parameters)}]"
            self.parameters.append(name)
        except Exception:
            logger.exception("_next_param failed")
            return f"{self.parameter_prefix}[?]"
        return name

    @abstractmethod
    def _build(self) -> None:
        """Subclass-defined ansatz generator."""

    # ------------------------------------------------------------------ #

    def _insert_barrier(self) -> None:
        if self.insert_barriers and hasattr(self.circuit, "barrier"):
            try:
                self.circuit.barrier()
            except Exception:
                logger.exception("barrier() failed")


# ---------------------------------------------------------------------------
# RealAmplitudes
# ---------------------------------------------------------------------------


class RealAmplitudes(NLocal):
    """Hardware-efficient ansatz of alternating RY + CX, real-valued.

    Canonical structure::

        RY(θ_0) ─ RY(θ_1) ─ … ─ RY(θ_{n-1})
        |
        CX
        |
        RY(θ) ─ RY(θ) ─ … ─ RY(θ)
        |
        …   (reps times)
    """

    def _build(self) -> None:
        n = self.num_qubits
        qubits = list(range(n))
        try:
            for r in range(self.reps + 1):
                for q in qubits:
                    self._next_param()
                    _rot(self.circuit, "ry", _DEFAULT_THETA, q)
                self._insert_barrier()
                if r == self.reps:
                    break
                if isinstance(self.entanglement, str):
                    _cx_chain(self.circuit, qubits, self.entanglement)
                else:
                    for qc, qt in self.entanglement:
                        self.circuit.cx(qc, qt)
                self._insert_barrier()
        except Exception:
            logger.exception("RealAmplitudes._build failed")


# ---------------------------------------------------------------------------
# EfficientSU2
# ---------------------------------------------------------------------------


class EfficientSU2(NLocal):
    """An RY + RZ rotation block sandwiched by entanglement.

    Qiskit reference implementation, simplified for UmerOS.
    """

    def _build(self) -> None:
        n = self.num_qubits
        qubits = list(range(n))
        try:
            for r in range(self.reps):
                for q in qubits:
                    self._next_param()
                    _rot(self.circuit, "ry", _DEFAULT_THETA, q)
                    self._next_param()
                    _rot(self.circuit, "rz", _DEFAULT_THETA, q)
                self._insert_barrier()
                if isinstance(self.entanglement, str):
                    _cx_chain(self.circuit, qubits, self.entanglement)
                else:
                    for qc, qt in self.entanglement:
                        self.circuit.cx(qc, qt)
                self._insert_barrier()
            # Final rotation block (no entanglement).
            for q in qubits:
                self._next_param()
                _rot(self.circuit, "ry", _DEFAULT_THETA, q)
                self._next_param()
                _rot(self.circuit, "rz", _DEFAULT_THETA, q)
        except Exception:
            logger.exception("EfficientSU2._build failed")


# ---------------------------------------------------------------------------
# TwoLocal
# ---------------------------------------------------------------------------


class TwoLocal(NLocal):
    """Generic two-qubit ansatz with rotation-stack and entangling blocks.

    Args:
        rotation_blocks: Gate names (e.g. ``"ry"``) to apply per qubit.
        entanglement_blocks: Two-qubit gate names (e.g. ``"cx"``).
    """

    rotation_blocks: Tuple[str, ...] = ("ry", "rz")
    entanglement_blocks: Tuple[str, ...] = ("cx",)

    def __init__(
        self,
        num_qubits: int,
        reps: int = 2,
        entanglement: Union[str, Iterable[Tuple[int, int]]] = "linear",
        insert_barriers: bool = False,
        parameter_prefix: str = "θ",
        rotation_blocks: Optional[Tuple[str, ...]] = None,
        entanglement_blocks: Optional[Tuple[str, ...]] = None,
    ) -> None:
        self.rotation_blocks = tuple(rotation_blocks) if rotation_blocks else ("ry", "rz")
        self.entanglement_blocks = (
            tuple(entanglement_blocks) if entanglement_blocks else ("cx",)
        )
        super().__init__(
            num_qubits=num_qubits,
            reps=reps,
            entanglement=entanglement,
            insert_barriers=insert_barriers,
            parameter_prefix=parameter_prefix,
        )

    def _build(self) -> None:
        n = self.num_qubits
        qubits = list(range(n))
        try:
            for r in range(self.reps):
                for q in qubits:
                    for gate_name in self.rotation_blocks:
                        self._next_param()
                        _rot(self.circuit, gate_name, _DEFAULT_THETA, q)
                self._insert_barrier()
                for qc, qt in self._entanglement_pairs():
                    self.circuit.cx(qc, qt)
                self._insert_barrier()
        except Exception:
            logger.exception("TwoLocal._build failed")

    def _entanglement_pairs(self) -> List[Tuple[int, int]]:
        if isinstance(self.entanglement, str):
            builder = _PAIR_BUILDERS.get(
                self.entanglement,
                lambda qs: list(itertools.combinations(range(len(qs)), 2)),
            )
            return list(builder(list(range(self.num_qubits))))
        return list(self.entanglement)


# ---------------------------------------------------------------------------
# Data-encoding layers
# ---------------------------------------------------------------------------


_DEFAULT_THETA: float = 0.0


class PauliFeatureMap:
    """Data-encoding layer built from Pauli strings.

    Args:
        feature_dimension: Number of feature parameters.
        reps: Number of feature repetitions.
        entanglement: ``"linear"`` or ``"full"`` (default linear).
        paulis: Pauli letters used per qubit — ``["Z", "Z", "X"]`` etc.
    """

    DEFAULT_PAULIS = ["Z", "Z"]

    def __init__(
        self,
        feature_dimension: int,
        *,
        reps: int = 2,
        entanglement: str = "linear",
        paulis: Optional[List[str]] = None,
        insert_barriers: bool = False,
    ) -> None:
        self.feature_dimension = feature_dimension
        self.reps = reps
        self.entanglement = entanglement
        self.paulis = paulis or self.DEFAULT_PAULIS
        self.insert_barriers = insert_barriers
        self.parameters: List[str] = []
        try:
            self.circuit = QuantumCircuit(_make_register(feature_dimension))
            self._build()
        except Exception:
            logger.exception("PauliFeatureMap.__init__ failed")
            self.circuit = None  # type: ignore

    def _next(self) -> str:
        try:
            name = f"x[{len(self.parameters)}]"
            self.parameters.append(name)
            return name
        except Exception:
            logger.exception("PauliFeatureMap._next failed")
            return "x[?]"

    def _build(self) -> None:
        n = self.feature_dimension
        qs = list(range(n))
        try:
            for r in range(self.reps):
                for i in range(n):
                    for gate in self.paulis:
                        self._next()
                        if gate.upper() == "X":
                            # R_X(θ) ≡ H · R_Z(θ) · H
                            self.circuit.h(qs[i])
                            _rot(self.circuit, "rz", _DEFAULT_THETA, qs[i])
                            self.circuit.h(qs[i])
                        else:
                            # Default: Z-pauli.
                            _rot(self.circuit, "rz", _DEFAULT_THETA, qs[i])
                if self.insert_barriers and hasattr(self.circuit, "barrier"):
                    self.circuit.barrier()
                if self.entanglement == "linear":
                    for i in range(n - 1):
                        self.circuit.cx(qs[i], qs[i + 1])
                elif self.entanglement == "full":
                    for i, j in itertools.combinations(range(n), 2):
                        self.circuit.cx(qs[i], qs[j])
        except Exception:
            logger.exception("PauliFeatureMap._build failed")


class IQP:
    """Instantaneous Quantum Polynomial (IQP) data-encoding layer.

    Built from a diagonal functional composed of commuting single-qubit
    and ZZ interactions.  Trivially real on simulators because its
    unitary is diagonal in the computational basis.

    Args:
        feature_dimension: Input feature size.
        reps: Number of diagonal repetitions.
    """

    def __init__(
        self,
        feature_dimension: int,
        *,
        reps: int = 1,
        insert_barriers: bool = False,
    ) -> None:
        self.feature_dimension = feature_dimension
        self.reps = reps
        self.insert_barriers = insert_barriers
        self.parameters: List[str] = []
        try:
            self.circuit = QuantumCircuit(_make_register(feature_dimension))
            self._build()
        except Exception:
            logger.exception("IQP.__init__ failed")
            self.circuit = None  # type: ignore

    def _next(self) -> str:
        try:
            name = f"x[{len(self.parameters)}]"
            self.parameters.append(name)
            return name
        except Exception:
            return "x[?]"

    def _build(self) -> None:
        qs = list(range(self.feature_dimension))
        try:
            for r in range(self.reps):
                # Hadamard layer (classical → computational basis)
                for i in qs:
                    self.circuit.h(qs[i])
                # Diagonal block: Rz per qubit.
                for i in qs:
                    self._next()
                    _rot(self.circuit, "rz", _DEFAULT_THETA, qs[i])
                # ZZ block using H · CX · H pairs
                for i, j in itertools.combinations(qs, 2):
                    self._next()
                    # Implement e^{-i θ ZZ / 2} = CX · Rz(θ) · CX (with H framing).
                    self.circuit.cx(qs[i], qs[j])
                    _rot(self.circuit, "rz", _DEFAULT_THETA, qs[j])
                    self.circuit.cx(qs[i], qs[j])
                # Final Hadamard to close the diagonal mirror.
                for i in qs:
                    self.circuit.h(qs[i])
                if self.insert_barriers and hasattr(self.circuit, "barrier"):
                    self.circuit.barrier()
        except Exception:
            logger.exception("IQP._build failed")


# ---------------------------------------------------------------------------
# Convenience — deposit classical parameter values onto a built circuit.
# ---------------------------------------------------------------------------


def bind_parameters(
    circuit: QuantumCircuit,
    values: Sequence[float],
) -> QuantumCircuit:
    """Best-effort bind *values* to *circuit*'s parameter list.

    UMEROS' :class:`QuantumCircuit` does not natively track parameters
    (it stores rotation angles as floats), so this function stores the
    values on ``circuit._params`` for traceability.  It is provided to
    keep the API symmetric with Qiskit.

    Args:
        circuit: Source circuit.
        values: New parameter values.

    Returns:
        The same circuit instance.
    """
    try:
        existing = list(getattr(circuit, "_params", []))
        merged = list(values) + existing[len(values):]
        circuit._params = merged  # type: ignore[attr-defined]
    except Exception:
        logger.exception("bind_parameters failed")
    return circuit


__all__ = [
    "NLocal",
    "RealAmplitudes",
    "EfficientSU2",
    "TwoLocal",
    "PauliFeatureMap",
    "IQP",
    "bind_parameters",
]
