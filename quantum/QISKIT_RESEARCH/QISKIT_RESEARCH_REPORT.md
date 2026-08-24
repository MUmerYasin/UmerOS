# Qiskit — Comprehensive Research Report

---

## 1. Project Overview

**Qiskit** is an open-source quantum computing software development framework developed by IBM Quantum. It provides tools for working with quantum circuits, running them on simulators or real quantum hardware, and performing advanced quantum information processing tasks.

- **GitHub**: https://github.com/Qiskit/qiskit
- **License**: License: GPL-3.0 (GNU General Public License Version 3)
- **Language**: Python (with Rust extensions compiled via PyO3 for performance)
- **Website**: https://qiskit.org
- **Docs**: https://docs.quantum.ibm.com/api/qiskit
- **Minimum Python**: 3.9+

---

## 2. Version History & Milestones

| Date | Version | Key Change |
|------|---------|------------|
| 2017 | 0.1 | Initial release as "QISKit" (Quantum Information Science Kit) |
| 2019 | 0.7 | Qiskit Terra released; package structure established |
| 2023-08-16 | 0.44 | Final release including deprecated `opflow` and `extensions` |
| 2024-02-15 | **1.0** | Major: renamed from "Qiskit Terra" to "Qiskit"; removed `opflow` and `extensions` |
| 2024-12 | 1.3 | Continued stability improvements |
| 2025-01 | **2.0** | Performance improvements via Rust |
| 2025-09 | 2.3 | Stable release |
| 2026-04-08 | 2.4 | Newer stable release |
| 2026-07-02 | **2.5** | Latest release per roadmap |

**Note**: "Qiskit Terra" was the core library. Starting with 1.0, the project was simplified to just "Qiskit" — the name "Terra" was dropped.

---

## 3. Core Repository Structure

Top-level layout:

```
qiskit/
  README.md
  LICENSE
  pyproject.toml           # Build config (requires-python >= 3.9)
  Cargo.toml               # Rust crate for performance extensions
  src/                     # Rust source for compiled extensions
  qiskit/                  # Python package root
    circuit/               # Quantum/classical circuits, gates, registers
    transpiler/            # Circuit optimization/compilation passes
    quantum_info/          # Operators, states, channels, entropies
    primitives/            # Sampler & Estimator interfaces
    providers/             # Backend provider abstraction
    synthesis/             # Circuit synthesis algorithms
    pulse/                 # Pulse-level scheduling
    tools/                 # Visualization, monitoring utilities
    utils/                 # Utility functions
    qpy/                   # Binary serialization format
    visualization/         # Circuit, Bloch sphere, state visualization
    __init__.py            # Top-level imports (Qiskit 1.0+ public API)
  docs/                    # Documentation source
  test/                    # Test suite
  tools/                   # Build/release scripts
```

---

## 4. Core Modules

### 4.1 qiskit.circuit

The fundamental building block:
- **QuantumCircuit** — Primary class for creating quantum circuits
- **Gates** — Standard gates: CXGate, RZGate, HGate, SGate, TGate, SwapGate, etc.
- **QuantumRegister / ClassicalRegister** — Register management
- **ControlledGate** — Parametric controlled gates
- **Instruction** — Base class for all circuit instructions
- Classical expressions: Bool, Expr for classical conditions

### 4.2 qiskit.transpiler

Circuit compilation and optimization framework:
- **Passes** — Individual optimization/transformation steps
- **PassManager** — Chains of passes
- **Preset Pass Managers** — generate_preset_pass_manager() for optimization levels 0-3
- **Plugin Interface** — Custom synthesis plugins via SynthesisPluginManager
- **CouplingMap** — Hardware topology definition
- **Target** — Hardware-aware transpilation target

### 4.3 qiskit.quantum_info

Quantum information science tools:
- Statevector, DensityMatrix — Quantum state representations
- Operator, Pauli, SparsePauliOp — Operator algebra
- partial_trace, entropy, mutual_information — Entanglement measures
- process_fidelity, average_gate_fidelity — Process tomography

### 4.4 qiskit.primitives

Modern interface for executing circuits (introduced 2023+):
- **StatevectorSampler** — Exact statevector-based sampling
- **StatevectorEstimator** — Exact expectation value estimation
- BaseSamplerV2, BaseEstimatorV2 — Abstract base classes
- Backend implementations: SamplerV2, EstimatorV2 (for real hardware)

### 4.5 qiskit.providers

Backend abstraction layer:
- **BackendV2** — Modern backend interface (recommended)
- **BackendV1** — Legacy backend interface
- **JobV1** — Job representation

### 4.6 qiskit.synthesis

High-level circuit synthesis:
- synth_circuit_* — Synthesize quantum circuits
- synth_unitary — Unitary matrix decomposition
- synth_permutation — Permutation circuits

### 4.7 qiskit.pulse

Pulse-level control:
- ScheduleBlock — Pulse schedule representation
- DriveChannel, AcquisitionChannel, ControlChannel — Channel abstractions

### 4.8 qiskit.qpy

Binary serialization for circuits:
- qpy.dumps() / qpy.loads() — Serialize/deserialize
- Supports circuits, parameters, and classical expressions

### 4.9 qiskit.visualization

Drawing and plotting:
- circuit_drawer() — Text, MPL, and latex circuit diagrams
- plot_bloch_multivector() — Bloch sphere plots
- plot_state_city() — City plot of statevectors
- plot_histogram() — Measurement result histograms

