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

"""
UmerOS /kernel — Quantum Simulation (prototype)  [EXPERIMENTAL]
===============================================================
Simulates qubits, superposition, entanglement, and basic gates using NumPy.

.. note:: This is a legacy prototype.  The canonical quantum simulator lives in
   ``quantum/quantum_sim.py``.
"""

from __future__ import annotations

import logging
from typing import List

import numpy as np

log = logging.getLogger("UmerOS.Kernel.QuantumSim")


class Qubit:
    """Represents a single qubit state: |psi> = alpha|0> + beta|1>."""

    def __init__(self, alpha: complex = 1 + 0j, beta: complex = 0 + 0j):
        self.alpha = alpha
        self.beta = beta
        self._normalize()

    def _normalize(self):
        norm = np.sqrt(abs(self.alpha) ** 2 + abs(self.beta) ** 2)
        if norm != 0:
            self.alpha /= norm
            self.beta /= norm

    def measure(self) -> int:
        prob0 = abs(self.alpha) ** 2
        if np.random.random() < prob0:
            self.alpha = 1 + 0j
            self.beta = 0 + 0j
            return 0
        self.alpha = 0 + 0j
        self.beta = 1 + 0j
        return 1

    def apply_gate(self, gate: np.ndarray):
        state = np.array([self.alpha, self.beta])
        new_state = gate @ state
        self.alpha, self.beta = new_state[0], new_state[1]
        self._normalize()


class QuantumSimulator:
    """Simulates a multi-qubit system and basic entanglement."""

    def __init__(self):
        self.qubits: List[Qubit] = []

    def create_qubit(self, alpha: complex = 1 + 0j, beta: complex = 0 + 0j):
        q = Qubit(alpha, beta)
        self.qubits.append(q)
        return q

    def entangle(self, q1: Qubit, q2: Qubit):
        """Simulate entanglement: measurement outcomes become perfectly correlated.

        A classical simulation enforces the correlation directly (both 0 or both
        1); true non-local correlation would require real quantum hardware.
        """
        if np.random.random() < 0.5:
            q1.alpha, q1.beta = 1, 0
            q2.alpha, q2.beta = 1, 0
        else:
            q1.alpha, q1.beta = 0, 1
            q2.alpha, q2.beta = 0, 1
