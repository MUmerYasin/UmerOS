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

"""Hardware-aware quantum transpiler.

Transpiles logical circuits for specific hardware coupling maps,
supporting routing, decomposition, layout, and optimization passes.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, List, Tuple, Dict
from dataclasses import dataclass, field

from .circuit import QuantumCircuit, Instruction
from .gates import H_GATE, X_GATE, CNOT_GATE, TOFFOLI_GATE, SWAP_GATE
from .native_gates import HardwarePlatform

__all__ = [
    "CouplingMap", "TranspilerPass", "RoutingPass", "DecompositionPass",
    "OptimizationPass", "LayoutPass", "PulseLevelPass", "HardwareTranspiler",
    "IBM_127_QUBIT", "IONQ_11_QUBIT", "RIGETTI_80_QUBIT",
    "transpile_for_hardware", "estimate_circuit_depth", "estimate_swaps_needed",
]


# ---------------------------------------------------------------------------
# CouplingMap
# ---------------------------------------------------------------------------

class CouplingMap:
    """Represents qubit connectivity for a hardware backend."""

    def __init__(self, num_qubits: int, edges: Sequence[Tuple[int, int]],
                 directed: bool = False):
        self.num_qubits = num_qubits
        self.edges = list(edges)
        self.directed = directed
        self._adj: Dict[int, List[int]] = {i: [] for i in range(num_qubits)}
        for a, b in self.edges:
            if a < 0 or a >= num_qubits or b < 0 or b >= num_qubits:
                raise ValueError(
                    f"Edge ({a},{b}) out of range for {num_qubits}-qubit map"
                )
            if a == b:
                raise ValueError(f"Self-loop on qubit {a}")
            self._adj[a].append(b)
            if not directed:
                self._adj[b].append(a)

    def is_connected(self, q1: int, q2: int) -> bool:
        return q2 in self._adj.get(q1, [])

    def neighbors(self, qubit: int) -> List[int]:
        return list(self._adj.get(qubit, []))

    def distance(self, q1: int, q2: int) -> int:
        if q1 == q2:
            return 0
        visited = {q1}
        queue = [(q1, 0)]
        while queue:
            node, d = queue.pop(0)
            for nb in self._adj.get(node, []):
                if nb == q2:
                    return d + 1
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, d + 1))
        return -1

    def shortest_path(self, q1: int, q2: int) -> List[int]:
        if q1 == q2:
            return [q1]
        visited = {q1}
        queue = [(q1, [q1])]
        while queue:
            node, path = queue.pop(0)
            for nb in self._adj.get(node, []):
                if nb == q2:
                    return path + [nb]
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, path + [nb]))
        return []


# ---------------------------------------------------------------------------
# Predefined coupling maps
# ---------------------------------------------------------------------------

def _heavy_hex_edges(n: int) -> List[Tuple[int, int]]:
    """Generate a heavy-hex-like coupling map."""
    edges: List[Tuple[int, int]] = []
    for i in range(n - 1):
        edges.append((i, i + 1))
    for i in range(0, n - 2, 3):
        edges.append((i, i + 2))
    return edges


def _ring_edges(n: int) -> List[Tuple[int, int]]:
    edges = [(i, (i + 1) % n) for i in range(n)]
    return edges


def _all_to_all_edges(n: int) -> List[Tuple[int, int]]:
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


def IBM_127_QUBIT() -> CouplingMap:
    """IBM 127-qubit heavy-hex coupling map."""
    return CouplingMap(127, _heavy_hex_edges(127))


def IONQ_11_QUBIT() -> CouplingMap:
    """IonQ 11-qubit all-to-all coupling map."""
    return CouplingMap(11, _all_to_all_edges(11))


def RIGETTI_80_QUBIT() -> CouplingMap:
    """Rigetti 80-qubit ring coupling map."""
    return CouplingMap(80, _ring_edges(80))


# ---------------------------------------------------------------------------
# Transpiler passes
# ---------------------------------------------------------------------------

class TranspilerPass:
    """Base class for transpiler passes."""

    def run(self, circuit: QuantumCircuit, **kwargs) -> QuantumCircuit:
        raise NotImplementedError


class DecompositionPass(TranspilerPass):
    """Decomposes non-native gates into a target gate set."""

    def __init__(self, target_gates: Optional[List[str]] = None):
        self.target_gates = set(target_gates or ["H", "X", "CNOT"])

    def run(self, circuit: QuantumCircuit, **kwargs) -> QuantumCircuit:
        out = QuantumCircuit(circuit.num_qubits)
        for inst in circuit.instructions:
            if inst.gate.name in ("TOFFOLI", "Toffoli"):
                c0, c1, t = inst.qubits
                for seq in _toffoli_decomposition(c0, c1, t):
                    out._instructions.append(seq)
            elif inst.gate.name == "SWAP":
                q0, q1 = inst.qubits
                for seq in _swap_decomposition(q0, q1):
                    out._instructions.append(seq)
            else:
                out._instructions.append(inst)
        return out


def _toffoli_decomposition(c0: int, c1: int, t: int) -> List[Instruction]:
    return [
        Instruction(gate=H_GATE, qubits=[t]),
        Instruction(gate=CNOT_GATE, qubits=[c1, t]),
        Instruction(gate=_inverse(H_GATE), qubits=[t]),
        Instruction(gate=CNOT_GATE, qubits=[c0, t]),
        Instruction(gate=H_GATE, qubits=[t]),
        Instruction(gate=CNOT_GATE, qubits=[c1, t]),
        Instruction(gate=_inverse(H_GATE), qubits=[t]),
        Instruction(gate=CNOT_GATE, qubits=[c0, t]),
        Instruction(gate=CNOT_GATE, qubits=[c0, c1]),
        Instruction(gate=H_GATE, qubits=[c1]),
        Instruction(gate=CNOT_GATE, qubits=[c0, c1]),
        Instruction(gate=_inverse(H_GATE), qubits=[c1]),
    ]


def _swap_decomposition(q0: int, q1: int) -> List[Instruction]:
    return [
        Instruction(gate=CNOT_GATE, qubits=[q0, q1]),
        Instruction(gate=CNOT_GATE, qubits=[q1, q0]),
        Instruction(gate=CNOT_GATE, qubits=[q0, q1]),
    ]


def _inverse(gate):
    return gate.inverse()


class OptimizationPass(TranspilerPass):
    """Cancel inverse gate pairs."""

    def run(self, circuit: QuantumCircuit, **kwargs) -> QuantumCircuit:
        remaining: List[Instruction] = []
        for inst in circuit.instructions:
            if remaining and (
                inst.gate.name.endswith("†") or inst.gate.name == remaining[-1].gate.name
            ):
                if (inst.gate.num_qubits == remaining[-1].gate.num_qubits
                        and inst.qubits == remaining[-1].qubits
                        and _are_inverse(inst.gate, remaining[-1].gate)):
                    remaining.pop()
                    continue
            remaining.append(inst)
        out = QuantumCircuit(circuit.num_qubits)
        out._instructions = remaining
        return out


def _are_inverse(g1, g2) -> bool:
    if g1.name == g2.name:
        return True
    if g1.name.endswith("†") and g1.name[:-1] == g2.name:
        return True
    if g2.name.endswith("†") and g2.name[:-1] == g1.name:
        return True
    return False


class LayoutPass(TranspilerPass):
    """Maps logical qubits to physical qubits."""

    def __init__(self, method: str = "trivial"):
        self.method = method

    def run(self, circuit: QuantumCircuit, **kwargs) -> QuantumCircuit:
        qubit_weights = kwargs.get("qubit_weights", {})
        if self.method == "noise_aware" and qubit_weights:
            best = min(qubit_weights, key=qubit_weights.get)
            remap = {q: best + i for i, q in enumerate(range(circuit.num_qubits))}
        else:
            remap = {q: q for q in range(circuit.num_qubits)}
        out = QuantumCircuit(circuit.num_qubits)
        for inst in circuit.instructions:
            out._instructions.append(
                Instruction(gate=inst.gate, qubits=[remap[q] for q in inst.qubits])
            )
        return out


class RoutingPass(TranspilerPass):
    """Inserts SWAPs to satisfy coupling constraints."""

    def __init__(self, coupling_map: CouplingMap):
        self.coupling_map = coupling_map

    def run(self, circuit: QuantumCircuit, **kwargs) -> QuantumCircuit:
        out = QuantumCircuit(circuit.num_qubits)
        for inst in circuit.instructions:
            if inst.gate.num_qubits == 2:
                q0, q1 = inst.qubits
                if not self.coupling_map.is_connected(q0, q1):
                    path = self.coupling_map.shortest_path(q0, q1)
                    if len(path) > 2:
                        for i in range(len(path) - 2):
                            out._instructions.append(
                                Instruction(gate=SWAP_GATE, qubits=[path[i], path[i + 1]])
                            )
            out._instructions.append(inst)
        return out


class PulseLevelPass(TranspilerPass):
    """Converts gates to pulse-level representations for specific platforms."""

    def __init__(self, platform: HardwarePlatform):
        self.platform = platform

    def run(self, circuit: QuantumCircuit, **kwargs) -> QuantumCircuit:
        out = QuantumCircuit(circuit.num_qubits)
        for inst in circuit.instructions:
            out._instructions.append(inst)
        return out


# ---------------------------------------------------------------------------
# HardwareTranspiler
# ---------------------------------------------------------------------------

class HardwareTranspiler:
    """Full hardware-aware transpiler pipeline."""

    def __init__(self, platform: HardwarePlatform = HardwarePlatform.SUPERCONDUCTING):
        self.platform = platform
        self._coupling = self._default_coupling()

    def _default_coupling(self) -> CouplingMap:
        if self.platform == HardwarePlatform.TRAPPED_ION:
            return IONQ_11_QUBIT()
        elif self.platform == HardwarePlatform.SUPERCONDUCTING:
            return IBM_127_QUBIT()
        return RIGETTI_80_QUBIT()

    def transpile(self, circuit: QuantumCircuit,
                  initial_layout: Optional[Dict[int, int]] = None,
                  optimization_level: int = 0) -> QuantumCircuit:
        max_q = self._coupling.num_qubits
        if circuit.num_qubits > max_q:
            raise ValueError(
                f"Circuit has {circuit.num_qubits} qubits, "
                f"but {self.platform.name} only has {max_q}"
            )
        result = circuit
        layout = LayoutPass(method="trivial")
        result = layout.run(result)
        if initial_layout:
            out = QuantumCircuit(circuit.num_qubits)
            for inst in result.instructions:
                mapped = [initial_layout.get(q, q) for q in inst.qubits]
                out._instructions.append(Instruction(gate=inst.gate, qubits=mapped))
            result = out
        routing = RoutingPass(self._coupling)
        result = routing.run(result)
        if optimization_level > 0:
            opt = OptimizationPass()
            result = opt.run(result)
        return result

    def transpile_and_report(self, circuit: QuantumCircuit) -> Tuple[QuantumCircuit, Dict]:
        initial_count = len(circuit.instructions)
        result = self.transpile(circuit)
        final_count = len(result.instructions)
        report = {
            "platform": self.platform.name,
            "initial_gate_count": initial_count,
            "final_gate_count": final_count,
        }
        return result, report


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def transpile_for_hardware(circuit: QuantumCircuit,
                           platform: HardwarePlatform) -> QuantumCircuit:
    transpiler = HardwareTranspiler(platform)
    return transpiler.transpile(circuit)


def estimate_circuit_depth(circuit: QuantumCircuit) -> int:
    if not circuit.instructions:
        return 0
    depth = 0
    qubit_depth: Dict[int, int] = {}
    for inst in circuit.instructions:
        max_d = max((qubit_depth.get(q, 0) for q in inst.qubits), default=0)
        depth = max_d + 1
        for q in inst.qubits:
            qubit_depth[q] = depth
    return depth


def estimate_swaps_needed(circuit: QuantumCircuit, coupling: CouplingMap) -> int:
    swaps = 0
    for inst in circuit.instructions:
        if inst.gate.num_qubits == 2:
            q0, q1 = inst.qubits
            if not coupling.is_connected(q0, q1):
                path = coupling.shortest_path(q0, q1)
                if len(path) > 2:
                    swaps += len(path) - 2
    return swaps
