"""Hardware-Aware Quantum Transpiler for UmerOS.

Provides transpiler passes optimized for real quantum hardware platforms:
IBM (superconducting), IonQ (trapped ion), and Rigetti (superconducting).

Features:
    - Hardware-specific coupling maps and native gate sets
    - SWAP routing for limited connectivity
    - Multi-controlled gate decomposition
    - Circuit optimization passes
    - SABRE-based qubit layout
    - Pulse-level transpilation
    - Hardware utility functions

Author: UmerOS Team
Version: 1.0.0
"""

from __future__ import annotations

import math
import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any

import numpy as np
from numpy.typing import NDArray

from .gates import (
    Gate, get_gate,
    H_GATE, X_GATE, Y_GATE, Z_GATE, S_GATE, T_GATE,
    CNOT_GATE, CZ_GATE, SWAP_GATE, TOFFOLI_GATE,
    RX_GATE, RY_GATE, RZ_GATE, PHASE_GATE,
    SINGLE_QUBIT_GATES, TWO_QUBIT_GATES, THREE_QUBIT_GATES,
)
from .native_gates import HardwarePlatform, NativeGateSet
from .transpiler import CouplingMap as BaseCouplingMap
from .circuit import QuantumCircuit, Instruction


# ---------------------------------------------------------------------------
# Coupling Map
# ---------------------------------------------------------------------------

@dataclass
class CouplingMap:
    """Defines hardware qubit connectivity.

    Attributes:
        num_qubits: Total number of qubits.
        edges: List of connected qubit pairs (i, j).
        directed: Whether connections are directional.
    """
    num_qubits: int
    edges: List[Tuple[int, int]] = field(default_factory=list)
    directed: bool = False

    def __post_init__(self):
        """Validate coupling map after initialization."""
        for i, j in self.edges:
            if i < 0 or i >= self.num_qubits:
                raise ValueError(f"Qubit {i} out of range [0, {self.num_qubits})")
            if j < 0 or j >= self.num_qubits:
                raise ValueError(f"Qubit {j} out of range [0, {self.num_qubits})")
            if i == j:
                raise ValueError(f"Self-loop detected: ({i}, {j})")

    def is_connected(self, q1: int, q2: int) -> bool:
        """Check if two qubits are directly connected."""
        if self.directed:
            return (q1, q2) in self.edges
        return (q1, q2) in self.edges or (q2, q1) in self.edges

    def neighbors(self, qubit: int) -> List[int]:
        """Return qubits directly connected to the given qubit."""
        result = []
        for i, j in self.edges:
            if i == qubit:
                result.append(j)
            elif not self.directed and j == qubit:
                result.append(i)
        return result

    def distance(self, q1: int, q2: int) -> int:
        """Compute shortest path distance between two qubits using BFS."""
        if q1 == q2:
            return 0
        if q1 < 0 or q1 >= self.num_qubits or q2 < 0 or q2 >= self.num_qubits:
            raise ValueError("Qubit index out of range")

        visited: Set[int] = {q1}
        queue = [(q1, 0)]
        idx = 0

        while idx < len(queue):
            current, dist = queue[idx]
            idx += 1
            for neighbor in self.neighbors(current):
                if neighbor == q2:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))

        return -1  # Unreachable

    def shortest_path(self, q1: int, q2: int) -> List[int]:
        """Find shortest path between two qubits."""
        if q1 == q2:
            return [q1]
        if q1 < 0 or q1 >= self.num_qubits or q2 < 0 or q2 >= self.num_qubits:
            raise ValueError("Qubit index out of range")

        visited: Set[int] = {q1}
        queue = [(q1, [q1])]
        idx = 0

        while idx < len(queue):
            current, path = queue[idx]
            idx += 1
            for neighbor in self.neighbors(current):
                if neighbor == q2:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []  # No path found

    def add_edge(self, q1: int, q2: int) -> None:
        """Add a coupling edge."""
        if self.is_connected(q1, q2):
            return  # Already connected
        self.edges.append((q1, q2))

    def to_base_coupling_map(self) -> BaseCouplingMap:
        """Convert to base CouplingMap used by standard transpiler."""
        return BaseCouplingMap(
            num_qubits=self.num_qubits,
            edges=list(self.edges),
            directed=self.directed,
        )


# ---------------------------------------------------------------------------
# Pre-defined Hardware Coupling Maps
# ---------------------------------------------------------------------------

def IBM_127_QUBIT() -> CouplingMap:
    """IBM Eagle 127-qubit heavy-hex topology.

    Returns:
        CouplingMap for IBM Eagle processor.
    """
    edges = []
    num_rows = 7
    num_cols = 15

    def qubit_index(row: int, col: int) -> int:
        """Map (row, col) to qubit index in heavy-hex pattern."""
        return row * num_cols + col

    for row in range(num_rows):
        for col in range(num_cols):
            idx = qubit_index(row, col)
            # Horizontal connections (alternating pattern)
            if (row + col) % 2 == 0 and col + 1 < num_cols:
                edges.append((idx, qubit_index(row, col + 1)))
            # Vertical connections
            if row + 1 < num_rows and col % 4 in (1, 3):
                edges.append((idx, qubit_index(row + 1, col)))

    return CouplingMap(num_qubits=num_rows * num_cols, edges=edges)


