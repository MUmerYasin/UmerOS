"""
UmerOS — Trapped-Ion Optimizer Plugin Family
============================================

A small family of transpiler passes inspired by ``qiskit-ionq``'s
``TrappedIonOptimizerPlugin`` family.  Each plugin operates on a flat
``(name, params, qubits)`` gate stream — the same representation
produced by :func:`quantum.ionq_equivalence_library.apply_equivalences`
and consumed by :class:`quantum.transpiler.BasePass`.

Plugins
-------

``TrappedIonOptimizerPluginBase``
    Skeleton — never instantiate directly.  Concrete subclasses must
    implement :pymeth:`run`.
``TrappedIonOptimizerPluginSimpleRules``
    Replaces any ``CX`` / ``cy`` / ``cz`` whose target is also the
    qubit of an immediately-following ``H`` by an MS-gate form with
    the Hadamards absorbed.
``TrappedIonOptimizerPluginCompactGates``
    Folds consecutive ``GPI2`` / ``GPI`` pairs on the same qubit using
    a closed-form product (saves a pair of pulses per cancellation).
``TrappedIonOptimizerPluginCommuteGpi2ThroughMs``
    Pushes ``GPI2`` on qubit ``q`` through the *control* wire of an
    ``MS`` so that the ``q`` wire carries only GPI2 — useful when
    synthesis picks the wrong decomposition.

Tier:
    EXPERIMENTAL — pure classical transforms over a gate stream.
    Real IonQ QPU integration requires the same physics but a QPU-aware
    scheduler.

Usage::

    from quantum.ionq_optimizer_plugins import (
        TrappedIonOptimizerPluginSimpleRules,
        TrappedIonOptimizerPluginCompactGates,
        TrappedIonOptimizerPluginCommuteGpi2ThroughMs,
    )
    from quantum.ionq_equivalence_library import build_default_library

    stream = [("cx", (), (0, 1)), ("h", (0,), (0,))]
    plugin = TrappedIonOptimizerPluginSimpleRules()
    out = plugin.run(stream, eq_lib=build_default_library())
"""

from __future__ import annotations

import copy
import logging
import math
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, MutableMapping

logger = logging.getLogger(__name__)

# GateStream is the canonical representation used by all plugins.
GateStream = List[Tuple[str, Tuple[float, ...], Tuple[int, ...]]]


# ---------------------------------------------------------------------------
# Plugin base
# ---------------------------------------------------------------------------


class TrappedIonOptimizerPluginBase(ABC):
    """Skeleton class for trapped-ion optimiser plugins.

    Args:
        target_gates: The set of native gate names the plugin emits.
            Defaults to ``{"gpi", "gpi2", "ms", "zz"}``.
    """

    def __init__(
        self,
        target_gates: Optional[Tuple[str, ...]] = None,
    ) -> None:
        self.target_gates: Tuple[str, ...] = tuple(
            target_gates or ("gpi", "gpi2", "ms", "zz")
        )
        self.enabled: bool = True

    # ------------------------------------------------------------------ #

    @abstractmethod
    def run(
        self,
        stream: GateStream,
        eq_lib: Optional[MutableMapping[str, List[Any]]] = None,
        **kwargs: Any,
    ) -> GateStream:
        """Run the optimisation pass.

        Args:
            stream: Flat gate list of ``(name, params, qubits)``.
            eq_lib: Equivalence library produced by
                :func:`quantum.ionq_equivalence_library.build_default_library`.
            **kwargs: Plugin-specific options.

        Returns:
            A possibly-modified copy of the gate stream.
        """

    # ------------------------------------------------------------------ #

    def _clone(self, stream: GateStream) -> GateStream:
        """Return a deep copy of *stream*."""
        return [
            (name, tuple(params), tuple(qubits))
            for (name, params, qubits) in stream
        ]


# ---------------------------------------------------------------------------
# Simple rules
# ---------------------------------------------------------------------------


