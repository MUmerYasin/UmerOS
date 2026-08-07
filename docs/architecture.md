# Umer OS — System Architecture

**Version:** 0.1.0-alpha | **Audience:** System architects, kernel developers

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         APPLICATIONS & USERS                                │
│   Native Umer Apps │ Web Apps │ Windows .exe │ Android .apk │ Linux ELF    │
└────────┬──────────────────────────────────────────────────────┬─────────────┘
         │                                                      │
         ▼                                                      ▼
┌─────────────────────────┐              ┌─────────────────────────────────────┐
│     UI / UX ENGINE      │              │       COMPATIBILITY LAYER           │
│  Kivy Shell / Headless  │              │  WineShim (.exe via Wine/LGPL)      │
│  TaskBar · AppLauncher  │              │  AndroidContainer (APK/ADB)         │
│  VoiceController        │              │  LinuxCompat (native ELF)           │
│  AIUIAdapter            │              │  SyscallTranslator (Win32→POSIX)    │
└─────────┬───────────────┘              └─────────────────┬───────────────────┘
          │                                                │
          └───────────────────┬────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     USER-SPACE SERVICES (Python)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ Quantum Layer│  │  AI Engine   │  │   Security   │  │  QFS (Storage) │ │
│  │ QuantumSim   │  │ ResourceMgr  │  │  Sandbox     │  │  CASStore      │ │
│  │ QuantumAPI   │  │ Assistant    │  │  SecureBoot  │  │  Compressor    │ │
│  │ ErrorMitig.  │  │ SelfHealing  │  │  AIFirewall  │  │  AIIndexer     │ │
│  │ PQ Crypto    │  │ Governance   │  │  IPCAuth     │  │  Snapshots     │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘ │
│         └─────────────────┴──────────────────┴──────────────────┘          │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │             NETWORK + CLOUD + PACKAGES                                 │ │
│  │  NetworkStack │ DNSoHTTPS │ VPN │ mDNS │ SyncAgent │ OTA │ UmerPkg   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ IPC Bus (HMAC-SHA256 signed messages)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UMER HYBRID QUANTUM KERNEL                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────────────┐  │
│  │ HybridScheduler │  │  MemoryManager  │  │       IPCBus              │  │
│  │ Task dataclass  │  │ Page table dict │  │ HMAC-SHA256 signing       │  │
│  │ quantum scoring │  │ allocate/free   │  │ async send/receive        │  │
│  └────────┬────────┘  └────────┬────────┘  └────────────┬──────────────┘  │
│  ┌────────┴────────────────────┴─────────────────────────┴──────────────┐  │
│  │  CapabilityManager (SYSTEM_PID=0, register/grant/check)                │  │
│  │  SecureBoot (SHA3-256 image verify, trust store, TPM log)              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   HARDWARE ABSTRACTION LAYER (HAL)                          │
│  Keyboard │ Network │ GPU │ Storage │ Base Driver (all inherit DeviceDriver)│
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  HARDWARE:  CPU (x86_64/ARM64/RISC-V) │ GPU/NPU │ RAM │ NVMe │ NIC │ USB   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Boot Process

```
POWER ON → UEFI/BIOS POST
    │
    ▼
UMER BOOTLOADER (boot/bootloader.py)
    ├── show_banner()
    ├── show_legal_warning()
    ├── system_check()           Python ≥3.10, platform, RAM
    ├── verify_kernel(hash)      SHA3-256 vs trust store
    └── load_kernel()
             │
             ▼
    UmerKernel.__init__()
         ├── HybridScheduler(quantum_simulator)
         ├── MemoryManager(total_memory_bytes)
         ├── IPCBus()
         └── CapabilityManager()  → SYSTEM_PID=0 gets all caps
             │
             ▼
    UmerKernel.init()   [async]
         ├── ipc.start(); ipc.register(SYSTEM_PID)
         └── scheduler.start(ai_manager=NullAIManager())
             │
             ▼
    SERVICES (dependency order)
         1. SecuritySandbox + SecureBoot
         2. QFS.mount("/")
         3. NetworkStack.start()
         4. QuantumAPIGateway.init()
         5. AIResourceManager.start()  ← replaces NullAIManager
         6. CloudSyncAgent.start() (opt-in)
             │
             ▼
    LOGIN MANAGER → USER SESSION (Kivy Desktop or headless)
```

