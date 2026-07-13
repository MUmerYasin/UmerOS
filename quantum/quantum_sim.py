import numpy as np
import math
import random

class QuantumSim:
    def __init__(self, num_qubits=2):
        self.num_qubits = num_qubits
        self.state = np.zeros(2**num_qubits, dtype=np.complex128)
        self.state[0] = 1.0 # Initialize to |0...0>

    def apply_hadamard(self, target_qubit):
        # Simplified placeholder for H-gate logic
        pass 

    def measure(self):
        probabilities = np.abs(self.state)**2
        # Add slight noise to probabilities to ensure sum to 1 in edge cases
        probabilities /= probabilities.sum()
        result = np.random.choice(len(self.state), p=probabilities)
        return format(result, f'0{self.num_qubits}b')

# --- Deepseek Merged Code Below ---
class Qubit:
    """Represents a single qubit as a complex vector [alpha, beta]."""
    def __init__(self, alpha=1.0, beta=0.0):
        self.alpha = complex(alpha)
        self.beta = complex(beta)
        self.normalize()

    def normalize(self):
        norm = math.sqrt(abs(self.alpha)**2 + abs(self.beta)**2)
        if norm > 0:
            self.alpha /= norm
            self.beta /= norm

    def measure(self) -> int:
        """Collapse to |0> or |1> based on probabilities."""
        prob0 = abs(self.alpha)**2
        result = 0 if random.random() < prob0 else 1
        # Collapse state
        if result == 0:
            self.alpha, self.beta = 1.0, 0.0
        else:
            self.alpha, self.beta = 0.0, 1.0
        return result

    def apply_hadamard(self):
        """Put qubit into superposition."""
        a, b = self.alpha, self.beta
        self.alpha = (a + b) / math.sqrt(2)
        self.beta = (a - b) / math.sqrt(2)
        self.normalize()

    def apply_pauli_x(self):
        self.alpha, self.beta = self.beta, self.alpha

class QuantumTask:
    """
    Represents a task in superposition: multiple possible execution paths
    until 'observed' (scheduled).
    """
    def __init__(self, name, possible_actions):
        self.name = name
        self.actions = possible_actions  # List of (action_desc, weight)
        self.qubit = Qubit(1, 0)

    def superpose(self):
        """Put action selection into superposition."""
        total = sum(w for _, w in self.actions)
        if total > 0:
            self.qubit.apply_hadamard()
        return self

    def collapse(self) -> str:
        """Measure qubit to select an action."""
        val = self.qubit.measure()
        if len(self.actions) == 2:
            return self.actions[val][0]
        else:
            actions, weights = zip(*self.actions)
            return random.choices(actions, weights=weights)[0]

class EntanglementSync:
    """Simulate instantaneous state synchronization between two tasks."""
    def __init__(self, task1, task2):
        self.task1 = task1
        self.task2 = task2
        self.entangled = True

    def sync(self):
        """Mirror state: if task1 changes, task2 is updated instantly."""
        if self.entangled:
            if hasattr(self.task1, 'quantum_weight') and hasattr(self.task2, 'quantum_weight'):
                self.task2.quantum_weight = self.task1.quantum_weight