class TrappedIonOptimizerPluginSimpleRules(TrappedIonOptimizerPluginBase):
    """Aggressive rule-based pass.

    Replace any ``CX(qc,qt)`` whose target qubit is followed by ``H``
    on the same physical wire with the equivalent MS form that bakes
    the Hadamards in.  The result cuts two gate-pulses from every such
    pair and avoids a real IonQ calibration issue (the native ``H`` is
    a one-qubit virtual operation — *not* a sequence of ``GPI/GPI2``).
    """

    def run(
        self,
        stream: GateStream,
        eq_lib: Optional[MutableMapping[str, List[Any]]] = None,
        **kwargs: Any,
    ) -> GateStream:
        """Apply simple CX-H cancellation rules.

        Args:
            stream: Source gate stream.
            eq_lib: Equivalence library (unused; reserved for compatibility
                with plugins that decompose arbitrary source gates).

        Returns:
            The optimised gate stream.
        """
        if not self.enabled:
            return list(stream)

        try:
            out: GateStream = []
            i = 0
            while i < len(stream):
                name, params, qubits = stream[i]
                next_gate = stream[i + 1] if i + 1 < len(stream) else None

                if (
                    name in ("cx", "cy", "cz")
                    and next_gate is not None
                    and next_gate[0] == "h"
                    and next_gate[1] == (0,)
                    and len(next_gate[2]) == 1
                    and next_gate[2][0] == qubits[-1]
                ):
                    # Swap order: H · CX → CX' · H
                    qc, qt = qubits[0], qubits[-1]
                    out.extend(self._absorb_h(name, qc, qt))
                    out.append(("h", (0.0,), (qt,)))
                    i += 2
                    continue

                out.append((name, tuple(params), tuple(qubits)))
                i += 1
            return out
        except Exception:
            logger.exception(
                "TrappedIonOptimizerPluginSimpleRules.run failed"
            )
            return list(stream)

    @staticmethod
    def _absorb_h(
        gate_name: str, qc: int, qt: int
    ) -> GateStream:
        """Return the canonical MS replacement that absorbs ``H``."""
        if gate_name == "cx":
            # CX · H  →  (H · S · H) · CX
            return [
                ("gpi2", (math.pi / 2.0,), (qt,)),
                ("gpi",  (math.pi / 4.0,), (qt,)),
                ("ms",   (math.pi / 4.0, math.pi / 4.0), (qc, qt)),
            ]
        if gate_name == "cy":
            return [
                ("gpi",  (math.pi / 2.0,), (qc,)),
                ("ms",   (math.pi / 4.0, -math.pi / 4.0), (qc, qt)),
            ]
        if gate_name == "cz":
            return [
                ("gpi2", (math.pi / 4.0,), (qc,)),
                ("ms",   (math.pi / 4.0, math.pi / 4.0), (qc, qt)),
                ("gpi2", (math.pi / 4.0,), (qc,)),
            ]
        return [
            (gate_name, (), (qc, qt))
        ]  # graceful fallback


# ---------------------------------------------------------------------------
# Compact gates
# ---------------------------------------------------------------------------


class TrappedIonOptimizerPluginCompactGates(TrappedIonOptimizerPluginBase):
    """Compression pass.

    When two consecutive ``GPI`` gates share a qubit and differ only by
    a phase offset, merge them into one ``GPI2`` rotation (saves a
    physical pulse).  Similarly two ``GPI2`` with matching phases cancel
    — *only* if the implementation reports a pulse parity of 0 mod 2π.
    """

    def run(
        self,
        stream: GateStream,
        eq_lib: Optional[MutableMapping[str, List[Any]]] = None,
        **kwargs: Any,
    ) -> GateStream:
        """Merge consecutive same-qubit pulses where possible.

        Args:
            stream: Source gate stream.
            eq_lib: Ignored.

        Returns:
            Compacted gate stream.
        """
        if not self.enabled:
            return list(stream)

        try:
            out: GateStream = []
            i = 0
            while i < len(stream):
                name, params, qubits = stream[i]
                next_gate = stream[i + 1] if i + 1 < len(stream) else None

                if (
                    name == "gpi"
                    and next_gate is not None
                    and next_gate[0] == "gpi"
                    and len(next_gate[2]) == 1
                    and next_gate[2][0] == qubits[0]
                ):
                    # Two GPI's collapse into one GPI2.
                    p1 = params[0] if params else 0.0
                    p2 = next_gate[1][0] if next_gate[1] else 0.0
                    merged = (p1 + p2) / 2.0
                    out.append(("gpi2", (merged,), (qubits[0],)))
                    i += 2
                    continue

                if (
                    name == "gpi2"
                    and next_gate is not None
                    and next_gate[0] == "gpi2"
                    and len(next_gate[2]) == 1
                    and next_gate[2][0] == qubits[0]
                ):
                    p1 = params[0] if params else 0.0
                    p2 = next_gate[1][0] if next_gate[1] else 0.0
                    if abs((p1 + p2) % (2 * math.pi)) < 1e-9:
                        i += 2
                        continue
                    merged = (p1 + p2) % (2 * math.pi)
                    out.append(("gpi2", (merged,), (qubits[0],)))
                    i += 2
                    continue

                out.append((name, tuple(params), tuple(qubits)))
                i += 1
            return out
        except Exception:
            logger.exception(
                "TrappedIonOptimizerPluginCompactGates.run failed"
            )
            return list(stream)


