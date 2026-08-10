"""Quantum Error Mitigation - ZNE, dynamical decoupling, readout correction.

Implements various error mitigation/suppression techniques:

    from quantum.error_mitigation import ErrorMitigator, ZeroNoiseExtrapolation

    mitigator = ErrorMitigator()
    mitigator.add_zne(scales=[1, 2, 3])
    mitigator.add_readout_correction(cal_matrix)

    corrected_result = mitigator.apply(result)
"""

from __future__ import annotations

import math
from typing import Optional, List, Dict, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from .circuit import QuantumCircuit, Instruction
from .gates import I_GATE, X_GATE, Z_GATE, H_GATE, CNOT_GATE
from .backend import JobResult


# ---------------------------------------------------------------------------
# Readout error mitigation
# ---------------------------------------------------------------------------

class ReadoutCorrection:
    """Measurement error mitigation via calibration matrix inversion.

    Builds a calibration matrix from calibration circuits and inverts
    it to correct measurement counts.
    """

    def __init__(self, num_qubits: int):
        self.num_qubits = num_qubits
        self._cal_matrix: Optional[NDArray] = None
        self._inv_matrix: Optional[NDArray] = None

    def build_calibration_matrix(self, backend, shots: int = 4096) -> NDArray:
        """Build calibration matrix from basis state measurements."""
        dim = 2**self.num_qubits
        cal_matrix = np.zeros((dim, dim), dtype=float)

        for i in range(dim):
            circuit = QuantumCircuit(self.num_qubits, self.num_qubits)
            label = f"{i:0{self.num_qubits}b}"
            for j, bit in enumerate(reversed(label)):
                if bit == "1":
                    circuit.x(j)
            circuit.measure_all()

            result = backend.run(circuit, shots=shots)
            total = sum(result.counts.values())

            for outcome, count in result.counts.items():
                col = int(outcome, 2)
                cal_matrix[col, i] = count / total

        self._cal_matrix = cal_matrix
        self._inv_matrix = np.linalg.pinv(cal_matrix)
        return cal_matrix

    def set_calibration_matrix(self, matrix: NDArray):
        """Set calibration matrix directly."""
        self._cal_matrix = matrix
        self._inv_matrix = np.linalg.pinv(matrix)

    def apply(self, counts: Dict[str, int]) -> Dict[str, int]:
        """Apply readout correction to measurement counts."""
        if self._inv_matrix is None:
            return counts

        dim = 2**self.num_qubits
        raw_vec = np.zeros(dim, dtype=float)
        total = sum(counts.values())

        for bitstring, count in counts.items():
            idx = int(bitstring, 2)
            raw_vec[idx] = count / total

        corrected_vec = self._inv_matrix @ raw_vec
        corrected_vec = np.maximum(corrected_vec, 0)
        if corrected_vec.sum() > 0:
            corrected_vec /= corrected_vec.sum()

        corrected_counts = {}
        for i in range(dim):
            if corrected_vec[i] > 1e-10:
                label = f"{i:0{self.num_qubits}b}"
                corrected_counts[label] = int(corrected_vec[i] * total)

        return corrected_counts


# ---------------------------------------------------------------------------
# Zero-Noise Extrapolation (ZNE)
# ---------------------------------------------------------------------------

@dataclass
class ZNEScale:
    """A noise scale factor and its corresponding result."""
    scale: float
    counts: Dict[str, int]
    expectation: float = 0.0


