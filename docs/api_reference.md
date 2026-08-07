# Umer OS — API Reference

## Quick Import Guide

```python
# Kernel
from sdk.kernel_api import UmerKernel, Task, TaskState, HybridScheduler
from sdk.kernel_api import MemoryManager, IPCBus, CapabilityManager, SYSTEM_PID

# Quantum
from sdk.quantum_api import QuantumCircuitSimulator, QuantumAPIGateway
from sdk.quantum_api import PostQuantumCrypto, ZeroNoiseExtrapolator

# AI
from sdk.ai_api import AIResourceManager, LocalAIAssistant, AIFirewall

# UI
from sdk.ui_toolkit import UmerDesktop, TaskBar, AppLauncher
```

## UmerKernel

| Method | Signature | Returns | Status |
|---|---|---|---|
| `__init__` | `(total_memory_bytes=1GiB, quantum_simulator=None)` | UmerKernel | ✅ |
| `init` | `async ()` | None | ✅ |
| `shutdown` | `async ()` | None | ✅ |
| `spawn_process` | `(name, priority=0.5, capabilities=None, coroutine=None)` | int (PID) | ✅ |
| `kill_process` | `(pid)` | bool | ✅ |
| `list_processes` | `()` | List[dict] | ✅ |
| `inject_ai_manager` | `(ai_manager)` | None | ✅ |
| `uptime` | `()` | float | ✅ |
| `status` | `()` | dict | ✅ |

## Task

| Field | Type | Constraint |
|---|---|---|
| `pid` | int | > 0 |
| `name` | str | any |
| `priority` | float | [0.0, 1.0] — ValueError if outside |
| `state` | str | TaskState.{READY,RUNNING,BLOCKED,DONE} |
| `cpu_time` | float | ≥ 0.0 |
| `quantum_state` | dict | {"superposition": float[0,1]} |

## MemoryManager

| Method | Raises |
|---|---|
| `MemoryManager(total_memory_bytes)` | ValueError if not positive + page-aligned |
| `allocate(size, pid)` | ValueError(size≤0), MemoryError(no pages) |
| `free(ptr, pid)` | ValueError(double-free) |
| `compact()` → int | — |
| `predict_usage(pid)` → int | — |
| `stats()` → dict | — |

## IPCBus

| Method | Note |
|---|---|
| `start()` | SYNC |
| `register(pid)` | SYNC, idempotent |
| `subscribe(pid, channel)` | SYNC — no await |
| `async send(src, dst, payload)` → bool | — |
| `async broadcast(src, channel, payload)` → int | — |
| `async receive(pid, timeout=None)` → IPCMessage | HMAC verified |
| `try_receive(pid)` → Optional[IPCMessage] | SYNC, non-blocking |
| `sign(payload: dict)` → str | SYNC, 64-char hex |
| `pending(pid)` → int | SYNC |

## CapabilityManager

| Method | Note |
|---|---|
| `register(pid)` | idempotent |
| `grant(pid, cap)` | — |
| `grant_many(pid, [caps])` | — |
| `revoke(pid, cap)` → bool | — |
| `revoke_all(pid)` → int | — |
| `query(pid, cap)` → bool | never raises |
| `check(pid, cap)` → bool | raises PermissionError |
| `list_capabilities(pid)` → FrozenSet | — |
| `registered_pids()` → List[int] | sorted |

## QuantumCircuitSimulator

| Method | Returns |
|---|---|
| `apply_h(qubit)` | self (chainable) |
| `apply_x(qubit)` | self |
| `apply_z(qubit)` | self |
| `apply_cnot(control, target)` | self |
| `probabilities()` | np.ndarray (sums to 1.0) |
| `measure()` | int (collapses state) |
| `measure_qubit(qubit)` | int 0 or 1 |
| `expectation_z(qubit)` | float [-1, 1] |
| `state_vector()` | complex np.ndarray (copy) |
| `reset()` | None |

## PostQuantumCrypto

| Method | Returns |
|---|---|
| `generate_keypair()` | (public_key: bytes, private_key: bytes) |
| `encrypt(plaintext, public_key)` | bytes |
| `decrypt(ciphertext, private_key)` | bytes |
| `sign(message, private_key)` | bytes |
| `verify(message, signature, public_key)` | bool |
| `.backend` | "liboqs" or "fallback" |

## QFS

| Method | Returns | Raises |
|---|---|---|
| `write_file(path, data)` | str (CAS address) | — |
| `read_file(path)` | bytes | FileNotFoundError |
| `delete_file(path)` | bool | — |
| `exists(path)` | bool | — |
| `list_dir(prefix)` | List[str] | — |
| `search(query, top_k=10)` | List[str] | — |
| `snapshot()` | str (snap_id) | — |
| `restore_snapshot(snap_id)` | bool | — |
| `file_info(path)` | Optional[dict] | — |
| `stats()` | dict | — |
