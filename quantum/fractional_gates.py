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

"""Fractional Gate Operations for UmerOS Quantum Computing.

Implements fractional gate operations for advanced quantum computing —
gates with non-integer parameter angles, useful for variational algorithms
and pulse-efficient transpilation.

Gate Categories:
- Single-qubit fractional rotations: FractionalRX, FractionalRY, FractionalRZ, FractionalPhase
- Two-qubit fractional controlled rotations: FractionalCRX, FractionalCRY, FractionalCRZ
- Two-qubit fractional interactions: FractionalRXX, FractionalRYY, FractionalRZZ, FractionalZXZ
- Library and utilities: ParametricGateLibrary, angle manipulation helpers
"""

from __future__ import annotations

import math
import cmath
from typing import Optional, List, Tuple, Dict, Sequence

import numpy as np
from numpy.typing import NDArray

from .gates import Gate
from .circuit import QuantumCircuit


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class FractionalRotationGate(Gate):
    """Base class for gates with fractional rotation angles.

    Provides angle normalization and a common interface for all
    fractional rotation gates. Angles are stored in radians and
    normalized to [-pi, pi].

    Parameters
    ----------
    name : str
        Gate name.
    num_qubits : int
        Number of qubits the gate acts on.
    matrix : NDArray
        Unitary matrix representation.
    theta : float
        Rotation angle in radians.
    qubit : int, optional
        Qubit index this gate is applied to (default 0).
    """

    def __init__(
        self,
        name: str,
        num_qubits: int,
        matrix: NDArray[np.complex128],
        theta: float,
        qubit: int = 0,
    ):
        self._theta = float(theta)
        self._qubit = qubit
        super().__init__(
            name=name,
            num_qubits=num_qubits,
            matrix=matrix,
            params=[self._theta],
        )

    @property
    def theta(self) -> float:
        """Rotation angle in radians."""
        return self._theta

    @property
    def qubit(self) -> int:
        """Qubit index this gate acts on."""
        return self._qubit

    def normalize_angle(self) -> float:
        """Reduce angle to [-pi, pi].

        Returns
        -------
        float
            Angle in [-pi, pi].
        """
        normalized = self._theta % (2 * math.pi)
        if normalized > math.pi:
            normalized -= 2 * math.pi
        return normalized

    def __repr__(self) -> str:
        return f"{self.name}(theta={self._theta:.6f})"


# ---------------------------------------------------------------------------
# Single-qubit fractional rotations
# ---------------------------------------------------------------------------

