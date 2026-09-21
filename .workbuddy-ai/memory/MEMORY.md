# UmerOS — Long-term Project Memory

## Standing conventions (CodeReviewExpert / Kim)
- After every study, bump the standard `MainTask/Raw Data/Code Review Standards and Process.md` (§1/§4/§7/§9/§11).
- Authoritative sources order: `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + LICENSE/setup.py.
- **Drift-recon first:** always verify the standard's premise against live repo state (scoped Grep/Glob/Read) before editing — many H premises are stale/overstated. Trust `Read` over `Grep` for authoritative file state.
- Do NOT batch multiple `Edit` calls on the SAME file in one message (they race); use an assert-first Python `pathlib` script for multi-line same-file edits.
- Backend = Python only; GPL-3.0 canonical (`Licence`→`License`, `Version 3`→`v3`).

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
- **Current pointer (session 71):** `compatibility/` sweep COMPLETE (**H50/H51/H52/H53/H54 🟢**); H54 = two container models documented as complementary zero-trust paths (`HARDWARE` vs `container.launch`), not deleted/merged. Next 🟢 **H57** — `core/` (H55,H56 🟢; H57 = `command.py` tier label + GPL header). Say **'continues'** for H57.
- H1 standing user action (not mine): user must rotate the leaked OpenRouter key + purge git history.

## Folder scope map — hotspots (🟢 fixed / 🟡 yellow / 💭 nit)
- boot/ 🟢 H27,H28,H29,H30,H31,H32,H33,H34
- bin/ 🟢 H4,H5,H37,H6,H8,H35,H36,H38,H39,H40
- build/ 🟢 H42,H41,H43,H44,H45
- cloud/ 🟢 H46,H154,H47,H48,H49
- compatibility/ 🟢 H50,H51,H52,H53,H54
- core/ 🟢 H55,H56; 🟡 H57
- dev/ 🟡 H59,H60,H61
- drivers/ 🟢 H64; 🟡 H62,H63,H66,H69; 💭 H65
- etc/ 🟢 H5,H72,H73; 🟡 H70,H71
- examples/ 💭 H74,H75
- feedback/ 🟡 H76–H79
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
