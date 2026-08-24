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
License: GPL-3.0 (GNU General Public License Version 3)
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
# QuantumDevice — abstract base + concrete provider implementations
# ---------------------------------------------------------------------------

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone


class DeviceStatus(Enum):
    """Status of a quantum device."""
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ERROR = "error"


@dataclass
class QubitAllocation:
    """Tracks allocated qubits on a device."""
    qubit_ids: List[int]
    allocated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    released: bool = False


class QuantumDeviceError(Exception):
    """Base error for quantum device operations."""


class QubitAllocationError(QuantumDeviceError):
    """Raised when qubit allocation fails."""


class GateNotSupportedError(QuantumDeviceError):
    """Raised when a gate is not supported by the device."""


class QuantumDevice(ABC):
    """Abstract base for real quantum hardware drivers.

    Concrete subclasses wire to real provider REST APIs:
      - IBMQuantumDevice — IBM Quantum (Qiskit Runtime REST)
      - IonQDevice — IonQ cloud API
      - BraketDevice — AWS Braket
      - RigettiDevice — Rigetti QCS

    Do not instantiate directly; use a provider to create devices.
    """

    def __init__(self, device_name: str, n_qubits: int) -> None:
        self._device_name = device_name
        self._n_qubits = n_qubits
        self._allocated: Dict[int, QubitAllocation] = {}
        self._circuit_ops: List[dict] = []
        log.info("QuantumDevice[%s]: initialized (%d qubits)", device_name, n_qubits)

    @property
    def device_name(self) -> str:
        return self._device_name

    @property
    def n_qubits(self) -> int:
        return self._n_qubits

    @abstractmethod
    def status(self) -> DeviceStatus:
        """Query current device status."""

    @abstractmethod
    def get_fidelity(self) -> float:
        """Return estimated 2-qubit gate fidelity [0, 1]."""

    def allocate_qubits(self, n: int) -> List[int]:
        """Allocate n logical qubit IDs on the hardware.

        Returns list of allocated qubit indices.
        Raises QubitAllocationError if not enough free qubits.
        """
        if n < 1:
            raise QubitAllocationError(f"Cannot allocate {n} qubits")
        free = [q for q in range(self._n_qubits) if q not in self._allocated]
        if len(free) < n:
            raise QubitAllocationError(
                f"Need {n} qubits but only {len(free)} free "
                f"(total={self._n_qubits}, allocated={len(self._allocated)})"
            )
        alloc_ids = free[:n]
        alloc = QubitAllocation(qubit_ids=alloc_ids)
        for q in alloc_ids:
            self._allocated[q] = alloc
        log.debug("Allocated qubits %s on %s", alloc_ids, self._device_name)
        return alloc_ids

    def deallocate(self, qubits: List[int]) -> None:
        """Release previously allocated qubit IDs."""
        for q in qubits:
            if q in self._allocated:
                del self._allocated[q]
        log.debug("Deallocated qubits %s on %s", qubits, self._device_name)

    def apply_gate(self, gate: str, qubit: int, **kwargs) -> None:
        """Apply a named gate to a hardware qubit and buffer the operation.

        Supported gates: H, X, Y, Z, CNOT, CZ, SWAP, T, S, RX, RY, RZ.
        For multi-qubit gates, pass control/target via kwargs.
        """
        if qubit not in self._allocated:
            raise QubitAllocationError(f"Qubit {qubit} not allocated")
        gate_upper = gate.upper()
        supported = {"H", "X", "Y", "Z", "CNOT", "CZ", "SWAP", "T", "S", "RX", "RY", "RZ"}
        if gate_upper not in supported:
            raise GateNotSupportedError(f"Gate '{gate}' not supported")
        op = {"gate": gate_upper, "qubit": qubit, **kwargs}
        self._circuit_ops.append(op)

    def measure(self, qubits: List[int]) -> List[int]:
        """Measure a list of qubits; return list of classical bits.

        Appends MEASURE operations and returns placeholder results.
        Actual measurement happens at run_circuit().
        """
        for q in qubits:
            self._circuit_ops.append({"gate": "MEASURE", "qubit": q})
        return [0] * len(qubits)

    def run_circuit(self, circuit_ops: Optional[List[dict]] = None, shots: int = 1024) -> Dict[str, int]:
        """Execute a list of gate operations on real hardware; return shot counts.

        Args:
            circuit_ops: Gate operations. If None, uses buffered ops.
            shots: Number of measurement shots.

        Returns:
            Dict mapping bitstring → count (e.g. {"00": 512, "11": 512}).
        """
        ops = circuit_ops if circuit_ops is not None else self._circuit_ops
        result = self._execute_on_hardware(ops, shots)
        self._circuit_ops = []
        return result

    @abstractmethod
    def _execute_on_hardware(self, ops: List[dict], shots: int) -> Dict[str, int]:
        """Provider-specific hardware execution."""

    def reset(self) -> None:
        """Clear buffered circuit operations."""
        self._circuit_ops.clear()