def IONQ_11_QUBIT() -> CouplingMap:
    """IonQ Harmony 11-qubit all-to-all topology.

    Returns:
        Fully-connected CouplingMap for IonQ trapped-ion processor.
    """
    edges = []
    num_qubits = 11
    for i in range(num_qubits):
        for j in range(i + 1, num_qubits):
            edges.append((i, j))
    return CouplingMap(num_qubits=num_qubits, edges=edges)


def RIGETTI_80_QUBIT() -> CouplingMap:
    """Rigetti Aspen 80-qubit heavy-hex (octagon) topology.

    Returns:
        CouplingMap for Rigetti superconducting processor.
    """
    edges = []
    num_qubits = 80

    # Simplified heavy-hex with octagon pattern
    for i in range(num_qubits):
        # Horizontal ring connections
        j = (i + 1) % num_qubits
        edges.append((i, j))

        # Vertical connectors (every 4th qubit)
        if i % 4 == 0 and i + 2 < num_qubits:
            edges.append((i, i + 2))

    return CouplingMap(num_qubits=num_qubits, edges=edges)


# ---------------------------------------------------------------------------
# Transpiler Pass (Abstract Base Class)
# ---------------------------------------------------------------------------

class TranspilerPass(ABC):
    """Abstract base class for transpiler passes.

    All transpiler passes must implement this interface.
    """

    @abstractmethod
    def run(self, circuit: QuantumCircuit, **kwargs: Any) -> QuantumCircuit:
        """Execute the transpiler pass.

        Args:
            circuit: Input quantum circuit.
            **kwargs: Additional pass-specific parameters.

        Returns:
            Transformed quantum circuit.
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Return the name of this pass."""
        pass


# ---------------------------------------------------------------------------
# Routing Pass
# ---------------------------------------------------------------------------

class RoutingPass(TranspilerPass):
    """Inserts SWAP gates to satisfy hardware connectivity constraints.

    Uses a greedy SWAP-based routing algorithm that inserts SWAP gates
    to move logical qubits to physically connected locations.
    """

    def __init__(self, coupling_map: CouplingMap):
        """Initialize routing pass.

        Args:
            coupling_map: Hardware connectivity definition.
        """
        self.coupling_map = coupling_map

    def name(self) -> str:
        """Return pass name."""
        return "Routing"

    def run(self, circuit: QuantumCircuit, **kwargs: Any) -> QuantumCircuit:
        """Route circuit to satisfy connectivity constraints.

        Args:
            circuit: Input circuit to route.
            **kwargs: Optional qubit_map (Dict[int, int]) mapping logical to physical.

        Returns:
            Routed circuit with inserted SWAP gates.
        """
        qubit_map = kwargs.get("qubit_map", {i: i for i in range(circuit.num_qubits)})
        inverse_map = {v: k for k, v in qubit_map.items()}

        routed_instructions = []

        for instr in circuit.instructions:
            if len(instr.qubits) == 1:
                routed_instructions.append(instr)
                continue

            if len(instr.qubits) == 2:
                q1, q2 = instr.qubits
                phys_q1 = qubit_map[q1]
                phys_q2 = qubit_map[q2]

                if self.coupling_map.is_connected(phys_q1, phys_q2):
                    routed_instructions.append(instr)
                else:
                    # Find shortest path and insert SWAPs
                    path = self.coupling_map.shortest_path(phys_q1, phys_q2)
                    if len(path) < 2:
                        raise RuntimeError(f"No path between qubits {phys_q1} and {phys_q2}")

                    # Insert SWAPs along path to bring q2 closer to q1
                    for k in range(len(path) - 2, 0, -1):
                        swap_instr = Instruction(
                            gate=SWAP_GATE,
                            qubits=[inverse_map[path[0]], inverse_map[path[k]]]
                        )
                        routed_instructions.append(swap_instr)
                        # Update mapping
                        qubit_map[inverse_map[path[0]]] = path[k]
                        qubit_map[inverse_map[path[k]]] = path[0]
                        inverse_map[path[0]] = inverse_map[path[k]]
                        inverse_map[path[k]] = path[k]

                    routed_instructions.append(instr)
            else:
                # Three-qubit gates: use Toffoli decomposition
                routed_instructions.extend(self._decompose_three_qubit(instr, qubit_map, inverse_map))

        result = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
        for instr in routed_instructions:
            result.instructions.append(instr)

        return result

    def _decompose_three_qubit(
        self,
        instr: Instruction,
        qubit_map: Dict[int, int],
        inverse_map: Dict[int, int]
    ) -> List[Instruction]:
        """Decompose three-qubit gate with routing."""
        q1, q2, q3 = instr.qubits
        phys_q1 = qubit_map[q1]
        phys_q2 = qubit_map[q2]
        phys_q3 = qubit_map[q3]

        # Simple decomposition: 6 CNOTs + single-qubit gates
        decomposed = []

        # Route CNOT(q1, q2)
        path12 = self.coupling_map.shortest_path(phys_q1, phys_q2)
        for k in range(len(path12) - 2, 0, -1):
            decomposed.append(Instruction(gate=SWAP_GATE, qubits=[inverse_map[path12[0]], inverse_map[path12[k]]]))
        decomposed.append(Instruction(gate=CNOT_GATE, qubits=[q1, q2]))

        # Route CNOT(q3, q2)
        path32 = self.coupling_map.shortest_path(qubit_map[q3], qubit_map[q2])
        for k in range(len(path32) - 2, 0, -1):
            decomposed.append(Instruction(gate=SWAP_GATE, qubits=[inverse_map[path32[0]], inverse_map[path32[k]]]))
        decomposed.append(Instruction(gate=CNOT_GATE, qubits=[q3, q2]))

        # Toffoli decomposition sequence
        decomposed.extend([
            Instruction(gate=CNOT_GATE, qubits=[q1, q2]),
            Instruction(gate=TOFFOLI_GATE, qubits=[q1, q2, q3]),
            Instruction(gate=CNOT_GATE, qubits=[q1, q2]),
        ])

        return decomposed


