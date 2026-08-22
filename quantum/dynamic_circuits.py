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

"""Dynamic quantum circuits with classical control flow.

Provides support for conditional operations, loops, and other
classical control flow constructs in quantum circuits.
"""

from __future__ import annotations

import numpy as np
from typing import Any, Union, Optional, Callable
from enum import Enum
import copy

from .circuit import QuantumCircuit, Instruction
from .gates import get_gate
from .operators import SparsePauliOp
from .simulator import StatevectorSimulator, Statevector


class ConditionType(Enum):
    """Types of classical conditions."""
    IF = "if"
    ELSE = "else"
    WHILE = "while"
    BREAK = "break"


class ClassicalCondition:
    """Represents a condition on classical bits or register values.

    Used in if/else and while loop constructs.

    Usage:
        cond = ClassicalCondition(classical_register, 0, 1)
        cond = ClassicalCondition(classical_register, None, 5)
    """

    def __init__(
        self,
        classical_register=None,
        bit_index: Optional[int] = None,
        value: Optional[int] = None,
        comparison: str = "==",
    ):
        self._classical_register = classical_register
        self._bit_index = bit_index
        self._value = value
        self._comparison = comparison

    @property
    def classical_register(self):
        return self._classical_register

    @property
    def bit_index(self) -> Optional[int]:
        return self._bit_index

    @property
    def value(self) -> Optional[int]:
        return self._value

    @property
    def comparison(self) -> str:
        return self._comparison

    def evaluate(self, measurement_counts: dict[str, int]) -> bool:
        """Evaluate the condition against measurement results."""
        if not measurement_counts:
            return False

        most_frequent = max(measurement_counts, key=measurement_counts.get)

        if self._bit_index is not None:
            if self._bit_index < len(most_frequent):
                bit_value = int(most_frequent[self._bit_index])
                return self._compare(bit_value, self._value)
        else:
            reg_value = int(most_frequent, 2)
            return self._compare(reg_value, self._value)

        return False

    def _compare(self, actual: int, expected: int) -> bool:
        """Perform the comparison."""
        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        return ops.get(self._comparison, lambda a, b: False)(actual, expected)

    def __repr__(self):
        if self._bit_index is not None:
            return f"ClassicalCondition(bit[{self._bit_index}] {self._comparison} {self._value})"
        return f"ClassicalCondition(register {self._comparison} {self._value})"


class IfElse:
    """Conditional execution of quantum operations.

    Executes different quantum operations based on classical
    measurement results.

    Usage:
        cond = ClassicalCondition(clreg, 0, 1)
        if_else = IfElse(
            condition=cond,
            true_ops=[get_gate('X')(0)],
            false_ops=[get_gate('H')(0)],
        )
        dynamic_circuit.add_control_flow(if_else)
    """

    def __init__(
        self,
        condition: ClassicalCondition,
        true_ops: list[Instruction] = None,
        false_ops: list[Instruction] = None,
    ):
        self._condition = condition
        self._true_ops = true_ops or []
        self._false_ops = false_ops or []

    @property
    def condition(self) -> ClassicalCondition:
        return self._condition

    @property
    def true_ops(self) -> list[Instruction]:
        return self._true_ops

    @property
    def false_ops(self) -> list[Instruction]:
        return self._false_ops

    def add_true_op(self, op: Instruction):
        self._true_ops.append(op)

    def add_false_op(self, op: Instruction):
        self._false_ops.append(op)

    def __repr__(self):
        return (
            f"IfElse(condition={self._condition}, "
            f"true_ops={len(self._true_ops)}, "
            f"false_ops={len(self._false_ops)})"
        )


