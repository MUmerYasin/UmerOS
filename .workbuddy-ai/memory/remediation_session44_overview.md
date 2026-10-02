# H16 — `tests/` Harness Framework Split — RESOLVED (Session 44, 2026-09-12)

**Expert:** CodeReviewExpert (Kim) · **Mode:** Agentic · **Files:** `tests/run_lib_tests.py`, `tests/run_root_tests.py`, `tests/run_initrd_tests.py`

## Summary

H16 targeted the test-harness framework split — mixed `unittest` (top-level) vs `pytest`
(`tests/quantum/`), no root pytest config, no CI suite step, and legacy `run_*.py` subset runners
that gave a false "green" signal. As with H7/H11/H13/H14/H15, **drift-reconciliation first** proved
the standard's premise was **substantially stale**.

### Drift-reconciliation findings (verify before edit)

| Claim in standard §9 H16 | Reality (verified) | Action |
|---|---|---|
| No root pytest config | `pyproject.toml` **already has** `[tool.pytest.ini_options]` (testpaths, `pythonpath=["."]`, asyncio_mode, addopts) | ➖ already done (stale) |
| No CI step runs the suite | `ci.yml` Job 1 **already runs** blocking `python -m pytest tests/` + `--cov-fail-under=30`, installs `requirements.txt` | ➖ already done (stale) |
| `tests/quantum/` uses pytest (implies it's the odd one out) | `tests/quantum/` **exists** with its own `conftest.py` + 7 pytest files; pytest collects both styles | ➖ moot (pytest unifies) |
| bundled pytest imports removed `imp` | venv runs **pytest 9.1.1** — breakage resolved by the `pytest>=8` pin | ➖ already done (stale) |
| 3 `run_*.py` run only a subset → false "green" | **TRUE** — `run_lib/root/initrd_tests.py` each exercise only 1–2 modules; referenced only in their own + sibling docstrings, **not by CI** | ✅ converted to pytest shims |
| "4 of 39 modules" | count outdated (~62 `test_*.py` now) | ➖ note corrected |

## Changes applied (the only genuine harness defect)

Converted the 3 legacy `run_*.py` **unittest subset runners** into **DEPRECATED shims** that
delegate to the canonical `pytest tests/`:

- `tests/run_lib_tests.py`, `tests/run_root_tests.py`, `tests/run_initrd_tests.py` → each now runs
  `python -m pytest <repo>/tests` (forwarding any args), with a deprecation header explaining
  pytest is the single canonical runner.
- This removes the "runs only a subset → false green signal" hazard and unifies on **ONE framework**.
- Kept as graceful shims (not deleted) so the few docstring references in `test_initrd.py` /
  `test_lib_cli.py` / `test_root.py` still work.

No other code change was needed: `pytest>=8.0.0` + `pytest-asyncio>=0.23.0` + `pytest-cov>=4.1.0`
were already pinned in `requirements.txt`.

## Verification

- `py_compile tests/run_*.py` → all 3 compile.
- `python tests/run_lib_tests.py --co -q` → delegates to pytest, collects **2178 tests** in ~2.4s.
- `pytest tests/ --co -q` → **2178 tests collected** cleanly (no collection errors) → suite is
  **fully discoverable**; pytest collects both `unittest.TestCase` and pytest styles.
- The blocking CI step fails the build on any test failure (+ `--cov-fail-under=30`), so the
  "full suite green" gate is enforced.

> **Scope note:** Full *execution* greenness is validated in CI (which installs all heavy deps —
> torch/qiskit/transformers). This sandbox lacks them, so a local full run isn't representative.
> The ~8 historical suite failures are tracked/enforced in CI, **not** a harness defect, and are
> out of H16's scope (harness, not individual test logic).

## Bookkeeping (4 surfaces)

1. Standard §9 H16 row (325): 🟡 → 🟢; stale premise (config/CI/quantum dir/`imp`) corrected.
2. Checkpoint `remediation_progress.md`: H16 box (236) `- [ ]` → `- [x]`; NEXT pointer → **H19**.
3. `MEMORY.md`: Decided H16 (13) + YELLOW pointer (24) advanced to **H19**.
4. Daily log `2026-09-12.md`: Session 44 appended (new file for the day).

## Next

**H19** — `ai/assistant.py` + `ai/self_healing.py` + `ai/resource_predictor.py` (no type
hints/docstrings/logging/per-file baseline; duplicated AI stacks: `AIAssistant`≈`LocalAIAssistant`,
`SelfHealingService`≈`SelfHealingEngine`, `ResourcePredictor`≈`AIResourceManager`). Consolidate
into `umer_ai.py`; bring files to baseline or delete; pick one predictor (`AIResourceManager`).
Say **"continues"**.
