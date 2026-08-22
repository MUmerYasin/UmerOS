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

"""Dynamic quantum circuits v2 — mid-circuit measurement and classical feedforward.

Comprehensive support for dynamic/mid-circuit measurement and classical
feedforward for real quantum hardware (IBM, Quantinuum, IonQ).

This module extends the v1 dynamic circuits with hardware-targeted
compilation, classical register manipulation, conditional gates,
while loops, switch-case constructs, and feedforward execution.

Classes:
    MidCircuitMeasurement — mid-circuit measurement descriptor.
    ClassicalRegister     — enhanced classical register for dynamic circuits.
    ClassicalBit          — single classical bit with optional value.
    DCClassicalCondition  — condition evaluated against classical bits.
    ClassicalOperation    — bitwise logic on classical bits.
    ConditionalGate       — gate applied when a classical condition holds.
    DCWhileLoop           — loop driven by a classical condition.
    SwitchCase            — multi-branch classical control flow.
    DynamicCircuitCompiler — compile dynamic circuits for real backends.
    FeedforwardController — resolve conditional operations from measurements.
    DynamicCircuitExecutor — execute dynamic circuits on real hardware.

Utility functions:
    create_bell_pair_with_condition
    create_bit_flip_detection
    create_teleportation_circuit  (v2 version)
    is_dynamic_capable
    estimate_classical_processing_overhead
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Mid-circuit measurement
# ---------------------------------------------------------------------------

@dataclass
class MidCircuitMeasurement:
    """Descriptor for a mid-circuit measurement on a single qubit.

    Attributes:
        qubit: Logical qubit index to measure.
        classical_bit: Target classical bit index (within a register).
        basis: Measurement basis — ``"Z"`` (computational), ``"X"``,
            or ``"Y"``.
        condition_on: Optional condition that must be true *before*
            this measurement is performed.  Useful for dynamic
            repeat-until-success patterns.
    """

    qubit: int
    classical_bit: int
    basis: str = "Z"
    condition_on: Optional["DCClassicalCondition"] = None

    def __post_init__(self) -> None:
        if self.basis not in ("Z", "X", "Y"):
            raise ValueError(
                f"Invalid measurement basis {self.basis!r}; "
                "expected 'Z', 'X', or 'Y'."
            )
        if self.qubit < 0:
            raise ValueError("qubit index must be non-negative.")
        if self.classical_bit < 0:
            raise ValueError("classical_bit index must be non-negative.")

    # -- serialisation helpers -------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "qubit": self.qubit,
            "classical_bit": self.classical_bit,
            "basis": self.basis,
            "condition_on": self.condition_on.to_dict() if self.condition_on else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MidCircuitMeasurement":
        """Deserialise from a dictionary."""
        cond = None
        if d.get("condition_on") is not None:
            cond = DCClassicalCondition.from_dict(d["condition_on"])
        return cls(
            qubit=d["qubit"],
            classical_bit=d["classical_bit"],
            basis=d.get("basis", "Z"),
            condition_on=cond,
        )

    # -- circuit manipulation --------------------------------------------------

    def apply(self, circuit: Any) -> None:
        """Append this measurement to *circuit*.

        If a ``condition_on`` is set the measurement is only performed
        when the condition evaluates to ``True``.  The concrete API
        depends on the circuit class; this method attempts to call
        ``add_mid_circuit_measure`` and falls back to ``measure``.
        """
        if hasattr(circuit, "add_mid_circuit_measure"):
            circuit.add_mid_circuit_measure(
                qubit=self.qubit,
                clbit=self.classical_bit,
                basis=self.basis,
                condition=self.condition_on,
            )
        else:
            circuit.measure(self.qubit, self.classical_bit)

    def __repr__(self) -> str:
        cond = f", condition_on={self.condition_on!r}" if self.condition_on else ""
        return (
            f"MidCircuitMeasurement(qubit={self.qubit}, "
            f"classical_bit={self.classical_bit}, "
            f"basis={self.basis!r}{cond})"
        )


# ---------------------------------------------------------------------------
# Classical bit
# ---------------------------------------------------------------------------

@dataclass
class ClassicalBit:
    """Single classical bit with an optional stored value.

    Attributes:
        index: Position within the owning register.
        register: Name of the owning :class:`ClassicalRegister`.
        value: ``0``, ``1``, or ``None`` (unmeasured / unknown).
    """

    index: int
    register: str
    value: Optional[int] = None

    def __post_init__(self) -> None:
        if self.value is not None and self.value not in (0, 1):
            raise ValueError(
                f"Classical bit value must be 0, 1, or None; got {self.value!r}."
            )

    def __repr__(self) -> str:
        val = str(self.value) if self.value is not None else "?"
        return f"ClassicalBit({self.register}[{self.index}]={val})"


# ---------------------------------------------------------------------------
# Classical register
# ---------------------------------------------------------------------------

class ClassicalRegister:
    """Enhanced classical register for dynamic circuits.

    Provides bit-level access and integer interpretation utilities.

    Usage::

        cr = ClassicalRegister("c", 4)
        cr.set_bit(0, 1)
        cr.set_bit(3, 1)
        assert cr.to_int() == 9
    """

    def __init__(self, name: str, size: int) -> None:
        if size <= 0:
            raise ValueError("Register size must be positive.")
        self._name = name
        self._size = size
        self._bits: List[ClassicalBit] = [
            ClassicalBit(index=i, register=name) for i in range(size)
        ]

    # -- properties ------------------------------------------------------------

    @property
    def name(self) -> str:
        """Register name."""
        return self._name

    @property
    def size(self) -> int:
        """Number of bits in this register."""
        return self._size

    @property
    def bits(self) -> List[ClassicalBit]:
        """Read-only list of :class:`ClassicalBit` objects."""
        return list(self._bits)

    # -- bit access ------------------------------------------------------------

    def get_bit(self, index: int) -> ClassicalBit:
        """Return the :class:`ClassicalBit` at *index*.

        Raises:
            IndexError: if *index* is out of range.
        """
        if not 0 <= index < self._size:
            raise IndexError(
                f"Bit index {index} out of range for register "
                f"{self._name!r} of size {self._size}."
            )
        return self._bits[index]

    def set_bit(self, index: int, value: int) -> None:
        """Set bit at *index* to *value* (0 or 1).

        Raises:
            IndexError: if *index* is out of range.
            ValueError: if *value* is not 0 or 1.
        """
        if not 0 <= index < self._size:
            raise IndexError(
                f"Bit index {index} out of range for register "
                f"{self._name!r} of size {self._size}."
            )
        if value not in (0, 1):
            raise ValueError(f"Bit value must be 0 or 1; got {value!r}.")
        self._bits[index].value = value

    # -- integer conversion ----------------------------------------------------

    def to_int(self) -> int:
        """Interpret the register contents as an unsigned integer.

        Uses little-endian ordering: bit 0 is the least significant.
        Unknown bits are treated as 0.
        """
        result = 0
        for i, bit in enumerate(self._bits):
            v = bit.value if bit.value is not None else 0
            result |= v << i
        return result

    @classmethod
    def from_int(cls, value: int, size: int, name: str = "c") -> "ClassicalRegister":
        """Create a register from an integer value.

        Args:
            value: Non-negative integer whose binary representation
                populates the register.
            size: Number of bits.
            name: Register name.
        """
        if value < 0:
            raise ValueError("value must be non-negative.")
        if size <= 0:
            raise ValueError("size must be positive.")
        if value.bit_length() > size:
            raise ValueError(
                f"Value {value} requires {value.bit_length()} bits "
                f"but register has only {size}."
            )
        reg = cls(name, size)
        for i in range(size):
            reg.set_bit(i, (value >> i) & 1)
        return reg

    # -- iteration / repr ------------------------------------------------------

    def __iter__(self):
        return iter(self._bits)

    def __len__(self) -> int:
        return self._size

    def __getitem__(self, index: int) -> ClassicalBit:
        return self.get_bit(index)

    def __repr__(self) -> str:
        vals = "".join(
            str(b.value) if b.value is not None else "?" for b in self._bits
        )
        return f"ClassicalRegister({self._name}, size={self._size}, bits={vals})"


# ---------------------------------------------------------------------------
# Classical condition (dataclass variant for dynamic circuits v2)
# ---------------------------------------------------------------------------

@dataclass
class DCClassicalCondition:
    """Condition evaluated against a single classical bit.

    This is the **v2 dataclass** variant — distinct from the v1
    :class:`ClassicalCondition` in ``dynamic_circuits.py`` which
    operates on measurement-count dictionaries.

    Attributes:
        bit_index: Index of the classical bit to test.
        register: Name of the register containing the bit.
        comparison: One of ``"=="``, ``"!="``, ``">"``, ``"<"``,
            ``">="``, ``"<="``.
        value: Integer value to compare against.
    """

    bit_index: int
    register: str
    comparison: str
    value: int

    _VALID_OPS = frozenset(("==", "!=", ">", "<", ">=", "<="))

    def __post_init__(self) -> None:
        if self.comparison not in self._VALID_OPS:
            raise ValueError(
                f"Invalid comparison {self.comparison!r}; "
                f"must be one of {sorted(self._VALID_OPS)}."
            )

    # -- serialisation ---------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "bit_index": self.bit_index,
            "register": self.register,
            "comparison": self.comparison,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DCClassicalCondition":
        """Deserialise from a dictionary."""
        return cls(
            bit_index=d["bit_index"],
            register=d["register"],
            comparison=d.get("comparison", "=="),
            value=d.get("value", 0),
        )

    # -- evaluation ------------------------------------------------------------

    def evaluate(self, bits: ClassicalRegister) -> bool:
        """Evaluate this condition against *bits*.

        Args:
            bits: The :class:`ClassicalRegister` containing the
                target bit.

        Returns:
            ``True`` when the comparison holds.

        Raises:
            IndexError: if ``bit_index`` is out of range.
        """
        bit = bits.get_bit(self.bit_index)
        if bit.value is None:
            raise ValueError(
                f"Cannot evaluate condition: bit {self.bit_index} "
                "in register "
                f"{self.register!r} has not been measured."
            )
        return self._compare(bit.value, self.value)

    def _compare(self, actual: int, expected: int) -> bool:
        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        return ops[self.comparison](actual, expected)

    def __repr__(self) -> str:
        return (
            f"DCClassicalCondition({self.register}[{self.bit_index}] "
            f"{self.comparison} {self.value})"
        )


# ---------------------------------------------------------------------------
# Classical operation
# ---------------------------------------------------------------------------

@dataclass
class ClassicalOperation:
    """Bitwise logic operation on classical bits.

    Attributes:
        operation: One of ``"NOT"``, ``"AND"``, ``"OR"``, ``"XOR"``,
            ``"NAND"``, ``"NOR"``.
        input_bits: List of ``(register_name, bit_index)`` pairs
            that supply operands.
        output_bit: ``(register_name, bit_index)`` pair that receives
            the result.
    """

    operation: str
    input_bits: List[Tuple[str, int]]
    output_bit: Tuple[str, int]

    _VALID_OPS = frozenset(("NOT", "AND", "OR", "XOR", "NAND", "NOR"))

    def __post_init__(self) -> None:
        if self.operation not in self._VALID_OPS:
            raise ValueError(
                f"Invalid operation {self.operation!r}; "
                f"must be one of {sorted(self._VALID_OPS)}."
            )
        if self.operation == "NOT" and len(self.input_bits) != 1:
            raise ValueError("NOT requires exactly one input bit.")
        if self.operation in ("NAND", "NOR") and len(self.input_bits) < 2:
            raise ValueError(f"{self.operation} requires at least two input bits.")

    def evaluate(self, bit_values: Dict[Tuple[str, int], int]) -> int:
        """Compute the result given a mapping of ``(register, index) -> value``.

        Args:
            bit_values: Current values of all relevant classical bits.

        Returns:
            0 or 1.

        Raises:
            KeyError: if any required input bit is missing from
                *bit_values*.
            ValueError: if a bit value is not 0 or 1.
        """
        values: List[int] = []
        for reg, idx in self.input_bits:
            if (reg, idx) not in bit_values:
                raise KeyError(
                    f"Missing value for bit ({reg!r}, {idx}) in bit_values."
                )
            v = bit_values[(reg, idx)]
            if v not in (0, 1):
                raise ValueError(
                    f"Bit ({reg!r}, {idx}) has invalid value {v!r}; "
                    "expected 0 or 1."
                )
            values.append(v)

        result = self._compute(values)
        return int(result)

    def _compute(self, values: List[int]) -> bool:
        if self.operation == "NOT":
            return not values[0]
        if self.operation == "AND":
            return all(values)
        if self.operation == "OR":
            return any(values)
        if self.operation == "XOR":
            return sum(values) % 2 == 1
        if self.operation == "NAND":
            return not all(values)
        if self.operation == "NOR":
            return not any(values)
        raise RuntimeError(f"Unhandled operation {self.operation!r}.")

    def __repr__(self) -> str:
        ins = ", ".join(f"{r}[{i}]" for r, i in self.input_bits)
        out_r, out_i = self.output_bit
        return (
            f"ClassicalOperation({self.operation}({ins}) "
            f"-> {out_r}[{out_i}])"
        )


# ---------------------------------------------------------------------------
# Conditional gate
# ---------------------------------------------------------------------------

@dataclass
class ConditionalGate:
    """A gate that is applied only when a classical condition holds.

    Attributes:
        gate_name: Name of the quantum gate (e.g. ``"X"``, ``"H"``).
        target_qubits: Qubit indices the gate acts on.
        condition: The :class:`DCClassicalCondition` to evaluate.
        params: Optional gate parameters (e.g. rotation angles).
    """

    gate_name: str
    target_qubits: List[int]
    condition: DCClassicalCondition
    params: Dict[str, Any] = field(default_factory=dict)

    def apply(self, circuit: Any) -> None:
        """Append the conditional gate to *circuit*.

        The concrete API depends on the circuit class.  This method
        tries ``add_conditional_gate`` first, then falls back to
        unconditionally applying the gate.
        """
        if hasattr(circuit, "add_conditional_gate"):
            circuit.add_conditional_gate(
                gate_name=self.gate_name,
                qubits=self.target_qubits,
                condition=self.condition,
                params=self.params,
            )
        else:
            # Fallback: apply gate unconditionally (best-effort)
            gate_fn = getattr(circuit, self.gate_name.lower(), None)
            if gate_fn is not None:
                gate_fn(*self.target_qubits, **self.params)
            else:
                raise AttributeError(
                    f"Circuit has no method for gate {self.gate_name!r}."
                )

    def __repr__(self) -> str:
        qubits = self.target_qubits if len(self.target_qubits) > 1 else self.target_qubits[0]
        params = f", params={self.params}" if self.params else ""
        return (
            f"ConditionalGate({self.gate_name}({qubits}) "
            f"if {self.condition!r}{params})"
        )


# ---------------------------------------------------------------------------
# While loop (dataclass variant)
# ---------------------------------------------------------------------------

@dataclass
class DCWhileLoop:
    """Repeat a circuit body while a classical condition is ``True``.

    This is the **v2 dataclass** variant — distinct from the v1
    :class:`WhileLoop` in ``dynamic_circuits.py`` which stores
    :class:`Instruction` lists.

    Attributes:
        condition: Condition evaluated at the *top* of each iteration.
        circuit_body: The circuit (or list of operations) to repeat.
        max_iterations: Safety bound to prevent infinite loops.
    """

    condition: DCClassicalCondition
    circuit_body: Any = None
    max_iterations: int = 100

    def __post_init__(self) -> None:
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive.")

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dictionary."""
        body: Any = None
        if self.circuit_body is not None:
            if hasattr(self.circuit_body, "to_dict"):
                body = self.circuit_body.to_dict()
            elif isinstance(self.circuit_body, list):
                body = [
                    op.to_dict() if hasattr(op, "to_dict") else repr(op)
                    for op in self.circuit_body
                ]
            else:
                body = repr(self.circuit_body)
        return {
            "condition": self.condition.to_dict(),
            "circuit_body": body,
            "max_iterations": self.max_iterations,
        }

    def __repr__(self) -> str:
        body_type = type(self.circuit_body).__name__ if self.circuit_body is not None else "None"
        return (
            f"DCWhileLoop(condition={self.condition!r}, "
            f"body={body_type}, max_iterations={self.max_iterations})"
        )


