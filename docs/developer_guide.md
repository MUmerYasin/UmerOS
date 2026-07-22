# Umer OS — Developer Guide

**Version:** 0.1.0-alpha | **Audience:** Software developers, OS engineers, contributors  
**Python:** 3.12+ | **Licence:** Apache 2.0

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Repository Structure](#2-repository-structure)
3. [Core API Contracts](#3-core-api-contracts)
4. [Kernel Subsystem](#4-kernel-subsystem)
5. [Quantum Layer](#5-quantum-layer)
6. [AI System](#6-ai-system)
7. [Security Subsystem](#7-security-subsystem)
8. [Quantum Filesystem (QFS)](#8-quantum-filesystem-qfs)
9. [Compatibility Layer](#9-compatibility-layer)
10. [Writing Tests](#10-writing-tests)
11. [Adding a Driver](#11-adding-a-driver)
12. [Contributing Guidelines](#12-contributing-guidelines)
13. [Performance Notes](#13-performance-notes)

---

## 1. Architecture Overview

Umer OS follows a **microkernel architecture** — the kernel core handles only:
- Process scheduling (HybridScheduler)
- Virtual memory management (MemoryManager)
- Inter-process communication (IPCBus)
- Capability-based security (CapabilityManager)

Everything else (drivers, filesystems, AI, networking, UI) runs as **user-space Python services**
that communicate with the kernel via the IPCBus.

```
Process A   Process B   Process C    ... (user space)
    ↕           ↕           ↕
  ┌─────────────────────────────────┐
  │     IPCBus (HMAC-signed)        │
  └──────────┬──────────────────────┘
             ↕
  ┌─────────────────────────────────┐
  │        UmerKernel               │
  │  ┌──────────┐ ┌──────────────┐ │
  │  │Scheduler │ │MemoryManager │ │
  │  └──────────┘ └──────────────┘ │
  │  ┌──────────┐ ┌──────────────┐ │
  │  │CapManager│ │  SecureBoot  │ │
  │  └──────────┘ └──────────────┘ │
  └──────────────────────────────── ┘
             ↕
  ┌─────────────────────────────────┐
  │   Hardware Abstraction Layer    │
  └─────────────────────────────────┘
```

### Key Design Decisions

1. **asyncio everywhere** — the kernel uses `asyncio` for cooperative multitasking.
   `asyncio.Lock` guards all shared state. Do **not** use `threading.Lock` inside async code.

2. **No circular imports** — the dependency graph is strictly layered:
   `hardware → kernel → services → ui/apps`

3. **Fail-safe defaults** — every subsystem has a Null/stub variant that works without
   external dependencies (e.g. `NullAIManager` for the scheduler, `_FallbackBackend` for PQC).

4. **Tier labelling** — every feature must be marked `TODAY`, `EXPERIMENTAL`, or `FUTURE`
   in its docstring.

---

## 2. Repository Structure

```
UmerOS/
├── kernel/                   # Microkernel core
│   ├── umer_kernel.py        # Main kernel orchestrator (UmerKernel class)
│   ├── scheduler.py          # HybridScheduler + Task + TaskState + NullAIManager
│   ├── memory_manager.py     # MemoryManager — page-based virtual memory
│   ├── ipc_bus.py            # IPCBus — HMAC-signed message passing
│   ├── capability_manager.py # CapabilityManager — zero-trust permissions
│   └── drivers/              # Device driver submodules
│       ├── base_driver.py    # DeviceDriver abstract base class
│       ├── keyboard_driver.py
│       ├── network_driver.py
│       ├── gpu_driver.py
│       └── storage_driver.py
│
├── quantum/                  # Quantum simulation layer
│   ├── quantum_sim.py        # QuantumCircuitSimulator + adapters
│   ├── quantum_api.py        # QuantumAPIGateway — routes to sim or QPU
│   ├── error_mitigation.py   # ZNE + ReadoutCalibrator
│   └── crypto_pqc.py         # Post-quantum cryptography (Kyber + Dilithium)
│
├── ai/                       # AI orchestration engine
│   ├── umer_ai.py            # All AI classes (main module)
│   ├── resource_manager.py   # Re-export: AIResourceManager
│   ├── assistant.py          # Re-export: LocalAIAssistant
│   ├── self_healing.py       # Re-export: SelfHealingEngine
│   └── firewall.py           # Re-export: AIFirewall
│
├── security/                 # Security subsystem
│   ├── security.py           # SecuritySandbox + SecureBoot + IPCAuthenticator
│   ├── secure_boot.py        # Re-export: SecureBoot
│   └── ipc_auth.py           # Re-export: IPCAuthenticator
│
├── fs/                       # Quantum Filesystem
│   ├── qfs.py                # QFS + CASStore + QFSCompressor + AIFileIndexer
│   ├── compressor.py         # Re-export: QFSCompressor
│   ├── cas_store.py          # Re-export: CASStore
│   └── ai_indexer.py         # Re-export: AIFileIndexer
│
├── compatibility/            # Cross-platform compatibility
│   └── container_engine.py   # ContainerEngine + WineShim + AndroidContainer
│
├── installer/                # Installation wizard
│   ├── installer.py          # UmerInstaller — EULA + backup + install + rollback
│   ├── warning.txt           # Standalone EULA text
│   └── rollback_tools/       # Restoration utilities
│
├── boot/                     # Boot sequence
│   └── bootloader.py         # Python boot simulation
│
├── ui/                       # Desktop shell
│   └── gui.py                # UmerDesktop (Kivy) + headless fallback
│
├── network/                  # Networking
│   └── network_stack.py      # NetworkStack + DoH + VPN + mDNS + QoS
│
├── cloud/                    # Cloud integration stubs
├── packages/                 # Package manager
├── sdk/                      # Developer SDK
├── tests/                    # All test suites (305 tests)
└── docs/                     # Documentation (you are here)
```

---

## 3. Core API Contracts

These contracts are **frozen** — all code that depends on them must be updated if changed.

### Task (kernel/scheduler.py)

```python
@dataclass
class Task:
    pid:           int             # unique process ID (> 0)
    name:          str             # human-readable name
    priority:      float = 0.5    # [0.0, 1.0] — raises ValueError if out of range
    state:         str = "READY"  # use TaskState constants
    cpu_time:      float = 0.0    # accumulated CPU seconds
    quantum_state: Dict = ...     # {"superposition": float} — AI/quantum score
    coroutine:     Optional[Callable] = None

# TaskState constants (importable class, not enum):
TaskState.READY   = "READY"
TaskState.RUNNING = "RUNNING"
TaskState.BLOCKED = "BLOCKED"
TaskState.DONE    = "DONE"
```

### HybridScheduler (kernel/scheduler.py)

```python
sched = HybridScheduler(quantum_simulator=None)
await sched.add_task(task)                    # enqueue; quantum_state scored by AI
await sched.remove_task(pid) -> Optional[Task]
await sched.get_task(pid) -> Optional[Task]   # non-removing lookup
await sched.tick() -> Optional[Task]          # select next READY task (no execution)
await sched.start(ai_manager=None)            # start background loop
await sched.stop()                            # MUST be awaited — cancel loop task
len(sched)                                    # total task count
```

### MemoryManager (kernel/memory_manager.py)

```python
mm = MemoryManager(total_memory_bytes=N)    # N must be > 0 AND page-aligned (4096)
addr = mm.allocate(size=1024, pid=1)        # returns page-aligned virtual address
mm.free(ptr=addr, pid=1)                    # raises ValueError on double-free
mm.compact() -> int                          # returns orphan pages reclaimed
mm.predict_usage(pid=1) -> int              # AI-hinted bytes estimate
mm.stats() -> dict                          # total_pages, free_pages, used_pages, ...
```

### IPCBus (kernel/ipc_bus.py)

```python
bus = IPCBus()
bus.start()                                  # SYNC — lifecycle hook, no-op today
bus.register(pid)                            # SYNC — idempotent
bus.subscribe(pid, channel)                  # SYNC — no await (critical for tests)
await bus.send(src, dst, payload, channel)   # async directed send
await bus.broadcast(src, channel, payload)   # async fan-out → count returned
await bus.receive(pid, timeout=None)         # async blocking + HMAC verified
bus.try_receive(pid) -> Optional[IPCMessage] # SYNC non-blocking — no event loop needed
bus.sign(payload: dict) -> str               # SYNC HMAC-SHA256 hex of dict
bus.pending(pid) -> int                      # SYNC queue depth
```

### CapabilityManager (kernel/capability_manager.py)

```python
# Module-level export:
SYSTEM_PID: int = 0

cm = CapabilityManager()
cm.register(pid)                             # idempotent — creates empty grant set
cm.grant(pid, capability)                    # add named capability string
cm.grant_many(pid, [cap1, cap2])
cm.revoke(pid, capability) -> bool
cm.revoke_all(pid) -> int                    # returns count revoked
cm.query(pid, capability) -> bool            # NEVER raises — bool only
cm.check(pid, capability) -> bool            # raises PermissionError if denied
cm.list_capabilities(pid) -> FrozenSet[str]
cm.registered_pids() -> List[int]            # sorted ascending
```

### NullAIManager (kernel/scheduler.py — module-level export)

```python
from kernel.scheduler import NullAIManager

class NullAIManager:
    def predict_task_success(self, task) -> float:
        return 0.5   # neutral — must never raise
```

---

## 4. Kernel Subsystem

### UmerKernel Lifecycle

```python
import asyncio
from kernel.umer_kernel import UmerKernel

async def main():
    # Construct — does NOT start anything
    kernel = UmerKernel(
        total_memory_bytes=512 * 1024 * 1024,   # 512 MiB simulated RAM
        quantum_simulator=None                    # or SuperpositionSchedulerAdapter()
    )

    # Start all subsystems
    await kernel.init()

    # Spawn a process (returns PID)
    pid = kernel.spawn_process(
        name="my_service",
        priority=0.8,
        capabilities=["fs.read", "net.send"],
        coroutine=None    # optional async callable for the scheduler
    )

    # Inject AI after boot (replaces NullAIManager)
    from ai.umer_ai import AIResourceManager
    kernel.inject_ai_manager(AIResourceManager())

    # Run for 10 ticks
    await kernel.main_loop(ticks=10)

    # Get system health
    print(kernel.status())

    # Shutdown
    await kernel.shutdown()

asyncio.run(main())
```

### Adding a Custom Coroutine to the Scheduler

```python
from kernel.scheduler import Task, HybridScheduler
import asyncio

async def my_task_coroutine(task: Task) -> None:
    """Called by the scheduler each time this task is selected."""
    print(f"Task {task.pid} running, cpu_time={task.cpu_time:.3f}s")
    await asyncio.sleep(0.01)   # simulate work; yield control

sched = HybridScheduler()

async def run():
    await sched.start()
    task = Task(pid=1, name="worker", priority=0.9, coroutine=my_task_coroutine)
    await sched.add_task(task)
    await asyncio.sleep(0.1)    # let scheduler run
    await sched.stop()

asyncio.run(run())
```

---

## 5. Quantum Layer

### QuantumCircuitSimulator — Complete API

```python
from quantum.quantum_sim import QuantumCircuitSimulator
import numpy as np

sim = QuantumCircuitSimulator(n_qubits=3)

# Single-qubit gates (all return self for chaining)
sim.apply_h(0)           # Hadamard → superposition
sim.apply_x(1)           # Pauli-X (NOT gate)
sim.apply_z(2)           # Pauli-Z (phase flip)
sim.apply_h(0).apply_x(1).apply_z(2)   # chained

# Two-qubit gate
sim.apply_cnot(control=0, target=1)    # entanglement

# Measurement
probs = sim.probabilities()            # np.ndarray shape (2^n,), sums to 1.0
outcome = sim.measure()                # int — collapses state, returns basis index
bit = sim.measure_qubit(0)             # int 0 or 1 — single qubit
ev = sim.expectation_z(0)             # float [-1, 1] — ⟨Z⟩ expectation

# State access
state = sim.state_vector()            # copy of complex ndarray
sim.reset()                            # return to |00...0⟩
```

### QuantumAPIGateway — Routing Circuits

```python
from quantum.quantum_api import QuantumAPIGateway

gw = QuantumAPIGateway()

# Run a simple circuit
result = gw.run(
    circuit_ops=[
        {"gate": "H",    "qubit": 0},
        {"gate": "CNOT", "control": 0, "target": 1},
    ],
    backend="simulator",
    shots=1024
)
print(result)
# {"counts": {"0": 512, "3": 512}, "backend": "simulator", "shots": 1024}
# Note: "0" = |00⟩, "3" = |11⟩ — Bell state!

# Register a future real QPU backend
# gw.register_backend("my_qpu", MyQPUDevice())  # TODO: QPU integration

# Get noise model
noise = gw.get_noise_model("simulator")
# {"depolarizing_rate": 0.01, "readout_error": 0.005, ...}
```

### Error Mitigation

```python
from quantum.error_mitigation import ZeroNoiseExtrapolator, ErrorMitigationPipeline

# Zero-Noise Extrapolation
zne = ZeroNoiseExtrapolator(scale_factors=[1.0, 2.0, 3.0])

def get_expectation(noise_scale: float) -> float:
    """Run circuit at this noise scale and return ⟨Z⟩."""
    sim.reset()
    sim.apply_h(0)
    return sim.expectation_z(0)   # simplified — real ZNE needs noise injection

zero_noise_ev = zne.extrapolate(get_expectation)

# Full pipeline (calibration + ZNE)
pipeline = ErrorMitigationPipeline(n_qubits=2)
mitigated = pipeline.run(
    raw_counts={"0": 480, "3": 520, "1": 12, "2": 8},
    counts_at_scales=[   # optional ZNE
        {"0": 480, "3": 520, "1": 12, "2": 8},   # scale=1
        {"0": 460, "3": 500, "1": 22, "2": 18},  # scale=2
    ]
)
```

---

## 6. AI System

### AIResourceManager — EWMA Predictor

```python
from ai.umer_ai import AIResourceManager
from kernel.scheduler import Task

arm = AIResourceManager(window=20, alpha=0.3)

# Record observations (call periodically from a monitoring coroutine)
arm.record_cpu(pid=1, usage=0.75)       # CPU fraction [0, 1]
arm.record_ram(pid=1, bytes_used=256*1024*1024)   # bytes

# Predict next values (used by HybridScheduler)
cpu_pred = arm.predict_cpu_usage(pid=1)     # → float [0,1]
ram_pred = arm.predict_ram_usage(pid=1)     # → int bytes

# Predict scheduling success (called by HybridScheduler.add_task)
task = Task(pid=1, name="worker", priority=0.8)
score = arm.predict_task_success(task)      # → float [0,1]

# Record a crash (reduces future success scores)
arm.record_crash(pid=1)

# Rebalance (called every kernel tick)
arm.rebalance_resources()    # logs warnings for high-CPU or crash-prone processes
```

### Integrating AI into the Kernel

```python
from kernel.umer_kernel import UmerKernel
from ai.umer_ai import AIResourceManager
import asyncio

async def main():
    kernel = UmerKernel()
    await kernel.init()                        # starts with NullAIManager

    arm = AIResourceManager()
    kernel.inject_ai_manager(arm)              # upgrade to real AI

    # Now spawn processes — AI will score them
    pid = kernel.spawn_process("critical_svc", priority=0.95)

    # Feed CPU samples to the AI (e.g. from a monitoring loop)
    arm.record_cpu(pid, 0.85)
    arm.record_cpu(pid, 0.78)
    arm.record_cpu(pid, 0.82)

    # Scheduler now uses predicted success to order tasks
    await kernel.main_loop(ticks=50)
    await kernel.shutdown()

asyncio.run(main())
```

---

## 7. Security Subsystem

### SecuritySandbox — Per-Process Isolation

```python
from security.security import SecuritySandbox

box = SecuritySandbox(pid=42, allowed_caps=["fs.read"])

box.grant("net.send")          # add a capability
box.revoke("fs.read")          # remove (returns bool)
box.has("net.send")            # → True (non-raising check)
box.check("net.send")          # → True or raises PermissionError
box.all_capabilities()         # → FrozenSet[str]
```

### IPCAuthenticator — Message Signing

```python
from security.security import IPCAuthenticator

auth = IPCAuthenticator()     # generates random 32-byte key

msg = {"action": "start", "pid": 5, "ts": 1234567890}
mac = auth.sign_message(msg)   # → 64-char hex HMAC-SHA256

# On the receiving end:
valid = auth.verify_message(msg, mac)   # → True
tampered = {"action": "stop", "pid": 5, "ts": 1234567890}
valid2 = auth.verify_message(tampered, mac)   # → False

auth.rotate_key()    # old MACs immediately invalid
```

### Capability Constants

```python
from kernel.capability_manager import (
    CAP_FS_READ,    CAP_FS_WRITE,   CAP_FS_ADMIN,
    CAP_NET_SEND,   CAP_NET_RECV,   CAP_NET_ADMIN,
    CAP_GPU_RENDER, CAP_GPU_COMPUTE,
    CAP_QUANTUM_SIM,                             # ✅ TODAY
    CAP_QUANTUM_HW,                              # 🔮 FUTURE — real QPU access
    CAP_AI_INFERENCE, CAP_AI_TRAIN,              # AI_TRAIN requires user consent
    CAP_PROC_SPAWN, CAP_PROC_KILL,
    CAP_DEVICE_USB, CAP_IPC_BROADCAST, CAP_INSTALL
)
```

---

## 8. Quantum Filesystem (QFS)

### Complete Usage Example

```python
from fs.qfs import QFS

qfs = QFS(
    max_store_bytes=512 * 1024 * 1024,   # 512 MiB CAS limit
    lzma_preset=3                          # 1=fast, 9=best ratio
)
qfs.mount("/")

# Write — returns SHA3-256 CAS address
addr = qfs.write_file("/data/report.csv", b"col1,col2\n1,2\n3,4\n")

# Read — raises FileNotFoundError if not found
data = qfs.read_file("/data/report.csv")

# Delete — releases CAS block
qfs.delete_file("/data/report.csv")

# List directory
files = qfs.list_dir("/data/")   # → ["/data/a.txt", "/data/b.csv", ...]

# Semantic search
results = qfs.search("quarterly revenue", top_k=10)   # → List[str] of paths

# Snapshot (copy-on-write)
snap_id = qfs.snapshot()
qfs.write_file("/data/report.csv", b"modified data")
qfs.restore_snapshot(snap_id)   # undo

# Stats
stats = qfs.stats()
# {
#   "files": 42,
#   "total_original_bytes": 1048576,
#   "total_compressed_bytes": 524288,
#   "compression_ratio": 0.5,
#   "space_saving_pct": 50.0,
#   "cas": {"blocks": 40, "used_bytes": 524288, "dedup_savings": 102400},
#   "index": {"indexed_files": 42, "max_entries": 100000}
# }
```

### CASStore — Direct Usage

```python
from fs.qfs import CASStore

store = CASStore(max_size_bytes=256 * 1024 * 1024)

addr = store.put(b"block data")     # → 64-char SHA3-256 hex
data = store.get(addr)              # → bytes (raises KeyError if not found)
exists = store.exists(addr)         # → bool

# Reference counting — block freed when count hits 0
store.put(b"shared")                # ref count = 1
store.put(b"shared")                # ref count = 2
store.release(addr)                 # ref count = 1 → False (still alive)
store.release(addr)                 # ref count = 0 → True (freed)
```

---

## 9. Compatibility Layer

### Running a Linux Binary

```python
from compatibility.container_engine import ContainerEngine

engine = ContainerEngine()
inst = engine.launch("/usr/bin/python3", args=["--version"])
exit_code = inst.wait(timeout=5.0)
print(f"Exit: {exit_code}, PID was: {inst.pid}")
```

### Running a Windows .exe (Requires Wine)

```python
engine = ContainerEngine()
inst = engine.launch("/path/to/app.exe", app_type="windows")
# ContainerInstance has .is_alive(), .terminate(), .resource_usage()
```

### Syscall Translation

```python
from compatibility.container_engine import SyscallTranslator

trans = SyscallTranslator()
posix, args = trans.translate_win32("CreateFile", {"path": "C:\\test.txt"})
# posix = "open", args = {"path": "C:\\test.txt"}

posix, args = trans.translate_android("openFile", {"uri": "content://..."})
# posix = "open"
```

---

## 10. Writing Tests

All tests use Python's stdlib `unittest`. Async tests use `IsolatedAsyncioTestCase`.

### Async Test Template

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

### Sync Test Template

```python
import unittest
from fs.qfs import QFS

class TestQFS(unittest.TestCase):

    def setUp(self):
        self.qfs = QFS(max_store_bytes=16 * 1024 * 1024)
        self.qfs.mount("/")

    def test_write_read(self):
        self.qfs.write_file("/test.txt", b"hello")
        self.assertEqual(self.qfs.read_file("/test.txt"), b"hello")
```

### Rules for QFS / Compression Tests

> ⚠️ **Critical:** Always use **compressible data** (repeated patterns) in tests that
> touch the QFSCompressor or CASStore, not random bytes:

```python
# ✅ CORRECT — fast (repeating pattern, LZMA compresses in milliseconds)
data = b"Umer OS test pattern " * 100

# ❌ WRONG — causes test timeout (random data, LZMA takes forever)
import os
data = os.urandom(256 * 1024)
```

### Running the Test Suite

```bash
# All 305 tests
python -m unittest discover -s tests -v

# Individual suite
python -m unittest tests.test_kernel -v
python -m unittest tests.test_quantum_sim -v
python -m unittest tests.test_ai -v
python -m unittest tests.test_security -v
python -m unittest tests.test_qfs.TestCASStore tests.test_qfs.TestQFSCompressor \
                   tests.test_qfs.TestAIFileIndexer tests.test_qfs.TestQFS -v
python -m unittest tests.test_compatibility -v
python -m unittest tests.test_installer -v
```

---

## 11. Adding a Driver

All drivers inherit from `DeviceDriver` in `kernel/drivers/base_driver.py`.

### Step 1 — Create the Driver Class

```python
# kernel/drivers/my_device_driver.py
from kernel.drivers.base_driver import DeviceDriver
import logging
log = logging.getLogger("UmerOS.Drivers.MyDevice")

class MyDeviceDriver(DeviceDriver):
    """Custom device driver for MyDevice. [TODAY]"""
    driver_name = "my_device"
    driver_version = "0.1.0"

    def __init__(self):
        super().__init__({"type": "custom", "vendor": "MyVendor"})

    def probe(self) -> bool:
        """Return True if the device is found."""
        # Check for device presence (USB ID, /dev/xxx, etc.)
        import os
        return os.path.exists("/dev/my_device")

    def init(self) -> bool:
        """Open the device and prepare for operation."""
        try:
            # Open device file, initialise hardware, etc.
            self._active = True
            log.info("MyDevice initialised.")
            return True
        except OSError as e:
            log.error("MyDevice init failed: %s", e)
            return False

    def read(self, size: int = 64) -> bytes:
        """Read data from the device."""
        # Replace with real hardware read
        return b"mock data"[:size]

    def write(self, data: bytes) -> int:
        """Write data to the device."""
        # Replace with real hardware write
        return len(data)

    def shutdown(self) -> None:
        """Cleanly close the device."""
        self._active = False
        log.info("MyDevice shut down.")
```

### Step 2 — Register with the Kernel

```python
from kernel.umer_kernel import UmerKernel
from kernel.drivers.my_device_driver import MyDeviceDriver
import asyncio

async def main():
    kernel = UmerKernel()
    await kernel.init()

    driver = MyDeviceDriver()
    if driver.probe():
        driver.init()
        pid = kernel.spawn_process(
            "my_device_service",
            priority=0.6,
            capabilities=["device.usb"]
        )
        # Driver runs as a user-space service communicating via IPCBus

    await kernel.shutdown()
```

### Step 3 — Write Tests

```python
# tests/test_my_driver.py
import unittest
from kernel.drivers.my_device_driver import MyDeviceDriver

class TestMyDeviceDriver(unittest.TestCase):
    def test_probe_returns_bool(self):
        d = MyDeviceDriver()
        self.assertIsInstance(d.probe(), bool)

    def test_driver_name(self):
        d = MyDeviceDriver()
        self.assertEqual(d.driver_name, "my_device")

    def test_status_has_required_keys(self):
        d = MyDeviceDriver()
        s = d.status()
        for k in ("driver", "version", "active"):
            self.assertIn(k, s)
```

---

## 12. Contributing Guidelines

1. **Every new file must have a module docstring** with tier label and author.
2. **Every public function/method must have a Google-format docstring** with Args/Returns/Raises.
3. **Every file must include type hints** on all function signatures.
4. **Every new feature must have tests** — no exceptions.
5. **Maintain or exceed 305 tests passing** — PRs that break tests are rejected.
6. **Use `try/except` on all I/O and hardware calls** — never let a driver crash the kernel.
7. **Never hardcode credentials** — use `os.environ` or `os.urandom(32)` for keys.
8. **Quantum features must be marked** — any QPU integration point gets a `# TODO: QPU integration` comment.

### Code Style

```python
# ✅ Good
async def allocate_memory(size: int, pid: int) -> int:
    """Allocate virtual memory for a process.

    Args:
        size: Bytes to allocate. Must be > 0.
        pid:  Owner process ID.

    Returns:
        Page-aligned virtual base address.

    Raises:
        ValueError:  If size <= 0.
        MemoryError: If insufficient free pages remain.
    """
    if size <= 0:
        raise ValueError(f"size must be > 0; got {size}")
    ...

# ❌ Bad — no type hints, no docstring, no error handling
def alloc(s, p):
    return self.mm.allocate(s, p)
```

---

## 13. Performance Notes

### Python Speed Constraints

Python is ~100× slower than C for tight loops. Mitigation strategies used in Umer OS:

| Hot Path | Strategy | Speedup |
|---|---|---|
| Kernel scheduler loop | asyncio cooperative (no threading overhead) | 2–5× |
| QFS compression | LZMA preset=3 (balanced speed/ratio) | — |
| Quantum sim | NumPy vectorised operations | 100× vs pure Python |
| AI predictions | EWMA (O(n) in window size) | — |
| IPC message signing | HMAC-SHA256 (stdlib, C-backed) | — |

### Memory Usage

- The kernel's `MemoryManager` simulates virtual memory using Python dicts.
  Each allocated block uses ~200 bytes of Python overhead per page, plus the actual bytes.
- For production use, consider Cython-compiled hot paths (see `build/build.sh`).

### Scheduling Performance

The `HybridScheduler` selects tasks in O(n) time where n = number of READY tasks.
For large task counts, consider a priority queue (`heapq`) replacement:

```python
# Future optimisation (not yet implemented):
import heapq
# heap = [(score, task)] — O(log n) selection
```

---

*Umer OS Developer Guide — v0.1.0-alpha | Apache 2.0*  
*For end-user documentation, see `user_manual.md`*  
*For architecture diagrams, see `architecture.md`*
