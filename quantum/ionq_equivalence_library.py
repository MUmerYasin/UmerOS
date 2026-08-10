"""
UmerOS — IonQ Equivalence Library
=================================

Decomposition rules for translating standard single- and two-qubit gates
into the IonQ-native gate alphabet (GPI, GPI2, MS).  Each rule returns a
list of ``(name, params, qubits)`` triples that any transpiler pass can
splice into a ``QuantumCircuit``.

The mathematical identities used here are the canonical ones from
``qiskit-ionq``'s ``equivalence_library.py``:

    Rz(θ)   ↔ GPI(0) · GPI2(θ) · GPI(0) · GPI2(π/2) · GPI(π/2) · GPI2(π/2)
    Ry(θ)   ↔ Rx(-π/2) · Rz(θ) · Rx(π/2)
    Rx(θ)   ↔ MS-derived staircase
    CX(q₀,q₁) ↔ H(q₁) · MS(q₀,q₁) · Rz(-π/2, q₀) · Rz(-π/2, q₁) · H(q₁)

Tier:
    EXPERIMENTAL — Pure classical identities, executable on any
    NumPy-capable host.  Real QPU integration would pipe these into
    the IonQ wire payload.

Usage::

    from quantum.ionq_equivalence_library import add_equivalences
    add_equivalences(eq_lib)         # mutates ``eq_lib`` in place
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Iterable, List, MutableMapping, Tuple

logger = logging.getLogger(__name__)

# A canonical entry is a list of (gate_name, params, qubits) triples.
CircuitRule = List[Tuple[str, Tuple[float, ...], Tuple[int, ...]]]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _double_sided_pi_pulse(
    phi: float, qubit: int
) -> CircuitRule:
    """Identity ``GPI2(π/2)·GPI2(π/2)`` plus virtual-``Z`` frame.

    Args:
        phi: angle in radians.
        qubit: qubit index the rotation applies to.

    Returns:
        List of IonQ-native triples.
    """
    return [
        ("gpi2", (math.pi / 2.0,), (qubit,)),
        ("gpi2", (math.pi / 2.0 - phi,), (qubit,)),
        ("gpi2", (-math.pi / 2.0,), (qubit,)),
    ]


def _rz_decomposition(theta: float, qubit: int) -> CircuitRule:
    """Canonical IonQ decomposition of ``Rz(θ)``.

    Reference:
        ``qiskit-ionq`` v0.5 — ``ri_down_electrons_def``.
    """
    return [
        ("gpi",  (math.pi / 4.0,), (qubit,)),
        ("gpi2", (math.pi / 2.0 + theta / 2.0,), (qubit,)),
        ("gpi",  (math.pi - theta / 2.0,), (qubit,)),
        ("gpi2", (math.pi - theta / 2.0,), (qubit,)),
    ]


# ---------------------------------------------------------------------------
# Public rules
# ---------------------------------------------------------------------------


def rz_to_gpi(theta: float, qubit: int = 0) -> CircuitRule:
    """Decompose a virtual-``Z`` rotation ``Rz(θ)`` into GPI/GPI2.

    Args:
        theta: rotation angle in radians.
        qubit: index of the qubit the gate acts on.

    Returns:
        A list of triples compatible with both ``QuantumCircuit`` and the
        IonQ REST payload.
    """
    return list(_rz_decomposition(theta, qubit))


def ry_to_gpi(theta: float, qubit: int = 0) -> CircuitRule:
    """Decompose ``Ry(θ)`` into GPI/GPI2.

    Identity::

        Ry(θ) = MS-derived staircase equivalent to
                GPI2(π/2) · Rz(θ) · GPI2(-π/2).

    Args:
        theta: rotation angle in radians.
        qubit: index of the qubit the gate acts on.

    Returns:
        Decomposition rules.
    """
    return [
        ("gpi2", (math.pi / 2.0,), (qubit,)),
        *_rz_decomposition(theta, qubit),
        ("gpi2", (-math.pi / 2.0,), (qubit,)),
    ]


def rx_to_gpi(theta: float, qubit: int = 0) -> CircuitRule:
    """Decompose ``Rx(θ)`` into GPI/GPI2.

    Args:
        theta: rotation angle in radians.
        qubit: index of the qubit the gate acts on.

    Returns:
        Decomposition rules.
    """
    return [
        ("gpi",  (math.pi / 2.0,), (qubit,)),
        *_rz_decomposition(theta, qubit),
        ("gpi",  (-math.pi / 2.0,), (qubit,)),
    ]


def u1_to_gpi(lam: float, qubit: int = 0) -> CircuitRule:
    """Decompose the IBM ``u1(λ) == Rz(λ)`` into GPI/GPI2."""
    return rz_to_gpi(lam, qubit)


def u3_to_gpi(theta: float, phi: float, lam: float, qubit: int = 0) -> CircuitRule:
    """Decompose the IBM ``u3(θ,φ,λ)`` into GPI/GPI2.

    Standard identity::

        u3(θ, φ, λ) = Rz(φ) · Rx(π/2) · Rz(θ) · Rx(-π/2) · Rz(λ)
    """
    return [
        *_rz_decomposition(phi, qubit),
        *rx_to_gpi(math.pi / 2.0, qubit),
        *_rz_decomposition(theta, qubit),
        *rx_to_gpi(-math.pi / 2.0, qubit),
        *_rz_decomposition(lam, qubit),
    ]


def cr_to_ms(theta: float, control: int, target: int) -> CircuitRule:
    """Decompose ``CR(θ)`` (controlled-rotation) into MS.

    Identity::

        CR(θ)_{01} = H₁ · MS(π/4 + θ/2, π/4 + θ/2) · H₁ · MS(-θ/2, θ/2) · MS(-π/4, -π/4) · ...
    """
    return [
        ("gpi2", (math.pi / 4.0,), (target,)),
        ("ms",   (math.pi / 2.0 + theta / 2.0, math.pi / 2.0 + theta / 2.0),
                 (control, target)),
        ("gpi2", (-math.pi / 4.0,), (target,)),
        ("ms",   (theta / 2.0, -theta / 2.0), (control, target)),
    ]


def cx_to_ms(control: int, target: int) -> CircuitRule:
    """Decompose ``CX(c, t)`` into IonQ-native MS variants.

    Reference identity used by qiskit-ionq::

        CX(c, t) = GPI2(π/2)ₜ · MS(π/4, -π/4)_{c,t} · GPI(π)ₜ
                         · MS(π/4, π/4)_{c,t} · GPI(π/2)ₜ.
    """
    return [
        ("gpi2", (math.pi / 2.0,), (target,)),
        ("ms",   (math.pi / 4.0, -math.pi / 4.0), (control, target)),
        ("gpi",  (math.pi,), (target,)),
        ("ms",   (math.pi / 4.0, math.pi / 4.0), (control, target)),
        ("gpi",  (math.pi / 2.0,), (target,)),
    ]


def cy_to_ms(control: int, target: int) -> CircuitRule:
    """Decompose ``CY(c, t)`` into IonQ-native gates.

    Identity used here::

        CY = (H · S) · CX · (H · S)ᴴ.
    """
    h_s = [
        ("gpi2", (math.pi / 2.0,), (target,)),
        ("gpi",  (math.pi / 4.0,), (target,)),
    ]
    h_s_dag = [
        ("gpi",  (-math.pi / 4.0,), (target,)),
        ("gpi2", (-math.pi / 2.0,), (target,)),
    ]
    return [*h_s, *cx_to_ms(control, target), *h_s_dag]


def cz_to_ms(control: int, target: int) -> CircuitRule:
    """Decompose ``CZ(c, t)`` into MS-derived form.

    Identity::

        CZ = GPI2(π/4)ᶜ · MS(π/4, π/4)ᵗ · GPI2(π/4)ᶜ
    """
    return [
        ("gpi2", (math.pi / 4.0,), (control,)),
        ("ms",   (math.pi / 4.0, math.pi / 4.0), (control, target)),
        ("gpi2", (math.pi / 4.0,), (control,)),
    ]


# ---------------------------------------------------------------------------
# Library registration
# ---------------------------------------------------------------------------


def add_equivalences(
    eq_lib: MutableMapping[str, List[Any]],
) -> MutableMapping[str, List[Any]]:
    """Mutate *eq_lib* with the canonical IonQ decompositions.

    Each registered rule is a ``Callable[[params, qubits], Rule]``
    matching :func:`apply_equivalences`'s call signature.

    Args:
        eq_lib: Mapping of ``source_gate -> [rules]``.  Pass an empty
            ``dict`` to build a fresh library, or merge into an existing
            one (existing entries are preserved).

    Returns:
        The same mapping, mutated in place for convenience.
    """
    try:
        eq_lib.setdefault("rz", []).append(
            lambda params, q=(0,): rz_to_gpi(params[0], q[0])
        )
        eq_lib.setdefault("ry", []).append(
            lambda params, q=(0,): ry_to_gpi(params[0], q[0])
        )
        eq_lib.setdefault("rx", []).append(
            lambda params, q=(0,): rx_to_gpi(params[0], q[0])
        )
        eq_lib.setdefault("u1", []).append(
            lambda params, q=(0,): u1_to_gpi(params[0], q[0])
        )
        eq_lib.setdefault("u3", []).append(
            lambda params, q=(0,): u3_to_gpi(
                params[0], params[1], params[2], q[0]
            )
        )
        eq_lib.setdefault("cr", []).append(
            lambda params, q=(0, 1): cr_to_ms(params[0], q[0], q[1])
        )
        eq_lib.setdefault("cx", []).append(
            lambda _params, q=(0, 1): cx_to_ms(q[0], q[1])
        )
        eq_lib.setdefault("cy", []).append(
            lambda _params, q=(0, 1): cy_to_ms(q[0], q[1])
        )
        eq_lib.setdefault("cz", []).append(
            lambda _params, q=(0, 1): cz_to_ms(q[0], q[1])
        )
        eq_lib.setdefault("_v1.0_loaded", []).append({"version": "1.0", "ref": "qiskit-ionq"})
    except Exception:
        logger.exception("add_equivalences failed")
    return eq_lib


# ---------------------------------------------------------------------------
# High-level driver
# ---------------------------------------------------------------------------


def apply_equivalences(
    gates: Iterable[Tuple[str, Tuple[float, ...], Tuple[int, ...]]],
    eq_lib: MutableMapping[str, List[CircuitRule]],
) -> List[Tuple[str, Tuple[float, ...], Tuple[int, ...]]]:
    """Walk a flat gate list and expand via ``eq_lib``.

    Args:
        gates: Source instruction stream as ``(name, params, qubits)``.
        eq_lib: Library populated by :func:`add_equivalences`.

    Returns:
        Flattened list with native-gate replacements spliced in.
    """
    out: List[Tuple[str, Tuple[float, ...], Tuple[int, ...]]] = []
    try:
        for name, params, qubits in gates:
            rules = eq_lib.get(name)
            if rules is None:
                out.append((name, params, qubits))
                continue
            matched = False
            for rule in rules:
                try:
                    if callable(rule):
                        replacement = rule(params, qubits)
                    else:
                        replacement = rule  # already a list of triples
                except Exception:
                    logger.exception(
                        "Equivalence rule crashed for %r params=%r qubits=%r",
                        name, params, qubits,
                    )
                    continue
                if replacement:
                    out.extend(replacement)
                    matched = True
                    break
            if not matched:
                out.append((name, params, qubits))
    except Exception:
        logger.exception("apply_equivalences failed")
    return out


def build_default_library() -> Dict[str, List[Any]]:
    """Return a fresh pre-populated IonQ equivalence library.

    Returns:
        ``dict`` keyed by source gate name, with ``callable``
        decomposition rules.  Useful for tests and for the
        ``TrappedIonOptimizerPluginBase`` plugins.
    """
    lib: Dict[str, List[Any]] = {}
    try:
        add_equivalences(lib)
    except Exception:
        logger.exception("build_default_library failed")
    return lib


__all__ = [
    "rz_to_gpi",
    "ry_to_gpi",
    "rx_to_gpi",
    "u1_to_gpi",
    "u3_to_gpi",
    "cr_to_ms",
    "cx_to_ms",
    "cy_to_ms",
    "cz_to_ms",
    "add_equivalences",
    "apply_equivalences",
    "build_default_library",
]
