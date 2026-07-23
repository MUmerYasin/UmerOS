# Umer OS — System Architecture

**Version:** 0.1.0-alpha | **Audience:** System architects, kernel developers, OS researchers

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
│  Kivy Shell             │              │  WineShim (.exe via Wine/LGPL)      │
│  TaskBar · AppLauncher  │              │  AndroidContainer (APK/ADB)         │
│  VoiceController (Vosk) │              │  LinuxCompat (native ELF)           │
│  AIUIAdapter (layout)   │              │  SyscallTranslator (Win32→POSIX)    │
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
│         │                 │                  │                  │           │
│  ┌──────┴─────────────────┴──────────────────┴──────────────────┴────────┐ │
│  │                    NETWORK + CLOUD + PACKAGES                          │ │
│  │  NetworkStack │ DNSoHTTPS │ VPN │ mDNS │ SyncAgent │ OTA │ UmerPkg   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ IPC Bus (HMAC-SHA256 signed messages)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UMER HYBRID QUANTUM KERNEL                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────────────┐  │
│  │ HybridScheduler │  │  MemoryManager  │  │       IPCBus              │  │
│  │                 │  │                 │  │                           │  │
│  │ Task dataclass  │  │ Page table dict │  │ HMAC-SHA256 signing       │  │
│  │ quantum scoring │  │ allocate/free   │  │ async send/receive        │  │
│  │ asyncio loop    │  │ compact/predict │  │ sync subscribe/try_recv   │  │
│  └────────┬────────┘  └────────┬────────┘  └────────────┬──────────────┘  │
│           │                    │                         │                  │
│  ┌────────┴────────────────────┴─────────────────────────┴──────────────┐  │
│  │           CapabilityManager          │         SecureBoot             │  │
│  │  SYSTEM_PID=0 │ register/grant/check │  SHA3-256 image verify        │  │
│  │  query(bool) │ check(raises) │ revoke │  trust store JSON │ TPM log   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   HARDWARE ABSTRACTION LAYER (HAL)                          │
│     ctypes bindings │ Cython extensions │ VirtIO │ USB HID │ DMA           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │Keyboard  │ │ Network  │ │   GPU    │ │ Storage  │ │   Base Driver    │ │
│  │ Driver   │ │ Driver   │ │ Driver   │ │ Driver   │ │   (Abstract)     │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HARDWARE                                          │
│  CPU (x86_64 / ARM64 / RISC-V) │ GPU/NPU │ RAM │ NVMe/SSD │ NIC │ USB    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Boot Process

```
POWER ON
    │
    ▼
UEFI / BIOS POST
    │ Hardware self-test, memory check
    ▼
UMER BOOTLOADER (signed image)
    │
    ├─── show_banner()              Display Umer OS logo and version
    ├─── show_legal_warning()       Condensed liability notice
    ├─── system_check()             Python version ≥ 3.10, platform, RAM
    ├─── verify_kernel(path, hash)  SHA3-256 of kernel image vs trust store
    └─── load_kernel()              Import + instantiate UmerKernel
             │
             ▼
    UmerKernel.__init__()
         ├── HybridScheduler(quantum_simulator)
         ├── MemoryManager(total_memory_bytes)
         ├── IPCBus()
         └── CapabilityManager()  → SYSTEM_PID=0 gets all capabilities
             │
             ▼
    UmerKernel.init()   [async]
         ├── ipc.start()
         ├── ipc.register(SYSTEM_PID)
         └── scheduler.start(ai_manager=NullAIManager())
             │
             ▼
    INIT SERVICES (spawned as processes, dependency order)
         │
         ├── 1. SecuritySandbox + SecureBoot
         ├── 2. QFS.mount("/")
         ├── 3. NetworkStack.start()
         ├── 4. QuantumAPIGateway.init()
         ├── 5. AIResourceManager.start()  ← replaces NullAIManager
         ├── 6. CloudSyncAgent.start()     (opt-in only)
         └── 7. Package registry scan
             │
             ▼
    LOGIN MANAGER (GUI or CLI)
         │
         ▼
    USER SESSION
         ├── Kivy Desktop Shell
         ├── App Launcher
         └── User Applications
```

---

## 3. IPC Message Flow

Every message in Umer OS is signed and verified. Here's the full flow:

```
Process A (sender)                    Process B (receiver)
    │                                      │
    │  payload = {"action": "start"}       │
    │                                      │
    ├── IPCBus.send(src=A, dst=B,          │
    │              payload=payload)        │
    │         │                            │
    │    [IPCBus internal]                 │
    │    msg = IPCMessage(src=A, dst=B,    │
    │                     payload=payload) │
    │    msg.sign(self._key)               │
    │    # HMAC-SHA256 over:               │
    │    # JSON({src,dst,channel,          │
    │    #        payload,ts})             │
    │    queue_B.put(msg)                  │
    │         │                            │
    │         └────────────────────────────┤
    │                                      │
    │                               await IPCBus.receive(B)
    │                                      │
    │                               [IPCBus internal]
    │                               msg.verify(self._key)
    │                               # recompute HMAC
    │                               # compare_digest (timing-safe)
    │                                      │
    │                               if valid: return msg
    │                               else: DROP (log security error)
    │                                      │
    │                               Process B handles msg.payload
```