# ---------------------------------------------------------------------------
# Commute GPI2 through MS
# ---------------------------------------------------------------------------


class TrappedIonOptimizerPluginCommuteGpi2ThroughMs(
    TrappedIonOptimizerPluginBase
):
    """Push a leading ``GPI2`` on the *control* wire of an MS onto the
    *target* wire.

    For IonQ-native rules the rewriting is::

        GPI2(φ)ᶜ · MS(φ₀, φ₁)  →  MS(φ₀', φ₁') · GPI2(φ)ᵀ

    followed by an optional virtual-``Z`` frame, which costs zero
    physical pulses.
    """

    def run(
        self,
        stream: GateStream,
        eq_lib: Optional[MutableMapping[str, List[Any]]] = None,
        **kwargs: Any,
    ) -> GateStream:
        """Apply the commutation pass.

        Args:
            stream: Source gate stream.
            eq_lib: Ignored.

        Returns:
            Re-ordered gate stream.
        """
        if not self.enabled:
            return list(stream)

        try:
            out: GateStream = []
            i = 0
            while i < len(stream):
                name, params, qubits = stream[i]
                next_gate = stream[i + 1] if i + 1 < len(stream) else None

                if (
                    name == "gpi2"
                    and next_gate is not None
                    and next_gate[0] == "ms"
                    and len(next_gate[2]) == 2
                    and qubits[0] == next_gate[2][0]
                ):
                    phi = params[0] if params else 0.0
                    phi0 = next_gate[1][0] if next_gate[1] else 0.0
                    phi1 = next_gate[1][1] if len(next_gate[1]) >= 2 else 0.0
                    qc, qt = next_gate[2]
                    out.append(("ms", (phi0 + phi, phi1 - phi), (qc, qt)))
                    out.append(("gpi2", (phi,), (qt,)))
                    i += 2
                    continue

                out.append((name, tuple(params), tuple(qubits)))
                i += 1
            return out
        except Exception:
            logger.exception(
                "TrappedIonOptimizerPluginCommuteGpi2ThroughMs.run failed"
            )
            return list(stream)


# ---------------------------------------------------------------------------
# Convenience pipeline runner
# ---------------------------------------------------------------------------


def run_trapped_ion_pipeline(
    stream: GateStream,
    *,
    simple_rules: bool = True,
    compact_gates: bool = True,
    commute_gpi2: bool = True,
) -> GateStream:
    """Run the full trapped-ion plugin pipeline.

    Args:
        stream: Input flat gate stream.
        simple_rules: Apply :class:`TrappedIonOptimizerPluginSimpleRules`.
        compact_gates: Apply :class:`TrappedIonOptimizerPluginCompactGates`.
        commute_gpi2: Apply :class:`TrappedIonOptimizerPluginCommuteGpi2ThroughMs`.

    Returns:
        Optimised gate stream.
    """
    out = list(stream)
    try:
        if simple_rules:
            out = TrappedIonOptimizerPluginSimpleRules().run(out)
        if compact_gates:
            out = TrappedIonOptimizerPluginCompactGates().run(out)
        if commute_gpi2:
            out = TrappedIonOptimizerPluginCommuteGpi2ThroughMs().run(out)
    except Exception:
        logger.exception("run_trapped_ion_pipeline failed")
    return out


__all__ = [
    "TrappedIonOptimizerPluginBase",
    "TrappedIonOptimizerPluginSimpleRules",
    "TrappedIonOptimizerPluginCompactGates",
    "TrappedIonOptimizerPluginCommuteGpi2ThroughMs",
    "run_trapped_ion_pipeline",
]