class ZeroNoiseExtrapolation:
    """Zero-Noise Extrapolation (ZNE) error mitigation.

    Runs the circuit at multiple noise levels and extrapolates
    to the zero-noise limit.
    """

    def __init__(self, scales: Optional[List[float]] = None):
        self.scales = scales or [1.0, 2.0, 3.0]

    def fold_circuit(self, circuit: QuantumCircuit, scale: float) -> QuantumCircuit:
        """Noise amplification via circuit folding.

        At scale=1: no folding (original)
        At scale=3: C -> C C-dagger C
        At scale=5: C -> C C-dagger C C-dagger C
        """
        if scale < 1.0:
            scale = 1.0
        if abs(scale - 1.0) < 1e-10:
            return circuit

        n_folds = int((scale - 1) / 2)
        result = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)

        for _ in range(n_folds):
            for inst in circuit:
                if inst.gate.name != "measure":
                    result._instructions.append(inst)
            inv = circuit.inverse()
            for inst in inv:
                if inst.gate.name != "measure":
                    result._instructions.append(inst)
        for inst in circuit:
            result._instructions.append(inst)

        return result

    def extrapolate(self, scale_results: List[ZNEScale]) -> Dict[str, float]:
        """Extrapolate to zero noise using Richardson extrapolation.

        Returns: dict mapping bitstring -> extrapolated probability
        """
        if len(scale_results) < 2:
            return {k: v for rs in scale_results for k, v in rs.counts.items()}

        all_bitstrings = set()
        for rs in scale_results:
            all_bitstrings.update(rs.counts.keys())

        extrapolated = {}
        scales = [rs.scale for rs in scale_results]

        for bs in all_bitstrings:
            values = []
            for rs in scale_results:
                total = sum(rs.counts.values())
                values.append(rs.counts.get(bs, 0) / total if total > 0 else 0.0)

            n = len(scales)
            if n == 2:
                slope = (values[1] - values[0]) / (scales[1] - scales[0])
                extrapolated[bs] = values[0] - slope * scales[0]
            else:
                coeffs = np.polyfit(scales, values, min(n - 1, 3))
                extrapolated[bs] = float(np.polyval(coeffs, 0.0))

        total = sum(max(0, v) for v in extrapolated.values())
        if total > 0:
            extrapolated = {k: max(0, v) / total for k, v in extrapolated.items()}

        return extrapolated


# ---------------------------------------------------------------------------
# Dynamical Decoupling
# ---------------------------------------------------------------------------

class DynamicalDecoupling:
    """Dynamical decoupling pulse sequences for idle qubit dephasing suppression.

    Supported sequences: XX, XY4, XY8, CPMG
    """

    class Sequence(Enum):
        XX = "xx"
        XY4 = "xy4"
        XY8 = "xy8"
        CPMG = "cpmg"

    def __init__(self, sequence_type: "DynamicalDecoupling.Sequence" = None):
        self.sequence_type = sequence_type or self.Sequence.XY4

    def get_pulses(self) -> List[Tuple[str, List[int]]]:
        """Get pulse sequence as list of (gate_name, qubit_indices) tuples."""
        if self.sequence_type == self.Sequence.XX:
            return [("x", []), ("x", [])]
        elif self.sequence_type == self.Sequence.XY4:
            return [("x", []), ("y", []), ("x", []), ("y", [])]
        elif self.sequence_type == self.Sequence.XY8:
            pulses = []
            for _ in range(4):
                pulses.append(("x", []))
                pulses.append(("y", []))
            return pulses
        elif self.sequence_type == self.Sequence.CPMG:
            pulses = []
            for _ in range(4):
                pulses.append(("x", []))
            return pulses
        return []

    def insert_into_circuit(self, circuit: QuantumCircuit,
                            idle_qubits: List[int]) -> QuantumCircuit:
        """Insert DD pulses into circuit for idle qubits.

        Inserts X-X or XY4 sequences at idle points.
        """
        if not idle_qubits:
            return circuit

        result = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
        pulses = self.get_pulses()

        for inst in circuit:
            result._instructions.append(inst)

        for qubit in idle_qubits:
            for gate_name, _ in pulses:
                if gate_name == "x":
                    result._instructions.append(Instruction(X_GATE, [qubit]))
                elif gate_name == "y":
                    from .gates import Y_GATE
                    result._instructions.append(Instruction(Y_GATE, [qubit]))

        return result


# ---------------------------------------------------------------------------
# Pauli Twirling
# ---------------------------------------------------------------------------