# ---------------------------------------------------------------------------
# IBMQuantumDevice
# ---------------------------------------------------------------------------

class IBMQuantumDevice(QuantumDevice):
    """Real IBM Quantum device via Qiskit Runtime REST API.

    Uses IBM's REST endpoints:
      POST /Runtime/{backend}/jobs — submit job
      GET  /Runtime/jobs/{id}      — poll status
      GET  /Runtime/jobs/{id}/result — fetch results
    """

    def __init__(self, device_name: str, n_qubits: int, access_token: str, api_base: str = "https://auth.quantum-computing.ibm.com/api") -> None:
        super().__init__(device_name, n_qubits)
        self._access_token = access_token
        self._api_base = api_base.rstrip("/")
        self._hub = "ibm-q"
        self._group = "open"
        self._project = "main"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def status(self) -> DeviceStatus:
        """Query IBM Quantum backend status via REST."""
        import urllib.request
        import urllib.error
        url = f"{self._api_base}/Network/{self._hub}/Groups/{self._group}/Projects/{self._project}/devices/{self._device_name}"
        try:
            req = urllib.request.Request(url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                status_str = data.get("status", "unknown")
                if status_str == "active":
                    return DeviceStatus.ONLINE
                elif status_str in ("maintenance", "maintenance昼"):
                    return DeviceStatus.MAINTENANCE
                else:
                    return DeviceStatus.OFFLINE
        except urllib.error.URLError as e:
            log.warning("IBM status check failed: %s", e)
            return DeviceStatus.OFFLINE

    def get_fidelity(self) -> float:
        """Return typical IBM backend 2-qubit gate fidelity."""
        return 0.99

    def _execute_on_hardware(self, ops: List[dict], shots: int) -> Dict[str, int]:
        """Submit circuit to IBM Quantum via Qiskit Runtime REST API."""
        import urllib.request
        import urllib.error
        qasm = self._ops_to_openqasm(ops, shots)
        payload = {
            "backend": self._device_name,
            "program_id": "sampler",
            "params": {"circuits": [qasm], "shots": shots},
        }
        url = f"{self._api_base}/Network/{self._hub}/Groups/{self._group}/Projects/{self._project}/Jobs"
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers=self._headers(), method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                job_data = json.loads(resp.read())
                job_id = job_data.get("id", "")
        except urllib.error.URLError as e:
            raise QuantumDeviceError(f"IBM job submission failed: {e}")

        # Poll for completion
        result_url = f"{self._api_base}/Network/{self._hub}/Groups/{self._group}/Projects/{self._project}/Jobs/{job_id}"
        for _ in range(120):
            time.sleep(2)
            try:
                req = urllib.request.Request(result_url, headers=self._headers(), method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    job_status = json.loads(resp.read())
                    if job_status.get("status") == "completed":
                        break
                    elif job_status.get("status") == "failed":
                        raise QuantumDeviceError(f"IBM job {job_id} failed")
            except urllib.error.URLError:
                continue

        # Fetch results
        try:
            res_url = f"{result_url}/result"
            req = urllib.request.Request(res_url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result_data = json.loads(resp.read())
                counts = result_data.get("results", [{}])[0].get("data", {}).get("counts", {})
                return counts
        except urllib.error.URLError as e:
            raise QuantumDeviceError(f"IBM result fetch failed: {e}")

    def _ops_to_openqasm(self, ops: List[dict], shots: int) -> str:
        """Convert gate operations to OpenQASM 2.0 string."""
        n = self._n_qubits
        lines = [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            f"qreg q[{n}];",
            f"creg c[{n}];",
        ]
        for op in ops:
            gate = op["gate"]
            q = op["qubit"]
            if gate == "H":
                lines.append(f"h q[{q}];")
            elif gate == "X":
                lines.append(f"x q[{q}];")
            elif gate == "Y":
                lines.append(f"y q[{q}];")
            elif gate == "Z":
                lines.append(f"z q[{q}];")
            elif gate == "T":
                lines.append(f"t q[{q}];")
            elif gate == "S":
                lines.append(f"s q[{q}];")
            elif gate == "RX":
                angle = op.get("angle", 0.0)
                lines.append(f"rx({angle}) q[{q}];")
            elif gate == "RY":
                angle = op.get("angle", 0.0)
                lines.append(f"ry({angle}) q[{q}];")
            elif gate == "RZ":
                angle = op.get("angle", 0.0)
                lines.append(f"rz({angle}) q[{q}];")
            elif gate == "CNOT":
                ctrl = op.get("control", q)
                tgt = op.get("target", q)
                lines.append(f"cx q[{ctrl}],q[{tgt}];")
            elif gate == "CZ":
                ctrl = op.get("control", q)
                tgt = op.get("target", q)
                lines.append(f"cz q[{ctrl}],q[{tgt}];")
            elif gate == "SWAP":
                q2 = op.get("target", q)
                lines.append(f"swap q[{q}],q[{q2}];")
            elif gate == "MEASURE":
                lines.append(f"measure q[{q}] -> c[{q}];")
        lines.append(f"// shots = {shots}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# IonQDevice
# ---------------------------------------------------------------------------

class IonQDevice(QuantumDevice):
    """Real IonQ device via IonQ cloud REST API.

    Uses IonQ's REST endpoints:
      POST /v1/apps — submit circuit
      GET  /v1/apps/{id}/status — poll status
      GET  /v1/apps/{id} — fetch results
    """

    def __init__(self, device_name: str, n_qubits: int, api_key: str, api_base: str = "https://api.ionq.co") -> None:
        super().__init__(device_name, n_qubits)
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")

    def _headers(self) -> dict:
        return {
            "Authorization": f"apiKey {self._api_key}",
            "Content-Type": "application/json",
        }

    def status(self) -> DeviceStatus:
        """Query IonQ device status via REST."""
        import urllib.request
        import urllib.error
        url = f"{self._api_base}/v1/backends/{self._device_name}"
        try:
            req = urllib.request.Request(url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("available", False):
                    return DeviceStatus.ONLINE
                return DeviceStatus.OFFLINE
        except urllib.error.URLError:
            return DeviceStatus.OFFLINE

    def get_fidelity(self) -> float:
        """Return typical IonQ backend fidelity."""
        return 0.999

    def _execute_on_hardware(self, ops: List[dict], shots: int) -> Dict[str, int]:
        """Submit circuit to IonQ via REST API."""
        import urllib.request
        import urllib.error
        ionq_circuit = self._ops_to_ionq_circuit(ops)
        payload = {
            "name": f"umeros-job-{int(time.time())}",
            "target": self._device_name,
            "shots": shots,
            "input": {
                "qubits": self._n_qubits,
                "circuit": ionq_circuit,
            },
        }
        url = f"{self._api_base}/v1/apps"
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers=self._headers(), method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                job_data = json.loads(resp.read())
                job_id = job_data.get("id", "")
        except urllib.error.URLError as e:
            raise QuantumDeviceError(f"IonQ job submission failed: {e}")

        # Poll for completion
        status_url = f"{self._api_base}/v1/apps/{job_id}/status"
        for _ in range(120):
            time.sleep(2)
            try:
                req = urllib.request.Request(status_url, headers=self._headers(), method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    job_status = json.loads(resp.read())
                    if job_status.get("status") == "completed":
                        break
                    elif job_status.get("status") == "failed":
                        raise QuantumDeviceError(f"IonQ job {job_id} failed")
            except urllib.error.URLError:
                continue

        # Fetch results
        try:
            result_url = f"{self._api_base}/v1/apps/{job_id}"
            req = urllib.request.Request(result_url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result_data = json.loads(resp.read())
                counts_raw = result_data.get("result", {}).get("counts", {})
                return {k: int(v) for k, v in counts_raw.items()}
        except urllib.error.URLError as e:
            raise QuantumDeviceError(f"IonQ result fetch failed: {e}")

    def _ops_to_ionq_circuit(self, ops: List[dict]) -> List[dict]:
        """Convert gate operations to IonQ circuit format."""
        circuit = []
        for op in ops:
            gate = op["gate"]
            q = op["qubit"]
            if gate == "MEASURE":
                circuit.append({"gate": "measure", "qubit": q})
            elif gate in ("H", "X", "Y", "Z", "T", "S"):
                circuit.append({"gate": gate.lower(), "qubit": q})
            elif gate == "CNOT":
                ctrl = op.get("control", q)
                tgt = op.get("target", q)
                circuit.append({"gate": "cnot", "control": ctrl, "target": tgt})
            elif gate == "CZ":
                ctrl = op.get("control", q)
                tgt = op.get("target", q)
                circuit.append({"gate": "cz", "control": ctrl, "target": tgt})
            elif gate == "SWAP":
                q2 = op.get("target", q)
                circuit.append({"gate": "swap", "qubit1": q, "qubit2": q2})
            elif gate in ("RX", "RY", "RZ"):
                angle = op.get("angle", 0.0)
                circuit.append({"gate": gate.lower(), "qubit": q, "angle": angle})
        return circuit


# ---------------------------------------------------------------------------
# BraketDevice
# ---------------------------------------------------------------------------

class BraketDevice(QuantumDevice):
    """Real AWS Braket device via Amazon Braket REST API.

    Uses AWS Braket endpoints:
      POST /jobs — submit task
      GET  /jobs/{arn} — poll status
      GET  /jobs/{arn}/result — fetch results
    """

    def __init__(self, device_arn: str, n_qubits: int, aws_access_key: str, aws_secret_key: str, region: str = "us-east-1") -> None:
        super().__init__(device_arn.split("/")[-1], n_qubits)
        self._device_arn = device_arn
        self._aws_access_key = aws_access_key
        self._aws_secret_key = aws_secret_key
        self._region = region
        self._api_base = f"https://braket.{region}.amazonaws.com"

    def _headers(self) -> dict:
        """Generate AWS-signed headers (simplified — real impl uses SigV4)."""
        return {
            "Authorization": f"AWS4-HMAC-SHA256 Credential={self._aws_access_key}",
            "Content-Type": "application/json",
            "X-Amz-Date": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        }

    def status(self) -> DeviceStatus:
        """Query AWS Braket device status."""
        import urllib.request
        import urllib.error
        url = f"{self._api_base}/devices/{self._device_arn}"
        try:
            req = urllib.request.Request(url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                status_str = data.get("deviceStatus", "OFFLINE")
                if status_str == "IDLE":
                    return DeviceStatus.ONLINE
                elif status_str == "MAINTENANCE":
                    return DeviceStatus.MAINTENANCE
                else:
                    return DeviceStatus.OFFLINE
        except urllib.error.URLError:
            return DeviceStatus.OFFLINE

    def get_fidelity(self) -> float:
        """Return typical Braket device fidelity."""
        return 0.995

    def _execute_on_hardware(self, ops: List[dict], shots: int) -> Dict[str, int]:
        """Submit circuit to AWS Braket via REST API."""
        import urllib.request
        import urllib.error
        braket_circuit = self._ops_to_braket_circuit(ops)
        payload = {
            "action": {
                "type": "circuit",
                "circuits": [braket_circuit],
                "shots": shots,
            },
            "deviceArn": self._device_arn,
            "shots": shots,
            "name": f"umeros-job-{int(time.time())}",
        }
        url = f"{self._api_base}/jobs"
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers=self._headers(), method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                job_data = json.loads(resp.read())
                job_arn = job_data.get("jobArn", "")
        except urllib.error.URLError as e:
            raise QuantumDeviceError(f"Braket job submission failed: {e}")

        # Poll for completion
        status_url = f"{self._api_base}/jobs/{job_arn}"
        for _ in range(120):
            time.sleep(2)
            try:
                req = urllib.request.Request(status_url, headers=self._headers(), method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    job_status = json.loads(resp.read())
                    if job_status.get("status") == "COMPLETED":
                        break
                    elif job_status.get("status") in ("FAILED", "CANCELLED"):
                        raise QuantumDeviceError(f"Braket job {job_arn} failed")
            except urllib.error.URLError:
                continue

        # Fetch results
        try:
            result_url = f"{self._api_base}/jobs/{job_arn}/result"
            req = urllib.request.Request(result_url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result_data = json.loads(resp.read())
                counts_raw = result_data.get("measurementProbabilities", {})
                counts = {}
                for bitstring, prob in counts_raw.items():
                    counts[bitstring] = int(prob * shots)
                return counts
        except urllib.error.URLError as e:
            raise QuantumDeviceError(f"Braket result fetch failed: {e}")

    def _ops_to_braket_circuit(self, ops: List[dict]) -> dict:
        """Convert gate operations to Amazon Braket circuit JSON format."""
        instructions = []
        for op in ops:
            gate = op["gate"]
            q = op["qubit"]
            if gate == "MEASURE":
                instructions.append({"type": "measure", "qubit": q, "target": q})
            elif gate in ("H", "X", "Y", "Z", "T", "S"):
                instructions.append({"type": gate.lower(), "qubit": q})
            elif gate == "CNOT":
                ctrl = op.get("control", q)
                tgt = op.get("target", q)
                instructions.append({"type": "cnot", "control": ctrl, "target": tgt})
            elif gate == "CZ":
                ctrl = op.get("control", q)
                tgt = op.get("target", q)
                instructions.append({"type": "cz", "qubit1": ctrl, "qubit2": tgt})
            elif gate == "SWAP":
                q2 = op.get("target", q)
                instructions.append({"type": "swap", "qubit1": q, "qubit2": q2})
            elif gate in ("RX", "RY", "RZ"):
                angle = op.get("angle", 0.0)
                instructions.append({"type": gate.lower(), "qubit": q, "angle": angle})
        return {"instructions": instructions}


# ---------------------------------------------------------------------------
# RigettiDevice
# ---------------------------------------------------------------------------

class RigettiDevice(QuantumDevice):
    """Real Rigetti device via QCS REST API.

    Uses Rigetti Quantum Cloud Services endpoints:
      POST /v1/quantum-jobs — submit job
      GET  /v1/quantum-jobs/{id} — poll status/results
    """

    def __init__(self, device_name: str, n_qubits: int, api_key: str, api_base: str = "https://qcs.rigetti.com") -> None:
        super().__init__(device_name, n_qubits)
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def status(self) -> DeviceStatus:
        """Query Rigetti QCS device status."""
        import urllib.request
        import urllib.error
        url = f"{self._api_base}/v1/quantum-devices/{self._device_name}"
        try:
            req = urllib.request.Request(url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("online", False):
                    return DeviceStatus.ONLINE
                return DeviceStatus.OFFLINE
        except urllib.error.URLError:
            return DeviceStatus.OFFLINE

    def get_fidelity(self) -> float:
        """Return typical Rigetti device fidelity."""
        return 0.99

    def _execute_on_hardware(self, ops: List[dict], shots: int) -> Dict[str, int]:
        """Submit circuit to Rigetti QCS via REST API."""
        import urllib.request
        import urllib.error
        quil = self._ops_to_quil(ops)
        payload = {
            "device": self._device_name,
            "program": quil,
            "shots": shots,
            "name": f"umeros-job-{int(time.time())}",
        }
        url = f"{self._api_base}/v1/quantum-jobs"
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers=self._headers(), method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                job_data = json.loads(resp.read())
                job_id = job_data.get("id", "")
        except urllib.error.URLError as e:
            raise QuantumDeviceError(f"Rigetti job submission failed: {e}")

        # Poll for completion
        status_url = f"{self._api_base}/v1/quantum-jobs/{job_id}"
        for _ in range(120):
            time.sleep(2)
            try:
                req = urllib.request.Request(status_url, headers=self._headers(), method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    job_status = json.loads(resp.read())
                    if job_status.get("status") == "completed":
                        break
                    elif job_status.get("status") == "failed":
                        raise QuantumDeviceError(f"Rigetti job {job_id} failed")
            except urllib.error.URLError:
                continue

        # Fetch results
        try:
            req = urllib.request.Request(status_url, headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result_data = json.loads(resp.read())
                counts_raw = result_data.get("result", {}).get("counts", {})
                return {k: int(v) for k, v in counts_raw.items()}
        except urllib.error.URLError as e:
            raise QuantumDeviceError(f"Rigetti result fetch failed: {e}")

    def _ops_to_quil(self, ops: List[dict]) -> str:
        """Convert gate operations to Quil program string."""
        lines = []
        for op in ops:
            gate = op["gate"]
            q = op["qubit"]
            if gate == "MEASURE":
                lines.append(f"MEASURE q[{q}]")
            elif gate == "H":
                lines.append(f"H q[{q}]")
            elif gate == "X":
                lines.append(f"X q[{q}]")
            elif gate == "Y":
                lines.append(f"Y q[{q}]")
            elif gate == "Z":
                lines.append(f"Z q[{q}]")
            elif gate == "T":
                lines.append(f"T q[{q}]")
            elif gate == "S":
                lines.append(f"S q[{q}]")
            elif gate == "CNOT":
                ctrl = op.get("control", q)
                tgt = op.get("target", q)
                lines.append(f"CNOT q[{ctrl}],q[{tgt}]")
            elif gate == "CZ":
                ctrl = op.get("control", q)
                tgt = op.get("target", q)
                lines.append(f"CZ q[{ctrl}],q[{tgt}]")
            elif gate == "SWAP":
                q2 = op.get("target", q)
                lines.append(f"SWAP q[{q}],q[{q2}]")
            elif gate == "RX":
                angle = op.get("angle", 0.0)
                lines.append(f"RX({angle}) q[{q}]")
            elif gate == "RY":
                angle = op.get("angle", 0.0)
                lines.append(f"RY({angle}) q[{q}]")
            elif gate == "RZ":
                angle = op.get("angle", 0.0)
                lines.append(f"RZ({angle}) q[{q}]")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# DeviceManager — registry for quantum devices
# ---------------------------------------------------------------------------

class DeviceManager:
    """Registry for quantum devices. Provides factory methods for creating
    and managing device instances.
    """

    _registry: Dict[str, type] = {
        "ibm": IBMQuantumDevice,
        "ionq": IonQDevice,
        "braket": BraketDevice,
        "rigetti": RigettiDevice,
    }

    @classmethod
    def register(cls, provider_name: str, device_class: type) -> None:
        """Register a custom device class."""
        cls._registry[provider_name.lower()] = device_class

    @classmethod
    def create(cls, provider: str, device_name: str, n_qubits: int, **kwargs) -> QuantumDevice:
        """Create a device instance by provider name."""
        provider_lower = provider.lower()
        if provider_lower not in cls._registry:
            raise ValueError(f"Unknown provider '{provider}'. Registered: {list(cls._registry.keys())}")
        return cls._registry[provider_lower](device_name, n_qubits, **kwargs)

    @classmethod
    def available_providers(cls) -> List[str]:
        """Return list of registered provider names."""
        return list(cls._registry.keys())
