# Umer OS

**Python-first | Hybrid Classical-Quantum | AI-Native | Cross-Device**

Umer OS is a next-generation operating system prototype designed to
eventually replace Linux, Windows, Android, macOS, and HarmonyOS across
all device classes — desktops, laptops, Android phones, tablets, smart TVs,
smartwatches, and IoT devices.

---

## Feature Tiers

Every feature is labelled with one of three tiers:

| Label | Meaning |
|---|---|
| ✅ **TODAY** | Works now on classical hardware |
| 🔬 **EXPERIMENTAL** | Requires careful engineering; known instability possible |
| 🔮 **FUTURE** | Requires hardware (QPU/NPU) not yet mainstream |

---

## Architecture

```
Hardware → HAL → Umer Hybrid Quantum Kernel
                      ├── HybridScheduler   (AI + quantum-inspired) ✅
                      ├── MemoryManager     (virtual paging)        ✅
                      ├── IPCBus            (HMAC-signed messages)  ✅
                      └── CapabilityManager (zero-trust)            ✅
                 ↓
         User-Space Services (Python)
                      ├── Quantum Layer     (NumPy state-vector sim) ✅
                      ├── AI Orchestrator   (EWMA predictor + LLM)  ✅
                      ├── Security Sandbox  (PQ crypto + firewall)  ✅
                      ├── QFS               (CAS + compression)     ✅
                      ├── ContainerEngine   (Wine/Android/Linux)    🔬
                      ├── NetworkStack      (DoH + VPN + mDNS)      ✅
                      └── GUI Shell         (Kivy / headless)       ✅
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/umeros/UmerOS.git
cd UmerOS

# 2. Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Install minimal dependencies
pip install numpy cryptography

# 4. Run the test suite (all tests use stdlib only)
python -m unittest discover -s tests -v

# 5. Simulate the boot sequence
python -m boot.bootloader

# 6. Launch the GUI (requires Kivy)
pip install kivy
python -m ui.gui
```

---

## Project Structure

```
UmerOS/
├── boot/               Bootloader simulation
├── kernel/             Hybrid microkernel (scheduler, memory, IPC, caps)
├── quantum/            Quantum circuit simulator + PQ crypto
├── ai/                 AI orchestration engine
├── security/           Zero-trust sandbox + SecureBoot + IPC auth
├── fs/                 Quantum-inspired filesystem (QFS)
├── compatibility/      Container engine (Wine/Android/Linux)
├── ui/                 Kivy desktop shell
├── network/            Async TCP/IP, DoH, VPN, mDNS
├── cloud/              OTA updates + cloud sync stubs
├── installer/          Installation wizard + rollback
├── packages/           umer-pkg package manager
├── sdk/                Developer SDK stubs
└── tests/              Full unit test suite (stdlib unittest)
```

---

## Core Components

### Kernel (`kernel/`)

| File | Status | Description |
|---|---|---|
| `umer_kernel.py` | ✅ | Main microkernel orchestrator |
| `scheduler.py` | ✅ | AI+quantum-inspired HybridScheduler |
| `memory_manager.py` | ✅ | Page-based virtual memory |
| `ipc_bus.py` | ✅ | HMAC-SHA256 signed message passing |
| `capability_manager.py` | ✅ | Zero-trust capability grants |

### Quantum Layer (`quantum/`)

| File | Status | Description |
|---|---|---|
| `quantum_sim.py` | ✅ | NumPy state-vector simulator |
| `crypto_pqc.py` | ✅ | CRYSTALS-Kyber + Dilithium (liboqs / fallback) |

### AI System (`ai/`)

| File | Status | Description |
|---|---|---|
| `umer_ai.py` | ✅ | Resource manager, assistant, self-healing, firewall |

### Security (`security/`)

| File | Status | Description |
|---|---|---|
| `security.py` | ✅ | Sandbox, SecureBoot, IPCAuthenticator |

### Filesystem (`fs/`)

| File | Status | Description |
|---|---|---|
| `qfs.py` | ✅ | CAS store, LZMA+delta compression, AI search |

### Compatibility (`compatibility/`)

| File | Status | Description |
|---|---|---|
| `container_engine.py` | 🔬 | Wine/.exe, Android APK, Linux ELF launcher |

---

## Running Tests

```bash
# All tests (no extra deps needed)
python -m unittest discover -s tests -v

# Individual suites
python -m unittest tests.test_kernel        -v
python -m unittest tests.test_quantum_sim   -v
python -m unittest tests.test_ai            -v
python -m unittest tests.test_security      -v
python -m unittest tests.test_qfs           -v
python -m unittest tests.test_compatibility -v
python -m unittest tests.test_installer     -v
```

---

## Legal

### Installation Warning

> ⚠️ Installing Umer OS may void device warranties and existing software
> licences. Data loss is possible without a verified backup. Umer OS is
> provided "AS IS" with NO WARRANTY. The Umer OS project assumes NO
> LIABILITY for any damage or data loss.
>
> The installer **requires explicit consent** (`I AGREE`) before proceeding.

### Licence

Apache Licence 2.0 — see `LICENSE`.

---

## Roadmap

| Timeline | Milestone |
|---|---|
| **Years 0–2 (now)** | Python kernel + quantum sim + AI assistant + Linux compat + installer |
| **Years 2–5** | ARM64/Android port, post-quantum TLS live, SDK v1, beta on Raspberry Pi |
| **Years 5–10** | QPU co-processor interface, NPU/FPGA acceleration, stable ecosystem |
| **Years 10–20** | Fault-tolerant QPU, AGI-level AI services, mainstream consumer devices |

---

## Reality Check

- Quantum features today are **classical simulations** (NumPy state-vector).
- "Zero-error qubits" is a **FUTURE** research goal only.
- Python cannot replace C/ASM for bare-metal boot on real hardware today.
- iPhone support is **BLOCKED** by Apple's Secure Enclave.
- Performance gains come from **algorithmic efficiency**, not magic hardware speedups.

---

*Umer OS — Engineering a universal quantum-AI operating system, one realistic prototype at a time.*
