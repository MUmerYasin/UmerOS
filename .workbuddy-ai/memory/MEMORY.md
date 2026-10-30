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
- Test runner: pytest>=8 via venv `C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default` (QUOTE — has a space). `cryptography` 50.0.0. **`requests` 2.34.2 installed in session 206** — `quantum/providers/ibm_provider.py:43` gained an `import requests` in the external re-save of 2026-10-29T17:09, and without it `tests/test_quantum_providers.py` raises a **collection error that aborts the whole run** (you see "1 testcase node, 1 error" instead of ~4800 nodes). If a full run suddenly collapses to 1 node, check `import requests` first.
- **Full-suite temp dir:** redirecting `TMP`/`TEMP` *into the project* causes **15 false failures** (9 `test_legal_scan`/`test_legal_security`, 6 `test_mnt`): `legal/licenses.py:scan_directory` skips any `.`-prefixed path component; `mnt/fstab.py` whitespace-splits fstab lines so a space in the path (`F:\Pension Person Details\UmerOS`) corrupts field offsets. **Use `TMP=F:/umeros_tmp TEMP=F:/umeros_tmp`** (space-free, dot-free) — **and `mkdir -p /f/umeros_tmp` FIRST**: `tempfile.gettempdir()` silently falls back to the space-containing Windows temp dir (`…\Temp\pytest-of-MC Raja Jang`) if the target does not exist, which reintroduces the 6 `test_mnt` false failures. Use `--junitxml` (basetemp cleanup trips the safe-delete guard and kills the terminal summary). **H140:** the full/CI run now targets `tests/ legal/ opt/ sources/ srv/ tmp/` (in-package suites included).
- Shared guards: `core/path_guard.py` (`safe_child`/`safe_join`/`PathTraversalError`); `core/capability_gate.py` (`gate`/`require(cap)`, fail-closed when wired).
- Project: ~735 Python modules; CI in `.github/workflows/` (`ci.yml`, `security_scan.yml`); `Old Linux Code/` (~93k) reference-only (out of scope).
- **Corrected session 185:** `tests/test_ai*.py` (61 cases) collect and pass again — the old "skip broken test_ai.py" note is STALE. `home` package-shadow (`bin/home.py`/`root/home.py`) — load `home_backup.py` by file path under a unique module name in tests.
- CWE-22 / zero-trust norm: fail-closed path traversal + signature verification; many "leaky/dummy-crypto" items were already fixed or false premises.

## Remediation status
- **RED blockers: ALL CLOSED (sessions 1–33). YELLOW sweep in progress (session 36+).**
- **Current pointer (session 209):** `compatibility/ core/ dev/ drivers/ etc/ feedback/ fs/ home/ initrd/ installer/ kernel/ legal/` COMPLETE; `lib/`/`liboqs/` COMPLETE; `media/` COMPLETE; `mnt/` COMPLETE; `network/` COMPLETE; `opt/` H183–H193 done. **`packages/` COMPLETE** (H194–H204). **`proc/` COMPLETE — H205–H214 all done.** **`quantum/` in progress — H218 done** (TLS cert verification + optional CA pinning), **H219 done** (real Cascade replacing oracle reconciliation), **H220 done** (QRNG honestly labelled a simulator; seed + entropy pool wired; `measure(qr,cr)` TypeError fixed), **H222 done** (provider tokens no longer require argv: `--token-file`/`--token-stdin`/`--token-prompt`/env, `--token` deprecated with warning). Pinned by 10 new tests (6+10+12+104+201+10+18+20+24+30 passed). Full run **5062 passed / 8 failed / 0 errors / 72 skipped** (7 known external-rewrite + 1 order-dependent `test_opt_selftest_h192` flake). **⚠ H218 checkpoint gap fixed:** checkpoint had jumped H214 → H222; H219/H220 rows inserted. Next: **H223** (💭 — `quantum/quantum_sim.py:20` second GPL-3.0 header stray).
- **⚠ Standard §9 REVERTED (session 84):** live standard = 973 lines / 217 rows (39🔴 63🟢 115🟡) — the 🟢-removal was reverted/replaced externally (file grew 736→673→973). H46 duplicated (stale 🔴 L356 + resolved 🟢 L549). Backup: `Code Review Standards and Process.md.pre-green-removal.bak`. Awaiting user decision on re-removing 🟢 rows.
- **⚠ H62 REGRESSION (found s117):** `drivers/` has **0/75** `[TODAY]` tier labels despite H62 RESOLVED (s76); the labels still hold in `boot/` (23), `bin/` (44), `kernel/` (6), `core/` (1), `etc/` (81). Re-apply on request (same mechanical op as H70).
- H1 (user action, not mine): rotate the leaked OpenRouter key + purge git history.

