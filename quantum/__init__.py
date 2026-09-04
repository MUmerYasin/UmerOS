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

"""UmerOS Quantum Computing Stack.

Complete quantum computing framework with:
- Core (Layer 1): gates, circuit, operators, quantum_info
- Simulation (Layer 2): statevector simulator, noise models, backends
- Optimization (Layer 3): transpiler, error mitigation
- Execution (Layer 4): primitives (Sampler, Estimator), execution, dynamic circuits
- Applications (Layer 5): algorithms, circuit library, visualization
- Specialized (Layer 6): QRNG, QKD, error correction
"""

# Simulation (Layer 2)
from .simulator import StatevectorSimulator, Statevector, MeasurementResult
from .noise import (
    NoiseModel, DepolarizingChannel, AmplitudeDampingChannel, PhaseDampingChannel,
    BitFlipChannel, PhaseFlipChannel, ReadoutError, ThermalRelaxationChannel,
)
from .backend import Backend, LocalBackend, get_backend

# Optimization (Layer 3)
from .transpiler import Transpiler, transpile, PassManager, DecomposeToBasicPass
from .error_mitigation import (
    ZeroNoiseExtrapolation, ReadoutCorrection, DynamicalDecoupling,
    PauliTwirling, ErrorMitigator,
)

from .gates import (
    Gate, I_GATE, X_GATE, Y_GATE, Z_GATE, H_GATE, S_GATE, T_GATE,
    rx, ry, rz, phase_gate, u1, u2, u3,
    CNOT_GATE, CX_GATE, CZ_GATE, CY_GATE, CH_GATE, SWAP_GATE, ISWAP_GATE,
    crx, cry, crz, cphase_gate,
    TOFFOLI_GATE, CCX_GATE, CCZ_GATE, CSWAP_GATE, FREDKIN_GATE,
    get_gate, unitary, global_phase,
)
from .circuit import (
    QuantumCircuit, QuantumRegister, ClassicalRegister, Instruction,
    from_gate_list,
)
from .operators import (
    SparsePauliOp, PauliTerm, pauli_string, identity, zero_operator, Hamiltonian,
    commutator, anticommutor, are_commuting,
    PAULI_MAP, PAULI_X, PAULI_Y, PAULI_Z, PAULI_I,
)
from .info import (
    statevector_to_density, partial_trace, partial_transpose,
    purity, fidelity, trace_distance, von_neumann_entropy, relative_entropy,
    concurrence, entanglement_of_formation, negativity,
    bell_state, ghz_state, w_state,
    KrausChannel, depolarizing_channel, amplitude_damping, phase_damping,
    bit_flip_channel, phase_flip_channel, thermal_relaxation,
)

# Execution (Layer 4) - Primitives
from .primitives import (
    SamplerV2, EstimatorV2, PrimitiveJob, PrimitiveJobStatus,
    PrimitiveV2Result, SamplerPubResult, EstimatorPubResult,
    sampler_run, estimator_run,
)

# Execution (Layer 4) - Execution Management
from .execution import (
    QuantumJob, JobStatus, Batch, Session, execute,
    ExecutionManager, ExecutionOptions, MeasurementResult,
)

# Execution (Layer 4) - Dynamic Circuits
from .dynamic_circuits import (
    DynamicCircuit, ClassicalCondition, IfElse, WhileLoop, Break,
    create_teleportation_circuit, create_superposition_with_correction,
)

# Applications (Layer 5) - Algorithms
from .algorithms import (
    shor, shor_circuit, ShorResult,
    grover, grover_circuit, grover_oracle, grover_diffuser, GroverResult,
    vqe, vqe_ansatz, VQEResult,
    qaoa, qaoa_cost_circuit, qaoa_mixer_circuit, QAOAResult,
    qpe, qpe_circuit, QPEResult,
    deutsch_jozsa, bernstein_vazirani, simon, amplitude_estimation,
)

# Applications (Layer 5) - Circuit Library
from .circuit_library import (
    bell_state_circuit, ghz_circuit, w_state_circuit,
    qft_circuit, qft_inverse_circuit, quantum_walk_circuit,
    teleportation_circuit as teleportation_circuit_lib,
    superdense_coding_circuit,
    grover_diffusion_circuit, qpe_circuit_simple,
    random_circuit, hardware_efficient_ansatz,
    bb84_sender_circuit, bb84_receiver_circuit,
    bit_flip_encode_circuit, phase_flip_encode_circuit,
    create_ghz_state, create_bell_state, create_w_state,
    create_qft, create_random_circuit,
)

