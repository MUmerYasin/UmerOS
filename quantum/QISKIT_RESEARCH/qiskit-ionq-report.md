# Qiskit IonQ Provider — Comprehensive Report

> **Repository:** [qiskit-community/qiskit-ionq](https://github.com/qiskit-community/qiskit-ionq)  
> **License:** Apache 2.0 (IBM) + Apache 2.0 (IonQ, Inc.)  
> **Status:** Community project, actively maintained

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Authentication](#authentication)
5. [Provider](#provider)
6. [Backends](#backends)
7. [Native IonQ Gates](#native-ionq-gates)
8. [Standard Gates](#standard-gates)
9. [Jobs & Sessions](#jobs--sessions)
10. [API Client](#api-client)
11. [Transpiler Optimizer Plugins](#transpiler-optimizer-plugins)
12. [Equivalence Library](#equivalence-library)
13. [Configuration](#configuration)
14. [Usage Examples](#usage-examples)
15. [Project Structure](#project-structure)

---

## Overview

Qiskit IonQ is a Qiskit provider for IonQ quantum computing hardware and simulators. It allows users to submit quantum circuits to IonQ's trapped-ion quantum computers via Qiskit's transpiler and execution framework.

**Key capabilities:**
- Submit circuits to IonQ hardware (Aria, Forte) and simulators (Aria Simulator, FPU Simulator)
- Native IonQ gate support: `GPIGate`, `GPI2Gate`, `MSGate`, `ZZGate`
- Transpiler optimizer plugins for trapped-ion backends
- Gate equivalence library for IonQ native gates
- Session management for grouping jobs
- Configurable error mitigation and aggregation methods

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  User Application               │
├─────────────────────────────────────────────────┤
│              Qiskit Transpiler                  │
│         (IonQ Optimizer Plugins)                │
├─────────────────────────────────────────────────┤
│              IonQProvider                       │
│         └── IonQClient (REST API)              │
├─────────────────────────────────────────────────┤
│           Backend Classes                      │
│  ┌──────────────────┐  ┌─────────────────────┐ │
│  │IonQSimulatorBackend│  │IonQHardwareBackend  │ │
│  │  (aer_simulator)  │  │  (ionq_hardware)    │ │
│  └──────────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────┤
│           IonQ Job Management                  │
│         IonQJob (JobV1 subclass)               │
│         IonQResult (ResultV1)                  │
└─────────────────────────────────────────────────┘
```

**Core classes:**
| Class | Inherits | Purpose |
|-------|----------|---------|
| `IonQProvider` | Standalone (`ProviderV1`) | Main entry point |
| `IonQSimulatorBackend` | `BackendV2` | Simulator backend |
| `IonQHardwareBackend` | `BackendV2` | Hardware backend |
| `IonQClient` | N/A | REST API client |
| `IonQJob` | `JobV1` | Job management |
| `Session` | N/A | Session grouping |
| `IonQResult` | `ResultV1` | Result handling |

---

## Installation

```bash
pip install qiskit-ionq
```

**Dependencies:**
- `qiskit >= 1.0`
- `requests >= 2.0`

**Optional dependencies:**
- `qiskit-aer` for local simulation

---

## Authentication

### Method 1: Direct (Recommended for scripts)

```python
from qiskit_ionq import IonQProvider

provider = IonQProvider(
    token="your_ionq_api_key",
    url="https://api.ionq.co/v0.4"
)
```

### Method 2: Environment Variables

```bash
export IONQ_API_TOKEN="your_ionq_api_key"
export IONQ_API_URL="https://api.ionq.co/v0.4"  # optional
```

```python
from qiskit_ionq import IonQProvider

provider = IonQProvider()  # reads from env
```

### Method 3: Qiskit User Config

```json
{
  "IonQ": {
    "token": "your_ionq_api_key",
    "url": "https://api.ionq.co/v0.4"
  }
}
```

---

## Provider

**Class:** `IonQProvider`

```python
from qiskit_ionq import IonQProvider

provider = IonQProvider(token="your_api_key")

# List available backends
backends = provider.backends()

# Get a specific backend
backend = provider.get_backend("ionq_simulator")
```

**Provider properties:**
- `name` = `"ionq_provider"`
- `token` — API key
- `url` — API base URL

**Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `backends()` | `list[IonQBackend]` | All available backends |
| `get_backend(name)` | `IonQBackend` | Specific backend by name |
| `save_account(token, url)` | None | Save credentials to disk |
| `delete_account()` | None | Delete saved credentials |

---

## Backends

### Backend Hierarchy

```
IonQBackend (abstract base)
├── IonQSimulatorBackend  (name: "aer_simulator")
└── IonQHardwareBackend   (name: "ionq_hardware")
```

### Common Backend Properties

| Property | Description |
|----------|-------------|
| `name` | Backend identifier |
| `num_qubits` | Number of qubits (e.g., 32) |
| `target` | `Target` object with gate set |
| `max_circuits` | Maximum circuits per job |
| `shots` | Default number of shots |

### Common Backend Methods

| Method | Description |
|--------|-------------|
| `run(circuit, **options)` | Submit a circuit for execution |
| `configuration()` | Backend configuration dict |
| `properties()` | Backend properties (gates, noise) |
| `status()` | Backend operational status |

### IonQSimulatorBackend

Simulates circuits using IonQ's FPU (Floating Point Unit) simulator. Ideal for development and testing before running on hardware.

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `noise_model` | str | None | Noise model for simulation |
| `shots` | int | 1024 | Number of measurement shots |

### IonQHardwareBackend

Runs circuits on IonQ's trapped-ion quantum computers (Aria, Forte).

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `error_mitigation` | ErrorMitigation | None | Error mitigation strategy |
| `shots` | int | 1024 | Number of measurement shots |
| `aggregate` | AggregationMethod | None | Result aggregation method |

---

## Native IonQ Gates

IonQ's trapped-ion hardware natively supports a specific gate set. These are defined in `ionq_gates.py`.

### GPIGate (Global Phase + Interaction)

**Symbol:** `GPI`  
**Description:** Single-qubit gate implementing global phase interaction.

```python
from qiskit_ionq.gates import GPIGate

# Create a GPI gate
gpi = GPIGate(phi=0.5)  # phi is the rotation angle
```

**Parameters:**
| Param | Type | Range | Description |
|-------|------|-------|-------------|
| `phi` | float | [0, 2π] | Rotation angle |

**Matrix:**
```
┌ e^(-i*φ)  0   ┐
│              │
└ 0       e^(i*φ) ┘
```

### GPI2Gate (Global Phase + Interaction 2)

**Symbol:** `GPI2`  
**Description:** Single-qubit gate, variant of GPI with different phase.

```python
from qiskit_ionq.gates import GPI2Gate

gpi2 = GPI2Gate(phi=1.0)
```

**Parameters:**
| Param | Type | Range | Description |
|-------|------|-------|-------------|
| `phi` | float | [0, 2π] | Rotation angle |

### MSGate (Molmer-Sorensen Gate)

**Symbol:** `MS`  
**Description:** Two-qubit entangling gate native to trapped-ion systems.

```python
from qiskit_ionq.gates import MSGate

ms = MSGate(phi=0.5, theta=1.0)
```

**Parameters:**
| Param | Type | Range | Description |
|-------|------|-------|-------------|
| `phi` | float | [0, 2π] | Phase angle |
| `theta` | float | [0, π] | Interaction strength |

**Matrix (2-qubit):**
```
┌ 1    0         0         0    ┐
│ 0   cos(θ)   -i*sin(θ)*e^(-i*φ)  0   │
│ 0   -i*sin(θ)*e^(i*φ)  cos(θ)    0   │
│ 0    0         0         1    ┘
```

### ZZGate (ZZ Interaction)

**Symbol:** `ZZ`  
**Description:** Two-qubit ZZ interaction gate.

```python
from qiskit_ionq.gates import ZZGate

zz = ZZGate(theta=0.8)
```

**Parameters:**
| Param | Type | Range | Description |
|-------|------|-------|-------------|
| `theta` | float | [0, 2π] | Rotation angle |

---

## Standard Gates

IonQ supports a comprehensive set of standard Qiskit gates in addition to native gates.

### Single-Qubit Gates

| Gate | Description |
|------|-------------|
| `I` | Identity |
| `X` | Pauli-X (NOT) |
| `Y` | Pauli-Y |
| `Z` | Pauli-Z |
| `H` | Hadamard |
| `S` | Phase gate |
| `S†` (Sdg) | Adjunct Phase gate |
| `T` | π/8 gate |
| `T†` (Tdg) | Adjunct π/8 gate |
| `SX` | √X gate |
| `SX†` (SXdg) | Adjunct √X gate |
| `RX(θ)` | X-rotation |
| `RY(θ)` | Y-rotation |
| `RZ(θ)` | Z-rotation |
| `Phase(θ)` | Phase rotation |

### Two-Qubit Gates

| Gate | Description |
|------|-------------|
| `CX` (CNOT) | Controlled-X |
| `CY` | Controlled-Y |
| `CZ` | Controlled-Z |
| `CH` | Controlled-H |
| `CRX(θ)` | Controlled-RX |
| `CRY(θ)` | Controlled-RY |
| `CRZ(θ)` | Controlled-RZ |
| `CSX` | Controlled-SX |
| `CPhase(θ)` | Controlled-Phase |
| `SWAP` | Swap |
| `RXX(θ)` | XX interaction |
| `RYY(θ)` | YY interaction |
| `RZZ(θ)` | ZZ interaction |

### Multi-Qubit Gates

| Gate | Description |
|------|-------------|
| `MCX` | Multi-controlled X |
| `MCPhase` | Multi-controlled Phase |

### Measurement & Reset

| Operation | Description |
|-----------|-------------|
| `Measure` | Measurement |
| `Reset` | Qubit reset |

---

## Jobs & Sessions

### IonQJob

**Inherits:** `JobV1`

```python
from qiskit_ionq import IonQJob

# Submit a job
job = backend.run(circuit, shots=1024)

# Check status
print(job.status())  # JobStatus enum

# Get results
result = job.result()

# Get job ID
print(job.job_id())

# Cancel a job
job.cancel()
```

**Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `status()` | `JobStatus` | Current job status |
| `result()` | `IonQResult` | Job results |
| `job_id()` | `str` | IonQ job ID |
| `cancel()` | None | Cancel running job |
| `error_message()` | `str` | Error message if failed |
| `wait_for_final_state(timeout, wait)` | `JobStatus` | Block until done |

**Job Status Mapping:**

| IonQ Status | Qiskit Status |
|-------------|---------------|
| `SUBMITTED` | `JobStatus.INITIALIZING` |
| `READY` | `JobStatus.QUEUED` |
| `RUNNING` | `JobStatus.RUNNING` |
| `COMPLETED` | `JobStatus.DONE` |
| `FAILED` | `JobStatus.ERROR` |
| `CANCELED` | `JobStatus.CANCELLED` |

### Session

```python
from qiskit_ionq import Session

# Create a session for grouping jobs
with Session(backend=backend) as session:
    job1 = backend.run(circuit1)
    job2 = backend.run(circuit2)
    
    # Results available after completion
    result1 = job1.result()
    result2 = job2.result()
```

---

## API Client

**Class:** `IonQClient`

Internal REST API client that communicates with IonQ's API.

**Base URL:** `https://api.ionq.co/v0.4`

**Key API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v0.4/keys` | GET | List API keys |
| `/v0.4/keys/{key_id}` | GET | Get specific key |
| `/v0.4/{backend}/jobs` | POST | Submit a job |
| `/v0.4/{backend}/jobs/{job_id}` | GET | Get job status |
| `/v0.4/{backend}/jobs/{job_id}/results` | GET | Get job results |
| `/v0.4/{backend}/jobs/{job_id}` | DELETE | Cancel a job |
| `/v0.4/backends` | GET | List available backends |
| `/v0.4/backends/{backend}` | GET | Get backend details |

**Circuit Serialization:**
- Circuits are serialized to IonQ's native JSON format before submission
- Gate mapping handled by `helpers.py`
- `ionq_circuit_to_json()` converts Qiskit circuits to IonQ format

---

## Transpiler Optimizer Plugins

IonQ provides transpiler optimizer plugins to improve circuit compilation for trapped-ion hardware.

### Plugin Classes

| Plugin | Description |
|--------|-------------|
| `TrappedIonOptimizerPlugin` | Base optimizer for trapped-ion |
| `TrappedIonOptimizerPluginSimpleRules` | Simplifies common gate patterns |
| `TrappedIonOptimizerPluginCompactGates` | Compacts gate sequences |
| `TrappedIonOptimizerPluginCommuteGpi2ThroughMs` | Commutes GPI2 gates through MS gates |

### Usage

```python
from qiskit import transpile
from qiskit_ionq import IonQProvider
from qiskit_ionq.plugins import TrappedIonOptimizerPlugin

provider = IonQProvider(token="your_api_key")
backend = provider.get_backend("ionq_hardware")

# Transpile with IonQ optimizer
transpiled = transpile(
    circuit,
    backend=backend,
    optimization_plugins=[TrappedIonOptimizerPlugin()]
)
```

### Available Optimizer Plugins

```python
from qiskit_ionq.plugins import (
    TrappedIonOptimizerPlugin,
    TrappedIonOptimizerPluginSimpleRules,
    TrappedIonOptimizerPluginCompactGates,
    TrappedIonOptimizerPluginCommuteGpi2ThroughMs
)
```

---

## Equivalence Library

IonQ provides gate equivalence definitions for converting standard gates to native IonQ gates.

```python
from qiskit_ionq import add_equivalences

# Add IonQ equivalences to the equivalence library
add_equivalences()

# Now transpile can use these equivalences
transpiled = transpile(circuit, backend=backend)
```

**Equivalences provided:**
- `RZ` → `GPI` + `GPI2` decomposition
- `RY` → `GPI` + `GPI2` decomposition
- `RX` → `GPI` + `GPI2` decomposition
- `CX` → `GPI` + `GPI2` + `MS` decomposition
- Other standard gates to native IonQ gate equivalents

---

## Configuration

### Constants

**File:** `constants.py`

```python
from qiskit_ionq.constants import (
    APIJobStatus,
    JobStatusMap,
    AggregationMethod,
    ErrorMitigation
)
```

### APIJobStatus

```python
class APIJobStatus(Enum):
    SUBMITTED = "submitted"
    READY = "ready"
    RUNNING = "running"
    CANCELED = "canceled"
    COMPLETED = "completed"
    FAILED = "failed"
```

### AggregationMethod

```python
class AggregationMethod(Enum):
    MOST_LIKELY = "most_likely"
    EXPECTATION_VALUE = "expectation_value"
    HISTOGRAM = "histogram"
```

### ErrorMitigation

```python
class ErrorMitigation(Enum):
    NONE = "none"
    SHOT_NOISE = "shot_noise"
    ZERO_NOISE_EXTRAPOLATION = "zero_noise_extrapolation"
    MATRIX_ERROR_DIFFUSION = "matrix_error_diffusion"
```

---

## Usage Examples

### Basic Example: Submit a Circuit

```python
from qiskit import QuantumCircuit
from qiskit_ionq import IonQProvider

# Create a simple circuit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

# Connect to IonQ
provider = IonQProvider(token="your_api_key")
backend = provider.get_backend("ionq_simulator")

# Run the circuit
job = backend.run(qc, shots=1024)

# Get results
result = job.result()
counts = result.get_counts()
print(counts)  # {'00': ~512, '11': ~512}
```

### Native Gate Example

```python
from qiskit import QuantumCircuit
from qiskit_ionq.gates import GPIGate, GPI2Gate, MSGate

qc = QuantumCircuit(2, 2)
qc.append(GPIGate(phi=0.5), [0])
qc.append(GPI2Gate(phi=1.0), [1])
qc.append(MSGate(phi=0.0, theta=3.14159/4), [0, 1])
qc.measure([0, 1], [0, 1])

# Run on IonQ hardware
provider = IonQProvider(token="your_api_key")
backend = provider.get_backend("ionq_hardware")
job = backend.run(qc, shots=1024)
result = job.result()
```

### Error Mitigation Example

```python
from qiskit import QuantumCircuit
from qiskit_ionq import IonQProvider
from qiskit_ionq.constants import ErrorMitigation

provider = IonQProvider(token="your_api_key")
backend = provider.get_backend("ionq_hardware")

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

# Run with error mitigation
job = backend.run(
    qc,
    shots=4096,
    error_mitigation=ErrorMitigation.ZERO_NOISE_EXTRAPOLATION
)

result = job.result()
```

### Transpile with IonQ Optimizer

```python
from qiskit import QuantumCircuit
from qiskit import transpile
from qiskit_ionq import IonQProvider
from qiskit_ionq.plugins import TrappedIonOptimizerPlugin

provider = IonQProvider(token="your_api_key")
backend = provider.get_backend("ionq_hardware")

qc = QuantumCircuit(3, 3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.measure([0, 1, 2], [0, 1, 2])

# Transpile with IonQ-specific optimizations
transpiled = transpile(
    qc,
    backend=backend,
    optimization_plugins=[TrappedIonOptimizerPlugin()]
)

job = backend.run(transpiled, shots=1024)
```

---

## Project Structure

```
qiskit-ionq/
├── README.md                    # Project documentation
├── setup.py / setup.cfg         # Package configuration
├── requirements.txt             # Dependencies
├── LICENSE                      # Apache 2.0
├── docs/                        # Documentation
│   ├── getting_started.md
│   ├── usage.md
│   └── api_reference.md
├── qiskit_ionq/                 # Main package
│   ├── __init__.py              # Package exports
│   ├── ionq_provider.py         # IonQProvider class
│   ├── ionq_backend.py          # Backend classes
│   ├── ionq_client.py           # REST API client
│   ├── ionq_job.py              # Job management
│   ├── ionq_result.py           # Result handling
│   ├── ionq_gates.py            # Native IonQ gates
│   ├── ionq_session.py          # Session management
│   ├── constants.py             # Enums and constants
│   ├── exceptions.py            # Custom exceptions
│   ├── helpers.py               # Utility functions
│   ├── ionq_optimizer_plugin.py # Transpiler plugins
│   └── ionq_equivalence_library.py # Gate equivalences
└── tests/                       # Test suite
    ├── test_provider.py
    ├── test_backend.py
    ├── test_gates.py
    └── test_job.py
```

---

## Known Limitations

1. **Truncated source files:** Some source files were truncated during research; full implementation details may vary
2. **API version:** Based on IonQ API v0.4; check for updates
3. **Max circuits per job:** May be limited by IonQ API quotas
4. **Gate support:** Native gate support varies by backend (Aria vs Forte)

---

## References

- [Qiskit IonQ GitHub](https://github.com/qiskit-community/qiskit-ionq)
- [IonQ API Documentation](https://docs.ionq.com/)
- [Qiskit Documentation](https://qiskit.org/documentation/)
- [IonQ Quantum Computers](https://ionq.com/quantum-computers)

---

*Report compiled: 2026-08-10*
