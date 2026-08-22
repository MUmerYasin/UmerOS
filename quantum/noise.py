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

"""Quantum Noise Models - Depolarizing, amplitude damping, phase damping, readout error, thermal relaxation.

Provides composable noise models that can be applied to any simulator:

    from quantum.noise import NoiseModel
    noise = NoiseModel()
    noise.add_depolarizing(prob=0.01)
    noise.add_readout_error([0.95, 0.05])
    result = simulator.run(circuit, noise_model=noise)

Noise is applied per-gate after each instruction in the circuit.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence, List, Dict, Tuple
from copy import deepcopy

import numpy as np
from numpy.typing import NDArray

from .gates import Gate
from .circuit import QuantumCircuit
from .simulator import Statevector


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

class DepolarizingChannel:
    """Single-qubit depolarizing channel.

    With probability p, replaces the state with the maximally mixed state I/2.
    """

    def __init__(self, prob: float):
        self.prob = max(0.0, min(1.0, prob))

    def apply_to_state(self, state: Statevector, gate: Gate,
                       qubits: List[int], num_qubits: int) -> Statevector:
        """Apply depolarizing noise to specified qubits."""
        if self.prob < 1e-12:
            return state

        n = num_qubits
        data = state._data.copy()

        for qubit in qubits:
            if np.random.random() < self.prob:
                idx0 = qubit
                probs = np.abs(data) ** 2

                prob_zero = 0.0
                for i in range(2**n):
                    if not ((i >> (n - 1 - idx0)) & 1):
                        prob_zero += probs[i]

                alpha = 1 - self.prob
                mixed = data.copy()
                norm = np.linalg.norm(data)
                if norm > 1e-15:
                    mixed = mixed / norm

                p0 = prob_zero
                p1 = 1 - prob_zero

                new_data = np.zeros_like(data)
                for i in range(2**n):
                    bit = (i >> (n - 1 - idx0)) & 1
                    if bit == 0:
                        new_data[i] = alpha * data[i] + (1 - alpha) * math.sqrt(p0) * mixed[i]
                    else:
                        new_data[i] = alpha * data[i] + (1 - alpha) * math.sqrt(p1) * mixed[i]

                data = new_data

        return Statevector(data)

    def apply_to_density(self, rho: NDArray, gate: Gate,
                         qubits: List[int], num_qubits: int) -> NDArray:
        """Apply depolarizing channel to density matrix."""
        if self.prob < 1e-12:
            return rho

        n = num_qubits
        dim = 2**n
        result = rho.copy()

        for qubit in qubits:
            p = self.prob
            I2 = np.eye(2, dtype=np.complex128)
            X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
            Y = np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
            Z = np.array([[1, 0], [0, -1]], dtype=np.complex128)

            op = np.eye(1, dtype=np.complex128)
            for q in range(n):
                if q == qubit:
                    op = np.kron(op, I2)
                else:
                    op = np.kron(op, I2)

            eye_full = np.eye(dim, dtype=np.complex128)
            result = (1 - p) * result + p * eye_full / dim

        return result


class AmplitudeDampingChannel:
    """Single-qubit amplitude damping (T1 relaxation).

    Models energy decay from |1> to |0> with probability gamma.
    """

    def __init__(self, gamma: float):
        self.gamma = max(0.0, min(1.0, gamma))

    def get_kraus_operators(self) -> List[NDArray]:
        g = self.gamma
        K0 = np.array([[1, 0], [0, math.sqrt(1 - g)]], dtype=np.complex128)
        K1 = np.array([[0, math.sqrt(g)], [0, 0]], dtype=np.complex128)
        return [K0, K1]

    def apply_to_state(self, state: Statevector, gate: Gate,
                       qubits: List[int], num_qubits: int) -> Statevector:
        if self.gamma < 1e-12:
            return state

        n = num_qubits
        data = state._data.copy()

        for qubit in qubits:
            new_data = np.zeros_like(data)
            g = self.gamma

            for i in range(2**n):
                bit = (i >> (n - 1 - qubit)) & 1
                j_zero = i & ~(1 << (n - 1 - qubit))

                if bit == 0:
                    new_data[i] += data[i]
                    new_data[j_zero] += math.sqrt(1 - g) * data[i]
                else:
                    new_data[i] += math.sqrt(1 - g) * data[i]
                    new_data[j_zero] += math.sqrt(g) * data[i]

            data = new_data

        return Statevector(data)


class PhaseDampingChannel:
    """Single-qubit phase damping (T2 dephasing).

    Models loss of quantum coherence without energy loss.
    """

    def __init__(self, gamma: float):
        self.gamma = max(0.0, min(1.0, gamma))

    def get_kraus_operators(self) -> List[NDArray]:
        g = self.gamma
        K0 = np.array([[1, 0], [0, math.sqrt(1 - g)]], dtype=np.complex128)
        K1 = np.array([[0, 0], [0, math.sqrt(g)]], dtype=np.complex128)
        return [K0, K1]

    def apply_to_state(self, state: Statevector, gate: Gate,
                       qubits: List[int], num_qubits: int) -> Statevector:
        if self.gamma < 1e-12:
            return state

        n = num_qubits
        data = state._data.copy()

        for qubit in qubits:
            new_data = data.copy()
            g = self.gamma

            for i in range(2**n):
                bit = (i >> (n - 1 - qubit)) & 1
                if bit == 1:
                    new_data[i] *= math.sqrt(1 - g)

            data = new_data

        return Statevector(data)


class BitFlipChannel:
    """Single-qubit bit flip channel."""

    def __init__(self, prob: float):
        self.prob = max(0.0, min(1.0, prob))

    def apply_to_state(self, state: Statevector, gate: Gate,
                       qubits: List[int], num_qubits: int) -> Statevector:
        if self.prob < 1e-12:
            return state

        n = num_qubits
        data = state._data.copy()

        for qubit in qubits:
            if np.random.random() < self.prob:
                new_data = data.copy()
                for i in range(2**n):
                    bit = (i >> (n - 1 - qubit)) & 1
                    j_flipped = i ^ (1 << (n - 1 - qubit))
                    new_data[i] = data[j_flipped]
                data = new_data

        return Statevector(data)


class PhaseFlipChannel:
    """Single-qubit phase flip channel."""

    def __init__(self, prob: float):
        self.prob = max(0.0, min(1.0, prob))

    def apply_to_state(self, state: Statevector, gate: Gate,
                       qubits: List[int], num_qubits: int) -> Statevector:
        if self.prob < 1e-12:
            return state

        n = num_qubits
        data = state._data.copy()

        for qubit in qubits:
            if np.random.random() < self.prob:
                new_data = data.copy()
                for i in range(2**n):
                    bit = (i >> (n - 1 - qubit)) & 1
                    if bit == 1:
                        new_data[i] = -data[i]
                data = new_data

        return Statevector(data)


class ReadoutError:
    """Readout (measurement) error.

    With probability p1, flips the measurement outcome.
    probs=[p(0->0), p(0->1)] means probability of reading 0 when true is 0,
    and probability of reading 1 when true is 0.
    """

    def __init__(self, probs: Optional[List[float]] = None):
        if probs is None:
            probs = [0.95, 0.05]
        self.probs = probs

    def apply_to_counts(self, counts: Dict[str, int], num_qubits: int) -> Dict[str, int]:
        """Apply readout error to measurement counts."""
        p = self.probs
        if abs(p[0] - 1.0) < 1e-10:
            return counts

        new_counts: Dict[str, int] = {}
        for bitstring, count in counts.items():
            for i in range(len(bitstring)):
                bit = int(bitstring[i])
                if bit == 0:
                    new_bit = 0 if np.random.random() < p[0] else 1
                else:
                    new_bit = 0 if np.random.random() < (1 - p[1]) else 1

                new_list = list(bitstring)
                new_list[i] = str(new_bit)
                new_bitstring = "".join(new_list)
                new_counts[new_bitstring] = new_counts.get(new_bitstring, 0) + count

        return new_counts


class ThermalRelaxationChannel:
    """Thermal relaxation channel combining T1 and T2.

    Models both energy relaxation (T1) and dephasing (T2).
    """

    def __init__(self, t1: float, t2: float, time: float):
        self.t1 = max(0.0, t1)
        self.t2 = max(0.0, min(t2, 2 * t1))
        self.time = max(0.0, time)

    def get_kraus_operators(self) -> List[NDArray]:
        if self.time < 1e-15 or self.t1 < 1e-15:
            return [np.eye(2, dtype=np.complex128)]

        e1 = math.exp(-self.time / self.t1)
        e2 = math.exp(-self.time / self.t2)

        p_reset = 1 - e1
        e_z = e2 / math.sqrt(1 - p_reset) if (1 - p_reset) > 1e-15 else 0

        K0 = np.array([
            [math.sqrt(1 - p_reset), 0],
            [0, e_z * math.sqrt(1 - p_reset)]
        ], dtype=np.complex128)
        K1 = np.array([
            [0, math.sqrt(p_reset * (1 + e_z) / 2)],
            [math.sqrt(p_reset * (1 - e_z) / 2), 0]
        ], dtype=np.complex128)

        return [K0, K1]

    def apply_to_state(self, state: Statevector, gate: Gate,
                       qubits: List[int], num_qubits: int) -> Statevector:
        if self.time < 1e-15:
            return state

        n = num_qubits
        kraus = self.get_kraus_operators()

        data = state._data.copy()
        new_data = np.zeros_like(data)

        for qubit in qubits:
            for K in kraus:
                for i in range(2**n):
                    bit = (i >> (n - 1 - qubit)) & 1
                    for out_bit in range(2):
                        j = i ^ (bit << (n - 1 - qubit)) | (out_bit << (n - 1 - qubit))
                        new_data[j] += K[out_bit, bit] * data[i]

            data = new_data.copy()
            new_data = np.zeros_like(data)

        return Statevector(data)


# ---------------------------------------------------------------------------
# Composite Noise Model
# ---------------------------------------------------------------------------

class NoiseModel:
    """Composable noise model that applies channels per-gate.

    Usage:
        noise = NoiseModel()
        noise.add_depolarizing(prob=0.01)
        noise.add_amplitude_damping(gamma=0.02)
        noise.add_readout_error([0.95, 0.05])

        result = simulator.run(circuit, noise_model=noise)
    """

    def __init__(self):
        self._gate_channels: List[Tuple[str, object]] = []
        self._readout_error: Optional[ReadoutError] = None
        self._custom_channels: List[object] = []

    # ---- Gate noise channels ----

    def add_depolarizing(self, prob: float, gate_filter: Optional[str] = None):
        """Add depolarizing noise to gate applications."""
        ch = DepolarizingChannel(prob)
        self._gate_channels.append((gate_filter, ch))
        return self

    def add_amplitude_damping(self, gamma: float, gate_filter: Optional[str] = None):
        """Add amplitude damping to gate applications."""
        ch = AmplitudeDampingChannel(gamma)
        self._gate_channels.append((gate_filter, ch))
        return self

    def add_phase_damping(self, gamma: float, gate_filter: Optional[str] = None):
        """Add phase damping to gate applications."""
        ch = PhaseDampingChannel(gamma)
        self._gate_channels.append((gate_filter, ch))
        return self

    def add_bit_flip(self, prob: float, gate_filter: Optional[str] = None):
        """Add bit flip noise."""
        ch = BitFlipChannel(prob)
        self._gate_channels.append((gate_filter, ch))
        return self

    def add_phase_flip(self, prob: float, gate_filter: Optional[str] = None):
        """Add phase flip noise."""
        ch = PhaseFlipChannel(prob)
        self._gate_channels.append((gate_filter, ch))
        return self

    def add_thermal_relaxation(self, t1: float, t2: float, time: float,
                               gate_filter: Optional[str] = None):
        """Add thermal relaxation noise."""
        ch = ThermalRelaxationChannel(t1, t2, time)
        self._gate_channels.append((gate_filter, ch))
        return self

    # ---- Readout noise ----

    def add_readout_error(self, probs: List[float]):
        """Add measurement readout error."""
        self._readout_error = ReadoutError(probs)
        return self

    # ---- Custom channels ----

    def add_custom_channel(self, channel: object):
        """Add a custom noise channel (must implement apply_to_state)."""
        self._custom_channels.append(channel)
        return self

    # ---- Application ----

    def apply_to_state(self, state: Statevector, gate: Gate,
                       qubits: List[int], num_qubits: int) -> Statevector:
        """Apply all noise channels to the state after a gate."""
        current = state

        for gate_filter, channel in self._gate_channels:
            if gate_filter is None or gate.name == gate_filter:
                current = channel.apply_to_state(current, gate, qubits, num_qubits)

        for ch in self._custom_channels:
            if hasattr(ch, "apply_to_state"):
                current = ch.apply_to_state(current, gate, qubits, num_qubits)

        return current

    def apply_to_density(self, rho: NDArray, gate: Gate,
                         qubits: List[int], num_qubits: int) -> NDArray:
        """Apply all noise channels to density matrix."""
        result = rho.copy()

        for gate_filter, channel in self._gate_channels:
            if gate_filter is None or gate.name == gate_filter:
                if hasattr(channel, "apply_to_density"):
                    result = channel.apply_to_density(result, gate, qubits, num_qubits)

        return result

    def apply_readout_error(self, counts: Dict[str, int], num_qubits: int) -> Dict[str, int]:
        """Apply readout error to measurement counts."""
        if self._readout_error is not None:
            return self._readout_error.apply_to_counts(counts, num_qubits)
        return counts

    def __repr__(self) -> str:
        parts = []
        for gf, ch in self._gate_channels:
            name = type(ch).__name__
            if gf:
                parts.append(f"{name}(filter={gf})")
            else:
                parts.append(name)
        if self._readout_error:
            parts.append("ReadoutError")
        return f"NoiseModel([{', '.join(parts)}])"
