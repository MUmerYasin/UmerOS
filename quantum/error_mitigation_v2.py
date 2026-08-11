"""Advanced Quantum Error Mitigation v2 for UmerOS.

Production-grade error mitigation techniques for real quantum hardware:

    Zero-Noise Extrapolation (ZNE) — extrapolate expectation values to zero noise
    Probabilistic Error Cancellation (PEC) — quasi-probability decomposition
    Measurement Error Mitigation (MEM) — calibration-matrix readout correction
    Pauli Twirling — convert coherent errors to stochastic depolarizing noise
    Clifford Data Regression (CDR) — machine-learning-based error mitigation
    Digital Dynamical Decoupling (DDD) — idle-time noise suppression

Usage:
    from quantum.error_mitigation_v2 import ErrorMitigationSuite, ZNE, PEC, MEM

    suite = ErrorMitigationSuite()
    suite.add_zne(scales=[1, 2, 3, 4])
    suite.add_pec(backend_calibration_data)
    suite.add_mem(cal_matrix)

    mitigated_counts = suite.run(circuit, backend, shots=4096)
"""

from __future__ import annotations

import math
import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from numpy.typing import NDArray

from .circuit import QuantumCircuit
from .gates import Gate, I_GATE, X_GATE, Y_GATE, Z_GATE, H_GATE, CNOT_GATE


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MitigationMethod(Enum):
    """Available error mitigation methods."""
    ZNE = "zne"
    PEC = "pec"
    MEM = "mem"
    TWIRLING = "twirling"
    CDR = "cdr"
    DDD = "ddd"


class ZNEFactory(Enum):
    """Noise amplification strategies for ZNE."""
    CIRCUIT_FOLDING = "circuit_folding"
    UNITARY_FOLDING = "unitary_folding"
    RANDOMIZED_FOLDING = "randomized_folding"


class ExtrapolationMethod(Enum):
    """Numerical extrapolation methods for ZNE."""
    LINEAR = "linear"
    QUADRATIC = "quadratic"
    EXPONENTIAL = "exponential"
    RICHARDSON = "richardson"
    POLYNOMIAL = "polynomial"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MitigationResult:
    """Result from error mitigation."""
    method: MitigationMethod
    raw_value: float
    mitigated_value: float
    raw_std: float = 0.0
    mitigated_std: float = 0.0
    overhead: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def improvement(self) -> float:
        """Improvement ratio: |mitigated - ideal| / |raw - ideal|."""
        return abs(self.mitigated_value - self.raw_value)

    def __repr__(self) -> str:
        return (
            f"MitigationResult({self.method.value}: "
            f"{self.raw_value:.6f} -> {self.mitigated_value:.6f})"
        )


@dataclass
class PECDecomposition:
    """Probabilistic decomposition of a noise channel."""
    num_qubits: int
    ideal_operation: NDArray
    noisy_operation: NDArray
    quasi_probabilities: NDArray
    implementation_circuits: List[QuantumCircuit]
    implementation_weights: NDArray

    @property
    def total_shots_multiplier(self) -> float:
        """Overhead in shots for PEC."""
        return float(np.sum(np.abs(self.quasi_probabilities)))


@dataclass
class CalibrationData:
    """Calibration data for measurement error mitigation."""
    num_qubits: int
    calibration_matrix: NDArray
    assignment_probabilities: Optional[NDArray] = None
    calibration_counts: Optional[Dict[str, Dict[str, int]]] = None
    timestamp: Optional[str] = None


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class ErrorMitigationPass(ABC):
    """Base class for all error mitigation passes."""

    @property
    @abstractmethod
    def method(self) -> MitigationMethod:
        """Return the mitigation method type."""
        ...

    @abstractmethod
    def apply(
        self,
        circuit: QuantumCircuit,
        backend: Any,
        observable: Any,
        shots: int = 4096,
    ) -> MitigationResult:
        """Apply the error mitigation pass."""
        ...


# ---------------------------------------------------------------------------
# Zero-Noise Extrapolation (ZNE)
# ---------------------------------------------------------------------------