---

## 4. Memory Management Architecture

```
VIRTUAL ADDRESS SPACE (simulated with Python dict)

 0x0000_0000   ← NULL page (reserved, never allocated)
 0x0000_1000   ← First allocatable page (PAGE_SIZE = 4096 = 0x1000)
     │
     │  [Page allocation: contiguous pages]
     │
     ▼
 ┌──────────────────────────────────────────────────────────────┐
 │  _allocs: Dict[base_addr, (pid, n_pages, requested_size)]    │
 │                                                              │
 │  0x1000 → (pid=1, n_pages=3, size=10240)  ← 3 × 4KiB pages │
 │  0x4000 → (pid=2, n_pages=1, size=100)    ← 1 × 4KiB page  │
 │  0x5000 → (pid=1, n_pages=2, size=7000)   ← 2 × 4KiB pages │
 │  ...                                                          │
 └──────────────────────────────────────────────────────────────┘
     │
     │  _next_address advances on each allocation
     │  (freed addresses are NOT reused in this prototype)
     │  compact() removes orphan page entries
     ▼
 0xFFFF_FFFF   ← End of simulated address space

 TOTAL PAGES = total_memory_bytes ÷ PAGE_SIZE
 FREE PAGES  = TOTAL_PAGES - 1 - Σ(n_pages for all allocations)
```

---

## 5. Quantum Layer Architecture

```
APPLICATION CODE
      │
      │  circuit_ops = [{"gate":"H","qubit":0}, {"gate":"CNOT","control":0,"target":1}]
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    QuantumAPIGateway                            │
│                                                                  │
│   run(circuit_ops, backend="simulator", shots=1024)             │
│         │                                                        │
│         ├── backend == "simulator" ?                             │
│         │       └── _run_local(circuit_ops, shots)              │
│         │             │                                          │
│         │             ▼                                          │
│         │    QuantumCircuitSimulator (NumPy)                     │
│         │    state: complex ndarray[2^n]                         │
│         │    apply_h() → Kronecker(H, I, I, ...)                │
│         │    apply_cnot() → index-permutation                   │
│         │    measure() → weighted random sample                  │
│         │                                                        │
│         └── backend == "ibm" / "aws" / etc. ?  [FUTURE]         │
│                 └── self._backends[backend].run_circuit(...)     │
│                       └── QuantumDevice.run_circuit()  ← TODO   │
└─────────────────────────────────────────────────────────────────┘
      │
      │  result = {"counts": {"0": 512, "3": 512}, "backend": "simulator"}
      ▼
ERROR MITIGATION (optional)
      │
      ├── ReadoutCalibrator.mitigate(raw_counts)
      │       Applies calibration matrix: counts_corrected = M⁻¹ × counts_raw
      │
      └── ZeroNoiseExtrapolator.extrapolate(expectation_fn)
              Runs at λ=1,2,3 → fits polynomial → evaluate at λ=0
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
      │       └── For each task: apply_h(0), measure expectation_z(0)
      │           Blends 50% static priority + 50% quantum probability
      │
      ├── For each task: compute schedule_score
      │       score = quantum_state["superposition"] × priority / (cpu_time + ε)
      │
      └── Select MAX(schedule_score) → dispatch task
              │
              ▼
      task.state = RUNNING
      await task.coroutine(task)
      task.cpu_time += elapsed
      task.state = READY

AI FEEDBACK LOOP (parallel)
      │
      ▼
AIResourceManager (monitoring coroutine)
      │
      ├── record_cpu(pid, measured_usage)     every second
      ├── record_ram(pid, measured_bytes)     every second
      │
      └── predict_task_success(task)
              success_score = 0.5 × (1/(1+crashes))
                            + 0.3 × (1 - predicted_cpu)
                            + 0.2 × static_priority
              → stored in task.quantum_state["superposition"]
```

---

## 7. Security Architecture Detail

```
ZERO-TRUST FLOW: Process requests file access

Process X                 CapabilityManager          FileSystem Service
    │                           │                          │
    │── check("fs.read") ──────▶│                          │
    │                           │                          │
    │                    [grants lookup]                   │
    │                    with self._lock:                  │
    │                      ok = "fs.read" in grants[X]    │
    │                           │                          │
    │         PermissionError ◀─┤ if NOT ok               │
    │         (raised here)     │                          │
    │                           │                          │
    │                True ◀─────┤ if ok                   │
    │                           │                          │
    │── IPCBus.send(X, FS,                                 │
    │           {"op":"read","path":"/data"})              │
    │                           │                          │
    │              [IPCBus signs message with HMAC]        │
    │                                                       │
    │                                    [message arrives]  │
    │                                    msg.verify(key)   │
    │                                    # valid → process │
    │                                    read file         │
    │◀─────────────────────────────────── file bytes ──────┤
```

