# UmerOS — Remediation Session 45 Overview (H19: `ai/` consolidate duplicated AI stacks)

**Expert:** CodeReviewExpert (Kim) · **Mode:** Agentic (resumable H1–H307 loop)
**Date:** 2026-09-12 · **Standard:** `MainTask/Raw Data/Code Review Standards and Process.md` §9 (H19)

## TL;DR
H19 ("`ai/` ships duplicated AI stacks + violates per-file baseline") was **RESOLVED** after drift-reconciliation proved the premise substantially stale. The only genuine remaining defect — a dead, duplicated `ResourcePredictor` — was retired to a deprecated alias of the canonical `AIResourceManager`. No logic with any caller was lost; the `ai` package still imports cleanly and its selftest passes.

## What the standard claimed (H19)
- `ai/assistant.py` / `ai/self_healing.py` violate the per-file baseline (no hints/docstrings/logging/tier labels, use `print()`).
- `ai/` ships three parallel implementations duplicating `ai/umer_ai.py`: `AIAssistant`≈`LocalAIAssistant`, `SelfHealingService`≈`SelfHealingEngine`, `ResourcePredictor`≈`AIResourceManager` (both EWMA + z-score, different `SPIKE_Z_THRESHOLD` 2.0 vs 2.5).
- Consolidate into `umer_ai.py`; pick one predictor.

## What the repo actually showed (drift-reconciliation)
| File | Reality |
|------|---------|
| `ai/assistant.py` | Already a thin shim: `AIAssistant = LocalAIAssistant` alias + `get_chat_service()` → consent-gated `chat_service`. GPL header + H19 docstring. No `print()`. |
| `ai/self_healing.py` | Already refactored: `logging`, type hints, docstrings, `[FIX H21/H12]` `gate.require(CAP_SYS_ADMIN)` gate, **never executes generated code**. It is the deliberate zero-trust *wrapper* over canonical `SelfHealingEngine` — a security enhancement, not blind duplication. The security test imports it. |
| `ai/resource_predictor.py` | 356-line full-featured `ResourcePredictor`, but **ZERO importers** repo-wide. Duplicated canonical `ai/umer_ai.AIResourceManager` (wired into `SelfHealingEngine`/`AIGovernance`/kernel bootstrap `NullAIResourceManager`). Different units + `SPIKE_Z_THRESHOLD` (2.0 vs 2.5), but `AIResourceManager` is the strict superset. |
| `ai/umer_ai.py` | Canonical module: `NullAIResourceManager`, `AIResourceManager` (predictor), `LocalAIAssistant`, `SelfHealingEngine`, `AIFirewall`, `AIGovernance`. Fully hinted/docstringed/logged. |

## Change made
- **`ai/resource_predictor.py`** — rewrote as a DEPRECATED compatibility shim:
  `from ai.umer_ai import AIResourceManager as ResourcePredictor`, with a `# [FIX H19]` note and a docstring explaining the consolidation. Removes ~356 lines of dead duplicate logic; keeps the name importable (reversible); `ai/umer_ai.py` is the single source of truth.
- **`ai/__init__.py`** (line 11) — package-index comment updated to mark `resource_predictor` as a deprecated alias of `AIResourceManager`.
- **`ai/self_healing.py`** — docstring gained an `[FIX H19]` traceability note (canonical gate-wrapped healing service; `SelfHealingEngine` is the one canonical engine).

`assistant.py` and `umer_ai.py` needed no change (already correct).

## Verification
- `ResourcePredictor is ai.umer_ai.AIResourceManager` → **True**.
- Canonical methods resolve (`predict_cpu_usage`, `detect_cpu_spike`); `SPIKE_Z_THRESHOLD` = 2.5.
- `ai.assistant.AIAssistant` → `LocalAIAssistant` (MRO); `ai.self_healing.SelfHealingService` present.
- `ai` package `_selftest()` passes; `__all__` unchanged (no circular import).

## Bookkeeping (4 surfaces)
1. Standard §9 H19 rows 131 & 132: `- [ ]` → `- [x]` (premise corrected).
2. Checkpoint `remediation_progress.md` H19 box (237): `- [ ]` → `- [x]`.
3. Checkpoint NEXT pointer (538): H19 → **H20**.
4. `MEMORY.md`: new Decided H19 line + YELLOW pointer advanced to **H20**.

## Next
H20 — `ai/providers.py` (and the now-canonical-shim `resource_predictor.py`) module docstrings declare `Licence: GPL-3.0 (GNU General Public License Version 3)`; normalize to canonical **GPL-3.0** (`Licence`→`License`, `Version 3`→`v3`, per H7).
