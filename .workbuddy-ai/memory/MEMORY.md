# UmerOS — Long-term Project Memory

## Standing conventions (CodeReviewExpert / Kim)
- Review-standard-first: after every study, bump `MainTask/Raw Data/Code Review Standards and Process.md` (§1/§4/§7/§9/§11).
- Authoritative sources: `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + LICENSE/setup.py.

## Decided
- H7 → GPL-3.0 canonical (sweep Apache-2.0 strays to GPLv3).
- H11 → Flutter (Dart) frontend canonical; backend = Python only; `ui/*.py` retired (H25); UI follows HCI Nielsen-10 (§4.8).

## Resumable remediation loop
- Goal: fix all H1–H307; tests in `tests/`; `# [FIX Hxxx]` comments; resumable via checkpoint.
- Checkpoint: `.workbuddy-ai/memory/remediation_progress.md` (307 items). Maintain by Edit (flip `- [ ]`→`- [x]`), never regenerate.
- Test runner: stdlib `unittest` via venv `C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default`. `cryptography` 50.0.0 available in venv.
- Shared CWE-22 guard: `core/path_guard.py` (`safe_child`, `safe_join`, `PathTraversalError`).
- Shared zero-trust guard: `core/capability_gate.py` (`gate` singleton + `require(cap)`) — bridge to `kernel.capability_manager.CapabilityManager`; fail-closed when wired, permissive-with-warning standalone; `set_strict` to deny.
- Project facts: ~735 Python modules; `tests/` runnable via stdlib `unittest` AND pytest>=8 (the old bundled pytest `imp` issue is fixed by the pin — pytest 9.1.1 verified working in the managed venv). CI now lives in `.github/workflows/` (`ci.yml` + `security_scan.yml`). `Old Linux Code/` (~93k) reference-only (excluded from scope).
- Pre-existing broken test to ignore: `tests/test_ai.py` (collection error — `ai.providers` missing `AIConfigManager`); `home` package-shadowing collision (`bin/home.py`/`root/home.py`) — load `home_backup.py` by file path under a unique name in tests.

## Remediation status
- **RED blockers: ALL CLOSED (H1–H307).** Per-cluster detail + bookkeeping live in `remediation_progress.md` (sessions 1–33).
- **YELLOW sweep in progress (session 36+):** H4, H5, H6, H8, H9 done (H55 root cause fixed; bin/* broad-except finalized + lint gate; CI gates implemented per §7). Next = **H7** (license consistency: Apache-2.0 strays in docs), then remaining YELLOW.
- Sessions 1–23 clusters: var/ boot/ path-traversal, fail-open + dummy-crypto, cap-gate (8/8), collection-error reconciliation, bin/proc, H7 GPL sweep, mount (media/mnt), legal/ GPL + consent, initrd/ eval + traversal, kernel/ managers + crypto + sandbox, proc/srv priv-write, installer/ priv-write + fail-open + dataloss, home tar-restore, etc/ priv-write. (Full per-session notes in the checkpoint file.)
- Sessions 24–35 (carried RED + YELLOW): H3/H146/H147 (lib ssl/pam false-positive + cert-expiry), H157/H167/H168 (media/mnt auto-mount + symlink rmtree), H184/H187 (opt), H198 (packages), H215/H216/H217/H221 (quantum), H244/H245/H246 (security), H12/H18/H21/H42 (cross-cutting: API key, OnlineProvider, self-heal, code-signing), H4/H5 (bin host-subprocess sandbox), H6/H55 (core command base signature convergence).

## Folder scope map — hotspots (🟢 fixed / 🟡 yellow / 💭 nit / 🔴 red; blurbs in standard §9)
- boot/ 🟢 H27,H28,H29; 🟡 H30–H34
- bin/ 🟢 H4,H5,H37,H6,H8; 🟡 H35,H36,H38–H40
- build/ 🟢 H42; 🟡 H41,H43–H45
- cloud/ 🟢 H46,H154; 🟡 H47–H49
- compatibility/ 🟡 H50,H52–H54 (H51 🟢)
- core/ 🟢 H55; 🟡 H56,H57
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
