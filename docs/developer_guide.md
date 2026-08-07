# Umer OS — Developer Guide

**Version:** 0.1.0-alpha | **Python:** 3.12+ | **Licence:** Apache 2.0

---

## Table of Contents

1. [Repository Structure](#1-repository-structure)
2. [Core API Contracts](#2-core-api-contracts)
3. [Kernel Usage](#3-kernel-usage)
4. [Quantum Layer Usage](#4-quantum-layer-usage)
5. [AI System Usage](#5-ai-system-usage)
6. [Security Usage](#6-security-usage)
7. [QFS Usage](#7-qfs-usage)
8. [Compatibility Layer Usage](#8-compatibility-layer-usage)
9. [Writing Tests](#9-writing-tests)
10. [Adding a Driver](#10-adding-a-driver)
11. [Contributing Guidelines](#11-contributing-guidelines)

---

## 1. Repository Structure

```
UmerOS/
├── kernel/                   Microkernel core
│   ├── umer_kernel.py        UmerKernel orchestrator
│   ├── scheduler.py          HybridScheduler + Task + TaskState + NullAIManager
│   ├── memory_manager.py     MemoryManager — page-based virtual memory
│   ├── ipc_bus.py            IPCBus — HMAC-signed message passing
│   ├── capability_manager.py CapabilityManager — zero-trust permissions
│   └── drivers/               DeviceDriver + keyboard/network/gpu/storage
│
├── quantum/                  Quantum simulation layer
│   ├── quantum_sim.py         QuantumCircuitSimulator + adapters
│   ├── quantum_api.py         QuantumAPIGateway — routes to sim or QPU
│   ├── error_mitigation.py    ZNE + ReadoutCalibrator
│   └── crypto_pqc.py          Post-quantum crypto (Kyber + Dilithium)
│
├── ai/                        AI orchestration engine
│   └── umer_ai.py             All 6 AI classes (main module)
│
├── security/                  security.py — Sandbox + SecureBoot + IPCAuth
├── fs/                        qfs.py — QFS + CASStore + Compressor + Indexer
├── compatibility/             container_engine.py — Wine/Android/Linux
├── installer/                 installer.py — EULA + backup + install + rollback
├── boot/                      bootloader.py — Python boot simulation
├── ui/                        gui.py — Kivy shell + headless fallback
├── network/                   network_stack.py — DoH + VPN + mDNS + QoS
├── cloud/                     sync_agent.py, ota_updater.py, remote_ai.py
├── packages/                  umer_pkg.py — package manager
├── sdk/                       Developer SDK re-export bindings
├── tests/                     431 tests across 11 suites
└── docs/                      Documentation (you are here)
```

---

## 2. Core API Contracts

### Task (kernel/scheduler.py)

```python
@dataclass
class Task:
    pid:           int
    name:          str
    priority:      float = 0.5    # [0.0, 1.0] — raises ValueError if out of range
    state:         str = "READY"  # use TaskState constants
    cpu_time:      float = 0.0
    quantum_state: Dict = ...     # {"superposition": float}
    coroutine:     Optional[Callable] = None

TaskState.READY / RUNNING / BLOCKED / DONE   # importable string constants
```

### HybridScheduler

```python
sched = HybridScheduler(quantum_simulator=None)
await sched.add_task(task)
await sched.remove_task(pid) -> Optional[Task]
await sched.get_task(pid) -> Optional[Task]
await sched.tick() -> Optional[Task]          # select next READY task, no execution
await sched.start(ai_manager=None)
await sched.stop()                            # MUST be awaited
len(sched)                                     # total task count
```

### MemoryManager

```python
mm = MemoryManager(total_memory_bytes=N)     # N must be > 0 AND page-aligned (4096)
addr = mm.allocate(size=1024, pid=1)
mm.free(ptr=addr, pid=1)                     # raises ValueError on double-free
mm.compact() -> int
mm.predict_usage(pid=1) -> int
mm.stats() -> dict
```

### IPCBus

```python
bus = IPCBus()
bus.start()                                   # SYNC
bus.register(pid)                             # SYNC, idempotent
bus.subscribe(pid, channel)                   # SYNC — no await
await bus.send(src, dst, payload, channel)
await bus.broadcast(src, channel, payload)
await bus.receive(pid, timeout=None)          # HMAC verified
bus.try_receive(pid) -> Optional[IPCMessage]  # SYNC non-blocking
bus.sign(payload: dict) -> str                # SYNC HMAC-SHA256 hex
```

### CapabilityManager

```python
SYSTEM_PID: int = 0   # module-level export

cm = CapabilityManager()
cm.register(pid)                              # idempotent
cm.grant(pid, capability)
cm.query(pid, capability) -> bool             # NEVER raises
cm.check(pid, capability) -> bool             # raises PermissionError
cm.registered_pids() -> List[int]             # sorted
```

---

## 3. Kernel Usage

```python
import asyncio
from kernel.umer_kernel import UmerKernel
from ai.umer_ai import AIResourceManager

async def main():
    kernel = UmerKernel(total_memory_bytes=512 * 1024 * 1024)
    await kernel.init()

    pid = kernel.spawn_process(
        name="my_service", priority=0.8,
        capabilities=["fs.read", "net.send"]
    )

    kernel.inject_ai_manager(AIResourceManager())

    await kernel.main_loop(ticks=10)
    print(kernel.status())
    await kernel.shutdown()

asyncio.run(main())
```

---

## 4. Quantum Layer Usage

```python
from quantum.quantum_sim import QuantumCircuitSimulator
from quantum.quantum_api import QuantumAPIGateway

# Direct simulator use
sim = QuantumCircuitSimulator(n_qubits=2)
sim.apply_h(0).apply_cnot(0, 1)          # Bell state
print(sim.probabilities())               # [0.5, 0, 0, 0.5]

# Via the gateway (auto-sizes qubits per circuit)
gw = QuantumAPIGateway()
result = gw.run(
    [{"gate":"H","qubit":0}, {"gate":"CNOT","control":0,"target":1}],
    backend="simulator", shots=1024
)
print(result["counts"])   # {"0": ~512, "3": ~512}
```

> **Important:** `QuantumAPIGateway._run_local()` dynamically sizes the simulator
> based on `_required_qubits(circuit_ops)`. Never hardcode a fixed qubit count —
> this was a critical bug (Bell-state probability leaked into unused qubits).

### Post-Quantum Crypto

```python
from quantum.crypto_pqc import PostQuantumCrypto

pqc = PostQuantumCrypto()
pk, sk = pqc.generate_keypair()
ct = pqc.encrypt(b"secret", pk)
pt = pqc.decrypt(ct, sk)                 # == b"secret"
sig = pqc.sign(b"message", sk)
ok = pqc.verify(b"message", sig, pk)     # True
```

---

## 5. AI System Usage

```python
from ai.umer_ai import AIResourceManager, LocalAIAssistant, AIFirewall

arm = AIResourceManager(window=20, alpha=0.3)
arm.record_cpu(pid=1, usage=0.75)
score = arm.predict_task_success(task)

assistant = LocalAIAssistant()
assistant.index_files("/home/user/docs")
reply = assistant.ask("optimize resources")

fw = AIFirewall(threshold=0.75)
fw.profile_process(pid=3)
score = fw.check_and_act(pid=3, syscall_trace=["read","write"])
```

---

## 6. Security Usage

```python
from security.security import SecuritySandbox, IPCAuthenticator

box = SecuritySandbox(pid=42, allowed_caps=["fs.read"])
box.grant("net.send")
box.check("net.send")     # True or raises PermissionError

auth = IPCAuthenticator()
mac = auth.sign_message({"action": "start"})
valid = auth.verify_message({"action": "start"}, mac)
```

---

## 7. QFS Usage

```python
from fs.qfs import QFS

qfs = QFS(max_store_bytes=512 * 1024 * 1024, lzma_preset=3)
qfs.mount("/")

addr = qfs.write_file("/data/report.csv", b"col1,col2\n1,2\n")
data = qfs.read_file("/data/report.csv")

snap_id = qfs.snapshot()
qfs.write_file("/data/report.csv", b"modified")
qfs.restore_snapshot(snap_id)   # undo

results = qfs.search("quarterly revenue", top_k=10)
stats = qfs.stats()   # compression_ratio, space_saving_pct, cas, index
```

---

## 8. Compatibility Layer Usage

```python
from compatibility.container_engine import ContainerEngine

engine = ContainerEngine()
inst = engine.launch("/usr/bin/python3", args=["--version"])
exit_code = inst.wait(timeout=5.0)

# Windows .exe (requires Wine)
inst = engine.launch("/path/to/app.exe", app_type="windows")

# Android APK (requires ADB)
inst = engine.launch("/path/to/app.apk", app_type="android")
```

---

## 9. Writing Tests

```python
import unittest
from kernel.scheduler import HybridScheduler, Task

class TestMyFeature(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sched = HybridScheduler()

    async def asyncTearDown(self):
        await self.sched.stop()

    async def test_something(self):
        task = Task(pid=1, name="test", priority=0.5)
        await self.sched.add_task(task)
        self.assertEqual(len(self.sched), 1)
```

> ⚠️ **Critical:** For QFS/compression tests, always use **compressible data**
> (repeated patterns), never `os.urandom()` — random data makes LZMA extremely
> slow and can cause test timeouts.

```python
# ✅ CORRECT — fast
data = b"Umer OS test pattern " * 100

# ❌ WRONG — causes timeout
import os
data = os.urandom(256 * 1024)
```

### Running Tests

```bash
python -m unittest discover -s tests -v          # all 431 tests
python -m unittest tests.test_kernel -v           # single suite
```

---

## 10. Adding a Driver

```python
from kernel.drivers.base_driver import DeviceDriver

class MyDriver(DeviceDriver):
    driver_name = "my_device"
    driver_version = "0.1.0"

    def probe(self) -> bool:
        return True   # detect hardware

    def init(self) -> bool:
        self._active = True
        return True

    def read(self, size: int = 64) -> bytes:
        return b"data"

    def write(self, data: bytes) -> int:
        return len(data)

    def shutdown(self) -> None:
        self._active = False
```

---

## 11. Contributing Guidelines

1. Every new file needs a module docstring with a tier label (`[TODAY]`, `[EXPERIMENTAL]`, `[FUTURE]`).
2. Every public function needs type hints.
3. Every new feature needs tests — maintain or exceed 431 tests passing.
4. Use `try/except` on all I/O and hardware calls.
5. Never hardcode credentials — use `os.urandom(32)` for keys.
6. Mark future QPU integration points with `# TODO: QPU integration`.

---

*Umer OS Developer Guide — v0.1.0-alpha | 431 tests passing*
