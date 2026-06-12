#!/usr/bin/env python3
"""
Quantum Simulation Module for Umer OS
Simulates qubits, superposition, entanglement, and basic gates using NumPy.
"""

import numpy as np
from typing import List, Tuple

class Qubit:
    """Represents a single qubit state: |ψ> = α|0> + β|1>"""
    def __init__(self, alpha: complex = 1+0j, beta: complex = 0+0j):
        self.alpha = alpha
        self.beta = beta
        self._normalize()

    def _normalize(self):
        norm = np.sqrt(abs(self.alpha)**2 + abs(self.beta)**2)
        if norm != 0:
            self.alpha /= norm
            self.beta /= norm

    def measure(self) -> int:
        prob0 = abs(self.alpha)**2
        if np.random.random() < prob0:
            self.alpha = 1+0j
            self.beta = 0+0j
            return 0
        else:
            self.alpha = 0+0j
            self.beta = 1+0j
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

    def create_qubit(self, alpha: complex = 1+0j, beta: complex = 0+0j):
        q = Qubit(alpha, beta)
        self.qubits.append(q)
        return q

    def entangle(self, q1: Qubit, q2: Qubit):
        """
        Simulate entanglement: after this, the measurement outcomes will be
        perfectly correlated (both 0 or both 1) using a random shared state.
        """
        # Classical simulation: enforce correlation
        if np.random.random() < 0.5:
            q1.alpha, q1.beta = 1, 0
            q2.alpha, q2.beta = 1, 0
        else:
            q1.alpha, q1.beta = 0, 1
            q2.alpha, q2.beta = 0, 1
        # Note: true entanglement would require non-local correlation,
        # but this simulates the measurement correlation.

def demo():
    print("=== Quantum Simulation Demo ===")
    sim = QuantumSimulator()
    q0 = sim.create_qubit(1, 0)  # |0>
    q1 = sim.create_qubit(0, 1)  # |1>
    print(f"Before entanglement: q0={q0.alpha}|0> + {q0.beta}|1>, q1={q1.alpha}|0> + {q1.beta}|1>")
    sim.entangle(q0, q1)
    m0 = q0.measure()
    m1 = q1.measure()
    print(f"After entanglement: q0 measured {m0}, q1 measured {m1}")
    print("They are correlated (both 0 or both 1).")

if __name__ == "__main__":
    demo()