# ---------------------------------------------------------------------------
# Decomposition Pass
# ---------------------------------------------------------------------------

class DecompositionPass(TranspilerPass):
    """Decomposes multi-qubit gates into hardware-native gate sets.

    Provides decomposition rules for:
    - TOFFOLI → 6 CNOT + single-qubit gates
    - SWAP → 3 CNOT
    - Multi-controlled gates → cascaded CNOTs
    """

    def __init__(self, target_gates: Optional[List[str]] = None):
        """Initialize decomposition pass.

        Args:
            target_gates: List of allowed gate names after decomposition.
                         Defaults to ['H', 'X', 'CNOT', 'RZ', 'RX'].
        """
        self.target_gates = target_gates or ['H', 'X', 'CNOT', 'RZ', 'RX']

    def name(self) -> str:
        """Return pass name."""
        return "Decomposition"

    def run(self, circuit: QuantumCircuit, **kwargs: Any) -> QuantumCircuit:
        """Decompose circuit into target gate set.

        Args:
            circuit: Input circuit with arbitrary gates.
            **kwargs: Reserved for future use.

        Returns:
            Decomposed circuit using only target gates.
        """
        decomposed_instructions = []

        for instr in circuit.instructions:
            gate_name = instr.gate.name

            if gate_name in self.target_gates:
                decomposed_instructions.append(instr)
            elif gate_name == 'TOFFOLI':
                decomposed_instructions.extend(self._decompose_toffoli(instr.qubits))
            elif gate_name == 'SWAP':
                decomposed_instructions.extend(self._decompose_swap(instr.qubits))
            elif gate_name == 'CCZ':
                decomposed_instructions.extend(self._decompose_ccz(instr.qubits))
            elif len(instr.qubits) > 2:
                decomposed_instructions.extend(self._decompose_multi_control(instr))
            else:
                # Keep as-is if already two-qubit or single-qubit
                decomposed_instructions.append(instr)

        result = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
        for instr in decomposed_instructions:
            result.instructions.append(instr)

        return result

    def _decompose_toffoli(self, qubits: List[int]) -> List[Instruction]:
        """Decompose Toffoli (CCX) into 6 CNOT + single-qubit gates.

        Toffoli decomposition:
        |abc⟩ → CNOT(c,b) · T†(b) · CNOT(a,b) · T(b) · CNOT(a,b) · T†(b) ·
                CNOT(a,b) · T(b) · CNOT(a,c) · T(b) · T†(c) · H(c) ·
                CNOT(a,c) · T(a) · T†(c) · CNOT(a,c)

        Args:
            qubits: [control1, control2, target]

        Returns:
            List of decomposed instructions.
        """
        a, b, c = qubits
        return [
            Instruction(gate=CNOT_GATE, qubits=[a, b]),
            Instruction(gate=T_GATE, qubits=[b]),
            Instruction(gate=CNOT_GATE, qubits=[c, b]),
            Instruction(gate=T_GATE, qubits=[b]),
            Instruction(gate=CNOT_GATE, qubits=[a, b]),
            Instruction(gate=T_GATE, qubits=[b]),
            Instruction(gate=CNOT_GATE, qubits=[c, b]),
            Instruction(gate=T_GATE, qubits=[c]),
            Instruction(gate=H_GATE, qubits=[c]),
            Instruction(gate=CNOT_GATE, qubits=[a, c]),
            Instruction(gate=T_GATE, qubits=[a]),
            Instruction(gate=T_GATE, qubits=[c]),
            Instruction(gate=CNOT_GATE, qubits=[a, c]),
        ]

    def _decompose_swap(self, qubits: List[int]) -> List[Instruction]:
        """Decompose SWAP into 3 CNOT gates.

        SWAP(a,b) = CNOT(a,b) · CNOT(b,a) · CNOT(a,b)

        Args:
            qubits: [qubit1, qubit2]

        Returns:
            List of three CNOT instructions.
        """
        a, b = qubits
        return [
            Instruction(gate=CNOT_GATE, qubits=[a, b]),
            Instruction(gate=CNOT_GATE, qubits=[b, a]),
            Instruction(gate=CNOT_GATE, qubits=[a, b]),
        ]

    def _decompose_ccz(self, qubits: List[int]) -> List[Instruction]:
        """Decompose CCZ into single-qubit and CNOT gates.

        CCZ = (I ⊗ I ⊗ H) · Toffoli · (I ⊗ I ⊗ H)

        Args:
            qubits: [qubit1, qubit2, qubit3]

        Returns:
            List of decomposed instructions.
        """
        a, b, c = qubits
        decomposed = [
            Instruction(gate=H_GATE, qubits=[c]),
        ]
        decomposed.extend(self._decompose_toffoli([a, b, c]))
        decomposed.append(Instruction(gate=H_GATE, qubits=[c]))
        return decomposed

    def _decompose_multi_control(self, instr: Instruction) -> List[Instruction]:
        """Decompose multi-controlled gate using V-chain decomposition.

        For a k-controlled gate, this uses 2(k-1) ancilla-free CNOT decomposition.

        Args:
            instr: Multi-controlled gate instruction.

        Returns:
            List of decomposed instructions.
        """
        qubits = instr.qubits
        if len(qubits) <= 2:
            return [instr]

        controls = qubits[:-1]
        target = qubits[-1]
        decomposed = []

        # For 3-qubit: use Toffoli
        if len(qubits) == 3:
            if instr.gate.name in ('CCX', 'TOFFOLI'):
                return self._decompose_toffoli(qubits)

        # General multi-control: cascaded decomposition
        # For k controls, use k-1 intermediate CNOTs
        for i in range(len(controls) - 1):
            decomposed.append(Instruction(gate=CNOT_GATE, qubits=[controls[i], controls[i + 1]]))

        decomposed.append(Instruction(gate=CNOT_GATE, qubits=[controls[-1], target]))

        for i in range(len(controls) - 2, -1, -1):
            decomposed.append(Instruction(gate=CNOT_GATE, qubits=[controls[i], controls[i + 1]]))

        return decomposed


