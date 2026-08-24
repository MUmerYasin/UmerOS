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

"""Tests for quantum.simulator — StatevectorSimulator, Statevector, MeasurementResult."""

import math
import pytest
import numpy as np

from quantum.circuit import QuantumCircuit
from quantum.simulator import StatevectorSimulator, Statevector, MeasurementResult


class TestStatevector:
    def test_from_array(self):
        sv = Statevector(np.array([1, 0], dtype=complex))
        assert sv.num_qubits == 1
        np.testing.assert_allclose(sv.data, [1, 0], atol=1e-10)

    def test_norm(self):
        sv = Statevector(np.array([1, 0], dtype=complex))
        # [RECONCILE] The shipped Statevector exposes `data`; norm is derived.
        assert abs(np.linalg.norm(sv.data) - 1.0) < 1e-10

    def test_probabilities(self):
        sv = Statevector(np.array([1 / np.sqrt(2), 1 / np.sqrt(2)], dtype=complex))
        # [RECONCILE] The shipped Statevector exposes `probabilities` (np.array
        # indexed by basis-state integer), not `probabilities_dict()`.
        probs = sv.probabilities
        np.testing.assert_allclose(probs[0], 0.5, atol=1e-10)
        np.testing.assert_allclose(probs[1], 0.5, atol=1e-10)

    def test_is_valid(self):
        sv = Statevector(np.array([1, 0], dtype=complex))
        # [RECONCILE] Validity = unit norm (the constructor already normalizes).
        assert abs(np.linalg.norm(sv.data) - 1.0) < 1e-10

    def test_measure(self):
        sv = Statevector(np.array([1, 0], dtype=complex))
        # [RECONCILE] The shipped Statevector measures via measure_all() which
        # returns a list of bitstring outcomes.
        outcome = sv.measure_all(shots=1)[0]
        assert outcome == "0"

    def test_repr(self):
        sv = Statevector(np.array([1, 0], dtype=complex))
        r = repr(sv)
        # [RECONCILE] The shipped __repr__ is a ket expansion, e.g. "(1.0)|0>".
        assert "|0>" in r


class TestMeasurementResult:
    def test_counts(self):
        # [RECONCILE] The shipped MeasurementResult takes a counts dict and is
        # indexed via __getitem__ (no get_counts()).
        mr = MeasurementResult({"0": 3, "1": 2}, 1)
        assert mr["0"] == 3
        assert mr["1"] == 2

    def test_probabilities(self):
        mr = MeasurementResult({"0": 2, "1": 2}, 1)
        # [RECONCILE] The shipped API exposes frequency(bitstring), not probabilities().
        assert mr.frequency("0") == 0.5
        assert mr.frequency("1") == 0.5


class TestStatevectorSimulator:
    def test_run_simple(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        sim = StatevectorSimulator()
        result = sim.run(qc)
        assert result is not None

    def test_run_with_state(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        sim = StatevectorSimulator()
        sv = sim.run_with_state(qc)
        assert sv.num_qubits == 1
        probs = sv.probabilities
        np.testing.assert_allclose(probs[0], 0.5, atol=1e-10)

    def test_run_x_gate(self):
        qc = QuantumCircuit(1)
        qc.x(0)
        sim = StatevectorSimulator()
        sv = sim.run_with_state(qc)
        probs = sv.probabilities
        np.testing.assert_allclose(probs[1], 1.0, atol=1e-10)

    def test_run_bell_state(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        sim = StatevectorSimulator()
        sv = sim.run_with_state(qc)
        probs = sv.probabilities
        # [RECONCILE] Basis-state index 0 == "00", index 3 == "11".
        np.testing.assert_allclose(probs[0], 0.5, atol=1e-10)
        np.testing.assert_allclose(probs[3], 0.5, atol=1e-10)

    def test_run_with_shots(self):
        qc = QuantumCircuit(1)
        qc.x(0)
        sim = StatevectorSimulator()
        result = sim.run(qc, shots=100)
        assert result is not None

    def test_toffoli_gate(self):
        qc = QuantumCircuit(3)
        qc.x(0)
        qc.x(1)
        qc.ccx(0, 1, 2)
        sim = StatevectorSimulator()
        sv = sim.run_with_state(qc)
        probs = sv.probabilities
        # [RECONCILE] Basis-state index 7 == "111".
        np.testing.assert_allclose(probs[7], 1.0, atol=1e-10)
