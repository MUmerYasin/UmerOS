# UmerOS Remediation Loop — Status & Next Cluster

_Last updated: 2026-08-22 (session 7). Resumable checkpoint: `remediation_progress.md`._

## ✅ Cluster 1: Collection errors — CLOSED
Full `pytest tests/` now **collects 1742 tests, 0 errors, exit 0** (was blocked).

Fixes (each carries `# [FIX Hxxx]` comments):
- `quantum/gates.py` — `get_gate` raises `KeyError`; added class aliases `I,X,Y,Z,H,S,T,CX,CZ,CCX,SWAP` + parametric `RX,RY,RZ,PhaseGate`.
- `quantum/circuit_library.py` — `inverse_qft_circuit` alias + `grover_circuit()` (with `_multi_controlled_z` helper).
- `tests/test_dc_v2.py` — hardcoded `UmerOS\quantum\...` path → project-root relative.
- `sources/*` + `sbin/*` — removed `sys.path` self-injection; bare sibling imports → relative.
- `tests/test_sbin.py`/`test_sources.py` — collect; `test_sbin` uses qualified `from sbin.X import`.

Verified **zero regressions** from this work.

## 🔶 Cluster 2: 80 failing tests (surfaced once the suite could collect)
After collection was fixed, a full run shows **80 failed, 1614 passed, 48 skipped**.

| Bucket | Count | Nature | Fix direction |
|---|---|---|---|
| `tests/quantum/*` | ~68 | **API drift.** Tests written against a Qiskit-style API (`Statevector.probabilities_dict()`, `SparsePauliOp.from_list()`, `SamplerV2`/`EstimatorV2`/`PrimitiveJob`, transpiler `CouplingMap`, circuit `Instruction`/`QuantumCircuit` signatures) but the bespoke UmerOS quantum lib implements a different, partial API. **Not H-targeted.** | **Decision needed** (see below) |
| `tests/test_bin.py` + `tests/test_proc.py` | ~12 | **Mixed.** Some POSIX-only-by-design (`DfCommand` uses `os.statvfs("/")` — absent on Windows; `proc` reads real `/proc`). Some genuine source↔test drift (`test_filesystems` expects `'proc'` but lib returns `'nodev/proc'`; `TestDateCommand` `strftime` `TypeError`; tar/cpio/dd return-code assertions). | Skip POSIX-only on non-POSIX + per-test triage of real drift |
| `test_cap_gate.py` | 0 | Pollution resolved in session 6 (`finally: mod.gate = prev`). | — |
| `test_legal_scan.py` | 0 | Session-3 typo fixed this turn (`== 2` → `== 1`). | — |

## 🛠️ What was fixed this turn
- `tests/test_legal_scan.py::test_scan_directory_compliant_with_declaration`: assertion `compliant_files == 2` → `== 1` (only 1 file is written; `scan_directory` logic is correct). **3/3 pass.**

## 🧭 Recommended plan & open decision
1. **Quantum (the big one) — NEEDS YOUR CALL.** Two reconciling strategies:
   - **(A) Rewrite ~68 quantum tests** to match the *shipped* bespoke library API. Lower risk, no architectural change, but the tests stop being a Qiskit-compat check.
   - **(B) Re-architect the quantum library** to implement the Qiskit-style API the tests expect. Large, but makes the SDK genuinely Qiskit-compatible.
2. **`test_bin`/`test_proc` (12)** — proceed independently: skip POSIX-only tests on non-POSIX (aligns with existing `os.name=="posix"` guards) and fix the genuine drift (format + return-code + `strftime`).
3. **H7 licence sweep** — `Licence: Apache 2.0` → `License: GPL-3.0` in `opt/config.py`, `opt/var.py`, `opt/package.py`, `srv/backup.py`, `packages/umer_pkg.py`, `tmp/tmpfs.py`.
4. **Full YELLOW/BLUE sweep** of remaining H-targeted hotspots.

_The loop is resumable: every cluster's state is in `remediation_progress.md` (NEXT section) and the daily log `2026-08-22.md`._
