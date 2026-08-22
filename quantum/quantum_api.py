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

"""Umer OS Quantum API Gateway [TODAY/FUTURE]"""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from quantum.quantum_sim import QuantumCircuitSimulator, QuantumDevice

log = logging.getLogger("UmerOS.QuantumAPI")


class QuantumAPIGateway:
    def __init__(self):
        self._backends: Dict[str, QuantumDevice] = {}
        self._default = "simulator"

    def register_backend(self, name: str, device: QuantumDevice) -> None:
        self._backends[name] = device

    def list_backends(self) -> List[str]:
        return ["simulator"] + list(self._backends.keys())

    def run(self, circuit_ops: List[Dict], backend: str = "simulator", shots: int = 1024) -> Dict[str, Any]:
        if backend == "simulator":
            return self._run_local(circuit_ops, shots)
        dev = self._backends.get(backend)
        if dev is None:
            return self._run_local(circuit_ops, shots)
        try:
            counts = dev.run_circuit(circuit_ops)
            return {"counts": counts, "backend": backend}
        except NotImplementedError:
            return self._run_local(circuit_ops, shots)

    @staticmethod
    def _required_qubits(circuit_ops: List[Dict]) -> int:
        max_index = 0
        for op in circuit_ops:
            indices = [v for k, v in op.items() if k in ("qubit", "control", "target")]
            if indices:
                max_index = max(max_index, max(indices))
        return max_index + 1

    def _run_local(self, circuit_ops: List[Dict], shots: int) -> Dict[str, Any]:
        # Size the simulator to exactly fit this circuit so entangled states
        # (e.g. Bell pairs) don't leak probability into unused extra qubits.
        n_qubits = max(1, self._required_qubits(circuit_ops))
        sim = QuantumCircuitSimulator(n_qubits=n_qubits)
        counts: Dict[str, int] = {}
        for _ in range(shots):
            sim.reset()
            for op in circuit_ops:
                gate = op.get("gate", "").upper()
                if gate == "H":
                    sim.apply_h(op["qubit"])
                elif gate == "X":
                    sim.apply_x(op["qubit"])
                elif gate == "Z":
                    sim.apply_z(op["qubit"])
                elif gate == "CNOT":
                    sim.apply_cnot(op["control"], op["target"])
            out = str(sim.measure())
            counts[out] = counts.get(out, 0) + 1
        return {"counts": counts, "backend": "simulator", "shots": shots}

    def get_noise_model(self, backend: str = "simulator") -> Dict[str, float]:
        if backend == "simulator":
            return {"depolarizing_rate": 0.01, "readout_error": 0.005, "t1_us": 100.0, "t2_us": 80.0}
        return {"depolarizing_rate": 0.05, "readout_error": 0.02, "t1_us": 50.0, "t2_us": 40.0}

    def status(self) -> dict:
        return {"default_backend": self._default, "available_backends": self.list_backends(),
                "simulator_qubits": "dynamic"}