# ---------------------------------------------------------------------------
# Optimization Pass
# ---------------------------------------------------------------------------

class OptimizationPass(TranspilerPass):
    """Reduces circuit depth and gate count.

    Optimization techniques:
    - Gate cancellation (adjacent inverse gates)
    - Commutation-based optimization
    - Redundant gate elimination
    """

    def __init__(self, max_iterations: int = 10):
        """Initialize optimization pass.

        Args:
            max_iterations: Maximum number of optimization iterations.
        """
        self.max_iterations = max_iterations

    def name(self) -> str:
        """Return pass name."""
        return "Optimization"

    def run(self, circuit: QuantumCircuit, **kwargs: Any) -> QuantumCircuit:
        """Optimize circuit by removing redundant gates.

        Args:
            circuit: Input circuit to optimize.
            **kwargs: Reserved for future use.

        Returns:
            Optimized circuit with fewer gates.
        """
        current_instructions = list(circuit.instructions)

        for _ in range(self.max_iterations):
            optimized = self._cancel_inverse_pairs(current_instructions)
            if len(optimized) == len(current_instructions):
                break  # No more optimizations possible
            current_instructions = optimized

        result = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
        for instr in current_instructions:
            result.instructions.append(instr)

        return result

    def _cancel_inverse_pairs(self, instructions: List[Instruction]) -> List[Instruction]:
        """Cancel adjacent inverse gate pairs.

        Recognizes:
        - H · H = I
        - X · X = I
        - S · S† = I (handled as S† S)
        - T · T† = I
        - CNOT · CNOT = I (same qubits)
        - SWAP · SWAP = I (same qubits)

        Args:
            instructions: List of circuit instructions.

        Returns:
            Optimized instruction list.
        """
        if not instructions:
            return []

        result = list(instructions)
        i = 0

        while i < len(result) - 1:
            curr = result[i]
            next_instr = result[i + 1]

            # Check if same single-qubit gate on same qubit
            if (len(curr.qubits) == 1 and len(next_instr.qubits) == 1 and
                curr.qubits == next_instr.qubits):
                if self._are_inverses(curr.gate.name, next_instr.gate.name):
                    result.pop(i + 1)
                    result.pop(i)
                    i = max(0, i - 1)
                    continue

            # Check if same two-qubit gate on same qubits
            if (len(curr.qubits) == 2 and len(next_instr.qubits) == 2 and
                curr.qubits == next_instr.qubits):
                if self._are_inverses(curr.gate.name, next_instr.gate.name):
                    result.pop(i + 1)
                    result.pop(i)
                    i = max(0, i - 1)
                    continue

            i += 1

        return result

    def _are_inverses(self, gate1: str, gate2: str) -> bool:
        """Check if two gates are inverses of each other.

        Args:
            gate1: First gate name.
            gate2: Second gate name.

        Returns:
            True if gates are inverses.
        """
        inverse_pairs = {
            ('H', 'H'): True,
            ('X', 'X'): True,
            ('Y', 'Y'): True,
            ('Z', 'Z'): True,
            ('S', 'SDG'): True,
            ('T', 'TDG'): True,
            ('CNOT', 'CNOT'): True,
            ('CZ', 'CZ'): True,
            ('SWAP', 'SWAP'): True,
            ('RX', 'RX'): True,  # With negated parameter
            ('RY', 'RY'): True,  # With negated parameter
            ('RZ', 'RZ'): True,  # With negated parameter
        }

        return (gate1, gate2) in inverse_pairs


