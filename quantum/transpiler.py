"""Quantum Transpiler - Circuit optimization and hardware mapping.

Implements a 6-stage transpilation pipeline:
1. Init - Initial layout selection
2. Layout - Physical-to-logical qubit mapping
3. Routing - SWAP insertion for non-adjacent gates
4. Translation - Decompose to target gate set
5. Optimization - Circuit optimization passes
6. Scheduling - Gate scheduling and timing

Usage:
    from quantum.transpiler import transpile, PassManager
    optimized = transpile(circuit, backend=target, optimization_level=2)
"""

from __future__ import annotations

import math
from typing import Optional, List, Dict, Set, Tuple
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from .circuit import QuantumCircuit, Instruction, QuantumRegister
from .gates import (
    Gate, get_gate, I_GATE, X_GATE, Y_GATE, Z_GATE, H_GATE,
    S_GATE, T_GATE, CNOT_GATE, CZ_GATE, SWAP_GATE,
    TOFFOLI_GATE, rx, ry, rz, phase_gate
)


# ---------------------------------------------------------------------------
# Coupling map / topology
# ---------------------------------------------------------------------------

class CouplingMap:
    """Defines which qubit pairs can interact directly."""

    def __init__(self, edges: List[Tuple[int, int]], num_qubits: Optional[int] = None):
        self.edges = set()
        for a, b in edges:
            self.edges.add((min(a, b), max(a, b)))
        self._num_qubits = num_qubits or (max(max(e) for e in self.edges) + 1 if edges else 0)
        self._adj: Dict[int, Set[int]] = {i: set() for i in range(self._num_qubits)}
        for a, b in self.edges:
            self._adj[a].add(b)
            self._adj[b].add(a)

    @property
    def num_qubits(self) -> int:
        return self._num_qubits

    def are_connected(self, q1: int, q2: int) -> bool:
        return (min(q1, q2), max(q1, q2)) in self.edges

    def neighbors(self, qubit: int) -> Set[int]:
        return self._adj.get(qubit, set())

    def distance(self, q1: int, q2: int) -> int:
        """BFS shortest path distance."""
        if q1 == q2:
            return 0
        visited = {q1}
        queue = [q1]
        dist = 0
        while queue:
            dist += 1
            next_queue = []
            for q in queue:
                for n in self._adj.get(q, set()):
                    if n == q2:
                        return dist
                    if n not in visited:
                        visited.add(n)
                        next_queue.append(n)
            queue = next_queue
        return -1

    def shortest_path(self, q1: int, q2: int) -> List[int]:
        """Find shortest path between two qubits."""
        if q1 == q2:
            return [q1]
        visited = {q1}
        queue = [[q1]]
        while queue:
            path = queue.pop(0)
            q = path[-1]
            for n in self._adj.get(q, set()):
                if n == q2:
                    return path + [n]
                if n not in visited:
                    visited.add(n)
                    queue.append(path + [n])
        return []

    @classmethod
    def line(cls, num_qubits: int) -> "CouplingMap":
        """Create linear coupling: 0-1-2-...-n."""
        edges = [(i, i + 1) for i in range(num_qubits - 1)]
        return cls(edges, num_qubits)

    @classmethod
    def grid(cls, rows: int, cols: int) -> "CouplingMap":
        """Create 2D grid coupling."""
        edges = []
        n = rows * cols
        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                if c + 1 < cols:
                    edges.append((idx, idx + 1))
                if r + 1 < rows:
                    edges.append((idx, idx + cols))
        return cls(edges, n)

    @classmethod
    def full(cls, num_qubits: int) -> "CouplingMap":
        """Fully connected topology."""
        edges = [(i, j) for i in range(num_qubits) for j in range(i + 1, num_qubits)]
        return cls(edges, num_qubits)


# ---------------------------------------------------------------------------
# Transpiler target
# ---------------------------------------------------------------------------