# Applications (Layer 5) - Visualization
from .visualization import (
    draw_circuit, draw_circuit_compact,
    statevector_to_ascii, density_matrix_ascii, bloch_sphere_ascii,
    circuit_stats, matrix_ascii, histogram_ascii,
    draw, print_state, print_density,
    plot_histogram, plot_circuit, plot_state,
)

# Specialized (Layer 6) - QRNG
from .qrng import (
    RandomBit, RandomBytes, QRNG, QuantumEntropy,
    test_randomness_bias, test_entropy_rate,
    generate_random_bit, generate_random_int,
    generate_random_bytes, generate_random_string,
)

# Specialized (Layer 6) - QKD
from .qkd import (
    QKDResult, BB84Session, BB84, E91,
    key_reconciliation, privacy_amplification,
    run_bb84, run_e91,
)

# Specialized (Layer 6) - Error Correction
from .error_correction import (
    Syndrome, CorrectionResult, QuantumCode,
    BitFlipCode, PhaseFlipCode, ShorCode, SteaneCode, RepetitionCode,
    create_encoder,
)

# Specialized (Layer 6) - Native Gates (Hardware-specific)
from .native_gates import (
    HardwarePlatform, NativeGateSet, NativeGateSetInfo,
    NativeGate, GPI, GPI2, MS, RZ as NativeRZ,
    U1 as NativeU1, U2 as NativeU2, U3 as NativeU3,
    ISwap, ISwapDag, SQISwap, ECR, ECRDag, SX as NativeSX, SXdg as NativeSXdg,
    ZZ,
    get_native_gate_set, list_native_gates, decompose_to_native, get_native_decomposition,
)

# IonQ-specific extensions (QISKIT_RESEARCH: qiskit-ionq-report.md)
from .ionq_constants import (
    IONQ_DEFAULT_URL, IONQ_DEFAULT_URL_V4, IONQ_DEFAULT_SHOTS,
    IONQ_MAX_CIRCUITS_PER_JOB, IONQ_MAX_DEBIAS, IONQ_POLL_INTERVAL_SECONDS,
    IONQ_NATIVE_GATES, IONQ_TRANSLATABLE_GATES,
    APIJobStatus, IonQAggregationMethod, IonQErrorMitigation, IonQTargetBackend,
    IONQ_BACKEND_QUBITS,
)
from .ionq_gates import (
    IonQGate, GPIGate, GPI2Gate, MSGate, ZZGate, get_ionq_gate,
)
from .ionq_equivalence_library import (
    rz_to_gpi, ry_to_gpi, rx_to_gpi, u1_to_gpi, u3_to_gpi,
    cr_to_ms, cx_to_ms, cy_to_ms, cz_to_ms,
    add_equivalences, apply_equivalences, build_default_library,
)
from .ionq_optimizer_plugins import (
    TrappedIonOptimizerPluginBase,
    TrappedIonOptimizerPluginSimpleRules,
    TrappedIonOptimizerPluginCompactGates,
    TrappedIonOptimizerPluginCommuteGpi2ThroughMs,
    run_trapped_ion_pipeline,
)

# IBM Quantum Runtime v0.48 (QISKIT_RESEARCH: qiskit-ibm-runtime-report.md)
from .ibm_runtime_service import (
    Channel, JobState,
    OptionsV2, SamplerV2Options, EstimatorV2Options,
    UsageData, PrimitiveResult,
    RuntimeJobV2, Session, QiskitRuntimeService,
    get_runtime_service,
    RUNTIME_BASE_URL, RUNTIME_POLL_INTERVAL_SECONDS, RUNTIME_API_VERSION,
)

# Circuit-library extensions (QISKIT_RESEARCH: QISKIT_RESEARCH_REPORT.md §3.2)
from .circuit_library_extensions import (
    NLocal, RealAmplitudes, EfficientSU2, TwoLocal,
    PauliFeatureMap, IQP, bind_parameters,
)