- **Known-UNRELATED full-run failures (do NOT re-investigate):** 6 failures from *externally rewritten* files — 5 × `tests/test_legal_pii_h137` (the committed `legal/creator_accounts.example.json` was re-saved mid-session and now carries what looks like real personal data: a PK IBAN, a Gmail address, a phone number) and 1 × `tests/test_lib_pam_h150` (`lib/security.py` lost its "Fail-open modules (H150)" docstring marker). They reproduce standalone in <1s with zero coupling to the folder under study; first observed session 186, still present session 188. Both folders are closed — flagged for the user, not fixed. Additionally, `tests/test_compatibility.py::TestEnvironment::test_selftest_passes` occasionally fails in full-suite (order-dependent flake) but passes in isolation (115/115) — unrelated to any folder under study. **NEW (found session 206):** `tests/test_media_license_h160.py::TestCanonicalLicenseLine::test_every_module_carries_the_canonical_line` now fails because an external process created a whole `media/network/` package (5 modules: `__init__`, `network_credentials`, `network_discovery`, `network_mount`, `network_share`) at **2026-10-29 16:03–16:04** without the canonical license line — `media/` was already COMPLETE (H156–H165), so this is a post-completion external addition. Not fixed (external re-saves would undo it); flagged to the user. **ALSO NEW (session 208):** `tests/test_compatibility.py::TestEnvironmentCommands::test_setx_rejects_values_over_1024_characters` fails because `compatibility/environment.py` was rewritten **mid-session at 2026-10-30 14:26:41** so `setx()` now *crops* a 1025-char value to 1024 and returns True, while the test (mtime 2026-10-29) still expects rejection. Fails in isolation too, so not a flake. Not fixed (external re-write would undo it); flagged to the user. **NOTE (session 209):** that `setx` failure did **not** reproduce in the H222 run — the external rewrite appears to have been reverted. **ALSO (session 209):** `tests/test_opt_selftest_h192.py::test_package_selftests_run_their_children` fails only in full-suite and passes 32/32 when its own file runs alone — order-dependent flake, unrelated to any folder under study.

## Folder scope map — hotspots (🟢 fixed / 🟡 yellow / 💭 nit)
- boot/ 🟢 H27–H34 | bin/ 🟢 H4,H5,H6,H8,H35–H40 | build/ 🟢 H41–H45
- cloud/ 🟢 H46–H49,H154 | compatibility/ 🟢 H50–H54
- core/ 🟢 H55,H56; 💭 H57 | dev/ 🟢 H59,H60; 💭 H61
- drivers/ 🟢 H64,H66–H69; 🟡 H63; 💭 H62,H65
- etc/ 🟢 H5,H70–H73 | examples/ 💭 H74,H75 | feedback/ 🟢 H76–H79 | fs/ 🟢 H80–H82
- home/ 🟢 H83–H87 (COMPLETE) | HostFiles/ 💭 H89
- initrd/ 🟢 H2,H91–H95,H97; 💭 H96 | installer/ 🟢 H98–H104,H106,H108,H109 (COMPLETE)
- kernel/ 🟢 H110–H127 (incl. H122,H125 nits) — sweep COMPLETE
- legal/ 🟢 H128–H141; 💭 H137 (COMPLETE)
- lib/ 🟢 H3,H146,H147,H148,H149,H150 | liboqs/ 🟢 H151,H155
- media/ 🟢 H156–H165 **COMPLETE** (H156,H157,H158,H159,H160,H161,H162,H163,H164,H165)
- mnt/ 🟢 H166–H176 (H166,H167,H168,H169,H170,H171,H172,H173,H174,H175,H176) **COMPLETE**
- network/ 🟢 H177,H178,H179,H180,H181,H182 — **COMPLETE**
- opt/ 🟢 H183–H193; 🟡 H200
- packages/ 🟢 H194–H198,H199,H200,H201,H202,H203,H204 **COMPLETE** | proc/ 🟢 H205–H211; 💭 H212–H214 **COMPLETE**
- quantum/ 🟢 H152,H215–H217,H221; 🟡 H218 ✅,H219 ✅,H220 ✅; 💭 H222 ✅,H223–H225
- root/ 🟢 H227; 🟡 H226,H228; 💭 H229–H231 | sbin/ 🟢 H233; 🟡 H232; 💭 H234,H235
- scripts/ 🟡 H236,H237; 💭 H238,H239 | sdk/ 🟡 H240,H241; 💭 H242,H243
- security/ 🟢 H17,H244–H246; 🟡 H247–H254; 💭 H255–H258
- sources/ 🟡 H259–H262; 💭 H263,H264
- srv/ 🟢 H265–H268,H271,H273; 🟡 H269,H270,H272; 💭 H274–H277
- tmp/ 🟢 H281–H283; 🟡 H278–H280; 💭 H284–H287
- tools/ 🟡 H288–H292; 💭 H293–H295 | ui/ 🟢 H90 (H25 legacy flagged)
- usr/ 🟢 H296; 🟡 H297–H300; 💭 H301,H302 | var/ 🟢 H303–H307