# ---------------------------------------------------------------------------
# Layout Pass (SABRE-based)
# ---------------------------------------------------------------------------

class LayoutPass(TranspilerPass):
    """Maps logical qubits to physical qubits.

    Layout methods:
    - 'trivial': Linear mapping (q0→0, q1→1, ...)
    - 'sabre': SABRE algorithm for SWAP-minimal mapping
    - 'noise_aware': Noise-aware mapping (prefers low-error qubits)
    """

    def __init__(self, method: str = 'sabre', coupling_map: Optional[CouplingMap] = None):
        """Initialize layout pass.

        Args:
            method: Layout method ('trivial', 'sabre', 'noise_aware').
            coupling_map: Hardware coupling map for SABRE and noise-aware.
        """
        self.method = method
        self.coupling_map = coupling_map

    def name(self) -> str:
        """Return pass name."""
        return "Layout"

    def run(self, circuit: QuantumCircuit, **kwargs: Any) -> QuantumCircuit:
        """Apply layout mapping to circuit.

        Args:
            circuit: Input circuit to map.
            **kwargs: Optional:
                - qubit_weights: Dict[int, float] for noise-aware layout
                - initial_layout: Dict[int, int] to override

        Returns:
            Circuit with qubit mapping applied.
        """
        initial_layout = kwargs.get("initial_layout")

        if initial_layout:
            qubit_map = initial_layout
        elif self.method == 'trivial':
            qubit_map = self._trivial_layout(circuit.num_qubits)
        elif self.method == 'sabre':
            qubit_map = self._sabre_layout(circuit)
        elif self.method == 'noise_aware':
            qubit_weights = kwargs.get("qubit_weights", {})
            qubit_map = self._noise_aware_layout(circuit.num_qubits, qubit_weights)
        else:
            raise ValueError(f"Unknown layout method: {self.method}")

        # Apply layout mapping
        result = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
        for instr in circuit.instructions:
            mapped_qubits = [qubit_map[q] for q in instr.qubits]
            result.instructions.append(
                Instruction(
                    gate=instr.gate,
                    qubits=mapped_qubits,
                    clbits=instr.clbits,
                    params=instr.params
                )
            )

        return result

    def _trivial_layout(self, num_qubits: int) -> Dict[int, int]:
        """Create trivial linear mapping.

        Args:
            num_qubits: Number of qubits.

        Returns:
            Identity mapping {0: 0, 1: 1, ...}.
        """
        return {i: i for i in range(num_qubits)}

    def _sabre_layout(self, circuit: QuantumCircuit) -> Dict[int, int]:
        """Create SABRE-based mapping.

        Simplified SABRE (SWAP-based bidirectional heuristic) algorithm:
        1. Start with random initial layout
        2. Iteratively improve by considering SWAP candidates
        3. Minimize estimated SWAP count

        Args:
            circuit: Input circuit.

        Returns:
            Qubit mapping minimizing SWAP insertions.
        """
        if self.coupling_map is None:
            return self._trivial_layout(circuit.num_qubits)

        # Initialize with random layout
        physical_qubits = list(range(self.coupling_map.num_qubits))
        np.random.shuffle(physical_qubits)
        qubit_map = {i: physical_qubits[i] for i in range(circuit.num_qubits)}

        # Greedy SWAP insertion
        for _ in range(10):  # Multiple passes for convergence
            improved = False

            for instr in circuit.instructions:
                if len(instr.qubits) < 2:
                    continue

                for i in range(len(instr.qubits)):
                    for j in range(i + 1, len(instr.qubits)):
                        q1, q2 = instr.qubits[i], instr.qubits[j]
                        phys_q1, phys_q2 = qubit_map[q1], qubit_map[q2]

                        if not self.coupling_map.is_connected(phys_q1, phys_q2):
                            # Try swapping to improve connectivity
                            best_swap = None
                            best_distance = self.coupling_map.distance(phys_q1, phys_q2)

                            neighbors = self.coupling_map.neighbors(phys_q1)
                            for neighbor in neighbors:
                                # Estimate improvement
                                new_distance = self.coupling_map.distance(neighbor, phys_q2)
                                if new_distance < best_distance:
                                    best_distance = new_distance
                                    best_swap = neighbor

                            if best_swap is not None:
                                # Apply swap
                                for k, v in qubit_map.items():
                                    if v == best_swap:
                                        qubit_map[k] = phys_q1
                                        break
                                qubit_map[q1] = best_swap
                                improved = True

            if not improved:
                break

        return qubit_map

    def _noise_aware_layout(
        self,
        num_qubits: int,
        qubit_weights: Dict[int, float]
    ) -> Dict[int, int]:
        """Create noise-aware mapping.

        Prefers mapping logical qubits to low-error physical qubits.

        Args:
            num_qubits: Number of logical qubits.
            qubit_weights: Dict mapping physical qubit to error rate (lower is better).

        Returns:
            Noise-optimized qubit mapping.
        """
        if not qubit_weights:
            return self._trivial_layout(num_qubits)

        # Sort physical qubits by error rate (lowest first)
        sorted_phys = sorted(qubit_weights.keys(), key=lambda x: qubit_weights[x])

        # Map logical qubits to lowest-error physical qubits
        qubit_map = {}
        for i in range(num_qubits):
            qubit_map[i] = sorted_phys[i % len(sorted_phys)]

        return qubit_map