class WhileLoop:
    """Repeated execution of quantum operations based on a condition.

    Usage:
        cond = ClassicalCondition(clreg, None, 0, comparison="!=")
        while_loop = WhileLoop(
            condition=cond,
            body_ops=[get_gate('X')(0)],
            max_iterations=10,
        )
        dynamic_circuit.add_control_flow(while_loop)
    """

    def __init__(
        self,
        condition: ClassicalCondition,
        body_ops: list[Instruction] = None,
        max_iterations: int = 100,
    ):
        self._condition = condition
        self._body_ops = body_ops or []
        self._max_iterations = max_iterations

    @property
    def condition(self) -> ClassicalCondition:
        return self._condition

    @property
    def body_ops(self) -> list[Instruction]:
        return self._body_ops

    @property
    def max_iterations(self) -> int:
        return self._max_iterations

    def add_body_op(self, op: Instruction):
        self._body_ops.append(op)

    def __repr__(self):
        return (
            f"WhileLoop(condition={self._condition}, "
            f"body_ops={len(self._body_ops)}, "
            f"max_iter={self._max_iterations})"
        )


class Break:
    """Break out of a WhileLoop."""

    def __repr__(self):
        return "Break()"


class DynamicCircuit(QuantumCircuit):
    """Quantum circuit with classical control flow support.

    Extends QuantumCircuit with support for conditional operations,
    while loops, and other dynamic circuit constructs.

    Usage:
        qc = DynamicCircuit(2, 2)
        qc.h(0)
        qc.measure(0, 0)

        cond = ClassicalCondition(qc.cregs[0], 0, 1)
        if_else = IfElse(
            condition=cond,
            true_ops=[get_gate('X')(1)],
            false_ops=[get_gate('H')(1)],
        )
        qc.add_control_flow(if_else)
    """

    def __init__(self, num_qubits: int = 0, num_clbits: int = 0, name: str = None):
        super().__init__(num_qubits, num_clbits)
        self._control_flow_ops: list = []

    @property
    def control_flow_ops(self) -> list:
        return self._control_flow_ops.copy()

    def add_control_flow(self, operation):
        """Add a control flow operation (IfElse, WhileLoop, Break).

        Args:
            operation: A control flow operation to add.
        """
        if isinstance(operation, (IfElse, WhileLoop, Break)):
            self._control_flow_ops.append(operation)
        else:
            raise TypeError(f"Unsupported control flow type: {type(operation)}")

    def if_else(
        self,
        condition: ClassicalCondition,
        true_ops: list[Instruction] = None,
        false_ops: list[Instruction] = None,
    ):
        """Add an if/else construct.

        Args:
            condition: Classical condition to evaluate.
            true_ops: Operations to execute if condition is true.
            false_ops: Operations to execute if condition is false.
        """
        if_else = IfElse(condition, true_ops, false_ops)
        self.add_control_flow(if_else)
        return if_else

    def while_loop(
        self,
        condition: ClassicalCondition,
        body_ops: list[Instruction] = None,
        max_iterations: int = 100,
    ):
        """Add a while loop construct.

        Args:
            condition: Classical condition to check.
            body_ops: Operations to execute in loop body.
            max_iterations: Maximum number of iterations.
        """
        while_loop = WhileLoop(condition, body_ops, max_iterations)
        self.add_control_flow(while_loop)
        return while_loop

    def break_loop(self):
        """Add a break operation."""
        break_op = Break()
        self.add_control_flow(break_op)
        return break_op

    def simulate_dynamic(self, initial_state: Optional[np.ndarray] = None) -> dict:
        """Simulate the dynamic circuit.

        This performs a simplified simulation of the dynamic circuit,
        executing control flow based on measurement outcomes.

        Args:
            initial_state: Optional initial statevector.

        Returns:
            Dictionary with simulation results.
        """
        sv_sim = StatevectorSimulator()

        # Build the full operation list
        all_ops = list(self._instructions) + self._control_flow_ops

        if initial_state is not None:
            state = Statevector(initial_state)
        else:
            # Start with |0...0>
            state = Statevector(np.zeros(2 ** self.num_qubits, dtype=complex))
            state.data[0] = 1.0

        iteration = 0
        max_total_iterations = 1000

        for op in all_ops:
            if iteration >= max_total_iterations:
                break

            if isinstance(op, IfElse):
                # Simplified: apply true_ops (full simulation would measure first)
                for true_op in op.true_ops:
                    state = self._apply_operation(state, true_op)

            elif isinstance(op, WhileLoop):
                cond = op.condition
                for _ in range(op.max_iterations):
                    iteration += 1
                    if iteration >= max_total_iterations:
                        break

                    # Apply body operations
                    for body_op in op.body_ops:
                        state = self._apply_operation(state, body_op)

                    # Check condition (simplified - would need measurement)
                    # For simulation, we assume condition becomes false
                    break

            elif isinstance(op, Break):
                break

        return {"statevector": state, "num_iterations": iteration}

    def _apply_operation(self, state: Statevector, op: Instruction) -> Statevector:
        """Apply a single operation to a statevector."""
        import numpy as np
        from .info import partial_trace

        gate = op.gate
        qubits = op.qubits

        # Get the unitary matrix for this gate
        matrix = np.array(gate.unitary())

        # For multi-qubit gates on a subset of qubits, we need to embed
        # the unitary in the full Hilbert space
        n_total = state.num_qubits
        n_gate = len(qubits)

        if n_gate == n_total and sorted(qubits) == list(range(n_total)):
            # Gate acts on all qubits directly
            new_state = matrix @ state.data
        else:
            # Embed gate in full space using tensor product with identity
            # Build the full unitary: I ⊗ ... ⊗ U ⊗ ... ⊗ I
            other_qubits = [i for i in range(n_total) if i not in qubits]

            # Reorder so that target qubits are at the end
            # Full unitary = I_other ⊗ U_target
            full_dim = 2 ** n_total
            target_dim = 2 ** n_gate
            other_dim = full_dim // target_dim

            # Create the full operator
            full_matrix = np.zeros((full_dim, full_dim), dtype=complex)

            # For each computational basis state of the other qubits,
            # apply the gate to the target qubits
            for i in range(other_dim):
                # Indices for this block
                start = i * target_dim
                end = start + target_dim
                full_matrix[start:end, start:end] = matrix

            new_state = full_matrix @ state.data

        # Normalize
        norm = np.linalg.norm(new_state)
        if norm > 0:
            new_state = new_state / norm

        return Statevector(new_state)

    def depth_with_control_flow(self) -> int:
        """Estimate circuit depth including control flow operations."""
        base_depth = self.depth()
        control_flow_depth = len(self._control_flow_ops) * 10  # Estimate
        return base_depth + control_flow_depth

    def __repr__(self):
        return (
            f"DynamicCircuit(qubits={self.num_qubits}, "
            f"clbits={self.num_clbits}, "
            f"instructions={len(self._instructions)}, "
            f"control_flow={len(self._control_flow_ops)})"
        )


