# UmerOS Remediation — Session 22 (kernel/ H110, H111, H112)

Resumed the resumable H1–H307 remediation loop at the next open RED cluster in `kernel/`.
All edits carry `# [FIX Hxxx]` traceability comments; bookkeeping updated on all four surfaces
(checkpoint, standard §9, MEMORY.md folder map + DONE bullet, daily log).

## What changed

### H110 — real subsystems wired into the kernel (was inert)
`kernel/umer_kernel.py` `__init__` built `MemoryManager`, `IPCBus`, and `CapabilityManager` as
no-op `type(...)` stubs while the correctly-built real modules sat unused (the import + wiring was
commented out at L1544-1571 / L1622-1624). Zero-trust capability gating, signed IPC and real memory
accounting were all inert.
- Added real imports (`kernel.memory_manager`, `kernel.ipc_bus`, `kernel.capability_manager`).
- Replaced the three stubs with `MemoryManager(total_memory_bytes=_DEFAULT_RAM)` (4 GiB, page-aligned),
  `IPCBus()`, `CapabilityManager()`.
- `SYSTEM_PID` (0) is omnipotent in the real manager, so the kernel keeps all privileges; `init`
  (PID 1000) now receives a minimal explicit cap set (`fs.read/write`, `proc.spawn`, `ai.inference`,
  `ipc.broadcast`) via `grant_many` during boot.
- Wiring is safe: the kernel only calls `.register()`/`.start()`/`.stats()`/`.free()` (all present on
  the real classes) and `free()` is already guarded by try/except in shutdown.

### H111 — CryptoEngine confirmed real (bookkeeping only)
`CryptoEngine` was already real (Session 3): HMAC-SHA256 `sign`/`verify` (constant-time compare) +
AES-256-GCM `encrypt`/`decrypt`, with `verify` failing closed. Only the standard §9 row was left 🔴 —
bumped to 🟢 this session. `tests/test_crypto_engine.py` already locks the fail-closed behavior.

### H112 — SecuritySandbox now enforces fs_root (was decorative)
`SecuritySandbox.register_process` only stored `{name, fs_root}` and `print`ed — a decorative
zero-trust gate that claimed sandboxing it did not perform (H51 family).
- `register_process` validates a non-empty `fs_root` (raises `ValueError` if empty).
- Added `check_path(pid, path)` / `is_path_allowed(pid, path)` that enforce containment via the shared
  `core.path_guard.safe_join` (CWE-22). An escape raises a new `SecurityViolation` (fail-closed).
- The kernel runs in userspace, so this is a *simulated* VFS-level jail — but the containment contract
  is real and testable, not a no-op.

## Tests
New `tests/test_kernel_security.py` (16 tests, stdlib unittest):
- `TestKernelManagersWired` (5) — managers are the REAL classes; SYSTEM_PID omnipotent; stats real.
- `TestCryptoEngineReal` (5) — tampered/wrong signature rejected; key-bound; roundtrip; non-constant.
- `TestSecuritySandboxEnforcement` (6) — normalized fs_root; in-root allowed; escapes denied; empty/registered checks.

## Verification
- `py_compile` clean on `kernel/umer_kernel.py` + the new test file.
- Targeted: `test_kernel_security` + `test_kernel` + `test_crypto_engine` = **76 passed**.
- Full suite (excl. pre-existing `tests/test_ai.py` collection error) = **1447 passed, 0 failures, 0 errors**.

## Bookkeeping
- `remediation_progress.md`: H110/H112 → `[x]` (H111 already `[x]`).
- Standard §9: H110/H111/H112 → 🟢.
- `MEMORY.md`: `kernel/` → 🟢 H110,H111,H112; Session 22 DONE bullet added.
- Daily log: `2026-08-24.md` Session 22 block.

## Loop status
`kernel/` REDs closed. Next open RED cluster: **legal/ H128, H130, H131, H135** (H129 🟢).
Say **"continues"** to pick it up.