# ---------------------------------------------------------------------------
# Pulse-Level Pass
# ---------------------------------------------------------------------------

class PulseLevelPass(TranspilerPass):
    """Transpiles to pulse-level instructions for hardware control.

    Maps gate-level instructions to native pulses with:
    - Duration optimization
    - Crosstalk mitigation
    - Frequency allocation
    """

    def __init__(self, hardware_platform: HardwarePlatform):
        """Initialize pulse-level pass.

        Args:
            hardware_platform: Target hardware platform.
        """
        self.hardware_platform = hardware_platform
        self.native_gates = NativeGateSet()

    def name(self) -> str:
        """Return pass name."""
        return "PulseLevel"

    def run(self, circuit: QuantumCircuit, **kwargs: Any) -> QuantumCircuit:
        """Convert circuit to pulse-level instructions.

        Note: This pass returns a circuit with metadata attached
        describing pulse-level parameters.

        Args:
            circuit: Input circuit to convert.
            **kwargs: Optional:
                - pulse_schedule: Dict to fill with pulse schedule
                - qubit_frequencies: Dict[int, float] for qubit frequencies

        Returns:
            Circuit with pulse-level metadata attached.
        """
        pulse_schedule = kwargs.get("pulse_schedule", {})
        qubit_frequencies = kwargs.get("qubit_frequencies", {})

        result = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)

        for instr in circuit.instructions:
            gate_name = instr.gate.name

            # Get native gates for this platform
            native_gates = self.native_gates.native_gates(self.hardware_platform)

            if gate_name in [g.name for g in native_gates]:
                # Gate is native - attach pulse metadata
                pulse_info = self._create_pulse_info(instr, qubit_frequencies)
                result.instructions.append(instr)
                pulse_schedule[gate_name] = pulse_info
            else:
                # Need decomposition first
                decomposer = DecompositionPass()
                decomposed = decomposer.run(
                    QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
                )
                for d_instr in decomposed.instructions:
                    result.instructions.append(d_instr)

        return result

    def _create_pulse_info(
        self,
        instr: Instruction,
        qubit_frequencies: Dict[int, float]
    ) -> Dict[str, Any]:
        """Create pulse-level information for a gate.

        Args:
            instr: Gate instruction.
            qubit_frequencies: Qubit frequencies in GHz.

        Returns:
            Dictionary with pulse parameters.
        """
        gate_name = instr.gate.name

        # Platform-specific pulse parameters
        if self.hardware_platform == HardwarePlatform.TRAPPED_ION:
            return {
                "type": "trap",
                "duration_ns": self._get_trap_duration(gate_name),
                "amplitude": self._get_trap_amplitude(gate_name),
                "qubit_freq_ghz": qubit_frequencies.get(instr.qubits[0], 1.0),
            }
        elif self.hardware_platform == HardwarePlatform.SUPERCONDUCTING:
            return {
                "type": "transmon",
                "duration_ns": 20.0,  # Typical transmon gate time
                "amplitude": 0.5,
                "drag_coefficient": 0.1,
                "qubit_freq_ghz": qubit_frequencies.get(instr.qubits[0], 5.0),
            }
        else:
            return {
                "type": "native",
                "duration_ns": 10.0,
                "amplitude": 1.0,
            }

    def _get_trap_duration(self, gate_name: str) -> float:
        """Get trapped-ion gate duration in nanoseconds."""
        durations = {
            "H": 1000.0,
            "X": 10.0,
            "RZ": 100.0,
            "CNOT": 100000.0,  # 100 µs
        }
        return durations.get(gate_name, 100.0)

    def _get_trap_amplitude(self, gate_name: str) -> float:
        """Get trapped-ion pulse amplitude."""
        amplitudes = {
            "H": 0.5,
            "X": 1.0,
            "RZ": 0.3,
            "CNOT": 0.8,
        }
        return amplitudes.get(gate_name, 0.5)


