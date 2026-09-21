# Session 70 — H54: `compatibility/` two container models (complementary, not duplicate)

**Status:** 💭 RESOLVED · **Expert:** CodeReviewExpert (Kim) · **Loop:** H1–H307 remediation

## Premise vs. live state (drift-recon)
The standard (§9 H54) asserted there are "two divergent container models: the real, used `ContainerEngine`/`ContainerInstance`, and the unused `ZeroTrustContainer`" — implying the latter is dead code that should be reconciled/deleted.

Live findings (corrected — premise was **overstated**):
- `ZeroTrustContainer` is **exported** by `compatibility/__init__.py` (`_IMPORT_PLAN["container"] = ("ZeroTrustContainer",)`), so it is part of the public API surface, not an orphan.
- It has a **dedicated, real test suite**: `tests/test_zero_trust_container.py` (5 cases, all green) that asserts the fail-closed `HARDWARE` gate (H51) — denied without the capability, allowed with it.
- It is the kernel's **intended** hardware-gated execution path: `umer_kernel.py:1660` (`from compatibility.container import ZeroTrustContainer`) and `:1863` (`container = ZeroTrustContainer(legacy_pid, self.capabilities)`) are both present but **commented out** — i.e. an inactive-but-planned path, not dead code.
- The two models are *complementary zero-trust paths with different capability scope*:
  - `ZeroTrustContainer` (`container.py`) — single foreign/legacy binary, enforces `HARDWARE` (fail-closed, H51), syscall translation via `SyscallShim`.
  - `ContainerEngine` (`container_engine.py`) — multi-backend foreign-binary launcher (ELF/.exe/APK), enforces `container.launch` (fail-closed, H52), syscall translation via `SyscallTranslator`.

## Changes applied
💭 (nit) fix — documentation + guardrail, NOT deletion/merge:
1. `compatibility/__init__.py` — added a "Stop-gap containers" header note (lines 26–39) explaining the **two complementary, zero-trust execution paths**, explicitly stating **"Keep the two paths SEPARATE — do not merge their capability gates or syscall shims"** and ending with `[FIX H54]`.
2. `compatibility/container.py` — added a module docstring (lines 14–24) describing `ZeroTrustContainer` as the hardware-gated path, contrasting it with `ContainerEngine`, and repeating the "do not merge" warning + `[FIX H54]`.

No code behaviour changed; the H51 fail-closed gate in `container.py` is untouched. A risky merge of the two models was deliberately avoided — it would have broken `tests/test_zero_trust_container.py` and the kernel's planned wiring.

## Verification
- `python -m py_compile compatibility/__init__.py compatibility/container.py compatibility/syscall_shim.py` → clean.
- `python -m pytest tests/test_zero_trust_container.py -q` → **5 passed** (only a pre-existing, unrelated `SyntaxWarning` from `long_path.py:229` — not touched).
- Import check: both `ZeroTrustContainer` (from `container`) and `ContainerEngine` (from `container_engine`) resolve from `compatibility`. **VERIFY_OK.**

## Bookkeeping (6 surfaces)
- Checkpoint `remediation_progress.md`: H54 box `[x]` (+ RESOLVED(session 70) note).
- Standard §9: H54 💭 row appended RESOLVED note (premise corrected — used/exported/tested; complementary paths; no merge).
- `MEMORY.md`: YELLOW pointer → session 70; folder map `compatibility/ 🟢 H50,H51,H52,H53,H54` (severity corrected BLUE/💭).
- Daily log `2026-09-21.md`: this Session 70 entry.
- This `remediation_session70_overview.md`.
- `compatibility/` sweep is now **COMPLETE**.

## Next
**H56** — `core/` (next open YELLOW; H55 already 🟢): `core/command.py` base `Command` `privileges` field not enforced + the H6/H55 command contract. Say **'continues'** for H56.
