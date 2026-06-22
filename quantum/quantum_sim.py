import numpy as np

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