@dataclass
class TargetGateSet:
    """Target gate set for transpilation."""
    gates: List[str] = field(default_factory=lambda: ["cx", "rz", "sx", "x"])

    @classmethod
    def clifford_plus_t(cls) -> "TargetGateSet":
        return cls(gates=["cx", "h", "s", "t", "x", "z"])

    @classmethod
    def ibm(cls) -> "TargetGateSet":
        return cls(gates=["cx", "rz", "sx", "x"])

    @classmethod
    def universal(cls) -> "TargetGateSet":
        return cls(gates=["cx", "u3"])

    @classmethod
    def rypp(cls) -> "TargetGateSet":
        return cls(gates=["cxx", "ry", "rz", "x"])


# ---------------------------------------------------------------------------
# Transpiler passes
# ---------------------------------------------------------------------------

class PassResult:
    """Result of a transpilation pass."""
    def __init__(self, circuit: QuantumCircuit, modified: bool = False):
        self.circuit = circuit
        self.modified = modified


class BasePass:
    """Base class for transpiler passes."""
    def run(self, circuit: QuantumCircuit, **kwargs) -> PassResult:
        raise NotImplementedError


class DecomposeToBasicPass(BasePass):
    """Decompose multi-qubit gates into the target gate set."""

    def __init__(self, target_gate_set: Optional[TargetGateSet] = None):
        self.target = target_gate_set or TargetGateSet.ibm()

    def run(self, circuit: QuantumCircuit, **kwargs) -> PassResult:
        new_insts = []
        modified = False

        for inst in circuit:
            if inst.gate.name == "measure":
                new_insts.append(inst)
                continue

            decomposed = self._decompose_gate(inst)
            if decomposed is not None:
                new_insts.extend(decomposed)
                modified = True
            else:
                new_insts.append(inst)

        result_circuit = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
        for inst in new_insts:
            result_circuit._instructions.append(inst)

        return PassResult(result_circuit, modified)

    def _decompose_gate(self, inst: Instruction) -> Optional[List[Instruction]]:
        """Decompose a gate into the target set."""
        name = inst.gate.name

        if name in self.target.gates:
            return None

        if name == "swap":
            return [
                Instruction(CNOT_GATE, [inst.qubits[0], inst.qubits[1]]),
                Instruction(CNOT_GATE, [inst.qubits[1], inst.qubits[0]]),
                Instruction(CNOT_GATE, [inst.qubits[0], inst.qubits[1]]),
            ]

        if name == "ccx":
            q0, q1, q2 = inst.qubits
            return [
                Instruction(H_GATE, [q2]),
                Instruction(CNOT_GATE, [q1, q2]),
                Instruction(T_GATE, [q2]),
                Instruction(CNOT_GATE, [q0, q2]),
                Instruction(T_GATE.dagger(), [q2]),
                Instruction(CNOT_GATE, [q1, q2]),
                Instruction(T_GATE.dagger(), [q2]),
                Instruction(CNOT_GATE, [q0, q2]),
                Instruction(T_GATE, [q1]),
                Instruction(T_GATE, [q2]),
                Instruction(H_GATE, [q2]),
                Instruction(CNOT_GATE, [q0, q1]),
                Instruction(T_GATE.dagger(), [q0]),
                Instruction(T_GATE, [q1]),
                Instruction(CNOT_GATE, [q0, q1]),
            ]

        if name == "cy":
            q0, q1 = inst.qubits
            return [
                Instruction(H_GATE, [q1]),
                Instruction(CNOT_GATE, [q0, q1]),
                Instruction(H_GATE, [q1]),
            ]

        if name == "cz":
            q0, q1 = inst.qubits
            return [
                Instruction(H_GATE, [q1]),
                Instruction(CNOT_GATE, [q0, q1]),
                Instruction(H_GATE, [q1]),
            ]

        if name == "ch":
            q0, q1 = inst.qubits
            return [
                Instruction(H_GATE, [q1]),
                Instruction(S_GATE.dagger(), [q1]),
                Instruction(H_GATE, [q1]),
                Instruction(CNOT_GATE, [q0, q1]),
                Instruction(H_GATE, [q1]),
                Instruction(S_GATE, [q1]),
                Instruction(H_GATE, [q1]),
            ]

        if name == "iswap":
            q0, q1 = inst.qubits
            return [
                Instruction(H_GATE, [q0]),
                Instruction(CNOT_GATE, [q0, q1]),
                Instruction(CNOT_GATE, [q1, q0]),
                Instruction(H_GATE, [q1]),
            ]

        return None


