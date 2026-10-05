# **Proposed: UmerOS Hardware Requirements Document**

### **1. Summary**

UmerOS is a Python-based research operating system with a Flutter desktop frontend. Hardware requirements differ significantly based on:

- Whether you're **developing** UmerOS or **running** it
- Whether you're using the **Python services only** or the **full Flutter GUI**
- Your workload type (simulation, quantum research, AI inference, etc.)

---

### **2. Minimum Hardware Requirements**

#### **For Running UmerOS (User Mode)**

| Component | Minimum | Recommended | Notes |
| --- | --- | --- | --- |
| **Processor** | Dual-core x86_64 or ARM64, 1.5 GHz+ | Quad-core, 2.0 GHz+ | ARM64 (Raspberry Pi 4+, Jetson) supported |
| **RAM** | 2 GB | 4-8 GB | Quantum simulator needs exponential memory; add 2× simulation qubits |
| **Storage** | 500 MB free | 2-5 GB | Python 3.12+ required, Python environment, dependencies, quantum states |
| **GPU** | Integrated (optional) | Discrete (optional) | For AI inference or complex rendering only |
| **Network** | Not required | Loopback sufficient | Cloud/online providers optional |

#### **For Flutter Desktop Frontend (GUI)**

| Component | Minimum | Recommended |
| --- | --- | --- |
| **Processor** | Dual-core, 1.8 GHz+ | Quad-core, 2.2 GHz+ |
| **RAM** | 4 GB | 8 GB |
| **Storage** | 1 GB free | 2 GB free |
| **Display** | 1024×768 @ 60 Hz | 1920×1080 @ 60 Hz or better |
| **GPU** | Integrated OpenGL/Vulkan | Dedicated GPU |

#### **For Python Services Only (Headless)**

| Component | Minimum | Recommended |
| --- | --- | --- |
| **Processor** | Single-core x86_64 or ARM64 | Dual-core or better |
| **RAM** | 512 MB - 1 GB | 2-4 GB |
| **Storage** | 200 MB | 1 GB |

---

### **3. Workload-Specific Requirements**

| Use Case | CPU Cores | RAM | Storage | Notes |
| --- | --- | --- | --- | --- |
| **Python services only** (AI, QFS, network) | 1-2 | 512 MB - 2 GB | 500 MB - 1 GB | Suitable for embedded/IoT |
| **Flutter GUI + light workload** | 2 | 2-4 GB | 1-2 GB | Typical development machine |
| **Quantum simulation (5-10 qubits)** | 2-4 | 2-4 GB | 1-2 GB | Exponential scaling: `memory ≈ 2^qubits × 16 bytes` |
| **Quantum simulation (15+ qubits)** | 4-8 | 8-32 GB | 5-20 GB | Requires high-end machine or distributed backend |
| **Full development environment** | 4+ | 8-16 GB | 5-10 GB | Flutter SDK, Python venv, IDE, docs, tests |
| **Production service deployment** | 4-8 | 4-8 GB | 10-50 GB | Multiple services, persistent storage, logs |

---

### **4. By Platform**

#### **Raspberry Pi and Embedded (ARM64)**

- **Model:** Raspberry Pi 4 (4GB+) or later
- **Storage:** microSD card UHS-II 32 GB+ (UHS recommended for speed)
- **Note:** Quantum simulation and full UI are limited by 4 GB RAM; suitable for headless services and research only

#### **NVIDIA Jetson (ARM64, research-grade)**

- **Model:** Jetson Nano (4 GB, headless) or Xavier NX/AGX (development)
- **Storage:** 64 GB+ NVMe SSD (microSD too slow for sustained workloads)
- **CUDA:** Optional GPU acceleration for quantum simulation
- **Recommended:** Jetson Xavier for full UmerOS capabilities

---

### **5. Network Requirements**

- **Minimum:** Loopback only (localhost, no external connectivity)
- **Recommended:** 10 Mbps Ethernet for development/testing
- **Optional:** Cloud/online providers require internet access and explicit consent

---

### **6. Storage Details**