---

## 3. IPC Message Flow

```
Process A (sender)                       Process B (receiver)
    │                                          │
    │ IPCBus.send(src=A, dst=B, payload)       │
    │       │                                  │
    │  msg = IPCMessage(src,dst,payload)       │
    │  msg.sign(self._key)                     │
    │  # HMAC-SHA256 over                      │
    │  # JSON({src,dst,channel,payload,ts})    │
    │  queue_B.put(msg) ────────────────────────►
    │                                          │
    │                                    await IPCBus.receive(B)
    │                                          │
    │                                    msg.verify(self._key)
    │                                    # recompute HMAC
    │                                    # compare_digest (timing-safe)
    │                                          │
    │                                    valid → return msg
    │                                    invalid → DROP + log security error
```

---

## 4. Memory Management

```
VIRTUAL ADDRESS SPACE (simulated with Python dict)

 0x0000_0000   ← NULL page (reserved, never allocated)
 0x0000_1000   ← First allocatable page (PAGE_SIZE = 4096)
     │
     │  _allocs: Dict[base_addr, (pid, n_pages, requested_size)]
     │
     │  0x1000 → (pid=1, n_pages=3, size=10240)
     │  0x4000 → (pid=2, n_pages=1, size=100)
     │  0x5000 → (pid=1, n_pages=2, size=7000)
     ▼
 0xFFFF_FFFF   ← End of simulated address space

 TOTAL_PAGES = total_memory_bytes ÷ PAGE_SIZE
 FREE_PAGES  = TOTAL_PAGES - 1 - Σ(n_pages for all allocations)
```

---

## 5. Quantum Layer Architecture

```
APPLICATION CODE
      │  circuit_ops = [{"gate":"H","qubit":0}, {"gate":"CNOT","control":0,"target":1}]
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    QuantumAPIGateway                            │
│   run(circuit_ops, backend="simulator", shots=1024)              │
│       │                                                          │
│       ├── _required_qubits(circuit_ops)  ← dynamically sized!    │
│       │       Prevents entangled states leaking into unused      │
│       │       qubits (critical bug fixed: was fixed at 4 qubits) │
│       │                                                          │
│       ├── backend == "simulator"?                                │
│       │       └── QuantumCircuitSimulator(n_qubits=required)     │
│       │             state: complex ndarray[2^n]                  │
│       │             apply_h() → Kronecker(H, I, I, ...)          │
│       │             apply_cnot() → index-permutation              │
│       │             measure() → weighted random sample            │
│       │                                                          │
│       └── backend == real QPU?  [FUTURE]                         │
│               └── self._backends[backend].run_circuit(...)       │
│                     └── QuantumDevice.run_circuit()  ← TODO      │
└─────────────────────────────────────────────────────────────────┘
      │  result = {"counts": {"0": 512, "3": 512}, "backend": "simulator"}
      ▼
ERROR MITIGATION (optional)
      ├── ReadoutCalibrator.mitigate(raw_counts)
      └── ZeroNoiseExtrapolator.extrapolate(expectation_fn)
```

---

## 6. AI Scheduling Integration

```
KERNEL TICK (every 10ms)
      │
      ▼
HybridScheduler._select_next()
      │
      ├── Get all tasks with state == READY
      │
      ├── [Optional] quantum_sim.evaluate_task_paths(ready_tasks)
      │       Blends 50% static priority + 50% quantum probability
      │
      ├── For each task: schedule_score =
      │       quantum_state["superposition"] × priority / (cpu_time + ε)
      │
      └── Select MAX(schedule_score) → dispatch task

AI FEEDBACK LOOP (parallel)
      ▼
AIResourceManager (monitoring)
      ├── record_cpu(pid, usage)   every tick
      ├── record_ram(pid, bytes)   every tick
      └── predict_task_success(task)
              = 0.5×(1/(1+crashes)) + 0.3×(1-predicted_cpu) + 0.2×priority
              → stored in task.quantum_state["superposition"]
```

