# UmerOS — Long-term Project Memory

## Conventions
- Backend = Python only; GPL-3.0 canonical (`Licence`→`License`, `Version 3`→`v3`).
- Source authority: `Skills/Context File/umer_os_skills.json` > `MainTask/prompt/*.md` > `MainTask/Raw Data/*.docx` > repo + LICENSE/setup.py.
- **Drift-recon first** — verify the row's premise against live repo state before editing; most premises are stale/overstated. Trust `Read` over `Grep`.
- Never batch multiple `Edit` calls on one file; use assert-first `pathlib` appliers (`text.count(old) == 1`).
- Bookkeeping per study (5 surfaces): checkpoint box + RESOLVED + NEXT pointer, standard §9 note, this file's pointer + folder map, daily `YYYY-MM-DD.md`, delete scratch scripts.

## Loop mechanics
- Severity source of truth: standard §9 rows (🔴/🟡/💭). **🔴 RED loop COMPLETE** (s112, 39/39, `MainTask/Raw Data/RED Loop Prompt.md`); 8 real fixes there: H184, H194, H245, H246, H265/H266, H267, H268.
- Checkpoint `.workbuddy-ai/memory/remediation_progress.md` (307 items; flip `- [ ]`→`- [x]`, append RESOLVED, **never regenerate**).
- **Files that revert externally:** `RED Loop Prompt.md` (loses checklist boxes) and standard §9 (a 🟢-removal was undone, 736→673→973 lines). Write standard §9 + MEMORY **first**; treat the checklist as rebuildable.
- **An external process re-saves sources and strips cosmetic `[FIX Hxxx]` tags.** Rule: source-invariant tests pin *code facts* (gate calls, method names), never the tag. Do not re-add tags.
- H1 (user action): rotate the leaked OpenRouter key + purge git history.

## Test runner
- `"C:/Users/MC Raja Jang/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe" -m pytest tests/ legal/ opt/ sources/ srv/ tmp/ --junitxml=… -q` (venv path has a space — quote it).
- **`mkdir -p /f/umeros_tmp` FIRST**, then `TMP=F:/umeros_tmp TEMP=F:/umeros_tmp`. A TMP inside the project → 15 false failures (`legal/licenses.py` skips dot-prefixed path components; `mnt/fstab.py` whitespace-splits, so the space in `F:\Pension Person Details` corrupts offsets). Use `--junitxml` — basetemp cleanup trips the safe-delete guard.
- If a full run collapses to **1 node**, check `import requests` first (`quantum/providers/ibm_provider.py` needs it; missing → collection error aborts the run).
- Baseline: ~5140 testcase nodes / 0 errors / 72 skipped.
- Guards: `core/path_guard.py` (`safe_child`/`safe_join`), `core/capability_gate.py` (`gate.require`). ~735 Python modules; `Old Linux Code/` (~93k) out of scope.
- `tests/test_ai*.py` collect fine (old "broken" note stale). `home` package-shadow: load `home_backup.py` by path under a unique module name.

## Status
- **Pointer: `quantum/` COMPLETE** (H152, H215–H225). H225 added `quantum/tls.py` — one strict TLS policy (`CERT_REQUIRED` + `check_hostname` + TLS1.2 floor + optional `UMEROS_TLS_CAFILE`, fail-closed) now used by all **22** provider REST call sites; `cloud/auth.py::_tls_context` is a thin alias.
- **Next: `root/` H231** (💭 `root/dotfiles.py:232,240-283` template-name path traversal — `self.home / name` with an unvalidated name), the last item in `root/`; then `sbin/` H232–H235. H226 ✅ (canonical GPL header across 9 `root/*.py` + `README.md`; the row's "Apache-2.0/`Licence`" framing was stale — the real defect was the spelled-out `Version 3`). H228 ✅ (root home created 0700 + `.forward` written 0600 via `os.open`). H229 ✅ (`.bak` written 0600 via `_write_backup`; **found a real bug — `os.write` is text-mode on Windows, so it corrupted CRLF backups; fixed with `O_BINARY` in both `passwd._write_backup` and `mail._write_forward`**). H230 ✅ (`RootHomeManager.ensure` refuses a symlinked path before chmod; CLI reports `ensure failed:` + exit 1).
- Done: `compatibility/ core/ dev/ drivers/ etc/ feedback/ fs/ home/ initrd/ installer/ kernel/ legal/ lib/ liboqs/ media/ mnt/ network/ opt/ packages/ proc/ quantum/`.
- After `root/`: `sbin/`, then scripts/sdk/security/sources/srv/tmp/tools/ui/usr/var.
- ⚠ H62 regression: `drivers/` has 0/75 `[TODAY]` labels (boot 23, bin 44, kernel 6, core 1, etc 81 still fine). Re-apply on request.

## Known-unrelated failures (do NOT re-investigate)
- 5 × `tests/test_legal_pii_h137` (external re-save put PII into `legal/creator_accounts.example.json`), 1 × `tests/test_lib_pam_h150` (docstring marker lost), 1 × `tests/test_media_license_h160` (external `media/network/` package added post-completion without the canonical line).
- Order-dependent flakes: `test_compatibility.py` (`test_selftest_passes`; the `setx` failure appeared s208 and was gone s209), `test_opt_selftest_h192.py::test_package_selftests_run_their_children`.

## Folder map (🟢 fixed / 🟡 yellow / 💭 nit)
- boot 🟢H27–34 | bin 🟢H4–6,H8,H35–40 | build 🟢H41–45 | cloud 🟢H46–49,H154
- compatibility 🟢H50–54 | core 🟢H55,H56,💭H57 | dev 🟢H59,H60,💭H61
- drivers 🟢H64,H66–69,🟡H63,💭H62,H65 | etc 🟢H5,H70–73 | examples 💭H74,H75
- feedback 🟢H76–79 | fs 🟢H80–82 | home 🟢H83–87 | HostFiles 💭H89
- initrd 🟢H2,H91–95,H97,💭H96 | installer 🟢H98–104,H106,H108,H109
- kernel 🟢H110–127 | legal 🟢H128–141,💭H137
- lib 🟢H3,H146–150 | liboqs 🟢H151,H155 | media 🟢H156–165
- mnt 🟢H166–176 | network 🟢H177–182 | opt 🟢H183–193,🟡H200
- packages 🟢H194–204 | proc 🟢H205–211,💭H212–214
- quantum 🟢H152,H215–217,H221,🟡H218✅H219✅H220✅,💭H222✅H223✅H224✅H225✅ — **COMPLETE**
- root 🟢H227,🟡H226✅H228✅,💭H229✅H230✅,H231 | sbin 🟢H233,🟡H232,💭H234,H235
- scripts 🟡H236,H237,💭H238,H239 | sdk 🟡H240,H241,💭H242,H243
- security 🟢H17,H244–246,🟡H247–254,💭H255–258 | sources 🟡H259–262,💭H263,H264
- srv 🟢H265–268,H271,H273,🟡H269,H270,H272,💭H274–277
- tmp 🟢H281–283,🟡H278–280,💭H284–287 | tools 🟡H288–292,💭H293–295
- ui 🟢H90 (H25 legacy) | usr 🟢H296,🟡H297–300,💭H301,H302 | var 🟢H303–307
