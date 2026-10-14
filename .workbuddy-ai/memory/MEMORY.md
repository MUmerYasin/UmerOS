# UmerOS — Long-term Project Memory

## Conventions (CodeReviewExpert / Kim)
- After every study, bump the standard `MainTask/Raw Data/Code Review Standards and Process.md` (§1/§4/§7/§9/§11).
- Source authority: `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + LICENSE/setup.py.
- **Drift-recon first:** verify the standard's premise against live repo state (scoped Grep/Glob/Read) before editing — many H premises are stale/overstated. Trust `Read` over `Grep`.
- Never batch multiple `Edit` calls on the SAME file in one message (they race); use an assert-first Python `pathlib` script for multi-line same-file edits.
- Backend = Python only; GPL-3.0 canonical (`Licence`→`License`, `Version 3`→`v3`).

## 🔴 RED loop — COMPLETE (2026-10-09 / session 112)
- `MainTask/Raw Data/RED Loop Prompt.md` — 39-item 🔴 checklist, **all RESOLVED** (session 112; full list in the checkpoint). **8 real fixes:** H184 (20 cap-gates in `opt/`), H194 (tar-slip guard), H245 (AV `api_server` `create_app` break), H246 (`security/sandbox.py` cap-gate + `fs_root` no longer "/"), H265/H266 (tar/zip-slip guards + fixed `zipfile.extractall(filter=...)` TypeError on ≥3.12), H267 (`restore_backup` srv-root guard), H268 (`delete_service_tree` `safe_join` containment). Rest were drift. ➡ Resume the 🟡 sweep.
- **⚠ That file reverts repeatedly** (sessions 95–108): regenerated to an earlier state, losing checklist boxes/RESOLVED notes. **Survives:** standard §9 rows + `MEMORY.md`. **Mitigation:** write standard §9 + MEMORY first; treat the checklist as rebuildable (re-apply boxes bottom-up anchored on the NEXT box line, matching `- [x] ` / `- [ ] `).
- Severity source of truth: standard §9 (rows whose Severity == 🔴).

## ⚠ External rewrite strips `[FIX Hxxx]` tags (2026-10-13, s145)
- An external process periodically re-saves sources and **strips the cosmetic `[FIX Hxxx]` comment tags** (H114–H119 *code* intact; also truncated the H77 GFDL note in `feedback/__init__.py`). **Rule: source-invariant tests must pin *code facts* (gate calls, method names, removed-excuse strings), never the tag.** Do not re-add tags. The trail lives in standard §9 + checkpoint + this file.

## Resumable remediation loop (H1–H307)
- Checkpoint: `.workbuddy-ai/memory/remediation_progress.md` (307 items; flip `- [ ]`→`- [x]`, never regenerate). Bookkeeping per study: checkpoint box + NEXT pointer, standard §9 row (color + RESOLVED note), MEMORY pointer + folder map, daily `YYYY-MM-DD.md`.
- Test runner: pytest>=8 via venv `C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default` (QUOTE — has a space). `cryptography` 50.0.0.
- **Full-suite temp dir:** redirecting `TMP`/`TEMP` *into the project* causes **15 false failures** (9 `test_legal_scan`/`test_legal_security`, 6 `test_mnt`): `legal/licenses.py:scan_directory` skips any `.`-prefixed path component; `mnt/fstab.py` whitespace-splits fstab lines so a space in the path (`F:\Pension Person Details\UmerOS`) corrupts field offsets. **Use `TMP=F:/umeros_tmp TEMP=F:/umeros_tmp`** (space-free, dot-free). Use `--junitxml` (basetemp cleanup trips the safe-delete guard and kills the terminal summary).
- Shared guards: `core/path_guard.py` (`safe_child`/`safe_join`/`PathTraversalError`); `core/capability_gate.py` (`gate`/`require(cap)`, fail-closed when wired).
- Project: ~735 Python modules; CI in `.github/workflows/` (`ci.yml`, `security_scan.yml`); `Old Linux Code/` (~93k) reference-only (out of scope).
- Skip pre-existing broken `tests/test_ai.py` (collection error — `ai.providers` missing `AIConfigManager`); `home` package-shadow (`bin/home.py`/`root/home.py`) — load `home_backup.py` by file path under a unique module name in tests.
- CWE-22 / zero-trust norm: fail-closed path traversal + signature verification; many "leaky/dummy-crypto" items were already fixed or false premises.

## Remediation status
- **RED blockers: ALL CLOSED (sessions 1–33). YELLOW sweep in progress (session 36+).**
- **Current pointer (session 149):** `compatibility/ core/ dev/ drivers/ etc/ feedback/ fs/ home/ initrd/ installer/` COMPLETE; now in `kernel/` — **H127 RESOLVED (REAL FIX: registered `TAINT_KERNEL_PANIC` in `kernel/taint.py` (bit 256); `panic()` now uses the imported constant instead of a bare literal; dropped 3 dead taint imports; fixed the stale `kernel/__init__` taint re-export (`TaintFlag`/`TaintFlags`/`TaintReason` → `KernelTaint`/`TAINT_KERNEL_PANIC`); new `tests/test_kernel_panic_taint_h127.py` 20 passed; full `tests/` 3566 testcases / 0 failed)**. Next 💭 **H124** — `kernel/pqcrypto_.py`/`onnxruntime_.py` import-time execution (likely DRIFT after H123). Then H126. Say **'continues'** for H124.
- **⚠ Standard §9 REVERTED (session 84):** live standard = 973 lines / 217 rows (39🔴 63🟢 115🟡) — the 🟢-removal was reverted/replaced externally (file grew 736→673→973). H46 duplicated (stale 🔴 L356 + resolved 🟢 L549). Backup: `Code Review Standards and Process.md.pre-green-removal.bak`. Awaiting user decision on re-removing 🟢 rows.
- **⚠ H62 REGRESSION (found s117):** `drivers/` has **0/75** `[TODAY]` tier labels despite H62 RESOLVED (s76); the labels still hold in `boot/` (23), `bin/` (44), `kernel/` (6), `core/` (1), `etc/` (81). Re-apply on request (same mechanical op as H70).
- H1 (user action, not mine): rotate the leaked OpenRouter key + purge git history.

## Folder scope map — hotspots (🟢 fixed / 🟡 yellow / 💭 nit)
- boot/ 🟢 H27–H34 | bin/ 🟢 H4,H5,H6,H8,H35–H40 | build/ 🟢 H41–H45
- cloud/ 🟢 H46–H49,H154 | compatibility/ 🟢 H50–H54
- core/ 🟢 H55,H56; 💭 H57 | dev/ 🟢 H59,H60; 💭 H61
- drivers/ 🟢 H64,H66–H69; 🟡 H63; 💭 H62,H65
- etc/ 🟢 H5,H70–H73 | examples/ 💭 H74,H75 | feedback/ 🟢 H76–H79 | fs/ 🟢 H80–H82
- home/ 🟢 H83–H87 (COMPLETE) | HostFiles/ 💭 H89
- initrd/ 🟢 H2,H91–H95,H97; 💭 H96 | installer/ 🟢 H98–H104,H106,H108,H109 (COMPLETE)
- kernel/ 🟢 H110–H123 (+ H122,H125 nits), H127; 💭 H124,H126
- legal/ 🟢 H128–H131,H135; 🟡 H132,H136–H141; 💭 H137
- lib/ 🟢 H3,H146,H147; 🟡 H148–H150 | liboqs/ 🟡 H151; 💭 H155
- media/ 🟢 H156,H157; 🟡 H158–H160; 💭 H161–H165
- mnt/ 🟢 H166–H168; 🟡 H169–H171,H176; 💭 H172–H175
- network/ 🟢 H177,H178; 🟡 H179,H180; 💭 H181,H182
- opt/ 🟢 H184–H187; 🟡 H188–H193,H200; 💭 H183
- packages/ 🟢 H194–H198; 🟡 H199,H201,H204 | proc/ 🟢 H205–H208; 🟡 H209–H211; 💭 H212–H214
- quantum/ 🟢 H152,H215–H217,H221; 🟡 H218–H220; 💭 H222–H225
- root/ 🟢 H227; 🟡 H226,H228; 💭 H229–H231 | sbin/ 🟢 H233; 🟡 H232; 💭 H234,H235
- scripts/ 🟡 H236,H237; 💭 H238,H239 | sdk/ 🟡 H240,H241; 💭 H242,H243
- security/ 🟢 H17,H244–H246; 🟡 H247–H254; 💭 H255–H258
- sources/ 🟡 H259–H262; 💭 H263,H264
- srv/ 🟢 H265–H268,H271,H273; 🟡 H269,H270,H272; 💭 H274–H277
- tmp/ 🟢 H281–H283; 🟡 H278–H280; 💭 H284–H287
- tools/ 🟡 H288–H292; 💭 H293–H295 | ui/ 🟢 H90 (H25 legacy flagged)
- usr/ 🟢 H296; 🟡 H297–H300; 💭 H301,H302 | var/ 🟢 H303–H307
