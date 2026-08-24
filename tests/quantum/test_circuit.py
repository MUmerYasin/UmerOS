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

"""Tests for quantum.circuit — QuantumCircuit, registers, Instruction."""

import math
import pytest
import numpy as np

from quantum.circuit import (
    QuantumCircuit,
    QuantumRegister,
    ClassicalRegister,
    Instruction,
)
from quantum.gates import H, X, CX, RZ


class TestQuantumRegister:
    def test_create_default(self):
        r = QuantumRegister(3)
        assert r.size == 3
        assert r.name == "q"

    def test_create_named(self):
        r = QuantumRegister(4, name="reg")
        assert r.name == "reg"

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            QuantumRegister(-1)


class TestClassicalRegister:
    def test_create_default(self):
        r = ClassicalRegister(2)
        assert r.size == 2

    def test_create_named(self):
        r = ClassicalRegister(5, name="meas")
        assert r.name == "meas"


class TestInstruction:
    def test_properties(self):
        # [RECONCILE] The shipped Instruction is a dataclass(gate, qubits,
        # clbits, params) — not Qiskit's (name, num_qubits, num_clbits, params,
        # definition). Build it with the real fields and assert on those.
        inst = Instruction(gate=H, qubits=[0], clbits=[], params=[math.pi])
        assert inst.gate.name == "H"
        assert len(inst.qubits) == 1
        assert len(inst.clbits) == 0
        assert inst.params == [math.pi]

    def test_repr(self):
        inst = Instruction(gate=X, qubits=[0], clbits=[])
        assert "x" in repr(inst).lower()


class TestQuantumCircuit:
    def test_empty(self):
        qc = QuantumCircuit(1)
        assert qc.num_qubits == 1
        assert qc.size() == 0

    def test_with_classical_register(self):
        qc = QuantumCircuit(2, 2)
        assert qc.num_qubits == 2
        assert qc.num_clbits == 2

    def test_append_gate(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        assert qc.size() == 1

    def test_cnot(self):
        qc = QuantumCircuit(2)
        qc.cx(0, 1)
        assert qc.size() == 1

    def test_toffoli(self):
        qc = QuantumCircuit(3)
        qc.ccx(0, 1, 2)
        assert qc.size() == 1

    def test_rz(self):
        qc = QuantumCircuit(1)
        qc.rz(math.pi / 4, 0)
        assert qc.size() == 1

    def test_swap(self):
        qc = QuantumCircuit(2)
        qc.swap(0, 1)
        assert qc.size() == 1

    def test_compose(self):
        qc1 = QuantumCircuit(2)
        qc1.h(0)
        qc2 = QuantumCircuit(2)
        qc2.cx(0, 1)
        # [RECONCILE] The shipped QuantumCircuit.compose returns a NEW circuit
        # (it has no inplace= kwarg), so reassign the result.
        qc1 = qc1.compose(qc2)
        assert qc1.size() == 2

    def test_copy(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        qc2 = qc.copy()
        assert qc2.size() == qc.size()

    def test_depth(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        assert qc.depth() >= 1

    def test_qasm_output(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        qasm = qc.qasm()
        assert "OPENQASM" in qasm or "h" in qasm.lower()

    def test_invalid_qubit_raises(self):
        qc = QuantumCircuit(2)
        with pytest.raises((IndexError, ValueError)):
            qc.h(5)

    def test_num_ancillas(self):
        qc = QuantumCircuit(3)
        assert qc.num_ancillas == 0

    def test_visualize_returns_str(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        # [RECONCILE] The shipped QuantumCircuit exposes draw() for text
        # rendering (no visualize() method).
        result = qc.draw()
        assert isinstance(result, str)
        assert "q[0]" in result or "q0" in result or "H" in result