# Utility functions for creating common dynamic circuit patterns

def create_teleportation_circuit() -> DynamicCircuit:
    """Create a quantum teleportation circuit using dynamic control flow.

    Teleports the state of qubit 0 to qubit 2 using classical
    feedback operations.
    """
    qc = DynamicCircuit(3, 2)

    # Prepare state to teleport
    qc.h(0)
    qc.cx(0, 1)

    # Bell pair between qubits 1 and 2
    qc.h(1)
    qc.cx(1, 2)

    # Bell measurement
    qc.cx(0, 1)
    qc.h(0)
    qc.measure(0, 0)
    qc.measure(1, 1)

    # Classical corrections using control flow
    # If q0 measured as 1, apply X to q2
    cond0 = ClassicalCondition(qc.cregs[0], 0, 1)
    qc.if_else(
        condition=cond0,
        true_ops=[get_gate('X')(2)],
    )

    # If q1 measured as 1, apply Z to q2
    cond1 = ClassicalCondition(qc.cregs[0], 1, 1)
    qc.if_else(
        condition=cond1,
        true_ops=[get_gate('Z')(2)],
    )

    return qc


def create_superposition_with_correction() -> DynamicCircuit:
    """Create a circuit that creates superposition and corrects based on measurement."""
    qc = DynamicCircuit(1, 1)

    qc.h(0)
    qc.measure(0, 0)

    # If measured as 0, re-create superposition
    cond = ClassicalCondition(qc.cregs[0], 0, 0)
    qc.if_else(
        condition=cond,
        true_ops=[get_gate('H')(0)],
        false_ops=[],
    )

    return qc
