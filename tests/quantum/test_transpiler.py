"""Tests for quantum.transpiler — CouplingMap, PassManager, transpile()."""

import math
import pytest
import numpy as np

from quantum.circuit import QuantumCircuit
from quantum.transpiler import CouplingMap, PassManager, transpile


class TestCouplingMap:
    def test_linear(self):
        cmap = CouplingMap([[0, 1], [1, 2]])
        assert cmap.size == 3

    def test_full(self):
        cmap = CouplingMap([[0, 1], [1, 0], [0, 2], [2, 0]])
        assert cmap.size == 3

    def test_empty(self):
        cmap = CouplingMap([])
        assert cmap.size == 0

    def test_repr(self):
        cmap = CouplingMap([[0, 1]])
        r = repr(cmap)
        assert "CouplingMap" in r


class TestPassManager:
    def test_create(self):
        pm = PassManager()
        assert pm is not None

    def test_run_circuit(self):
        pm = PassManager()
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        result = pm.run(qc)
        assert result is not None
        assert result.num_qubits == 2


class TestTranspile:
    def test_identity_circuit(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        result = transpile(qc)
        assert result.num_qubits == 1
        assert result.size() >= 1

    def test_preserves_qubits(self):
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.cx(1, 2)
        result = transpile(qc)
        assert result.num_qubits == 3

    def test_with_coupling_map(self):
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.cx(1, 2)
        cmap = CouplingMap([[0, 1], [1, 2]])
        result = transpile(qc, coupling_map=cmap)
        assert result.num_qubits == 3

    def test_empty_circuit(self):
        qc = QuantumCircuit(2)
        result = transpile(qc)
        assert result.num_qubits == 2

    def test_visualize(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        result = transpile(qc)
        vis = result.visualize()
        assert isinstance(vis, str)