---

## 8. QFS Storage Flow

```
WRITE FILE: qfs.write_file("/home/user/doc.txt", data)

  data (bytes)
      │
      ▼
QFSCompressor.compress(data)
      │
      ├── Stage 1: LZMA compression
      │       compressed = lzma.compress(data, preset=3)
      │
      ├── Stage 2 [EXPERIMENTAL]: Delta encoding
      │       if self._last is not None:
      │           delta = XOR(data, self._last)
      │           store delta instead of full data
      │
      └── Stage 3: Metadata dedup (via CAS addressing)
              compressed_bytes
                  │
                  ▼
          CASStore.put(compressed_bytes)
                  │
                  ├── address = SHA3-256(compressed_bytes)
                  │
                  ├── if address already in _blocks:
                  │       _refs[address] += 1  ← DEDUPLICATION
                  │       return existing address
                  │
                  └── else:
                          _blocks[address] = compressed_bytes
                          _refs[address] = 1
                          _used += len(compressed_bytes)
                          return address
                              │
                              ▼
                  _files["/home/user/doc.txt"] = address
                  _meta[path] = {size, compressed, mtime}
                  indexer.index(path, data)   ← search index update
```

---

## 9. Data Flow: Complete Request Lifecycle

```
User opens "README.md" in Text Editor
      │
      ▼
AppLauncher.launch_app("text_editor")
      │ registers open event → AIUIAdapter learns usage pattern
      ▼
Text Editor process spawned
   UmerKernel.spawn_process("text_editor", priority=0.6, caps=["fs.read"])
      │
      ▼
Text Editor requests file
   CapabilityManager.check(pid, "fs.read") → OK
      │
      ▼
Text Editor sends IPC message to QFS service
   IPCBus.send(src=editor_pid, dst=qfs_pid, payload={"op":"read","path":"README.md"})
   [message HMAC-signed by IPCBus]
      │
      ▼
QFS service receives and verifies message
   await IPCBus.receive(qfs_pid)
   msg.verify(key) → True
      │
      ▼
QFS reads file
   address = _files["README.md"]
   compressed = CASStore.get(address)
   data = QFSCompressor.decompress(compressed)
      │
      ▼
QFS sends response back to Text Editor
   IPCBus.send(src=qfs_pid, dst=editor_pid, payload={"data": data})
      │
      ▼
Text Editor displays file content to user
```

---

## 10. Module Dependency Graph

```
                        hardware
                           │
                     base_driver.py
                    /      │      \
          keyboard  network  gpu  storage
          _driver  _driver  _driver _driver
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
               _manager              │
                           │    self_healing
                           │
                        qfs.py
                       /   │   \
               cas_store comp  ai_indexer
                           │
                 container_engine.py
                    /          \
              wine_shim   android_container
                           │
                      installer.py
                           │
                     bootloader.py
                           │
                         gui.py
                           │
                    network_stack.py
                           │
                    umer_pkg.py
```

---

## 11. Test Coverage Map

| Module | Test File | Tests | Coverage Areas |
|---|---|---|---|
| `kernel/scheduler.py` | `test_kernel.py` | 20 | Task, TaskState, HybridScheduler, NullAIManager |
| `kernel/memory_manager.py` | `test_kernel.py` | 10 | allocate, free, compact, stats, validation |
| `kernel/ipc_bus.py` | `test_kernel.py` | 11 | send, receive, broadcast, subscribe, sign |
| `kernel/capability_manager.py` | `test_kernel.py` | 11 | register, grant, revoke, check, query |
| `kernel/umer_kernel.py` | `test_kernel.py` | 9 | init, spawn, kill, inject_ai, status |
| `quantum/quantum_sim.py` | `test_quantum_sim.py` | 22 | gates, measurement, Bell state, expectation |
| `quantum/quantum_sim.py` adapters | `test_quantum_sim.py` | 4 | SuperpositionAdapter, EntanglementIPC |
| `ai/umer_ai.py` | `test_ai.py` | 47 | All 6 AI classes, EWMA, governance |
| `security/security.py` | `test_security.py` | 46 | Sandbox, SecureBoot, IPCAuth, crypto |
| `fs/qfs.py` | `test_qfs.py` | 51 | CAS, compressor, indexer, QFS full API |
| `compatibility/*` | `test_compatibility.py` | 42 | ContainerEngine, Wine, Android, syscall |
| `installer/installer.py` | `test_installer.py` | 33 | EULA, backup, copy, bootloader, rollback |

**Total: 305 tests — all passing**

---

*Umer OS Architecture Guide — v0.1.0-alpha*  
*For visual diagrams, see `docs/index.html` (open in a browser)*
