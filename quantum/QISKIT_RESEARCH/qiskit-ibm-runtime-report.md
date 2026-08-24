# Qiskit IBM Runtime — Comprehensive Report

## Overview

**Qiskit IBM Runtime** is IBM's Python SDK for accessing IBM Quantum services through the Qiskit Runtime API. It provides primitives (Sampler, Estimator), session management, backend access, and noise learning tools for running quantum circuits on IBM Quantum hardware and simulators.

- **Repository**: [Qiskit/qiskit-ibm-runtime](https://github.com/Qiskit/qiskit-ibm-runtime)
- **License**: License: GPL-3.0 (GNU General Public License Version 3)
- **Python**: ≥ 3.9
- **Latest Version**: 0.48.0 (2026-07-14)
- **API Reference**: [quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime)

---

## Dependencies

### Core (from `pyproject.toml`)
| Package | Constraint |
|---|---|
| `qiskit` | ≥ 2.3.0 |
| `qiskit-ibm-provider` | * |
| `ibm-cloud-sdk-core` | * |
| `requests-ntlm` | * |
| `requests` | * |
| `urllib3` | * |
| `python-dateutil` | * |
| `numpy` | * |
| `dill` | * |
| `ibm-platform-services` | (IBM Cloud only) |

### Dev / Test extras
| Group | Packages |
|---|---|
| `dev` | `pylint`, `pylint-pydantic`, `ruff`, `mypy`, `black`, `coverage`, `pydocstyle`, `pyproject-fluff8` |
| `test` | `pytest`, `pytest-xdist`, `pytest-mock`, `responses`, `ibm-cloud-sdk-core`, `PyGithub`, `sphinx`, `pylatexenc`, `numpy`, `qiskit-aer`, `scikit-learn`, `scipy`, `pandas` |
| `visualization` | `matplotlib` |

### Build System
- **Build backend**: `setuptools` (≥ 68.0)
- **Versioning**: `setuptools_scm` with `release-branch-semver` scheme (fallback `0.46.1`)
- **Towncrier** for changelog management

---

## Architecture

```
qiskit_ibm_runtime/
├── __init__.py              # Project entry, API overview, re-exports
├── session.py               # Session management (Session context manager)
├── QiskitRuntimeService.py  # Service entry point, account management
├── IBMBackend.py            # Backend representation, job submission
├── IBMJob.py                # Job representation (legacy)
├── RuntimeJobV2.py          # Job representation (V2)
├── RuntimeJobMPS.py         # MPS-specific job
├── RuntimeEncoder.py        # JSON serialization
├── RuntimeDecoder.py        # JSON deserialization
├── RuntimePrimitive.py      # Base primitive class
├── SamplerV2.py             # Sampler primitive (V2)
├── EstimatorV2.py           # Estimator primitive (V2)
├── OptionsV2.py             # Runtime options (V2)
├── Options.py               # Runtime options (legacy)
├── version.py               # Version utilities
├── utils/                   # Utility functions, noise learning results
├── providers/               # Backend providers
├── base/                    # Base classes
├── exceptions.py            # Custom exceptions
├── APIError.py              # API error handling
├── json.py                  # Custom JSON serialization/deserialization
├── ibm_backend.py           # Alternative backend module
├── ibm_job.py               # Alternative job module
├── qiskit_runtime_service.py # Alternative service module
└── channel/                 # Cloud channel support
```

### Key Modules

| Module | Purpose |
|---|---|
| `QiskitRuntimeService` | Main entry point. Manages accounts, discovers backends, creates sessions. |
| `Session` | Context manager for grouping primitive jobs. Supports multi-job sessions. |
| `SamplerV2` | Samples circuits. Returns quasi-distributions. |
| `EstimatorV2` | Estimates expectation values. Supports pubs with observables. |
| `OptionsV2` | Configures primitives: execution, resilience, execution.transpilation, environment settings. |
| `IBMBackend` | Represents an IBM Quantum backend. Provides job submission, queue info, properties. |
| `RuntimeJobV2` | Represents a running/completed job. Supports status, results, usage, error handling. |
| `utils.noise_learner_result` | Noise learning results (PauliLindbladError, LayerError, NoiseLearnerResult). |

---

## Usage Patterns

### Authentication
```python
from qiskit_ibm_runtime import QiskitRuntimeService

# Save account (first time only)
QiskitRuntimeService.save_account(
    channel="ibm_quantum",
    token="YOUR_API_TOKEN",
    instance="auto"  # New in 0.48.0
)

# Load account
service = QiskitRuntimeService(channel="ibm_quantum")
```

### Session + Sampler
```python
from qiskit_ibm_runtime import QiskitRuntimeService, Session, SamplerV2
from qiskit.circuit.library import RealAmplitudes
from qiskit.quantum_info import SparsePauliOp

service = QiskitRuntimeService(channel="ibm_quantum")
backend = service.least_busy(
    simulator=False,
    min_num_qubits=2,
    use_fractional_gates=True  # New in 0.48.0
)

# Build circuit + observable
circuit = RealAmplitudes(num_qubits=2, reps=1)
circuit.measure_all()
observable = SparsePauliOp.from_list([("ZZ", 1)])

with Session(backend=backend) as session:
    sampler = SamplerV2(session=session)
    job = sampler.run([circuit], shots=1000)
    result = job.result()
```

### Session + Estimator
```python
from qiskit_ibm_runtime import EstimatorV2
from qiskit.circuit.library import RealAmplitudes
from qiskit.quantum_info import SparsePauliOp

circuit = RealAmplitudes(num_qubits=2, reps=1)
observable = SparsePauliOp.from_list([("ZZ", 1)])

with Session(backend=backend) as session:
    estimator = EstimatorV2(session=session)
    pub = (circuit, observable)
    job = estimator.run([pub])
    result = job.result()
```

### Options
```python
from qiskit_ibm_runtime import EstimatorV2, Options

options = Options()
options.resilience_level = 1
options.execution.shots = 4000
options.dynamical_decoupling.enable = True
options.dynamical_decoupling.sequence_type = "XY4"
options.environment.retries = 3

estimator = EstimatorV2(session=session, options=options)
```

### Job Management
```python
job = estimator.run([pub])

# Status
job.status()

# Result
result = job.result()

# Usage (new partial parameter in 0.48.0)
usage = job.usage(partial=True)

# Error handling
if job.status() == "ERROR":
    print(job.error_message())
```

### Backend Discovery
```python
# List all backends
backends = service.backends()

# Least busy
backend = service.least_busy(
    simulator=False,
    min_num_qubits=127,
    use_fractional_gates=True
)

# Backend properties
print(backend.name)
print(backend.num_qubits)
print(backend.target)
```

---

## Latest Release (0.48.0 — 2026-07-14)

### Upgrade Notes
- Minimum `qiskit` version bumped to **2.3.0**; `Samplomatic` minimum is **0.18.0**
- `Executor` users can twirl circuits with `"local_c1"` group (requires Samplomatic ≥ 0.17.0)

### New Features
- **`RuntimeJobV2.usage(partial=...)`**: Returns incremental partial usage before calculation completes
- **Executor timing options**: Request circuit schedule timing and numeric stretch resolutions
- **`instance="auto"`**: Auto-select instance without warnings in `QiskitRuntimeService`
- **`least_busy(use_fractional_gates=True)`**: Filter backends by fractional gate support
- **Multiple result decoders** reintroduced for `RuntimeJobV2`
- **`meas_level="both"`**: Request classified and kerneled measurements in QuantumProgram results

### Deprecations
- Result classes moved to `qiskit_ibm_runtime.results` package; old import locations deprecated
  - `PauliLindbladError`, `LayerError`, `NoiseLearnerResult` (from `utils.noise_learner_result`)
  - `EstimatorPubResult` (from `utils.estimator_pub_result`)
- Running `SamplerV2` with different `pub.shots` across PUBs deprecated
- Running `EstimatorV2` with different `pub.precision` across PUBs deprecated
- `MeasureNoiseLearningOptions.shots_per_randomization` as `int` deprecated; use `"auto"`

### Bug Fixes
- `FoldRzzAngle`: Fixed global phase issue for Rzz gates wrapping at ±π boundary
- Cross-instance backend job submission now uses correct API client
- Fixed out-of-bounds Rzz angle folding; replaced `IBMDynamicFractionalTranslationPlugin` with `WrapAngles` pass

### Other
- Now uses Qiskit Runtime REST API version `2026-04-15`
- `IBMFractionalTranslationPlugin` removed
- Default Executor schema version is now `1.1`

---

## Deprecation Policy

- **3 months / 2 minor versions** minimum before removal
- All removals require `DeprecationWarning` with alternative path
- Only minor releases (not patch) may contain API changes
- Use `@deprecate_function`, `deprecate_arguments`, or `issue_deprecation_msg` from `qiskit_ibm_runtime.utils.deprecation`
- `FutureWarning` for behavioral changes
- Deprecated features remain frozen (critical bug fixes only) until removal

---

## Project Structure Summary

| Directory | Purpose |
|---|---|
| `qiskit_ibm_runtime/` | Main source package |
| `docs/` | Sphinx documentation |
| `release-notes/` | Towncrier-based release notes (not CHANGELOG.md) |
| `test/` | Test suite (pytest) |
| `examples/` | Usage examples |
| `scripts/` | Build/CI scripts |

---

*Report compiled from GitHub repository analysis, `pyproject.toml`, `__init__.py` docstring, release notes, and source directory listing.*