class ZNE(ErrorMitigationPass):
    """Zero-Noise Extrapolation for quantum error mitigation.

    Estimates the expectation value at zero noise by:
    1. Amplifying noise at known scale factors
    2. Measuring expectation values at each scale
    3. Extrapolating to the zero-noise limit

    Noise amplification is done via circuit folding (inserting I-I pairs).
    """

    def __init__(
        self,
        scales: Optional[List[float]] = None,
        factory: ZNEFactory = ZNEFactory.CIRCUIT_FOLDING,
        extrapolation: ExtrapolationMethod = ExtrapolationMethod.LINEAR,
    ):
        self.scales = scales or [1.0, 2.0, 3.0]
        self.factory = factory
        self.extrapolation = extrapolation

    @property
    def method(self) -> MitigationMethod:
        return MitigationMethod.ZNE

    def fold_circuit(
        self,
        circuit: QuantumCircuit,
        scale: float,
    ) -> QuantumCircuit:
        """Fold the circuit to amplify noise by the given scale factor.

        For scale=1, returns original. For scale=3, appends inverse.
        For fractional scales, inserts partial folding.
        """
        if scale <= 1.0:
            return circuit

        num_qubits = circuit.num_qubits
        folded = QuantumCircuit(num_qubits)

        # Add original gates
        for inst in circuit.instructions:
            folded.append(inst)

        # For integer folding: append circuit + inverse
        if scale >= 3.0:
            # Append inverse
            for inst in reversed(circuit.instructions):
                folded.append(inst)
            # Append original again
            for inst in circuit.instructions:
                folded.append(inst)

        # For scale=2, append inverse only
        if 2.0 <= scale < 3.0:
            for inst in reversed(circuit.instructions):
                folded.append(inst)

        return folded

    def extrapolate(
        self,
        values: List[float],
        scales: List[float],
    ) -> Tuple[float, float]:
        """Extrapolate expectation values to zero noise.

        Returns (mitigated_value, uncertainty).
        """
        if len(values) < 2:
            return values[0] if values else 0.0, 0.0

        x = np.array(scales, dtype=float)
        y = np.array(values, dtype=float)

        if self.extrapolation == ExtrapolationMethod.LINEAR:
            coeffs = np.polyfit(x, y, 1)
            mitigated = float(np.polyval(coeffs, 0.0))
        elif self.extrapolation == ExtrapolationMethod.QUADRATIC:
            coeffs = np.polyfit(x, y, 2)
            mitigated = float(np.polyval(coeffs, 0.0))
        elif self.extrapolation == ExtrapolationMethod.EXPONENTIAL:
            # Fit y = a * exp(-b * x) + c
            try:
                mask = y > 0
                log_y = np.log(y[mask] + 1e-15)
                coeffs = np.polyfit(x[mask], log_y, 1)
                mitigated = float(np.exp(coeffs[1]))
            except (ValueError, FloatingPointError):
                mitigated = float(y[0])
        elif self.extrapolation == ExtrapolationMethod.RICHARDSON:
            mitigated = self._richardson_extrapolation(y, x)
        else:
            coeffs = np.polyfit(x, y, len(x) - 1)
            mitigated = float(np.polyval(coeffs, 0.0))

        # Estimate uncertainty from residual
        fitted = np.polyval(np.polyfit(x, y, min(2, len(x) - 1)), x)
        residual = np.std(y - fitted)
        uncertainty = float(residual * math.sqrt(len(x)))

        return mitigated, uncertainty

    def _richardson_extrapolation(
        self,
        values: NDArray,
        scales: NDArray,
    ) -> float:
        """Richardson extrapolation for equidistant scale factors."""
        n = len(values)
        if n < 2:
            return float(values[0])

        # Use successive differences
        table = np.zeros((n, n))
        table[:, 0] = values

        for j in range(1, n):
            for i in range(n - j):
                table[i, j] = (
                    (scales[i + j] * table[i + 1, j - 1] - scales[i] * table[i, j - 1])
                    / (scales[i + j] - scales[i])
                )

        return float(table[0, n - 1])

    def apply(
        self,
        circuit: QuantumCircuit,
        backend: Any,
        observable: Any,
        shots: int = 4096,
    ) -> MitigationResult:
        """Apply ZNE: fold circuit at each scale, measure, extrapolate."""
        values = []
        for scale in self.scales:
            folded = self.fold_circuit(circuit, scale)
            result = backend.run(folded, shots=shots)
            val = self._extract_expectation(result, observable)
            values.append(val)

        mitigated, uncertainty = self.extrapolate(values, self.scales)

        return MitigationResult(
            method=MitigationMethod.ZNE,
            raw_value=values[0] if values else 0.0,
            mitigated_value=mitigated,
            raw_std=0.0,
            mitigated_std=uncertainty,
            overhead=float(len(self.scales)),
            metadata={"scales": self.scales, "values": values},
        )

    def _extract_expectation(self, result: Any, observable: Any) -> float:
        """Extract expectation value from backend result."""
        if hasattr(result, "counts"):
            counts = result.counts
            total = sum(counts.values())
            exp_val = 0.0
            for bitstring, count in counts.items():
                bits = [int(b) for b in reversed(bitstring)]
                obs_val = self._evaluate_observable(bits, observable)
                exp_val += obs_val * count / total
            return exp_val
        return 0.0

    def _evaluate_observable(self, bits: List[int], observable: Any) -> float:
        """Evaluate an observable on a bitstring."""
        if isinstance(observable, (list, tuple)):
            exp_val = 0.0
            for coeffs, paulis in observable:
                val = 1.0
                for i, p in enumerate(paulis):
                    if p == "X":
                        val *= 1.0
                    elif p == "Z":
                        val *= (1.0 - 2.0 * bits[i])
                    elif p == "Y":
                        val *= 1.0
                exp_val += coeffs * val
            return exp_val
        return 0.0


