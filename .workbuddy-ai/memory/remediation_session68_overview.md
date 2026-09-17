# Session 68 — H52 (compatibility/ foreign binaries launched unsandboxed) — RESOLVED

## Premise drift-recon (CONFIRMED, with a collision caught)
The standard §9 row H52 cited `container_engine.py:269,348,435` (`LinuxCompat.launch` / `WineShim.run` / `AndroidContainer.launch_app`) launching ELF/.exe/APK via `subprocess.Popen` with no isolation and inheriting the full parent env. Live: all three confirmed at those roles. The first apply attempt also surfaced a **second** launcher with the same signature tail — `ContainerEngine.launch` (the high-level facade at L659) — which also had to be gated. Both were handled in the corrected script.

## Fix (zero-trust, fail-closed where wired)
Added to `compatibility/container_engine.py` (assert-first script, `_h52_apply2.py`, deleted):
- `from core.capability_gate import gate`; capability constant `CAP_FOREIGN_EXEC = "container.launch"`.
- `from core.capability_gate import gate` bridge; `gate.require(CAP_FOREIGN_EXEC)` is called at the top of every launcher (`_require_launch_capability(sandbox)`). Fail-closed when a `CapabilityManager` is wired **or** `gate.set_strict(True)`; permissive-with-warning otherwise (matches the rest of the cap-gate cluster).
- **Secret-safe env:** `_sanitize_env()` — an explicit `env` is always honoured, but when `env is None` the launcher no longer inherits the *full* parent environment; it passes an allow-listed subset (`PATH`, `HOME`, `USER`, `TERM`, `LANG`, `DISPLAY`, `XDG_RUNTIME_DIR`, `TMPDIR`, …). This blocks leakage of trust material (`UMEROS_OTA_*`, `OPENROUTER_API_KEY`) into untrusted foreign processes.
- **Opt-in POSIX sandbox** (`_sandbox_preexec`): when `sandbox=True` (or repo-wide `UMEROS_COMPAT_SANDBOX=1`), applies `os.unshare(NEWNS|NEWPID|NEWNET)` + `resource.setrlimit` (address-space / CPU / nproc / fsize) via `preexec_fn`. Raises `RuntimeError` on any step so a launch that *asked* to be sandboxed never silently runs unsandboxed; on non-POSIX hosts a requested `sandbox=True` is refused fail-closed.
- **`gate.enforcing` refuses unsandboxed launches outright** — in a hard zero-trust posture, running untrusted foreign code with the launcher's privileges is not permitted.
- The `ContainerEngine.launch` facade accepts `sandbox` and threads it to all three sub-launchers.
- Full chroot/OCI/seccomp-bpf isolation remains the module's documented FUTURE note (EXPERIMENTAL, off by default so wine/adb host-tool launches keep working).

## Verification
- `py_compile` → clean.
- Smoke test (module loaded by file path, repo root on `sys.path`): `LinuxCompat().launch("/missing")` raises `FileNotFoundError` in permissive mode (gate warns + allows); with `gate.set_strict(True)` the same call raises `PermissionError` (fail-closed cap denial). `_sanitize_env({"FOO":"bar"})` returns as-is; `_sanitize_env(None)` returns an allow-listed dict.
- Read-back of all four launcher bodies confirms the gate call, env sanitization, and `preexec_fn` wiring are present and correctly placed.

## Bookkeeping closed (6 surfaces)
1. Checkpoint box H52 → `[x]` (location corrected to `:365,445,547 (+ facade :659)`); RESOLVED note.
2. Checkpoint NEXT header → `session 68`; NEXT pointer → **H53**.
3. Standard §9 row H52 🟡→🟢 (+ RESOLVED note).
4. MEMORY.md YELLOW pointer → session 68; folder map `compatibility/` → `🟢 H50,H51,H52; 🟡 H53,H54`.
5. Daily log `2026-09-17.md` — Session 68 appended.
6. This overview (`remediation_session68_overview.md`).

## Next
**H53** (`compatibility/container.py` + `compatibility/syscall_shim.py` — both files skip the per-file baseline: `print` instead of `logging`, no `from __future__ import annotations`, no Google docstrings, no tier label; `syscall_shim.py:13` also does dynamic `self.syscall_table[name](*args)` — must stay allow-listed). Say **'continues'** for H53.
