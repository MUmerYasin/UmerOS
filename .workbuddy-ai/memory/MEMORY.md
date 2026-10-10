# UmerOS — Long-term Project Memory

## Standing conventions (CodeReviewExpert / Kim)
- After every study, bump the standard `MainTask/Raw Data/Code Review Standards and Process.md` (§1/§4/§7/§9/§11).
- Authoritative sources order: `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + LICENSE/setup.py.
- **Drift-recon first:** always verify the standard's premise against live repo state (scoped Grep/Glob/Read) before editing — many H premises are stale/overstated. Trust `Read` over `Grep` for authoritative file state.
- Do NOT batch multiple `Edit` calls on the SAME file in one message (they race); use an assert-first Python `pathlib` script for multi-line same-file edits.
- Backend = Python only; GPL-3.0 canonical (`Licence`→`License`, `Version 3`→`v3`).

## 🔴 RED loop (separate, resumable) — 2026-10-09
- **File:** `MainTask/Raw Data/RED Loop Prompt.md` — self-contained loop prompt + 39-item 🔴 checklist + NEXT pointer.
- Scope: ALL 39 🔴-severity hotspots from the standard §9. Procedure: drift-recon → fix in Python → test → bookkeeping. Say **"continues"** to resume at §NEXT.
- **RED loop progress (session 112):** **🔴 RED LOOP COMPLETE — ALL 39 🔴 items RESOLVED.** H1, H3, H12, H18, H46, H51, H146, H147, H152, H156, H157, H166, H167, H168, H185, H186, H187, H195, H196, H197, H198, H205, H206, H207, H208, H215, H216, H217, H221, H244, H245, H246, H265, H266, H267, H268, H303 all resolved. **Real FIXES (8):** H184 (20 cap-gates in opt/), H194 (version-independent tar-slip guard), H245 (AV api_server `create_app` structural break fixed), H246 (`security/sandbox.py` relabelled + wired to the cap gate + `fs_root` no longer defaults to "/"), H265 (`_assert_safe_tar_members` tar-slip guard), H266 (`_assert_safe_zip_members` zip-slip guard + fixed the live `zipfile.extractall(filter=...)` TypeError on >=3.12), H267 (`restore_backup` refuses to `rmtree` the resolved srv root), H268 (`srv/hierarchy.py` `delete_service_tree` now contains `service_name` via `safe_join`). **H303: DRIFT** (var/* already use `safe_child`/`safe_join` + H304 cap-gates; `tests/test_var.py` 32 passed). All other 30 were drift. ➡ Next: resume the 🟡 YELLOW loop at **H66**.
- **⚠ RED-loop file reverts repeatedly (sessions 95, 96→99, 100→101, 102→103, 104/105→106, 107→108):** `MainTask/Raw Data/RED Loop Prompt.md` gets regenerated back to an earlier state (session 95: post-session-93; session 99: post-session-H185; session 101: post-session-H195; session 103: post-session-101; session 106: post-session-103; session 108: post-session-106) with a reformatted layout (`  \- ` sub-bullets, sometimes a whole item's Issue+Action collapsed onto the box line). **Survives every revert:** the standard §9 rows and `MEMORY.md`. **Lost every revert:** the checklist boxes + RESOLVED notes (whole-file or, recent sessions, only the most-recent session(s)' edits). **Mitigation:** after each item, (a) always write the standard §9 row + MEMORY first (they persist), and (b) treat the checklist as rebuildable — re-apply lost boxes/notes bottom-up by anchoring on the NEXT box line, matching either `- [x] ` or `- [ ] ` prefix. If the file reverts again, rebuild from MEMORY's progress line.
- Severity source of truth: standard §9 (rows whose Severity == 🔴).

## Resumable remediation loop (H1–H307)
- Checkpoint: `.workbuddy-ai/memory/remediation_progress.md` (307 items; flip `- [ ]`→`- [x]`, never regenerate). 6 bookkeeping surfaces per study: checkpoint box + NEXT pointer, standard §9 row (color + RESOLVED note), MEMORY YELLOW pointer + folder map, daily `YYYY-MM-DD.md`, per-session `remediation_sessionNN_overview.md`.
- Test runner: stdlib `unittest` / pytest>=8 via venv `C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default` (QUOTE the path — it has a space). `cryptography` 50.0.0 present.
- Shared guards: `core/path_guard.py` (`safe_child`/`safe_join`/`PathTraversalError`); `core/capability_gate.py` (`gate`/`require(cap)`, fail-closed when wired).
- Project facts: ~735 Python modules; CI in `.github/workflows/` (`ci.yml`, `security_scan.yml`); `Old Linux Code/` (~93k) is reference-only (out of scope).
- Pre-existing broken test to skip: `tests/test_ai.py` (collection error — `ai.providers` missing `AIConfigManager`); `home` package-shadow (`bin/home.py`/`root/home.py`) — load `home_backup.py` by file path under a unique module name in tests.
- CWE-22 / zero-trust families: fail-closed path traversal + signature verification are the norm; many "leaky/dummy-crypto" items were already fixed or were false premises.

## Remediation status
- **RED blockers: ALL CLOSED (sessions 1–33).**
- **YELLOW sweep in progress (session 36+).** Large drift-recon resolutions: cloud/ fully 🟢 (H46,H154,H47,H48,H49). Many earlier H-items (H4,H5,H6,H7,H8,H9,H11,H13,H14,H15,H16,H19,H20,H23,H24,H26,H30) were RESOLVED with the premise proven stale/overstated — detail lives in the standard §9 + per-session overview files, not re-duplicated here.
**Current pointer (session 120):** `compatibility/` + `core/` + `dev/` + `drivers/` + `etc/` COMPLETE; `feedback/` in progress — **H76 RESOLVED (REAL FIX + drift: `feedback/` already imported cleanly via guarded relative imports; made the header/docstring honest — 5 missing submodules marked `[PLANNED - not implemented]` + `[STUB]` declared; new `tests/test_feedback_package.py` 8 passed)**. Next 🟡 **H77** - `feedback/` verbose `License: GPL-3.0 (GNU General Public License Version 3)` strays (2 files) + GFDL reference reconciliation. Say **'continues'** for H77.
- **Standard §9 cleanup (2026-10-09):** all 63 resolved (🟢-severity) hotspot rows were removed from `MainTask/Raw Data/Code Review Standards and Process.md`; §9 now lists ONLY open hotspots (rows skip the removed IDs). Full resolution record remains in the checkpoint `remediation_progress.md`. Backup: `Code Review Standards and Process.md.pre-green-removal.bak`.
- **⚠ Standard §9 REVERTED (session 84):** the live standard is now **973 lines / 217 rows (39🔴 63🟢 115🟡)** — the 🟢-removal edit was reverted/replaced externally (the file grew 736→673→973). H46 is duplicated (stale 🔴 at L356 + resolved 🟢 at L549). Awaiting user decision on whether to re-remove 🟢 rows.
- **⚠ H62 REGRESSION (found session 117):** `drivers/` now has **0/75** `[TODAY]` tier labels despite H62 being marked RESOLVED (session 76). The tier-label convention still holds in `boot/` (23), `bin/` (44), `kernel/` (6), `core/` (1) and now `etc/` (81, H70) — but the drivers/ labels are gone (external revert or never persisted). Re-apply on request (same mechanical op as H70).
- H1 standing user action (not mine): user must rotate the leaked OpenRouter key + purge git history.

## Folder scope map — hotspots (🟢 fixed / 🟡 yellow / 💭 nit)
- boot/ 🟢 H27,H28,H29,H30,H31,H32,H33,H34
- bin/ 🟢 H4,H5,H37,H6,H8,H35,H36,H38,H39,H40
- build/ 🟢 H42,H41,H43,H44,H45
- cloud/ 🟢 H46,H154,H47,H48,H49
- compatibility/ 🟢 H50,H51,H52,H53,H54
- core/ 🟢 H55,H56; 💭 H57
- dev/ 🟢 H59,H60; 💭 H61
- drivers/ 🟢 H64,H66,H67,H68,H69; 🟡 H63; 💭 H62,H65
- etc/ 🟢 H5,H70,H71,H72,H73
- examples/ 💭 H74,H75
- feedback/ 🟢 H76; 🟡 H77; 💭 H78,H79
- fs/ 🟡 H80,H81,H82
- home/ 🟢 H83; 🟡 H84–H88
- HostFiles/ 🟡 H89,H90
- initrd/ 🟢 H2,H91,H92,H93; 🟡 H94,H95,H97
- installer/ 🟢 H98,H99,H100,H101,H102,H103; 🟡 H104–H109
- kernel/ 🟢 H110,H111,H112; 🟡 H113–H127
- legal/ 🟢 H128,H129,H130,H131,H135; 🟡 H132,H136–H141; 💭 H137
- lib/ 🟢 H3,H146,H147; 🟡 H148,H149,H150
- liboqs/ 🟡 H151; 💭 H155
- media/ 🟢 H156,H157; 🟡 H158–H160; 💭 H161–H165
- mnt/ 🟢 H166,H167,H168; 🟡 H169–H171,H176; 💭 H172–H175
- network/ 🟢 H177,H178; 🟡 H179,H180; 💭 H181,H182
- opt/ 🟢 H184,H185,H186,H187; 🟡 H188–H193,H200; 💭 H183
- packages/ 🟢 H194,H195,H196,H197,H198; 🟡 H199,H201,H204
- proc/ 🟢 H205,H206,H207,H208; 🟡 H209,H210,H211; 💭 H212–H214
- quantum/ 🟢 H152,H215,H216,H217,H221; 🟡 H218,H219,H220; 💭 H222–H225
- root/ 🟢 H227; 🟡 H226,H228; 💭 H229,H230,H231
- sbin/ 🟢 H233; 🟡 H232; 💭 H234,H235
- scripts/ 🟡 H236,H237; 💭 H238,H239
- sdk/ 🟡 H240,H241; 💭 H242,H243
- security/ 🟢 H17,H244,H245,H246; 🟡 H247–H254; 💭 H255–H258
- sources/ 🟡 H259,H260,H261,H262; 💭 H263,H264
- srv/ 🟢 H265,H266,H267,H268,H271,H273; 🟡 H269,H270,H272; 💭 H274–H277
- tmp/ 🟢 H281,H282,H283; 🟡 H278,H279,H280; 💭 H284–H287
- tools/ 🟡 H288–H292; 💭 H293–H295
- usr/ 🟢 H296; 🟡 H297,H298,H299,H300; 💭 H301,H302
- var/ 🟢 H303,H304,H305,H306,H307