# Pulse control
from .pulse_control import (
    WaveformType, Waveform, ConstantWaveform, GaussianWaveform,
    Frame, Pulse, PulseSequence, PulseScheduleType, PulseScheduler, SchedulingStrategy,
)

# Compiler job management
from .compiler import (
    Job, JobStatus, JobPriority,
    JobQueueManager, CloudJobManager, HybridJobManager,
)

__all__ = [
    # Gates
    "Gate", "I_GATE", "X_GATE", "Y_GATE", "Z_GATE", "H_GATE", "S_GATE", "T_GATE",
    "rx", "ry", "rz", "phase_gate", "u1", "u2", "u3",
    "CNOT_GATE", "CX_GATE", "CZ_GATE", "CY_GATE", "CH_GATE", "SWAP_GATE", "ISWAP_GATE",
    "crx", "cry", "crz", "cphase_gate",
    "TOFFOLI_GATE", "CCX_GATE", "CCZ_GATE", "CSWAP_GATE", "FREDKIN_GATE",
    "get_gate", "unitary", "global_phase",
    # Circuit
    "QuantumCircuit", "QuantumRegister", "ClassicalRegister", "Instruction",
    "from_gate_list",
    # Operators
    "SparsePauliOp", "PauliTerm", "pauli_string", "identity", "zero_operator", "Hamiltonian",
    "commutator", "anticommutor", "are_commuting",
    "PAULI_MAP", "PAULI_X", "PAULI_Y", "PAULI_Z", "PAULI_I",
    # Info
    "statevector_to_density", "partial_trace", "partial_transpose",
    "purity", "fidelity", "trace_distance", "von_neumann_entropy", "relative_entropy",
    "concurrence", "entanglement_of_formation", "negativity",
    "bell_state", "ghz_state", "w_state",
    "KrausChannel", "depolarizing_channel", "amplitude_damping", "phase_damping",
    "bit_flip_channel", "phase_flip_channel", "thermal_relaxation",
    # Simulation (Layer 2)
    "StatevectorSimulator", "Statevector", "MeasurementResult",
    "NoiseModel", "DepolarizingChannel", "AmplitudeDampingChannel", "PhaseDampingChannel",
    "BitFlipChannel", "PhaseFlipChannel", "ReadoutError", "ThermalRelaxationChannel",
    "Backend", "LocalBackend", "get_backend",
    # Optimization (Layer 3)
    "Transpiler", "transpile", "PassManager", "DecomposeToBasicPass",
    "ZeroNoiseExtrapolation", "ReadoutCorrection", "DynamicalDecoupling",
    "PauliTwirling", "ErrorMitigator",
    # Execution (Layer 4) - Primitives
    "SamplerV2", "EstimatorV2", "PrimitiveJob", "PrimitiveJobStatus",
    "PrimitiveV2Result", "SamplerPubResult", "EstimatorPubResult",
    "sampler_run", "estimator_run",
    # Execution (Layer 4) - Execution
    "QuantumJob", "JobStatus", "Batch", "Session", "execute",
    "ExecutionManager", "ExecutionOptions",
    # Execution (Layer 4) - Dynamic Circuits
    "DynamicCircuit", "ClassicalCondition", "IfElse", "WhileLoop", "Break",
    "create_teleportation_circuit", "create_superposition_with_correction",
    # Applications (Layer 5) - Algorithms
    "shor", "shor_circuit", "ShorResult",
    "grover", "grover_circuit", "grover_oracle", "grover_diffuser", "GroverResult",
    "vqe", "vqe_ansatz", "VQEResult",
    "qaoa", "qaoa_cost_circuit", "qaoa_mixer_circuit", "QAOAResult",
    "qpe", "qpe_circuit", "QPEResult",
    "deutsch_jozsa", "bernstein_vazirani", "simon", "amplitude_estimation",
    # Applications (Layer 5) - Circuit Library
    "bell_state_circuit", "ghz_circuit", "w_state_circuit",
    "qft_circuit", "qft_inverse_circuit", "quantum_walk_circuit",
    "teleportation_circuit_lib", "superdense_coding_circuit",
    "grover_diffusion_circuit", "qpe_circuit_simple",
    "random_circuit", "hardware_efficient_ansatz",
    "bb84_sender_circuit", "bb84_receiver_circuit",
    "bit_flip_encode_circuit", "phase_flip_encode_circuit",
    "create_ghz_state", "create_bell_state", "create_w_state",
    "create_qft", "create_random_circuit",
    # Applications (Layer 5) - Visualization
    "draw_circuit", "draw_circuit_compact",
    "statevector_to_ascii", "density_matrix_ascii", "bloch_sphere_ascii",
    "circuit_stats", "matrix_ascii", "histogram_ascii",
    "draw", "print_state", "print_density",
    "plot_histogram", "plot_circuit", "plot_state",
    # Specialized (Layer 6) - QRNG
    "RandomBit", "RandomBytes", "QRNG", "QuantumEntropy",
    "test_randomness_bias", "test_entropy_rate",
    "generate_random_bit", "generate_random_int",
    "generate_random_bytes", "generate_random_string",
    # Specialized (Layer 6) - QKD
    "QKDResult", "BB84Session", "BB84", "E91",
    "key_reconciliation", "privacy_amplification",
    "run_bb84", "run_e91",
    # Specialized (Layer 6) - Error Correction
    "Syndrome", "CorrectionResult", "QuantumCode",
    "BitFlipCode", "PhaseFlipCode", "ShorCode", "SteaneCode", "RepetitionCode",
    "create_encoder",
    # Native Gates (Hardware-specific)
    "HardwarePlatform", "NativeGateSet", "NativeGateSetInfo",
    "NativeGate", "GPI", "GPI2", "MS",
    "ISwap", "ISwapDag", "SQISwap", "ECR", "ECRDag", "ZZ",
    "get_native_gate_set", "list_native_gates", "decompose_to_native", "get_native_decomposition",
    # IonQ (QISKIT_RESEARCH)
    "IONQ_DEFAULT_URL", "IONQ_DEFAULT_URL_V4", "IONQ_DEFAULT_SHOTS",
    "IONQ_MAX_CIRCUITS_PER_JOB", "IONQ_MAX_DEBIAS", "IONQ_POLL_INTERVAL_SECONDS",
    "IONQ_NATIVE_GATES", "IONQ_TRANSLATABLE_GATES",
    "APIJobStatus", "IonQAggregationMethod", "IonQErrorMitigation",
    "IonQTargetBackend", "IONQ_BACKEND_QUBITS",
    "IonQGate", "GPIGate", "GPI2Gate", "MSGate", "ZZGate", "get_ionq_gate",
    "rz_to_gpi", "ry_to_gpi", "rx_to_gpi", "u1_to_gpi", "u3_to_gpi",
    "cr_to_ms", "cx_to_ms", "cy_to_ms", "cz_to_ms",
    "add_equivalences", "apply_equivalences", "build_default_library",
    "TrappedIonOptimizerPluginBase",
    "TrappedIonOptimizerPluginSimpleRules",
    "TrappedIonOptimizerPluginCompactGates",
    "TrappedIonOptimizerPluginCommuteGpi2ThroughMs",
    "run_trapped_ion_pipeline",
    # IBM Quantum Runtime v0.48
    "Channel", "JobState",
    "OptionsV2", "SamplerV2Options", "EstimatorV2Options",
    "UsageData", "PrimitiveResult",
    "RuntimeJobV2", "Session", "QiskitRuntimeService",
    "get_runtime_service",
    "RUNTIME_BASE_URL", "RUNTIME_POLL_INTERVAL_SECONDS", "RUNTIME_API_VERSION",
    # Circuit library extensions
    "NLocal", "RealAmplitudes", "EfficientSU2", "TwoLocal",
    "PauliFeatureMap", "IQP", "bind_parameters",
    # Pulse control
    "WaveformType", "Waveform", "ConstantWaveform", "GaussianWaveform",
    "Frame", "Pulse", "PulseSequence", "PulseScheduleType",
    "PulseScheduler", "SchedulingStrategy",
    # Compiler job management
    "Job", "JobStatus", "JobPriority",
    "JobQueueManager", "CloudJobManager", "HybridJobManager",
]


def _selftest() -> bool:
    """Verify every public name in ``__all__`` is importable from this package."""
    import importlib as _il
    import sys as _sys
    pkg = _il.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(
            f"{__name__} selftest FAIL: missing {missing}",
            file=_sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