class FractionalRX(FractionalRotationGate):
    """Fractional RX rotation gate.

    Applies a rotation about the X-axis by an arbitrary angle theta.

    Matrix
    ------
    RX(θ) = [[cos(θ/2),      -i·sin(θ/2)],
              [-i·sin(θ/2),    cos(θ/2)  ]]

    Parameters
    ----------
    theta : float
        Rotation angle in radians.
    """

    def __init__(self, theta: float):
        c = math.cos(theta / 2)
        s = math.sin(theta / 2)
        matrix = np.array(
            [[c, -1j * s],
             [-1j * s, c]],
            dtype=np.complex128,
        )
        super().__init__("FractionalRX", 1, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalRX(theta={self.theta:.6f})"


class FractionalRY(FractionalRotationGate):
    """Fractional RY rotation gate.

    Applies a rotation about the Y-axis by an arbitrary angle theta.

    Matrix
    ------
    RY(θ) = [[cos(θ/2),  -sin(θ/2)],
              [sin(θ/2),   cos(θ/2)]]

    Parameters
    ----------
    theta : float
        Rotation angle in radians.
    """

    def __init__(self, theta: float):
        c = math.cos(theta / 2)
        s = math.sin(theta / 2)
        matrix = np.array(
            [[c, -s],
             [s, c]],
            dtype=np.complex128,
        )
        super().__init__("FractionalRY", 1, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalRY(theta={self.theta:.6f})"


class FractionalRZ(FractionalRotationGate):
    """Fractional RZ rotation gate.

    Applies a rotation about the Z-axis by an arbitrary angle theta.

    Matrix
    ------
    RZ(θ) = [[e^(-iθ/2),  0      ],
              [0,           e^(iθ/2)]]

    Parameters
    ----------
    theta : float
        Rotation angle in radians.
    """

    def __init__(self, theta: float):
        matrix = np.array(
            [[cmath.exp(-1j * theta / 2), 0],
             [0, cmath.exp(1j * theta / 2)]],
            dtype=np.complex128,
        )
        super().__init__("FractionalRZ", 1, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalRZ(theta={self.theta:.6f})"


class FractionalPhase(FractionalRotationGate):
    """Fractional Phase gate.

    Applies a phase shift of theta to the |1⟩ state.

    Matrix
    ------
    P(θ) = [[1, 0      ],
             [0, e^(iθ) ]]

    Parameters
    ----------
    theta : float
        Phase angle in radians.
    """

    def __init__(self, theta: float):
        matrix = np.array(
            [[1, 0],
             [0, cmath.exp(1j * theta)]],
            dtype=np.complex128,
        )
        super().__init__("FractionalPhase", 1, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalPhase(theta={self.theta:.6f})"


# ---------------------------------------------------------------------------
# Two-qubit fractional controlled rotations
# ---------------------------------------------------------------------------

class FractionalCRX(FractionalRotationGate):
    """Fractional controlled-RX gate.

    Applies RX(theta) to the target qubit when the control qubit is |1⟩.

    Matrix: 4x4 block diagonal — I in the |0⟩ block, RX(θ) in the |1⟩ block.

    Parameters
    ----------
    theta : float
        Rotation angle in radians.
    """

    def __init__(self, theta: float):
        c = math.cos(theta / 2)
        s = math.sin(theta / 2)
        rx = np.array([[c, -1j * s], [-1j * s, c]], dtype=np.complex128)
        matrix = np.eye(4, dtype=np.complex128)
        matrix[2:, 2:] = rx
        super().__init__("FractionalCRX", 2, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalCRX(theta={self.theta:.6f})"


class FractionalCRY(FractionalRotationGate):
    """Fractional controlled-RY gate.

    Applies RY(theta) to the target qubit when the control qubit is |1⟩.

    Matrix: 4x4 block diagonal — I in the |0⟩ block, RY(θ) in the |1⟩ block.

    Parameters
    ----------
    theta : float
        Rotation angle in radians.
    """

    def __init__(self, theta: float):
        c = math.cos(theta / 2)
        s = math.sin(theta / 2)
        ry = np.array([[c, -s], [s, c]], dtype=np.complex128)
        matrix = np.eye(4, dtype=np.complex128)
        matrix[2:, 2:] = ry
        super().__init__("FractionalCRY", 2, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalCRY(theta={self.theta:.6f})"


class FractionalCRZ(FractionalRotationGate):
    """Fractional controlled-RZ gate.

    Applies RZ(theta) to the target qubit when the control qubit is |1⟩.

    Matrix: 4x4 block diagonal — I in the |0⟩ block, RZ(θ) in the |1⟩ block.

    Parameters
    ----------
    theta : float
        Rotation angle in radians.
    """

    def __init__(self, theta: float):
        matrix = np.eye(4, dtype=np.complex128)
        matrix[2, 2] = cmath.exp(-1j * theta / 2)
        matrix[3, 3] = cmath.exp(1j * theta / 2)
        super().__init__("FractionalCRZ", 2, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalCRZ(theta={self.theta:.6f})"


# ---------------------------------------------------------------------------
# Two-qubit fractional interaction gates
# ---------------------------------------------------------------------------

class FractionalRXX(FractionalRotationGate):
    """Fractional RXX interaction gate.

    Evolves the system under the XX interaction: exp(-iθ·X⊗X/2).

    Matrix
    ------
    RXX(θ) = [[cos(θ/2),       0,              0,            -i·sin(θ/2)],
               [0,              cos(θ/2),       -i·sin(θ/2),  0          ],
               [0,              -i·sin(θ/2),    cos(θ/2),     0          ],
               [-i·sin(θ/2),    0,              0,            cos(θ/2)   ]]

    Parameters
    ----------
    theta : float
        Interaction strength (radians).
    """

    def __init__(self, theta: float):
        c = math.cos(theta / 2)
        s = math.sin(theta / 2)
        matrix = np.array(
            [[c, 0, 0, -1j * s],
             [0, c, -1j * s, 0],
             [0, -1j * s, c, 0],
             [-1j * s, 0, 0, c]],
            dtype=np.complex128,
        )
        super().__init__("FractionalRXX", 2, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalRXX(theta={self.theta:.6f})"


class FractionalRYY(FractionalRotationGate):
    """Fractional RYY interaction gate.

    Evolves the system under the YY interaction: exp(-iθ·Y⊗Y/2).

    Matrix
    ------
    RYY(θ) = [[cos(θ/2),       0,             0,           i·sin(θ/2)],
               [0,              cos(θ/2),      i·sin(θ/2),  0         ],
               [0,              i·sin(θ/2),    cos(θ/2),    0         ],
               [i·sin(θ/2),     0,             0,           cos(θ/2)  ]]

    Parameters
    ----------
    theta : float
        Interaction strength (radians).
    """

    def __init__(self, theta: float):
        c = math.cos(theta / 2)
        s = math.sin(theta / 2)
        matrix = np.array(
            [[c, 0, 0, 1j * s],
             [0, c, 1j * s, 0],
             [0, 1j * s, c, 0],
             [1j * s, 0, 0, c]],
            dtype=np.complex128,
        )
        super().__init__("FractionalRYY", 2, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalRYY(theta={self.theta:.6f})"


class FractionalRZZ(FractionalRotationGate):
    """Fractional RZZ interaction gate.

    Evolves the system under the ZZ interaction: exp(-iθ·Z⊗Z/2).

    Matrix: 4x4 diagonal
    ------
    RZZ(θ) = diag(e^(-iθ), e^(iθ), e^(iθ), e^(-iθ))

    Parameters
    ----------
    theta : float
        Interaction strength (radians).
    """

    def __init__(self, theta: float):
        matrix = np.diag([
            cmath.exp(-1j * theta),
            cmath.exp(1j * theta),
            cmath.exp(1j * theta),
            cmath.exp(-1j * theta),
        ]).astype(np.complex128)
        super().__init__("FractionalRZZ", 2, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalRZZ(theta={self.theta:.6f})"


class FractionalZXZ(FractionalRotationGate):
    """Fractional ZXZ interaction gate.

    Fractional ZXZ rotation: Rz(theta/2) @ Rx(theta) @ Rz(theta/2).

    Matrix: 2x2 (single-qubit composite rotation)

    Parameters
    ----------
    theta : float
        Rotation angle (radians).
    """

    def __init__(self, theta: float):
        c = math.cos(theta / 2)
        s = math.sin(theta / 2)
        # Rz(theta/2)
        Rz_half = np.array(
            [[math.e ** (-1j * theta / 4), 0],
             [0, math.e ** (1j * theta / 4)]],
            dtype=np.complex128,
        )
        # Rx(theta)
        Rx = np.array(
            [[c, -1j * s],
             [-1j * s, c]],
            dtype=np.complex128,
        )
        # Full ZXZ: Rz(theta/2) @ Rx(theta) @ Rz(theta/2)
        matrix = Rz_half @ Rx @ Rz_half
        super().__init__("FractionalZXZ", 1, matrix, theta)

    def __repr__(self) -> str:
        return f"FractionalZXZ(theta={self.theta:.6f})"


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def fractional_rotation_matrix(axis: str, angle: float) -> NDArray[np.complex128]:
    """Compute a single-qubit rotation matrix about the given axis.

    Parameters
    ----------
    axis : str
        Rotation axis: 'x', 'y', or 'z'.
    angle : float
        Rotation angle in radians.

    Returns
    -------
    NDArray[np.complex128]
        2x2 unitary rotation matrix.

    Raises
    ------
    ValueError
        If axis is not 'x', 'y', or 'z'.

    Examples
    --------
    >>> m = fractional_rotation_matrix('x', math.pi / 4)
    >>> m.shape
    (2, 2)
    """
    axis = axis.lower()
    if axis == "x":
        c, s = math.cos(angle / 2), math.sin(angle / 2)
        return np.array([[c, -1j * s], [-1j * s, c]], dtype=np.complex128)
    elif axis == "y":
        c, s = math.cos(angle / 2), math.sin(angle / 2)
        return np.array([[c, -s], [s, c]], dtype=np.complex128)
    elif axis == "z":
        return np.array(
            [[cmath.exp(-1j * angle / 2), 0],
             [0, cmath.exp(1j * angle / 2)]],
            dtype=np.complex128,
        )
    else:
        raise ValueError(f"Invalid axis '{axis}'. Must be 'x', 'y', or 'z'.")


def controlled_fractional_matrix(gate_matrix: NDArray[np.complex128]) -> NDArray[np.complex128]:
    """Compute the controlled version of any single-qubit gate.

    Parameters
    ----------
    gate_matrix : NDArray[np.complex128]
        2x2 unitary matrix of the single-qubit gate.

    Returns
    -------
    NDArray[np.complex128]
        4x4 controlled gate matrix.

    Raises
    ------
    ValueError
        If gate_matrix is not 2x2.
    """
    if gate_matrix.shape != (2, 2):
        raise ValueError(
            f"Expected 2x2 gate matrix, got shape {gate_matrix.shape}"
        )
    matrix = np.eye(4, dtype=np.complex128)
    matrix[2:, 2:] = gate_matrix
    return matrix


def decompose_to_rotation_chain(
    theta: float, axis: str
) -> List[Tuple[str, float]]:
    """Decompose a rotation angle into a chain of primitive rotations.

    Breaks down a large rotation into smaller rotation gates plus
    accumulated phase, useful for pulse-efficient decomposition.

    Parameters
    ----------
    theta : float
        Total rotation angle in radians.
    axis : str
        Rotation axis: 'x', 'y', or 'z'.

    Returns
    -------
    List[Tuple[str, float]]
        List of (gate_name, angle) pairs forming the decomposition.

    Examples
    --------
    >>> chain = decompose_to_rotation_chain(3 * math.pi, 'x')
    >>> all(g[0] == 'RX' for g in chain)
    True
    """
    gate_map = {"x": "RX", "y": "RY", "z": "RZ"}
    axis = axis.lower()
    if axis not in gate_map:
        raise ValueError(f"Invalid axis '{axis}'. Must be 'x', 'y', or 'z'.")

    gate_name = gate_map[axis]
    normalized = theta % (2 * math.pi)
    if normalized > math.pi:
        normalized -= 2 * math.pi

    if abs(normalized) < 1e-12:
        return []

    # If angle is small enough, single gate suffices
    if abs(normalized) <= math.pi:
        return [(gate_name, normalized)]

    # Decompose into pi rotations plus remainder
    num_full = int(abs(normalized) // math.pi)
    remainder = normalized - math.copysign(num_full * math.pi, normalized)
    chain: List[Tuple[str, float]] = []
    for _ in range(num_full):
        chain.append((gate_name, math.copysign(math.pi, normalized)))
    if abs(remainder) > 1e-12:
        chain.append((gate_name, remainder))
    return chain


def validate_angle_range(angle: float, gate_name: str) -> bool:
    """Check if an angle is within the valid range for a given gate.

    Parameters
    ----------
    angle : float
        Rotation angle in radians.
    gate_name : str
        Name of the fractional gate.

    Returns
    -------
    bool
        True if the angle is in the valid range, False otherwise.
    """
    # All fractional gates accept any real angle
    _single_qubit = {
        "FractionalRX", "FractionalRY", "FractionalRZ", "FractionalPhase",
    }
    _two_qubit = {
        "FractionalCRX", "FractionalCRY", "FractionalCRZ",
        "FractionalRXX", "FractionalRYY", "FractionalRZZ", "FractionalZXZ",
    }

    if gate_name not in _single_qubit and gate_name not in _two_qubit:
        return False

    # All fractional gates are continuous — any real angle is valid
    return math.isfinite(angle)


def optimize_angles_forardware(
    circuit: QuantumCircuit,
    target_gates: Optional[List[str]] = None,
) -> QuantumCircuit:
    """Rewrite fractional angles in a circuit for target hardware.

    Normalizes angles to [-pi, pi] and eliminates identity rotations
    (angles very close to 0 or multiples of 2pi).

    Parameters
    ----------
    circuit : QuantumCircuit
        Input quantum circuit.
    target_gates : List[str], optional
        Target hardware gate set (currently unused; reserved for
        future hardware-specific optimization).

    Returns
    -------
    QuantumCircuit
        Optimized circuit with cleaned-up angles.
    """
    from .circuit import Instruction

    optimized = QuantumCircuit(circuit.num_qubits)

    for instr in circuit.instructions:
        gate = instr.gate

        # Only optimize fractional gates
        if not isinstance(gate, FractionalRotationGate):
            for qb in instr.qubits:
                optimized._instructions.append(
                    Instruction(gate=gate, qubits=list(instr.qubits))
                )
                break
            else:
                optimized._instructions.append(
                    Instruction(gate=gate, qubits=list(instr.qubits))
                )
            continue

        # Normalize angle to [-pi, pi]
        theta = gate.normalize_angle()

        # Skip identity rotations
        if abs(theta) < 1e-12:
            continue

        # Recreate gate with normalized angle
        normalized_gate = _recreate_fractional_gate(type(gate).__name__, theta)
        optimized._instructions.append(
            Instruction(gate=normalized_gate, qubits=list(instr.qubits))
        )

    return optimized


def _recreate_fractional_gate(class_name: str, theta: float) -> FractionalRotationGate:
    """Recreate a fractional gate by class name and angle."""
    _registry = {
        "FractionalRX": FractionalRX,
        "FractionalRY": FractionalRY,
        "FractionalRZ": FractionalRZ,
        "FractionalPhase": FractionalPhase,
        "FractionalCRX": FractionalCRX,
        "FractionalCRY": FractionalCRY,
        "FractionalCRZ": FractionalCRZ,
        "FractionalRXX": FractionalRXX,
        "FractionalRYY": FractionalRYY,
        "FractionalRZZ": FractionalRZZ,
        "FractionalZXZ": FractionalZXZ,
    }
    if class_name not in _registry:
        raise ValueError(f"Unknown fractional gate class: {class_name}")
    return _registry[class_name](theta)


# ---------------------------------------------------------------------------
# Parametric Gate Library
# ---------------------------------------------------------------------------

class ParametricGateLibrary:
    """Utility for managing and querying fractional gate operations.

    Provides a centralized registry for fractional gate creation,
    decomposition, and hardware-targeted optimization.

    Examples
    --------
    >>> lib = ParametricGateLibrary()
    >>> lib.supported_gates()
    ['FractionalRX', 'FractionalRY', ...]
    >>> gate = lib.get_gate('FractionalRX', math.pi / 4)
    """

    _GATE_CLASSES: Dict[str, type] = {
        "FractionalRX": FractionalRX,
        "FractionalRY": FractionalRY,
        "FractionalRZ": FractionalRZ,
        "FractionalPhase": FractionalPhase,
        "FractionalCRX": FractionalCRX,
        "FractionalCRY": FractionalCRY,
        "FractionalCRZ": FractionalCRZ,
        "FractionalRXX": FractionalRXX,
        "FractionalRYY": FractionalRYY,
        "FractionalRZZ": FractionalRZZ,
        "FractionalZXZ": FractionalZXZ,
    }

    @classmethod
    def supported_gates(cls) -> List[str]:
        """List all supported fractional gate names.

        Returns
        -------
        List[str]
            Sorted list of supported gate names.
        """
        return sorted(cls._GATE_CLASSES.keys())

    @classmethod
    def get_gate(cls, name: str, theta: float) -> FractionalRotationGate:
        """Create a fractional gate by name.

        Parameters
        ----------
        name : str
            Gate name (e.g. 'FractionalRX').
        theta : float
            Rotation angle in radians.

        Returns
        -------
        FractionalRotationGate
            The requested fractional gate instance.

        Raises
        ------
        ValueError
            If the gate name is not recognized.
        """
        if name not in cls._GATE_CLASSES:
            raise ValueError(
                f"Unknown fractional gate '{name}'. "
                f"Available: {', '.join(cls.supported_gates())}"
            )
        return cls._GATE_CLASSES[name](theta)

    @classmethod
    def decompose_fractional(
        cls,
        gate_name: str,
        theta: float,
        method: str = "standard",
    ) -> List[dict]:
        """Decompose a fractional gate into elementary operations.

        Parameters
        ----------
        gate_name : str
            Name of the fractional gate.
        theta : float
            Rotation angle in radians.
        method : str
            Decomposition method. Currently supported: 'standard'.

        Returns
        -------
        List[dict]
            List of operation dicts, each with 'gate', 'angle', and 'type' keys.

        Raises
        ------
        ValueError
            If the gate name or method is not recognized.
        """
        if gate_name not in cls._GATE_CLASSES:
            raise ValueError(f"Unknown fractional gate: {gate_name}")
        if method != "standard":
            raise ValueError(f"Unknown decomposition method: {method}")

        # Single-qubit gates decompose to one rotation
        _single = {
            "FractionalRX", "FractionalRY", "FractionalRZ", "FractionalPhase",
        }
        _controlled = {
            "FractionalCRX", "FractionalCRY", "FractionalCRZ",
        }
        _interaction = {
            "FractionalRXX", "FractionalRYY", "FractionalRZZ", "FractionalZXZ",
        }

        ops: List[dict] = []

        if gate_name in _single:
            axis_map = {
                "FractionalRX": "x",
                "FractionalRY": "y",
                "FractionalRZ": "z",
                "FractionalPhase": "z",
            }
            axis = axis_map[gate_name]
            chain = decompose_to_rotation_chain(theta, axis)
            for gname, angle in chain:
                ops.append({"gate": gname, "angle": angle, "type": "rotation"})
            if not chain:
                ops.append({"gate": "I", "angle": 0.0, "type": "identity"})

        elif gate_name in _controlled:
            base_map = {
                "FractionalCRX": ("RX", "x"),
                "FractionalCRY": ("RY", "y"),
                "FractionalCRZ": ("RZ", "z"),
            }
            base_name, axis = base_map[gate_name]
            chain = decompose_to_rotation_chain(theta, axis)
            for gname, angle in chain:
                ops.append({"gate": f"C{gname}", "angle": angle, "type": "controlled"})
            if not chain:
                ops.append({"gate": "I", "angle": 0.0, "type": "identity"})

        elif gate_name in _interaction:
            # Two-qubit interactions decompose to their constituent rotations
            _int_map = {
                "FractionalRXX": [("RX", "x"), ("RX", "x")],
                "FractionalRYY": [("RY", "y"), ("RY", "y")],
                "FractionalRZZ": [("RZ", "z"), ("RZ", "z")],
                "FractionalZXZ": [("RZ", "z"), ("RX", "x")],
            }
            for gname, axis in _int_map[gate_name]:
                chain = decompose_to_rotation_chain(theta, axis)
                for g, angle in chain:
                    ops.append({"gate": g, "angle": angle, "type": "rotation"})
                if not chain:
                    ops.append({"gate": "I", "angle": 0.0, "type": "identity"})

        else:
            raise ValueError(f"Unknown fractional gate: {gate_name}")

        return ops

    @classmethod
    def is_fractional_compatible(cls, gate_name: str) -> bool:
        """Check if a gate name supports fractional angles.

        Parameters
        ----------
        gate_name : str
            Gate name to check.

        Returns
        -------
        bool
            True if the gate supports fractional angles.
        """
        return gate_name in cls._GATE_CLASSES

    @classmethod
    def optimize_fractional_angles(cls, circuit: QuantumCircuit) -> QuantumCircuit:
        """Optimize fractional angles in a circuit.

        Normalizes angles to [-pi, pi] and removes identity rotations.

        Parameters
        ----------
        circuit : QuantumCircuit
            Input circuit.

        Returns
        -------
        QuantumCircuit
            Optimized circuit.
        """
        return optimize_angles_forardware(circuit)