---

## 5. Transpiler Deep Dive

### Architecture

The transpiler transforms quantum circuits to be hardware-compatible. It operates through **pass managers** that chain individual **passes**.

### Optimization Levels

| Level | Description |
|-------|-------------|
| 0 | No optimization; just maps to hardware layout |
| 1 | Light optimization (default) |
| 2 | Medium optimization |
| 3 | Heavy optimization (slowest, best quality) |

### Usage Example

```python
from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

# Transpile for a specific backend
pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
transpiled_qc = pm.run(qc)
```

### Key Passes

- BasisBasisTranslator — Translates gates to hardware basis
- UnitarySynthesis — Decomposes unitary matrices
- ConsolidateBlocks — Merges consecutive gates
- CNOTCancellation — Cancels adjacent CNOTs
- Optimize1qGatesDecomposition — Optimizes 1q gate decomposition
- ApplyLayout — Applies initial/final layout
- FullAncillaAllocation — Adds ancilla qubits

### Transpiler Plugins

Custom passes can be registered as SynthesisPlugin for extensibility.

---

## 6. Dependencies

### Runtime Dependencies

Core:
- **rustworkx** — Rust-based graph library (replaced networkx for performance)
- **numpy** — Numerical arrays
- **stevedore** — Plugin management (for transpiler plugins)

Optional:
- scipy, scikit-learn — For quantum info / ML features
- matplotlib — Visualization
- pydot — DOT graph output
- tweedledum — Classical logic synthesis

### Build Dependencies

- **Rust toolchain** — Compiled via PyO3 into qiskit._accelerate
- setuptools-rust — Rust build integration

---

## 7. Ecosystem Packages

The Qiskit ecosystem extends the core library:

| Package | Purpose |
|---------|---------|
| **qiskit-aer** | High-performance simulators (statevector, density matrix, stabilizer, matrix product state, extended stabilizer) |
| **qiskit-ibm-runtime** | IBM Quantum hardware access (Runtime Service, Sessions, Primitives) |
| **qiskit-experiments** | Experiment design, calibration, characterization |
| **qiskit-machine-learning** | Quantum kernels, neural networks, QNN classifiers |
| **qiskit-nature** | Chemistry, physics, and materials science applications |
| **qiskit-finance** | Portfolio optimization, risk analysis, option pricing |
| **qiskit-optimization** | Quadratic programs, Grover optimizer, minimum eigen optimizer |
| **qiskit-dynamics** | ODE/SDE solvers for quantum dynamics |
| **qiskit-circuit-library** | Parametric circuit library (pre-built circuits) |
| **qiskit-transpiler-service** | Cloud-based transpilation |
| **qiskit-serverless** | Distributed Qiskit workloads |
| **qiskit-code-assistant** | AI-powered code suggestions |
| **qiskit-ibm-provider** | Legacy IBM provider (superseded by qiskit-ibm-runtime) |

---

## 8. Code Examples

### Basic Circuit Creation and Execution

```python
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

# Create a Bell state
qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

# Get statevector
sv = Statevector.from_instruction(qc)
print(sv)
```

### Transpilation

```python
from qiskit import transpile

# Transpile circuit for a backend
transpiled = transpile(qc, backend, optimization_level=2)
```

### Using Primitives

```python
from qiskit.primitives import StatevectorSampler, StatevectorEstimator

# Sampling
sampler = StatevectorSampler()
job = sampler.run([qc])
result = job.result()

# Estimation
estimator = StatevectorEstimator()
observable = SparsePauliOp.from_list([("ZZ", 1.0)])
job = estimator.run([(qc, observable)])
result = job.result()
```

### Visualization

```python
from qiskit.visualization import circuit_drawer, plot_histogram

# Draw circuit
circuit_drawer(qc, output='mpl')

# Plot measurement results
plot_histogram(counts)
```

---

## 9. Removed Modules (Legacy)

### opflow (removed in 1.0)

Previously in qiskit.opflow:
- OperatorSum, PauliOp, MatrixOp — Operator algebra for VQE
- ListOp, ComposedOp — Operator composition
- CircuitSampler, PauliExpectation — Circuit execution patterns

**Migration**: Use qiskit.quantum_info (SparsePauliOp) and qiskit.primitives instead.

### extensions (removed in 1.0)

Previously in qiskit.extensions:
- UnitaryGate — Convert numpy unitary to gate
- HamiltonianGate — Time evolution gate
- QFT, InverseQFT — Quantum Fourier Transform

**Migration**: Use qiskit.circuit.library (UnitaryGate, QFTGate) instead.

---

## 10. Key Design Patterns

1. **Circuit-First API**: Everything builds around QuantumCircuit
2. **Pass Manager Architecture**: Transpiler uses composable pass managers
3. **Provider Abstraction**: BackendV2 enables hardware-agnostic code
4. **Primitives Pattern**: Sampler/Estimator provide standardized execution
5. **Plugin System**: stevedore-based plugin architecture for extensibility
6. **Rust Acceleration**: Performance-critical paths compiled from Rust via PyO3

---

## 11. Summary

Qiskit has evolved from a Python-only SDK (2017) to a high-performance quantum computing framework with:
- Rust-accelerated core for speed
- Clean separation of concerns (circuit, transpiler, providers, primitives)
- A rich ecosystem covering simulators, IBM hardware, and domain-specific applications
- Active development with releases every few months
- ~700+ contributors, one of the most active quantum computing projects globally
