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
        assert abs(sv.norm() - 1.0) < 1e-10

    def test_probabilities(self):
        sv = Statevector(np.array([1 / np.sqrt(2), 1 / np.sqrt(2)], dtype=complex))
        probs = sv.probabilities_dict()
        assert "0" in probs
        assert "1" in probs
        np.testing.assert_allclose(probs["0"], 0.5, atol=1e-10)

    def test_is_valid(self):
        sv = Statevector(np.array([1, 0], dtype=complex))
        assert sv.is_valid()

    def test_measure(self):
        sv = Statevector(np.array([1, 0], dtype=complex))
        result = sv.measure()
        assert result == 0 or isinstance(result, tuple)

    def test_repr(self):
        sv = Statevector(np.array([1, 0], dtype=complex))
        r = repr(sv)
        assert "Statevector" in r


class TestMeasurementResult:
    def test_counts(self):
        mr = MeasurementResult([0, 1, 0, 1, 0], 5)
        counts = mr.get_counts()
        assert counts[0] == 3
        assert counts[1] == 2

    def test_probabilities(self):
        mr = MeasurementResult([0, 0, 1, 1], 4)
        probs = mr.probabilities()
        assert probs[0] == 0.5
        assert probs[1] == 0.5


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
        probs = sv.probabilities_dict()
        assert "0" in probs
        assert "1" in probs
        np.testing.assert_allclose(probs["0"], 0.5, atol=1e-10)

    def test_run_x_gate(self):
        qc = QuantumCircuit(1)
        qc.x(0)
        sim = StatevectorSimulator()
        sv = sim.run_with_state(qc)
        probs = sv.probabilities_dict()
        assert "1" in probs
        np.testing.assert_allclose(probs["1"], 1.0, atol=1e-10)

    def test_run_bell_state(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        sim = StatevectorSimulator()
        sv = sim.run_with_state(qc)
        probs = sv.probabilities_dict()
        assert "00" in probs
        assert "11" in probs
        np.testing.assert_allclose(probs["00"], 0.5, atol=1e-10)
        np.testing.assert_allclose(probs["11"], 0.5, atol=1e-10)

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
        probs = sv.probabilities_dict()
        assert "111" in probs
        np.testing.assert_allclose(probs["111"], 1.0, atol=1e-10)
