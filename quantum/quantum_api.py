from .quantum_sim import QuantumSim

class QuantumAPI:
    def __init__(self):
        self.simulator = QuantumSim(num_qubits=4)

    def generate_random_seed(self):
        # Simulate measuring a superposition state to generate entropy
        return self.simulator.measure()