# ---------------------------------------------------------------------------
# Switch-case
# ---------------------------------------------------------------------------

@dataclass
class SwitchCase:
    """Multi-branch classical control flow.

    Attributes:
        classical_bit_index: Index of the classical bit to switch on.
        register: Name of the register containing the bit.
        cases: Maps integer values to lists of operations.
        default: Operations executed when no case matches.
    """

    classical_bit_index: int
    register: str
    cases: Dict[int, List[Any]] = field(default_factory=dict)
    default: Optional[List[Any]] = None

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dictionary."""
        serialised_cases: Dict[str, Any] = {}
        for val, ops in self.cases.items():
            serialised_ops = []
            for op in ops:
                if hasattr(op, "to_dict"):
                    serialised_ops.append(op.to_dict())
                else:
                    serialised_ops.append(repr(op))
            serialised_cases[str(val)] = serialised_ops

        serialised_default: Any = None
        if self.default is not None:
            serialised_default = []
            for op in self.default:
                if hasattr(op, "to_dict"):
                    serialised_default.append(op.to_dict())
                else:
                    serialised_default.append(repr(op))

        return {
            "classical_bit_index": self.classical_bit_index,
            "register": self.register,
            "cases": serialised_cases,
            "default": serialised_default,
        }

    def get_branch(self, bit_value: int) -> Optional[List[Any]]:
        """Return the operation list for *bit_value*, or ``default``."""
        if bit_value in self.cases:
            return self.cases[bit_value]
        return self.default

    def __repr__(self) -> str:
        case_keys = sorted(self.cases.keys())
        has_default = self.default is not None
        return (
            f"SwitchCase({self.register}[{self.classical_bit_index}], "
            f"cases={case_keys}, default={has_default})"
        )


# ---------------------------------------------------------------------------
# Dynamic circuit compiler
# ---------------------------------------------------------------------------

# Backends known to support mid-circuit measurement + feedforward
_DYNAMIC_CAPABLE_BACKENDS = frozenset({
    "ibm_brisbane",
    "ibm_osaka",
    "ibm_kyoto",
    "ibm_torino",
    "ibmsherbrooke",
    "ibm_lagos",
    "ibm_nairobi",
    "ibm_perth",
    "ibm_cairo",
    "ibm_kolkata",
    "ibm_mumbai",
    "ibm_geneva",
    "ibm_peekskill",
    "quantinuum_h1",
    "quantinuum_h1e",
    "quantinuum_h1-1",
    "quantinuum_h2",
    "quantinuum_h2-1",
    "ionq_harmony",
    "ionq_aria",
    "ionq_forte",
    "rigetti_ankaa",
})


class DynamicCircuitCompiler:
    """Compile dynamic circuits targeting specific quantum hardware.

    Translates abstract mid-circuit measurements, conditional gates,
    and classical feedforward into backend-specific instruction streams.

    Usage::

        compiler = DynamicCircuitCompiler(backend="ibm")
        compiled = compiler.compile(my_dynamic_circuit)
    """

    def __init__(self, backend: str = "ibm") -> None:
        if not backend:
            raise ValueError("backend must be a non-empty string.")
        self._backend = backend.lower()

    # -- public API -----------------------------------------------------------

    def compile(self, circuit: Any) -> dict:
        """Compile *circuit* for the target backend.

        Returns:
            Dictionary with keys:
            - ``"backend"``: target backend name.
            - ``"mid_circuit_measurements"``: list of serialised
              measurements.
            - ``"conditional_gates"``: list of serialised conditional
              gates.
            - ``"classical_registers"``: list of register descriptors.
            - ``"resource_overhead"``: estimated resource overhead.
            - ``"native_gates"``: list of native gate names.
            - ``"supports_dynamic"``: ``True`` / ``False``.

        Raises:
            ValueError: if the circuit is incompatible with the
                backend.
        """
        self._validate_mid_circuit_support(circuit, self._backend)

        result: Dict[str, Any] = {
            "backend": self._backend,
            "supports_dynamic": True,
        }

        if self._backend.startswith("ibm") or self._backend.startswith("ibm_"):
            result.update(self._compile_for_ibm(circuit))
        elif self._backend.startswith("ionq"):
            result.update(self._compile_for_ionq(circuit))
        elif self._backend.startswith("quantinuum"):
            result.update(self._compile_for_quantinuum(circuit))
        else:
            result.update(self._compile_generic(circuit))

        result["resource_overhead"] = self.estimate_resource_overhead(circuit)
        return result

    # -- backend-specific compilers -------------------------------------------

    def _compile_for_ibm(self, circuit: Any) -> dict:
        """IBM-specific compilation (Eagle/Heron backends)."""
        measurements = self._extract_mid_circuit_measurements(circuit)
        conditionals = self._extract_conditional_gates(circuit)
        registers = self._extract_classical_registers(circuit)

        return {
            "native_gates": [
                "id", "rz", "sx", "x", "cx", "ecr", "rxx", "ryy", "rzz",
            ],
            "mid_circuit_measurements": [m.to_dict() for m in measurements],
            "conditional_gates": [
                {"gate": c.gate_name, "qubits": c.target_qubits,
                 "condition": c.condition.to_dict(), "params": c.params}
                for c in conditionals
            ],
            "classical_registers": [
                {"name": r.name, "size": r.size} for r in registers
            ],
            "transpilation_notes": [
                "Dynamic circuits require the Qiskit Runtime primitives.",
                "Mid-circuit measurements are mapped to "
                "single-qubit measure ops.",
                "Conditional gates use the 'if_else' circuit operation.",
            ],
        }

    def _compile_for_ionq(self, circuit: Any) -> dict:
        """IonQ-specific compilation (trapped-ion backends)."""
        measurements = self._extract_mid_circuit_measurements(circuit)
        conditionals = self._extract_conditional_gates(circuit)
        registers = self._extract_classical_registers(circuit)

        return {
            "native_gates": ["gpi", "gpi2", "ms"],
            "mid_circuit_measurements": [m.to_dict() for m in measurements],
            "conditional_gates": [
                {"gate": c.gate_name, "qubits": c.target_qubits,
                 "condition": c.condition.to_dict(), "params": c.params}
                for c in conditionals
            ],
            "classical_registers": [
                {"name": r.name, "size": r.size} for r in registers
            ],
            "transpilation_notes": [
                "IonQ supports arbitrary single-qubit rotations natively.",
                "Mid-circuit measurement is natively supported.",
                "No two-qubit gate decomposition required (native MS gate).",
            ],
        }

    def _compile_for_quantinuum(self, circuit: Any) -> dict:
        """Quantinuum-specific compilation (H-series backends)."""
        measurements = self._extract_mid_circuit_measurements(circuit)
        conditionals = self._extract_conditional_gates(circuit)
        registers = self._extract_classical_registers(circuit)

        return {
            "native_gates": ["rz", "rx", "ry", "rxx", "h"],
            "mid_circuit_measurements": [m.to_dict() for m in measurements],
            "conditional_gates": [
                {"gate": c.gate_name, "qubits": c.target_qubits,
                 "condition": c.condition.to_dict(), "params": c.params}
                for c in conditionals
            ],
            "classical_registers": [
                {"name": r.name, "size": r.size} for r in registers
            ],
            "transpilation_notes": [
                "Quantinuum H-series supports dynamic circuits natively.",
                "TK1 and TK2 native gates are used.",
                "Mid-circuit measurement and feedforward are first-class.",
            ],
        }

    def _compile_generic(self, circuit: Any) -> dict:
        """Generic fallback for unknown backends."""
        measurements = self._extract_mid_circuit_measurements(circuit)
        conditionals = self._extract_conditional_gates(circuit)
        registers = self._extract_classical_registers(circuit)

        return {
            "native_gates": ["cx", "rz", "sx", "x", "h"],
            "mid_circuit_measurements": [m.to_dict() for m in measurements],
            "conditional_gates": [
                {"gate": c.gate_name, "qubits": c.target_qubits,
                 "condition": c.condition.to_dict(), "params": c.params}
                for c in conditionals
            ],
            "classical_registers": [
                {"name": r.name, "size": r.size} for r in registers
            ],
            "transpilation_notes": [
                "Generic compilation — verify backend compatibility.",
            ],
        }

    # -- validation -----------------------------------------------------------

    def _validate_mid_circuit_support(
        self, circuit: Any, backend: str,
    ) -> None:
        """Validate that the backend supports dynamic circuits.

        Raises:
            ValueError: if the backend does not support mid-circuit
                measurement.
        """
        # Check against known list
        if backend not in _DYNAMIC_CAPABLE_BACKENDS:
            # Check if the circuit actually needs dynamic features
            measurements = self._extract_mid_circuit_measurements(circuit)
            conditionals = self._extract_conditional_gates(circuit)
            if measurements or conditionals:
                raise ValueError(
                    f"Backend {backend!r} is not known to support "
                    "dynamic circuits.  Remove mid-circuit measurements "
                    "and conditional gates, or target a supported "
                    f"backend from: {sorted(_DYNAMIC_CAPABLE_BACKENDS)}."
                )

    # -- resource estimation ---------------------------------------------------

    def estimate_resource_overhead(self, circuit: Any) -> dict:
        """Estimate the extra resource cost of dynamic features.

        Returns:
            Dictionary with estimated overhead metrics.
        """
        measurements = self._extract_mid_circuit_measurements(circuit)
        conditionals = self._extract_conditional_gates(circuit)
        registers = self._extract_classical_registers(circuit)

        num_measurements = len(measurements)
        num_conditionals = len(conditionals)
        total_clbits = sum(r.size for r in registers)

        # Rough heuristic: each mid-circuit measurement adds ~5μs
        # classical processing latency; each conditional gate adds ~10μs.
        classical_latency_us = num_measurements * 5 + num_conditionals * 10

        return {
            "num_mid_circuit_measurements": num_measurements,
            "num_conditional_gates": num_conditionals,
            "total_classical_bits": total_clbits,
            "classical_processing_latency_us": classical_latency_us,
            "extra_circuit_depth_estimate": num_measurements + num_conditionals,
            "requires_real_time_classical": num_conditionals > 0,
        }

    # -- extraction helpers ---------------------------------------------------

    @staticmethod
    def _extract_mid_circuit_measurements(circuit: Any) -> List[MidCircuitMeasurement]:
        """Pull ``MidCircuitMeasurement`` objects from *circuit*."""
        if hasattr(circuit, "mid_circuit_measurements"):
            return list(circuit.mid_circuit_measurements)
        if hasattr(circuit, "_mid_circuit_measurements"):
            return list(circuit._mid_circuit_measurements)
        return []

    @staticmethod
    def _extract_conditional_gates(circuit: Any) -> List[ConditionalGate]:
        """Pull ``ConditionalGate`` objects from *circuit*."""
        if hasattr(circuit, "conditional_gates"):
            return list(circuit.conditional_gates)
        if hasattr(circuit, "_conditional_gates"):
            return list(circuit._conditional_gates)
        return []

    @staticmethod
    def _extract_classical_registers(circuit: Any) -> List[ClassicalRegister]:
        """Pull ``ClassicalRegister`` objects from *circuit*."""
        if hasattr(circuit, "classical_registers"):
            return list(circuit.classical_registers)
        if hasattr(circuit, "_classical_registers"):
            return list(circuit._classical_registers)
        return []


# ---------------------------------------------------------------------------
# Feedforward controller
# ---------------------------------------------------------------------------

class FeedforwardController:
    """Resolve conditional operations given measured classical values.

    The controller accumulates conditional operations and, once
    measured values are available, resolves which operations to
    actually perform.

    Usage::

        ffc = FeedforwardController()
        cond = DCClassicalCondition(bit_index=0, register="c",
                                     comparison="==", value=1)
        ffc.add_condition(qubit=1, classical_bit=0,
                          operation="X", params={})
        resolved = ffc.resolve(circuit, measured_values)
    """

    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []

    # -- public API -----------------------------------------------------------

    def add_condition(
        self,
        qubit: int,
        classical_bit: int,
        operation: str,
        params: Optional[Dict[str, Any]] = None,
        register: str = "c",
        comparison: str = "==",
        value: int = 1,
    ) -> None:
        """Register a feedforward operation.

        Args:
            qubit: Target qubit for the operation.
            classical_bit: Classical bit to test.
            operation: Gate name (e.g. ``"X"``, ``"Z"``).
            params: Optional gate parameters.
            register: Name of the classical register.
            comparison: Comparison operator.
            value: Value to compare against.
        """
        condition = DCClassicalCondition(
            bit_index=classical_bit,
            register=register,
            comparison=comparison,
            value=value,
        )
        self._entries.append({
            "qubit": qubit,
            "classical_bit": classical_bit,
            "register": register,
            "operation": operation,
            "params": params or {},
            "condition": condition,
        })

    def resolve(
        self,
        circuit: Any,
        measured_values: ClassicalRegister,
    ) -> Any:
        """Apply all feedforward operations whose conditions are met.

        Args:
            circuit: The quantum circuit to modify.
            measured_values: The :class:`ClassicalRegister` holding
                measurement results.

        Returns:
            The (mutated) *circuit* for convenience.
        """
        for entry in self._entries:
            cond: DCClassicalCondition = entry["condition"]
            try:
                if cond.evaluate(measured_values):
                    gate_fn = getattr(circuit, entry["operation"].lower(), None)
                    if gate_fn is not None:
                        gate_fn(entry["qubit"], **entry["params"])
            except (ValueError, IndexError):
                # Bit not measured yet — skip this entry silently.
                continue
        return circuit

    def get_all_conditions(self) -> List[DCClassicalCondition]:
        """Return all registered conditions."""
        return [e["condition"] for e in self._entries]

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"FeedforwardController(entries={len(self._entries)})"


# ---------------------------------------------------------------------------
# Dynamic circuit executor
# ---------------------------------------------------------------------------

class DynamicCircuitExecutor:
    """Execute dynamic circuits on real quantum hardware.

    Wraps a backend provider and handles the measurement →
    feedforward → re-measurement cycle that dynamic circuits
    require.

    Usage::

        executor = DynamicCircuitExecutor(backend_provider=my_provider)
        results = executor.execute(circuit, shots=2048)
    """

    def __init__(self, backend_provider: Any) -> None:
        if backend_provider is None:
            raise ValueError("backend_provider must not be None.")
        self._provider = backend_provider

    def execute(self, circuit: Any, shots: int = 1024) -> dict:
        """Execute a dynamic circuit with mid-circuit measurements.

        Returns:
            Dictionary with keys:
            - ``"counts"``: binned measurement outcomes.
            - ``"total_shots"``: number of shots executed.
            - ``"metadata"``: backend-specific metadata.
        """
        if shots <= 0:
            raise ValueError("shots must be positive.")

        # Attempt to delegate to the provider's run method
        raw_results = self._run_on_backend(circuit, shots)
        results = self._collect_results(raw_results)
        counts = self._bin_counts(results)

        return {
            "counts": counts,
            "total_shots": shots,
            "metadata": {
                "backend": getattr(self._provider, "name", "unknown"),
                "shots": shots,
                "num_qubits": getattr(circuit, "num_qubits", None),
                "num_clbits": getattr(circuit, "num_clbits", None),
            },
        }

    # -- internal helpers -----------------------------------------------------

    def _run_on_backend(self, circuit: Any, shots: int) -> Any:
        """Submit the circuit to the backend provider."""
        if hasattr(self._provider, "run"):
            return self._provider.run(circuit, shots=shots)
        if hasattr(self._provider, "execute"):
            return self._provider.execute(circuit, shots=shots)
        # Fallback: return the circuit itself (simulated / no-op)
        return {"circuit": circuit, "shots": shots}

    def _collect_results(self, raw_results: Any) -> List[str]:
        """Normalise backend results into a list of bitstrings."""
        if raw_results is None:
            return []

        # Qiskit-style result object
        if hasattr(raw_results, "get_counts"):
            counts = raw_results.get_counts()
            outcomes: List[str] = []
            for bitstring, count in counts.items():
                outcomes.extend([bitstring] * count)
            return outcomes

        # Dict of counts already
        if isinstance(raw_results, dict) and "counts" in raw_results:
            counts = raw_results["counts"]
            if isinstance(counts, dict):
                outcomes = []
                for bitstring, count in counts.items():
                    outcomes.extend([str(bitstring)] * count)
                return outcomes

        # Already a list of bitstrings
        if isinstance(raw_results, list):
            return [str(r) for r in raw_results]

        return [str(raw_results)]

    def _bin_counts(self, results: List[str]) -> Dict[str, int]:
        """Bin a list of bitstrings into counts."""
        counts: Dict[str, int] = {}
        for bitstring in results:
            # Normalise: strip spaces, ensure consistent endianness
            key = bitstring.replace(" ", "")
            counts[key] = counts.get(key, 0) + 1
        return counts

    def __repr__(self) -> str:
        provider_name = getattr(self._provider, "name", type(self._provider).__name__)
        return f"DynamicCircuitExecutor(provider={provider_name!r})"


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def create_bell_pair_with_condition() -> Any:
    """Create a Bell pair using mid-circuit measurement and feedforward.

    Circuit:
        1. Prepare |Φ+⟩ on qubits 0, 1.
        2. Measure qubit 0 mid-circuit.
        3. Conditionally correct qubit 1.

    Returns:
        A dynamic circuit dictionary describing the operations.
    """
    meas = MidCircuitMeasurement(qubit=0, classical_bit=0, basis="Z")

    condition = DCClassicalCondition(
        bit_index=0, register="c", comparison="==", value=1,
    )
    correction = ConditionalGate(
        gate_name="X",
        target_qubits=[1],
        condition=condition,
    )

    return {
        "type": "bell_pair_with_condition",
        "num_qubits": 2,
        "num_clbits": 1,
        "operations": [
            {"gate": "H", "qubits": [0]},
            {"gate": "CX", "qubits": [0, 1]},
            {"measurement": meas.to_dict()},
            {"conditional_gate": {
                "gate": "X",
                "qubits": [1],
                "condition": condition.to_dict(),
            }},
        ],
        "description": (
            "Bell pair (|Φ+⟩) prepared on qubits 0,1. Qubit 0 is "
            "measured mid-circuit; if result is 1, X is applied to "
            "qubit 1 to preserve entanglement."
        ),
    }


def create_bit_flip_detection() -> Any:
    """Create a bit-flip error detection circuit with feedforward.

    Circuit:
        1. Encode logical qubit into a 3-qubit repetition code.
        2. Apply a bit-flip (simulating noise).
        3. Measure syndrome qubits mid-circuit.
        4. Conditionally correct the data qubit.

    Returns:
        A dynamic circuit dictionary describing the operations.
    """
    syndrome_meas_0 = MidCircuitMeasurement(qubit=3, classical_bit=0, basis="Z")
    syndrome_meas_1 = MidCircuitMeasurement(qubit=4, classical_bit=1, basis="Z")

    # If syndrome 0 == 1 and syndrome 1 == 0 → error on qubit 0
    cond_q0 = DCClassicalCondition(
        bit_index=0, register="c", comparison="==", value=1,
    )
    correction_q0 = ConditionalGate(
        gate_name="X", target_qubits=[0], condition=cond_q0,
    )

    # If syndrome 0 == 0 and syndrome 1 == 1 → error on qubit 2
    cond_q2 = DCClassicalCondition(
        bit_index=1, register="c", comparison="==", value=1,
    )
    correction_q2 = ConditionalGate(
        gate_name="X", target_qubits=[2], condition=cond_q2,
    )

    return {
        "type": "bit_flip_detection",
        "num_qubits": 5,
        "num_clbits": 2,
        "operations": [
            # Encoding
            {"gate": "CX", "qubits": [0, 1]},
            {"gate": "CX", "qubits": [0, 2]},
            # Simulated noise
            {"gate": "X", "qubits": [0], "label": "noise"},
            # Syndrome extraction
            {"gate": "CX", "qubits": [0, 3]},
            {"gate": "CX", "qubits": [1, 3]},
            {"gate": "CX", "qubits": [1, 4]},
            {"gate": "CX", "qubits": [2, 4]},
            # Mid-circuit measurements
            {"measurement": syndrome_meas_0.to_dict()},
            {"measurement": syndrome_meas_1.to_dict()},
            # Feedforward corrections
            {"conditional_gate": {
                "gate": "X", "qubits": [0],
                "condition": cond_q0.to_dict(),
            }},
            {"conditional_gate": {
                "gate": "X", "qubits": [2],
                "condition": cond_q2.to_dict(),
            }},
        ],
        "description": (
            "3-qubit repetition code with mid-circuit syndrome "
            "measurement and feedforward bit-flip correction."
        ),
    }


def create_teleportation_circuit() -> Any:
    """Create a quantum teleportation circuit (v2) with mid-circuit measurement.

    Teleports the state of qubit 0 to qubit 2 using:
        1. Bell pair on qubits 1, 2.
        2. Bell measurement on qubits 0, 1.
        3. Mid-circuit measurements.
        4. Conditional X and Z corrections on qubit 2.

    Returns:
        A dynamic circuit dictionary describing the operations.
    """
    meas_0 = MidCircuitMeasurement(qubit=0, classical_bit=0, basis="Z")
    meas_1 = MidCircuitMeasurement(qubit=1, classical_bit=1, basis="Z")

    cond_x = DCClassicalCondition(
        bit_index=0, register="c", comparison="==", value=1,
    )
    correction_x = ConditionalGate(
        gate_name="X", target_qubits=[2], condition=cond_x,
    )

    cond_z = DCClassicalCondition(
        bit_index=1, register="c", comparison="==", value=1,
    )
    correction_z = ConditionalGate(
        gate_name="Z", target_qubits=[2], condition=cond_z,
    )

    return {
        "type": "teleportation",
        "num_qubits": 3,
        "num_clbits": 2,
        "operations": [
            # State to teleport (example: |+⟩)
            {"gate": "H", "qubits": [0]},
            # Bell pair
            {"gate": "H", "qubits": [1]},
            {"gate": "CX", "qubits": [1, 2]},
            # Bell measurement
            {"gate": "CX", "qubits": [0, 1]},
            {"gate": "H", "qubits": [0]},
            # Mid-circuit measurements
            {"measurement": meas_0.to_dict()},
            {"measurement": meas_1.to_dict()},
            # Classical corrections
            {"conditional_gate": {
                "gate": "X", "qubits": [2],
                "condition": cond_x.to_dict(),
            }},
            {"conditional_gate": {
                "gate": "Z", "qubits": [2],
                "condition": cond_z.to_dict(),
            }},
        ],
        "description": (
            "Quantum teleportation using mid-circuit measurements "
            "and conditional X/Z corrections."
        ),
    }


# Backends known to support dynamic circuits (public constant)
DYNAMIC_CAPABLE_BACKENDS = frozenset(_DYNAMIC_CAPABLE_BACKENDS)


def is_dynamic_capable(backend_name: str) -> bool:
    """Check whether *backend_name* supports dynamic circuits.

    Returns ``True`` if the backend is in the known-capable list.
    Matching is case-insensitive and prefix-based (e.g.
    ``"IBM_Brisbane"`` matches ``"ibm_brisbane"``).
    """
    normalised = backend_name.lower().replace(" ", "_")
    for known in _DYNAMIC_CAPABLE_BACKENDS:
        if normalised == known or normalised.startswith(known):
            return True
    return False


def estimate_classical_processing_overhead(circuit: Any) -> dict:
    """Estimate the classical processing overhead of a dynamic circuit.

    Returns:
        Dictionary with:
        - ``"num_mid_circuit_measurements"``: count of mid-circuit
          measurements.
        - ``"num_conditional_gates"``: count of conditional gates.
        - ``"num_classical_registers"``: count of classical registers.
        - ``"total_classical_bits"``: total bits across all registers.
        - ``"estimated_classical_latency_us"``: rough latency in
          microseconds.
        - ``"requires_real_time_classical"``: whether real-time
          classical processing is needed.
    """
    compiler = DynamicCircuitCompiler(backend="generic")
    overhead = compiler.estimate_resource_overhead(circuit)

    registers = DynamicCircuitCompiler._extract_classical_registers(circuit)
    total_clbits = sum(r.size for r in registers) if registers else overhead["total_classical_bits"]

    return {
        "num_mid_circuit_measurements": overhead["num_mid_circuit_measurements"],
        "num_conditional_gates": overhead["num_conditional_gates"],
        "num_classical_registers": len(registers),
        "total_classical_bits": total_clbits,
        "estimated_classical_latency_us": overhead["classical_processing_latency_us"],
        "requires_real_time_classical": overhead["requires_real_time_classical"],
    }
