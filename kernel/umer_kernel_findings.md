# UmerKernel — Key Findings

Source: `umer_kernel.py` (1536 lines)
Generated: analysis of architecture + active vs. legacy code split

## Overview

`umer_kernel.py` implements a hybrid, simulation-style operating system kernel in
Python. It combines a classic micro-kernel structure (sysctls, panic handling,
signals, workqueues, credentials, audit, cgroups) with an AI/Quantum execution
layer (AI manager, UI Render Engine, Universal Container, quantum superposition
execution).

Architecture flow:

    FluidicShell -> CommandContext -> UmerKernel

`FluidicShell` is the interactive REPL. `CommandContext` wires shell command
handlers (`cc_*`) to a `kernel` instance. `UmerKernel` is the core.

## Active Code (lines ~1-1058)

### FluidicShell (~L500-555)

- Interactive REPL for issuing commands against the kernel.
- GUI branches: `gui_start` / `startx` -> `desktop`, `gui_android`, `gui_ios`,
  `gui_web`.
- Registry fallback for unknown commands; prints `command not found` at L551.
- `EOFError` handled for clean exit at L553-555.

### CommandContext

- Loads the command registry (`kernel/shell_commands.py`).
- Wires `cc_` command handlers to a `kernel` instance.

### UmerKernel (L650+)

- Header constants: `PAGE_SIZE = 4096`, `_DEFAULT_RAM` (4 GiB, page-aligned).
- `_register_default_sysctls` (L739-764) registers:
  - `kernel.panic_timeout`
  - `kernel.hung_task_timeout`
  - `kernel.warn_limit`
  - `kernel.panic_on_taint`
- `panic()` (L781-800):
  - Fires `panic_notifier`.
  - Taints the kernel.
  - Auto-reboots if `panic_timeout > 0`, otherwise halts.
- `boot()`:
  - Starts softirq.
  - Sets `PID_SYSTEM` credentials.
  - Wires AI manager into the scheduler.
  - Starts IPC.
  - Merged AI/Quantum demo (UI Render Engine, Universal Container, quantum
    superposition execution).
  - Registers init (PID 1000, sandboxed `fs_root="/"`).
  - Mounts VFS: `/` plus `/system`, `/user`, `/tmp`, `/packages`.
  - Crypto round-trip on `/system/secrets.enc`.
- `status()` (L921-927): uptime / tasks / memory / running state.
- `shutdown()` (L928-989): five ordered phases, ends with
  `"=== UmerKernel shut down cleanly ==="`.
- `start_gui_shell(mode='desktop')` (L991+): launches `ui\launch_gui.py`.

## Legacy Code (lines ~1060-1536)

One long commented-out appendix. Per the MERGE NOTE, the AI/Quantum logic was
merged into the live kernel; the appendix is retained for reference only.

Contains old versions of:

- Imports
- Placeholder classes: `TaskState`, `Task`, `NullAIManager`, `HybridScheduler`,
  `QuantumScheduler` (sim), `AIFirewall`, `LocalAIAssistant`, `QFS`, `VFS`
- Old `UmerKernel` class, `run_loop`, and shell handlers

## Key Module References

Imported at L25-36: `kernel.pid_allocator`, `kernel.taint`, `kernel.sysctl`,
`kernel.panic`, `kernel.signals`, `kernel.cgroup`, `kernel.audit`,
`kernel.workqueue`, `kernel.cred`, `kernel.reboot`, `kernel.resource`,
`kernel.softirq`.

Also referenced: `security/sandbox.py`, `ui/launch_gui.py`,
`umer_kernel1.py` (AI/Quantum logic merged per MERGE NOTE).

## Summary

- Active, production path: L1-1058.
- Legacy/reference appendix: L1060-1536.
- Kernel is a Python-based simulator exposing a shell (`FluidicShell`), a
  micro-kernel core (`UmerKernel`), and an AI/Quantum execution layer.
