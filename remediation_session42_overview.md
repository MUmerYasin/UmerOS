# Session 42 — H14 RESOLVED: README layout drift reconciled + CI doc-drift check

**Date:** 2026-09-11 · **Expert:** CodeReviewExpert (Kim) · **Severity:** 🟡 YELLOW → 🟢

## What was wrong (H14)
The standard claimed README documents an *aspirational* layout whose named modules
"do not exist", with illustrative code examples and false stats (~3,500 LOC / 12 modules).
**Verified the premise** (drift-reconciliation discipline):
- `kernel/scheduler.py`, `kernel/hal.py`, `quantum/simulator.py` **do** exist today.
- Only `kernel/ipc.py`, `security/crypto.py`, `fs/quantum_fs.py`, `ui/shell.py` are missing.
- The *existing* modules don't match the README's example APIs either: real classes are
  `HybridScheduler` (not `Scheduler`) and `StatevectorSimulator` (no `QuantumCircuitSimulator`
  / `apply_hadamard` / `measure` / `qubits=`). So examples are illustrative, not runnable.
- Stats were off by ~77×: **actual ~825 active Python modules / ~270k LOC** (measured).

## Fix
| File | Change |
|------|--------|
| `README.md` | "📌 Documentation status" disclaimer (README = aspiration, **not** a review oracle); 🚧 planned markers on missing tree modules; illustrative notes on Component Details + Code Examples; IPC Broker section marked planned; corrected statistics (~270k LOC / 825+ modules, last-updated 2026-09-11, with approximate-footnote). |
| `scripts/check_readme_drift.py` (**NEW**) | H14 CI gate. Parses fenced `python` blocks; fails if a README example imports a module absent from the tree. Allows `PLANNED_MODULES` (kernel.ipc etc.); skips stdlib/3rd-party. |
| `.github/workflows/ci.yml` | Added Job 6 `doc-drift` running the checker (blocking) — the standard's "add a CI doc-drift check if feasible" deliverable. |

## Verification
- `python scripts/check_readme_drift.py` → **OK** (no phantom-module imports; `kernel.ipc` allowlisted).
- README re-grep: only the allowlisted `kernel.ipc` phantom import remains (clearly marked 🚧 planned).

## Bookkeeping (4 surfaces)
1. Standard §9 H14 row → 🟢 (stale "modules don't exist" premise corrected — 3 exist).
2. Checkpoint box H14 → `- [x]`.
3. Checkpoint NEXT pointer → H14 done, next = **H15**.
4. `MEMORY.md` Decided H14 + YELLOW pointer → H14 resolved, next = H15.

## Scope discipline
H14 = README drift only. The tree has other aspirational entries not exhaustively verified;
the disclaimer + doc-drift CI gate cover the regression class ("open an issue to refresh
actual vs documented" backlog). H15 (`g4f` + floating pins + drop kivy) and H116
(capability-gate + real Flutter launch) remain open.

## Next
**H15** — `requirements.txt` (`g4f>=0.4.0` supply-chain/ToS risk; floating `>=`/`>` pins →
non-reproducible builds; drop `kivy` entirely per H11; align Contributing with enforced
Ruff+Mypy). Say **"continues"**.