class SwapRoutingPass(BasePass):
    """Insert SWAP gates for non-adjacent two-qubit interactions."""

    def __init__(self, coupling_map: CouplingMap):
        self.coupling_map = coupling_map

    def run(self, circuit: QuantumCircuit, **kwargs) -> PassResult:
        layout = kwargs.get("layout", {i: i for i in range(circuit.num_qubits)})
        reverse_layout = {v: k for k, v in layout.items()}

        new_insts = []
        current_layout = layout.copy()
        modified = False

        for inst in circuit:
            if len(inst.qubits) <= 1:
                new_insts.append(inst)
                continue

            q0_phys = current_layout[inst.qubits[0]]
            q1_phys = current_layout[inst.qubits[1]]

            if self.coupling_map.are_connected(q0_phys, q1_phys):
                new_insts.append(inst)
            else:
                path = self.coupling_map.shortest_path(q0_phys, q1_phys)
                if len(path) < 2:
                    new_insts.append(inst)
                    continue

                for i in range(len(path) - 2, -1, -1):
                    p1, p2 = path[i], path[i + 1]
                    l1 = reverse_layout.get(p1, p1)
                    l2 = reverse_layout.get(p2, p2)

                    new_insts.append(Instruction(SWAP_GATE, [l1, l2]))

                    for k, v in current_layout.items():
                        if v == p1:
                            current_layout[k] = p2
                        elif v == p2:
                            current_layout[k] = p1

                    reverse_layout = {v: k for k, v in current_layout.items()}

                new_insts.append(inst)
                modified = True

        result_circuit = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
        for inst in new_insts:
            result_circuit._instructions.append(inst)

        return PassResult(result_circuit, modified)


class BasicLayoutPass(BasePass):
    """Simple default layout: logical i -> physical i."""

    def run(self, circuit: QuantumCircuit, **kwargs) -> PassResult:
        layout = {i: i for i in range(circuit.num_qubits)}
        return PassResult(circuit, modified=False), layout


class RandomLayoutPass(BasePass):
    """Random layout assignment."""

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed

    def run(self, circuit: QuantumCircuit, **kwargs) -> PassResult:
        rng = np.random.RandomState(self.seed)
        perm = rng.permutation(circuit.num_qubits)
        layout = {i: int(perm[i]) for i in range(circuit.num_qubits)}
        return PassResult(circuit, modified=False), layout