| Component | Size | Notes |
| --- | --- | --- |
| Python 3.12 + venv | ~150-200 MB | Includes pip, setuptools, wheel |
| Core UmerOS code | ~50-100 MB | kernel, quantum, ai, fs, drivers, security |
| Dependencies (requirements.txt) | ~100-300 MB | NumPy, cryptography, qiskit, FastAPI, etc. |
| Flutter SDK (UI development) | ~2-3 GB | Including Dart SDK, build artifacts |
| Quantum states (15 qubits sim) | ~1 GB | State vector alone; add circuit artifacts |
| Test suite | ~10-50 MB | Fixtures and test data |
| **Total: minimal install** | ~300-500 MB | Python + core modules only |
| **Total: full development** | ~5-10 GB | Everything including Flutter, docs, tests |

---

### **7. Key Installation Paths**

#### **Path A: Python Services Only (Minimal)**

```bash
Minimum: 1 GB free disk, 1 GB RAM, Python 3.12
Installation: pip install -e . (core)
Footprint: ~300-500 MB
Uses: AI, QFS, security, network, limited quantum
```

#### **Path B: Python + Flutter GUI (Development)**

```bash
Minimum: 5 GB free disk, 4-8 GB RAM, Python 3.12, Flutter SDK
Installation: pip install -e . && flutter pub get
Footprint: ~5-7 GB
Uses: Full desktop experience, all subsystems
```

#### **Path C: Python + Full Features (Research)**

```bash
Minimum: 10 GB free disk, 8-16 GB RAM, Python 3.12 + optionals
Installation: pip install -e ".[all]"
Footprint: ~2-3 GB (after cleanup)
Uses: Quantum at scale, AI with large models, storage experiments
```

---

### **8. Special Considerations**

#### **Quantum Simulation Scaling**

| Qubits | State Vector Size | Recommended RAM | Typical Runtime (1000 shots) |
| --- | --- | --- | --- |
| 5-8 | 1-64 KB | 1 GB | <1 sec |
| 10-15 | 16 KB - 1 MB | 4-8 GB | 1-10 sec |
| 20-25 | 4 MB - 128 MB | 32-64 GB | 10-60 sec |
| 30+ | 1 GB+ | 256+ GB | Minutes+ |

#### **AI Model Inference**

- **Small models (100M - 1B params):** 1-2 GB RAM, 2 GB disk
- **Medium models (1B - 7B params):** 4-16 GB RAM, 5-10 GB disk
- **Large models (13B+ params):** 32 GB+ RAM, 20+ GB disk
- **Recommendation:** Use online providers for models > 13B unless dedicated hardware available

#### **Docker / Containerized Deployment**

- Add ~100-200 MB for container image overhead
- Use multi-stage builds to minimize final size
- See [`Dockerfile`](Dockerfile) and [`docker-compose.yml`](docker-compose.yml) for examples

---

### **9. Verification Checklist**

Before installation, verify:

- [ ] Python 3.12+ installed: `python --version`
- [ ] Sufficient free disk: `df -h` (at least 1 GB)
- [ ] Available RAM: `free -h` (at least 512 MB for headless, 4 GB for GUI)
- [ ] Architecture supported: `uname -m` (x86_64 or aarch64)
- [ ] C compiler (optional but recommended): `gcc --version` or `clang --version`
- [ ] Git: `git --version`

---

### **10. Unsupported Configurations**

- ❌ 32-bit x86 or ARMv7 (only 64-bit: x86_64, ARM64)
- ❌ < 512 MB RAM (hard limit for Python runtime)

---

## **Summary Table**

| Scenario | CPU | RAM | Storage | Network | Cost |
| --- | --- | --- | --- | --- | --- |
| **Hobbyist / Learning** | Dual-core | 2 GB | 1 GB | Optional | $0-100 (reuse old hardware) |
| **Developer / Researcher** | Quad-core | 8 GB | 5-10 GB | Gigabit | $400-800 |
| **Quantum research (15+ qubits)** | 8+ cores | 32+ GB | 20+ GB | Gigabit | $2000+ |
| **Production deployment** | 8+ cores | 8-16 GB | 50-100 GB | Redundant | $1000-5000+ |
