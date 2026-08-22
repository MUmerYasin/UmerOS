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

"""Error Correction — Quantum Error Correction codes.

Implements bit-flip, phase-flip, Shor, Steane, and other
quantum error correction codes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from .circuit import QuantumCircuit, QuantumRegister, ClassicalRegister
from .backend import LocalBackend


@dataclass
class Syndrome:
    qubit_index: int
    error_type: str
    confidence: float


@dataclass
class CorrectionResult:
    original_circuit: QuantumCircuit
    corrected_circuit: QuantumCircuit
    syndromes: List[Syndrome]
    errors_detected: int
    errors_corrected: int
    code_distance: int


class QuantumCode:
    def __init__(self, num_qubits: int, num_ancilla: int, code_distance: int):
        self.num_qubits = num_qubits
        self.num_ancilla = num_ancilla
        self.code_distance = code_distance

    def encode(self, circuit: QuantumCircuit) -> QuantumCircuit:
        raise NotImplementedError

    def syndrome_measure(self, circuit: QuantumCircuit) -> List[Syndrome]:
        raise NotImplementedError

    def correct(self, circuit: QuantumCircuit) -> CorrectionResult:
        raise NotImplementedError


class BitFlipCode(QuantumCode):
    def __init__(self):
        super().__init__(num_qubits=3, num_ancilla=2, code_distance=3)

    def encode(self, circuit: QuantumCircuit) -> QuantumCircuit:
        qr = QuantumRegister(3, "q")
        encoded = QuantumCircuit(qr)
        for inst in circuit.instructions:
            if inst.gate is not None:
                encoded.append(inst.gate, [qr[0]])
        encoded.cx(0, 1)
        encoded.cx(0, 2)
        return encoded

    def syndrome_measure(self, circuit: QuantumCircuit) -> List[Syndrome]:
        qr = QuantumRegister(3, "q")
        cr = ClassicalRegister(2, "syndrome")
        meas = QuantumCircuit(qr, cr)
        meas.cx(0, 1)
        meas.cx(0, 2)
        meas.measure(1, 0)
        meas.measure(2, 1)
        backend = LocalBackend()
        result = backend.run(meas, shots=1)
        key = list(result.counts.keys())[0]
        syndromes = []
        if key[0] == '1':
            syndromes.append(Syndrome(0, "X", 1.0))
        if key[1] == '1':
            syndromes.append(Syndrome(1, "X", 1.0))
        return syndromes

    def correct(self, circuit: QuantumCircuit) -> CorrectionResult:
        syndromes = self.syndrome_measure(circuit)
        errors_detected = len(syndromes)
        errors_corrected = 0
        qr = QuantumRegister(3, "q")
        corrected = QuantumCircuit(qr)
        for syn in syndromes:
            if syn.error_type == "X":
                corrected.x(syn.qubit_index)
                errors_corrected += 1
        return CorrectionResult(
            original_circuit=circuit, corrected_circuit=corrected,
            syndromes=syndromes, errors_detected=errors_detected,
            errors_corrected=errors_corrected, code_distance=self.code_distance,
        )


class PhaseFlipCode(QuantumCode):
    def __init__(self):
        super().__init__(num_qubits=3, num_ancilla=2, code_distance=3)

    def encode(self, circuit: QuantumCircuit) -> QuantumCircuit:
        qr = QuantumRegister(3, "q")
        encoded = QuantumCircuit(qr)
        for inst in circuit.instructions:
            if inst.gate is not None:
                encoded.append(inst.gate, [qr[0]])
        encoded.h(0)
        encoded.h(1)
        encoded.h(2)
        encoded.cx(0, 1)
        encoded.cx(0, 2)
        encoded.h(0)
        encoded.h(1)
        encoded.h(2)
        return encoded

    def syndrome_measure(self, circuit: QuantumCircuit) -> List[Syndrome]:
        qr = QuantumRegister(3, "q")
        cr = ClassicalRegister(2, "syndrome")
        meas = QuantumCircuit(qr, cr)
        meas.h(0)
        meas.h(1)
        meas.h(2)
        meas.cx(0, 1)
        meas.cx(0, 2)
        meas.measure(1, 0)
        meas.measure(2, 1)
        backend = LocalBackend()
        result = backend.run(meas, shots=1)
        key = list(result.counts.keys())[0]
        syndromes = []
        if key[0] == '1':
            syndromes.append(Syndrome(0, "Z", 1.0))
        if key[1] == '1':
            syndromes.append(Syndrome(1, "Z", 1.0))
        return syndromes

    def correct(self, circuit: QuantumCircuit) -> CorrectionResult:
        syndromes = self.syndrome_measure(circuit)
        errors_detected = len(syndromes)
        errors_corrected = 0
        qr = QuantumRegister(3, "q")
        corrected = QuantumCircuit(qr)
        for syn in syndromes:
            if syn.error_type == "Z":
                corrected.z(syn.qubit_index)
                errors_corrected += 1
        return CorrectionResult(
            original_circuit=circuit, corrected_circuit=corrected,
            syndromes=syndromes, errors_detected=errors_detected,
            errors_corrected=errors_corrected, code_distance=self.code_distance,
        )


class ShorCode(QuantumCode):
    def __init__(self):
        super().__init__(num_qubits=9, num_ancilla=8, code_distance=3)

    def encode(self, circuit: QuantumCircuit) -> QuantumCircuit:
        qr = QuantumRegister(9, "q")
        encoded = QuantumCircuit(qr)
        for inst in circuit.instructions:
            if inst.gate is not None:
                encoded.append(inst.gate, [qr[0]])
        encoded.cx(0, 3)
        encoded.cx(0, 6)
        encoded.h(0)
        encoded.h(3)
        encoded.h(6)
        encoded.cx(0, 1)
        encoded.cx(0, 2)
        encoded.cx(3, 4)
        encoded.cx(3, 5)
        encoded.cx(6, 7)
        encoded.cx(6, 8)
        return encoded

    def syndrome_measure(self, circuit: QuantumCircuit) -> List[Syndrome]:
        qr = QuantumRegister(9, "q")
        cr = ClassicalRegister(8, "syndrome")
        meas = QuantumCircuit(qr, cr)
        meas.cx(0, 1)
        meas.cx(0, 2)
        meas.cx(3, 4)
        meas.cx(3, 5)
        meas.cx(6, 7)
        meas.cx(6, 8)
        meas.measure(1, 0)
        meas.measure(2, 1)
        meas.measure(4, 2)
        meas.measure(5, 3)
        meas.measure(7, 4)
        meas.measure(8, 5)
        meas.h(0)
        meas.h(3)
        meas.h(6)
        meas.cx(0, 3)
        meas.cx(0, 6)
        meas.measure(3, 6)
        meas.measure(6, 7)
        backend = LocalBackend()
        result = backend.run(meas, shots=1)
        key = list(result.counts.keys())[0]
        syndromes = []
        qubit_map = [1, 2, 4, 5, 7, 8]
        for i in range(6):
            if key[i] == '1':
                syndromes.append(Syndrome(qubit_map[i], "X", 1.0))
        if key[6] == '1':
            syndromes.append(Syndrome(3, "Z", 1.0))
        if key[7] == '1':
            syndromes.append(Syndrome(6, "Z", 1.0))
        return syndromes

    def correct(self, circuit: QuantumCircuit) -> CorrectionResult:
        syndromes = self.syndrome_measure(circuit)
        errors_detected = len(syndromes)
        errors_corrected = 0
        qr = QuantumRegister(9, "q")
        corrected = QuantumCircuit(qr)
        for syn in syndromes:
            if syn.error_type == "X":
                corrected.x(syn.qubit_index)
                errors_corrected += 1
            elif syn.error_type == "Z":
                corrected.z(syn.qubit_index)
                errors_corrected += 1
        return CorrectionResult(
            original_circuit=circuit, corrected_circuit=corrected,
            syndromes=syndromes, errors_detected=errors_detected,
            errors_corrected=errors_corrected, code_distance=self.code_distance,
        )


class SteaneCode(QuantumCode):
    def __init__(self):
        super().__init__(num_qubits=7, num_ancilla=6, code_distance=3)

    def encode(self, circuit: QuantumCircuit) -> QuantumCircuit:
        qr = QuantumRegister(7, "q")
        encoded = QuantumCircuit(qr)
        for inst in circuit.instructions:
            if inst.gate is not None:
                encoded.append(inst.gate, [qr[0]])
        encoded.h(0)
        encoded.h(1)
        encoded.h(2)
        encoded.cx(0, 3)
        encoded.cx(0, 5)
        encoded.cx(0, 6)
        encoded.cx(1, 3)
        encoded.cx(1, 4)
        encoded.cx(1, 6)
        encoded.cx(2, 4)
        encoded.cx(2, 5)
        encoded.cx(2, 6)
        return encoded

    def syndrome_measure(self, circuit: QuantumCircuit) -> List[Syndrome]:
        qr = QuantumRegister(7, "q")
        cr = ClassicalRegister(6, "syndrome")
        meas = QuantumCircuit(qr, cr)
        meas.cx(0, 3)
        meas.cx(1, 4)
        meas.cx(2, 5)
        meas.measure(3, 0)
        meas.measure(4, 1)
        meas.measure(5, 2)
        meas.h(0)
        meas.h(1)
        meas.h(2)
        meas.cx(0, 3)
        meas.cx(1, 4)
        meas.cx(2, 5)
        meas.measure(3, 3)
        meas.measure(4, 4)
        meas.measure(5, 5)
        backend = LocalBackend()
        result = backend.run(meas, shots=1)
        key = list(result.counts.keys())[0]
        syndromes = []
        for i in range(3):
            if key[i] == '1':
                syndromes.append(Syndrome(i, "X", 1.0))
        for i in range(3, 6):
            if key[i] == '1':
                syndromes.append(Syndrome(i - 3, "Z", 1.0))
        return syndromes

    def correct(self, circuit: QuantumCircuit) -> CorrectionResult:
        syndromes = self.syndrome_measure(circuit)
        errors_detected = len(syndromes)
        errors_corrected = 0
        qr = QuantumRegister(7, "q")
        corrected = QuantumCircuit(qr)
        for syn in syndromes:
            if syn.error_type == "X":
                corrected.x(syn.qubit_index)
                errors_corrected += 1
            elif syn.error_type == "Z":
                corrected.z(syn.qubit_index)
                errors_corrected += 1
        return CorrectionResult(
            original_circuit=circuit, corrected_circuit=corrected,
            syndromes=syndromes, errors_detected=errors_detected,
            errors_corrected=errors_corrected, code_distance=self.code_distance,
        )


class RepetitionCode(QuantumCode):
    def __init__(self, num_qubits: int = 5):
        super().__init__(num_qubits=num_qubits, num_ancilla=num_qubits - 1, code_distance=num_qubits)
        self._n = num_qubits

    def encode(self, circuit: QuantumCircuit) -> QuantumCircuit:
        qr = QuantumRegister(self._n, "q")
        encoded = QuantumCircuit(qr)
        for inst in circuit.instructions:
            if inst.gate is not None:
                encoded.append(inst.gate, [qr[0]])
        for i in range(1, self._n):
            encoded.cx(0, i)
        return encoded

    def syndrome_measure(self, circuit: QuantumCircuit) -> List[Syndrome]:
        qr = QuantumRegister(self._n, "q")
        cr = ClassicalRegister(self._n - 1, "syndrome")
        meas = QuantumCircuit(qr, cr)
        for i in range(self._n - 1):
            meas.cx(i, i + 1)
            meas.measure(i + 1, i)
        backend = LocalBackend()
        result = backend.run(meas, shots=1)
        key = list(result.counts.keys())[0]
        syndromes = []
        for i, bit in enumerate(key):
            if bit == '1':
                syndromes.append(Syndrome(i, "X", 1.0))
        return syndromes

    def correct(self, circuit: QuantumCircuit) -> CorrectionResult:
        syndromes = self.syndrome_measure(circuit)
        errors_detected = len(syndromes)
        errors_corrected = 0
        qr = QuantumRegister(self._n, "q")
        corrected = QuantumCircuit(qr)
        for syn in syndromes:
            if syn.error_type == "X":
                corrected.x(syn.qubit_index)
                errors_corrected += 1
        return CorrectionResult(
            original_circuit=circuit, corrected_circuit=corrected,
            syndromes=syndromes, errors_detected=errors_detected,
            errors_corrected=errors_corrected, code_distance=self.code_distance,
        )


def create_encoder(code_name: str = "bit_flip") -> QuantumCode:
    codes = {
        "bit_flip": BitFlipCode,
        "phase_flip": PhaseFlipCode,
        "shor": ShorCode,
        "steane": SteaneCode,
    }
    if code_name not in codes:
        raise ValueError(f"Unknown code: {code_name}. Available: {list(codes.keys())}")
    return codes[code_name]()


__all__ = [
    "Syndrome", "CorrectionResult", "QuantumCode",
    "BitFlipCode", "PhaseFlipCode", "ShorCode", "SteaneCode", "RepetitionCode",
    "create_encoder",
]