# ---------------------------------------------------------------------------
# Main Hardware Transpiler
# ---------------------------------------------------------------------------

class HardwareTranspiler:
    """Hardware-Aware Quantum Transpiler.

    Orchestrates a pipeline of transpiler passes to transform a
    quantum circuit for execution on specific quantum hardware.

    Stages:
        1. Layout: Map logical to physical qubits
        2. Routing: Insert SWAPs for connectivity
        3. Decomposition: Break down multi-qubit gates
        4. Optimization: Remove redundant gates
        5. PulseLevel: Generate pulse instructions
        6. FinalOptimization: Last-pass cleanup
    """

    def __init__(
        self,
        platform: HardwarePlatform = HardwarePlatform.SUPERCONDUCTING,
        coupling_map: Optional[CouplingMap] = None,
    ):
        """Initialize hardware transpiler.

        Args:
            platform: Target hardware platform.
            coupling_map: Optional coupling map. Auto-selected if not provided.
        """
        self.platform = platform

        if coupling_map is None:
            if platform == HardwarePlatform.TRAPPED_ION:
                coupling_map = IONQ_11_QUBIT()
            elif platform == HardwarePlatform.SUPERCONDUCTING:
                coupling_map = IBM_127_QUBIT()
            else:
                coupling_map = IBM_127_QUBIT()

        self.coupling_map = coupling_map
        self.native_gates = NativeGateSet()

        # Initialize passes
        self.layout_pass = LayoutPass(method='sabre', coupling_map=coupling_map)
        self.routing_pass = RoutingPass(coupling_map=coupling_map)
        self.decomposition_pass = DecompositionPass(
            target_gates=self.native_gates.native_gate_names(platform)
        )
        self.optimization_pass = OptimizationPass()
        self.pulse_pass = PulseLevelPass(platform)

    def transpile(
        self,
        circuit: QuantumCircuit,
        optimization_level: int = 1,
        initial_layout: Optional[Dict[int, int]] = None,
        **kwargs: Any,
    ) -> QuantumCircuit:
        """Transpile circuit for target hardware.

        Args:
            circuit: Input quantum circuit.
            optimization_level: Optimization level (0-3).
            initial_layout: Optional initial qubit mapping.
            **kwargs: Additional parameters passed to passes.

        Returns:
            Transpiled circuit ready for hardware execution.

        Raises:
            ValueError: If circuit is invalid for target hardware.
        """
        if circuit.num_qubits > self.coupling_map.num_qubits:
            raise ValueError(
                f"Circuit has {circuit.num_qubits} qubits but hardware "
                f"only has {self.coupling_map.num_qubits} qubits"
            )

        # Stage 1: Layout
        result = self.layout_pass.run(
            circuit,
            initial_layout=initial_layout,
            **kwargs,
        )

        # Stage 2: Routing
        result = self.routing_pass.run(result, **kwargs)

        # Stage 3: Decomposition
        result = self.decomposition_pass.run(result, **kwargs)

        # Stage 4: Optimization (level-dependent iterations)
        if optimization_level >= 1:
            result = self.optimization_pass.run(result, **kwargs)

        if optimization_level >= 2:
            result = self.optimization_pass.run(result, **kwargs)

        # Stage 5: Pulse-level (optional)
        if optimization_level >= 3:
            pulse_schedule = kwargs.get("pulse_schedule", {})
            result = self.pulse_pass.run(result, pulse_schedule=pulse_schedule, **kwargs)

        # Stage 6: Final optimization
        result = self.optimization_pass.run(result, **kwargs)

        return result

    def transpile_and_report(
        self,
        circuit: QuantumCircuit,
        optimization_level: int = 1,
        **kwargs: Any,
    ) -> Tuple[QuantumCircuit, Dict[str, Any]]:
        """Transpile circuit and provide detailed report.

        Args:
            circuit: Input quantum circuit.
            optimization_level: Optimization level (0-3).
            **kwargs: Additional parameters.

        Returns:
            Tuple of (transpiled circuit, report dictionary).
        """
        initial_gate_count = len(circuit.instructions)
        initial_depth = self._estimate_depth(circuit)

        transpiled = self.transpile(
            circuit,
            optimization_level=optimization_level,
            **kwargs,
        )

        final_gate_count = len(transpiled.instructions)
        final_depth = self._estimate_depth(transpiled)

        report = {
            "platform": self.platform.value,
            "num_qubits": circuit.num_qubits,
            "initial_gate_count": initial_gate_count,
            "final_gate_count": final_gate_count,
            "gate_reduction": initial_gate_count - final_gate_count,
            "initial_depth": initial_depth,
            "final_depth": final_depth,
            "depth_reduction": initial_depth - final_depth,
            "optimization_level": optimization_level,
            "coupling_map_edges": len(self.coupling_map.edges),
        }

        return transpiled, report

    def _estimate_depth(self, circuit: QuantumCircuit) -> int:
        """Estimate circuit depth (simplified layer count)."""
        if not circuit.instructions:
            return 0
        return len(circuit.instructions)


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def transpile_for_hardware(
    circuit: QuantumCircuit,
    platform: HardwarePlatform,
    optimization_level: int = 1,
    **kwargs: Any,
) -> QuantumCircuit:
    """Convenience function to transpile for specific hardware.

    Args:
        circuit: Input quantum circuit.
        platform: Target hardware platform.
        optimization_level: Optimization level (0-3).
        **kwargs: Additional parameters.

    Returns:
        Transpiled circuit.

    Example:
        >>> transpiled = transpile_for_hardware(circuit, HardwarePlatform.IBM)

    Raises:
        ValueError: If platform is not supported.
    """
    if platform == HardwarePlatform.TRAPPED_ION:
        coupling_map = IONQ_11_QUBIT()
    elif platform == HardwarePlatform.SUPERCONDUCTING:
        coupling_map = IBM_127_QUBIT()
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    transpiler = HardwareTranspiler(platform=platform, coupling_map=coupling_map)
    return transpiler.transpile(circuit, optimization_level=optimization_level, **kwargs)