class OptimizationPass(BasePass):
    """Remove redundant gates and combine adjacent rotations."""

    def run(self, circuit: QuantumCircuit, **kwargs) -> PassResult:
        instructions = list(circuit)
        modified = False

        changed = True
        while changed:
            changed = False
            new_insts = []
            i = 0
            while i < len(instructions):
                if i + 1 < len(instructions):
                    merged = self._try_merge(instructions[i], instructions[i + 1])
                    if merged is not None:
                        new_insts.extend(merged)
                        i += 2
                        changed = True
                        modified = True
                        continue

                if self._is_identity(instructions[i]):
                    changed = True
                    modified = True
                    i += 1
                    continue

                new_insts.append(instructions[i])
                i += 1

            instructions = new_insts

        result_circuit = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
        for inst in instructions:
            result_circuit._instructions.append(inst)

        return PassResult(result_circuit, modified)

    def _try_merge(self, i1: Instruction, i2: Instruction) -> Optional[List[Instruction]]:
        """Try merging two adjacent same-qubit single-qubit gates."""
        if len(i1.qubits) != 1 or len(i2.qubits) != 1:
            return None
        if i1.qubits != i2.qubits:
            return None
        if i1.gate.name == i2.gate.name and i1.gate.name in ("rz", "rx", "ry"):
            p1 = getattr(i1.gate, "params", [0])
            p2 = getattr(i2.gate, "params", [0])
            if p1 and p2:
                combined = p1[0] + p2[0]
                return [Instruction(get_gate(i1.gate.name, combined), i1.qubits)]
        return None

    def _is_identity(self, inst: Instruction) -> bool:
        """Check if gate is effectively identity."""
        if inst.gate.name == "i":
            return True
        if inst.gate.name in ("rz", "rx", "ry"):
            params = getattr(inst.gate, "params", [0])
            if params:
                return abs(params[0] % (2 * math.pi)) < 1e-10
        return False


# ---------------------------------------------------------------------------
# Pass Manager
# ---------------------------------------------------------------------------

class PassManager:
    """Manages a sequence of transpiler passes."""

    def __init__(self, passes: Optional[List[BasePass]] = None):
        self.passes = passes or []

    def add_pass(self, p: BasePass):
        self.passes.append(p)
        return self

    def run(self, circuit: QuantumCircuit, **kwargs) -> QuantumCircuit:
        current = circuit
        for p in self.passes:
            result = p.run(current, **kwargs)
            current = result.circuit
            if isinstance(result, tuple) and len(result) > 1:
                kwargs.update({"layout": result[1]})
        return current


# ---------------------------------------------------------------------------
# Transpiler
# ---------------------------------------------------------------------------

class Transpiler:
    """Main transpiler that orchestrates the 6-stage pipeline."""

    def __init__(self, coupling_map: Optional[CouplingMap] = None,
                 target_gate_set: Optional[TargetGateSet] = None,
                 optimization_level: int = 1):
        self.coupling_map = coupling_map
        self.target = target_gate_set or TargetGateSet.ibm()
        self.optimization_level = optimization_level

    def transpile(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Run the full transpilation pipeline."""
        current = circuit

        layout = self._select_layout(current)
        if self.coupling_map:
            current = self._route(current, layout)

        current = self._decompose(current)

        for _ in range(self.optimization_level + 1):
            current = self._optimize(current)

        return current

    def _select_layout(self, circuit: QuantumCircuit) -> Dict[int, int]:
        """Stage 1-2: Layout selection."""
        return {i: i for i in range(circuit.num_qubits)}

    def _route(self, circuit: QuantumCircuit, layout: Dict[int, int]) -> QuantumCircuit:
        """Stage 3: SWAP routing."""
        if self.coupling_map is None:
            return circuit
        pass_mgr = PassManager([SwapRoutingPass(self.coupling_map)])
        return pass_mgr.run(circuit, layout=layout)

    def _decompose(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Stage 4: Gate decomposition."""
        pass_mgr = PassManager([DecomposeToBasicPass(self.target)])
        return pass_mgr.run(circuit).circuit

    def _optimize(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Stage 5: Optimization."""
        pass_mgr = PassManager([OptimizationPass()])
        return pass_mgr.run(circuit).circuit


def transpile(circuit: QuantumCircuit,
              coupling_map: Optional[CouplingMap] = None,
              target_gate_set: Optional[TargetGateSet] = None,
              optimization_level: int = 1) -> QuantumCircuit:
    """High-level transpile function.

    Args:
        circuit: Input circuit
        coupling_map: Hardware topology
        target_gate_set: Target gates
        optimization_level: 0-3
    """
    t = Transpiler(coupling_map, target_gate_set, optimization_level)
    return t.transpile(circuit)
