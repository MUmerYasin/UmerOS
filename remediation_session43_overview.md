# H15 — `requirements.txt` Hygiene — RESOLVED (Session 43, 2026-09-11)

**Expert:** CodeReviewExpert (Kim) · **Mode:** Agentic · **File:** `requirements.txt`

## Summary

H15 targeted dependency hygiene in `requirements.txt` — supply-chain risk, non-reproducible
version floats, and UI-tech drift. As with H7/H11/H13/H14, **drift-reconciliation first** showed
the standard's premise was **partially stale**, so the real, verifiable fixes were narrower (and
safer) than the literal row implied.

### Drift-reconciliation findings (verify before edit)

| Claim in standard §9 H15 | Reality (verified) | Action |
|---|---|---|
| `g4f>=0.4.0` — supply-chain + ToS risk | **0 import sites** repo-wide → unused | ✅ REMOVED |
| floating `>` on `fastapi`/`uvicorn`/`httpx` | only these 3 use strict `>` (all else `>=`) | ✅ BOUNDED `<1.0` |
| `kivy` commented → "drop entirely" | already commented; only `kernel/gui.py` imports it (legacy) | ✅ made explicit |
| `black`/`flake8`/`mypy`/`pylint` commented, README tells users to run them | tools **don't exist** in reqs; README Contributing **already** uses `ruff`+`mypy` | ➖ already done (premise stale) |
| — | `setup.py` still hard-ships `kivy>=2.3.0` (L75/L110) | ⏭️ **H22** (out of H15 scope) |

## Changes applied (atomic rewrite of `requirements.txt`)

1. **`g4f` removed** — `g4f>=0.4.0` deleted; comment explains it was unused + supply-chain/ToS risk,
   and points to `ai/umer_ai.OnlineProvider` + `AIGovernance.check_consent` (H18) if ever needed.
2. **3 strict `>` floats bounded** → `httpx>=0.27.0,<1.0`, `fastapi>=0.110.0,<1.0`,
   `uvicorn[standard]>=0.30.0,<1.0`.
3. **Security/transport upper caps** → `cryptography>=42.0.0,<46.0.0`,
   `python-jose[cryptography]>=3.3.0,<4.0.0`, `aiohttp>=3.9.0,<4.0.0`.
4. **`kivy` removal made explicit** — bare commented pin replaced with a note (Flutter canonical,
   H11/H25; `kernel/gui.py` is legacy drift).
5. **Reproducibility policy header** — recommends a hash-pinned `requirements.lock` via
   `pip-compile --generate-hashes` (full `==`+hash lock lives in the lockfile, not hand-guessed).

> **Scope discipline:** I did **not** hand-`==`-pin all 35 deps. Fabricating exact versions/hashes
> offline would risk breaking installs. The reproducible `==`+hash lock is the documented
> `requirements.lock` path (generate via `pip-compile` in CI).

## Verification

- Parsed all **42 active specs** with `packaging.requirements.Requirement` → **ALL VALID** (PEP 440).
- Precise scan: **0 strict `>` floats remain**, **0 active `g4f` dependency lines** (only in comments).
- No source code changed → lint/type-check unaffected.

## Bookkeeping (4 surfaces)

1. Standard §9 H15 row (324): 🟡 → 🟢; stale (d)/(c) premises corrected.
2. Standard §1.1 Dependencies row (38): updated to resolved reality (42 deps; linters gone;
   `g4f` removed; floats bounded; lockfile recommended).
3. Checkpoint `remediation_progress.md`: H15 box (235) `- [ ]` → `- [x]`; NEXT pointer (538) → **H16**.
4. `MEMORY.md`: Decided H15 (12) + YELLOW pointer (24) advanced to **H16**.

## Next

**H16** — `tests/` harness framework split (top-level `test_*.py`+`run_*.py` use `unittest`;
`tests/quantum/` uses pytest; no root pytest config; design source prescribes pytest but the bundled
pytest imports the removed `imp` module). Pick ONE framework (recommend **pytest** — collects
`unittest.TestCase` too), ensure `pyproject [tool.pytest]` (already present) + add a CI `pytest` step,
repin `pytest>=8`, and make the suite discoverable & green in CI (H9). Say **"continues"**.