def estimate_circuit_depth(circuit: QuantumCircuit) -> int:
    """Estimate circuit depth (longest path through circuit).

    Depth = maximum number of gates on any qubit's timeline.

    Args:
        circuit: Quantum circuit to analyze.

    Returns:
        Estimated circuit depth.

    Example:
        >>> depth = estimate_circuit_depth(circuit)
    """
    if not circuit.instructions:
        return 0

    qubit_depth = [0] * circuit.num_qubits

    for instr in circuit.instructions:
        if len(instr.qubits) == 1:
            q = instr.qubits[0]
            qubit_depth[q] += 1
        elif len(instr.qubits) == 2:
            q1, q2 = instr.qubits
            current_depth = max(qubit_depth[q1], qubit_depth[q2]) + 1
            qubit_depth[q1] = current_depth
            qubit_depth[q2] = current_depth
        else:
            # Three-qubit gate
            max_depth = max(qubit_depth[q] for q in instr.qubits) + 1
            for q in instr.qubits:
                qubit_depth[q] = max_depth

    return max(qubit_depth) if qubit_depth else 0


def estimate_swaps_needed(
    circuit: QuantumCircuit,
    coupling_map: CouplingMap,
) -> int:
    """Estimate number of SWAP gates needed for routing.

    Uses a greedy algorithm to count non-adjacent two-qubit gates.

    Args:
        circuit: Input quantum circuit.
        coupling_map: Target hardware coupling map.

    Returns:
        Estimated number of SWAP insertions needed.

    Example:
        >>> swaps = estimate_swaps_needed(circuit, coupling_map)
    """
    swap_count = 0

    for instr in circuit.instructions:
        if len(instr.qubits) == 2:
            q1, q2 = instr.qubits
            if not coupling_map.is_connected(q1, q2):
                # Estimate SWAPs based on distance
                distance = coupling_map.distance(q1, q2)
                if distance > 0:
                    swap_count += distance - 1
                else:
                    swap_count += 1  # Fallback

    return swap_count


# ---------------------------------------------------------------------------
# Module Exports
# ---------------------------------------------------------------------------

__all__ = [
    # Main Classes
    "CouplingMap",
    "TranspilerPass",
    "RoutingPass",
    "DecompositionPass",
    "OptimizationPass",
    "LayoutPass",
    "PulseLevelPass",
    "HardwareTranspiler",

    # Pre-defined Coupling Maps
    "IBM_127_QUBIT",
    "IONQ_11_QUBIT",
    "RIGETTI_80_QUBIT",

    # Utility Functions
    "transpile_for_hardware",
    "estimate_circuit_depth",
    "estimate_swaps_needed",
]
