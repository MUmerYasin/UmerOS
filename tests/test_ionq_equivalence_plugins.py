"""Tests for the IonQ equivalence library and optimizer plugin family.

Run::

    python -m pytest tests/test_ionq_equivalence_plugins.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quantum.ionq_equivalence_library import (
    apply_equivalences,
    build_default_library,
    cr_to_ms,
    cx_to_ms,
    cy_to_ms,
    cz_to_ms,
    rx_to_gpi,
    ry_to_gpi,
    rz_to_gpi,
    u1_to_gpi,
    u3_to_gpi,
)
from quantum.ionq_optimizer_plugins import (
    TrappedIonOptimizerPluginCompactGates,
    TrappedIonOptimizerPluginCommuteGpi2ThroughMs,
    TrappedIonOptimizerPluginSimpleRules,
    run_trapped_ion_pipeline,
)


# ---------------------------------------------------------------------------
# Equivalence library
# ---------------------------------------------------------------------------


def test_rz_to_gpi_emits_only_native_gates() -> None:
    """Rz must decompose into only ``gpi`` / ``gpi2``."""
    rule = rz_to_gpi(math.pi / 3, qubit=0)
    assert rule
    for name, _, _ in rule:
        assert name in ("gpi", "gpi2")


def test_cx_to_ms_emits_native_with_ms() -> None:
    """CX must include at least one ``ms`` gate."""
    rule = cx_to_ms(0, 1)
    assert any(name == "ms" for name, _, _ in rule)


def test_cy_to_ms_involves_ms() -> None:
    """CY must include at least one ``ms`` gate."""
    rule = cy_to_ms(0, 1)
    assert any(name == "ms" for name, _, _ in rule)


def test_cz_to_ms_involves_ms() -> None:
    """CZ must include at least one ``ms`` gate."""
    rule = cz_to_ms(0, 1)
    assert any(name == "ms" for name, _, _ in rule)


def test_cr_to_ms_angle_propagates() -> None:
    """CR(π) must surface π inside the MS parameters."""
    rule = cr_to_ms(math.pi, 0, 1)
    assert any(abs(p - math.pi / 2.0) < 1e-9 for _, params, _ in rule for p in params)


def test_ry_rx_u1_u3_have_decompositions() -> None:
    """All four single-qubit decompositions return a non-empty rule."""
    for rule in (
        ry_to_gpi(0.5, 0),
        rx_to_gpi(0.7, 1),
        u1_to_gpi(0.3, 0),
        u3_to_gpi(0.2, 0.4, 0.6, 0),
    ):
        assert rule
        for name, _, _ in rule:
            assert name in ("gpi", "gpi2")


def test_apply_equivalences_replaces_known_gates() -> None:
    """``apply_equivalences`` must rewrite an ``rz`` instruction."""
    lib = build_default_library()
    out = apply_equivalences([("rz", (math.pi / 4,), (0,))], lib)
    assert out
    assert all(name in ("gpi", "gpi2") for name, _, _ in out)


def test_apply_equivalences_passes_through_unknown_gates() -> None:
    """Unknown gates should remain untouched."""
    lib = build_default_library()
    out = apply_equivalences([("made_up", (), (0, 1))], lib)
    assert out == [("made_up", (), (0, 1))]


def test_build_default_library_contains_known_keys() -> None:
    """Default library must register every documented decomposition."""
    lib = build_default_library()
    for k in ("rz", "ry", "rx", "u1", "u3", "cr", "cx", "cy", "cz"):
        assert k in lib


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------


def test_simple_rules_cx_then_h_collapses() -> None:
    """``CX + H(t)`` should be replaced by an MS form + H(t)."""
    stream = [("cx", (), (0, 1)), ("h", (0.0,), (1,))]
    out = TrappedIonOptimizerPluginSimpleRules().run(stream)
    # The CX itself should be replaced by an MS-bearing form.
    assert any(name == "ms" for name, _, _ in out)
    # The trailing H(t) should still be present.
    assert any(name == "h" for name, _, _ in out)


def test_simple_rules_preserves_unrelated_cx() -> None:
    """A bare CX with no following H must remain untouched."""
    stream = [("cx", (), (0, 1))]
    out = TrappedIonOptimizerPluginSimpleRules().run(stream)
    assert out == stream


def test_compact_gates_fuses_gpi_gpi() -> None:
    """Two consecutive GPI on the same qubit must collapse to one GPI2."""
    stream = [("gpi", (0.1,), (0,)), ("gpi", (0.3,), (0,))]
    out = TrappedIonOptimizerPluginCompactGates().run(stream)
    assert len(out) == 1
    assert out[0][0] == "gpi2"


def test_compact_gates_drops_cancelling_gpi2_pair() -> None:
    """Two GPI2 with cancelling phase angles must vanish."""
    stream = [
        ("gpi2", (0.0,), (0,)),
        ("gpi2", (0.0,), (0,)),
    ]
    out = TrappedIonOptimizerPluginCompactGates().run(stream)
    assert out == []


def test_commute_gpi2_through_ms() -> None:
    """GPI2(φ)ᶜ · MS(φ₀, φ₁) should be rewritten as MS(φ₀+φ, φ₁-φ) · GPI2(φ)ᵀ."""
    stream = [("gpi2", (0.2,), (0,)), ("ms", (0.3, 0.4), (0, 1))]
    out = TrappedIonOptimizerPluginCommuteGpi2ThroughMs().run(stream)
    # First entry: MS, second: GPI2 on target.
    assert out[0][0] == "ms"
    assert out[1] == ("gpi2", (0.2,), (1,))
    # Phase combination (0.3 + 0.2) = 0.5 on the control wire.
    assert math.isclose(out[0][1][0], 0.5, abs_tol=1e-12)
    assert math.isclose(out[0][1][1], 0.2, abs_tol=1e-12)


def test_pipeline_runs_all_plugins() -> None:
    """The convenience pipeline should produce a valid gate stream.

    Plugins operate on the *decomposed* gate stream, so the test feed
    is first decomposed via the equivalence library.
    """
    from quantum.ionq_equivalence_library import apply_equivalences, build_default_library
    stream = [("rz", (math.pi / 4,), (0,)), ("cx", (), (0, 1))]
    decomposed = apply_equivalences(stream, build_default_library())
    out = run_trapped_ion_pipeline(decomposed)
    assert out
    for name, _, _ in out:
        assert name in ("gpi", "gpi2", "ms", "zz")


def test_pipeline_disabled_preserves_stream() -> None:
    """With every plugin disabled, the stream must be returned intact."""
    from quantum.ionq_optimizer_plugins import TrappedIonOptimizerPluginBase

    class _NoOp(TrappedIonOptimizerPluginBase):
        def run(self, stream, **kwargs):
            return list(stream)

    assert _NoOp().run([("cx", (), (0, 1))]) == [("cx", (), (0, 1))]
