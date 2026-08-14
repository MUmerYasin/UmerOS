"""Tests for the IonQ equivalence library and optimizer plugin family."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

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
    TrappedIonOptimizerPluginBase,
    run_trapped_ion_pipeline,
)


class TestEquivalenceLibrary(unittest.TestCase):
    def test_rz_to_gpi_native_only(self):
        rule = rz_to_gpi(math.pi / 3, qubit=0)
        self.assertTrue(rule)
        for name, _, _ in rule:
            self.assertIn(name, ("gpi", "gpi2"))

    def test_cx_to_ms_has_ms(self):
        rule = cx_to_ms(0, 1)
        self.assertTrue(any(name == "ms" for name, _, _ in rule))

    def test_cy_to_ms_has_ms(self):
        rule = cy_to_ms(0, 1)
        self.assertTrue(any(name == "ms" for name, _, _ in rule))

    def test_cz_to_ms_has_ms(self):
        rule = cz_to_ms(0, 1)
        self.assertTrue(any(name == "ms" for name, _, _ in rule))

    def test_cr_to_ms_angle(self):
        rule = cr_to_ms(math.pi, 0, 1)
        self.assertTrue(any(abs(p - math.pi / 2.0) < 1e-9 for _, params, _ in rule for p in params))

    def test_ry_rx_u1_u3_decompositions(self):
        for rule in (
            ry_to_gpi(0.5, 0),
            rx_to_gpi(0.7, 1),
            u1_to_gpi(0.3, 0),
            u3_to_gpi(0.2, 0.4, 0.6, 0),
        ):
            self.assertTrue(rule)
            for name, _, _ in rule:
                self.assertIn(name, ("gpi", "gpi2"))

    def test_apply_equivalences_replaces_rz(self):
        lib = build_default_library()
        out = apply_equivalences([("rz", (math.pi / 4,), (0,))], lib)
        self.assertTrue(out)
        self.assertTrue(all(name in ("gpi", "gpi2") for name, _, _ in out))

    def test_apply_equivalences_passes_unknown(self):
        lib = build_default_library()
        out = apply_equivalences([("made_up", (), (0, 1))], lib)
        self.assertEqual(out, [("made_up", (), (0, 1))])

    def test_build_default_library_keys(self):
        lib = build_default_library()
        for k in ("rz", "ry", "rx", "u1", "u3", "cr", "cx", "cy", "cz"):
            self.assertIn(k, lib)


class TestPlugins(unittest.TestCase):
    def test_simple_rules_cx_then_h(self):
        stream = [("cx", (), (0, 1)), ("h", (0.0,), (1,))]
        out = TrappedIonOptimizerPluginSimpleRules().run(stream)
        self.assertTrue(any(name == "ms" for name, _, _ in out))
        self.assertTrue(any(name == "h" for name, _, _ in out))

    def test_simple_rules_preserves_bare_cx(self):
        stream = [("cx", (), (0, 1))]
        out = TrappedIonOptimizerPluginSimpleRules().run(stream)
        self.assertEqual(out, stream)

    def test_compact_gates_fuses_gpi(self):
        stream = [("gpi", (0.1,), (0,)), ("gpi", (0.3,), (0,))]
        out = TrappedIonOptimizerPluginCompactGates().run(stream)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "gpi2")

    def test_compact_gates_drops_cancelling_gpi2(self):
        stream = [("gpi2", (0.0,), (0,)), ("gpi2", (0.0,), (0,))]
        out = TrappedIonOptimizerPluginCompactGates().run(stream)
        self.assertEqual(out, [])

    def test_commute_gpi2_through_ms(self):
        stream = [("gpi2", (0.2,), (0,)), ("ms", (0.3, 0.4), (0, 1))]
        out = TrappedIonOptimizerPluginCommuteGpi2ThroughMs().run(stream)
        self.assertEqual(out[0][0], "ms")
        self.assertEqual(out[1], ("gpi2", (0.2,), (1,)))
        self.assertTrue(math.isclose(out[0][1][0], 0.5, abs_tol=1e-12))
        self.assertTrue(math.isclose(out[0][1][1], 0.2, abs_tol=1e-12))

    def test_pipeline_all_native(self):
        stream = [("rz", (math.pi / 4,), (0,)), ("cx", (), (0, 1))]
        decomposed = apply_equivalences(stream, build_default_library())
        out = run_trapped_ion_pipeline(decomposed)
        self.assertTrue(out)
        for name, _, _ in out:
            self.assertIn(name, ("gpi", "gpi2", "ms", "zz"))

    def test_pipeline_disabled_preserves(self):
        class _NoOp(TrappedIonOptimizerPluginBase):
            def run(self, stream, **kwargs):
                return list(stream)
        self.assertEqual(_NoOp().run([("cx", (), (0, 1))]), [("cx", (), (0, 1))])


if __name__ == "__main__":
    unittest.main()