---

## 7. Security: Zero-Trust Flow

```
Process X                 CapabilityManager          FileSystem Service
    │                           │                          │
    │── check("fs.read") ──────▶│                          │
    │                    with self._lock:                  │
    │                      ok = "fs.read" in grants[X]      │
    │                           │                          │
    │    PermissionError ◀──────┤ if NOT ok                │
    │    (raised here)          │                          │
    │                           │                          │
    │    True ◀──────────────────┤ if ok                    │
    │                           │                          │
    │── IPCBus.send(X, FS, {"op":"read","path":"/data"}) ──▶│
    │              [message HMAC-signed]                   │
    │                                    [msg.verify(key)]  │
    │                                    read file          │
    │◀─────────────────────────────────── file bytes ───────┤
```

---

## 8. QFS Storage Flow

```
qfs.write_file("/home/user/doc.txt", data)
      │
      ▼
QFSCompressor.compress(data)
      ├── Stage 1: LZMA compression
      ├── Stage 2 [EXPERIMENTAL]: XOR delta encoding vs previous block
      └── Stage 3: Metadata dedup via CAS addressing
              │
              ▼
      CASStore.put(compressed_bytes)
              ├── address = SHA3-256(compressed_bytes)
              ├── if exists: refs[address] += 1  ← DEDUPLICATION
              └── else: store new block
                      │
                      ▼
              _files[path] = address
              _meta[path] = {size, compressed, mtime}
              indexer.index(path, data)   ← keyword search update
```

---

## 9. Module Dependency Graph

```
                        hardware
                           │
                     base_driver.py
                    /      │      \
          keyboard  network  gpu  storage
                           │
                    umer_kernel.py
                    /    │    │   \
              scheduler  mm  ipc  caps
                   │            │
             quantum_sim    security.py
                   │            │
             quantum_api    crypto_pqc
                   │
             error_mitigation
                           │
                       umer_ai.py
                      /    │    \
               resource  assistant  firewall
                                     │
                              self_healing
                           │
                        qfs.py
                       /   │   \
               cas_store comp  ai_indexer
                           │
                 container_engine.py
                           │
                      installer.py
                           │
                     bootloader.py
                           │
                    gui.py / network_stack.py / umer_pkg.py
```

---

## 10. Test Coverage Map

| Module | Test File | Tests |
|---|---|---|
| kernel/scheduler.py, memory_manager.py, ipc_bus.py, capability_manager.py, umer_kernel.py | test_kernel.py | 60 |
| quantum/quantum_sim.py | test_quantum_sim.py | 26 |
| quantum/quantum_api.py, error_mitigation.py | test_quantum_extra.py | 20 |
| ai/umer_ai.py (6 classes) | test_ai.py | 47 |
| security/security.py, quantum/crypto_pqc.py | test_security.py | 46 |
| fs/qfs.py (CAS, Compressor, Indexer, QFS) | test_qfs.py | 51 |
| compatibility/container_engine.py | test_compatibility.py | 42 |
| installer/installer.py | test_installer.py | 33 |
| network/network_stack.py | test_network.py | 28 |
| packages/umer_pkg.py | test_packages.py | 26 |
| kernel/drivers/*, cloud/* | test_drivers.py | 52 |
| **TOTAL** | | **431** |

---

## 11. Critical Bugs Fixed (Engineering Notes)

| Bug | Root Cause | Fix |
|---|---|---|
| Bell-state probability leaking into unused qubits | `QuantumAPIGateway` used a fixed 4-qubit simulator regardless of circuit size | Added `_required_qubits()` to dynamically size the simulator per circuit |
| `CASStore.stats()` deadlock | `stats()` called `dedup_scan()` while holding the same lock | Inlined the dedup calculation inside the existing lock scope |
| QFS/compressor test timeouts | Tests used `os.urandom()` — incompressible data made LZMA extremely slow | Switched to repeated-pattern data (`b"X" * 2000`) which compresses in milliseconds |

---

*Umer OS Architecture Guide — v0.1.0-alpha | 431 tests passing*
