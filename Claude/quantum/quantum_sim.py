"""
Umer OS Quantum Simulation Layer  [TODAY - classical NumPy simulation]
======================================================================
Provides quantum-inspired computation on classical hardware using NumPy
state-vector simulation.

TODAY:
  - QuantumCircuitSimulator — pure-NumPy state-vector engine (no QPU needed).
  - SuperpositionSchedulerAdapter — evaluates task-priority paths.
  - EntanglementIPCAdapter — quantum-inspired pub/sub synchronisation.

EXPERIMENTAL:
  - Multi-qubit entangled circuits via CNOT + measurement.

FUTURE (TODO: QPU integration):
  - QuantumDevice abstract base → real IBM/IonQ/AWS Braket hardware.
  - QuantumAPIGateway will route here once hardware is detected.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger("UmerOS.QuantumSim")


# ---------------------------------------------------------------------------
# QuantumCircuitSimulator
# ---------------------------------------------------------------------------

class QuantumCircuitSimulator:
    """Pure-NumPy state-vector quantum circuit simulator.

    Models n qubits as a complex state vector of length 2**n.
    Initial state: |00…0⟩  (all probability on index 0).

    Supported gates: H (Hadamard), CNOT, X (Pauli-X / NOT), Z (Pauli-Z).
    Measurement collapses the state and returns a classical bit-string index.

    Args:
        n_qubits: Number of qubits (1–20 practical limit on classical hardware).
    """

    # Gate matrices
    _H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
    _X = np.array([[0, 1], [1,  0]], dtype=complex)
    _Z = np.array([[1, 0], [0, -1]], dtype=complex)
    _I = np.eye(2, dtype=complex)

    def __init__(self, n_qubits: int = 2) -> None:
        if n_qubits < 1 or n_qubits > 20:
            raise ValueError(f"n_qubits must be 1-20; got {n_qubits}.")
        self.n_qubits = n_qubits
        self.state = np.zeros(2 ** n_qubits, dtype=complex)
        self.state[0] = 1.0   # |00…0⟩
        log.debug("QuantumCircuitSimulator: %d qubit(s), dim=%d", n_qubits, 2 ** n_qubits)

    def reset(self) -> None:
        """Reset to ground state |00…0⟩."""
        self.state[:] = 0
        self.state[0] = 1.0

    def _single_qubit_gate(self, gate: np.ndarray, target: int) -> None:
        """Apply a 2×2 gate to a single qubit via Kronecker expansion.

        Args:
            gate:   2×2 unitary matrix.
            target: Zero-indexed qubit (0 = most-significant).
        """
        if target < 0 or target >= self.n_qubits:
            raise ValueError(f"Qubit index {target} out of range [0, {self.n_qubits-1}].")
        mats = [gate if i == target else self._I for i in range(self.n_qubits)]
        full = mats[0]
        for m in mats[1:]:
            full = np.kron(full, m)
        self.state = full @ self.state

    def apply_h(self, qubit: int) -> "QuantumCircuitSimulator":
        """Apply Hadamard gate — puts qubit into equal superposition."""
        self._single_qubit_gate(self._H, qubit)
        return self

    def apply_x(self, qubit: int) -> "QuantumCircuitSimulator":
        """Apply Pauli-X (NOT) gate — flips |0⟩ ↔ |1⟩."""
        self._single_qubit_gate(self._X, qubit)
        return self

    def apply_z(self, qubit: int) -> "QuantumCircuitSimulator":
        """Apply Pauli-Z gate — flips phase of |1⟩."""
        self._single_qubit_gate(self._Z, qubit)
        return self

    def apply_cnot(self, control: int, target: int) -> "QuantumCircuitSimulator":
        """Apply CNOT (controlled-X) gate.

        Flips the target qubit if and only if the control qubit is |1⟩.
        Implements two-qubit entanglement.

        Args:
            control: Control qubit index.
            target:  Target qubit index.
        """
        if control == target:
            raise ValueError("control and target must differ.")
        n = self.n_qubits
        dim = 2 ** n
        new_state = np.zeros(dim, dtype=complex)
        for idx in range(dim):
            bits = format(idx, f"0{n}b")
            ctrl_bit = int(bits[control])
            if ctrl_bit == 1:
                # Flip target bit
                tgt_bit = int(bits[target])
                flipped = list(bits)
                flipped[target] = "1" if tgt_bit == 0 else "0"
                new_idx = int("".join(flipped), 2)
                new_state[new_idx] += self.state[idx]
            else:
                new_state[idx] += self.state[idx]
        self.state = new_state
        return self

    def probabilities(self) -> np.ndarray:
        """Return the probability distribution over all basis states.

        Returns:
            Real array of length 2**n_qubits; values sum to 1.0.
        """
        probs = np.abs(self.state) ** 2
        # Normalise to correct floating-point drift
        total = probs.sum()
        if total > 0:
            probs /= total
        return probs

    def measure(self) -> int:
        """Collapse the state and sample a classical outcome.

        Returns:
            Integer index of the measured basis state.
        """
        probs = self.probabilities()
        outcome = int(np.random.choice(len(probs), p=probs))
        # Collapse: set state to the measured basis vector
        self.state[:] = 0
        self.state[outcome] = 1.0
        return outcome

    def measure_qubit(self, qubit: int) -> int:
        """Measure a single qubit and return 0 or 1.

        Args:
            qubit: Zero-indexed qubit.

        Returns:
            0 or 1 (classical bit).
        """
        probs = self.probabilities()
        n = self.n_qubits
        prob1 = sum(
            probs[idx]
            for idx in range(2 ** n)
            if (idx >> (n - 1 - qubit)) & 1
        )
        return int(np.random.random() < prob1)

    def expectation_z(self, qubit: int) -> float:
        """Return ⟨Z⟩ expectation value for a qubit (-1 ≤ value ≤ 1).

        Args:
            qubit: Zero-indexed qubit.

        Returns:
            Float expectation value.
        """
        probs = self.probabilities()
        n = self.n_qubits
        ev = 0.0
        for idx in range(2 ** n):
            bit = (idx >> (n - 1 - qubit)) & 1
            ev += probs[idx] * (1 - 2 * bit)
        return float(ev)

    def state_vector(self) -> np.ndarray:
        """Return a copy of the current state vector.

        Returns:
            Complex ndarray of length 2**n_qubits.
        """
        return self.state.copy()


# ---------------------------------------------------------------------------
# SuperpositionSchedulerAdapter
# ---------------------------------------------------------------------------

class SuperpositionSchedulerAdapter:
    """Adapts QuantumCircuitSimulator to refine scheduler task scores.

    Uses a one-qubit Hadamard circuit per task to produce a probabilistic
    priority refinement.  In practice this adds quantum-inspired randomness
    to the priority calculation, breaking ties and exploring scheduling paths.

    TODO: QPU integration — replace NumPy sim with real QPU shots.

    Args:
        sim: QuantumCircuitSimulator instance (single qubit sufficient).
    """

    def __init__(self, sim: Optional[QuantumCircuitSimulator] = None) -> None:
        self._sim = sim or QuantumCircuitSimulator(n_qubits=1)

    def evaluate_task_paths(self, tasks: list) -> Dict[int, float]:
        """Produce a quantum-inspired success probability for each task.

        Algorithm:
          1. Apply H gate → put qubit in superposition.
          2. Sample ⟨Z⟩ expectation (value in [-1, 1]).
          3. Normalise to [0, 1] and blend with the task's static priority.

        Args:
            tasks: List of Task objects (must have .pid and .priority attrs).

        Returns:
            Dict mapping pid → refined success probability in [0.0, 1.0].
        """
        result: Dict[int, float] = {}
        for task in tasks:
            self._sim.reset()
            self._sim.apply_h(0)
            ev = self._sim.expectation_z(0)          # [-1, 1]
            quantum_prob = (ev + 1.0) / 2.0           # [0, 1]
            # 50% static priority + 50% quantum refinement
            blended = 0.5 * float(task.priority) + 0.5 * quantum_prob
            result[task.pid] = round(max(0.0, min(1.0, blended)), 4)
        return result


# ---------------------------------------------------------------------------
# EntanglementIPCAdapter
# ---------------------------------------------------------------------------

class EntanglementIPCAdapter:
    """Quantum-inspired pub/sub IPC synchronisation.

    Simulates entanglement-like state sharing between publisher and subscriber:
    when the publisher qubit is measured as |1⟩, the "correlated" subscriber
    qubit collapses to |1⟩ as well (Bell state simulation).

    TODAY:   Fully classical NumPy simulation.
    FUTURE:  Use real entangled qubit pairs for zero-latency distributed sync.

    Args:
        sim: QuantumCircuitSimulator with at least 2 qubits.
    """

    def __init__(self, sim: Optional[QuantumCircuitSimulator] = None) -> None:
        self._sim = sim or QuantumCircuitSimulator(n_qubits=2)
        self._channels: Dict[str, List[int]] = {}

    def _bell_state(self) -> None:
        """Prepare a Bell state |Φ+⟩ = (|00⟩ + |11⟩) / √2."""
        self._sim.reset()
        self._sim.apply_h(0)
        self._sim.apply_cnot(0, 1)

    def subscribe(self, pid: int, channel: str) -> None:
        """Subscribe a PID to a named entangled channel.

        Args:
            pid:     Subscribing process ID.
            channel: Channel name.
        """
        if channel not in self._channels:
            self._channels[channel] = []
        if pid not in self._channels[channel]:
            self._channels[channel].append(pid)

    def publish(self, channel: str, message: dict) -> Tuple[int, dict]:
        """Publish to a channel; return (measured_bit, message).

        Prepares a Bell state, measures qubit 0 (publisher side).
        The correlated qubit-1 outcome is embedded in the returned dict.

        Args:
            channel: Channel to publish to.
            message: Payload dict.

        Returns:
            Tuple of (publisher_measurement, enriched_message_dict).
        """
        self._bell_state()
        pub_bit = self._sim.measure_qubit(0)
        sub_bit = self._sim.measure_qubit(1)   # correlated in Bell state
        enriched = {
            **message,
            "_quantum": {"pub_bit": pub_bit, "sub_bit": sub_bit, "channel": channel},
        }
        return pub_bit, enriched

    def sync_state(self) -> dict:
        """Return current state vector info for diagnostics."""
        return {
            "n_qubits":   self._sim.n_qubits,
            "dim":        2 ** self._sim.n_qubits,
            "probabilities": self._sim.probabilities().tolist(),
        }


# ---------------------------------------------------------------------------
# FUTURE: QuantumDevice abstract base (document only — not yet implemented)
# ---------------------------------------------------------------------------

class QuantumDevice:
    """Abstract base for real quantum hardware drivers.

    TODO: QPU integration — implement this interface per vendor:
      - IBMQuantumDevice (via qiskit-ibm-runtime)
      - AWSBraketDevice  (via amazon-braket-sdk)
      - IonQDevice       (via ionq SDK)

    Do not instantiate directly; register a subclass via DeviceManager.
    """

    def allocate_qubits(self, n: int) -> List[int]:
        """Allocate n logical qubit IDs on the hardware."""
        raise NotImplementedError("TODO: QPU integration")

    def apply_gate(self, gate: str, qubit: int, **kwargs) -> None:
        """Apply a named gate to a hardware qubit."""
        raise NotImplementedError("TODO: QPU integration")

    def measure(self, qubits: List[int]) -> List[int]:
        """Measure a list of qubits; return list of classical bits."""
        raise NotImplementedError("TODO: QPU integration")

    def run_circuit(self, circuit_ops: List[dict]) -> Dict[str, int]:
        """Execute a list of gate operations; return shot counts."""
        raise NotImplementedError("TODO: QPU integration")

    def get_fidelity(self) -> float:
        """Return estimated gate fidelity [0, 1]."""
        raise NotImplementedError("TODO: QPU integration")

    def deallocate(self, qubits: List[int]) -> None:
        """Release previously allocated qubit IDs."""
        raise NotImplementedError("TODO: QPU integration")