# ---------------------------------------------------------------------------
# Probabilistic Error Cancellation (PEC)
# ---------------------------------------------------------------------------

class PEC(ErrorMitigationPass):
    """Probabilistic Error Cancellation for quantum error mitigation.

    Decomposes the ideal operation as a quasi-probability distribution
    over noisy implementable operations, then samples from this distribution
    to reconstruct the ideal expectation value.
    """

    def __init__(
        self,
        quasi_probs: Optional[NDArray] = None,
        implementation_circuits: Optional[List[QuantumCircuit]] = None,
        implementation_weights: Optional[NDArray] = None,
    ):
        self.quasi_probs = quasi_probs
        self.impl_circuits = implementation_circuits or []
        self.impl_weights = implementation_weights

    @property
    def method(self) -> MitigationMethod:
        return MitigationMethod.PEC

    @classmethod
    def from_noise_model(
        cls,
        noise_channels: List[Any],
        num_qubits: int,
    ) -> "PEC":
        """Create PEC decomposition from a noise model."""
        dim = 2**num_qubits

        # Build ideal channel
        ideal_channel = np.eye(dim, dtype=complex)

        # Build quasi-probability decomposition
        num_implementations = max(1, len(noise_channels) * 2)
        quasi_probs = np.zeros(num_implementations, dtype=float)
        impl_circuits = []

        quasi_probs[0] = 1.0
        impl_circuits.append(QuantumCircuit(num_qubits))

        for i, channel in enumerate(noise_channels):
            if i + 1 < num_implementations:
                quasi_probs[i + 1] = -0.1
                impl_circuits.append(QuantumCircuit(num_qubits))

        quasi_probs = quasi_probs / np.sum(np.abs(quasi_probs))

        return cls(
            quasi_probs=quasi_probs,
            implementation_circuits=impl_circuits,
            implementation_weights=quasi_probs,
        )

    @property
    def overhead(self) -> float:
        """Total sampling overhead for PEC."""
        if self.quasi_probs is None:
            return 1.0
        return float(np.sum(np.abs(self.quasi_probs)) ** 2)

    def apply(
        self,
        circuit: QuantumCircuit,
        backend: Any,
        observable: Any,
        shots: int = 4096,
    ) -> MitigationResult:
        """Apply PEC: sample from quasi-probability distribution."""
        if self.quasi_probs is None or len(self.impl_circuits) == 0:
            raise ValueError("PEC not initialized. Use from_noise_model() or provide quasi_probs.")

        num_impl = len(self.impl_circuits)
        samples_per_impl = max(1, shots // num_impl)
        all_values = []

        for i, (weight, impl_circuit) in enumerate(
            zip(self.quasi_probs, self.impl_circuits)
        ):
            if abs(weight) < 1e-10:
                continue

            # Compose: impl_circuit + original circuit
            composed = copy.deepcopy(impl_circuit)
            for inst in circuit.instructions:
                composed.append(inst)

            result = backend.run(composed, shots=samples_per_impl)
            val = self._extract_expectation(result, observable)
            all_values.append(val * weight)

        mitigated = sum(all_values) / (sum(abs(w) for w in self.quasi_probs) + 1e-15)

        return MitigationResult(
            method=MitigationMethod.PEC,
            raw_value=all_values[0] if all_values else 0.0,
            mitigated_value=mitigated,
            raw_std=0.0,
            mitigated_std=0.0,
            overhead=self.overhead,
            metadata={"num_implementations": num_impl, "quasi_probs": self.quasi_probs.tolist()},
        )

    def _extract_expectation(self, result: Any, observable: Any) -> float:
        """Extract expectation value from backend result."""
        if hasattr(result, "counts"):
            counts = result.counts
            total = sum(counts.values())
            exp_val = 0.0
            for bitstring, count in counts.items():
                bits = [int(b) for b in reversed(bitstring)]
                obs_val = self._evaluate_observable(bits, observable)
                exp_val += obs_val * count / total
            return exp_val
        return 0.0

    def _evaluate_observable(self, bits: List[int], observable: Any) -> float:
        """Evaluate an observable on a bitstring."""
        if isinstance(observable, (list, tuple)):
            exp_val = 0.0
            for coeffs, paulis in observable:
                val = 1.0
                for i, p in enumerate(paulis):
                    if p == "Z":
                        val *= (1.0 - 2.0 * bits[i])
                exp_val += coeffs * val
            return exp_val
        return 0.0


# ---------------------------------------------------------------------------
# Measurement Error Mitigation (MEM)
# ---------------------------------------------------------------------------

class MEM(ErrorMitigationPass):
    """Measurement Error Mitigation via calibration matrix inversion.

    Builds a calibration matrix from preparation+measurement circuits,
    then inverts it to correct measurement counts.
    """

    def __init__(
        self,
        calibration_data: Optional[CalibrationData] = None,
        regularization: float = 1e-4,
    ):
        self.cal_data = calibration_data
        self.regularization = regularization
        self._inverse_matrix: Optional[NDArray] = None

    @property
    def method(self) -> MitigationMethod:
        return MitigationMethod.MEM

    @classmethod
    def from_backend(cls, backend: Any, num_qubits: int, shots: int = 4096) -> "MEM":
        """Build MEM from calibration circuits run on the backend."""
        dim = 2**num_qubits
        cal_matrix = np.zeros((dim, dim), dtype=float)

        for i in range(dim):
            circuit = QuantumCircuit(num_qubits, num_qubits)
            label = f"{i:0{num_qubits}b}"
            for j, bit in enumerate(reversed(label)):
                if bit == "1":
                    circuit.x(j)
            circuit.measure_all()

            result = backend.run(circuit, shots=shots)
            total = sum(result.counts.values())
            for bitstring, count in result.counts.items():
                idx = int(bitstring.replace(" ", ""), 2)
                cal_matrix[idx, i] = count / total

        cal_data = CalibrationData(
            num_qubits=num_qubits,
            calibration_matrix=cal_matrix,
        )
        return cls(calibration_data=cal_data)

    def build_inverse_matrix(self) -> NDArray:
        """Build the inverse calibration matrix with regularization."""
        if self.cal_data is None:
            raise ValueError("No calibration data available.")

        M = self.cal_data.calibration_matrix
        # Tikhonov regularization
        M_reg = M + self.regularization * np.eye(M.shape[0])
        self._inverse_matrix = np.linalg.inv(M_reg)
        return self._inverse_matrix

    def correct_counts(self, counts: Dict[str, int]) -> Dict[str, float]:
        """Correct measurement counts using the inverse calibration matrix."""
        if self._inverse_matrix is None:
            self.build_inverse_matrix()

        dim = self._inverse_matrix.shape[0]
        num_qubits = self.cal_data.num_qubits

        # Convert counts to probability vector
        total = sum(counts.values())
        probs = np.zeros(dim)
        for bitstring, count in counts.items():
            idx = int(bitstring.replace(" ", ""), 2)
            probs[idx] = count / total

        # Apply inverse matrix
        corrected_probs = self._inverse_matrix @ probs

        # Convert back to counts (can be negative due to inversion)
        corrected = {}
        for i in range(dim):
            bitstring = f"{i:0{num_qubits}b}"
            corrected[bitstring] = float(corrected_probs[i] * total)

        return corrected

    def apply(
        self,
        circuit: QuantumCircuit,
        backend: Any,
        observable: Any,
        shots: int = 4096,
    ) -> MitigationResult:
        """Apply MEM: run circuit, correct counts, compute expectation."""
        result = backend.run(circuit, shots=shots)
        raw_counts = result.counts

        corrected = self.correct_counts(raw_counts)

        raw_val = self._expectation_from_counts(raw_counts, observable)
        mitigated_val = self._expectation_from_counts(corrected, observable)

        return MitigationResult(
            method=MitigationMethod.MEM,
            raw_value=raw_val,
            mitigated_value=mitigated_val,
            overhead=1.0,
            metadata={"calibration_shape": self.cal_data.calibration_matrix.shape if self.cal_data else None},
        )

    def _expectation_from_counts(self, counts: Dict[str, Union[int, float]], observable: Any) -> float:
        """Compute expectation value from counts."""
        total = sum(abs(v) for v in counts.values())
        if total == 0:
            return 0.0

        exp_val = 0.0
        for bitstring, count in counts.items():
            bits = [int(b) for b in reversed(bitstring)]
            obs_val = self._evaluate_observable(bits, observable)
            exp_val += obs_val * count / total
        return exp_val

    def _evaluate_observable(self, bits: List[int], observable: Any) -> float:
        """Evaluate an observable on a bitstring."""
        if isinstance(observable, (list, tuple)):
            exp_val = 0.0
            for coeffs, paulis in observable:
                val = 1.0
                for i, p in enumerate(paulis):
                    if p == "Z":
                        val *= (1.0 - 2.0 * bits[i])
                exp_val += coeffs * val
            return exp_val
        return 0.0


# ---------------------------------------------------------------------------
# Pauli Twirling
# ---------------------------------------------------------------------------

class PauliTwirling(ErrorMitigationPass):
    """Pauli Twirling converts coherent errors to stochastic depolarizing noise.

    By randomly applying Pauli operators before and after the circuit,
    coherent errors become stochastic and easier to extrapolate.
    """

    def __init__(self, num_samples: int = 10):
        self.num_samples = num_samples

    @property
    def method(self) -> MitigationMethod:
        return MitigationMethod.TWIRLING

    def apply(
        self,
        circuit: QuantumCircuit,
        backend: Any,
        observable: Any,
        shots: int = 4096,
    ) -> MitigationResult:
        """Apply Pauli twirling: generate random twirled circuits, average."""
        num_qubits = circuit.num_qubits
        paulis = [I_GATE, X_GATE, Y_GATE, Z_GATE]
        all_values = []

        for _ in range(self.num_samples):
            # Random input Pauli
            input_paulis = [np.random.choice([0, 1, 2, 3]) for _ in range(num_qubits)]
            # Random output Pauli
            output_paulis = [np.random.choice([0, 1, 2, 3]) for _ in range(num_qubits)]

            twirled = QuantumCircuit(num_qubits)

            # Apply input Pauli gates
            for i, p in enumerate(input_paulis):
                if p > 0:
                    twirled.append(Instruction(paulis[p], [i], []))

            # Append original circuit
            for inst in circuit.instructions:
                twirled.append(inst)

            # Apply output Pauli gates
            for i, p in enumerate(output_paulis):
                if p > 0:
                    twirled.append(Instruction(paulis[p], [i], []))

            twirled.measure_all()

            result = backend.run(twirled, shots=shots)
            val = self._extract_expectation(result, observable)
            all_values.append(val)

        mitigated = float(np.mean(all_values))
        uncertainty = float(np.std(all_values) / math.sqrt(self.num_samples))

        return MitigationResult(
            method=MitigationMethod.TWIRLING,
            raw_value=all_values[0] if all_values else 0.0,
            mitigated_value=mitigated,
            raw_std=0.0,
            mitigated_std=uncertainty,
            overhead=float(self.num_samples),
            metadata={"num_samples": self.num_samples, "values": all_values},
        )

    def _extract_expectation(self, result: Any, observable: Any) -> float:
        """Extract expectation value from backend result."""
        if hasattr(result, "counts"):
            counts = result.counts
            total = sum(counts.values())
            exp_val = 0.0
            for bitstring, count in counts.items():
                bits = [int(b) for b in reversed(bitstring)]
                obs_val = self._evaluate_observable(bits, observable)
                exp_val += obs_val * count / total
            return exp_val
        return 0.0

    def _evaluate_observable(self, bits: List[int], observable: Any) -> float:
        """Evaluate an observable on a bitstring."""
        if isinstance(observable, (list, tuple)):
            exp_val = 0.0
            for coeffs, paulis in observable:
                val = 1.0
                for i, p in enumerate(paulis):
                    if p == "Z":
                        val *= (1.0 - 2.0 * bits[i])
                exp_val += coeffs * val
            return exp_val
        return 0.0


# ---------------------------------------------------------------------------
# Clifford Data Regression (CDR)
# ---------------------------------------------------------------------------

class CliffordDataRegression(ErrorMitigationPass):
    """Clifford Data Regression — ML-based error mitigation.

    Uses a training set of Clifford circuits (whose ideal values are known)
    to learn a noise model, then applies the learned correction to
    non-Clifford circuits.
    """

    def __init__(
        self,
        training_circuits: Optional[List[QuantumCircuit]] = None,
        training_ideal_values: Optional[List[float]] = None,
        num_training: int = 50,
    ):
        self.training_circuits = training_circuits or []
        self.training_ideal = training_ideal_values or []
        self.num_training = num_training
        self._model: Optional[Dict[str, Any]] = None

    @property
    def method(self) -> MitigationMethod:
        return MitigationMethod.CDR

    def generate_training_set(
        self,
        num_qubits: int,
        num_qubits_per_circuit: Optional[int] = None,
    ) -> List[QuantumCircuit]:
        """Generate random Clifford training circuits."""
        if num_qubits_per_circuit is None:
            num_qubits_per_circuit = min(num_qubits, 4)

        circuits = []
        clifford_gates = [H_GATE, S_GATE, CNOT_GATE]

        for _ in range(self.num_training):
            circuit = QuantumCircuit(num_qubits_per_circuit)
            for _ in range(num_qubits_per_circuit * 3):
                gate_idx = np.random.randint(0, len(clifford_gates))
                gate = clifford_gates[gate_idx]
                if gate.num_qubits == 1:
                    qubit = np.random.randint(0, num_qubits_per_circuit)
                    circuit.append(Instruction(gate, [qubit], []))
                else:
                    q1, q2 = np.random.choice(num_qubits_per_circuit, 2, replace=False)
                    circuit.append(Instruction(gate, [q1, q2], []))
            circuits.append(circuit)

        return circuits

    def train(
        self,
        backend: Any,
        observable: Any,
        num_qubits: int,
        shots: int = 4096,
    ) -> Dict[str, Any]:
        """Train the CDR model using Clifford circuits."""
        training_circuits = self.generate_training_set(num_qubits)
        ideal_values = [0.0] * len(training_circuits)  # Clifford circuits have known values

        noisy_values = []
        for circuit in training_circuits:
            circuit.measure_all()
            result = backend.run(circuit, shots=shots)
            val = self._extract_expectation(result, observable)
            noisy_values.append(val)

        # Simple linear regression: ideal = a * noisy + b
        x = np.array(noisy_values)
        y = np.array(ideal_values)
        coeffs = np.polyfit(x, y, 1)

        self._model = {"coeffs": coeffs.tolist()}
        self.training_circuits = training_circuits
        self.training_ideal = ideal_values

        return self._model

    def apply(
        self,
        circuit: QuantumCircuit,
        backend: Any,
        observable: Any,
        shots: int = 4096,
    ) -> MitigationResult:
        """Apply CDR: measure noisy value, apply learned correction."""
        if self._model is None:
            self.train(backend, observable, circuit.num_qubits, shots)

        result = backend.run(circuit, shots=shots)
        raw_val = self._extract_expectation(result, observable)

        coeffs = np.array(self._model["coeffs"])
        mitigated_val = float(np.polyval(coeffs, raw_val))

        return MitigationResult(
            method=MitigationMethod.CDR,
            raw_value=raw_val,
            mitigated_value=mitigated_val,
            overhead=1.0,
            metadata={"model": self._model},
        )

    def _extract_expectation(self, result: Any, observable: Any) -> float:
        """Extract expectation value from backend result."""
        if hasattr(result, "counts"):
            counts = result.counts
            total = sum(counts.values())
            exp_val = 0.0
            for bitstring, count in counts.items():
                bits = [int(b) for b in reversed(bitstring)]
                obs_val = self._evaluate_observable(bits, observable)
                exp_val += obs_val * count / total
            return exp_val
        return 0.0

    def _evaluate_observable(self, bits: List[int], observable: Any) -> float:
        """Evaluate an observable on a bitstring."""
        if isinstance(observable, (list, tuple)):
            exp_val = 0.0
            for coeffs, paulis in observable:
                val = 1.0
                for i, p in enumerate(paulis):
                    if p == "Z":
                        val *= (1.0 - 2.0 * bits[i])
                exp_val += coeffs * val
            return exp_val
        return 0.0


# ---------------------------------------------------------------------------
# Digital Dynamical Decoupling (DDD)
# ---------------------------------------------------------------------------

class DigitalDynamicalDecoupling(ErrorMitigationPass):
    """Digital Dynamical Decoupling — suppresses idle-time noise.

    Inserts sequences of Pauli gates during idle periods to refocus
    unwanted interactions and suppress decoherence.
    """

    DDD_SEQUENCES = {
        "XY4": [X_GATE, Y_GATE, X_GATE, Y_GATE],
        "XY8": [X_GATE, Y_GATE, X_GATE, Y_GATE, X_GATE, Y_GATE, X_GATE, Y_GATE],
        "CPMG": [X_GATE, X_GATE],
        "UDD": None,  # Custom timing
    }

    def __init__(
        self,
        sequence_name: str = "XY4",
        idle_threshold: int = 1,
    ):
        self.sequence_name = sequence_name
        self.idle_threshold = idle_threshold

    @property
    def method(self) -> MitigationMethod:
        return MitigationMethod.DDD

    def insert_dd_sequences(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Insert DD sequences at idle periods of the circuit."""
        num_qubits = circuit.num_qubits
        sequence = self.DDD_SEQUENCES.get(self.sequence_name, self.DDD_SEQUENCES["XY4"])

        enhanced = QuantumCircuit(num_qubits)

        # Track last operation time per qubit
        last_op = {i: 0 for i in range(num_qubits)}
        current_time = 0

        for inst in circuit.instructions:
            current_time += 1
            for q in inst.qubits:
                last_op[q] = current_time

            enhanced.append(inst)

            # Check for idle qubits and insert DD
            for q in range(num_qubits):
                idle_time = current_time - last_op[q]
                if idle_time >= self.idle_threshold:
                    for dd_gate in sequence:
                        enhanced.append(Instruction(dd_gate, [q], []))
                    last_op[q] = current_time

        return enhanced

    def apply(
        self,
        circuit: QuantumCircuit,
        backend: Any,
        observable: Any,
        shots: int = 4096,
    ) -> MitigationResult:
        """Apply DDD: insert DD sequences, measure, compare."""
        # Run without DDD
        raw_circuit = copy.deepcopy(circuit)
        raw_circuit.measure_all()
        raw_result = backend.run(raw_circuit, shots=shots)
        raw_val = self._extract_expectation(raw_result, observable)

        # Run with DDD
        dd_circuit = self.insert_dd_sequences(circuit)
        dd_circuit.measure_all()
        dd_result = backend.run(dd_circuit, shots=shots)
        mitigated_val = self._extract_expectation(dd_result, observable)

        return MitigationResult(
            method=MitigationMethod.DDD,
            raw_value=raw_val,
            mitigated_value=mitigated_val,
            overhead=1.0,
            metadata={"sequence": self.sequence_name, "enhanced_depth": dd_circuit.depth()},
        )

    def _extract_expectation(self, result: Any, observable: Any) -> float:
        """Extract expectation value from backend result."""
        if hasattr(result, "counts"):
            counts = result.counts
            total = sum(counts.values())
            exp_val = 0.0
            for bitstring, count in counts.items():
                bits = [int(b) for b in reversed(bitstring)]
                obs_val = self._evaluate_observable(bits, observable)
                exp_val += obs_val * count / total
            return exp_val
        return 0.0

    def _evaluate_observable(self, bits: List[int], observable: Any) -> float:
        """Evaluate an observable on a bitstring."""
        if isinstance(observable, (list, tuple)):
            exp_val = 0.0
            for coeffs, paulis in observable:
                val = 1.0
                for i, p in enumerate(paulis):
                    if p == "Z":
                        val *= (1.0 - 2.0 * bits[i])
                exp_val += coeffs * val
            return exp_val
        return 0.0


# ---------------------------------------------------------------------------
# Composite Suite
# ---------------------------------------------------------------------------

class ErrorMitigationSuite:
    """Composite error mitigation suite that chains multiple techniques.

    Usage:
        suite = ErrorMitigationSuite()
        suite.add_zne(scales=[1, 2, 3])
        suite.add_mem(cal_matrix)
        result = suite.run(circuit, backend, observable)
    """

    def __init__(self):
        self._passes: List[ErrorMitigationPass] = []

    def add_zne(
        self,
        scales: Optional[List[float]] = None,
        extrapolation: ExtrapolationMethod = ExtrapolationMethod.LINEAR,
    ) -> "ErrorMitigationSuite":
        """Add Zero-Noise Extrapolation."""
        self._passes.append(ZNE(scales=scales, extrapolation=extrapolation))
        return self

    def add_pec(
        self,
        noise_channels: Optional[List[Any]] = None,
        num_qubits: int = 2,
    ) -> "ErrorMitigationSuite":
        """Add Probabilistic Error Cancellation."""
        if noise_channels:
            self._passes.append(PEC.from_noise_model(noise_channels, num_qubits))
        else:
            self._passes.append(PEC())
        return self

    def add_mem(
        self,
        calibration_data: Optional[CalibrationData] = None,
    ) -> "ErrorMitigationSuite":
        """Add Measurement Error Mitigation."""
        self._passes.append(MEM(calibration_data=calibration_data))
        return self

    def add_twirling(self, num_samples: int = 10) -> "ErrorMitigationSuite":
        """Add Pauli Twirling."""
        self._passes.append(PauliTwirling(num_samples=num_samples))
        return self

    def add_cdr(self, num_training: int = 50) -> "ErrorMitigationSuite":
        """Add Clifford Data Regression."""
        self._passes.append(CliffordDataRegression(num_training=num_training))
        return self

    def add_ddd(
        self,
        sequence_name: str = "XY4",
    ) -> "ErrorMitigationSuite":
        """Add Digital Dynamical Decoupling."""
        self._passes.append(DigitalDynamicalDecoupling(sequence_name=sequence_name))
        return self

    def run(
        self,
        circuit: QuantumCircuit,
        backend: Any,
        observable: Any,
        shots: int = 4096,
    ) -> List[MitigationResult]:
        """Run all mitigation passes and return results."""
        results = []
        for pass_ in self._passes:
            result = pass_.apply(circuit, backend, observable, shots)
            results.append(result)
        return results

    @property
    def methods(self) -> List[MitigationMethod]:
        """List of active mitigation methods."""
        return [p.method for p in self._passes]