class PauliTwirling:
    """Pauli twirling to convert coherent errors to stochastic errors.

    Applies random Pauli gates before and after two-qubit gates.
    """

    def __init__(self, seed: Optional[int] = None):
        self._rng = np.random.RandomState(seed)

    def apply(self, circuit: QuantumCircuit, probability: float = 1.0) -> QuantumCircuit:
        """Apply Pauli twirling to two-qubit gates."""
        paulis = ["i", "x", "y", "z"]
        result = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)

        for inst in circuit:
            if len(inst.qubits) == 2 and self._rng.random() < probability:
                for q in inst.qubits:
                    p = self._rng.choice(paulis)
                    if p == "x":
                        result._instructions.append(Instruction(X_GATE, [q]))
                    elif p == "y":
                        from .gates import Y_GATE
                        result._instructions.append(Instruction(Y_GATE, [q]))
                    elif p == "z":
                        result._instructions.append(Instruction(Z_GATE, [q]))

            result._instructions.append(inst)

            if len(inst.qubits) == 2 and self._rng.random() < probability:
                for q in inst.qubits:
                    p = self._rng.choice(paulis)
                    if p == "x":
                        result._instructions.append(Instruction(X_GATE, [q]))
                    elif p == "y":
                        from .gates import Y_GATE
                        result._instructions.append(Instruction(Y_GATE, [q]))
                    elif p == "z":
                        result._instructions.append(Instruction(Z_GATE, [q]))

        return result


# ---------------------------------------------------------------------------
# Composite Error Mitigator
# ---------------------------------------------------------------------------

class ErrorMitigator:
    """Composite error mitigation combining multiple techniques.

    Usage:
        mitigator = ErrorMitigator()
        mitigator.add_readout_correction(cal_matrix)
        mitigator.add_zne(scales=[1, 2, 3])
        mitigator.add_dynamical_decoupling()

        corrected = mitigator.apply(result)
    """

    def __init__(self):
        self._readout_correction: Optional[ReadoutCorrection] = None
        self._zne: Optional[ZeroNoiseExtrapolation] = None
        self._dd: Optional[DynamicalDecoupling] = None
        self._pauli_twirling: Optional[PauliTwirling] = None
        self._custom_filters: List[Callable] = []

    def add_readout_correction(self, cal_matrix: Optional[NDArray] = None,
                               num_qubits: Optional[int] = None,
                               backend=None):
        """Add readout error mitigation."""
        n = num_qubits or 4
        rc = ReadoutCorrection(n)
        if cal_matrix is not None:
            rc.set_calibration_matrix(cal_matrix)
        elif backend is not None:
            rc.build_calibration_matrix(backend)
        self._readout_correction = rc
        return self

    def add_zne(self, scales: Optional[List[float]] = None):
        """Add zero-noise extrapolation."""
        self._zne = ZeroNoiseExtrapolation(scales)
        return self

    def add_dynamical_decoupling(self, sequence_type=None):
        """Add dynamical decoupling."""
        self._dd = DynamicalDecoupling(sequence_type)
        return self

    def add_pauli_twirling(self, seed: Optional[int] = None):
        """Add Pauli twirling."""
        self._pauli_twirling = PauliTwirling(seed)
        return self

    def add_custom_filter(self, fn: Callable):
        """Add custom mitigation function."""
        self._custom_filters.append(fn)
        return self

    def apply(self, result: JobResult) -> JobResult:
        """Apply all mitigation techniques to a result."""
        counts = result.counts.copy()

        if self._readout_correction is not None:
            counts = self._readout_correction.apply(counts)

        for fn in self._custom_filters:
            counts = fn(counts)

        return JobResult(
            job_id=result.job_id,
            status=result.status,
            counts=counts,
            num_qubits=result.num_qubits,
            shots=result.shots,
            execution_time=result.execution_time,
            metadata={**result.metadata, "error_mitigated": True}
        )

    def mitigate_circuit(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Apply circuit-level error suppression (DD, twirling)."""
        current = circuit

        if self._dd is not None:
            idle_qubits = list(range(circuit.num_qubits))
            current = self._dd.insert_into_circuit(current, idle_qubits)

        if self._pauli_twirling is not None:
            current = self._pauli_twirling.apply(current)

        return current
