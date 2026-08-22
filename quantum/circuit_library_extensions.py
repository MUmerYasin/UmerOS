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

"""Extended circuit library — NLocal, RealAmplitudes, EfficientSU2, etc."""
from __future__ import annotations

import math
from typing import Optional, List, Sequence, Set
from .circuit import QuantumCircuit, Instruction
from .gates import H_GATE, CNOT_GATE, ry, rz

__all__ = [
    "NLocal", "RealAmplitudes", "EfficientSU2", "TwoLocal",
    "PauliFeatureMap", "IQP", "bind_parameters",
]


class _Param:
    """Named parameter for circuit parameterization."""
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return self.name


class _CircuitWrapper:
    """Wrapper that exposes num_qubits and acts as a parameter container."""
    def __init__(self, num_qubits: int):
        self.num_qubits = num_qubits


class NLocal:
    def __init__(self, num_qubits: int, rotation_blocks: Optional[List] = None,
                 entanglement_blocks: Optional[List] = None,
                 entanglement: str = "full", reps: int = 1):
        self.num_qubits = num_qubits
        self._rotation_blocks = rotation_blocks or []
        self._entanglement_blocks = entanglement_blocks or ["cx"]
        self._entanglement = entanglement
        self._reps = reps
        self._params: List[_Param] = []
        self._build()

    def _build(self):
        self._params = []
        n_blocks = len(self._rotation_blocks) if self._rotation_blocks else 1
        for rep in range(self._reps + 1):
            for q in range(self.num_qubits):
                for b in range(n_blocks):
                    self._params.append(_Param(f"p{rep}_{q}_{b}"))

    @property
    def circuit(self):
        return self

    @property
    def parameters(self) -> List[_Param]:
        return list(self._params)


class RealAmplitudes(NLocal):
    def __init__(self, num_qubits: int, reps: int = 3, entanglement: str = "full"):
        super().__init__(num_qubits, rotation_blocks=["ry"], reps=reps,
                         entanglement=entanglement)


class EfficientSU2(NLocal):
    def __init__(self, num_qubits: int, reps: int = 3, entanglement: str = "full"):
        super().__init__(num_qubits, rotation_blocks=["ry", "rz"], reps=reps,
                         entanglement=entanglement)


class TwoLocal(NLocal):
    def __init__(self, num_qubits: int, rotation_blocks: Optional[List] = None,
                 entanglement_blocks: Optional[List] = None,
                 reps: int = 1, entanglement: str = "full"):
        super().__init__(num_qubits, rotation_blocks=rotation_blocks or ["ry"],
                         entanglement_blocks=entanglement_blocks or ["cx"],
                         reps=reps, entanglement=entanglement)


class PauliFeatureMap:
    def __init__(self, feature_dimension: int = 2, reps: int = 1):
        self.num_qubits = feature_dimension
        self._reps = reps
        self._params = [_Param(f"p{i}") for i in range(feature_dimension * reps)]

    @property
    def circuit(self):
        return self

    @property
    def parameters(self) -> List[_Param]:
        return list(self._params)


class IQP:
    def __init__(self, feature_dimension: int = 2, reps: int = 1):
        self.num_qubits = feature_dimension
        self._reps = reps
        self._params = [_Param(f"p{i}") for i in range(feature_dimension * reps)]

    @property
    def circuit(self):
        return self

    @property
    def parameters(self) -> List[_Param]:
        return list(self._params)


def bind_parameters(circuit, values: Sequence[float]):
    """Bind parameter values to a circuit. Returns the circuit unchanged for stub."""
    return circuit
